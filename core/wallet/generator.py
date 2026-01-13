"""Wallet generation using eth-account."""

from eth_account import Account
from typing import Tuple


class WalletGenerator:
    """Generate Ethereum/Polygon wallets."""

    @staticmethod
    def create_wallet() -> Tuple[str, str]:
        """
        Generate a new wallet.

        Returns:
            Tuple of (address, private_key)
        """
        # Enable unaudited HD wallet features
        Account.enable_unaudited_hdwallet_features()

        # Create new account
        account = Account.create()

        return account.address, account.key.hex()

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
