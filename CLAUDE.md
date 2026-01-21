# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Activate virtual environment (Python 3.12)
source .venv/bin/activate

# Run the bot
python run.py

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest

# Run single test
pytest tests/test_file.py::test_function

# Format code
black .

# Lint
ruff check .
```

## Architecture

PolyBot is a Telegram bot for trading on Polymarket prediction markets. It uses python-telegram-bot v21 with ConversationHandler for multi-step flows.

### Layer Structure

```
bot/                    → Telegram handlers and UI
  handlers/             → One file per feature (trading, wallet, settings, etc.)
  conversations/states.py → ConversationState enum for all flows
  application.py        → Bot factory, wires all handlers into ConversationHandler

services/               → Business logic layer
  user_service.py       → Registration, settings, wallet access
  trading_service.py    → Order placement via Polymarket CLOB
  market_service.py     → Market data via Gamma API

core/                   → External integrations
  polymarket/
    clob_client.py      → py-clob-client wrapper (trading)
    gamma_client.py     → Market data API client
  blockchain/
    deposit_monitor.py  → USDC transfer detection (web3)
    withdrawals.py      → USDC withdrawal execution
  wallet/
    generator.py        → eth-account wallet creation
    encryption.py       → Fernet encryption for private keys
  websocket/            → Real-time WebSocket subscriptions
    manager.py          → WebSocket connection manager with auto-reconnect
    price_subscriber.py → Polymarket price feeds (stop loss + position sync)
    copy_trade_subscriber.py → Polymarket user channel for copy trading
    setup.py            → WebSocket service initialization
  webhook/              → Alchemy webhooks for cost-effective deposit detection
    alchemy_webhook.py  → Webhook handler for deposit notifications
    alchemy_manager.py  → API client for managing webhook addresses

database/               → SQLite persistence
  models/               → Dataclasses (User, Wallet, Order, Position, etc.)
  repositories/         → CRUD operations per model
  connection.py         → aiosqlite connection + table initialization
```

### Key Patterns

**ConversationHandler Flow**: All user interactions go through a single ConversationHandler in `application.py`. Each state maps to specific CallbackQueryHandlers and MessageHandlers. Handlers return `ConversationState.X` to transition states.

**Callback Data Convention**: Button callbacks use prefixed patterns:
- `menu_*` → Main menu navigation
- `settings_*` → Settings page actions
- `trade_*` → Trading flow
- `wallet_*` → Wallet operations
- `browse_*` → Market browsing

**Services in bot_data**: Services are initialized in `create_application()` and stored in `context.bot_data`:
```python
user_service = context.bot_data["user_service"]
```

**Settings Storage**: User settings stored as JSON in `users.settings` column. Use `DEFAULT_SETTINGS` in `database/models/user.py` for schema. Access via `UserService.get_user_settings()` / `update_user_setting()`.

### APIs

- **Polymarket CLOB** (`clob.polymarket.com`): Trading via `py-clob-client`. Uses `MarketOrderArgs` for market orders, `OrderArgs` for limit orders. Side constants: `BUY`, `SELL` from `py_clob_client.order_builder.constants`.

- **Gamma API** (`gamma-api.polymarket.com`): Market data, no auth required. Response fields `outcomePrices` and `clobTokenIds` may be JSON strings - parse accordingly.

- **web3 v7**: Use `contract.events.Transfer.get_logs(from_block=X)` not `create_filter(fromBlock=X)`.

## UI Design

All bot UI elements must be professional, polished, and visually appealing:

- **Emojis required**: Every button, menu item, and message should include relevant emojis for visual clarity
- **Button text**: Use clear, action-oriented text with emojis (e.g., `📈 Trade`, `💰 Wallet`, `⚙️ Settings`, `🔙 Back`)
- **Message formatting**: Use proper spacing, line breaks, and emoji headers to organize information
- **Status indicators**: Use emojis to show states (✅ success, ❌ error, ⏳ pending, ⚠️ warning)
- **Financial data**: Format numbers with `💵` for amounts, `📊` for percentages, `📈📉` for gains/losses
- **Consistency**: Maintain consistent emoji usage across all handlers - same action = same emoji

### Emoji Reference
```
Navigation:  🏠 Home  🔙 Back  ❌ Close  ✅ Confirm  🔄 Refresh
Trading:     📈 Buy   📉 Sell  💹 Markets  📊 Portfolio  🎯 Positions
Wallet:      💰 Balance  💳 Deposit  💸 Withdraw  🔑 Address
Settings:    ⚙️ Settings  🔔 Notifications  🛡️ Security  👤 Profile
Status:      ✅ Success  ❌ Failed  ⏳ Pending  ⚠️ Warning  ℹ️ Info
```

## Git Workflow

**Always commit and push after any code change:**
- After completing any code modification, immediately create a git commit with a descriptive message
- Push commits to the remote repository right after committing
- Use conventional commit messages (e.g., `feat:`, `fix:`, `refactor:`, `style:`, `docs:`)
- Group related changes into a single commit when they belong together

## Code Style

- **File length**: Keep files under 300-400 lines. Split large files into smaller modules.
- **Comments**: Add explanatory comments for non-obvious logic. Every function should have a clear purpose.
- **Code reuse**: Extract shared logic into helper functions. Avoid duplication - if code appears twice, refactor it.
- **Organization**: Keep imports sorted, group related functions together, maintain clean module boundaries.

## Testing

- **No mock data**: Never use mock data in tests. Always test with real data or realistic test fixtures using the implemented methods and code
- **Test coverage**: Create tests for every new method or code addition. No code should be merged without corresponding tests.
- **Test location**: All tests must be in the `tests/` folder, mirroring the source structure:
  ```
  tests/
    test_services/
      test_user_service.py
      test_trading_service.py
    test_handlers/
      test_settings.py
    test_core/
      test_wallet.py
  ```
- **Run tests**: Always run `pytest` before committing to ensure nothing is broken.

## Documentation

All project documentation is organized in the `docs/` folder for easy maintenance and discovery.

### Documentation Structure

```
polybot/
├── README.md                    # Project overview (STAYS IN ROOT)
├── CLAUDE.md                    # AI assistant guide (STAYS IN ROOT - THIS FILE)
│
├── docs/                        # All feature & setup documentation
│   ├── README.md               # Documentation index
│   ├── TESTING.md              # Integration test setup guide
│   ├── 2FA_VERIFICATION_REPORT.md
│   ├── BROADCAST_SYSTEM_SUMMARY.md
│   └── [other feature docs]
│
└── tests/                       # Test documentation
    ├── README.md               # Test suite overview
    └── integration/
        └── README.md           # Integration test guide
