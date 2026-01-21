# PolyBot Test Suite

Comprehensive test suite for PolyBot with organized structure for different test types.

## Directory Structure

```
tests/
├── integration/          # Real blockchain integration tests (costs money!)
│   ├── conftest.py      # Fixtures using REAL bot services
│   ├── test_real_deposits.py
│   ├── test_real_withdrawals.py
│   └── test_real_trading_flow.py
│
├── test_admin/          # Admin panel tests
│   └── test_broadcast_manual.py
│
├── test_core/           # Core functionality tests
│   ├── test_polymarket/ # Polymarket API tests
│   │   ├── test_gamma_client.py
│   │   ├── test_market_slug.py
│   │   ├── test_poly_credentials.py
│   │   └── test_poly_trading_readonly.py
│   │
│   ├── test_wallet/     # Wallet generation & encryption tests
│   │   ├── test_encryption.py
│   │   └── test_generator.py
│   │
│   ├── test_websocket/  # WebSocket tests
│   │   ├── test_integration.py
│   │   ├── test_manager.py
│   │   └── test_price_subscriber.py
│   │
│   └── test_webhook/    # Webhook tests (deposit detection)
│       └── test_alchemy_webhook.py
│
├── test_database/       # Database tests
│   ├── test_connection.py
│   ├── test_models/     # Data model tests
│   │   ├── test_order.py
│   │   └── test_user.py
│   │
│   └── test_repositories/  # Repository tests
│       ├── test_order_repo.py
│       ├── test_position_repo.py
│       ├── test_user_repo.py
│       └── test_wallet_repo.py
│
├── test_manual/         # Manual test scripts for production verification
│   ├── send_test_broadcast_manual.py
│   ├── test_2fa_flow_manual.py
│   └── test_real_broadcast_manual.py
│
├── test_services/       # Service layer tests
│   ├── test_2fa.py
│   ├── test_leaderboard_service.py
│   ├── test_referral_service.py
│   ├── test_trading_service.py
│   └── test_user_service.py
│
└── test_utils/          # Utility function tests
    ├── test_formatters.py
    ├── test_url_parser.py
    └── test_validators.py
```

## Test Categories

### 1. Integration Tests (`tests/integration/`)

**What**: Tests using REAL bot implementation with real blockchain
**Cost**: Real money (small amounts)
**Run**: `ENV_FILE=test.env pytest tests/integration/ -v`

Features:
- ✅ Real USDC transfers on Polygon
- ✅ Real Polymarket trades
- ✅ Real database operations
- ❌ NO MOCKS - everything is real!

See: [integration/README.md](integration/README.md)

### 2. Unit Tests (`tests/test_*`)

**What**: Isolated tests for specific components
**Cost**: Free
**Run**: `pytest tests/test_core/ tests/test_database/ tests/test_services/ tests/test_utils/ -v`

Features:
- ✅ Fast execution
- ✅ No external dependencies
- ✅ Mock external services where needed
- ✅ High coverage

### 3. Manual Tests (`tests/test_manual/`)

**What**: Scripts for manual testing and production verification
**Cost**: Varies
**Run**: Execute scripts directly with `python3 tests/test_manual/script_name.py`

Use cases:
- Production smoke tests
- Manual feature verification
- Real bot testing before deployment

## Running Tests

### Quick Start

```bash
# All unit tests (fast, free)
pytest -v

# Integration tests only (slow, costs money!)
ENV_FILE=test.env pytest tests/integration/ -v

# Specific test file
pytest tests/test_core/test_wallet/test_encryption.py -v

# Specific test function
pytest tests/test_services/test_user_service.py::test_register_user -v
```

### By Category

```bash
# Core functionality
pytest tests/test_core/ -v

# Database layer
pytest tests/test_database/ -v

# Service layer
pytest tests/test_services/ -v

# Utilities
pytest tests/test_utils/ -v

# Integration (requires test.env configuration)
ENV_FILE=test.env pytest tests/integration/ -v
```

### With Coverage

```bash
# Run tests with coverage report
pytest --cov=. --cov-report=html --cov-report=term -v

# Open coverage report
open htmlcov/index.html
```

### Test Markers

```bash
# Skip expensive tests
pytest -m "not expensive" -v

# Only integration tests
pytest -m integration -v

# Only expensive tests (be careful!)
pytest -m expensive -v
```

## Configuration

### For Unit Tests

No configuration needed - just run `pytest`

### For Integration Tests

1. Create `test.env`:
   ```bash
   cp .env.example test.env
   # Edit test.env with test credentials
   ```

2. Run setup wizard:
   ```bash
   python3 setup_test_env.py
   ```

3. Verify configuration:
   ```bash
   python3 setup_test_env.py --check
   ```

See: [../TESTING.md](../TESTING.md) for full setup guide

## Best Practices

### Writing Tests

1. **Name tests clearly**: `test_<action>_<expected_result>`
2. **One assertion per test**: Keep tests focused
3. **Use fixtures**: Reuse setup code via conftest.py
4. **Document costs**: Add docstring with cost estimate for paid tests
5. **Clean up**: Withdraw funds, close connections

### Test Organization

- **Unit tests**: Test one component in isolation
- **Integration tests**: Test multiple components together with real dependencies
- **Manual tests**: For production verification and smoke testing

### Running Before Commit

```bash
# Quick sanity check (fast tests only)
pytest tests/test_core/ tests/test_database/ tests/test_services/ -v

# Full test suite (including integration - costs money!)
ENV_FILE=test.env pytest -v
```

## Continuous Integration

The test suite is designed to run in CI/CD:

- **Unit tests**: Run on every PR (fast, free)
- **Integration tests**: Run manually or on release branches (requires secrets)

## Troubleshooting

### "ModuleNotFoundError"
Add project root to Python path:
```bash
export PYTHONPATH=$PWD:$PYTHONPATH
pytest -v
```

### "Database is locked"
Close any running bot instances:
```bash
pkill -f "python run.py"
pytest -v
```

### "Cannot connect to Polygon RPC"
Check your `test.env` configuration:
```bash
python3 setup_test_env.py --check
```

### "Insufficient funds"
For integration tests, ensure your funding wallet has:
- ~$50-100 USDC on Polygon
- ~0.5 POL for gas

## Contributing

When adding new tests:

1. ✅ Place in correct directory based on what you're testing
2. ✅ Use existing fixtures from conftest.py
3. ✅ Add docstrings explaining what the test does
4. ✅ Mark expensive tests with `@pytest.mark.expensive`
5. ✅ Ensure tests pass before committing

## Support

- Quick start: [../TESTING.md](../TESTING.md)
- Integration tests: [integration/README.md](integration/README.md)
- Bot architecture: [../CLAUDE.md](../CLAUDE.md)

---

**Happy Testing! 🧪**
