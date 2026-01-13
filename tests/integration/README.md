# Integration Tests - Real Blockchain Interactions

This directory contains integration tests that use **REAL bot implementations** and interact with:
- ✅ Real Polygon blockchain
- ✅ Real Polymarket CLOB API
- ✅ Real Alchemy WebSocket
- ✅ Real USDC transfers
- ✅ Real database operations

**IMPORTANT**: These tests cost real money (small amounts) and should be run carefully!

## Philosophy: NO MOCKS!

All tests use the actual bot implementation:
- Import real services: `UserService`, `TradingService`, `WithdrawalManager`
- Use real repositories: `WalletRepository`, `OrderRepository`, `PositionRepository`
- Execute real blockchain transactions via `web3`
- Connect to real Polymarket APIs
- Use real WebSocket connections

**We do NOT use:**
- ❌ Mock CLOB clients
- ❌ Mock blockchain responses
- ❌ Fake wallet addresses
- ❌ Mock WebSocket connections
- ❌ Hardcoded test data

## Test Files

| File | Purpose | Cost | Tests |
|------|---------|------|-------|
| `test_real_trading_flow.py` | Full trading cycle | ~$10-20 + gas | Market orders, limit orders, P&L |
| `test_real_deposits.py` | USDC deposit detection | ~$1-10 + gas | Deposit tracking, on-chain verification |
| `test_real_withdrawals.py` | USDC withdrawal execution | Gas only | Withdrawals, error handling |

## Setup

### 1. Configure Test Environment

```bash
# Copy test environment template
cp .env.example test.env

# Edit test.env with your credentials
vim test.env
```

### 2. Required Configuration

**test.env must include:**

```env
# Test Bot (create separate bot via @BotFather)
TELEGRAM_BOT_TOKEN=your_test_bot_token

# Encryption (generate new key for tests)
MASTER_ENCRYPTION_KEY=<run_command_below>

# Polygon RPC (free tier is fine)
POLYGON_RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/your_key
ALCHEMY_API_KEY=your_alchemy_key

# Test Database (separate from production!)
DATABASE_PATH=./data/test_integration.db

# External Wallet (YOUR wallet for funding tests)
TEST_FUNDING_WALLET_PRIVATE_KEY=your_private_key
TEST_FUNDING_WALLET_ADDRESS=your_wallet_address

# Test Amounts
TEST_DEPOSIT_AMOUNT=10.0
TEST_TRADE_AMOUNT=5.0
TEST_WITHDRAWAL_AMOUNT=3.0
```

**Generate encryption key:**
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Get Alchemy API key:**
1. Sign up at https://www.alchemy.com/
2. Create a Polygon app
3. Copy API key

### 3. Fund External Wallet

Your external wallet (TEST_FUNDING_WALLET) must have:
- **USDC**: ~$50-100 on Polygon (for test deposits)
- **POL**: ~0.5 POL (for gas fees)

