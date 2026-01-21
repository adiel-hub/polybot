# PolyBot Project Structure

Complete overview of the PolyBot project organization.

## 📁 Directory Structure

```
polybot/
│
├── 📄 README.md                      # Project overview & getting started
├── 📄 CLAUDE.md                      # AI coding assistant guidelines
├── 🔧 run.py                         # Main entry point
├── 🔧 setup_test_env.py              # Test environment setup wizard
├── 🔧 run_integration_tests.sh       # Interactive test runner
│
├── 📚 docs/                          # All documentation
│   ├── README.md                     # Documentation index
│   ├── TESTING.md                    # Integration test setup guide
│   ├── 2FA_VERIFICATION_REPORT.md   # 2FA implementation report
│   ├── BROADCAST_SYSTEM_SUMMARY.md  # Broadcast feature overview
│   ├── BROADCAST_VERIFICATION.md    # Broadcast testing results
│   └── BROADCAST_PREVIEW_DEMO.md    # Broadcast UI examples
│
├── 🤖 bot/                           # Telegram bot layer
│   ├── handlers/                     # Feature handlers
│   │   ├── start.py                 # Registration & license
│   │   ├── menu.py                  # Main menu
│   │   ├── wallet.py                # Deposits & withdrawals
│   │   ├── trading.py               # Order placement
│   │   ├── markets.py               # Market browsing
│   │   ├── portfolio.py             # Positions & P&L
│   │   ├── settings.py              # User settings & 2FA
│   │   ├── referrals.py             # Referral system
│   │   ├── leaderboard.py           # Trading leaderboard
│   │   └── copy_trading.py          # Copy trading discovery
│   │
│   ├── conversations/
│   │   └── states.py                # ConversationHandler states
│   │
│   └── application.py               # Bot factory & wiring
│
├── 🔧 services/                      # Business logic layer
│   ├── user_service.py              # User management
│   ├── trading_service.py           # Trading operations
│   ├── market_service.py            # Market data
│   ├── referral_service.py          # Referral tracking
│   └── leaderboard_service.py       # Leaderboard calculations
│
├── ⚙️ core/                          # External integrations
│   ├── polymarket/
│   │   ├── clob_client.py           # Trading API wrapper
│   │   └── gamma_client.py          # Market data API
│   │
│   ├── blockchain/
│   │   ├── deposit_monitor.py       # Deposit detection (polling)
│   │   └── withdrawals.py           # Withdrawal execution
│   │
│   ├── wallet/
│   │   ├── generator.py             # Wallet creation
│   │   └── encryption.py            # Key encryption
│   │
│   ├── websocket/
│   │   ├── manager.py               # Connection manager
│   │   ├── price_subscriber.py      # Price feeds
│   │   ├── copy_trade_subscriber.py # Copy trading
│   │   └── setup.py                 # WebSocket initialization
│   │
│   ├── webhook/
│   │   ├── alchemy_webhook.py       # Deposit detection (Webhooks)
│   │   └── alchemy_manager.py       # Webhook address management
│   │
│   └── security/
│       └── two_factor.py            # 2FA implementation
│
├── 💾 database/                      # Data persistence layer
│   ├── models/                       # Data models
│   │   ├── user.py
│   │   ├── wallet.py
│   │   ├── order.py
│   │   ├── position.py
│   │   ├── stop_loss.py
│   │   └── [other models]
│   │
│   ├── repositories/                 # CRUD operations
│   │   ├── user_repo.py
│   │   ├── wallet_repo.py
│   │   ├── order_repo.py
│   │   ├── position_repo.py
│   │   └── [other repos]
│   │
│   └── connection.py                 # Database initialization
│
├── 👑 admin/                         # Admin panel
│   ├── handlers/
│   │   ├── admin_menu.py            # Admin menu UI
│   │   ├── broadcast.py             # Broadcast feature
│   │   ├── analytics.py             # Analytics dashboard
│   │   └── revenue.py               # Revenue tracking
│   │
│   └── services/
│       ├── broadcast_service.py     # Broadcast logic
│       ├── analytics_service.py     # Analytics calculations
│       └── revenue_service.py       # Revenue management
│
├── 🛠️ utils/                         # Utility functions
│   ├── formatters.py                # Number/text formatting
│   ├── validators.py                # Input validation
│   └── url_parser.py                # Polymarket URL parsing
│
├── ⚙️ config/                        # Configuration
│   ├── settings.py                  # Settings schema (Pydantic)
│   └── constants.py                 # App constants
│
└── 🧪 tests/                         # Complete test suite
    ├── README.md                     # Test suite overview
    │
    ├── integration/                  # Real blockchain tests
    │   ├── README.md                # Integration test guide
    │   ├── conftest.py              # Real service fixtures
    │   ├── test_real_deposits.py    # Deposit detection
    │   ├── test_real_withdrawals.py # Withdrawal execution
    │   └── test_real_trading_flow.py # Full trading cycle
    │
    ├── test_core/                    # Core functionality tests
    │   ├── test_polymarket/         # Polymarket integration
    │   ├── test_wallet/             # Wallet generation
    │   └── test_websocket/          # WebSocket connections
    │
    ├── test_database/                # Database layer tests
    │   ├── test_models/
    │   └── test_repositories/
    │
    ├── test_services/                # Service layer tests
    │   ├── test_user_service.py
    │   ├── test_trading_service.py
    │   ├── test_2fa.py
    │   └── [other service tests]
    │
    ├── test_admin/                   # Admin panel tests
    │   └── test_broadcast_manual.py
    │
    ├── test_manual/                  # Manual test scripts
    │   ├── test_2fa_flow_manual.py
    │   └── test_real_broadcast_manual.py
    │
    ├── test_utils/                   # Utility tests
    │   ├── test_formatters.py
    │   ├── test_validators.py
    │   └── test_url_parser.py
    │
    └── conftest.py                   # Shared fixtures
```

