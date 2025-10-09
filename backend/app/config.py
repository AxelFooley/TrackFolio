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


# Global settings instance
settings = Settings()
