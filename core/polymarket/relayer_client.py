"""Polymarket Relayer API client for gasless operations."""

import hmac
import hashlib
import base64
import time
import json
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

import httpx
from eth_abi import encode
from eth_utils import to_checksum_address

from config import settings

logger = logging.getLogger(__name__)

# Retry settings for RPC calls
RPC_MAX_RETRIES = 3
RPC_INITIAL_DELAY = 2.0  # seconds


async def _rpc_call_with_retry(fn, description: str = "RPC call"):
    """
    Execute an RPC call with exponential backoff retry for rate limits.

    Args:
        fn: Async or sync function to call
        description: Description for logging

    Returns:
        Result of the function call
    """
    import asyncio
    delay = RPC_INITIAL_DELAY

    for attempt in range(RPC_MAX_RETRIES):
        try:
            # Handle both sync and async functions
            result = fn()
            if asyncio.iscoroutine(result):
                return await result
            return result
        except Exception as e:
            error_str = str(e).lower()
            if "rate limit" in error_str and attempt < RPC_MAX_RETRIES - 1:
                logger.warning(
                    f"{description} rate limited, retrying in {delay}s (attempt {attempt + 1}/{RPC_MAX_RETRIES})"
                )
                await asyncio.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                raise

# Polymarket contract addresses on Polygon
USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"  # USDC.e on Polygon (collateral)
USDC_NATIVE_ADDRESS = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"  # Native USDC
CTF_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"  # Conditional Token Framework
NEG_RISK_CTF_ADDRESS = "0xC5d563A36AE78145C45a50134d48A1215220f80a"  # Neg Risk CTF Exchange

# Spender addresses that need USDC approval for trading
CTF_EXCHANGE_ADDRESS = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"  # CTF Exchange
NEG_RISK_ADAPTER_ADDRESS = "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296"  # Neg Risk Adapter

# All spenders that need USDC approval
USDC_SPENDERS = [
    CTF_EXCHANGE_ADDRESS,      # CTF Exchange
    NEG_RISK_CTF_ADDRESS,      # Neg Risk CTF Exchange
    NEG_RISK_ADAPTER_ADDRESS,  # Neg Risk Adapter
]

# Contracts that need CTF operator approval
CTF_OPERATORS = [
    CTF_EXCHANGE_ADDRESS,      # CTF Exchange
    NEG_RISK_CTF_ADDRESS,      # Neg Risk CTF Exchange
    NEG_RISK_ADAPTER_ADDRESS,  # Neg Risk Adapter
]

# ERC20 function signatures
APPROVE_SIGNATURE = "approve(address,uint256)"
TRANSFER_SIGNATURE = "transfer(address,uint256)"

# Relayer endpoint
RELAYER_HOST = "https://relayer-v2.polymarket.com"


class RelayerTxType(Enum):
    """Transaction type for relayer."""
    PROXY = "PROXY"
    SAFE = "SAFE"


