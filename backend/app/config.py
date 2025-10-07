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

    # External APIs
    coingecko_api_key: str = ""  # Optional, for higher rate limits

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

    # Security settings
    encryption_key: str = ""  # Required for wallet credential encryption
    security_key_rotation_days: int = 90  # Days between key rotations (future)
    wallet_api_timeout: int = 30  # Timeout for wallet API calls
    max_wallet_connections: int = 10  # Maximum wallet connections per user
    rate_limit_wallet_api: int = 60  # Rate limit for wallet API calls per minute

    # Blockchain API configurations
    # Bitcoin API providers
    blockchain_api_key: str = ""  # blockchain.com API key
    blockcypher_api_key: str = ""  # blockcypher.com API key
    bitcoin_api_timeout: int = 30  # Timeout for Bitcoin API calls
    bitcoin_rate_limit: int = 30  # Bitcoin API calls per minute

    # Ethereum/EVM API providers
    alchemy_api_key: str = ""  # Alchemy API key (primary)
    infura_project_id: str = ""  # Infura Project ID (fallback)
    ankr_api_key: str = ""  # Ankr API key (fallback)
    ethereum_api_timeout: int = 30  # Timeout for Ethereum API calls
    ethereum_rate_limit: int = 60  # Ethereum API calls per minute

    # Network-specific RPC URLs
    bitcoin_rpc_url: str = "https://blockstream.info/api"
    ethereum_rpc_url: str = ""  # Will default to Alchemy if API key provided
    polygon_rpc_url: str = ""  # Will default to Alchemy if API key provided
    bsc_rpc_url: str = ""  # Will default to Alchemy if API key provided
    arbitrum_rpc_url: str = ""  # Will default to Alchemy if API key provided
    optimism_rpc_url: str = ""  # Will default to Alchemy if API key provided

    # Blockchain caching settings
    blockchain_cache_ttl_seconds: int = 300  # 5 minutes for balance data
    blockchain_tx_cache_ttl_seconds: int = 3600  # 1 hour for transaction data
    blockchain_network_stats_ttl: int = 60  # 1 minute for network stats

    # Blockchain sync settings
    blockchain_sync_batch_size: int = 50  # Number of addresses to sync in parallel
    blockchain_sync_max_retries: int = 3  # Max retries for failed sync operations
    blockchain_sync_retry_delay: int = 5  # Seconds between retries

    # Price oracle settings
    coingecko_api_key: str = ""  # For blockchain asset pricing
    defillama_api_key: str = ""  # For DeFi token pricing (future)

    # Blockchain rate limiting by network
    bitcoin_rate_per_minute: int = 30
    ethereum_rate_per_minute: int = 60
    polygon_rate_per_minute: int = 60
    bsc_rate_per_minute: int = 60
    arbitrum_rate_per_minute: int = 60
    optimism_rate_per_minute: int = 60

    # Testnet configuration
    enable_testnet_apis: bool = False  # Whether to use testnet APIs
    bitcoin_testnet_rpc_url: str = "https://blockstream.info/testnet/api"
    ethereum_testnet_rpc_url: str = ""  # Sepolia testnet

    # Blockchain provider priorities (fallback order)
    ethereum_providers: List[str] = ["alchemy", "infura", "ankr", "public"]
    bitcoin_providers: List[str] = ["blockchain", "blockcypher", "blockstream"]

    # API health check settings
    blockchain_health_check_interval: int = 300  # Seconds between health checks
    blockchain_health_check_timeout: int = 10  # Timeout for health checks


# Global settings instance
settings = Settings()
