# Token Approvals for Trading

## Overview

Before users can trade on Polymarket, they need to approve the CLOB (Central Limit Order Book) exchange contract to spend their USDC tokens. PolyBot **automatically handles this on the first deposit**, so users can trade immediately without manual setup.

---

## How It Works

### Automatic Approval Flow

```
1. User deposits USDC to wallet
   ↓
2. Alchemy webhook detects deposit
   ↓
3. Check if first deposit (usdc_approved = FALSE)
   ↓
4. Initialize CLOB client with wallet's private key
   ↓
5. Call set_allowance() via Polymarket's gasless relayer
   ↓
6. Set unlimited USDC approval for exchange contract
   ↓
7. Mark usdc_approved = TRUE in database
   ↓
8. User receives deposit notification
   ↓
9. ✅ User can trade immediately!
```

### Implementation

**File**: [core/webhook/alchemy_webhook.py:269](core/webhook/alchemy_webhook.py#L269)

```python
async def _setup_trading_approvals(self, wallet) -> None:
    """
    Set up USDC token approvals for trading on first deposit.
    Uses Polymarket's gasless relayer - no POL needed for gas.
    """
    # Decrypt private key
    encryption = KeyEncryption(settings.master_encryption_key)
    private_key = encryption.decrypt(
        wallet.encrypted_private_key,
        wallet.encryption_salt,
    )

    # Create CLOB client
    client = PolymarketCLOB(
        private_key=private_key,
        funder_address=wallet.address,
    )

    # Initialize (creates API credentials)
    await client.initialize()

    # Set unlimited USDC approval via gasless relayer
    success = await client.set_allowance()

    if success:
        # Mark as approved
        await wallet_repo.update(wallet.id, usdc_approved=True)
```

---

## What Gets Approved

### 1. USDC → CLOB Exchange

**Contract**: Polymarket CLOB Exchange Contract on Polygon
**Token**: USDC (0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174)
**Amount**: Unlimited (2^256-1)
**Method**: ERC-20 `approve(spender, amount)`

This allows the exchange contract to transfer USDC from the user's wallet when placing orders.

### Technical Details

```solidity
// What happens behind the scenes:
USDC.approve(
    spender: CLOB_EXCHANGE_CONTRACT,
    amount: type(uint256).max  // Unlimited
)
```

**Approval Address**: Polymarket CLOB Exchange Contract
**Network**: Polygon (Chain ID: 137)
**Gas Cost**: 0 POL (uses Polymarket's gasless relayer)

---

## Gasless Relayer

PolyBot uses Polymarket's **gasless relayer** for approvals, which means:

✅ **No POL needed** - Users don't need native Polygon tokens for gas
✅ **No transaction signing** - Relayer handles the blockchain transaction
✅ **Instant approvals** - No waiting for transaction confirmation
✅ **Zero cost** - Polymarket covers the gas fees

### How Gasless Relayer Works

```
1. Client signs approval message (off-chain)
   ↓
2. Sends signed message to Polymarket relayer API
   ↓
3. Relayer submits transaction on-chain
   ↓
4. Relayer pays gas fees
   ↓
5. ✅ Approval complete!
```

**Implementation**: [py-clob-client](https://github.com/Polymarket/py-clob-client)

```python
# Uses relayer automatically
params = BalanceAllowanceParams(
    asset_type=AssetType.COLLATERAL,  # USDC
    signature_type=0,  # EOA wallet
)
result = self.client.update_balance_allowance(params)
```

---

## Database Tracking

### wallets.usdc_approved

**Type**: `BOOLEAN`
**Default**: `FALSE`
**Purpose**: Track whether USDC approval has been set

```sql
CREATE TABLE wallets (
    ...
    usdc_approved BOOLEAN DEFAULT FALSE,
    ...
);
```

**States**:
- `FALSE` - No approval set, will be done on first deposit
- `TRUE` - Approval set, user can trade

**Queries**:
```sql
-- Check if user needs approval
SELECT usdc_approved FROM wallets WHERE user_id = $1;

-- Mark as approved
UPDATE wallets SET usdc_approved = TRUE WHERE id = $1;

-- Find users needing approval (shouldn't happen after this feature)
SELECT * FROM wallets WHERE usdc_approved = FALSE AND usdc_balance > 0;
```

---

## User Experience

### Before This Feature ❌

```
1. User deposits USDC ✅
2. User tries to trade ❌
   → Error: "USDC allowance not set"
3. User stuck - no UI to fix it ❌
4. User can't trade ❌
```

### After This Feature ✅

```
1. User deposits USDC ✅
2. Auto-approval happens in background ✅
   → User sees: "🔐 Setting up trading approvals..."
3. User receives: "📈 You're ready to trade!" ✅
4. User can trade immediately ✅
```

---

## Deposit Notification

**Before** (no approval):
```
💰 Deposit Received!

💵 Amount: $100.00 USDC
🔗 TX: 0x1234567890abcdef...

📈 You're ready to trade!
```

**After** (with approval on first deposit):
```
💰 Deposit Received!

💵 Amount: $100.00 USDC
🔗 TX: 0x1234567890abcdef...

🔐 Setting up trading approvals...

📈 You're ready to trade!
```

---

## Error Handling

### Approval Fails

If approval fails (network error, relayer down, etc.):

1. **Error logged** but not shown to user
2. **Deposit notification still sent**
3. **User can still trade** - approval will be retried on first trade attempt

```python
try:
    success = await client.set_allowance()
    if success:
        await wallet_repo.update(wallet.id, usdc_approved=True)
except Exception as e:
    logger.error(f"Error setting up trading approvals: {e}")
    # Don't fail the deposit notification
```

### Fallback: First Trade Approval

If automatic approval fails, the bot will try again on the first trade:

**File**: [services/trading_service.py](services/trading_service.py)

```python
async def place_order(self, user_id, ...):
    wallet = await self.wallet_repo.get_by_user_id(user_id)

    # Check if approvals needed
    if not wallet.usdc_approved:
        # Retry approval
        client = await self._get_clob_client(user_id)
        await client.set_allowance()
        await self.wallet_repo.update(wallet.id, usdc_approved=True)

    # Place order
    result = await client.place_market_order(...)
```

---

## Security Considerations

### 1. Unlimited Approval

**Question**: Is unlimited approval safe?

**Answer**: Yes, for these reasons:
- Standard practice for DEXs (Uniswap, 1inch, etc.)
- User retains custody of funds
- Exchange can only transfer when user signs order
- User can revoke approval anytime via blockchain

### 2. Private Key Handling

- Private key **never** leaves the server
- Decrypted only in memory for signing
- Encrypted at rest with Fernet (AES-128)
- Unique salt per wallet

### 3. Relayer Trust

- Relayer operated by Polymarket
- Cannot access user funds
- Can only submit pre-signed messages
- User signature required for all actions

---

## Monitoring & Debugging

### Check Approval Status

**Via Database**:
```sql
SELECT
    u.telegram_id,
    w.address,
    w.usdc_approved,
    w.usdc_balance,
    w.created_at
FROM wallets w
JOIN users u ON u.id = w.user_id
ORDER BY w.created_at DESC;
```

**Via Script**:
```bash
python scripts/check_wallet_approvals.py <wallet_address>
```

### Logs

**Successful Approval**:
```
[INFO] Setting up trading approvals for wallet 0x5b56B38...
[INFO] ✅ Trading approvals set for wallet 0x5b56B38...
```

**Failed Approval**:
```
[ERROR] Failed to set trading approvals for 0x5b56B38...
[ERROR] Error setting up trading approvals: <error details>
```

### Reset Approval (for testing)

```bash
python scripts/reset_wallet_approvals.py <wallet_address>
```

This sets `usdc_approved = FALSE` to trigger re-approval on next deposit/trade.

---

## Testing

### Test Automatic Approval

1. **Create new test user** via bot (`/start`)
2. **Send USDC** to user's wallet address
3. **Check logs** for approval messages:
   ```
   [INFO] Setting up trading approvals for wallet...
   [INFO] ✅ Trading approvals set for wallet...
   ```
4. **Check database**:
   ```sql
   SELECT usdc_approved FROM wallets WHERE address = '0x...';
   -- Should return: TRUE
   ```
5. **Place test trade** - should work immediately

### Test Failed Approval Handling

1. **Disconnect from network** temporarily
2. **Send deposit** - approval will fail
3. **Verify** deposit notification still sent
4. **Reconnect network**
5. **Place trade** - should trigger fallback approval

---

## Alternative: Manual Approval UI

If you want to give users manual control:

**Add button in wallet settings**:
```python
keyboard = [
    [InlineKeyboardButton("🔐 Approve USDC for Trading", callback_data="wallet_approve_usdc")],
]
```

**Handler**:
```python
async def approve_usdc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wallet = await get_user_wallet(user_id)

    if wallet.usdc_approved:
        await query.edit_message_text("✅ USDC already approved")
        return

    # Set approval
    client = await trading_service._get_clob_client(user_id)
    success = await client.set_allowance()

    if success:
        await wallet_repo.update(wallet.id, usdc_approved=True)
        await query.edit_message_text("✅ USDC approved for trading!")
    else:
        await query.edit_message_text("❌ Failed to approve USDC. Try again.")
```

---

## Related Files

| File | Purpose |
|------|---------|
| [core/webhook/alchemy_webhook.py:269](core/webhook/alchemy_webhook.py#L269) | Auto-approval on deposit |
| [core/polymarket/clob_client.py:436](core/polymarket/clob_client.py#L436) | `set_allowance()` method |
| [services/trading_service.py](services/trading_service.py) | CLOB client initialization |
| [database/repositories/wallet_repo.py](database/repositories/wallet_repo.py) | `usdc_approved` field |
| [scripts/check_wallet_approvals.py](scripts/check_wallet_approvals.py) | Check approval status |
| [scripts/reset_wallet_approvals.py](scripts/reset_wallet_approvals.py) | Reset for testing |

---

## Summary

✅ **Automatic** - No user action required
✅ **Instant** - Happens on first deposit
✅ **Gasless** - Uses Polymarket's relayer
✅ **Secure** - Private key stays encrypted
✅ **Reliable** - Falls back to first trade if needed
✅ **Monitored** - Tracked in database and logs

Users can now deposit and trade immediately without seeing "allowance not set" errors! 🚀