**How to get funds:**
- Bridge USDC to Polygon using [Polygon Bridge](https://portal.polygon.technology/)
- Buy POL on an exchange and withdraw to Polygon
- Or use a faucet for testnet POL (if using Mumbai testnet)

## Running Tests

### Run All Tests (WARNING: Expensive!)

```bash
# Load test environment and run all integration tests
ENV_FILE=test.env pytest tests/integration/ -v
```

### Run Specific Test File

```bash
# Just deposits
ENV_FILE=test.env pytest tests/integration/test_real_deposits.py -v

# Just withdrawals
ENV_FILE=test.env pytest tests/integration/test_real_withdrawals.py -v

# Just trading
ENV_FILE=test.env pytest tests/integration/test_real_trading_flow.py -v
```

### Run Specific Test

```bash
ENV_FILE=test.env pytest tests/integration/test_real_trading_flow.py::test_full_trading_cycle -v -s
```

### Skip Expensive Tests

```bash
# Run only free/cheap tests
ENV_FILE=test.env pytest tests/integration/ -v -m "not expensive"
```

### Run With Detailed Logging

```bash
ENV_FILE=test.env pytest tests/integration/ -v -s --log-cli-level=INFO
```

## Test Markers

Tests are marked for easy filtering:

- `@pytest.mark.integration` - All integration tests (auto-added)
- `@pytest.mark.expensive` - Tests that cost real money
- `@pytest.mark.slow` - Tests that take >30 seconds

**Examples:**
```bash
# Only integration tests
pytest -m integration

# Skip expensive tests
pytest -m "not expensive"

# Only expensive tests (be careful!)
pytest -m expensive
```

## Cost Estimates

| Test | USDC Cost | POL Cost | Total USD |
|------|-----------|----------|-----------|
| `test_real_usdc_deposit_detection` | $1 | $0.01 | ~$1.01 |
| `test_real_usdc_withdrawal` | $0 (returns) | $0.02 | ~$0.02 |
| `test_full_trading_cycle` | ~$10 | $0.05 | ~$10.05 |
| `test_place_and_cancel_limit_order` | $0 | $0.01 | ~$0.01 |
| **Full Test Suite** | **~$15-25** | **~$0.10** | **~$15-25** |

**Notes:**
- USDC costs are approximate (depends on Polymarket spreads)
- POL costs depend on network congestion
- Most USDC is recovered (withdrawn back to your wallet)
- Limit order tests don't fill, so minimal cost

## Verification

### Check Transactions on Polygonscan

Every test prints transaction hashes. Verify them on:
```
https://polygonscan.com/tx/<tx_hash>
```

### Monitor Test Wallets

Track USDC balance of generated test wallets:
```
https://polygonscan.com/address/<wallet_address>
```

### Check Database

Inspect test database:
```bash
sqlite3 ./data/test_integration.db

sqlite> SELECT * FROM wallets;
sqlite> SELECT * FROM orders;
sqlite> SELECT * FROM positions;
```

## Safety Features

### Pre-Execution Checks

Tests automatically verify:
- ✅ Required environment variables are set
- ✅ External wallet has sufficient USDC
- ✅ External wallet has POL for gas
- ✅ Polygon RPC connection works
- ✅ Test amounts are within safe limits

### Cost Warnings

Before running expensive tests:
```
⚠️  WARNING: You are about to run tests that cost REAL MONEY!
Expensive tests: 3
Estimated cost: ~$60 + gas fees
To skip expensive tests, run: pytest -m 'not expensive'
```

### Automatic Cleanup

Tests clean up after themselves:
- Withdraw remaining USDC back to external wallet
- Close all positions
- Delete test database entries
- Close WebSocket connections

## Troubleshooting

### "Cannot connect to Polygon RPC"

**Solution:**
- Check `POLYGON_RPC_URL` in test.env
- Verify Alchemy API key is valid
- Try alternative RPC: `https://polygon-rpc.com`

### "External wallet has no USDC"

**Solution:**
- Fund `TEST_FUNDING_WALLET_ADDRESS` with USDC on Polygon
- Use bridge: https://portal.polygon.technology/
- Minimum recommended: $50 USDC

### "Insufficient funds for gas"

**Solution:**
- Send POL to `TEST_FUNDING_WALLET_ADDRESS`
- Minimum recommended: 0.5 POL

### "TEST_FUNDING_WALLET_PRIVATE_KEY not configured"

**Solution:**
- Add your wallet private key to test.env
- **NEVER commit private keys to git!**
- Use a dedicated test wallet, not your main wallet

### "Trade failed: Could not create API credentials"

**Solution:**
- Check Polymarket CLOB API is accessible
- Verify bot wallet has USDC for trading
- Check private key decryption worked

### "WebSocket connection failed"

**Solution:**
- Verify `ALCHEMY_API_KEY` is set
- Check Alchemy subscription tier (free tier has limits)
- Test WebSocket URL manually

## Best Practices

### Before Running Tests

1. **Review cost estimates** - Know what you're spending
2. **Check external wallet balance** - Ensure sufficient funds
3. **Run specific tests first** - Don't run full suite blindly
4. **Use separate test bot** - Never test with production bot
5. **Backup test.env** - Don't lose configuration

### During Test Development

1. **Start with cheap tests** - Test basic functionality first
2. **Add cost estimates** - Document in test docstrings
3. **Verify on blockchain** - Check every transaction on Polygonscan
4. **Add cleanup code** - Withdraw funds at end of test
5. **Use assertions liberally** - Catch errors early

### After Tests Complete

1. **Review Polygonscan** - Verify all transactions succeeded
2. **Check final balances** - Ensure funds recovered
3. **Review logs** - Look for unexpected behavior
4. **Update documentation** - Document any issues found
5. **Clean up test data** - Delete test database if needed

## Example: Full Test Run

```bash
# 1. Activate virtual environment
source .venv/bin/activate

# 2. Verify external wallet has funds
python -c "
from web3 import Web3
from dotenv import load_dotenv
import os
load_dotenv('test.env')
w3 = Web3(Web3.HTTPProvider(os.getenv('POLYGON_RPC_URL')))
addr = os.getenv('TEST_FUNDING_WALLET_ADDRESS')
usdc = w3.eth.contract(address='0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359', abi=[{'constant':True,'inputs':[{'name':'_owner','type':'address'}],'name':'balanceOf','outputs':[{'name':'','type':'uint256'}],'type':'function'}])
balance = usdc.functions.balanceOf(addr).call() / 1e6
pol = w3.from_wei(w3.eth.get_balance(addr), 'ether')
print(f'USDC: \${balance:.2f}')
print(f'POL: {pol:.4f}')
"

# 3. Run free tests first
ENV_FILE=test.env pytest tests/integration/ -v -m "not expensive"

# 4. Review output and verify

# 5. Run expensive tests (one at a time)
ENV_FILE=test.env pytest tests/integration/test_real_deposits.py::test_real_usdc_deposit_detection -v -s

# 6. Check Polygonscan for transaction

# 7. If all good, run full suite
ENV_FILE=test.env pytest tests/integration/ -v
```

## Contributing

When adding new integration tests:

1. **Use real services only** - No mocks!
2. **Add cost estimates** - In docstring and README
3. **Include cleanup code** - Withdraw funds at end
4. **Add appropriate markers** - `@pytest.mark.expensive` if costs money
5. **Document clearly** - Explain what the test does
6. **Test before committing** - Run at least once successfully
7. **Update README** - Add to test files table

## Support

If you encounter issues:

1. Check this README first
2. Review test output and error messages
3. Verify transactions on Polygonscan
4. Check [CLAUDE.md](../../CLAUDE.md) for bot architecture
5. Create an issue with:
   - Test command you ran
   - Full error output
   - Transaction hashes (if any)
   - Environment (OS, Python version, etc.)

## Security Notes

**⚠️ CRITICAL SECURITY WARNINGS:**

1. **Never commit private keys** - test.env is in .gitignore
2. **Use dedicated test wallet** - Not your main wallet
3. **Limit funds** - Only keep what's needed for testing
4. **Secure test.env** - Set file permissions: `chmod 600 test.env`
5. **Monitor transactions** - Watch for unexpected activity
6. **Revoke after testing** - Consider rotating keys after major tests
7. **Separate databases** - Never point tests at production DB

## License

These tests are part of PolyBot and follow the same license as the main project.

---

**Happy Testing! 🧪**

Remember: These tests cost real money - run them wisely!
