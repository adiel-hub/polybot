"""
Setup gas sponsor wallet for withdrawals.
The gas sponsor wallet pays POL (gas fees) for USDC withdrawals.
"""
from eth_account import Account
from web3 import Web3
from config.settings import settings

print("=" * 80)
print("GAS SPONSOR WALLET SETUP")
print("=" * 80)
print()

# Option 1: Generate a new wallet
print("Option 1: Generate a NEW gas sponsor wallet")
print("-" * 80)
new_account = Account.create()
print(f"Address: {new_account.address}")
print(f"Private Key: {new_account.key.hex()}")
print()
print("⚠️  IMPORTANT:")
print("1. Save this private key securely!")
print("2. Send ~0.1 POL (MATIC) to this address for gas fees")
print("3. Add to test.env: GAS_SPONSOR_PRIVATE_KEY={new_account.key.hex()}")
print()

# Option 2: Use existing wallet
print("Option 2: Use an EXISTING wallet with POL")
print("-" * 80)
print("If you already have a wallet with POL on Polygon:")
print("1. Export the private key from MetaMask/your wallet")
print("2. Add to test.env: GAS_SPONSOR_PRIVATE_KEY=0xYOUR_PRIVATE_KEY_HERE")
print()

# Check if current config has a valid key
print("=" * 80)
print("CURRENT CONFIGURATION CHECK")
print("=" * 80)

if settings.gas_sponsor_private_key and settings.gas_sponsor_private_key != "your_sponsor_private_key_here":
    try:
        account = Account.from_key(settings.gas_sponsor_private_key)
        print(f"✅ Valid gas sponsor configured: {account.address}")

        # Check POL balance
        w3 = Web3(Web3.HTTPProvider(settings.polygon_rpc_url))
        balance_wei = w3.eth.get_balance(account.address)
        balance_pol = balance_wei / 1e18

        print(f"💰 POL Balance: {balance_pol:.4f} POL")

        if balance_pol < 0.01:
            print("⚠️  Low balance! Send at least 0.1 POL for gas fees")
        else:
            print("✅ Sufficient POL for withdrawals!")

    except Exception as e:
        print(f"❌ Invalid private key: {e}")
else:
    print("❌ No gas sponsor configured (using placeholder)")
    print()
    print("To enable withdrawals:")
    print("1. Choose Option 1 or 2 above")
    print("2. Update test.env with the private key")
    print("3. Restart the bot")

print()
print("=" * 80)
print("WHY DO WE NEED THIS?")
print("=" * 80)
print()
print("When users withdraw USDC:")
print("- USDC transfer requires gas (POL)")
print("- User's bot wallet might not have POL")
print("- Gas sponsor pays the POL gas fee")
print("- Makes withdrawals seamless for users")
print()
print("Recommended: Keep ~0.5-1 POL in gas sponsor for ~100-200 withdrawals")
print("=" * 80)
