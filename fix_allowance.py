"""
Fix USDC allowance for trading.
This approves the Polymarket CLOB contract to spend your USDC.
"""
import asyncio
from database.connection import Database
from database.repositories.user_repo import UserRepository
from services.trading_service import TradingService
from core.wallet.encryption import KeyEncryption
from config.settings import settings


async def main():
    print("=" * 80)
    print("FIXING USDC ALLOWANCE FOR POLYMARKET TRADING")
    print("=" * 80)
    print()

    # Initialize
    db = Database(settings.database_path)
    await db.initialize()

    key_encryption = KeyEncryption(settings.master_encryption_key)
    trading_service = TradingService(db, key_encryption)
    user_repo = UserRepository(db)

    # Get user
    users = await user_repo.get_all_active()
    if not users:
        print("❌ No users found")
        await db.close()
        return

    user = users[0]
    print(f"✅ User: {user.telegram_id}")
    print()

    # Get CLOB client
    print("🔄 Initializing CLOB client...")
    client = await trading_service._get_clob_client(user.id)

    if not client:
        print("❌ Failed to initialize CLOB client")
        print("   The API keys may need to be regenerated.")
        print("   Please use the bot's /start command to regenerate keys.")
        await db.close()
        return

    print("✅ CLOB client initialized")
    print()

    # Check current allowance
    print("🔍 Checking current USDC allowance...")
    try:
        allowance_info = await client.check_allowance()
        print(f"   Current allowance: {allowance_info}")
    except Exception as e:
        print(f"⚠️  Could not check allowance: {e}")
        allowance_info = {"allowance": 0}

    print()

    # Set allowance to unlimited
    print("🔄 Setting USDC allowance (this requires a blockchain transaction)...")
    print("   This will allow the Polymarket CLOB contract to spend your USDC.")
    print("   Please wait 10-30 seconds...")
    print()

    try:
        success = await client.set_allowance()

        if success:
            print("✅ Allowance set successfully!")
            print("   You can now trade on Polymarket!")
        else:
            print("❌ Failed to set allowance")
            print("   This could be due to:")
            print("   1. Insufficient POL for gas fees")
            print("   2. RPC connection issues")
            print("   3. Invalid API keys")
    except Exception as e:
        print(f"❌ Error setting allowance: {e}")

    print()
    print("=" * 80)

    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
