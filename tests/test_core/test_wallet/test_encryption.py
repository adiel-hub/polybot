"""Tests for wallet encryption module.

Tests the KeyEncryption class which handles private key encryption
using Fernet symmetric encryption with PBKDF2 key derivation.
"""

import pytest
from cryptography.fernet import Fernet, InvalidToken

from core.wallet.encryption import KeyEncryption


class TestKeyEncryption:
    """Test suite for KeyEncryption class."""

    def test_init_with_valid_key(self, encryption_key: str):
        """Test initialization with a valid Fernet key."""
        encryption = KeyEncryption(encryption_key)
        assert encryption.master_key == encryption_key.encode()

    def test_encrypt_returns_tuple(self, key_encryption: KeyEncryption):
        """Test that encrypt returns a tuple of (encrypted_data, salt)."""
        private_key = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"

        result = key_encryption.encrypt(private_key)

        assert isinstance(result, tuple)
        assert len(result) == 2
        encrypted, salt = result
        assert isinstance(encrypted, bytes)
        assert isinstance(salt, bytes)
        assert len(salt) == 16  # Salt should be 16 bytes

    def test_encrypt_produces_different_results_each_time(
        self, key_encryption: KeyEncryption
    ):
        """Test that encryption produces different ciphertext for same input."""
        private_key = "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"

        encrypted1, salt1 = key_encryption.encrypt(private_key)
        encrypted2, salt2 = key_encryption.encrypt(private_key)

        # Different salts should produce different encrypted outputs
        assert salt1 != salt2
        assert encrypted1 != encrypted2

    def test_decrypt_recovers_original(self, key_encryption: KeyEncryption):
        """Test that decrypt correctly recovers the original private key."""
        original_key = "0xdeadbeef1234567890abcdef1234567890abcdef1234567890abcdef12345678"

        encrypted, salt = key_encryption.encrypt(original_key)
        decrypted = key_encryption.decrypt(encrypted, salt)

        assert decrypted == original_key

    def test_decrypt_with_wrong_salt_fails(self, key_encryption: KeyEncryption):
        """Test that decryption fails with wrong salt."""
        private_key = "0x1111111111111111111111111111111111111111111111111111111111111111"

        encrypted, original_salt = key_encryption.encrypt(private_key)

        # Create a different salt
        wrong_salt = b"0" * 16

        with pytest.raises(InvalidToken):
            key_encryption.decrypt(encrypted, wrong_salt)

    def test_decrypt_with_different_master_key_fails(self, encryption_key: str):
        """Test that decryption fails with different master key."""
        encryption1 = KeyEncryption(encryption_key)

        # Create another encryption instance with different key
        different_key = Fernet.generate_key().decode()
        encryption2 = KeyEncryption(different_key)

        private_key = "0x2222222222222222222222222222222222222222222222222222222222222222"

        encrypted, salt = encryption1.encrypt(private_key)

        with pytest.raises(InvalidToken):
            encryption2.decrypt(encrypted, salt)

    def test_encrypt_string_same_as_encrypt(self, key_encryption: KeyEncryption):
        """Test that encrypt_string behaves same as encrypt."""
        data = "some_api_key_or_secret"

        result1 = key_encryption.encrypt(data)
        result2 = key_encryption.encrypt_string(data)

        # Both should return tuples with (encrypted, salt)
        assert isinstance(result1, tuple) and len(result1) == 2
        assert isinstance(result2, tuple) and len(result2) == 2

    def test_decrypt_string_same_as_decrypt(self, key_encryption: KeyEncryption):
        """Test that decrypt_string behaves same as decrypt."""
        data = "another_secret_value"

        encrypted, salt = key_encryption.encrypt_string(data)
        decrypted = key_encryption.decrypt_string(encrypted, salt)

        assert decrypted == data

    def test_generate_master_key_produces_valid_key(self):
        """Test that generate_master_key produces a valid Fernet key."""
        key = KeyEncryption.generate_master_key()

        # Should be a valid base64 string
        assert isinstance(key, str)
        assert len(key) == 44  # Fernet keys are 44 chars in base64

        # Should be usable for encryption
        encryption = KeyEncryption(key)
        encrypted, salt = encryption.encrypt("test_data")
        decrypted = encryption.decrypt(encrypted, salt)
        assert decrypted == "test_data"

    def test_encrypt_empty_string(self, key_encryption: KeyEncryption):
        """Test encryption of empty string."""
        encrypted, salt = key_encryption.encrypt("")
        decrypted = key_encryption.decrypt(encrypted, salt)
        assert decrypted == ""

    def test_encrypt_long_string(self, key_encryption: KeyEncryption):
        """Test encryption of a long string."""
        long_data = "x" * 10000

        encrypted, salt = key_encryption.encrypt(long_data)
        decrypted = key_encryption.decrypt(encrypted, salt)

        assert decrypted == long_data

    def test_encrypt_special_characters(self, key_encryption: KeyEncryption):
        """Test encryption of string with special characters."""
        special_data = "私は日本語を話します!@#$%^&*()_+-={}[]|\\:\";<>?,./"

        encrypted, salt = key_encryption.encrypt(special_data)
        decrypted = key_encryption.decrypt(encrypted, salt)

        assert decrypted == special_data
