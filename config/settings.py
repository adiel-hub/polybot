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

    # Alchemy Webhook (cost-effective deposit detection)
    alchemy_webhook_signing_key: str = Field(default="", description="Alchemy webhook signing key for verification")
    alchemy_webhook_id: str = Field(default="", description="Alchemy webhook ID for address management")
    alchemy_auth_token: str = Field(default="", description="Alchemy auth token for webhook API")
    webhook_port: int = Field(default=8080, description="Port for webhook server")

    # Rate Limits
    trade_rate_limit: int = Field(default=5, description="Max trades per minute")
    browse_rate_limit: int = Field(default=30, description="Max market views per minute")

    # Admin
    admin_telegram_ids: str = Field(default="", description="Comma-separated list of admin Telegram IDs")

    # Polymarket Builder Program
    poly_builder_api_key: str = Field(default="", description="Polymarket Builder API key")
    poly_builder_secret: str = Field(default="", description="Polymarket Builder secret")
    poly_builder_passphrase: str = Field(default="", description="Polymarket Builder passphrase")

    # Polymarket Relayer (uses builder credentials above)
    relayer_host: str = Field(
        default="https://relayer-v2.polymarket.com",
        description="Polymarket Relayer API host"
    )
    auto_claim_enabled: bool = Field(
        default=True,
        description="Enable automatic claiming of winning positions"
    )
    resolution_check_interval: int = Field(
        default=300,
        description="Interval in seconds to check for market resolutions (5 minutes)"
    )

    # Operator Commission Settings
    operator_commission_rate: float = Field(default=0.01, description="Commission rate on trades (0.01 = 1%)")
    min_commission_amount: float = Field(default=0.01, description="Minimum commission to charge in USDC")
    operator_wallet_address: str = Field(default="", description="Wallet address to receive commissions")

    # Integration Test Configuration
    test_funding_wallet_private_key: str = Field(default="", description="Test wallet private key for funding integration tests")
    test_funding_wallet_address: str = Field(default="", description="Test wallet address")
    test_deposit_amount: float = Field(default=10.0, description="Test deposit amount in USDC")
    test_trade_amount: float = Field(default=5.0, description="Test trade amount in USDC")
    test_withdrawal_amount: float = Field(default=3.0, description="Test withdrawal amount in USDC")

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


# Global settings instance
settings = Settings()
