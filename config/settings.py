from pydantic_settings import BaseSettings
from pydantic import ConfigDict, Field
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Telegram
    telegram_bot_token: str = Field(..., description="Telegram bot token from @BotFather")

    # Security
    master_encryption_key: str = Field(..., description="Master key for encrypting wallet private keys")

    # Blockchain
    polygon_rpc_url: str = Field(default="https://polygon-rpc.com", description="Polygon RPC URL")
    gas_sponsor_private_key: str = Field(default="", description="Private key for gas sponsorship")

    # Database
    database_path: str = Field(default="./data/polybot.db", description="SQLite database path")

    # Polymarket
    clob_host: str = Field(default="https://clob.polymarket.com", description="Polymarket CLOB API host")
    gamma_host: str = Field(default="https://gamma-api.polymarket.com", description="Polymarket Gamma API host")
    chain_id: int = Field(default=137, description="Polygon chain ID")

    # WebSocket URLs
    polymarket_ws_market_url: str = Field(
        default="wss://ws-subscriptions-clob.polymarket.com/ws/market",
        description="Polymarket market WebSocket URL"
    )
    polymarket_ws_user_url: str = Field(
        default="wss://ws-subscriptions-clob.polymarket.com/ws/user",
        description="Polymarket user WebSocket URL"
    )
    polymarket_ws_live_url: str = Field(
        default="wss://ws-live-data.polymarket.com",
        description="Polymarket live data WebSocket URL"
    )
    alchemy_api_key: str = Field(default="", description="Alchemy API key for Polygon WebSocket")

    # Rate Limits
    trade_rate_limit: int = Field(default=5, description="Max trades per minute")
    browse_rate_limit: int = Field(default=30, description="Max market views per minute")

    # Admin
    admin_telegram_ids: str = Field(default="", description="Comma-separated list of admin Telegram IDs")

    # Polymarket Builder Program
    poly_builder_api_key: str = Field(default="", description="Polymarket Builder API key")
    poly_builder_secret: str = Field(default="", description="Polymarket Builder secret")
    poly_builder_passphrase: str = Field(default="", description="Polymarket Builder passphrase")

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Allow extra fields in .env
    )

    @property
    def db_path(self) -> Path:
        """Return database path as Path object."""
        return Path(self.database_path)

    @property
    def alchemy_ws_url(self) -> str:
        """Return Alchemy WebSocket URL for Polygon."""
        if not self.alchemy_api_key:
            return ""
        return f"wss://polygon-mainnet.g.alchemy.com/v2/{self.alchemy_api_key}"


# Global settings instance
settings = Settings()
