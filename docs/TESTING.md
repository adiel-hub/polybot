# Integration Testing Quick Start Guide

This guide will help you set up and run integration tests for PolyBot with real Polygon blockchain interactions.

## 🎯 What You Need From Me

To run the integration tests, I need you to provide the following in `test.env`:

### Required (for manual testing via Telegram):

1. **Encryption Key** - Run this command to generate:
   ```bash
   python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
   Copy the output to `test.env` as `MASTER_ENCRYPTION_KEY`

2. **Polygon RPC URL**:
   - Sign up at https://www.alchemy.com/ (free)
   - Create Polygon Mainnet app
   - Update `POLYGON_RPC_URL` with: `https://polygon-mainnet.g.alchemy.com/v2/YOUR_API_KEY`
   - Optionally configure Alchemy webhooks for deposit detection (see .env.example)

3. **Test Telegram Bot Token**:
   - Message @BotFather on Telegram
   - Send `/newbot` and follow prompts
   - Copy token to `test.env` as `TELEGRAM_BOT_TOKEN`
   - **Important**: Use a separate test bot, NOT your production bot!

4. **Your Telegram ID**:
   - Message @userinfobot on Telegram
   - Copy your ID to `test.env` as `ADMIN_TELEGRAM_IDS`

### Optional (for automated tests):

5. **Your Wallet Private Key & Address**:
   - Export private key from MetaMask/wallet
   - Add to `test.env` as `TEST_FUNDING_WALLET_PRIVATE_KEY`
   - Add your address as `TEST_FUNDING_WALLET_ADDRESS`
   - ⚠️ **Use a dedicated test wallet with small amounts, not your main wallet!**

6. **Fund Your Test Wallet**:
   - ~$50-100 USDC on Polygon
   - ~0.5 POL for gas fees

## 🚀 Quick Start (3 Steps)

### Step 1: Configure Environment

```bash
# Run setup wizard
python3 setup_test_env.py

# It will show you what to configure and generate an encryption key

# Edit test.env with the required values
vim test.env

# Check configuration
python3 setup_test_env.py --check
```

### Step 2: Start Test Bot

```bash
# Activate virtual environment
source .venv/bin/activate

# Run bot with test environment
ENV_FILE=test.env python run.py
```

### Step 3: Test via Telegram

1. Message your test bot: `/start`
2. Save the wallet address shown
3. Send USDC and POL to that address from your personal wallet
4. Test all features through Telegram:
   - 💰 Deposit (check balance updates)
   - 📈 Trade (buy/sell on markets)
   - 📊 Portfolio (view positions)
   - 💸 Withdraw (send back to your wallet)

## 🧪 Running Automated Tests (Optional)

Once `test.env` is fully configured with your funding wallet:

### Easy Way (Interactive):

```bash
./run_integration_tests.sh
```

Select from menu:
1. Free tests (no money spent)
2. Expensive tests (costs real money - will ask for confirmation)
3. Specific test file
4. List all tests

### Manual Way:

```bash
# Activate virtual environment
source .venv/bin/activate

# Run free tests only (no money spent)
ENV_FILE=test.env pytest tests/integration/ -v -m "not expensive"

# Run expensive tests (costs real money!)
ENV_FILE=test.env pytest tests/integration/ -v -m expensive -s

# Run specific test file
ENV_FILE=test.env pytest tests/integration/test_real_deposits.py -v -s

# Run specific test
ENV_FILE=test.env pytest tests/integration/test_real_deposits.py::test_verify_polygonscan_api -v -s
```

## 📊 Test Files Overview

| File | What It Tests | Cost | Can Run Without Funding Wallet? |
|------|---------------|------|----------------------------------|
| `test_real_deposits.py` | USDC deposit detection | ~$1-10 + gas | ❌ Needs funding wallet |
| `test_real_withdrawals.py` | USDC withdrawal execution | Gas only | ❌ Needs funding wallet |
| `test_real_trading_flow.py` | Full trading cycle | ~$10-20 + gas | ❌ Needs funding wallet |

## ✅ What I Need From You (Summary)

**To start testing right now:**

1. **Generate and give me these values for test.env:**
   ```bash
   # Run this command:
   python3 setup_test_env.py

   # It will show you:
   # - Generated encryption key
   # - Where to get Alchemy API key
   # - How to create test bot
   # - How to get your Telegram ID
   ```

2. **Create test bot** via @BotFather

3. **Get free Alchemy API key** from alchemy.com

That's it for manual testing! The bot will generate wallets automatically.

**For automated tests (optional):**

4. **Provide your wallet private key** (dedicated test wallet only!)
5. **Fund that wallet** with ~$50 USDC + 0.5 POL on Polygon

## 🔒 Security Notes

- ✅ `test.env` is in `.gitignore` (won't be committed)
- ✅ Use separate test bot (not production)
- ✅ Use separate database (`test_polybot.db`)
- ✅ Use dedicated test wallet (not your main wallet)
- ✅ Start with small amounts
- ⚠️ **NEVER** commit `test.env` to git
- ⚠️ **NEVER** share your private keys

## 📖 Detailed Documentation

For complete documentation, see:
- [tests/integration/README.md](tests/integration/README.md) - Full integration testing guide
- [Plan file](.claude/plans/shimmering-popping-dongarra.md) - Complete implementation plan

## 🆘 Need Help?

Run the setup wizard:
```bash
python3 setup_test_env.py
```

Check your configuration:
```bash
python3 setup_test_env.py --check
```

Generate just the encryption key:
```bash
python3 setup_test_env.py --key
```

## 🎉 You're Ready!

Once you've completed Step 1 (configure test.env), just let me know and I can:
- ✅ Verify your configuration
- ✅ Help you run the bot
- ✅ Guide you through testing
- ✅ Run automated tests (if you've set up funding wallet)

Just say "configuration done" and I'll verify everything is ready!
