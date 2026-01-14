"""Manual script to approve CTF contract for selling positions."""

import asyncio
from web3 import Web3
from eth_account import Account

from database.connection import Database
from database.repositories.user_repo import UserRepository
from database.repositories.wallet_repo import WalletRepository
from config.settings import settings
from config.constants import CTF_CONTRACT, CLOB_CONTRACTS
from services.user_service import UserService
from core.wallet.encryption import KeyEncryption


async def approve_ctf_for_user():
    """Manually approve CTF contract for a user to enable selling."""
    print("=" * 80)
    print("MANUAL CTF APPROVAL FOR SELLING")
    print("=" * 80)

    # Initialize database
    db = Database(settings.database_path)
    await db.initialize()

    user_repo = UserRepository(db)
    wallet_repo = WalletRepository(db)

    # Get all users
    users = await user_repo.get_all_active()
    if not users:
        print("❌ No users found")
        await db.close()
        return

    # Show users
    print(f"\n📋 Found {len(users)} user(s):\n")
    for i, user in enumerate(users, 1):
        wallet = await wallet_repo.get_by_user_id(user.id)
        print(f"{i}. User ID: {user.telegram_id}, Wallet: {wallet.address if wallet else 'N/A'}")

    # Select user (default to first)
    user_index = 0
    if len(users) > 1:
        try:
            selection = input(f"\nSelect user (1-{len(users)}) [default: 1]: ").strip()
            if selection:
                user_index = int(selection) - 1
        except ValueError:
            print("Invalid selection, using first user")

    user = users[user_index]
    wallet = await wallet_repo.get_by_user_id(user.id)

    print(f"\n✅ Selected user: {user.telegram_id}")
    print(f"📬 Wallet: {wallet.address}")

    # Get user's private key
    user_service = UserService(db, KeyEncryption(settings.master_encryption_key))
    private_key = await user_service.get_private_key(user.id)

    if not private_key:
        print("❌ Could not decrypt private key")
        await db.close()
        return

    account = Account.from_key(private_key)
    user_address = account.address

    # Initialize web3
    w3 = Web3(Web3.HTTPProvider(settings.polygon_rpc_url))

    # Check POL balance
    pol_balance = w3.eth.get_balance(user_address) / 1e18
    print(f"💰 POL Balance: {pol_balance:.4f} POL")

    if pol_balance < 0.01:
        print("⚠️  Warning: Low POL balance. You need ~0.01 POL for gas fees.")
        proceed = input("Continue anyway? (y/n) [n]: ").strip().lower()
        if proceed != 'y':
            await db.close()
            return

    # CTF contract
    ctf_contract = w3.eth.contract(
        address=Web3.to_checksum_address(CTF_CONTRACT),
        abi=[
            {
                'constant': False,
                'inputs': [
                    {'name': 'operator', 'type': 'address'},
                    {'name': 'approved', 'type': 'bool'},
                ],
                'name': 'setApprovalForAll',
                'outputs': [],
                'type': 'function',
            },
            {
                'constant': True,
                'inputs': [
                    {'name': 'owner', 'type': 'address'},
                    {'name': 'operator', 'type': 'address'},
                ],
                'name': 'isApprovedForAll',
                'outputs': [{'name': '', 'type': 'bool'}],
                'type': 'function',
            },
        ],
    )

    print(f"\n📋 Checking current CTF approvals...\n")

    # Check current approvals
    contracts_to_approve = []
    for name, address in CLOB_CONTRACTS.items():
        try:
            is_approved = ctf_contract.functions.isApprovedForAll(
                Web3.to_checksum_address(user_address),
                Web3.to_checksum_address(address),
            ).call()

            status = "✅ Already Approved" if is_approved else "❌ Not Approved"
            print(f"{status} - {name} ({address[:10]}...)")

            if not is_approved:
                contracts_to_approve.append((name, address))
        except Exception as e:
            print(f"❌ Error checking {name}: {e}")

    if not contracts_to_approve:
        print("\n✅ All contracts are already approved for selling!")
        await db.close()
        return

    print(f"\n🔄 Need to approve {len(contracts_to_approve)} contract(s)")

    # Confirm
    proceed = input("\nProceed with approvals? (y/n) [y]: ").strip().lower()
    if proceed and proceed != 'y':
        print("❌ Cancelled")
        await db.close()
        return

    # Approve each contract
    gas_price = w3.eth.gas_price
    print(f"\n⛽ Gas Price: {gas_price / 1e9:.2f} Gwei")

    approved_count = 0
    for name, address in contracts_to_approve:
        try:
            print(f"\n🔄 Approving {name}...")

            # Build setApprovalForAll transaction
            tx = ctf_contract.functions.setApprovalForAll(
                Web3.to_checksum_address(address),
                True,
            ).build_transaction({
                'from': user_address,
                'nonce': w3.eth.get_transaction_count(user_address) + approved_count,
                'gas': 100000,
                'gasPrice': gas_price,
                'chainId': settings.chain_id,
            })

            # Sign and send
            signed = account.sign_transaction(tx)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

            print(f"📤 Transaction sent: {tx_hash.hex()}")
            print(f"⏳ Waiting for confirmation...")

            # Wait for receipt
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if receipt.status == 1:
                print(f"✅ {name} approved successfully!")
                approved_count += 1
            else:
                print(f"❌ {name} approval failed!")

            # Small delay between transactions
            if approved_count < len(contracts_to_approve):
                await asyncio.sleep(2)

        except Exception as e:
            print(f"❌ Failed to approve {name}: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 80)
    print(f"APPROVAL COMPLETE: {approved_count}/{len(contracts_to_approve)} contracts approved")
    print("=" * 80)

    if approved_count > 0:
        print("\n🎉 You can now sell your positions!")

    await db.close()


if __name__ == "__main__":
    asyncio.run(approve_ctf_for_user())
