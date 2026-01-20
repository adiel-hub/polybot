"""Wallet generation using eth-account."""

from eth_account import Account
from typing import Tuple

from web3 import Web3

# Polymarket Safe constants (from @polymarket/builder-relayer-client)
# https://polygonscan.com/address/0xaacfeea03eb1561c4e67d661e40682bd20e3541b
SAFE_FACTORY = "0xaacfeea03eb1561c4e67d661e40682bd20e3541b"
SAFE_INIT_CODE_HASH = "0x2bce2127ff07fb632d16c8347c4ebf501f4841168bed00d9e6ef715ddb6fcecf"


class WalletGenerator:
    """Generate Ethereum/Polygon wallets."""

    @staticmethod
    def derive_safe_address(eoa_address: str) -> str:
        """
        Derive Safe address from EOA using CREATE2.

        Uses Polymarket's SafeProxyFactory contract on Polygon.
        The Safe address is deterministic - same EOA always produces same Safe.

        Args:
            eoa_address: EOA (signer) address

        Returns:
            Deterministic Safe wallet address
        """
        # Normalize address
        eoa_address = Web3.to_checksum_address(eoa_address)

        # Salt = keccak256(abi.encode(eoa_address))
        # The address is left-padded to 32 bytes
        address_bytes = bytes.fromhex(eoa_address[2:])  # Remove 0x prefix
        padded_address = address_bytes.rjust(32, b'\x00')
        salt = Web3.keccak(padded_address)

        # CREATE2: keccak256(0xff ++ factory ++ salt ++ init_code_hash)[12:]
        create2_input = (
            b'\xff'
            + bytes.fromhex(SAFE_FACTORY[2:])
            + salt
            + bytes.fromhex(SAFE_INIT_CODE_HASH[2:])
        )
        full_hash = Web3.keccak(create2_input)
        # Take last 20 bytes (address = hash[12:])
        return Web3.to_checksum_address(full_hash[12:].hex())

    @staticmethod
    def create_wallet() -> Tuple[str, str]:
        """
        Generate a new EOA wallet.

        Returns:
            Tuple of (address, private_key)
        """
        # Enable unaudited HD wallet features
        Account.enable_unaudited_hdwallet_features()

        # Create new account
        account = Account.create()

        return account.address, account.key.hex()

    @staticmethod
    def create_safe_wallet() -> Tuple[str, str, str]:
        """
        Generate a new Safe wallet (EOA + derived Safe address).

        Returns:
            Tuple of (safe_address, eoa_address, private_key)
        """
        Account.enable_unaudited_hdwallet_features()
        account = Account.create()

        eoa_address = account.address
        private_key = account.key.hex()
        safe_address = WalletGenerator.derive_safe_address(eoa_address)

        return safe_address, eoa_address, private_key

    @staticmethod
    def from_private_key(private_key: str) -> str:
        """
        Get address from private key.

        Args:
            private_key: Hex string private key

        Returns:
            Wallet address
        """
        # Ensure private key has 0x prefix
        if not private_key.startswith("0x"):
            private_key = "0x" + private_key

        account = Account.from_key(private_key)
        return account.address

    @staticmethod
    def is_valid_address(address: str) -> bool:
        """
        Check if address is valid.

        Args:
            address: Ethereum address string

        Returns:
            True if valid, False otherwise
        """
        try:
            # Check basic format
            if not address.startswith("0x"):
                return False
            if len(address) != 42:
                return False

            # Check if it's valid hex
            int(address, 16)
            return True
        except (ValueError, TypeError):
            return False

    @staticmethod
    def checksum_address(address: str) -> str:
        """
        Convert address to checksum format.

        Args:
            address: Ethereum address string

        Returns:
            Checksum formatted address
        """
        from eth_utils import to_checksum_address
        return to_checksum_address(address)
