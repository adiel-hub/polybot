"""Tests for Safe wallet generation and derivation."""

import pytest
from core.wallet.generator import (
    WalletGenerator,
    SAFE_FACTORY,
    SAFE_INIT_CODE_HASH,
)


class TestSafeAddressDerivation:
    """Tests for Safe address derivation from EOA."""

    def test_derive_safe_address_deterministic(self):
        """Test that Safe address derivation is deterministic."""
        eoa_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f1abCD"

        # Derive twice - should get same result
        safe_address_1 = WalletGenerator.derive_safe_address(eoa_address)
        safe_address_2 = WalletGenerator.derive_safe_address(eoa_address)

        assert safe_address_1 == safe_address_2

    def test_derive_safe_address_different_for_different_eoa(self):
        """Test that different EOAs produce different Safe addresses."""
        eoa_1 = "0x742d35Cc6634C0532925a3b844Bc9e7595f1abCD"
        eoa_2 = "0x8626f6940E2eb28930eFb4CeF49B2d1F2C9C1199"

        safe_1 = WalletGenerator.derive_safe_address(eoa_1)
        safe_2 = WalletGenerator.derive_safe_address(eoa_2)

        assert safe_1 != safe_2

    def test_derive_safe_address_valid_checksum(self):
        """Test that derived Safe address is valid checksum format."""
        eoa_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f1abCD"
        safe_address = WalletGenerator.derive_safe_address(eoa_address)

        # Should be valid checksum address
        assert safe_address.startswith("0x")
        assert len(safe_address) == 42
        assert WalletGenerator.is_valid_address(safe_address)

    def test_derive_safe_address_case_insensitive(self):
        """Test that EOA case doesn't affect Safe address."""
        eoa_lower = "0x742d35cc6634c0532925a3b844bc9e7595f1abcd"
        eoa_upper = "0x742D35CC6634C0532925A3B844BC9E7595F1ABCD"
        eoa_mixed = "0x742d35Cc6634C0532925a3b844Bc9e7595f1abCD"

        safe_lower = WalletGenerator.derive_safe_address(eoa_lower)
        safe_upper = WalletGenerator.derive_safe_address(eoa_upper)
        safe_mixed = WalletGenerator.derive_safe_address(eoa_mixed)

        assert safe_lower == safe_upper == safe_mixed


class TestSafeWalletGeneration:
    """Tests for Safe wallet creation."""

    def test_create_safe_wallet_returns_three_values(self):
        """Test that create_safe_wallet returns Safe address, EOA, and private key."""
        safe_address, eoa_address, private_key = WalletGenerator.create_safe_wallet()

        assert safe_address is not None
        assert eoa_address is not None
        assert private_key is not None

    def test_create_safe_wallet_addresses_are_valid(self):
        """Test that generated addresses are valid."""
        safe_address, eoa_address, private_key = WalletGenerator.create_safe_wallet()

        assert WalletGenerator.is_valid_address(safe_address)
        assert WalletGenerator.is_valid_address(eoa_address)

    def test_create_safe_wallet_safe_address_matches_derived(self):
        """Test that Safe address matches derivation from EOA."""
        safe_address, eoa_address, private_key = WalletGenerator.create_safe_wallet()

        derived_safe = WalletGenerator.derive_safe_address(eoa_address)
        assert safe_address == derived_safe

    def test_create_safe_wallet_eoa_matches_private_key(self):
        """Test that EOA address matches the private key."""
        safe_address, eoa_address, private_key = WalletGenerator.create_safe_wallet()

        derived_eoa = WalletGenerator.from_private_key(private_key)
        assert eoa_address == derived_eoa

    def test_create_safe_wallet_unique_each_time(self):
        """Test that each call generates unique wallets."""
        wallet_1 = WalletGenerator.create_safe_wallet()
        wallet_2 = WalletGenerator.create_safe_wallet()

        # All three values should be different
        assert wallet_1[0] != wallet_2[0]  # Safe addresses
        assert wallet_1[1] != wallet_2[1]  # EOA addresses
        assert wallet_1[2] != wallet_2[2]  # Private keys


class TestSafeConstants:
    """Tests for Polymarket Safe contract constants."""

    def test_safe_factory_is_valid_address(self):
        """Test that SAFE_FACTORY is a valid Ethereum address."""
        assert SAFE_FACTORY.startswith("0x")
        assert len(SAFE_FACTORY) == 42
        assert WalletGenerator.is_valid_address(SAFE_FACTORY)

    def test_safe_init_code_hash_is_valid(self):
        """Test that SAFE_INIT_CODE_HASH is a valid bytes32 hex string."""
        assert SAFE_INIT_CODE_HASH.startswith("0x")
        assert len(SAFE_INIT_CODE_HASH) == 66  # 0x + 64 hex chars

    def test_safe_factory_is_polymarket_address(self):
        """Test that SAFE_FACTORY is the known Polymarket factory address."""
        expected = "0xaacfeea03eb1561c4e67d661e40682bd20e3541b"
        assert SAFE_FACTORY.lower() == expected.lower()


class TestBackwardsCompatibility:
    """Tests for backwards compatibility with existing EOA wallet generation."""

    def test_create_wallet_still_works(self):
        """Test that original create_wallet() still works."""
        address, private_key = WalletGenerator.create_wallet()

        assert WalletGenerator.is_valid_address(address)
        assert private_key is not None

    def test_create_wallet_returns_two_values(self):
        """Test that create_wallet returns address and private key."""
        result = WalletGenerator.create_wallet()
        assert len(result) == 2

    def test_from_private_key_still_works(self):
        """Test that from_private_key() still works."""
        address, private_key = WalletGenerator.create_wallet()

        derived = WalletGenerator.from_private_key(private_key)
        assert derived == address
