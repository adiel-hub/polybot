# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the bot (requires Python 3.11+)
/opt/homebrew/bin/python3.11 run.py

# Install dependencies
/opt/homebrew/bin/python3.11 -m pip install -r requirements.txt

# Run tests
/opt/homebrew/bin/python3.11 -m pytest

# Run single test
/opt/homebrew/bin/python3.11 -m pytest tests/test_file.py::test_function

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

database/               → SQLite persistence
  models/               → Dataclasses (User, Wallet, Order, Position, etc.)
  repositories/         → CRUD operations per model
  connection.py         → aiosqlite connection + table initialization

jobs/                   → Background tasks (APScheduler via python-telegram-bot)
  deposit_checker.py    → Polls for USDC deposits (30s)
  stop_loss_monitor.py  → Checks prices for stop loss triggers (10s)
  position_sync.py      → Syncs positions from Polymarket (5min)
  copy_trade_sync.py    → Mirrors copied trader orders (30s)
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

## Code Style

- **File length**: Keep files under 300-400 lines. Split large files into smaller modules.
- **Comments**: Add explanatory comments for non-obvious logic. Every function should have a clear purpose.
- **Code reuse**: Extract shared logic into helper functions. Avoid duplication - if code appears twice, refactor it.
- **Organization**: Keep imports sorted, group related functions together, maintain clean module boundaries.

## Testing

- **No mock data**: Never use mock data in tests. Always test with real data or realistic test fixtures.
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

## Environment

Copy `.env.example` to `.env` and configure:
- `TELEGRAM_BOT_TOKEN` - From @BotFather
- `MASTER_ENCRYPTION_KEY` - Generate with `Fernet.generate_key()`
- `POLYGON_RPC_URL` - Polygon RPC endpoint
- `GAS_SPONSOR_PRIVATE_KEY` - Wallet with POL for withdrawal gas fees
