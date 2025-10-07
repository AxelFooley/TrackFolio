"""
API Manager for rate limiting, caching, and provider management.

Provides centralized rate limiting, caching, and provider fallback functionality
for blockchain API integrations.
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Callable
from dataclasses import dataclass, field
from collections import defaultdict, deque
import redis.asyncio as redis
import aiohttp
from functools import wraps

from app.config import settings
from app.models.blockchain_data import BlockchainErrorResponse

logger = logging.getLogger(__name__)


@dataclass
class RateLimiter:
    """Rate limiter for API calls."""
    max_requests: int
    time_window: int  # seconds
    requests: deque = field(default_factory=deque)

    def is_allowed(self) -> bool:
        """Check if request is allowed under rate limit."""
        now = time.time()

        # Remove old requests outside time window
        while self.requests and self.requests[0] <= now - self.time_window:
            self.requests.popleft()

        # Check if we can make a request
        if len(self.requests) < self.max_requests:
            self.requests.append(now)
            return True

        return False

    def time_until_reset(self) -> float:
        """Get seconds until rate limit resets."""
        if not self.requests:
            return 0
        return max(0, self.requests[0] + self.time_window - time.time())


@dataclass
class ProviderInfo:
    """Information about an API provider."""
    name: str
    base_url: str
    api_key: Optional[str] = None
    timeout: int = 30
    priority: int = 1
    is_healthy: bool = True
    last_health_check: Optional[datetime] = None
    error_count: int = 0
    max_errors: int = 5
    rate_limiter: Optional[RateLimiter] = None


class CacheManager:
    """Redis-based cache manager for blockchain data."""

    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._connected = False

    async def connect(self):
        """Connect to Redis."""
        try:
            self._redis = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await self._redis.ping()
            self._connected = True
            logger.info("Connected to Redis for blockchain caching")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._connected = False

    async def disconnect(self):
        """Disconnect from Redis."""
        if self._redis:
            await self._redis.close()
            self._connected = False

    def is_connected(self) -> bool:
        """Check if Redis is connected."""
        return self._connected

    async def get(self, key: str) -> Optional[Any]:
        """Get cached value."""
        if not self._connected:
            return None

        try:
            value = await self._redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl_seconds: int = 300) -> bool:
        """Set cached value with TTL."""
        if not self._connected:
            return False

        try:
            serialized_value = json.dumps(value, default=str)
            await self._redis.setex(key, ttl_seconds, serialized_value)
            return True
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete cached value."""
        if not self._connected:
            return False

        try:
            await self._redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False

    async def clear_pattern(self, pattern: str) -> int:
        """Clear cache entries matching pattern."""
        if not self._connected:
            return 0

        try:
            keys = await self._redis.keys(pattern)
            if keys:
                return await self._redis.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Cache clear pattern error for {pattern}: {e}")
            return 0


