"""
Check complete bot status - all requirements for trading and withdrawals.
"""
import asyncio
from web3 import Web3
from eth_account import Account
from database.connection import Database
from database.repositories.user_repo import UserRepository
from database.repositories.wallet_repo import WalletRepository
from config.settings import settings
from config.constants import USDC_ADDRESS, USDC_E_ADDRESS


async def main():
    print("=" * 80)
    print("POLYBOT STATUS CHECK")
    print("=" * 80)
    print()

    # Initialize
    db = Database(settings.database_path)
    await db.initialize()
    user_repo = UserRepository(db)
    wallet_repo = WalletRepository(db)

    # Get user
    users = await user_repo.get_all_active()
    if not users:
        print("❌ No users found - register via Telegram bot first")
        await db.close()
        return

    user = users[0]
    wallet = await wallet_repo.get_by_user_id(user.id)

    print(f"👤 User: {user.telegram_id}")
    print(f"📬 Wallet: {wallet.address}")
    print()

    # Check balances
    print("=" * 80)
    print("BALANCE CHECK")
    print("=" * 80)
    print()

    w3 = Web3(Web3.HTTPProvider(settings.polygon_rpc_url))
    usdc_abi = [{
        'constant': True,
        'inputs': [{'name': '_owner', 'type': 'address'}],
        'name': 'balanceOf',
        'outputs': [{'name': 'balance', 'type': 'uint256'}],
        'type': 'function',
    }]

    # Check Native USDC
    usdc_native_contract = w3.eth.contract(
        address=Web3.to_checksum_address(USDC_ADDRESS),
        abi=usdc_abi
    )
    native_balance = usdc_native_contract.functions.balanceOf(
        Web3.to_checksum_address(wallet.address)
    ).call() / 1_000_000

    # Check USDC.e
    usdc_e_contract = w3.eth.contract(
        address=Web3.to_checksum_address(USDC_E_ADDRESS),
        abi=usdc_abi
    )
    usdc_e_balance = usdc_e_contract.functions.balanceOf(
        Web3.to_checksum_address(wallet.address)
    ).call() / 1_000_000

    print(f"💵 Native USDC: ${native_balance:.2f}")
    print(f"💰 USDC.e (Polymarket): ${usdc_e_balance:.2f}")
    print(f"📊 Database: ${wallet.usdc_balance:.2f}")
    print()

    # Trading status
    if usdc_e_balance > 0:
        print("✅ TRADING: Ready (has USDC.e)")
    elif native_balance > 0:
        print("⚠️  TRADING: Need to swap Native USDC → USDC.e")
        print("   See: SOLUTION_BALANCE_ISSUE.md")
    else:
        print("❌ TRADING: No funds - deposit USDC.e")

    print()

    # Gas sponsor check
    print("=" * 80)
    print("GAS SPONSOR CHECK (for withdrawals)")
    print("=" * 80)
    print()

    if settings.gas_sponsor_private_key and settings.gas_sponsor_private_key != "your_sponsor_private_key_here":
        try:
            gas_account = Account.from_key(settings.gas_sponsor_private_key)
            print(f"📬 Gas Sponsor: {gas_account.address}")

            pol_balance = w3.eth.get_balance(gas_account.address) / 1e18
            print(f"⛽ POL Balance: {pol_balance:.4f} POL")
            print()

            if pol_balance >= 0.01:
                print("✅ WITHDRAWALS: Ready (sufficient POL)")
            else:
                print("⚠️  WITHDRAWALS: Low POL - send more to gas sponsor")
                print(f"   Send 0.1 POL to: {gas_account.address}")

        except Exception as e:
            print(f"❌ WITHDRAWALS: Invalid gas sponsor key")
            print(f"   Error: {e}")
    else:
        print("❌ WITHDRAWALS: No gas sponsor configured")
        print("   Run: python setup_gas_sponsor.py")

    print()

    # API credentials check
    print("=" * 80)
    print("API CREDENTIALS CHECK")
    print("=" * 80)
    print()

    if wallet.has_api_credentials:
        print("✅ API Credentials: Configured")
    else:
        print("⚠️  API Credentials: Not configured")
        print("   Run: python reinit_api_keys.py")

    print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()

    ready_for_trading = usdc_e_balance > 0 and wallet.has_api_credentials
    ready_for_withdrawals = (
        settings.gas_sponsor_private_key
        and settings.gas_sponsor_private_key != "your_sponsor_private_key_here"
        and pol_balance >= 0.01
    )

    if ready_for_trading and ready_for_withdrawals:
        print("🎉 ALL SYSTEMS GO! Bot is fully operational!")
    elif ready_for_trading:
        print("✅ Trading ready")
        print("⚠️  Withdrawals need gas sponsor funding")
    elif ready_for_withdrawals:
        print("⚠️  Trading needs USDC.e")
        print("✅ Withdrawals ready")
    else:
        print("⚠️  Setup incomplete - see actions above")

    print()
    print("=" * 80)

    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
