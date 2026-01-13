"""Application constants."""

# Polygon USDC contract addresses
USDC_ADDRESS = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"  # Native USDC on Polygon
USDC_E_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"  # Bridged USDC.e on Polygon

# USDC has 6 decimals
USDC_DECIMALS = 6

# Minimum deposit amount (in USDC)
MIN_DEPOSIT = 1.0

# Minimum withdrawal amount (in USDC)
MIN_WITHDRAWAL = 1.0

# Maximum withdrawal amount per transaction (in USDC)
MAX_WITHDRAWAL = 10000.0

# Polymarket price bounds
MIN_PRICE = 0.01
MAX_PRICE = 0.99

# Pagination
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 50

# Job intervals (in seconds)
DEPOSIT_CHECK_INTERVAL = 30
STOP_LOSS_CHECK_INTERVAL = 10
POSITION_SYNC_INTERVAL = 300
BALANCE_UPDATE_INTERVAL = 120
MARKET_CACHE_INTERVAL = 900
COPY_TRADE_SYNC_INTERVAL = 30

# ERC20 Transfer event signature
TRANSFER_EVENT_SIGNATURE = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

# License agreement text
LICENSE_TEXT = """
*Welcome to PolyBot*

Your gateway to Polymarket trading.

Before proceeding, please review and accept our terms:

1. This bot is provided as-is for trading on Polymarket
2. Trading involves risk - you may lose your entire investment
3. You are responsible for compliance with your local laws
4. Your wallet keys are encrypted, but you trade at your own risk
5. We do not provide financial advice

By clicking "Accept", you agree to these terms.
"""

# Market categories
MARKET_CATEGORIES = {
    "volume": "Top Volume",
    "trending": "Trending",
    "new": "New Markets",
    "politics": "Politics",
    "sports": "Sports",
    "crypto": "Crypto",
    "entertainment": "Entertainment",
    "science": "Science",
}
