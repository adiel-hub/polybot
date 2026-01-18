"""Whale bot configuration loaded from environment."""
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("WHALE_BOT_TOKEN", "")
WHALE_THRESHOLD = float(os.getenv("WHALE_THRESHOLD", "10000"))
POLL_INTERVAL = int(os.getenv("WHALE_POLL_INTERVAL", "30"))
POLYBOT_USERNAME = os.getenv("POLYBOT_USERNAME", "")
LOG_LEVEL = os.getenv("WHALE_LOG_LEVEL", "INFO")

# Pre-configured channel ID (optional - bot will also accept /start subscriptions)
WHALE_CHANNEL_ID = os.getenv("WHALE_CHANNEL_ID", "")

# Polymarket Data API
DATA_API_URL = "https://data-api.polymarket.com"
