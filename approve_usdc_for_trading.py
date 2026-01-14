"""Approve USDC.e for Polymarket CLOB contracts."""

import asyncio
from web3 import Web3
from eth_account import Account

from database.connection import Database
from database.repositories.user_repo import UserRepository
from database.repositories.wallet_repo import WalletRepository
from core.wallet.encryption import KeyEncryption
from config.settings import settings
from config.constants import USDC_E_ADDRESS


async def main():
    print("=" * 80)
    print("APPROVE USDC.E FOR POLYMARKET TRADING")
    print("=" * 80)
    print()

    # Initialize
    db = Database(settings.database_path)
    await db.initialize()

    user_repo = UserRepository(db)
    wallet_repo = WalletRepository(db)
    key_encryption = KeyEncryption(settings.master_encryption_key)

    # Get user
    users = await user_repo.get_all_active()
    if not users:
        print("❌ No users found")
        await db.close()
        return

    user = users[0]
    wallet = await wallet_repo.get_by_user_id(user.id)

    print(f"👤 User: {user.telegram_id}")
    print(f"📬 Wallet: {wallet.address}")
    print()

    # Get private key
    from services.user_service import UserService
    user_service = UserService(db, key_encryption)
    private_key = await user_service.get_private_key(user.id)

    # Setup web3
    w3 = Web3(Web3.HTTPProvider(settings.polygon_rpc_url))
    account = Account.from_key(private_key)

    # USDC.e contract
    usdc_abi = [
        {
            'constant': False,
            'inputs': [
                {'name': '_spender', 'type': 'address'},
                {'name': '_value', 'type': 'uint256'},
            ],
            'name': 'approve',
            'outputs': [{'name': '', 'type': 'bool'}],
            'type': 'function',
        }
    ]

    usdc_e = w3.eth.contract(
        address=Web3.to_checksum_address(USDC_E_ADDRESS),
        abi=usdc_abi
    )

    # CLOB contract addresses (approve all three)
    clob_contracts = {
        "CLOB Exchange": "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E",
        "CTF Exchange": "0xC5d563A36AE78145C45a50134d48A1215220f80a",
        "NegRisk Exchange": "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296",
    }

    max_uint256 = 2**256 - 1

    for name, address in clob_contracts.items():
        print(f"📝 Approving {name} ({address[:10]}...)...")

        try:
            # Build approval transaction
            tx = usdc_e.functions.approve(
                Web3.to_checksum_address(address),
                max_uint256
            ).build_transaction({
                'from': account.address,
                'nonce': w3.eth.get_transaction_count(account.address),
                'gas': 100000,
                'gasPrice': w3.eth.gas_price,
                'chainId': 137,
            })

            # Sign and send
            signed = account.sign_transaction(tx)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

            print(f"   TX: {tx_hash.hex()}")

            # Wait for confirmation
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if receipt.status == 1:
                print(f"   ✅ Approved! Block: {receipt.blockNumber}")
            else:
                print(f"   ❌ Transaction failed")

            print()

        except Exception as e:
            print(f"   ❌ Error: {e}")
            print()

    print("=" * 80)
    print("✅ USDC.e approval complete - you can now trade on Polymarket!")
    print("=" * 80)

    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
