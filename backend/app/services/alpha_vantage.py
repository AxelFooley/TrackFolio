"""
Alpha Vantage API service for market data, company overview, and news data.

Provides functionality to fetch stock prices, company information, and news
with proper rate limiting and caching to respect API limits.
"""
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Any
import logging
import time
import requests
from concurrent.futures import ThreadPoolExecutor
import threading

from app.config import settings
from app.services.cache import CacheService

logger = logging.getLogger(__name__)


class AlphaVantageRateLimiter:
    """Rate limiter for Alpha Vantage API calls.

    Handles both per-minute (5 calls/min) and per-day (25 calls/day) limits.
    """

    def __init__(self):
        self.minute_calls = 0
        self.day_calls = 0
        self.last_reset_time = time.time()
        self.last_minute_reset = time.time()
        self._lock = threading.Lock()

    def can_make_request(self) -> bool:
        """Check if we can make an API call without exceeding rate limits."""
        current_time = time.time()

        with self._lock:
            # Reset minute counter if more than 60 seconds have passed
            if current_time - self.last_minute_reset >= 60:
                self.minute_calls = 0
                self.last_minute_reset = current_time

            # Check minute limit
            if self.minute_calls >= settings.alpha_vantage_requests_per_minute:
                logger.debug(f"Minute rate limit reached: {self.minute_calls}/{settings.alpha_vantage_requests_per_minute}")
                return False

            # Check day limit
            if self.day_calls >= settings.alpha_vantage_requests_per_day:
                logger.debug(f"Daily rate limit reached: {self.day_calls}/{settings.alpha_vantage_requests_per_day}")
                return False

            return True

    def record_request(self) -> None:
        """Record that an API call was made."""
        with self._lock:
            self.minute_calls += 1
            self.day_calls += 1
            logger.debug(f"Recorded API call: minute={self.minute_calls}, day={self.day_calls}")

    def get_wait_time(self) -> float:
        """Calculate how long to wait before making the next request."""
        current_time = time.time()

        with self._lock:
            # Check minute limit
            if self.minute_calls >= settings.alpha_vantage_requests_per_minute:
                time_since_last_minute_reset = current_time - self.last_minute_reset
                wait_time = max(0, 60 - time_since_last_minute_reset)
                return wait_time

            # Check day limit
            if self.day_calls >= settings.alpha_vantage_requests_per_day:
                # Wait until next day
                next_day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                wait_time = (next_day - datetime.now()).total_seconds()
                return wait_time

            return 0.0


