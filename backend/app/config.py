"""
Application configuration from environment variables.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, PositiveInt, PositiveFloat, NonNegativeInt, HttpUrl
from typing import List, Optional


class Settings(BaseSettings):
    """Application settings from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )

    # Application
    app_name: str = "Portfolio Tracker"
    environment: str = "production"
    log_level: str = "INFO"
    allowed_origins: List[str] = ["http://localhost:3000", "http://localhost"]

    # Database
    database_url: str = "postgresql://portfolio:portfolio@localhost:5432/portfolio_db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    
    # Timezone
    timezone: str = "Europe/Rome"

    # Rate limiting
    rate_limit_requests: int = 100  # requests per minute
    rate_limit_window: int = 60  # seconds

    # Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    # Price update schedule (cron format)
    price_update_hour: int = 23
    price_update_minute: int = 0

    # Cache TTL (seconds)
    price_cache_ttl: int = 86400  # 24 hours
    metrics_cache_ttl: int = 86400  # 24 hours

    # Blockchain settings
    blockchain_sync_enabled: bool = Field(
        True,
        env="BLOCKCHAIN_SYNC_ENABLED",
        description="Enable or disable blockchain sync"
    )
    blockchain_sync_interval_minutes: PositiveInt = Field(
        30,
        env="BLOCKCHAIN_SYNC_INTERVAL_MINUTES",
        description="Interval in minutes between blockchain syncs"
    )
    blockchain_max_transactions_per_sync: PositiveInt = Field(
        50,
        env="BLOCKCHAIN_MAX_TRANSACTIONS_PER_SYNC",
        description="Maximum number of transactions to sync per run"
    )
    blockchain_sync_days_back: PositiveInt = Field(
        7,
        env="BLOCKCHAIN_SYNC_DAYS_BACK",
        description="Number of days back to fetch transactions"
    )
    blockchain_rate_limit_requests_per_second: PositiveFloat = Field(
        1.0,
        env="BLOCKCHAIN_RATE_LIMIT_REQUESTS_PER_SECOND",
        description="Rate limit for blockchain API requests per second"
    )
    blockchain_request_timeout_seconds: PositiveInt = Field(
        30,
        env="BLOCKCHAIN_REQUEST_TIMEOUT_SECONDS",
        description="Timeout for blockchain API requests in seconds"
    )
    blockchain_max_retries: PositiveInt = Field(
        3,
        env="BLOCKCHAIN_MAX_RETRIES",
        description="Maximum number of retries for blockchain API requests"
    )

    # Blockchain API endpoints (can be overridden)
    blockstream_api_url: HttpUrl = Field(
        "https://blockstream.info/api",
        env="BLOCKSTREAM_API_URL",
        description="Blockstream API endpoint"
    )
    blockchain_com_api_url: HttpUrl = Field(
        "https://blockchain.info",
        env="BLOCKCHAIN_COM_API_URL",
        description="Blockchain.com API endpoint"
    )
    blockcypher_api_url: HttpUrl = Field(
        "https://api.blockcypher.com/v1/btc/main",
        env="BLOCKCYPHER_API_URL",
        description="BlockCypher API endpoint"
    )

    # Blockchain cache settings
    blockchain_transaction_cache_ttl: NonNegativeInt = Field(
        300,
        env="BLOCKCHAIN_TRANSACTION_CACHE_TTL",
        description="Cache TTL for blockchain transactions (seconds)"
    )
    blockchain_address_cache_ttl: NonNegativeInt = Field(
        86400,
        env="BLOCKCHAIN_ADDRESS_CACHE_TTL",
        description="Cache TTL for blockchain addresses (seconds)"
    )
    blockchain_deduplication_cache_ttl: NonNegativeInt = Field(
        86400 * 7,
        env="BLOCKCHAIN_DEDUPLICATION_CACHE_TTL",
        description="Cache TTL for blockchain transaction deduplication (seconds)"
    )

    # News API settings
    news_rate_limit_requests_per_minute: int = Field(
        60,
        env="NEWS_RATE_LIMIT_REQUESTS_PER_MINUTE",
        description="Rate limit for news API requests per minute"
    )
    news_cache_ttl_seconds: int = Field(
        600,  # 10 minutes
        env="NEWS_CACHE_TTL_SECONDS",
        description="Cache TTL for news API responses (seconds)"
    )
    news_sentiment_cache_ttl_seconds: int = Field(
        1800,  # 30 minutes
        env="NEWS_SENTIMENT_CACHE_TTL_SECONDS",
        description="Cache TTL for news sentiment analysis (seconds)"
    )
    news_movers_cache_ttl_seconds: int = Field(
        300,  # 5 minutes
        env="NEWS_MOVERS_CACHE_TTL_SECONDS",
        description="Cache TTL for news movers endpoint (seconds)"
    )
    alpha_vantage_enabled: bool = Field(
        True,
        env="ALPHA_VANTAGE_ENABLED",
        description="Enable Alpha Vantage news API integration"
    )
    alpha_vantage_api_key: Optional[str] = Field(
        None,
        env="ALPHA_VANTAGE_API_KEY",
        description="Alpha Vantage API key for news fetching"
    )
    alpha_vantage_base_url: str = Field(
        "https://www.alphavantage.co/query",
        env="ALPHA_VANTAGE_BASE_URL",
        description="Alpha Vantage API base URL"
    )
    alpha_vantage_timeout: PositiveInt = Field(
        30,
        env="ALPHA_VANTAGE_TIMEOUT",
        description="Timeout for Alpha Vantage API requests in seconds"
    )
    alpha_vantage_request_delay: PositiveFloat = Field(
        1.0,
        env="ALPHA_VANTAGE_REQUEST_DELAY",
        description="Delay between Alpha Vantage API requests in seconds"
    )
    alpha_vantage_requests_per_minute: PositiveInt = Field(
        5,
        env="ALPHA_VANTAGE_REQUESTS_PER_MINUTE",
        description="Alpha Vantage API requests per minute limit"
    )
    alpha_vantage_requests_per_day: PositiveInt = Field(
        25,
        env="ALPHA_VANTAGE_REQUESTS_PER_DAY",
        description="Alpha Vantage API requests per day limit"
    )
    alpha_vantage_fallback_enabled: bool = Field(
        True,
        env="ALPHA_VANTAGE_FALLBACK_ENABLED",
        description="Enable fallback to cached data when rate limited"
    )
    alpha_vantage_cache_fallback_ttl: int = Field(
        86400,  # 24 hours
        env="ALPHA_VANTAGE_CACHE_FALLBACK_TTL",
        description="Extended TTL for cached data used as fallback during rate limits"
    )
    alpha_vantage_stale_data_threshold_hours: int = Field(
        48,  # 2 days
        env="ALPHA_VANTAGE_STALE_DATA_THRESHOLD_HOURS",
        description="Maximum age of cached data to use as fallback (hours)"
    )
    alpha_vantage_rate_limit_backoff_hours: float = Field(
        24.0,
        env="ALPHA_VANTAGE_RATE_LIMIT_BACKOFF_HOURS",
        description="Hours to wait before retrying after daily rate limit is hit"
    )


# Global settings instance
settings = Settings()
