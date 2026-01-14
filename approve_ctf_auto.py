"""Auto-approve CTF contract for selling positions (no prompts)."""

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


async def auto_approve_ctf():
    """Automatically approve CTF contract for the first user."""
    print("=" * 80)
    print("AUTO CTF APPROVAL FOR SELLING")
    print("=" * 80)

    # Initialize database
    db = Database(settings.database_path)
    await db.initialize()

    user_repo = UserRepository(db)
    wallet_repo = WalletRepository(db)

    # Get first active user
    users = await user_repo.get_all_active()
    if not users:
        print("❌ No users found")
        await db.close()
        return

    user = users[0]
    wallet = await wallet_repo.get_by_user_id(user.id)

    print(f"\n✅ User: {user.telegram_id}")
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

    print(f"\n📋 Checking CTF approvals...\n")

    # Check and approve contracts
    gas_price = w3.eth.gas_price
    print(f"⛽ Gas Price: {gas_price / 1e9:.2f} Gwei\n")

    approved_count = 0
    for name, address in CLOB_CONTRACTS.items():
        try:
            is_approved = ctf_contract.functions.isApprovedForAll(
                Web3.to_checksum_address(user_address),
                Web3.to_checksum_address(address),
            ).call()

            if is_approved:
                print(f"✅ {name} - Already approved")
                continue

            print(f"🔄 Approving {name}...")

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

            print(f"📤 TX: {tx_hash.hex()}")
            print(f"⏳ Waiting for confirmation...")

            # Wait for receipt
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if receipt.status == 1:
                print(f"✅ {name} approved!\n")
                approved_count += 1
            else:
                print(f"❌ {name} failed!\n")

            # Delay between transactions
            if approved_count < len(CLOB_CONTRACTS):
                await asyncio.sleep(2)

        except Exception as e:
            print(f"❌ Error with {name}: {e}\n")

    print("=" * 80)
    print(f"COMPLETE: {approved_count} contracts approved for selling")
    print("=" * 80)

    if approved_count > 0:
        print("\n🎉 You can now sell your positions!")

    await db.close()


if __name__ == "__main__":
    asyncio.run(auto_approve_ctf())
