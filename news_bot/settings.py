"""News bot specific settings."""

from pydantic_settings import BaseSettings
from pydantic import ConfigDict, Field


class NewsBotSettings(BaseSettings):
    """Settings specific to the news bot."""

    # Telegram Channel
    news_channel_id: str = Field(
        default="",
        description="Telegram channel ID or @username for news posts"
    )
    news_bot_token: str = Field(
        default="",
        description="Telegram bot token for news bot (can use same as main bot)"
    )
    trading_bot_username: str = Field(
        default="",
        description="Username of the trading bot for Trade button deep links (without @)"
    )

    # Claude API
    anthropic_api_key: str = Field(
        default="",
        description="Anthropic API key for Claude"
    )
    claude_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Claude model to use for article generation"
    )
    article_max_tokens: int = Field(
        default=2000,
        description="Maximum tokens for generated articles"
    )

    # Web Search
    tavily_api_key: str = Field(
        default="",
        description="Tavily API key for web search"
    )

    # Scheduler
    poll_interval_minutes: int = Field(
        default=15,
        description="Minutes between market polls"
    )
    max_markets_per_poll: int = Field(
        default=5,
        description="Maximum markets to process per poll"
    )

    # Market Filters
    min_market_volume: float = Field(
        default=1000.0,
        description="Minimum total volume for market to be considered"
    )
    min_market_liquidity: float = Field(
        default=500.0,
        description="Minimum liquidity for market to be considered"
    )

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# Global settings instance
news_settings = NewsBotSettings()
