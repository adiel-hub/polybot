"""Configuration for Polymarket Whale Alert Bot."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load env from PolyBot directory (shared configuration)
polybot_env = Path(__file__).parent.parent / ".env"
if polybot_env.exists():
    load_dotenv(polybot_env)

# Also load local .env if exists (overrides)
local_env = Path(__file__).parent / ".env"
if local_env.exists():
    load_dotenv(local_env, override=True)

# Telegram Configuration
# WHALE_BOT_TOKEN for dedicated whale bot, or fall back to PolyBot's token
TELEGRAM_BOT_TOKEN = os.getenv("WHALE_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")

# PolyBot username for deep links (without @)
POLYBOT_USERNAME = os.getenv("POLYBOT_USERNAME", "")

# Pre-configured channel ID (optional - bot will also accept /start subscriptions)
WHALE_CHANNEL_ID = os.getenv("WHALE_CHANNEL_ID", "")

# Polymarket Data API
DATA_API_URL = "https://data-api.polymarket.com"

# Whale Alert Threshold (in USDC)
WHALE_THRESHOLD = float(os.getenv("WHALE_THRESHOLD", "10000"))

# Polling interval (in seconds)
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "30"))

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
