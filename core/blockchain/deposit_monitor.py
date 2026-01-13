"""USDC deposit monitoring for Polygon."""

import logging
from typing import List
from dataclasses import dataclass

from web3 import Web3

from config import settings
from config.constants import USDC_ADDRESS, USDC_E_ADDRESS, USDC_DECIMALS

logger = logging.getLogger(__name__)

# ERC20 ABI (Transfer event + balanceOf)
ERC20_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": False, "name": "value", "type": "uint256"},
        ],
        "name": "Transfer",
        "type": "event",
    },
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
]


@dataclass
class DepositEvent:
    """Deposit event data."""
    from_address: str
    to_address: str
    amount: float
    tx_hash: str
    block_number: int
    token_address: str


class DepositMonitor:
    """Monitor USDC deposits to user wallets."""

    def __init__(self, rpc_url: str = None):
        """
        Initialize deposit monitor.

        Args:
            rpc_url: Polygon RPC URL
        """
        self.rpc_url = rpc_url or settings.polygon_rpc_url
        self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))

        # Create contract instances for both USDC types
        self.usdc_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(USDC_ADDRESS),
            abi=ERC20_ABI,
        )
        self.usdc_e_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(USDC_E_ADDRESS),
            abi=ERC20_ABI,
        )

    async def get_current_block(self) -> int:
        """Get current block number."""
        return self.w3.eth.block_number

    async def check_deposits(
        self,
        wallet_addresses: List[str],
        from_block: int,
        to_block: int = None,
    ) -> List[DepositEvent]:
        """
        Check for USDC deposits to specified addresses.

        Args:
            wallet_addresses: List of wallet addresses to check
            from_block: Starting block number
            to_block: Ending block number (defaults to latest)

        Returns:
            List of deposit events
        """
        if to_block is None:
            to_block = await self.get_current_block()

        deposits = []

        # Normalize addresses
        addresses_set = {
            Web3.to_checksum_address(addr.lower())
            for addr in wallet_addresses
        }

        # Check both USDC contracts
        for contract, token_addr in [
            (self.usdc_contract, USDC_ADDRESS),
            (self.usdc_e_contract, USDC_E_ADDRESS),
        ]:
            try:
                # Get Transfer events using get_logs (web3 v7 compatible)
                events = contract.events.Transfer.get_logs(
                    from_block=from_block,
                    to_block=to_block,
                )

                for event in events:
                    to_addr = Web3.to_checksum_address(event.args.to)

                    # Check if this transfer is to one of our wallets
                    if to_addr in addresses_set:
                        amount = event.args.value / (10 ** USDC_DECIMALS)

                        deposits.append(DepositEvent(
                            from_address=event.args["from"],
                            to_address=to_addr,
                            amount=amount,
                            tx_hash=event.transactionHash.hex(),
                            block_number=event.blockNumber,
                            token_address=token_addr,
                        ))

                        logger.info(
                            f"Deposit detected: {amount} USDC to {to_addr[:10]}..."
                        )

            except Exception as e:
                logger.error(f"Error checking deposits for {token_addr}: {e}")
                continue

        return deposits

    async def get_usdc_balance(self, address: str) -> float:
        """
        Get total USDC balance for an address (both USDC and USDC.e).

        Args:
            address: Wallet address

        Returns:
            Total USDC balance
        """
        total = 0.0
        checksum_addr = Web3.to_checksum_address(address)

        for contract in [self.usdc_contract, self.usdc_e_contract]:
            try:
                # balanceOf function
                balance = contract.functions.balanceOf(checksum_addr).call()
                total += balance / (10 ** USDC_DECIMALS)
            except Exception as e:
                logger.error(f"Error getting balance: {e}")
                continue

        return total

    async def is_connected(self) -> bool:
        """Check if connected to RPC."""
        try:
            return self.w3.is_connected()
        except Exception:
            return False
