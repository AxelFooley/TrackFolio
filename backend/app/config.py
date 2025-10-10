"""
Application configuration from environment variables.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


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
    blockchain_sync_enabled: bool = True
    blockchain_sync_interval_minutes: int = 30  # Sync every 30 minutes
    blockchain_max_transactions_per_sync: int = 50
    blockchain_sync_days_back: int = 7
    blockchain_rate_limit_requests_per_second: float = 1.0
    blockchain_request_timeout_seconds: int = 30
    blockchain_max_retries: int = 3

    # Blockchain API endpoints (can be overridden)
    blockstream_api_url: str = "https://blockstream.info/api"
    blockchain_com_api_url: str = "https://blockchain.info"
    blockcypher_api_url: str = "https://api.blockcypher.com/v1/btc/main"

    # Blockchain cache settings
    blockchain_transaction_cache_ttl: int = 300  # 5 minutes
    blockchain_address_cache_ttl: int = 86400  # 24 hours
    blockchain_deduplication_cache_ttl: int = 86400 * 7  # 7 days


# Global settings instance
settings = Settings()
