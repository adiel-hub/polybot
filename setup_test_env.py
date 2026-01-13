#!/usr/bin/env python3
"""Setup helper for integration test environment.

This script helps you configure test.env with the required credentials.
Run this before running integration tests.
"""

import os
from cryptography.fernet import Fernet
from pathlib import Path


def generate_encryption_key():
    """Generate a new Fernet encryption key."""
    return Fernet.generate_key().decode()


def check_test_env():
    """Check if test.env is properly configured."""
    env_path = Path("test.env")

    if not env_path.exists():
        print("❌ test.env not found!")
        return False

    # Load test.env
    config = {}
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip()

    # Required fields
    required = {
        'TELEGRAM_BOT_TOKEN': 'Test bot token from @BotFather',
        'MASTER_ENCRYPTION_KEY': 'Encryption key (generate below)',
        'POLYGON_RPC_URL': 'Polygon RPC URL from Alchemy',
        'ALCHEMY_API_KEY': 'Alchemy API key',
    }

    # Optional but recommended for automated tests
    optional = {
        'TEST_FUNDING_WALLET_PRIVATE_KEY': 'Your wallet private key (for funding tests)',
        'TEST_FUNDING_WALLET_ADDRESS': 'Your wallet address',
    }

    print("\n" + "="*80)
    print("TEST ENVIRONMENT CONFIGURATION CHECK")
    print("="*80 + "\n")

    missing_required = []
    missing_optional = []

    # Check required fields
    print("📋 Required Configuration:")
    for key, description in required.items():
        value = config.get(key, '')
        if value and 'your_' not in value and 'here' not in value:
            print(f"  ✅ {key}: Configured")
        else:
            print(f"  ❌ {key}: NOT configured ({description})")
            missing_required.append(key)

    # Check optional fields
    print("\n📋 Optional Configuration (for automated tests):")
    for key, description in optional.items():
        value = config.get(key, '')
        if value and value != '':
            print(f"  ✅ {key}: Configured")
        else:
            print(f"  ⚠️  {key}: Not configured ({description})")
            missing_optional.append(key)

    # Test amounts
    print("\n💰 Test Amounts:")
    print(f"  • Deposit: ${config.get('TEST_DEPOSIT_AMOUNT', '10.0')} USDC")
    print(f"  • Trade: ${config.get('TEST_TRADE_AMOUNT', '5.0')} USDC")
    print(f"  • Withdrawal: ${config.get('TEST_WITHDRAWAL_AMOUNT', '3.0')} USDC")

    print("\n" + "="*80)

    if missing_required:
        print("\n❌ CONFIGURATION INCOMPLETE!")
        print(f"\nMissing required fields: {', '.join(missing_required)}")
        print("\nPlease update test.env with the required values.")
        return False

    if missing_optional:
        print("\n⚠️  OPTIONAL CONFIGURATION MISSING")
        print(f"\nMissing optional fields: {', '.join(missing_optional)}")
        print("\nYou can still run manual tests, but automated tests won't work.")
        print("Add these fields to test.env to enable automated testing.")
    else:
        print("\n✅ ALL CONFIGURATION COMPLETE!")
        print("\nYou can run:")
        print("  • Manual tests via Telegram bot")
        print("  • Automated integration tests")

    return True


def interactive_setup():
    """Interactive setup wizard."""
    print("\n" + "="*80)
    print("INTEGRATION TEST ENVIRONMENT SETUP WIZARD")
    print("="*80 + "\n")

    print("This wizard will help you configure test.env for integration testing.\n")

    # Generate encryption key
    print("1️⃣  ENCRYPTION KEY")
    print("   Generating a new encryption key...\n")
    encryption_key = generate_encryption_key()
    print(f"   Generated key: {encryption_key}\n")
    print("   ✅ Copy this to test.env as MASTER_ENCRYPTION_KEY\n")

    # Alchemy setup
    print("2️⃣  ALCHEMY API KEY")
    print("   You need a free Alchemy API key for Polygon.\n")
    print("   Steps:")
    print("   1. Go to https://www.alchemy.com/")
    print("   2. Sign up (free)")
    print("   3. Create a new app:")
    print("      - Chain: Polygon")
    print("      - Network: Polygon Mainnet")
    print("   4. Copy the API key")
    print("   5. Add to test.env as ALCHEMY_API_KEY")
    print("   6. Also update POLYGON_RPC_URL with:")
    print(f"      https://polygon-mainnet.g.alchemy.com/v2/YOUR_API_KEY\n")

    # Telegram bot
    print("3️⃣  TELEGRAM TEST BOT")
    print("   Create a separate test bot (don't use production bot!).\n")
    print("   Steps:")
    print("   1. Open Telegram and message @BotFather")
    print("   2. Send /newbot")
    print("   3. Follow prompts to create bot")
    print("   4. Copy the bot token")
    print("   5. Add to test.env as TELEGRAM_BOT_TOKEN\n")

    # Get Telegram ID
    print("4️⃣  YOUR TELEGRAM ID")
    print("   You need your Telegram user ID for admin access.\n")
    print("   Steps:")
    print("   1. Message @userinfobot on Telegram")
    print("   2. Copy your user ID")
    print("   3. Add to test.env as ADMIN_TELEGRAM_IDS\n")

    # Funding wallet (optional)
    print("5️⃣  FUNDING WALLET (Optional - for automated tests)")
    print("   This is YOUR personal wallet that will fund test wallets.\n")
    print("   Requirements:")
    print("   • ~$50-100 USDC on Polygon")
    print("   • ~0.5 POL for gas fees")
    print("\n   Steps:")
    print("   1. Export private key from MetaMask/wallet")
    print("   2. Add to test.env as TEST_FUNDING_WALLET_PRIVATE_KEY")
    print("   3. Add your address as TEST_FUNDING_WALLET_ADDRESS")
    print("\n   ⚠️  SECURITY: Use a dedicated test wallet, not your main wallet!")
    print("   ⚠️  NEVER commit test.env to git!\n")

    print("="*80)
    print("\n✅ Setup information displayed!")
    print("\nNext steps:")
    print("1. Edit test.env with the values above")
    print("2. Run: python setup_test_env.py --check")
    print("3. If all checks pass, you're ready to test!\n")


def main():
    """Main entry point."""
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '--check':
        # Check configuration
        success = check_test_env()
        sys.exit(0 if success else 1)

    elif len(sys.argv) > 1 and sys.argv[1] == '--key':
        # Just generate and print encryption key
        print(generate_encryption_key())

    else:
        # Interactive setup
        interactive_setup()


if __name__ == "__main__":
    main()
