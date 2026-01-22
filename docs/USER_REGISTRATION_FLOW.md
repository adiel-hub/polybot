# User Registration & Wallet Creation Flow

## Overview

When a user interacts with PolyBot for the first time, they go through an automated registration and wallet creation process. This document explains the complete flow.

---

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    User Sends /start Command                     │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│              bot/handlers/start.py:start_command()               │
│                                                                   │
│  • Extracts deep link parameters (referral, market, trader)      │
│  • Checks if user already registered                             │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                ┌─────────┴─────────┐
                │                   │
                ▼                   ▼
        ┌───────────────┐   ┌──────────────┐
        │  Registered?  │   │ Not Registered│
        │     YES       │   │      NO       │
        └───────┬───────┘   └──────┬────────┘
                │                  │
                │                  ▼
                │      ┌─────────────────────────────┐
                │      │  Show License Agreement     │
                │      │  (LICENSE_TEXT constant)    │
                │      │                             │
                │      │  [✅ Accept] [❌ Decline]   │
                │      └───────────┬─────────────────┘
                │                  │
                │                  ▼
                │      ┌─────────────────────────────┐
                │      │ User Clicks "Accept"        │
                │      │                             │
                │      │ license_accept() triggered  │
                │      └───────────┬─────────────────┘
                │                  │
                │                  ▼
                │      ┌─────────────────────────────────────────┐
                │      │  "🔐 Creating your secure wallet..."    │
                │      │           ⏳ Please wait.               │
                │      └───────────┬─────────────────────────────┘
                │                  │
                │                  ▼
                │      ┌──────────────────────────────────────────────┐
                │      │     services/user_service.py                  │
                │      │     register_user()                           │
                │      │                                               │
                │      │  STEP 1: Create User Record                  │
                │      │  ─────────────────────────────                │
                │      │  • user_repo.create()                        │
                │      │  • Stores: telegram_id, username, name       │
                │      │  • PostgreSQL: INSERT INTO users             │
                │      │                                               │
                │      │  STEP 2: Generate EOA Wallet                 │
                │      │  ─────────────────────────────                │
                │      │  • WalletGenerator.create_wallet()           │
                │      │  • Creates new Ethereum private key          │
                │      │  • Derives wallet address from key           │
                │      │                                               │
                │      │  STEP 3: Encrypt Private Key                 │
                │      │  ─────────────────────────────                │
                │      │  • encryption.encrypt(private_key)           │
                │      │  • Uses Fernet encryption (AES-128)          │
                │      │  • Master key: MASTER_ENCRYPTION_KEY         │
                │      │  • Generates unique salt per wallet          │
                │      │                                               │
                │      │  STEP 4: Store Wallet in Database            │
                │      │  ─────────────────────────────                │
                │      │  • wallet_repo.create()                      │
                │      │  • Stores: address, encrypted_key, salt     │
                │      │  • wallet_type: "EOA"                        │
                │      │  • PostgreSQL: INSERT INTO wallets           │
                │      │                                               │
                │      │  STEP 5: Accept License                      │
                │      │  ─────────────────────────────                │
                │      │  • user_repo.accept_license()                │
                │      │  • Sets license_accepted = TRUE              │
                │      │  • Records license_accepted_at timestamp     │
                │      │                                               │
                │      │  STEP 6: Register for Deposit Monitoring     │
                │      │  ─────────────────────────────                │
                │      │  • webhook_manager.add_addresses([address])  │
                │      │  • Registers wallet with Alchemy webhook    │
                │      │  • Enables automatic deposit detection      │
                │      │                                               │
                │      └───────────┬──────────────────────────────────┘
                │                  │
                │                  ▼
                │      ┌──────────────────────────────────────────────┐
                │      │  Generate Referral Code for New User        │
                │      │  • generate_referral_code_for_user()         │
                │      │  • Creates unique 8-char referral code       │
                │      └───────────┬──────────────────────────────────┘
                │                  │
                │                  ▼
                │      ┌──────────────────────────────────────────────┐
                │      │  Link Referral (if provided in /start)       │
                │      │  • referral_service.link_referral()          │
                │      │  • Credits referrer when new user trades     │
                │      └───────────┬──────────────────────────────────┘
                │                  │
                └──────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Show Welcome Message                            │