@dataclass
class RelayerResult:
    """Result of a relayer operation."""
    success: bool
    tx_hash: Optional[str] = None
    error: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class PolymarketRelayer:
    """
    Client for Polymarket Relayer API.

    Handles gasless operations including:
    - Position redemption after market resolution
    - ERC20 token approvals (USDC)
    - ERC20 token transfers (withdrawals)
    - Batch transaction execution
    """

    def __init__(self):
        self.host = RELAYER_HOST
        self.api_key = settings.poly_builder_api_key
        self.api_secret = settings.poly_builder_secret
        self.api_passphrase = settings.poly_builder_passphrase
        self._client: Optional[httpx.AsyncClient] = None

    def _get_secret_bytes(self) -> bytes:
        """
        Get the API secret as bytes.

        The secret is base64 URL-safe encoded (same format as py-clob-client).
        """
        try:
            # Use URL-safe base64 decode (same as py-clob-client)
            return base64.urlsafe_b64decode(self.api_secret)
        except Exception:
            # If that fails, try standard base64
            try:
                return base64.b64decode(self.api_secret)
            except Exception:
                # Last resort: use raw secret as bytes
                return self.api_secret.encode("utf-8")

    def _sign_request(
        self,
        method: str,
        path: str,
        timestamp: str,
        body: str = "",
    ) -> str:
        """
        Generate HMAC-SHA256 signature for relayer request.

        Uses the same signing method as py-clob-client for compatibility.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: Request path
            timestamp: Unix timestamp string
            body: Request body as string

        Returns:
            URL-safe Base64-encoded signature
        """
        message = timestamp + method.upper() + path + body
        signature = hmac.new(
            self._get_secret_bytes(),
            message.encode("utf-8"),
            hashlib.sha256,
        )
        # Use URL-safe base64 encoding (same as py-clob-client)
        return base64.urlsafe_b64encode(signature.digest()).decode("utf-8")

    def _get_headers(
        self,
        method: str,
        path: str,
        body: str = "",
    ) -> Dict[str, str]:
        """
        Build authenticated headers for relayer request.

        Uses builder-specific headers (POLY_BUILDER_*) as per
        @polymarket/builder-signing-sdk.

        Args:
            method: HTTP method
            path: Request path
            body: Request body

        Returns:
            Headers dict with builder authentication
        """
        timestamp = str(int(time.time()))
        signature = self._sign_request(method, path, timestamp, body)

        return {
            "POLY_BUILDER_API_KEY": self.api_key,
            "POLY_BUILDER_PASSPHRASE": self.api_passphrase,
            "POLY_BUILDER_SIGNATURE": signature,
            "POLY_BUILDER_TIMESTAMP": timestamp,
            "Content-Type": "application/json",
        }

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def is_configured(self) -> bool:
        """Check if relayer credentials are configured."""
        return bool(
            self.api_key
            and self.api_secret
            and self.api_passphrase
        )

    def _encode_erc20_approve(
        self,
        spender: str,
        amount: int,
    ) -> str:
        """
        Encode ERC20 approve function call.

        Args:
            spender: Address to approve
            amount: Amount to approve (in smallest unit)

        Returns:
            Hex-encoded calldata
        """
        # Function selector for approve(address,uint256)
        selector = "0x095ea7b3"
        # Encode parameters
        params = encode(
            ["address", "uint256"],
            [to_checksum_address(spender), amount]
        )
        return selector + params.hex()

    def _encode_erc20_transfer(
        self,
        to_address: str,
        amount: int,
    ) -> str:
        """
        Encode ERC20 transfer function call.

        Args:
            to_address: Recipient address
            amount: Amount to transfer (in smallest unit)

        Returns:
            Hex-encoded calldata
        """
        # Function selector for transfer(address,uint256)
        selector = "0xa9059cbb"
        # Encode parameters
        params = encode(
            ["address", "uint256"],
            [to_checksum_address(to_address), amount]
        )
        return selector + params.hex()

    def _encode_set_approval_for_all(
        self,
        operator: str,
        approved: bool,
    ) -> str:
        """
        Encode ERC1155 setApprovalForAll function call.

        Used to grant operator approval for conditional tokens (CTF).

        Args:
            operator: Operator address to approve
            approved: True to approve, False to revoke

        Returns:
            Hex-encoded calldata
        """
        # Function selector for setApprovalForAll(address,bool)
        selector = "0xa22cb465"
        # Encode parameters
        params = encode(
            ["address", "bool"],
            [to_checksum_address(operator), approved]
        )
        return selector + params.hex()

    def _encode_redeem_positions(
        self,
        condition_id: str,
        index_sets: List[int],
    ) -> str:
        """
        Encode CTF redeemPositions function call.

        Args:
            condition_id: Market condition ID (bytes32)
            index_sets: Outcome index sets to redeem

        Returns:
            Hex-encoded calldata
        """
        # Function selector for redeemPositions(bytes32,uint256[])
        selector = "0x9c8f9f23"
        # Ensure condition_id is bytes32
        if condition_id.startswith("0x"):
            condition_bytes = bytes.fromhex(condition_id[2:])
        else:
            condition_bytes = bytes.fromhex(condition_id)
        # Pad to 32 bytes
        condition_bytes = condition_bytes.rjust(32, b"\x00")
        # Encode parameters
        params = encode(
            ["bytes32", "uint256[]"],
            [condition_bytes, index_sets]
        )
        return selector + params.hex()

    async def _submit_transaction(
        self,
        user_address: str,
        to: str,
        data: str,
        value: int = 0,
    ) -> RelayerResult:
        """
        Submit a single transaction via relayer.

        Args:
            user_address: User's wallet address
            to: Contract address to call
            data: Encoded calldata
            value: ETH value to send (usually 0)

        Returns:
            RelayerResult with transaction hash
        """
        try:
            path = "/submit"
            body = {
                "type": RelayerTxType.PROXY.value,
                "data": {
                    "address": to_checksum_address(user_address),
                    "transactions": [
                        {
                            "to": to_checksum_address(to),
                            "data": data,
                            "value": str(value),
                        }
                    ],
                },
            }
            body_str = json.dumps(body)

            client = await self._get_client()
            headers = self._get_headers("POST", path, body_str)

            logger.debug(f"Relayer request to {self.host}{path}")
            response = await client.post(
                f"{self.host}{path}",
                headers=headers,
                content=body_str,
            )

            if response.status_code == 200:
                result = response.json()
                return RelayerResult(
                    success=True,
                    tx_hash=result.get("txHash") or result.get("hash"),
                    data=result,
                )
            else:
                error_text = response.text
                logger.error(f"Relayer error {response.status_code}: {error_text}")
                return RelayerResult(
                    success=False,
                    error=f"Relayer error: {response.status_code} - {error_text}",
                )

        except Exception as e:
            logger.error(f"Relayer submit failed: {e}")
            return RelayerResult(success=False, error=str(e))

    def _compute_safe_tx_hash(
        self,
        safe_address: str,
        to: str,
        value: int,
        data: str,
        operation: int,
        safe_tx_gas: int,
        base_gas: int,
        gas_price: int,
        gas_token: str,
        refund_receiver: str,
        nonce: int,
        chain_id: int,
    ) -> str:
        """
        Compute the EIP-712 struct hash for a Safe transaction.

        This follows the Gnosis Safe EIP-712 specification.

        Returns:
            The hex-encoded struct hash (with 0x prefix)
        """
        from eth_hash.auto import keccak

        # EIP-712 type hashes
        # Domain type: EIP712Domain(uint256 chainId,address verifyingContract)
        DOMAIN_SEPARATOR_TYPEHASH = keccak(
            b"EIP712Domain(uint256 chainId,address verifyingContract)"
        )

        # SafeTx type
        SAFE_TX_TYPEHASH = keccak(
            b"SafeTx(address to,uint256 value,bytes data,uint8 operation,"
            b"uint256 safeTxGas,uint256 baseGas,uint256 gasPrice,"
            b"address gasToken,address refundReceiver,uint256 nonce)"
        )

        # Compute domain separator
        domain_separator = keccak(
            encode(
                ["bytes32", "uint256", "address"],
                [
                    DOMAIN_SEPARATOR_TYPEHASH,
                    chain_id,
                    to_checksum_address(safe_address),
                ],
            )
        )

        # Encode data bytes and hash
        data_bytes = bytes.fromhex(data[2:]) if data.startswith("0x") else bytes.fromhex(data)
        data_hash = keccak(data_bytes)

        # Compute struct hash
        struct_hash = keccak(
            encode(
                [
                    "bytes32",  # typehash
                    "address",  # to
                    "uint256",  # value
                    "bytes32",  # keccak256(data)
                    "uint8",    # operation
                    "uint256",  # safeTxGas
                    "uint256",  # baseGas
                    "uint256",  # gasPrice
                    "address",  # gasToken
                    "address",  # refundReceiver
                    "uint256",  # nonce
                ],
                [
                    SAFE_TX_TYPEHASH,
                    to_checksum_address(to),
                    value,
                    data_hash,
                    operation,
                    safe_tx_gas,
                    base_gas,
                    gas_price,
                    to_checksum_address(gas_token),
                    to_checksum_address(refund_receiver),
                    nonce,
                ],
            )
        )

        # Compute final EIP-712 hash: keccak256("\x19\x01" || domainSeparator || structHash)
        final_hash = keccak(
            b"\x19\x01" + domain_separator + struct_hash
        )

        return "0x" + final_hash.hex()

    def _split_and_pack_signature(self, signature_hex: str) -> str:
        """
        Split signature and pack in Gnosis Safe format.

        Gnosis Safe uses a specific signature format where:
        - r and s are packed as uint256 (32 bytes each)
        - v is normalized: if v is 0-1, add 31; if v is 27-28, add 4
        - Final format is encodePacked(uint256 r, uint256 s, uint8 v) = 65 bytes

        Args:
            signature_hex: Raw signature in hex format (with or without 0x prefix)

        Returns:
            Packed signature in hex format with 0x prefix
        """
        # Remove 0x prefix if present
        sig = signature_hex[2:] if signature_hex.startswith("0x") else signature_hex

        # Extract r, s, v from signature (each component is hex)
        r = int(sig[0:64], 16)
        s = int(sig[64:128], 16)
        v = int(sig[128:130], 16)

        # Normalize v for Gnosis Safe format
        # If v is 0 or 1, add 31 to get 31 or 32
        # If v is 27 or 28, add 4 to get 31 or 32
        if v == 0 or v == 1:
            v = v + 31
        elif v == 27 or v == 28:
            v = v + 4
        else:
            raise ValueError(f"Invalid v value in signature: {v}")

        # Pack as (uint256, uint256, uint8) using tight/packed encoding
        # r: 32 bytes, s: 32 bytes, v: 1 byte = 65 bytes total
        r_bytes = r.to_bytes(32, byteorder="big")
        s_bytes = s.to_bytes(32, byteorder="big")
        v_bytes = v.to_bytes(1, byteorder="big")
        packed = r_bytes + s_bytes + v_bytes
        return "0x" + packed.hex()

    async def _submit_safe_transaction(
        self,
        private_key: str,
        safe_address: str,
        to: str,
        data: str,
        value: int = 0,
    ) -> RelayerResult:
        """
        Submit a transaction via Safe wallet with EIP-712 signature.

        Args:
            private_key: EOA private key for signing
            safe_address: Safe wallet address
            to: Contract address to call
            data: Encoded calldata
            value: ETH value to send (usually 0)

        Returns:
            RelayerResult with transaction hash
        """
        try:
            from eth_account import Account
            from eth_account.messages import encode_defunct
            from eth_hash.auto import keccak

            CHAIN_ID = 137  # Polygon
            ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

            # Get the Safe nonce from the relayer
            nonce = await self._get_safe_nonce(safe_address)

            account = Account.from_key(private_key)

            # Compute the EIP-712 struct hash for SafeTx
            # This follows the Polymarket SDK approach
            struct_hash = self._compute_safe_tx_hash(
                safe_address=safe_address,
                to=to,
                value=value,
                data=data,
                operation=0,
                safe_tx_gas=0,
                base_gas=0,
                gas_price=0,
                gas_token=ZERO_ADDRESS,
                refund_receiver=ZERO_ADDRESS,
                nonce=nonce,
                chain_id=CHAIN_ID,
            )

            # Sign the hash with EIP-191 prefix (like Polymarket SDK does)
            signable = encode_defunct(hexstr=struct_hash)
            signed = account.sign_message(signable)

            # Pack signature in Gnosis Safe format (r + s + normalized_v)
            raw_signature = signed.signature.hex()
            signature = self._split_and_pack_signature(raw_signature)

            # Build the request payload
            path = "/submit"
            body = {
                "type": "SAFE",
                "from": to_checksum_address(account.address),
                "to": to_checksum_address(to),
                "proxyWallet": to_checksum_address(safe_address),
                "data": data,
                "nonce": str(nonce),
                "signature": signature,
                "signatureParams": {
                    "operation": "0",
                    "safeTxnGas": "0",
                    "baseGas": "0",
                    "gasPrice": "0",
                    "gasToken": ZERO_ADDRESS,
                    "refundReceiver": ZERO_ADDRESS,
                },
            }
            body_str = json.dumps(body)

            client = await self._get_client()
            headers = self._get_headers("POST", path, body_str)

            logger.info(f"Submitting Safe transaction: {safe_address[:10]}... -> {to[:10]}...")
            response = await client.post(
                f"{self.host}{path}",
                headers=headers,
                content=body_str,
            )

            if response.status_code == 200:
                result = response.json()
                # Extract tx hash - relayer may return it under different keys
                tx_hash = (
                    result.get("txHash")
                    or result.get("hash")
                    or result.get("transactionHash")
                )
                logger.info(f"Safe transaction submitted: {tx_hash}")
                return RelayerResult(
                    success=True,
                    tx_hash=tx_hash,
                    data=result,
                )
            else:
                error_text = response.text
                logger.error(f"Safe transaction error {response.status_code}: {error_text}")
                return RelayerResult(
                    success=False,
                    error=f"Relayer error: {response.status_code} - {error_text}",
                )

        except Exception as e:
            logger.error(f"Safe transaction failed: {e}")
            return RelayerResult(success=False, error=str(e))

    async def _get_safe_nonce(self, safe_address: str) -> int:
        """
        Get the current nonce for a Safe wallet directly from on-chain.

        Args:
            safe_address: Safe wallet address

        Returns:
            Current nonce value
        """
        try:
            from web3 import Web3
            from config import settings

            w3 = Web3(Web3.HTTPProvider(settings.polygon_rpc_url))

            # Minimal Safe ABI for nonce
            nonce_abi = [{
                "constant": True,
                "inputs": [],
                "name": "nonce",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            }]

            safe_contract = w3.eth.contract(
                address=Web3.to_checksum_address(safe_address),
                abi=nonce_abi,
            )

            nonce = safe_contract.functions.nonce().call()
            logger.debug(f"Safe {safe_address[:10]}... on-chain nonce: {nonce}")
            return nonce

        except Exception as e:
            logger.error(f"Failed to get Safe nonce on-chain: {e}")
            # Fallback to relayer API
            try:
                path = "/nonce"
                client = await self._get_client()
                headers = self._get_headers("GET", path)

                response = await client.get(
                    f"{self.host}{path}",
                    params={
                        "address": to_checksum_address(safe_address),
                        "type": "SAFE",
                    },
                    headers=headers,
                )

                if response.status_code == 200:
                    result = response.json()
                    return int(result.get("nonce", 0))
            except Exception as e2:
                logger.error(f"Relayer nonce fallback also failed: {e2}")

            return 0

    async def approve_usdc(
        self,
        user_address: str,
        spender: str,
        amount: Optional[float] = None,
        private_key: Optional[str] = None,
    ) -> RelayerResult:
        """
        Approve USDC spending via relayer (gasless).

        For Safe wallets, private_key must be provided to sign the Safe transaction.

        Args:
            user_address: User's wallet address (Safe address for Safe wallets)
            spender: Address to approve for spending
            amount: Amount in USDC (None for unlimited)
            private_key: EOA private key for signing Safe transactions

        Returns:
            RelayerResult with transaction hash
        """
        if not self.is_configured():
            return RelayerResult(
                success=False,
                error="Relayer not configured - missing builder credentials",
            )

        # Convert amount to smallest unit (6 decimals for USDC)
        if amount is None:
            # Max uint256 for unlimited approval
            amount_wei = 2**256 - 1
        else:
            amount_wei = int(amount * 10**6)

        # Encode approve call
        calldata = self._encode_erc20_approve(spender, amount_wei)

        logger.info(f"Approving USDC via relayer: {user_address} -> {spender}")

        # If private_key is provided, use Safe transaction (for Safe wallets)
        if private_key:
            return await self._submit_safe_transaction(
                private_key=private_key,
                safe_address=user_address,
                to=USDC_ADDRESS,
                data=calldata,
            )

        # Otherwise use proxy transaction (for EOA wallets)
        return await self._submit_transaction(
            user_address=user_address,
            to=USDC_ADDRESS,
            data=calldata,
        )

    async def setup_all_allowances(
        self,
        safe_address: str,
        private_key: str,
    ) -> RelayerResult:
        """
        Set up all required allowances for Safe wallet trading on Polymarket.

        This includes:
        1. USDC approval for CTF Exchange, Neg Risk CTF Exchange, and Neg Risk Adapter
        2. CTF token operator approval for the same contracts

        Each approval is submitted as a separate Safe transaction.

        Args:
            safe_address: Safe wallet address
            private_key: EOA private key for signing Safe transactions

        Returns:
            RelayerResult with success status
        """
        if not self.is_configured():
            return RelayerResult(
                success=False,
                error="Relayer not configured - missing builder credentials",
            )

        logger.info(f"Setting up all allowances for Safe wallet {safe_address[:10]}...")

        # Max uint256 for unlimited approval
        max_amount = 2**256 - 1
        failed_approvals = []

        # 1. Approve USDC for all spenders
        for spender in USDC_SPENDERS:
            # First check if already approved on-chain
            if await self.verify_on_chain_allowance(safe_address, spender):
                logger.info(f"USDC already approved for {spender[:10]}... (verified on-chain)")
                continue

            logger.info(f"Approving USDC for spender {spender[:10]}...")
            calldata = self._encode_erc20_approve(spender, max_amount)

            result = await self._submit_safe_transaction(
                private_key=private_key,
                safe_address=safe_address,
                to=USDC_ADDRESS,
                data=calldata,
            )

            if not result.success:
                logger.error(f"USDC approval failed for {spender}: {result.error}")
                failed_approvals.append(f"USDC->{spender[:10]}")
            else:
                logger.info(f"USDC approval submitted for {spender[:10]}: {result.tx_hash}")
                # Wait for transaction to be confirmed on-chain
                if result.tx_hash:
                    confirmed = await self.wait_for_transaction(result.tx_hash, timeout=60)
                    if not confirmed:
                        logger.warning(f"USDC approval tx not confirmed for {spender[:10]}")
                        failed_approvals.append(f"USDC->{spender[:10]} (unconfirmed)")

        # 2. Set CTF operator approval for all operators
        # Note: We don't have an easy way to verify CTF operator approvals on-chain,
        # so we just submit them and wait for confirmation
        for operator in CTF_OPERATORS:
            logger.info(f"Setting CTF operator approval for {operator[:10]}...")
            calldata = self._encode_set_approval_for_all(operator, True)

            result = await self._submit_safe_transaction(
                private_key=private_key,
                safe_address=safe_address,
                to=CTF_ADDRESS,
                data=calldata,
            )

            if not result.success:
                logger.error(f"CTF operator approval failed for {operator}: {result.error}")
                failed_approvals.append(f"CTF->{operator[:10]}")
            else:
                logger.info(f"CTF operator approval submitted for {operator[:10]}: {result.tx_hash}")
                # Wait for transaction to be confirmed on-chain
                if result.tx_hash:
                    confirmed = await self.wait_for_transaction(result.tx_hash, timeout=60)
                    if not confirmed:
                        logger.warning(f"CTF operator approval tx not confirmed for {operator[:10]}")
                        failed_approvals.append(f"CTF->{operator[:10]} (unconfirmed)")

        if failed_approvals:
            return RelayerResult(
                success=False,
                error=f"Some approvals failed: {', '.join(failed_approvals)}",
            )

        # Final on-chain verification of USDC allowances
        logger.info("Verifying all USDC allowances on-chain...")
        for spender in USDC_SPENDERS:
            if not await self.verify_on_chain_allowance(safe_address, spender):
                logger.error(f"Final verification failed: USDC allowance not found for {spender[:10]}")
                return RelayerResult(
                    success=False,
                    error=f"On-chain verification failed for {spender[:10]}",
                )

        logger.info(f"All allowances set up and verified for Safe {safe_address[:10]}")
        return RelayerResult(success=True, data={"approvals_count": len(USDC_SPENDERS) + len(CTF_OPERATORS)})

    async def verify_on_chain_allowance(
        self,
        owner_address: str,
        spender_address: str,
    ) -> bool:
        """
        Verify USDC allowance directly on-chain using web3.

        Args:
            owner_address: Token owner (Safe wallet address)
            spender_address: Spender address to check

        Returns:
            True if allowance > 0, False otherwise
        """
        try:
            from web3 import Web3
            from config import settings

            w3 = Web3(Web3.HTTPProvider(settings.polygon_rpc_url))

            # Minimal ERC20 ABI for allowance check
            allowance_abi = [{
                "constant": True,
                "inputs": [
                    {"name": "_owner", "type": "address"},
                    {"name": "_spender", "type": "address"}
                ],
                "name": "allowance",
                "outputs": [{"name": "remaining", "type": "uint256"}],
                "type": "function"
            }]

            usdc_contract = w3.eth.contract(
                address=Web3.to_checksum_address(USDC_ADDRESS),
                abi=allowance_abi,
            )

            # Use retry wrapper for RPC calls
            allowance = await _rpc_call_with_retry(
                lambda: usdc_contract.functions.allowance(
                    Web3.to_checksum_address(owner_address),
                    Web3.to_checksum_address(spender_address),
                ).call(),
                f"Check USDC allowance for {spender_address[:10]}..."
            )

            has_allowance = allowance > 0
            logger.debug(
                f"On-chain allowance check: {owner_address[:10]}... -> {spender_address[:10]}... = {allowance} ({has_allowance})"
            )
            return has_allowance

        except Exception as e:
            logger.error(f"Failed to verify on-chain allowance: {e}")
            return False

    async def wait_for_transaction(
        self,
        tx_hash: str,
        timeout: int = 60,
        poll_interval: float = 3.0,
    ) -> bool:
        """
        Wait for a transaction to be confirmed on-chain.

        Args:
            tx_hash: Transaction hash to wait for
            timeout: Maximum wait time in seconds
            poll_interval: Time between checks in seconds

        Returns:
            True if transaction confirmed successfully, False if timeout/failed
        """
        if not tx_hash:
            logger.warning("No tx_hash provided to wait_for_transaction")
            return False

        try:
            import asyncio
            from web3 import Web3
            from config import settings

            w3 = Web3(Web3.HTTPProvider(settings.polygon_rpc_url))

            attempts = int(timeout / poll_interval)
            logger.info(f"Waiting for tx {tx_hash[:16]}... (timeout={timeout}s)")

            for i in range(attempts):
                try:
                    receipt = w3.eth.get_transaction_receipt(tx_hash)
                    if receipt:
                        if receipt.status == 1:
                            logger.info(
                                f"Transaction {tx_hash[:16]}... confirmed in block {receipt.blockNumber}"
                            )
                            return True
                        else:
                            logger.error(f"Transaction {tx_hash[:16]}... failed (status=0)")
                            return False
                except Exception:
                    pass  # Transaction not yet mined

                await asyncio.sleep(poll_interval)

            logger.warning(f"Transaction {tx_hash[:16]}... timed out after {timeout}s")
            return False

        except Exception as e:
            logger.error(f"Error waiting for transaction: {e}")
            return False

    async def verify_all_allowances(
        self,
        safe_address: str,
    ) -> bool:
        """
        Verify all required USDC allowances are set on-chain.

        Args:
            safe_address: Safe wallet address to check

        Returns:
            True if all allowances are set, False otherwise
        """
        for spender in USDC_SPENDERS:
            has_allowance = await self.verify_on_chain_allowance(safe_address, spender)
            if not has_allowance:
                logger.warning(f"Missing USDC allowance for {spender[:10]}...")
                return False

        logger.info(f"All USDC allowances verified for Safe {safe_address[:10]}...")
        return True

    async def verify_ctf_operator_approval(
        self,
        owner_address: str,
        operator_address: str,
    ) -> bool:
        """
        Verify CTF operator approval (setApprovalForAll) on-chain.

        Args:
            owner_address: Token owner (Safe wallet address)
            operator_address: Operator address to check

        Returns:
            True if operator is approved, False otherwise
        """
        try:
            from web3 import Web3
            from config import settings

            w3 = Web3(Web3.HTTPProvider(settings.polygon_rpc_url))

            # Minimal ERC1155 ABI for isApprovedForAll check
            is_approved_abi = [{
                "constant": True,
                "inputs": [
                    {"name": "_owner", "type": "address"},
                    {"name": "_operator", "type": "address"}
                ],
                "name": "isApprovedForAll",
                "outputs": [{"name": "", "type": "bool"}],
                "type": "function"
            }]

            ctf_contract = w3.eth.contract(
                address=Web3.to_checksum_address(CTF_ADDRESS),
                abi=is_approved_abi,
            )

            # Use retry wrapper for RPC calls
            is_approved = await _rpc_call_with_retry(
                lambda: ctf_contract.functions.isApprovedForAll(
                    Web3.to_checksum_address(owner_address),
                    Web3.to_checksum_address(operator_address),
                ).call(),
                f"Check CTF operator approval for {operator_address[:10]}..."
            )

            logger.debug(
                f"CTF operator approval check: {owner_address[:10]}... -> {operator_address[:10]}... = {is_approved}"
            )
            return is_approved

        except Exception as e:
            logger.error(f"Failed to verify CTF operator approval: {e}")
            return False

    async def verify_all_ctf_approvals(self, safe_address: str) -> bool:
        """
        Verify all required CTF operator approvals are set on-chain.

        Args:
            safe_address: Safe wallet address to check

        Returns:
            True if all CTF operators are approved, False otherwise
        """
        for operator in CTF_OPERATORS:
            is_approved = await self.verify_ctf_operator_approval(safe_address, operator)
            if not is_approved:
                logger.warning(f"Missing CTF operator approval for {operator[:10]}...")
                return False

        logger.info(f"All CTF operator approvals verified for Safe {safe_address[:10]}...")
        return True

    async def verify_all_approvals_complete(self, safe_address: str) -> bool:
        """
        Verify ALL required approvals (USDC + CTF operators) are set on-chain.

        Args:
            safe_address: Safe wallet address to check

        Returns:
            True if all 6 approvals are set, False otherwise
        """
        usdc_ok = await self.verify_all_allowances(safe_address)
        if not usdc_ok:
            return False

        ctf_ok = await self.verify_all_ctf_approvals(safe_address)
        if not ctf_ok:
            return False

        logger.info(f"All 6 approvals verified for Safe {safe_address[:10]}...")
        return True

    async def verify_safe_deployed(self, safe_address: str) -> bool:
        """
        Verify that a Safe wallet is deployed on-chain by checking for contract code.

        Args:
            safe_address: Safe wallet address to check

        Returns:
            True if Safe has contract code deployed, False otherwise
        """
        try:
            from web3 import Web3
            from config import settings

            w3 = Web3(Web3.HTTPProvider(settings.polygon_rpc_url))

            # Use retry wrapper for RPC calls
            code = await _rpc_call_with_retry(
                lambda: w3.eth.get_code(Web3.to_checksum_address(safe_address)),
                f"Check Safe deployment for {safe_address[:10]}..."
            )

            is_deployed = len(code) > 0
            logger.debug(f"Safe {safe_address[:10]}... deployed: {is_deployed} (code length: {len(code)})")
            return is_deployed

        except Exception as e:
            logger.error(f"Failed to verify Safe deployment: {e}")
            return False

    async def transfer_usdc(
        self,
        user_address: str,
        to_address: str,
        amount: float,
    ) -> RelayerResult:
        """
        Transfer USDC via relayer (gasless withdrawal).

        Args:
            user_address: User's wallet address (sender)
            to_address: Recipient address
            amount: Amount in USDC

        Returns:
            RelayerResult with transaction hash
        """
        if not self.is_configured():
            return RelayerResult(
                success=False,
                error="Relayer not configured - missing builder credentials",
            )

        # Convert amount to smallest unit (6 decimals)
        amount_wei = int(amount * 10**6)

        # Encode transfer call
        calldata = self._encode_erc20_transfer(to_address, amount_wei)

        logger.info(f"Transferring ${amount} USDC via relayer: {user_address} -> {to_address}")
        return await self._submit_transaction(
            user_address=user_address,
            to=USDC_ADDRESS,
            data=calldata,
        )

    async def redeem_positions(
        self,
        user_address: str,
        condition_id: str,
        index_sets: List[int],
        is_neg_risk: bool = False,
    ) -> RelayerResult:
        """
        Redeem winning positions via relayer (gasless).

        Called after a market resolves to claim winnings.

        Args:
            user_address: User's wallet address
            condition_id: Market condition ID
            index_sets: Outcome index sets to redeem (1 for YES, 2 for NO)
            is_neg_risk: Whether this is a negative risk market

        Returns:
            RelayerResult with transaction hash
        """
        if not self.is_configured():
            return RelayerResult(
                success=False,
                error="Relayer not configured - missing builder credentials",
            )

        # Encode redeemPositions call
        calldata = self._encode_redeem_positions(condition_id, index_sets)

        # Choose correct CTF contract
        ctf_address = NEG_RISK_CTF_ADDRESS if is_neg_risk else CTF_ADDRESS

        logger.info(
            f"Redeeming positions via relayer: {user_address} "
            f"market={condition_id[:16]}... outcomes={index_sets}"
        )
        return await self._submit_transaction(
            user_address=user_address,
            to=ctf_address,
            data=calldata,
        )

    async def execute_batch(
        self,
        user_address: str,
        transactions: List[Dict[str, Any]],
    ) -> RelayerResult:
        """
        Execute batch transactions via relayer.

        Args:
            user_address: User's wallet address
            transactions: List of transaction dicts with 'to', 'data', 'value'

        Returns:
            RelayerResult with transaction hash
        """
        if not self.is_configured():
            return RelayerResult(
                success=False,
                error="Relayer not configured - missing builder credentials",
            )

        try:
            path = "/submit"
            body = {
                "type": RelayerTxType.PROXY.value,
                "data": {
                    "address": to_checksum_address(user_address),
                    "transactions": [
                        {
                            "to": to_checksum_address(tx["to"]),
                            "data": tx["data"],
                            "value": str(tx.get("value", 0)),
                        }
                        for tx in transactions
                    ],
                },
            }
            body_str = json.dumps(body)

            client = await self._get_client()
            headers = self._get_headers("POST", path, body_str)

            logger.info(
                f"Executing batch via relayer: {user_address} "
                f"({len(transactions)} transactions)"
            )
            response = await client.post(
                f"{self.host}{path}",
                headers=headers,
                content=body_str,
            )

            if response.status_code == 200:
                result = response.json()
                return RelayerResult(
                    success=True,
                    tx_hash=result.get("txHash") or result.get("hash"),
                    data=result,
                )
            else:
                error_text = response.text
                logger.error(f"Relayer batch error {response.status_code}: {error_text}")
                return RelayerResult(
                    success=False,
                    error=f"Relayer error: {response.status_code} - {error_text}",
                )

        except Exception as e:
            logger.error(f"Relayer batch execute failed: {e}")
            return RelayerResult(success=False, error=str(e))

    async def check_safe_deployed(
        self,
        safe_address: str,
    ) -> bool:
        """
        Check if a Safe wallet is already deployed on-chain.

        Args:
            safe_address: The Safe wallet address to check

        Returns:
            True if deployed, False otherwise
        """
        try:
            path = "/deployed"
            client = await self._get_client()
            headers = self._get_headers("GET", path)

            response = await client.get(
                f"{self.host}{path}",
                params={"address": to_checksum_address(safe_address)},
                headers=headers,
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("deployed", False)
            return False

        except Exception as e:
            logger.error(f"Check Safe deployed failed: {e}")
            return False

    async def deploy_safe(
        self,
        private_key: str,
        eoa_address: str,
        safe_address: str,
    ) -> RelayerResult:
        """
        Deploy a Safe wallet via relayer with EIP-712 signature.

        Args:
            private_key: EOA private key for signing the deployment
            eoa_address: EOA signer address
            safe_address: Pre-derived Safe address

        Returns:
            RelayerResult with transaction hash
        """
        if not self.is_configured():
            return RelayerResult(
                success=False,
                error="Relayer not configured - missing builder credentials",
            )

        try:
            from eth_account import Account
            from eth_account.messages import encode_typed_data

            # Polymarket Safe Factory address on Polygon
            SAFE_FACTORY = "0xaacfeea03eb1561c4e67d661e40682bd20e3541b"
            CHAIN_ID = 137  # Polygon

            # Zero address for payment params (gasless)
            ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

            # EIP-712 domain for CreateProxy
            # From @polymarket/builder-relayer-client constants
            domain = {
                "name": "Polymarket Contract Proxy Factory",
                "chainId": CHAIN_ID,
                "verifyingContract": to_checksum_address(SAFE_FACTORY),
            }

            # EIP-712 types for CreateProxy (3 fields, no owner)
            types = {
                "CreateProxy": [
                    {"name": "paymentToken", "type": "address"},
                    {"name": "payment", "type": "uint256"},
                    {"name": "paymentReceiver", "type": "address"},
                ],
            }

            # Message data (payment params only)
            message = {
                "paymentToken": ZERO_ADDRESS,
                "payment": 0,
                "paymentReceiver": ZERO_ADDRESS,
            }

            # Create typed data for signing
            typed_data = {
                "types": types,
                "primaryType": "CreateProxy",
                "domain": domain,
                "message": message,
            }

            # Sign the typed data
            account = Account.from_key(private_key)
            signable = encode_typed_data(full_message=typed_data)
            signed = account.sign_message(signable)
            signature = signed.signature.hex()
            # Ensure 0x prefix
            if not signature.startswith("0x"):
                signature = "0x" + signature

            # Build the request payload
            # Transaction type is "SAFE-CREATE" (with hyphen)
            # Fields are at top level, not nested under "data"
            path = "/submit"
            body = {
                "type": "SAFE-CREATE",
                "from": to_checksum_address(eoa_address),
                "to": to_checksum_address(SAFE_FACTORY),
                "proxyWallet": to_checksum_address(safe_address),
                "data": "0x",
                "signature": signature,
                "signatureParams": {
                    "paymentToken": ZERO_ADDRESS,
                    "payment": "0",
                    "paymentReceiver": ZERO_ADDRESS,
                },
            }
            body_str = json.dumps(body)

            client = await self._get_client()
            headers = self._get_headers("POST", path, body_str)

            logger.info(f"Deploying Safe wallet via relayer for EOA: {eoa_address}")
            response = await client.post(
                f"{self.host}{path}",
                headers=headers,
                content=body_str,
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(
                    f"Safe deployment successful for {eoa_address}: "
                    f"tx={result.get('txHash') or result.get('hash')}"
                )
                return RelayerResult(
                    success=True,
                    tx_hash=result.get("txHash") or result.get("hash"),
                    data=result,
                )
            elif response.status_code == 400 and "already deployed" in response.text.lower():
                logger.info(f"Safe already deployed for {eoa_address}")
                return RelayerResult(
                    success=True,
                    data={"already_deployed": True},
                )
            else:
                error_text = response.text
                logger.error(f"Safe deploy error {response.status_code}: {error_text}")
                return RelayerResult(
                    success=False,
                    error=f"Deploy error: {response.status_code} - {error_text}",
                )

        except Exception as e:
            logger.error(f"Safe deployment failed: {e}")
            return RelayerResult(success=False, error=str(e))
