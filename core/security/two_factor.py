"""Two-Factor Authentication (2FA) using TOTP."""

import logging
import pyotp
from io import BytesIO
from typing import Optional, Tuple

import qrcode

logger = logging.getLogger(__name__)


class TwoFactorAuth:
    """Service for Two-Factor Authentication using TOTP."""

    @staticmethod
    def generate_secret() -> str:
        """
        Generate a new TOTP secret.

        Returns:
            Base32-encoded secret string
        """
        return pyotp.random_base32()

    @staticmethod
    def get_provisioning_uri(
        secret: str,
        username: str,
        issuer_name: str = "PolyBot",
    ) -> str:
        """
        Generate a provisioning URI for QR code.

        Args:
            secret: TOTP secret
            username: User identifier (telegram username or ID)
            issuer_name: Name of the service

        Returns:
            otpauth:// URI for QR code generation
        """
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(
            name=username,
            issuer_name=issuer_name,
        )

    @staticmethod
    def generate_qr_code(provisioning_uri: str) -> BytesIO:
        """
        Generate QR code image from provisioning URI.

        Args:
            provisioning_uri: otpauth:// URI

        Returns:
            BytesIO containing PNG image
        """
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(provisioning_uri)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        bio = BytesIO()
        img.save(bio, 'PNG')
        bio.seek(0)

        return bio

    @staticmethod
    def verify_token(secret: str, token: str) -> bool:
        """
        Verify a TOTP token.

        Args:
            secret: TOTP secret
            token: 6-digit code from authenticator app

        Returns:
            True if token is valid
        """
        try:
            totp = pyotp.TOTP(secret)
            # Allow 1 step (30 seconds) before and after for clock drift
            return totp.verify(token, valid_window=1)
        except Exception as e:
            logger.error(f"2FA verification error: {e}")
            return False

    @staticmethod
    def get_current_token(secret: str) -> str:
        """
        Get current TOTP token (for testing/debugging only).

        Args:
            secret: TOTP secret

        Returns:
            Current 6-digit token
        """
        totp = pyotp.TOTP(secret)
        return totp.now()

    @staticmethod
    def setup_2fa(username: str) -> Tuple[str, str, BytesIO]:
        """
        Complete 2FA setup flow.

        Args:
            username: User identifier

        Returns:
            Tuple of (secret, provisioning_uri, qr_code_image)
        """
        secret = TwoFactorAuth.generate_secret()
        provisioning_uri = TwoFactorAuth.get_provisioning_uri(secret, username)
        qr_code = TwoFactorAuth.generate_qr_code(provisioning_uri)

        return secret, provisioning_uri, qr_code
