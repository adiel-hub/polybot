"""
Check wallet status - database vs on-chain balance.
"""
import asyncio
from web3 import Web3
from database.connection import Database
from database.repositories.wallet_repo import WalletRepository
from database.repositories.user_repo import UserRepository
from services.trading_service import TradingService
from core.wallet.encryption import KeyEncryption
from config.settings import settings
from config.constants import USDC_ADDRESS


async def main():
    print("=" * 80)
    print("WALLET STATUS CHECK")
    print("=" * 80)
    print()

    db = Database(settings.database_path)
    await db.initialize()
    user_repo = UserRepository(db)
    wallet_repo = WalletRepository(db)
    key_encryption = KeyEncryption(settings.master_encryption_key)
    trading_service = TradingService(db, key_encryption)

    users = await user_repo.get_all_active()
    if not users:
        print("❌ No users found")
        await db.close()
        return

    user = users[0]
    wallet = await wallet_repo.get_by_user_id(user.id)

    print(f"👤 User: {user.telegram_id}")
    print(f"📬 Wallet Address: {wallet.address}")
    print()

    # Database balance
    print(f"💾 Database Balance: ${wallet.usdc_balance:.2f}")
    print()

    # On-chain balance via CLOB client
    print("🔗 Checking on-chain balance...")
    client = await trading_service._get_clob_client(user.id)
    if client:
        try:
            allowance_info = await client.check_allowance()
            on_chain_balance = float(allowance_info.get('balance', 0))
            print(f"💰 On-chain Balance (via CLOB): ${on_chain_balance:.2f}")
        except Exception as e:
            print(f"⚠️  Could not check via CLOB: {e}")
            on_chain_balance = 0
    else:
        on_chain_balance = 0
        print("⚠️  Could not initialize CLOB client")

    print()

    # Direct web3 check
    print("🔗 Checking on-chain balance (via Web3)...")
    try:
        w3 = Web3(Web3.HTTPProvider(settings.polygon_rpc_url))

        # USDC contract
        usdc_abi = [
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function",
            }
        ]

        usdc_contract = w3.eth.contract(address=Web3.to_checksum_address(USDC_ADDRESS), abi=usdc_abi)
        balance_wei = usdc_contract.functions.balanceOf(Web3.to_checksum_address(wallet.address)).call()
        balance_usdc = balance_wei / 1_000_000  # USDC has 6 decimals

        print(f"💵 USDC Balance (Web3): ${balance_usdc:.2f}")
        print()

        if balance_usdc == 0:
            print("=" * 80)
            print("⚠️  YOUR WALLET HAS NO USDC ON-CHAIN!")
            print("=" * 80)
            print()
            print("To deposit USDC to your wallet:")
            print(f"1. Send USDC (on Polygon network) to: {wallet.address}")
            print(f"2. Network: Polygon (MATIC)")
            print(f"3. Token: USDC")
            print(f"4. Amount: At least $5-10 for testing")
            print()
            print("After sending, wait a few minutes for confirmation, then:")
            print("- The bot will auto-detect the deposit via WebSocket")
            print("- Or manually check balance in the bot")
            print()
        elif abs(balance_usdc - wallet.usdc_balance) > 0.01:
            print("=" * 80)
            print("⚠️  BALANCE MISMATCH!")
            print("=" * 80)
            print(f"Database shows: ${wallet.usdc_balance:.2f}")
            print(f"On-chain actual: ${balance_usdc:.2f}")
            print()
            print("Syncing database with on-chain balance...")
            await wallet_repo.update_balance(wallet.id, balance_usdc)
            print("✅ Balance synced!")
            print()
        else:
            print("✅ Database and on-chain balances match!")
            print()

    except Exception as e:
        print(f"❌ Web3 check failed: {e}")

    await db.close()
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
