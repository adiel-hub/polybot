# How to Create Gas Sponsor Wallet

## What is a Gas Sponsor Wallet?

The gas sponsor wallet pays for POL (gas fees) when users withdraw USDC. This makes withdrawals seamless - users don't need POL in their bot wallets.

## Quick Setup (3 Steps)

### Step 1: Generate a New Wallet

Run this command:

```bash
source .venv/bin/activate
python setup_gas_sponsor.py
```

The script will generate a new wallet and show you:
- **Address**: Where to send POL
- **Private Key**: What to add to test.env

Example output:
```
Address: 0x79492544750AeC588Aef72Ff237925da682a47cD
Private Key: c4ea360ce369b6e289ed75b8e0fcd4d190ef385c2e67bbc0af908d5636b810ff
```

**⚠️ SAVE THE PRIVATE KEY SECURELY!**

### Step 2: Add to test.env

Edit `test.env` and replace the placeholder:

```bash
# Before
GAS_SPONSOR_PRIVATE_KEY=your_sponsor_private_key_here

# After (use the key from Step 1)
GAS_SPONSOR_PRIVATE_KEY=0xc4ea360ce369b6e289ed75b8e0fcd4d190ef385c2e67bbc0af908d5636b810ff
```

Note: Add `0x` prefix if not already present.

### Step 3: Send POL to the Gas Sponsor

1. **Get POL** (MATIC):
   - Buy on exchange (Binance, Coinbase, etc.)
   - Or swap on Polygon DEX (QuickSwap, Uniswap)

2. **Send to gas sponsor address**:
   - Network: **Polygon (not Ethereum!)**
   - Token: **POL (MATIC)**
   - Amount: **0.1-0.5 POL** (enough for 100-200 withdrawals)
   - To: Your gas sponsor address from Step 1

3. **Verify**:
   ```bash
   python setup_gas_sponsor.py
   ```
   Should show: "✅ Sufficient POL for withdrawals!"

## Alternative: Use Existing Wallet

If you already have a wallet with POL:

1. **Export private key from MetaMask**:
   - Open MetaMask
   - Click Account Details → Show Private Key
   - Enter password → Copy key

2. **Add to test.env**:
   ```bash
   GAS_SPONSOR_PRIVATE_KEY=0xYOUR_PRIVATE_KEY_FROM_METAMASK
   ```

3. **Verify it has POL**:
   ```bash
   python setup_gas_sponsor.py
   ```

## How Much POL Do You Need?

| POL Amount | Estimated Withdrawals |
|------------|---------------------|
| 0.1 POL    | ~50 withdrawals     |
| 0.5 POL    | ~250 withdrawals    |
| 1.0 POL    | ~500 withdrawals    |

**Recommendation**: Start with 0.1-0.5 POL, refill when low.

## Verification

After setup, verify everything works:

```bash
# 1. Check gas sponsor is configured
python setup_gas_sponsor.py

# Should show:
# ✅ Valid gas sponsor configured: 0x7949...
# 💰 POL Balance: 0.1234 POL
# ✅ Sufficient POL for withdrawals!

# 2. Restart the bot
ENV_FILE=test.env python run.py
```

## Troubleshooting

### "Non-hexadecimal digit found"
- Check that private key starts with `0x`
- Verify it's a valid 64-character hex string (after `0x`)
- Example: `0xc4ea360ce369b6e289ed75b8e0fcd4d190ef385c2e67bbc0af908d5636b810ff`

### "Insufficient POL"
- Send more POL to the gas sponsor address
- Make sure it's on **Polygon network**, not Ethereum

### "Invalid private key"
- Double-check you copied the entire key
- Don't include quotes or extra spaces
- Format: `GAS_SPONSOR_PRIVATE_KEY=0xabcd1234...` (no quotes)

## Security Notes

🔒 **Important**:
- The gas sponsor private key is sensitive - keep it secure
- Only needs enough POL for gas fees (~0.5-1 POL)
- Different from your main wallet private key
- Dedicated for paying withdrawal gas fees only

## What Happens Next?

Once configured:
1. ✅ Users can withdraw USDC via the bot
2. ✅ Gas sponsor automatically pays POL gas fees
3. ✅ USDC goes directly to user's wallet
4. ✅ Seamless experience - users don't need POL

---

**Need help?** Run `python setup_gas_sponsor.py` to check your configuration.