## 🎯 Key Files

### Entry Points
- **`run.py`** - Start the bot
- **`setup_test_env.py`** - Configure test environment
- **`run_integration_tests.sh`** - Run integration tests

### Documentation
- **`README.md`** - Project overview
- **`CLAUDE.md`** - AI coding guidelines
- **`docs/`** - All feature documentation
- **`tests/README.md`** - Test suite guide

### Configuration
- **`.env.example`** - Environment template
- **`test.env`** - Test environment config
- **`config/settings.py`** - Settings schema
- **`pytest.ini`** - Test configuration

## 📊 Statistics

- **Total Handlers**: 10+ feature handlers
- **Services**: 5+ business logic services
- **Database Models**: 10+ data models
- **Test Files**: 40+ test files
- **Integration Tests**: 3 real blockchain test files
- **Documentation**: 6 comprehensive guides

## 🔗 Quick Navigation

| Need | Go To |
|------|-------|
| Get Started | [README.md](README.md) |
| Architecture | [CLAUDE.md](CLAUDE.md) |
| All Documentation | [docs/README.md](docs/README.md) |
| Testing Guide | [docs/TESTING.md](docs/TESTING.md) |
| Test Suite | [tests/README.md](tests/README.md) |
| Integration Tests | [tests/integration/README.md](tests/integration/README.md) |

## 🎨 Conventions

### File Organization
- One handler per feature
- One service per business domain
- One repository per model
- Tests mirror source structure

### Naming Conventions
- **Handlers**: `feature.py` (e.g., `trading.py`)
- **Services**: `feature_service.py` (e.g., `trading_service.py`)
- **Repositories**: `model_repo.py` (e.g., `user_repo.py`)
- **Models**: `model.py` (e.g., `user.py`)
- **Tests**: `test_feature.py` (e.g., `test_trading.py`)
- **Documentation**: `FEATURE_TYPE.md` (e.g., `TESTING.md`)

### Code Structure
- **Handlers** → UI/interaction logic
- **Services** → Business logic
- **Repositories** → Data access
- **Core** → External integrations
- **Utils** → Shared utilities

## 🚀 Development Workflow

1. **Setup**: `pip install -r requirements.txt`
2. **Configure**: Copy `.env.example` to `.env`
3. **Run**: `python run.py`
4. **Test**: `pytest`
5. **Commit**: `git commit -m "feat: description"`
6. **Push**: `git push`

## 📦 Dependencies

- **python-telegram-bot** v21 - Telegram bot framework
- **py-clob-client** - Polymarket trading
- **web3** v7 - Blockchain interactions
- **aiosqlite** - Async SQLite
- **cryptography** - Key encryption
- **pytest** - Testing framework

## 🔐 Security

- Private keys encrypted with Fernet
- 2FA support with TOTP
- Environment variables for secrets
- Separate test environment
- No credentials in code

---

**Last Updated**: 2026-01-14
