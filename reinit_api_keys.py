"""
Re-initialize API keys for the existing wallet.
This will generate new Polymarket CLOB API credentials for your existing wallet.
"""
import asyncio
from database.connection import Database
from database.repositories.user_repo import UserRepository
from database.repositories.wallet_repo import WalletRepository
from core.wallet.encryption import KeyEncryption
from core.polymarket.clob_client import PolymarketCLOB
from config.settings import settings


async def main():
    print("=" * 80)
    print("RE-INITIALIZE POLYMARKET API KEYS")
    print("=" * 80)
    print()

    db = Database(settings.database_path)
    await db.initialize()
    user_repo = UserRepository(db)
    wallet_repo = WalletRepository(db)
    key_encryption = KeyEncryption(settings.master_encryption_key)

    users = await user_repo.get_all_active()
    if not users:
        print("❌ No users found")
        await db.close()
        return

    user = users[0]
    wallet = await wallet_repo.get_by_user_id(user.id)

    print(f"👤 User: {user.telegram_id}")
    print(f"📬 Wallet: {wallet.address}")
    print(f"💰 Balance: ${wallet.usdc_balance:.2f}")
    print()

    # Decrypt private key
    print("🔐 Decrypting wallet private key...")
    try:
        private_key = key_encryption.decrypt(
            wallet.encrypted_private_key,
            wallet.encryption_salt,
        )
        print("✅ Private key decrypted")
    except Exception as e:
        print(f"❌ Failed to decrypt private key: {e}")
        await db.close()
        return

    print()

    # Create CLOB client with private key
    print("🔄 Initializing Polymarket CLOB client...")
    client = PolymarketCLOB(
        private_key=private_key,
        funder_address=wallet.address,
    )

    # Generate new API credentials
    print("🔑 Generating new API credentials...")
    print("   (This registers your wallet with Polymarket's CLOB API)")
    print()

    try:
        await client.initialize()

        if not client.api_credentials:
            print("❌ Failed to generate API credentials")
            await db.close()
            return

        print("✅ API credentials generated!")
        print()

        # Encrypt and store credentials
        print("💾 Storing encrypted credentials in database...")
        creds = client.api_credentials

        # Use wallet's existing salt for consistency
        enc_key = key_encryption.encrypt_with_salt(creds["api_key"], wallet.encryption_salt)
        enc_secret = key_encryption.encrypt_with_salt(creds["api_secret"], wallet.encryption_salt)
        enc_pass = key_encryption.encrypt_with_salt(creds["api_passphrase"], wallet.encryption_salt)

        await wallet_repo.update_api_credentials(
            wallet.id,
            enc_key,
            enc_secret,
            enc_pass,
        )

        print("✅ Credentials stored!")
        print()

        # Verify by checking balance
        print("🔍 Verifying API credentials (checking balance)...")
        allowance_info = await client.check_allowance()
        balance = float(allowance_info.get('balance', 0))

        print(f"✅ API credentials working!")
        print(f"   On-chain balance: ${balance:.2f}")
        print()

        if balance > 0:
            print("=" * 80)
            print("✅ SUCCESS! Your wallet is ready for trading!")
            print("=" * 80)
        else:
            print("=" * 80)
            print("⚠️  API keys initialized, but wallet has no USDC")
            print("=" * 80)
            print(f"Send USDC to: {wallet.address}")
            print("Network: Polygon")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

    await db.close()
    print()
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
