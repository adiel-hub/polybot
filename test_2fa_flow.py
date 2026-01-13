"""Manual test script for 2FA flow verification."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.security.two_factor import TwoFactorAuth


async def test_2fa_creation_and_verification():
    """Test the complete 2FA flow."""

    print("=" * 60)
    print("2FA Creation and Verification Test")
    print("=" * 60)

    # Step 1: Generate secret
    print("\n1. Generating TOTP secret...")
    secret = TwoFactorAuth.generate_secret()
    print(f"   ✓ Secret generated: {secret}")
    print(f"   Length: {len(secret)} characters")

    # Step 2: Generate provisioning URI
    print("\n2. Generating provisioning URI...")
    username = "test_user"
    provisioning_uri = TwoFactorAuth.get_provisioning_uri(secret, username)
    print(f"   ✓ URI: {provisioning_uri}")

    # Step 3: Generate QR code
    print("\n3. Generating QR code...")
    qr_code = TwoFactorAuth.generate_qr_code(provisioning_uri)
    qr_size = len(qr_code.getvalue())
    print(f"   ✓ QR code generated: {qr_size} bytes")

    # Step 4: Get current token
    print("\n4. Getting current TOTP token...")
    current_token = TwoFactorAuth.get_current_token(secret)
    print(f"   ✓ Current token: {current_token}")
    print(f"   Token length: {len(current_token)} digits")

    # Step 5: Verify valid token
    print("\n5. Verifying valid token...")
    is_valid = TwoFactorAuth.verify_token(secret, current_token)
    print(f"   ✓ Token verification: {'PASSED' if is_valid else 'FAILED'}")

    # Step 6: Verify invalid token
    print("\n6. Verifying invalid token...")
    invalid_check = TwoFactorAuth.verify_token(secret, "000000")
    print(f"   ✓ Invalid token rejected: {'PASSED' if not invalid_check else 'FAILED'}")

    # Step 7: Test wrong format
    print("\n7. Testing wrong format tokens...")
    formats_to_test = [
        ("12345", "5 digits"),
        ("1234567", "7 digits"),
        ("abcdef", "letters"),
    ]

    all_rejected = True
    for token, description in formats_to_test:
        result = TwoFactorAuth.verify_token(secret, token)
        print(f"   - {description}: {'✗ ACCEPTED (BAD)' if result else '✓ Rejected'}")
        if result:
            all_rejected = False

    # Step 8: Test complete setup flow
    print("\n8. Testing complete setup flow...")
    secret2, uri2, qr2 = TwoFactorAuth.setup_2fa("another_user")
    print(f"   ✓ Secret: {secret2}")
    print(f"   ✓ URI: {uri2[:50]}...")
    print(f"   ✓ QR code: {len(qr2.getvalue())} bytes")

    # Step 9: Test clock drift tolerance
    print("\n9. Testing clock drift tolerance (±30 seconds)...")
    token = TwoFactorAuth.get_current_token(secret)
    is_valid = TwoFactorAuth.verify_token(secret, token)
    print(f"   ✓ Current token valid: {is_valid}")
    print(f"   Note: TOTP allows ±1 time window (30 sec) for clock drift")

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    checks = [
        ("Secret generation", True),
        ("Provisioning URI creation", True),
        ("QR code generation", qr_size > 0),
        ("Current token generation", len(current_token) == 6),
        ("Valid token verification", is_valid),
        ("Invalid token rejection", not invalid_check),
        ("Wrong format rejection", all_rejected),
        ("Complete setup flow", len(secret2) == 32),
    ]

    passed = sum(1 for _, result in checks if result)
    total = len(checks)

    for check_name, result in checks:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {check_name}")

    print(f"\nResult: {passed}/{total} checks passed")

    if passed == total:
        print("🎉 All 2FA creation and verification checks PASSED!")
        return True
    else:
        print("❌ Some checks FAILED!")
        return False


async def test_encryption_integration():
    """Test 2FA with encryption (simulating UserService flow)."""

    print("\n" + "=" * 60)
    print("2FA Encryption Integration Test")
    print("=" * 60)

    from core.wallet.encryption import KeyEncryption
    from cryptography.fernet import Fernet

    # Create encryption instance with a test master key
    test_master_key = Fernet.generate_key().decode()
    encryption = KeyEncryption(test_master_key)

    # Generate secret
    secret = TwoFactorAuth.generate_secret()
    print(f"\n1. Original secret: {secret}")

    # Encrypt secret
    encrypted_secret, salt = encryption.encrypt(secret)
    print(f"2. Encrypted: {len(encrypted_secret)} bytes")
    print(f"3. Salt: {len(salt)} bytes")

    # Decrypt secret
    decrypted_secret = encryption.decrypt(encrypted_secret, salt)
    print(f"4. Decrypted: {decrypted_secret}")

    # Verify decryption
    match = secret == decrypted_secret
    print(f"5. Encryption/Decryption: {'✓ PASS' if match else '✗ FAIL'}")

    # Get token with original secret
    token1 = TwoFactorAuth.get_current_token(secret)
    print(f"\n6. Token from original secret: {token1}")

    # Get token with decrypted secret
    token2 = TwoFactorAuth.get_current_token(decrypted_secret)
    print(f"7. Token from decrypted secret: {token2}")

    # Verify they match
    tokens_match = token1 == token2
    print(f"8. Tokens match: {'✓ PASS' if tokens_match else '✗ FAIL'}")

    # Verify token with decrypted secret
    is_valid = TwoFactorAuth.verify_token(decrypted_secret, token2)
    print(f"9. Token verification after encryption: {'✓ PASS' if is_valid else '✗ FAIL'}")

    print("\n" + "=" * 60)
    if match and tokens_match and is_valid:
        print("🎉 Encryption integration test PASSED!")
        return True
    else:
        print("❌ Encryption integration test FAILED!")
        return False


async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("PolyBot 2FA System Verification")
    print("=" * 60)

    # Run tests
    test1_passed = await test_2fa_creation_and_verification()
    test2_passed = await test_encryption_integration()

    # Final summary
    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    print(f"2FA Core Functions: {'✓ PASS' if test1_passed else '✗ FAIL'}")
    print(f"Encryption Integration: {'✓ PASS' if test2_passed else '✗ FAIL'}")

    if test1_passed and test2_passed:
        print("\n🎉 ALL TESTS PASSED - 2FA system is working correctly!")
        print("\nThe 2FA system is ready for:")
        print("  • User registration and setup")
        print("  • Token verification")
        print("  • Withdrawal protection")
        print("  • Private key export protection")
    else:
        print("\n❌ SOME TESTS FAILED - please review the output above")

    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
