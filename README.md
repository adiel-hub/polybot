# PolyBot

**A Telegram trading bot for Polymarket prediction markets**

![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)
![Telegram Bot](https://img.shields.io/badge/telegram-bot-26A5E4.svg)
![Polymarket](https://img.shields.io/badge/polymarket-trading-purple.svg)

---

## About

PolyBot is a feature-rich Telegram bot that enables trading on [Polymarket](https://polymarket.com) prediction markets directly from your phone. It provides a complete trading experience with wallet management, real-time price updates, portfolio tracking, and advanced features like stop-loss orders and copy trading.

### Key Capabilities

- Trade YES/NO outcomes on prediction markets
- Manage your portfolio with real-time P&L tracking
- Set up automated stop-loss protection
- Copy trades from successful traders
- Deposit and withdraw USDC via Polygon network

---

## Features

### Trading
- **Market Orders** - Buy/sell at current market prices
- **Limit Orders** - Set custom prices (1-99 cents)
- **Order Management** - View history, cancel pending orders
- **Trading Modes** - Standard, Fast, or Ludicrous execution speeds

### Portfolio Management
- **Position Tracking** - View all open positions with entry prices
- **Real-Time P&L** - Track unrealized gains and losses
- **Portfolio Value** - Aggregated value across all positions

### Advanced Features
- **Stop Loss** - Automatic selling when prices hit triggers
- **Copy Trading** - Follow and auto-copy top traders
- **Auto-Claim** - Automatically claim resolved positions

### Wallet & Deposits
- **Auto-Generated Wallets** - Secure Polygon wallet on registration
- **USDC Deposits** - Send USDC to your bot wallet
- **Gas-Sponsored Withdrawals** - Withdraw without needing POL for gas
- **Private Key Export** - Full control of your funds

### Real-Time Updates
- **WebSocket Price Feeds** - Live market prices
- **Instant Deposit Notifications** - Know when funds arrive
- **Position Sync** - Always up-to-date portfolio data

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Bot Framework | [python-telegram-bot](https://python-telegram-bot.org/) v21 |
| Trading API | [Polymarket CLOB](https://docs.polymarket.com/) |
| Market Data | Polymarket Gamma API |
| Blockchain | [Web3.py](https://web3py.readthedocs.io/) / Polygon |
| Database | SQLite with [aiosqlite](https://aiosqlite.omnilib.dev/) |
| Real-Time | WebSockets + [Alchemy](https://www.alchemy.com/) |
| Encryption | [cryptography](https://cryptography.io/) (Fernet) |

---

## Quick Start

### Prerequisites

- Python 3.11 or higher
- Telegram account
- Alchemy API key (free tier works)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/polybot.git
cd polybot

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Configure your environment variables (see Configuration section)

# Run the bot
python run.py
```

---

## Configuration

Create a `.env` file with the following variables:

| Variable | Description | Required |
|----------|-------------|:--------:|
| `TELEGRAM_BOT_TOKEN` | Bot token from [@BotFather](https://t.me/BotFather) | Yes |
| `MASTER_ENCRYPTION_KEY` | Key for encrypting wallet private keys | Yes |
| `POLYGON_RPC_URL` | Polygon RPC endpoint | No |
| `ALCHEMY_API_KEY` | For real-time deposit detection | No |
| `DATABASE_PATH` | SQLite database location | No |
| `GAS_SPONSOR_PRIVATE_KEY` | Wallet for sponsoring withdrawal gas | No |

### Generating the Encryption Key

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## Architecture

```
polybot/
├── bot/                    # Telegram handlers and UI
│   ├── handlers/           # One file per feature
│   ├── conversations/      # Conversation state management
│   └── application.py      # Bot factory and handler wiring
│
├── services/               # Business logic layer
│   ├── user_service.py     # Registration, settings, wallet access
│   ├── trading_service.py  # Order placement via Polymarket CLOB
│   └── market_service.py   # Market data via Gamma API
│
├── core/                   # External integrations
│   ├── polymarket/         # CLOB client, Gamma client
│   ├── blockchain/         # Deposit monitor, withdrawals
│   ├── wallet/             # Wallet generation, encryption
│   └── websocket/          # Real-time subscriptions
│
├── database/               # SQLite persistence
│   ├── models/             # Data models (User, Wallet, Order, etc.)
│   ├── repositories/       # CRUD operations
│   └── connection.py       # Database initialization
│
└── run.py                  # Application entry point
```

---

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Register and create your wallet |
| `/menu` | Open the main menu |
| `/wallet` | View your deposit address |
| `/portfolio` | View your positions |
| `/orders` | View order history |

---

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_file.py::test_function
```

### Code Quality

```bash
# Format code
black .

# Lint code
ruff check .
```

---

## Disclaimer

**Trading involves risk.** Prediction markets are speculative and you may lose some or all of your funds. PolyBot is provided as-is without warranty. Always trade responsibly and never invest more than you can afford to lose.

This bot is not affiliated with or endorsed by Polymarket.

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
