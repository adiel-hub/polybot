"""Private key encryption using Fernet with PBKDF2."""

import os
import base64
from typing import Tuple

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class KeyEncryption:
    """Encrypt and decrypt private keys using Fernet symmetric encryption."""

    # Number of iterations for PBKDF2 key derivation
    # Using high iteration count for security (Django 2024 recommendation)
    ITERATIONS = 1_200_000

    def __init__(self, master_key: str):
        """
        Initialize encryption with master key.

        Args:
            master_key: Master encryption key from environment
        """
        self.master_key = master_key.encode()

    def encrypt(self, private_key: str) -> Tuple[bytes, bytes]:
        """
        Encrypt a private key.

        Args:
            private_key: The private key to encrypt

        Returns:
            Tuple of (encrypted_key, salt)
        """
        # Generate random salt for this encryption
        salt = os.urandom(16)

        # Derive encryption key from master key + salt
        fernet = self._derive_fernet(salt)

        # Encrypt the private key
        encrypted = fernet.encrypt(private_key.encode())

        return encrypted, salt

    def decrypt(self, encrypted_key: bytes, salt: bytes) -> str:
        """
        Decrypt a private key.

        Args:
            encrypted_key: The encrypted private key
            salt: The salt used during encryption

        Returns:
            Decrypted private key string
        """
        # Derive the same encryption key using stored salt
        fernet = self._derive_fernet(salt)

        # Decrypt and return
        return fernet.decrypt(encrypted_key).decode()

    def _derive_fernet(self, salt: bytes) -> Fernet:
        """
        Derive a Fernet encryption key from master key and salt.

        Args:
            salt: Random salt for key derivation

        Returns:
            Fernet instance for encryption/decryption
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=self.ITERATIONS,
        )

        # Derive key and encode for Fernet
        key = base64.urlsafe_b64encode(kdf.derive(self.master_key))

        return Fernet(key)

    def encrypt_string(self, data: str) -> Tuple[bytes, bytes]:
        """
        Encrypt any string (for API keys, etc).

        Args:
            data: String to encrypt

        Returns:
            Tuple of (encrypted_data, salt)
        """
        return self.encrypt(data)

    def decrypt_string(self, encrypted_data: bytes, salt: bytes) -> str:
        """
        Decrypt any string.

        Args:
            encrypted_data: The encrypted data
            salt: The salt used during encryption

        Returns:
            Decrypted string
        """
        return self.decrypt(encrypted_data, salt)

    @staticmethod
    def generate_master_key() -> str:
        """
        Generate a new master encryption key.

        Returns:
            Base64 encoded Fernet key
        """
        return Fernet.generate_key().decode()