class AlphaVantageClient:
    """Alpha Vantage API client with rate limiting and caching."""

    def __init__(self):
        self.base_url = str(settings.alpha_vantage_base_url)
        self.api_key = settings.alpha_vantage_api_key
        self.timeout = settings.alpha_vantage_timeout
        self.rate_limiter = AlphaVantageRateLimiter()
        self.cache_manager = CacheService()

        # Cache keys
        self.price_cache_key = "alpha_vantage_prices"
        self.news_cache_key = "alpha_vantage_news"
        self.metadata_cache_key = "alpha_vantage_metadata"

    def _make_api_request(self, function: str, symbol: str, **kwargs) -> Dict:
        """Make an API request to Alpha Vantage with proper error handling."""
        if not self.api_key:
            raise ValueError("Alpha Vantage API key not configured")

        if not self.rate_limiter.can_make_request():
            wait_time = self.rate_limiter.get_wait_time()
            logger.warning(f"Rate limit reached, waiting {wait_time:.1f} seconds")
            time.sleep(wait_time)

        # Wait for configured delay between requests
        time.sleep(settings.alpha_vantage_request_delay)

        params = {
            'function': function,
            'symbol': symbol,
            'apikey': self.api_key,
            **kwargs
        }

        for attempt in range(settings.alpha_vantage_max_retries):
            try:
                logger.debug(f"Making Alpha Vantage request: function={function}, symbol={symbol}")

                response = requests.get(
                    self.base_url,
                    params=params,
                    timeout=self.timeout
                )
                response.raise_for_status()

                data = response.json()

                # Check for API errors
                if 'Error Message' in data:
                    error_msg = data['Error Message']
                    logger.error(f"Alpha Vantage API error: {error_msg}")
                    raise ValueError(f"Alpha Vantage API error: {error_msg}")

                if 'Information' in data:
                    info_msg = data['Information']
                    logger.warning(f"Alpha Vantage API info: {info_msg}")
                    if "API call frequency" in info_msg:
                        # Hit rate limit, need to wait
                        self.rate_limiter.record_request()
                        wait_time = self.rate_limiter.get_wait_time()
                        time.sleep(wait_time)
                        continue
                    raise ValueError(f"Alpha Vantage API info: {info_msg}")

                self.rate_limiter.record_request()
                return data

            except requests.exceptions.RequestException as e:
                logger.warning(f"Alpha Vantage request attempt {attempt + 1} failed: {str(e)}")
                if attempt < settings.alpha_vantage_max_retries - 1:
                    time.sleep(settings.alpha_vantage_retry_delay * (attempt + 1))
                else:
                    raise

        raise Exception("Max retries exceeded for Alpha Vantage API request")

    def fetch_intraday_data(self, symbol: str, interval: str = "5min", outputsize: str = "compact") -> List[Dict]:
        """Fetch intraday price data for a symbol."""
        cache_key = f"{self.price_cache_key}:intraday:{symbol}:{interval}:{outputsize}"
        cached_data = self.cache_manager.get(cache_key)

        if cached_data:
            logger.debug(f"Cache hit for intraday data: {symbol}")
            return cached_data

        try:
            data = self._make_api_request(
                "TIME_SERIES_INTRADAY",
                symbol,
                interval=interval,
                outputsize=outputsize
            )

            time_series = data.get("Time Series " + interval.upper(), {})

            result = []
            for timestamp, values in time_series.items():
                try:
                    result.append({
                        "timestamp": timestamp,
                        "open": Decimal(str(values["1. open"])),
                        "high": Decimal(str(values["2. high"])),
                        "low": Decimal(str(values["3. low"])),
                        "close": Decimal(str(values["4. close"])),
                        "volume": int(values["5. volume"])
                    })
                except (InvalidOperation, ValueError) as e:
                    logger.warning(f"Error parsing intraday data point for {symbol}: {e}")
                    continue

            # Sort by timestamp
            result.sort(key=lambda x: x["timestamp"])

            # Cache the result
            self.cache_manager.set(cache_key, result, settings.alpha_vantage_price_cache_ttl)

            logger.info(f"Fetched {len(result)} intraday data points for {symbol}")
            return result

        except Exception as e:
            logger.error(f"Error fetching intraday data for {symbol}: {str(e)}")
            raise

    def fetch_daily_data(self, symbol: str, outputsize: str = "compact") -> List[Dict]:
        """Fetch daily price data for a symbol."""
        cache_key = f"{self.price_cache_key}:daily:{symbol}:{outputsize}"
        cached_data = self.cache_manager.get(cache_key)

        if cached_data:
            logger.debug(f"Cache hit for daily data: {symbol}")
            return cached_data

        try:
            data = self._make_api_request(
                "TIME_SERIES_DAILY",
                symbol,
                outputsize=outputsize
            )

            time_series = data.get("Time Series (Daily)", {})

            result = []
            for timestamp, values in time_series.items():
                try:
                    result.append({
                        "date": timestamp.split()[0],  # Remove time part
                        "open": Decimal(str(values["1. open"])),
                        "high": Decimal(str(values["2. high"])),
                        "low": Decimal(str(values["3. low"])),
                        "close": Decimal(str(values["4. close"])),
                        "volume": int(values["5. volume"])
                    })
                except (InvalidOperation, ValueError) as e:
                    logger.warning(f"Error parsing daily data point for {symbol}: {e}")
                    continue

            # Sort by date
            result.sort(key=lambda x: x["date"])

            # Cache the result
            self.cache_manager.set(cache_key, result, settings.alpha_vantage_price_cache_ttl)

            logger.info(f"Fetched {len(result)} daily data points for {symbol}")
            return result

        except Exception as e:
            logger.error(f"Error fetching daily data for {symbol}: {str(e)}")
            raise

    def fetch_company_overview(self, symbol: str) -> Dict:
        """Fetch company overview data for a symbol."""
        cache_key = f"{self.metadata_cache_key}:company:{symbol}"
        cached_data = self.cache_manager.get(cache_key)

        if cached_data:
            logger.debug(f"Cache hit for company overview: {symbol}")
            return cached_data

        try:
            data = self._make_api_request(
                "OVERVIEW",
                symbol
            )

            # Clean up the data by converting numeric fields to proper types
            cleaned_data = {}
            for key, value in data.items():
                if value:
                    try:
                        # Try to convert numeric values
                        if '.' in str(value):
                            cleaned_data[key] = Decimal(value)
                        else:
                            cleaned_data[key] = int(value)
                    except (InvalidOperation, ValueError):
                        # Keep as string if not numeric
                        cleaned_data[key] = value
                else:
                    cleaned_data[key] = value

            # Cache the result
            self.cache_manager.set(cache_key, cleaned_data, settings.alpha_vantage_metadata_cache_ttl)

            logger.info(f"Fetched company overview for {symbol}")
            return cleaned_data

        except Exception as e:
            logger.error(f"Error fetching company overview for {symbol}: {str(e)}")
            raise

    def fetch_earnings_data(self, symbol: str) -> List[Dict]:
        """Fetch earnings data for a symbol."""
        cache_key = f"{self.metadata_cache_key}:earnings:{symbol}"
        cached_data = self.cache_manager.get(cache_key)

        if cached_data:
            logger.debug(f"Cache hit for earnings data: {symbol}")
            return cached_data

        try:
            data = self._make_api_request(
                "EARNINGS",
                symbol
            )

            # Extract quarterly earnings
            quarterly = data.get("quarterlyEarnings", [])
            cleaned_quarterly = []

            for quarter in quarterly:
                cleaned_quarter = {}
                for key, value in quarter.items():
                    if value:
                        try:
                            if '.' in str(value):
                                cleaned_quarter[key] = Decimal(value)
                            else:
                                cleaned_quarter[key] = int(value)
                        except (InvalidOperation, ValueError):
                            cleaned_quarter[key] = value
                    else:
                        cleaned_quarter[key] = value
                cleaned_quarterly.append(cleaned_quarter)

            # Extract annual earnings
            annual = data.get("annualEarnings", [])
            cleaned_annual = []

            for year in annual:
                cleaned_year = {}
                for key, value in year.items():
                    if value:
                        try:
                            if '.' in str(value):
                                cleaned_year[key] = Decimal(value)
                            else:
                                cleaned_year[key] = int(value)
                        except (InvalidOperation, ValueError):
                            cleaned_year[key] = value
                    else:
                        cleaned_year[key] = value
                cleaned_annual.append(cleaned_year)

            result = {
                "quarterly": cleaned_quarterly,
                "annual": cleaned_annual
            }

            # Cache the result
            self.cache_manager.set(cache_key, result, settings.alpha_vantage_metadata_cache_ttl)

            logger.info(f"Fetched earnings data for {symbol}")
            return result

        except Exception as e:
            logger.error(f"Error fetching earnings data for {symbol}: {str(e)}")
            raise

    def fetch_news_sentiment(self, symbol: str, limit: int = 50) -> List[Dict]:
        """Fetch news sentiment data for a symbol."""
        cache_key = f"{self.news_cache_key}:sentiment:{symbol}:{limit}"
        cached_data = self.cache_manager.get(cache_key)

        if cached_data:
            logger.debug(f"Cache hit for news sentiment: {symbol}")
            return cached_data

        try:
            data = self._make_api_request(
                "NEWS_SENTIMENT",
                symbol,
                limit=limit
            )

            feed = data.get("feed", [])
            cleaned_feed = []

            for article in feed:
                cleaned_article = {
                    "title": article.get("title"),
                    "url": article.get("url"),
                    "source": article.get("source"),
                    "time": article.get("time"),
                    "summary": article.get("summary"),
                    "banner_image": article.get("banner_image"),
                    "topics": article.get("topics", []),
                    "overall_sentiment_score": article.get("overall_sentiment_score"),
                    "overall_sentiment_label": article.get("overall_sentiment_label")
                }
                cleaned_feed.append(cleaned_article)

            # Cache the result
            self.cache_manager.set(cache_key, cleaned_feed, settings.alpha_vantage_news_cache_ttl)

            logger.info(f"Fetched {len(cleaned_feed)} news articles for {symbol}")
            return cleaned_feed

        except Exception as e:
            logger.error(f"Error fetching news sentiment for {symbol}: {str(e)}")
            raise

    def fetch_latest_price(self, symbol: str) -> Optional[Dict]:
        """Fetch latest price data for a symbol."""
        try:
            daily_data = self.fetch_daily_data(symbol, outputsize="compact")
            if daily_data:
                latest = daily_data[0]  # Most recent is first
                return {
                    "symbol": symbol,
                    "price": latest["close"],
                    "change": latest["close"] - latest["open"],
                    "change_percent": ((latest["close"] - latest["open"]) / latest["open"] * 100) if latest["open"] != 0 else 0,
                    "volume": latest["volume"],
                    "timestamp": latest["date"]
                }
            return None
        except Exception as e:
            logger.error(f"Error fetching latest price for {symbol}: {str(e)}")
            return None

    def get_daily_usage(self) -> Dict[str, int]:
        """Get current daily API usage statistics."""
        return {
            "minute_calls": self.rate_limiter.minute_calls,
            "minute_limit": settings.alpha_vantage_requests_per_minute,
            "day_calls": self.rate_limiter.day_calls,
            "day_limit": settings.alpha_vantage_requests_per_day
        }

    def clear_cache(self) -> None:
        """Clear all Alpha Vantage cache entries."""
        pattern = f"{self.price_cache_key}:*"
        self.cache_manager.clear_pattern(pattern)

        pattern = f"{self.news_cache_key}:*"
        self.cache_manager.clear_pattern(pattern)

        pattern = f"{self.metadata_cache_key}:*"
        self.cache_manager.clear_pattern(pattern)

        logger.info("Alpha Vantage cache cleared")


# Global client instance
_alpha_vantage_client = None


def get_alpha_vantage_client() -> AlphaVantageClient:
    """Get the global Alpha Vantage client instance."""
    global _alpha_vantage_client
    if _alpha_vantage_client is None:
        _alpha_vantage_client = AlphaVantageClient()
    return _alpha_vantage_client


def is_alpha_vantage_available() -> bool:
    """Check if Alpha Vantage is configured and available."""
    return settings.alpha_vantage_enabled and bool(settings.alpha_vantage_api_key)