```

### When to Create Documentation

**Create documentation in `docs/` for:**
- ✅ Feature implementation reports (e.g., `2FA_VERIFICATION_REPORT.md`)
- ✅ Setup and configuration guides (e.g., `TESTING.md`)
- ✅ System summaries and architecture docs (e.g., `BROADCAST_SYSTEM_SUMMARY.md`)
- ✅ Verification reports for completed features
- ✅ Integration guides for external APIs

**Keep in root directory:**
- ✅ `README.md` - Main project overview and getting started
- ✅ `CLAUDE.md` - This file, AI coding assistant guidelines

**Keep with tests:**
- ✅ `tests/README.md` - Test suite overview
- ✅ `tests/integration/README.md` - Specific test category guides

### Creating Documentation

When adding new documentation:

1. **Place in `docs/` folder**:
   ```bash
   # Create feature documentation
   touch docs/NEW_FEATURE_REPORT.md
   ```

2. **Use descriptive naming**:
   - ✅ `BROADCAST_SYSTEM_SUMMARY.md` (clear and specific)
   - ❌ `BROADCAST.md` (too vague)
   - ✅ `TESTING.md` (setup guide)
   - ✅ `2FA_VERIFICATION_REPORT.md` (verification report)

3. **Add to documentation index**:
   - Update `docs/README.md` with link to new doc
   - Categorize appropriately (Testing, Features, Guides, etc.)

4. **Format guidelines**:
   - Use markdown headers (`#`, `##`, `###`)
   - Include code blocks with syntax highlighting
   - Add table of contents for docs >200 lines
   - Use emojis for visual organization (📚 📖 ✅ ❌ ⚠️)
   - Link to related documentation

5. **Commit with docs prefix**:
   ```bash
   git add docs/NEW_FEATURE_REPORT.md
   git commit -m "docs: Add feature X implementation report"
   ```

### File Naming Convention

- Use `SCREAMING_SNAKE_CASE.md` for reports and guides
- Use `README.md` for directory indexes
- Be descriptive and specific in names
- Include document type in name (REPORT, GUIDE, SUMMARY, etc.)

### Documentation Best Practices

- **Keep it current**: Update docs when code changes
- **Link related docs**: Reference other relevant documentation
- **Include examples**: Show code examples and screenshots where helpful
- **Use clear structure**: Headers, lists, tables for easy scanning
- **No sensitive data**: Never include API keys, passwords, or private keys

### Finding Documentation

- **Quick reference**: See `docs/README.md` for full documentation index
- **Testing**: Start with `docs/TESTING.md` or `tests/README.md`
- **Features**: Check `docs/` for feature-specific reports
- **Architecture**: Refer to this file (CLAUDE.md) for system architecture

## Environment

Copy `.env.example` to `.env` and configure:
- `TELEGRAM_BOT_TOKEN` - From @BotFather
- `MASTER_ENCRYPTION_KEY` - Generate with `Fernet.generate_key()`
- `POLYGON_RPC_URL` - Polygon RPC endpoint
- `ALCHEMY_WEBHOOK_SIGNING_KEY` - For webhook signature verification
- `ALCHEMY_WEBHOOK_ID` - Webhook ID for address management
- `ALCHEMY_AUTH_TOKEN` - Auth token for Alchemy API
- `GAS_SPONSOR_PRIVATE_KEY` - Wallet with POL for withdrawal gas fees
