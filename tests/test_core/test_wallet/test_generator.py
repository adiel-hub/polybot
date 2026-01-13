"""Tests for wallet generator module.

Tests the WalletGenerator class which creates Ethereum/Polygon wallets
using eth-account library.
"""

import pytest

from core.wallet.generator import WalletGenerator


class TestWalletGenerator:
    """Test suite for WalletGenerator class."""

    def test_create_wallet_returns_tuple(self):
        """Test that create_wallet returns a tuple of (address, private_key)."""
        result = WalletGenerator.create_wallet()

        assert isinstance(result, tuple)
        assert len(result) == 2

        address, private_key = result
        assert isinstance(address, str)
        assert isinstance(private_key, str)

    def test_create_wallet_produces_valid_address(self):
        """Test that generated address is valid Ethereum format."""
        address, _ = WalletGenerator.create_wallet()

        # Should start with 0x
        assert address.startswith("0x")
        # Should be 42 characters (0x + 40 hex chars)
        assert len(address) == 42
        # Should be valid hex after 0x prefix
        int(address, 16)  # Should not raise

    def test_create_wallet_produces_valid_private_key(self):
        """Test that generated private key is valid hex string."""
        _, private_key = WalletGenerator.create_wallet()

        # eth-account returns key without 0x prefix
        # Should be 64 characters (64 hex chars)
        assert len(private_key) == 64
        # Should be valid hex
        int(private_key, 16)

    def test_create_wallet_produces_unique_wallets(self):
        """Test that each call produces different wallets."""
        wallet1 = WalletGenerator.create_wallet()
        wallet2 = WalletGenerator.create_wallet()
        wallet3 = WalletGenerator.create_wallet()

        # All addresses should be different
        assert wallet1[0] != wallet2[0]
        assert wallet2[0] != wallet3[0]
        assert wallet1[0] != wallet3[0]

        # All private keys should be different
        assert wallet1[1] != wallet2[1]
        assert wallet2[1] != wallet3[1]
        assert wallet1[1] != wallet3[1]

    def test_from_private_key_returns_correct_address(self):
        """Test that from_private_key returns correct address for key."""
        # First create a wallet
        original_address, private_key = WalletGenerator.create_wallet()

        # Then derive address from private key
        derived_address = WalletGenerator.from_private_key(private_key)

        assert derived_address == original_address

    def test_from_private_key_without_0x_prefix(self):
        """Test that from_private_key works without 0x prefix."""
        original_address, private_key = WalletGenerator.create_wallet()

        # eth-account already returns key without 0x prefix
        # The method should work with both formats
        derived_address = WalletGenerator.from_private_key(private_key)

        assert derived_address == original_address

    def test_is_valid_address_with_valid_address(self):
        """Test is_valid_address returns True for valid address."""
        address, _ = WalletGenerator.create_wallet()

        assert WalletGenerator.is_valid_address(address) is True

    def test_is_valid_address_with_invalid_prefix(self):
        """Test is_valid_address returns False without 0x prefix."""
        address, _ = WalletGenerator.create_wallet()
        address_no_prefix = address[2:]

        assert WalletGenerator.is_valid_address(address_no_prefix) is False

    def test_is_valid_address_with_wrong_length(self):
        """Test is_valid_address returns False for wrong length."""
        # Too short
        assert WalletGenerator.is_valid_address("0x1234") is False
        # Too long
        assert WalletGenerator.is_valid_address("0x" + "a" * 50) is False

    def test_is_valid_address_with_invalid_hex(self):
        """Test is_valid_address returns False for invalid hex chars."""
        # Contains 'g' which is not valid hex
        invalid_address = "0x" + "g" * 40

        assert WalletGenerator.is_valid_address(invalid_address) is False

    def test_is_valid_address_with_empty_string(self):
        """Test is_valid_address returns False for empty string."""
        assert WalletGenerator.is_valid_address("") is False

    def test_is_valid_address_with_none(self):
        """Test is_valid_address handles None gracefully."""
        # The function may raise AttributeError for None, which is acceptable
        # since None is not a valid input type
        try:
            result = WalletGenerator.is_valid_address(None)
            assert result is False
        except (AttributeError, TypeError):
            # Also acceptable - function doesn't handle None
            pass

    def test_checksum_address_converts_to_checksum(self):
        """Test checksum_address converts address to checksum format."""
        # Lowercase address
        lowercase = "0x742d35cc6634c0532925a3b844bc9e7595f1abcd"

        checksum = WalletGenerator.checksum_address(lowercase)

        # Should have mixed case (checksum format)
        assert checksum != lowercase
        assert checksum.lower() == lowercase

    def test_checksum_address_preserves_valid_checksum(self):
        """Test checksum_address works with already checksummed address."""
        address, _ = WalletGenerator.create_wallet()

        # Apply checksum twice should give same result
        checksum1 = WalletGenerator.checksum_address(address)
        checksum2 = WalletGenerator.checksum_address(checksum1)

        assert checksum1 == checksum2

    def test_create_wallet_generates_deterministic_address_from_key(self):
        """Test that same private key always yields same address."""
        _, private_key = WalletGenerator.create_wallet()

        # Derive address multiple times
        address1 = WalletGenerator.from_private_key(private_key)
        address2 = WalletGenerator.from_private_key(private_key)
        address3 = WalletGenerator.from_private_key(private_key)

        assert address1 == address2 == address3