│                                                                   │
│  ✅ Your PolyBot wallet is ready!                                │
│                                                                   │
│  🔑 Your wallet address:                                         │
│  `0x1234...5678`                                                 │
│                                                                   │
│  🚀 Get started:                                                 │
│  💳 Fund your wallet                                             │
│  👥 Copy trade your favorite traders                             │
│  🎁 Invite your friends and earn referral rewards                │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Show Main Menu                                │
│                                                                   │
│  🏠 Main Menu                                                    │
│                                                                   │
│  [📈 Trade]  [💰 Wallet]  [📊 Portfolio]                        │
│  [⚙️ Settings]  [🎁 Referrals]                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Detailed Steps

### 1. User Sends `/start` Command

**File**: [bot/handlers/start.py:15](bot/handlers/start.py#L15) - `start_command()`

**Actions**:
- Extracts deep link parameters from command args
  - `ref_XXXXXXXX` → Referral code
  - `m_XXXXXXXX` → Market deep link
  - `ct_0x...` → Copy trader deep link
  - `e_XXXXXXXX` → Event deep link
- Checks if user already registered: `user_service.is_registered(user.id)`

**Branches**:
- **If registered**: Redirect to main menu (or specific market if deep link)
- **If not registered**: Show license agreement

---

### 2. License Agreement

**File**: [config/constants.py](config/constants.py) - `LICENSE_TEXT`

**UI**:
```
📜 PolyBot Terms & Conditions

[License text...]

[✅ Accept]  [❌ Decline]
```

**User Actions**:
- **Accept** → Triggers `license_accept()` → Proceeds with registration
- **Decline** → Shows "You must accept to use PolyBot"

---

### 3. Wallet Creation Process

**File**: [services/user_service.py:45](services/user_service.py#L45) - `register_user()`

#### Step 3.1: Create User Record
```python
user = await self.user_repo.create(
    telegram_id=telegram_id,
    telegram_username=telegram_username,
    first_name=first_name,
    last_name=last_name,
)
```

**Database**: PostgreSQL `users` table
```sql
INSERT INTO users (telegram_id, telegram_username, first_name, last_name)
VALUES ($1, $2, $3, $4)
RETURNING id;
```

#### Step 3.2: Generate EOA Wallet
```python
address, private_key = WalletGenerator.create_wallet()
```

**File**: [core/wallet/generator.py](core/wallet/generator.py)

**Process**:
1. Generate random 32-byte private key using `secrets.token_bytes(32)`
2. Derive public key using elliptic curve cryptography (secp256k1)
3. Compute Ethereum address from public key (Keccak-256 hash)
4. Format as checksummed address: `0x1234...5678`

#### Step 3.3: Encrypt Private Key
```python
encrypted_key, salt = self.encryption.encrypt(private_key)
```

**File**: [core/wallet/encryption.py](core/wallet/encryption.py)

**Process**:
1. Uses Fernet encryption (AES-128-CBC + HMAC)
2. Master key from environment: `MASTER_ENCRYPTION_KEY`
3. Generates unique salt per wallet (16 bytes)
4. Derives encryption key: `PBKDF2(master_key, salt, iterations=100000)`
5. Encrypts private key with derived key

**Security**:
- Private keys NEVER stored in plaintext
- Each wallet has unique encryption salt
- Master key rotation supported
- Encryption verified with HMAC for integrity

#### Step 3.4: Store Wallet
```python
wallet = await self.wallet_repo.create(
    user_id=user.id,
    address=address,
    eoa_address=address,
    wallet_type="EOA",
    encrypted_private_key=encrypted_key,
    encryption_salt=salt,
)
```

**Database**: PostgreSQL `wallets` table
```sql
INSERT INTO wallets (
    user_id, address, eoa_address, wallet_type,
    encrypted_private_key, encryption_salt,
    safe_deployed, usdc_approved
)
VALUES ($1, $2, $3, $4, $5, $6, FALSE, FALSE)
RETURNING *;
```

**Wallet Types**:
- **EOA** (Externally Owned Account): Standard Ethereum wallet
- **SAFE** (Gnosis Safe): Multi-sig smart contract wallet (future feature)

#### Step 3.5: Accept License
```python
await self.user_repo.accept_license(user.id)
```

**Database**:
```sql
UPDATE users
SET license_accepted = TRUE,
    license_accepted_at = NOW()
WHERE id = $1;
```

#### Step 3.6: Register for Deposit Monitoring
```python
if self._webhook_manager:
    asyncio.create_task(self._register_webhook_address(address))
```

**File**: [core/webhook/alchemy_manager.py](core/webhook/alchemy_manager.py)

**Process**:
1. Calls Alchemy Notify API
2. Adds wallet address to webhook's monitored addresses
3. Webhook URL: `https://polybot.onrender.com/webhook/alchemy`
4. Monitors USDC deposits on Polygon network

**Webhook Event**:
```json
{
  "type": "ADDRESS_ACTIVITY",
  "activity": [{
    "fromAddress": "0xUSER...",
    "toAddress": "0xBOT_WALLET...",
    "asset": "USDC",
    "value": 100.0
  }]
}
```

---

### 4. Post-Registration Setup

#### Generate Referral Code
```python
await user_service.generate_referral_code_for_user(new_user.id)
```

**Process**:
- Generates unique 8-character code
- Stores in `users.referral_code`
- Used for sharing: `https://t.me/PolyBot?start=ref_ABC12345`

#### Link Referral (if provided)
```python
if referral_code:
    await referral_service.link_referral(new_user.id, referral_code)
```

**Database**: PostgreSQL `users` table
```sql
UPDATE users
SET referred_by = (SELECT id FROM users WHERE referral_code = $1)
WHERE id = $2;
```

**Rewards**:
- Referrer earns 10% of referee's trading commissions
- Tracked in `referral_commissions` table
- Paid out when referee makes trades

---

### 5. Welcome Message & Main Menu

**UI**:
```
✅ Your PolyBot wallet is ready!

🔑 Your wallet address:
`0x5b56B3871cbcDad6282A5E6f181b3AD5F9758185`

🚀 Get started:
💳 Fund your wallet
👥 Copy trade your favorite traders
🎁 Invite your friends and earn referral rewards

📋 You can also:
📈 Place market and limit orders
📊 Manage your portfolio
🛡️ Protect your positions with Stop Loss orders
🤖 Set up automated strategies
⚙️ Tune your trading settings
```

**Main Menu Buttons**:
```
┌──────────┬──────────┬──────────┐
│ 📈 Trade │ 💰 Wallet│📊 Portfolio│
├──────────┴──────────┴──────────┤
│       ⚙️ Settings              │
├────────────────────────────────┤
│       🎁 Referrals             │
└────────────────────────────────┘
```

---

## Database Schema

### Users Table
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    telegram_username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    referral_code VARCHAR(8) UNIQUE,
    referred_by INTEGER REFERENCES users(id),
    license_accepted BOOLEAN DEFAULT FALSE,
    license_accepted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Wallets Table
```sql
CREATE TABLE wallets (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    address VARCHAR(42) UNIQUE NOT NULL,
    eoa_address VARCHAR(42),
    wallet_type VARCHAR(10) DEFAULT 'EOA',
    encrypted_private_key BYTEA NOT NULL,
    encryption_salt BYTEA NOT NULL,
    safe_deployed BOOLEAN DEFAULT FALSE,
    usdc_approved BOOLEAN DEFAULT FALSE,
    usdc_balance DECIMAL(20, 6) DEFAULT 0,
    api_key_encrypted BYTEA,
    api_secret_encrypted BYTEA,
    api_passphrase_encrypted BYTEA,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## Security Features

### 1. Private Key Encryption
- **Algorithm**: Fernet (AES-128-CBC + HMAC-SHA256)
- **Key Derivation**: PBKDF2 with 100,000 iterations
- **Unique Salt**: 16 bytes per wallet
- **Master Key**: Stored in environment variable (never in code)

### 2. Wallet Security
- Private keys never transmitted over network
- Encryption at rest in PostgreSQL
- Master key rotation supported
- Each wallet has unique encryption parameters

### 3. Deposit Detection
- Webhook-based (no polling)
- Signature verification with `ALCHEMY_WEBHOOK_SIGNING_KEY`
- Monitors only registered wallet addresses
- Automatic balance updates

---

## Key Files

| File | Purpose |
|------|---------|
| [bot/handlers/start.py](bot/handlers/start.py) | `/start` command, license flow |
| [services/user_service.py](services/user_service.py) | User & wallet creation |
| [core/wallet/generator.py](core/wallet/generator.py) | Ethereum wallet generation |
| [core/wallet/encryption.py](core/wallet/encryption.py) | Private key encryption |
| [database/repositories/user_repo.py](database/repositories/user_repo.py) | User CRUD operations |
| [database/repositories/wallet_repo.py](database/repositories/wallet_repo.py) | Wallet CRUD operations |
| [core/webhook/alchemy_manager.py](core/webhook/alchemy_manager.py) | Alchemy webhook management |
| [config/constants.py](config/constants.py) | LICENSE_TEXT constant |

---

## WebSocket Integration

After registration, the user's wallet is automatically added to:

1. **Deposit Monitoring** (Alchemy Webhook)
   - File: [core/webhook/alchemy_webhook.py](core/webhook/alchemy_webhook.py)
   - Monitors USDC transfers to user wallet
   - Updates balance in real-time

2. **Price Monitoring** (When user creates positions)
   - File: [core/websocket/price_subscriber.py](core/websocket/price_subscriber.py)
   - Monitors market prices for stop loss
   - Updates position values in real-time

3. **Order Monitoring** (When user places limit orders)
   - File: [core/websocket/order_fill_subscriber.py](core/websocket/order_fill_subscriber.py)
   - Monitors order fills
   - Collects trading commissions

---

## Next Steps After Registration

1. **Fund Wallet**
   - User clicks "💰 Wallet" → "💳 Deposit"
   - Shows wallet address + QR code
   - User sends USDC from external wallet
   - Alchemy webhook detects deposit
   - Balance updated automatically

2. **Place First Trade**
   - User clicks "📈 Trade"
   - Browses trending markets
   - Selects outcome (YES/NO)
   - Enters amount
   - Confirms order
   - Order executed via Polymarket CLOB API

3. **Invite Friends**
   - User clicks "🎁 Referrals"
   - Gets unique referral link
   - Shares with friends
   - Earns 10% of their trading commissions

---

## Error Handling

### Registration Failures

**Duplicate Telegram ID**:
```sql
ERROR: duplicate key value violates unique constraint "users_telegram_id_key"
```
**Solution**: User already registered, redirect to main menu

**Wallet Generation Failure**:
```python
except Exception as e:
    logger.error(f"Wallet generation failed: {e}")
    await query.edit_message_text("❌ Wallet creation failed. Try /start again")
```

**Database Connection Error**:
```python
except asyncpg.PostgresError as e:
    logger.error(f"Database error during registration: {e}")
    # Rollback handled by asyncpg
```

### Alchemy Webhook Registration Failure
- Non-blocking: Runs in background task
- User can still use bot
- Manual address sync available in admin panel
- Webhook will catch up on next sync

---

## Performance Considerations

1. **Parallel Operations**
   - License acceptance and referral code generation run concurrently
   - Webhook registration runs in background (non-blocking)

2. **Database Optimization**
   - Indexed telegram_id for fast lookup
   - Indexed wallet address for deposit detection
   - Connection pooling (min: 2, max: 10)

3. **WebSocket Efficiency**
   - Single WebSocket connection for all users
   - Multiplexed subscriptions
   - Auto-reconnect on disconnect

---

## Testing the Flow

### Manual Test
```bash
# 1. Open Telegram
# 2. Search for your bot: @YourPolyBot
# 3. Send: /start
# 4. Click "Accept"
# 5. Wait for wallet creation
# 6. Verify main menu appears
```

### With Referral Code
```bash
# Send: /start ref_ABC12345
# Verify: "Registered via referral code: ABC12345" in logs
```

### With Market Deep Link
```bash
# Send: /start m_12345678
# Verify: Market detail page shows after registration
```

---

## Summary

The user registration flow is **fully automated** and takes ~2-3 seconds:

1. User sends `/start`
2. Bot shows license agreement
3. User clicks "Accept"
4. Bot creates user record in PostgreSQL
5. Bot generates new Ethereum wallet
6. Bot encrypts private key with Fernet
7. Bot stores wallet in PostgreSQL
8. Bot registers address with Alchemy webhook
9. Bot generates referral code
10. Bot links referral (if provided)
11. Bot shows welcome message
12. Bot displays main menu

**Total Time**: ~2-3 seconds
**Database Queries**: 4-5 INSERTs + 1 UPDATE
**Network Calls**: 1 (Alchemy webhook registration - async)
**Security**: Private key encrypted at rest, never exposed

The user is now ready to trade on Polymarket! 🚀
