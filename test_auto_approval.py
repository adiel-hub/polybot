"""Test auto-approval of USDC.e for trading on deposit."""

import asyncio
from web3 import Web3

from database.connection import Database
from database.repositories.user_repo import UserRepository
from database.repositories.wallet_repo import WalletRepository
from config.settings import settings
from config.constants import USDC_E_ADDRESS, CLOB_CONTRACTS
from core.websocket.deposit_subscriber import DepositSubscriber


async def check_allowances(wallet_address: str):
    """Check current allowances for all CLOB contracts."""
    w3 = Web3(Web3.HTTPProvider(settings.polygon_rpc_url))
    usdc_e = w3.eth.contract(
        address=Web3.to_checksum_address(USDC_E_ADDRESS),
        abi=[
            {
                'constant': True,
                'inputs': [
                    {'name': '_owner', 'type': 'address'},
                    {'name': '_spender', 'type': 'address'},
                ],
                'name': 'allowance',
                'outputs': [{'name': '', 'type': 'uint256'}],
                'type': 'function',
            },
        ],
    )

    print(f"\n📋 Checking allowances for {wallet_address[:10]}...\n")

    for name, address in CLOB_CONTRACTS.items():
        allowance = usdc_e.functions.allowance(
            Web3.to_checksum_address(wallet_address),
            Web3.to_checksum_address(address),
        ).call()

        max_uint256 = 2**256 - 1
        is_approved = allowance >= max_uint256 // 2

        status = "✅ Approved" if is_approved else "❌ Not Approved"
        print(f"{status} - {name} ({address[:10]}...)")
        print(f"   Allowance: {allowance}")

    print()


async def test_auto_approval():
    """Test the auto-approval functionality."""
    print("=" * 80)
    print("TESTING AUTO-APPROVAL ON DEPOSIT")
    print("=" * 80)

    # Initialize database
    db = Database(settings.database_path)
    await db.initialize()

    user_repo = UserRepository(db)
    wallet_repo = WalletRepository(db)

    # Get test user
    users = await user_repo.get_all_active()
    if not users:
        print("❌ No users found")
        await db.close()
        return

    user = users[0]
    wallet = await wallet_repo.get_by_user_id(user.id)

    print(f"\n👤 User: {user.telegram_id}")
    print(f"📬 Wallet: {wallet.address}")

    # Check POL balance
    w3 = Web3(Web3.HTTPProvider(settings.polygon_rpc_url))
    pol_balance = w3.eth.get_balance(wallet.address) / 1e18
    print(f"💰 POL Balance: {pol_balance:.4f} POL")

    # Check current allowances
    await check_allowances(wallet.address)

    # Initialize deposit subscriber (without starting WebSocket)
    deposit_subscriber = DepositSubscriber(
        db=db,
        alchemy_ws_url=settings.alchemy_ws_url,
        bot_send_message=None,  # No bot messages during test
    )

    # Test auto-approval
    print("🔄 Testing auto-approval logic...\n")

    try:
        result = await deposit_subscriber._auto_approve_trading(wallet, user)

        if result:
            print(f"✅ Auto-approval result:\n{result}")
        else:
            print("ℹ️  No approvals needed (already approved)")

        # Check allowances after auto-approval
        print("\n" + "=" * 80)
        print("ALLOWANCES AFTER AUTO-APPROVAL")
        print("=" * 80)
        await check_allowances(wallet.address)

    except Exception as e:
        print(f"❌ Error during auto-approval: {e}")
        import traceback
        traceback.print_exc()

    await db.close()


if __name__ == "__main__":
    asyncio.run(test_auto_approval())
