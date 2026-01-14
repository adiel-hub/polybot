"""USDC withdrawal management."""

import logging
from typing import Optional
from dataclasses import dataclass

from web3 import Web3
from eth_account import Account

from config import settings
from config.constants import USDC_E_ADDRESS, USDC_DECIMALS, MIN_WITHDRAWAL, MAX_WITHDRAWAL

logger = logging.getLogger(__name__)

# ERC20 ABI with transfer, transferFrom, approve, and balanceOf
ERC20_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_from", "type": "address"},
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "transferFrom",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_spender", "type": "address"},
        ],
        "name": "allowance",
        "outputs": [{"name": "remaining", "type": "uint256"}],
        "type": "function",
    },
]


@dataclass
class WithdrawalResult:
    """Result of withdrawal operation."""
    success: bool
    tx_hash: Optional[str] = None
    error: Optional[str] = None


class WithdrawalManager:
    """Manage USDC withdrawals with gas sponsorship."""

    def __init__(
        self,
        rpc_url: str = None,
        gas_sponsor_key: str = None,
    ):
        """
        Initialize withdrawal manager.

        Args:
            rpc_url: Polygon RPC URL
            gas_sponsor_key: Private key for gas sponsorship
        """
        self.rpc_url = rpc_url or settings.polygon_rpc_url
        self.gas_sponsor_key = gas_sponsor_key or settings.gas_sponsor_private_key

        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))

        # USDC.e contract (Polymarket uses bridged USDC.e)
        self.usdc_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(USDC_E_ADDRESS),
            abi=ERC20_ABI,
        )

        # Gas sponsor account
        if self.gas_sponsor_key:
            self.gas_sponsor_account = Account.from_key(self.gas_sponsor_key)
        else:
            self.gas_sponsor_account = None

    async def withdraw(
        self,
        from_private_key: str,
        to_address: str,
        amount: float,
    ) -> WithdrawalResult:
        """
        Withdraw USDC to external address.

        Note: This uses the user's own wallet to send.
        Gas is paid by the user's wallet (requires POL).

        Args:
            from_private_key: User's wallet private key
            to_address: Destination address
            amount: Amount in USDC

        Returns:
            WithdrawalResult with tx hash or error
        """
        try:
            # Validate amount
            if amount < MIN_WITHDRAWAL:
                return WithdrawalResult(
                    success=False,
                    error=f"Minimum withdrawal is ${MIN_WITHDRAWAL}",
                )

            if amount > MAX_WITHDRAWAL:
                return WithdrawalResult(
                    success=False,
                    error=f"Maximum withdrawal is ${MAX_WITHDRAWAL}",
                )

            # Validate destination address
            if not Web3.is_address(to_address):
                return WithdrawalResult(
                    success=False,
                    error="Invalid destination address",
                )

            # Get sender account
            sender_account = Account.from_key(from_private_key)
            sender_address = sender_account.address

            # Check USDC balance
            balance = self.usdc_contract.functions.balanceOf(sender_address).call()
            balance_usdc = balance / (10 ** USDC_DECIMALS)

            if balance_usdc < amount:
                return WithdrawalResult(
                    success=False,
                    error=f"Insufficient balance: ${balance_usdc:.2f} < ${amount:.2f}",
                )

            # Check if user has POL for gas, if not sponsor it
            user_pol_balance = self.w3.eth.get_balance(sender_address) / 1e18
            required_pol = 0.02  # Estimate ~0.02 POL needed for withdrawal gas

            if user_pol_balance < required_pol:
                logger.info(f"User has insufficient POL ({user_pol_balance:.4f}), sponsoring gas")
                if self.gas_sponsor_account:
                    # Sponsor gas for the user
                    sponsor_result = await self.sponsor_gas(sender_address, required_pol)
                    if not sponsor_result.success:
                        return WithdrawalResult(
                            success=False,
                            error=f"Gas sponsorship failed: {sponsor_result.error}",
                        )
                    logger.info(f"Gas sponsored successfully: {sponsor_result.tx_hash}")

                    # Wait for gas transfer to be mined (up to 60 seconds)
                    import asyncio
                    for i in range(30):  # 30 attempts * 2 seconds = 60 seconds max
                        await asyncio.sleep(2)
                        try:
                            receipt = self.w3.eth.get_transaction_receipt(sponsor_result.tx_hash)
                            if receipt and receipt.status == 1:
                                logger.info(f"Gas transfer confirmed in block {receipt.blockNumber}")
                                break
                        except Exception:
                            pass  # Transaction not yet mined
                    else:
                        logger.warning("Gas transfer taking longer than expected, proceeding anyway")

                    # Verify user now has POL
                    new_balance = self.w3.eth.get_balance(sender_address) / 1e18
                    logger.info(f"User POL balance after sponsorship: {new_balance:.6f} POL")
                else:
                    return WithdrawalResult(
                        success=False,
                        error="Insufficient POL for gas and no gas sponsor configured",
                    )

            # Convert amount to token units
            amount_units = int(amount * (10 ** USDC_DECIMALS))

            # Build transaction
            nonce = self.w3.eth.get_transaction_count(sender_address)
            gas_price = self.w3.eth.gas_price

            # Estimate gas
            tx_data = self.usdc_contract.functions.transfer(
                Web3.to_checksum_address(to_address),
                amount_units,
            )

            estimated_gas = tx_data.estimate_gas({"from": sender_address})

            # Build the transaction
            tx = tx_data.build_transaction({
                "from": sender_address,
                "nonce": nonce,
                "gas": int(estimated_gas * 1.2),  # Add 20% buffer
                "gasPrice": gas_price,
                "chainId": settings.chain_id,
            })

            # Sign transaction
            signed_tx = self.w3.eth.account.sign_transaction(tx, from_private_key)

            # Send transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

            logger.info(
                f"Withdrawal sent: {amount} USDC from {sender_address[:10]}... "
                f"to {to_address[:10]}... TX: {tx_hash.hex()}"
            )

            return WithdrawalResult(
                success=True,
                tx_hash=tx_hash.hex(),
            )

        except Exception as e:
            logger.error(f"Withdrawal failed: {e}")
            return WithdrawalResult(
                success=False,
                error=str(e),
            )

    async def check_tx_status(self, tx_hash: str) -> Optional[str]:
        """
        Check transaction status.

        Args:
            tx_hash: Transaction hash

        Returns:
            "CONFIRMED", "PENDING", or "FAILED"
        """
        try:
            receipt = self.w3.eth.get_transaction_receipt(tx_hash)

            if receipt is None:
                return "PENDING"

            if receipt.status == 1:
                return "CONFIRMED"
            else:
                return "FAILED"

        except Exception as e:
            logger.error(f"Failed to check tx status: {e}")
            return None

    async def wait_for_transaction(
        self,
        tx_hash: str,
        timeout: int = 60,
        poll_interval: float = 2.0,
    ) -> bool:
        """
        Wait for a transaction to be confirmed on-chain.

        Args:
            tx_hash: Transaction hash to wait for
            timeout: Maximum time to wait in seconds
            poll_interval: Time between checks in seconds

        Returns:
            True if confirmed, False if timeout or failed
        """
        import asyncio

        attempts = int(timeout / poll_interval)

        for i in range(attempts):
            try:
                receipt = self.w3.eth.get_transaction_receipt(tx_hash)
                if receipt:
                    if receipt.status == 1:
                        logger.info(f"Transaction {tx_hash[:16]}... confirmed in block {receipt.blockNumber}")
                        return True
                    else:
                        logger.error(f"Transaction {tx_hash[:16]}... failed")
                        return False
            except Exception:
                pass  # Transaction not yet mined

            await asyncio.sleep(poll_interval)

        logger.warning(f"Transaction {tx_hash[:16]}... timed out after {timeout}s")
        return False

    async def get_gas_balance(self, address: str) -> float:
        """
        Get POL (gas) balance for an address.

        Args:
            address: Wallet address

        Returns:
            Balance in POL
        """
        try:
            balance_wei = self.w3.eth.get_balance(
                Web3.to_checksum_address(address)
            )
            return self.w3.from_wei(balance_wei, "ether")
        except Exception as e:
            logger.error(f"Failed to get gas balance: {e}")
            return 0.0

    async def sponsor_gas(
        self,
        to_address: str,
        amount_pol: float = 0.01,
    ) -> WithdrawalResult:
        """
        Send POL for gas to a user wallet.

        Args:
            to_address: Destination wallet
            amount_pol: Amount of POL to send

        Returns:
            WithdrawalResult with tx hash
        """
        if not self.gas_sponsor_account:
            return WithdrawalResult(
                success=False,
                error="Gas sponsorship not configured",
            )

        try:
            sponsor_address = self.gas_sponsor_account.address
            nonce = self.w3.eth.get_transaction_count(sponsor_address)
            gas_price = self.w3.eth.gas_price

            tx = {
                "from": sponsor_address,
                "to": Web3.to_checksum_address(to_address),
                "value": self.w3.to_wei(amount_pol, "ether"),
                "nonce": nonce,
                "gas": 21000,
                "gasPrice": gas_price,
                "chainId": settings.chain_id,
            }

            signed_tx = self.w3.eth.account.sign_transaction(
                tx,
                self.gas_sponsor_key,
            )

            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

            logger.info(f"Gas sponsored: {amount_pol} POL to {to_address[:10]}...")

            return WithdrawalResult(
                success=True,
                tx_hash=tx_hash.hex(),
            )

        except Exception as e:
            logger.error(f"Gas sponsorship failed: {e}")
            return WithdrawalResult(
                success=False,
                error=str(e),
            )

    async def approve_gas_sponsor(
        self,
        user_private_key: str,
    ) -> WithdrawalResult:
        """
        Approve gas sponsor to spend USDC on behalf of user wallet.
        This is a one-time setup that allows gas sponsor to execute withdrawals.

        Args:
            user_private_key: User's wallet private key

        Returns:
            WithdrawalResult with tx hash or error
        """
        if not self.gas_sponsor_account:
            return WithdrawalResult(
                success=False,
                error="Gas sponsor not configured",
            )

        try:
            user_account = Account.from_key(user_private_key)
            user_address = user_account.address
            sponsor_address = self.gas_sponsor_account.address

            # Check if already approved
            current_allowance = self.usdc_contract.functions.allowance(
                Web3.to_checksum_address(user_address),
                Web3.to_checksum_address(sponsor_address),
            ).call()

            # Approve unlimited USDC (max uint256)
            max_uint256 = 2**256 - 1

            if current_allowance >= max_uint256 // 2:
                logger.info(f"Gas sponsor already approved for user {user_address[:10]}...")
                return WithdrawalResult(
                    success=True,
                    tx_hash="already_approved",
                )

            # Build approval transaction
            approve_tx = self.usdc_contract.functions.approve(
                Web3.to_checksum_address(sponsor_address),
                max_uint256,
            ).build_transaction({
                "from": user_address,
                "nonce": self.w3.eth.get_transaction_count(user_address),
                "gas": 100000,
                "gasPrice": self.w3.eth.gas_price,
                "chainId": settings.chain_id,
            })

            # User signs the approval
            signed_tx = self.w3.eth.account.sign_transaction(approve_tx, user_private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

            logger.info(f"USDC approval sent: {tx_hash.hex()}")

            return WithdrawalResult(
                success=True,
                tx_hash=tx_hash.hex(),
            )

        except Exception as e:
            logger.error(f"Approval failed: {e}")
            return WithdrawalResult(
                success=False,
                error=str(e),
            )

    async def withdraw_sponsored(
        self,
        user_address: str,
        to_address: str,
        amount: float,
    ) -> WithdrawalResult:
        """
        Withdraw USDC using gas sponsor to execute transferFrom.
        User must have approved gas sponsor first (via approve_gas_sponsor).
        Gas sponsor pays all fees, single transaction.

        Args:
            user_address: User's wallet address
            to_address: Destination address
            amount: Amount in USDC

        Returns:
            WithdrawalResult with tx hash or error
        """
        if not self.gas_sponsor_account:
            return WithdrawalResult(
                success=False,
                error="Gas sponsor not configured",
            )

        try:
            # Validate amount
            if amount < MIN_WITHDRAWAL:
                return WithdrawalResult(
                    success=False,
                    error=f"Minimum withdrawal is ${MIN_WITHDRAWAL}",
                )

            if amount > MAX_WITHDRAWAL:
                return WithdrawalResult(
                    success=False,
                    error=f"Maximum withdrawal is ${MAX_WITHDRAWAL}",
                )

            # Validate destination address
            if not Web3.is_address(to_address):
                return WithdrawalResult(
                    success=False,
                    error="Invalid destination address",
                )

            # Check user USDC balance
            balance = self.usdc_contract.functions.balanceOf(
                Web3.to_checksum_address(user_address)
            ).call()
            balance_usdc = balance / (10 ** USDC_DECIMALS)

            if balance_usdc < amount:
                return WithdrawalResult(
                    success=False,
                    error=f"Insufficient balance: ${balance_usdc:.2f} < ${amount:.2f}",
                )

            # Check allowance
            sponsor_address = self.gas_sponsor_account.address
            allowance = self.usdc_contract.functions.allowance(
                Web3.to_checksum_address(user_address),
                Web3.to_checksum_address(sponsor_address),
            ).call()

            amount_units = int(amount * (10 ** USDC_DECIMALS))

            if allowance < amount_units:
                return WithdrawalResult(
                    success=False,
                    error=f"Insufficient approval. Please approve gas sponsor first.",
                )

            # Build transferFrom transaction (gas sponsor executes)
            tx_data = self.usdc_contract.functions.transferFrom(
                Web3.to_checksum_address(user_address),
                Web3.to_checksum_address(to_address),
                amount_units,
            )

            # Estimate gas
            estimated_gas = tx_data.estimate_gas({"from": sponsor_address})

            # Build transaction
            nonce = self.w3.eth.get_transaction_count(sponsor_address)
            tx = tx_data.build_transaction({
                "from": sponsor_address,
                "nonce": nonce,
                "gas": int(estimated_gas * 1.2),  # 20% buffer
                "gasPrice": self.w3.eth.gas_price,
                "chainId": settings.chain_id,
            })

            # Gas sponsor signs and sends
            signed_tx = self.w3.eth.account.sign_transaction(tx, self.gas_sponsor_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

            logger.info(
                f"Sponsored withdrawal: {amount} USDC from {user_address[:10]}... "
                f"to {to_address[:10]}... TX: {tx_hash.hex()}"
            )

            return WithdrawalResult(
                success=True,
                tx_hash=tx_hash.hex(),
            )

        except Exception as e:
            logger.error(f"Sponsored withdrawal failed: {e}")
            return WithdrawalResult(
                success=False,
                error=str(e),
            )