class APIManager:
    """Centralized API management for blockchain integrations."""

    def __init__(self):
        self.providers: Dict[str, List[ProviderInfo]] = defaultdict(list)
        self.cache = CacheManager()
        self.rate_limiters: Dict[str, RateLimiter] = {}
        self._session: Optional[aiohttp.ClientSession] = None
        self._initialized = False

    async def initialize(self):
        """Initialize API manager with providers and cache."""
        if self._initialized:
            return

        # Initialize cache
        await self.cache.connect()

        # Create HTTP session
        connector = aiohttp.TCPConnector(
            limit=100,  # Total connection limit
            limit_per_host=20,  # Per-host connection limit
            ttl_dns_cache=300,
            ttl_dns_cache_per_host=300
        )
        timeout = aiohttp.ClientTimeout(total=settings.blockchain_api_timeout)
        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout
        )

        # Initialize providers
        await self._setup_providers()

        self._initialized = True
        logger.info("API Manager initialized")

    async def cleanup(self):
        """Cleanup resources."""
        if self._session:
            await self._session.close()
        await self.cache.disconnect()
        self._initialized = False
        logger.info("API Manager cleaned up")

    async def _setup_providers(self):
        """Setup API providers for each network."""
        # Bitcoin providers
        if settings.blockchain_api_key:
            self.providers["bitcoin"].append(ProviderInfo(
                name="blockchain",
                base_url="https://blockchain.info",
                api_key=settings.blockchain_api_key,
                priority=1,
                rate_limiter=RateLimiter(settings.bitcoin_rate_per_minute, 60)
            ))

        if settings.blockcypher_api_key:
            self.providers["bitcoin"].append(ProviderInfo(
                name="blockcypher",
                base_url="https://api.blockcypher.com/v1/btc/main",
                api_key=settings.blockcypher_api_key,
                priority=2,
                rate_limiter=RateLimiter(settings.bitcoin_rate_per_minute, 60)
            ))

        # Add Blockstream as free provider
        self.providers["bitcoin"].append(ProviderInfo(
            name="blockstream",
            base_url="https://blockstream.info/api",
            priority=3,
            rate_limiter=RateLimiter(settings.bitcoin_rate_per_minute, 60)
        ))

        # Ethereum/EVM providers
        if settings.alchemy_api_key:
            self.providers["ethereum"].append(ProviderInfo(
                name="alchemy",
                base_url=f"https://eth-mainnet.g.alchemy.com/v2/{settings.alchemy_api_key}",
                api_key=settings.alchemy_api_key,
                priority=1,
                rate_limiter=RateLimiter(settings.ethereum_rate_per_minute, 60)
            ))

            # Add EVM networks with Alchemy
            self.providers["polygon"].append(ProviderInfo(
                name="alchemy",
                base_url=f"https://polygon-mainnet.g.alchemy.com/v2/{settings.alchemy_api_key}",
                api_key=settings.alchemy_api_key,
                priority=1,
                rate_limiter=RateLimiter(settings.polygon_rate_per_minute, 60)
            ))

            self.providers["arbitrum"].append(ProviderInfo(
                name="alchemy",
                base_url=f"https://arb-mainnet.g.alchemy.com/v2/{settings.alchemy_api_key}",
                api_key=settings.alchemy_api_key,
                priority=1,
                rate_limiter=RateLimiter(settings.arbitrum_rate_per_minute, 60)
            ))

            self.providers["optimism"].append(ProviderInfo(
                name="alchemy",
                base_url=f"https://opt-mainnet.g.alchemy.com/v2/{settings.alchemy_api_key}",
                api_key=settings.alchemy_api_key,
                priority=1,
                rate_limiter=RateLimiter(settings.optimism_rate_per_minute, 60)
            ))

        if settings.infura_project_id:
            self.providers["ethereum"].append(ProviderInfo(
                name="infura",
                base_url=f"https://mainnet.infura.io/v3/{settings.infura_project_id}",
                api_key=settings.infura_project_id,
                priority=2,
                rate_limiter=RateLimiter(settings.ethereum_rate_per_minute, 60)
            ))

        # Add Ankr as fallback
        if settings.ankr_api_key:
            self.providers["ethereum"].append(ProviderInfo(
                name="ankr",
                base_url=f"https://rpc.ankr.com/eth",
                api_key=settings.ankr_api_key,
                priority=3,
                rate_limiter=RateLimiter(settings.ethereum_rate_per_minute, 60)
            ))

        # Add public endpoints as last resort
        self.providers["ethereum"].append(ProviderInfo(
            name="public",
            base_url="https://cloudflare-eth.com",
            priority=10,
            rate_limiter=RateLimiter(10, 60)  # Very conservative rate limiting
        ))

        # Sort providers by priority
        for network in self.providers:
            self.providers[network].sort(key=lambda p: p.priority)

        logger.info(f"Setup providers for networks: {list(self.providers.keys())}")

    def get_healthy_providers(self, network: str) -> List[ProviderInfo]:
        """Get healthy providers for a network."""
        return [p for p in self.providers.get(network, []) if p.is_healthy]

    async def make_request(
        self,
        network: str,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        use_cache: bool = True,
        cache_ttl: Optional[int] = None
    ) -> Union[Dict, List, None]:
        """
        Make API request with provider fallback and rate limiting.

        Args:
            network: Blockchain network (bitcoin, ethereum, etc.)
            endpoint: API endpoint path
            method: HTTP method
            params: Query parameters
            data: Request body data
            headers: Additional headers
            use_cache: Whether to use caching
            cache_ttl: Cache TTL in seconds

        Returns:
            API response data or None if all providers fail
        """
        if not self._initialized:
            await self.initialize()

        # Generate cache key
        cache_key = None
        if use_cache:
            params_str = json.dumps(params or {}, sort_keys=True)
            cache_key = f"blockchain:{network}:{endpoint}:{params_str}"

            # Try cache first
            cached_data = await self.cache.get(cache_key)
            if cached_data:
                logger.debug(f"Cache hit for {network}:{endpoint}")
                return cached_data

        # Get healthy providers
        providers = self.get_healthy_providers(network)
        if not providers:
            logger.error(f"No healthy providers available for {network}")
            return None

        # Try providers in order
        last_error = None

        for provider in providers:
            # Check rate limiting
            if provider.rate_limiter and not provider.rate_limiter.is_allowed():
                wait_time = provider.rate_limiter.time_until_reset()
                logger.warning(f"Rate limited for {provider.name}, waiting {wait_time:.1f}s")
                if wait_time > 60:  # Don't wait too long
                    continue
                await asyncio.sleep(wait_time)

            # Make request
            try:
                url = f"{provider.base_url}{endpoint}"
                request_headers = headers or {}

                if provider.api_key and provider.name != "public":
                    request_headers.update({
                        "Authorization": f"Bearer {provider.api_key}",
                        "User-Agent": "TrackFolio-Portfolio/1.0"
                    })

                start_time = time.time()

                async with self._session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=data,
                    headers=request_headers
                ) as response:
                    response_time = int((time.time() - start_time) * 1000)

                    if response.status == 200:
                        result_data = await response.json()

                        # Cache successful response
                        if use_cache and cache_key:
                            ttl = cache_ttl or settings.blockchain_cache_ttl_seconds
                            await self.cache.set(cache_key, result_data, ttl)

                        # Reset error count on success
                        provider.error_count = 0

                        logger.debug(f"Success from {provider.name} for {network}:{endpoint} ({response_time}ms)")
                        return result_data

                    else:
                        error_text = await response.text()
                        last_error = BlockchainErrorResponse(
                            error_code=f"HTTP_{response.status}",
                            error_message=f"HTTP {response.status}: {error_text}",
                            provider=provider.name,
                            request_url=url,
                            request_params=params
                        )
                        provider.error_count += 1

                        # Mark provider as unhealthy if too many errors
                        if provider.error_count >= provider.max_errors:
                            provider.is_healthy = False
                            logger.warning(f"Marked {provider.name} as unhealthy due to errors")

                        logger.warning(f"Error from {provider.name}: {last_error.error_message}")

            except asyncio.TimeoutError:
                last_error = BlockchainErrorResponse(
                    error_code="TIMEOUT",
                    error_message="Request timeout",
                    provider=provider.name,
                    request_url=f"{provider.base_url}{endpoint}",
                    request_params=params
                )
                provider.error_count += 1
                logger.warning(f"Timeout from {provider.name}")

            except Exception as e:
                last_error = BlockchainErrorResponse(
                    error_code="UNKNOWN",
                    error_message=str(e),
                    provider=provider.name,
                    request_url=f"{provider.base_url}{endpoint}",
                    request_params=params
                )
                provider.error_count += 1
                logger.warning(f"Exception from {provider.name}: {str(e)}")

        # All providers failed
        logger.error(f"All providers failed for {network}:{endpoint}")
        if last_error:
            logger.error(f"Last error: {last_error.error_message}")
        return None

    async def batch_request(
        self,
        network: str,
        requests: List[Dict],
        use_cache: bool = True
    ) -> List[Dict]:
        """
        Make multiple requests in parallel.

        Args:
            network: Blockchain network
            requests: List of request dictionaries
            use_cache: Whether to use caching

        Returns:
            List of responses
        """
        if not requests:
            return []

        # Create tasks for parallel execution
        tasks = []
        for i, req in enumerate(requests):
            task = self.make_request(
                network=network,
                endpoint=req.get("endpoint", ""),
                method=req.get("method", "GET"),
                params=req.get("params"),
                data=req.get("data"),
                headers=req.get("headers"),
                use_cache=use_cache,
                cache_ttl=req.get("cache_ttl")
            )
            tasks.append((i, task))

        # Execute tasks concurrently
        results = [None] * len(requests)

        async def execute_task(index_task):
            index, task = index_task
            try:
                result = await task
                results[index] = result
            except Exception as e:
                logger.error(f"Batch request {index} failed: {e}")
                results[index] = None

        await asyncio.gather(*(execute_task(t) for t in tasks))

        return results

    async def health_check(self, network: str) -> Dict[str, Any]:
        """
        Perform health check on providers for a network.

        Args:
            network: Blockchain network

        Returns:
            Health check results
        """
        providers = self.providers.get(network, [])
        results = {
            "network": network,
            "providers": [],
            "healthy_count": 0,
            "total_count": len(providers),
            "checked_at": datetime.utcnow().isoformat()
        }

        for provider in providers:
            start_time = time.time()
            is_healthy = False
            error_message = None

            try:
                # Simple health check - get latest block or basic endpoint
                if network == "bitcoin":
                    response = await self.make_request(
                        network=network,
                        endpoint="/blocks",
                        use_cache=False
                    )
                else:  # Ethereum/EVM
                    response = await self.make_request(
                        network=network,
                        endpoint="",
                        method="POST",
                        data={
                            "jsonrpc": "2.0",
                            "method": "eth_blockNumber",
                            "params": [],
                            "id": 1
                        },
                        use_cache=False
                    )

                is_healthy = response is not None
                if not is_healthy:
                    error_message = "No response"

            except Exception as e:
                error_message = str(e)

            response_time = int((time.time() - start_time) * 1000)

            # Update provider status
            provider.is_healthy = is_healthy
            provider.last_health_check = datetime.utcnow()

            provider_result = {
                "name": provider.name,
                "is_healthy": is_healthy,
                "response_time_ms": response_time,
                "error_message": error_message,
                "error_count": provider.error_count
            }

            results["providers"].append(provider_result)

            if is_healthy:
                results["healthy_count"] += 1

        return results

    async def clear_cache(self, network: Optional[str] = None) -> int:
        """Clear blockchain cache."""
        if network:
            pattern = f"blockchain:{network}:*"
        else:
            pattern = "blockchain:*"

        cleared_count = await self.cache.clear_pattern(pattern)
        logger.info(f"Cleared {cleared_count} cache entries for pattern: {pattern}")
        return cleared_count


# Global API manager instance
api_manager = APIManager()


def rate_limit(max_calls: int, time_window: int = 60):
    """Decorator for rate limiting function calls."""
    def decorator(func: Callable):
        limiter = RateLimiter(max_calls, time_window)

        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not limiter.is_allowed():
                wait_time = limiter.time_until_reset()
                logger.warning(f"Rate limit exceeded, waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)

            return await func(*args, **kwargs)

        return wrapper
    return decorator


def cache_response(ttl_seconds: int = 300, key_prefix: str = ""):
    """Decorator for caching function responses."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{key_prefix}:{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"

            # Try cache first
            cached = await api_manager.cache.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached

            # Execute function
            result = await func(*args, **kwargs)

            # Cache result
            if result is not None:
                await api_manager.cache.set(cache_key, result, ttl_seconds)
                logger.debug(f"Cached result for {func.__name__}")

            return result

        return wrapper
    return decorator