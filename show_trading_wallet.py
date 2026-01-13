"""
Show which wallet address is being used for trading.
"""
import asyncio
from database.connection import Database
from database.repositories.user_repo import UserRepository
from services.trading_service import TradingService
from core.wallet.encryption import KeyEncryption
from config.settings import settings


async def main():
    print("=" * 80)
    print("TRADING WALLET ADDRESS CHECK")
    print("=" * 80)
    print()

    db = Database(settings.database_path)
    await db.initialize()
    user_repo = UserRepository(db)
    key_encryption = KeyEncryption(settings.master_encryption_key)
    trading_service = TradingService(db, key_encryption)

    users = await user_repo.get_all_active()
    if not users:
        print("❌ No users found")
        await db.close()
        return

    user = users[0]

    # Get CLOB client
    print("🔄 Initializing CLOB client (this will show which wallet it's using)...")
    print()

    client = await trading_service._get_clob_client(user.id)

    if not client:
        print("❌ Could not initialize CLOB client")
        await db.close()
        return

    # The CLOB client has a `wallet` property or we can check via get_address()
    try:
        # Try to get the address from the client
        if hasattr(client, 'address'):
            trading_address = client.address
        elif hasattr(client, 'wallet'):
            trading_address = client.wallet.address if hasattr(client.wallet, 'address') else 'Unknown'
        else:
            trading_address = 'Unknown'

        print(f"📬 CLOB Client Wallet Address: {trading_address}")
        print()

        # Also show database wallet
        from database.repositories.wallet_repo import WalletRepository
        wallet_repo = WalletRepository(db)
        db_wallet = await wallet_repo.get_by_user_id(user.id)

        print(f"💾 Database Wallet Address: {db_wallet.address}")
        print()

        if trading_address.lower() != db_wallet.address.lower() and trading_address != 'Unknown':
            print("⚠️  MISMATCH! CLOB client is using a different wallet than database!")
            print("   This explains why trading fails - funds are in different wallet.")
            print()
            print(f"   Funds are in: {db_wallet.address}")
            print(f"   Trading uses: {trading_address}")
            print()
        else:
            print("✅ Wallet addresses match")

    except Exception as e:
        print(f"Could not determine trading address: {e}")

    await db.close()
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
