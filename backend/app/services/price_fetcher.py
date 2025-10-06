"""
Price fetcher service for Yahoo Finance and CoinGecko APIs.

From PRD Section 3 - Data Sources and Section 4.5 - Price Updates.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, ClassVar
import logging
import yfinance as yf
import requests
from time import sleep
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from app.config import settings
from app.services.ticker_mapper import TickerMapper

logger = logging.getLogger(__name__)


class RealtimePriceCache:
    """Simple in-memory cache for real-time prices with 30-second TTL."""

    def __init__(self, ttl_seconds: int = 30):
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Tuple[Dict, datetime]] = {}
        self._lock = threading.Lock()

    def get(self, ticker: str) -> Optional[Dict]:
        """Get cached price if not expired."""
        with self._lock:
            if ticker in self._cache:
                price_data, timestamp = self._cache[ticker]
                age = (datetime.utcnow() - timestamp).total_seconds()
                if age < self.ttl_seconds:
                    logger.debug(f"Cache hit for {ticker} (age: {age:.1f}s)")
                    return price_data
                else:
                    logger.debug(f"Cache expired for {ticker} (age: {age:.1f}s)")
                    del self._cache[ticker]
        return None

    def set(self, ticker: str, price_data: Dict) -> None:
        """Store price data in cache."""
        with self._lock:
            self._cache[ticker] = (price_data, datetime.utcnow())
            logger.debug(f"Cached price for {ticker}")

    def clear(self) -> None:
        """Clear all cached data."""
        with self._lock:
            self._cache.clear()
            logger.debug("Price cache cleared")


class PriceFetcher:
    """Fetch prices from Yahoo Finance and CoinGecko APIs."""

    # CoinGecko API configuration
    COINGECKO_API_URL = "https://api.coingecko.com/api/v3"
    COINGECKO_RATE_LIMIT_DELAY = 1.5  # seconds between requests (free tier: ~50 calls/minute)
    COINGECKO_RATE_LIMIT_DELAY_PREMIUM = 0.5  # seconds between requests (premium tier)
    COINGECKO_MAX_RETRIES = 3  # Maximum retry attempts
    COINGECKO_RETRY_BACKOFF = 2  # Backoff multiplier
    COINGECKO_TIMEOUT = 30  # seconds for API requests

    # Real-time price fetching configuration
    REALTIME_RATE_LIMIT_DELAY = 0.15  # seconds between Yahoo Finance requests
    REALTIME_CACHE_TTL = 30  # seconds
    REALTIME_MAX_WORKERS = 5  # concurrent threads for batch fetching

    def __init__(self):
        """Initialize price fetcher with real-time cache."""
        self._realtime_cache = RealtimePriceCache(ttl_seconds=self.REALTIME_CACHE_TTL)
        # Adjust rate limiting based on whether we have an API key
        self._crypto_delay = (
            self.COINGECKO_RATE_LIMIT_DELAY_PREMIUM
            if settings.coingecko_api_key
            else self.COINGECKO_RATE_LIMIT_DELAY
        )

    def _make_coingecko_request(
        self,
        url: str,
        params: Optional[Dict] = None,
        timeout: Optional[int] = None
    ) -> requests.Response:
        """
        Make a request to CoinGecko API with retry logic and rate limiting.

        Args:
            url: API endpoint URL
            params: Query parameters
            timeout: Request timeout in seconds

        Returns:
            requests.Response object

        Raises:
            requests.RequestException: If request fails after all retries
        """
        headers = {}
        if settings.coingecko_api_key:
            headers["x-cg-pro-api-key"] = settings.coingecko_api_key

        if timeout is None:
            timeout = self.COINGECKO_TIMEOUT

        for attempt in range(self.COINGECKO_MAX_RETRIES):
            try:
                # Apply rate limiting
                if attempt > 0:
                    # Exponential backoff for retries
                    delay = self._crypto_delay * (self.COINGECKO_RETRY_BACKOFF ** (attempt - 1))
                    logger.debug(f"CoinGecko retry {attempt + 1}, waiting {delay:.1f}s")
                    sleep(delay)
                else:
                    sleep(self._crypto_delay)

                response = requests.get(url, params=params, headers=headers, timeout=timeout)

                # Check for rate limiting (HTTP 429)
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    logger.warning(f"CoinGecko rate limit hit, waiting {retry_after}s")
                    sleep(retry_after)
                    continue

                response.raise_for_status()
                return response

            except requests.exceptions.Timeout:
                logger.warning(f"CoinGecko request timeout (attempt {attempt + 1})")
                if attempt == self.COINGECKO_MAX_RETRIES - 1:
                    raise
                continue

            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    # Not found - don't retry
                    raise
                elif e.response.status_code >= 500:
                    # Server error - retry
                    logger.warning(f"CoinGecko server error {e.response.status_code} (attempt {attempt + 1})")
                    if attempt == self.COINGECKO_MAX_RETRIES - 1:
                        raise
                    continue
                else:
                    # Client error - don't retry
                    raise

            except requests.exceptions.RequestException as e:
                logger.warning(f"CoinGecko request error (attempt {attempt + 1}): {str(e)}")
                if attempt == self.COINGECKO_MAX_RETRIES - 1:
                    raise
                continue

        raise requests.RequestException("All retry attempts exhausted")

    @staticmethod
    async def fetch_stock_price(ticker: str) -> Optional[Dict[str, Decimal]]:
        """
        Fetch current price for stock/ETF from Yahoo Finance.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dict with price data (open, high, low, close, volume) or None
        """
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1d")

            if hist.empty:
                logger.warning(f"No price data for {ticker} from Yahoo Finance")
                return None

            latest = hist.iloc[-1]

            return {
                "open": Decimal(str(latest["Open"])),
                "high": Decimal(str(latest["High"])),
                "low": Decimal(str(latest["Low"])),
                "close": Decimal(str(latest["Close"])),
                "volume": int(latest["Volume"]),
                "source": "yahoo"
            }

        except Exception as e:
            logger.error(f"Error fetching price for {ticker} from Yahoo Finance: {str(e)}")
            return None

    async def fetch_crypto_price(self, ticker: str, currency: str = "EUR") -> Optional[Dict[str, Decimal]]:
        """
        Fetch current price for cryptocurrency from CoinGecko with OHLCV data.

        Args:
            ticker: Crypto symbol (e.g., BTC, ETH)
            currency: Target currency (EUR or USD)

        Returns:
            Dict with price data (open, high, low, close, volume) or None
        """
        try:
            coin_id = PriceFetcher._map_ticker_to_coingecko_id(ticker)

            # First, fetch basic price data using the robust request method
            simple_url = f"{PriceFetcher.COINGECKO_API_URL}/simple/price"
            simple_params = {
                "ids": coin_id,
                "vs_currencies": "eur,usd",
                "include_24hr_vol": "true",
                "include_24hr_change": "true",
                "include_market_cap": "true"
            }

            response = self._make_coingecko_request(simple_url, simple_params, timeout=10)

            data = response.json()

            if coin_id not in data:
                logger.warning(f"No price data for {ticker} ({coin_id}) from CoinGecko")
                return None

            price_data = data[coin_id]
            close_price = Decimal(str(price_data.get(f"{currency.lower()}", 0)))
            volume_24h = Decimal(str(price_data.get(f"{currency.lower()}_24h_vol", 0)))
            change_24h = Decimal(str(price_data.get(f"{currency.lower()}_24h_change", 0)))

            # Try to get OHLC data for the current day (premium feature)
            # For free tier, we'll estimate OHLC from yesterday's data and current price
            ohlc_url = f"{PriceFetcher.COINGECKO_API_URL}/coins/{coin_id}/ohlc"
            ohlc_params = {
                "vs_currency": currency.lower(),
                "days": 2  # Get yesterday and today's data
            }

            ohlc_data = None

            # Handle OHLC request separately as it's optional
            try:
                ohlc_response = self._make_coingecko_request(ohlc_url, ohlc_params, timeout=10)
            except requests.RequestException as e:
                logger.debug(f"Could not fetch OHLC data for {ticker}: {str(e)}")
                ohlc_response = None

            if ohlc_response:
                ohlc_json = ohlc_response.json()
                if ohlc_json:
                    # Get the most recent OHLC data (today's data if available)
                    latest_ohlc = ohlc_json[-1] if ohlc_json else None
                    if latest_ohlc and len(latest_ohlc) >= 5:
                        ohlc_data = {
                            "open": Decimal(str(latest_ohlc[1])),
                            "high": Decimal(str(latest_ohlc[2])),
                            "low": Decimal(str(latest_ohlc[3])),
                            "close": Decimal(str(latest_ohlc[4]))
                        }

            # If OHLC data is not available or incomplete, use current price for all values
            if not ohlc_data:
                ohlc_data = {
                    "open": close_price,
                    "high": close_price,
                    "low": close_price,
                    "close": close_price
                }

            return {
                "open": ohlc_data["open"],
                "high": ohlc_data["high"],
                "low": ohlc_data["low"],
                "close": ohlc_data["close"],
                "volume": int(volume_24h),
                "change_24h": change_24h,
                "source": "coingecko",
                "currency": currency.upper()
            }

        except requests.RequestException as e:
            logger.error(f"Error fetching price for {ticker} from CoinGecko: {str(e)}")
            return None
        except (KeyError, ValueError) as e:
            logger.error(f"Error parsing CoinGecko response for {ticker}: {str(e)}")
            return None

    async def fetch_historical_prices(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
        is_crypto: bool = False
    ) -> List[Dict]:
        """
        Fetch historical price data.

        Args:
            ticker: Asset ticker symbol
            start_date: Start date
            end_date: End date
            is_crypto: Whether ticker is cryptocurrency

        Returns:
            List of price dictionaries
        """
        if is_crypto:
            return await self._fetch_crypto_historical(ticker, start_date, end_date)
        else:
            return await PriceFetcher._fetch_stock_historical(ticker, start_date, end_date)

    @staticmethod
    async def _fetch_stock_historical(
        ticker: str,
        start_date: date,
        end_date: date
    ) -> List[Dict]:
        """Fetch historical stock prices from Yahoo Finance."""
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(start=start_date, end=end_date)

            if hist.empty:
                logger.warning(f"No historical data for {ticker}")
                return []

            prices = []
            for idx, row in hist.iterrows():
                prices.append({
                    "date": idx.date(),
                    "open": Decimal(str(row["Open"])),
                    "high": Decimal(str(row["High"])),
                    "low": Decimal(str(row["Low"])),
                    "close": Decimal(str(row["Close"])),
                    "volume": int(row["Volume"]),
                    "source": "yahoo"
                })

            return prices

        except Exception as e:
            logger.error(f"Error fetching historical data for {ticker}: {str(e)}")
            return []

    async def _fetch_crypto_historical(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
        currency: str = "EUR"
    ) -> List[Dict]:
        """Fetch historical crypto prices from CoinGecko with OHLCV data."""
        try:
            coin_id = PriceFetcher._map_ticker_to_coingecko_id(ticker)

            # CoinGecko market chart range endpoint for prices and volumes
            url = f"{PriceFetcher.COINGECKO_API_URL}/coins/{coin_id}/market_chart/range"

            # Convert dates to UNIX timestamps
            from_timestamp = int(datetime.combine(start_date, datetime.min.time()).timestamp())
            to_timestamp = int(datetime.combine(end_date, datetime.max.time()).timestamp())

            params = {
                "vs_currency": currency.lower(),
                "from": from_timestamp,
                "to": to_timestamp
            }

            response = self._make_coingecko_request(url, params, timeout=30)
            data = response.json()
            prices_data = data.get("prices", [])
            volumes_data = data.get("total_volumes", [])

            # Create a map of timestamps to volumes for easier lookup
            volume_map = {timestamp: volume for timestamp, volume in volumes_data}

            prices = []
            for timestamp, price in prices_data:
                price_date = datetime.fromtimestamp(timestamp / 1000).date()
                price_decimal = Decimal(str(price))
                volume_decimal = Decimal(str(volume_map.get(timestamp, 0)))

                prices.append({
                    "date": price_date,
                    "open": price_decimal,
                    "high": price_decimal,
                    "low": price_decimal,
                    "close": price_decimal,
                    "volume": int(volume_decimal),
                    "source": "coingecko",
                    "currency": currency.upper()
                })

            # For better OHLC data, try to get daily OHLC if the date range is not too long
            if (end_date - start_date).days <= 365:  # Limit to 1 year for OHLC data
                try:
                    ohlc_url = f"{PriceFetcher.COINGECKO_API_URL}/coins/{coin_id}/ohlc"
                    ohlc_params = {
                        "vs_currency": currency.lower(),
                        "days": min(365, (end_date - start_date).days + 30)  # Get some buffer days
                    }

                    ohlc_response = self._make_coingecko_request(ohlc_url, ohlc_params, timeout=30)

                    if ohlc_response:
                        ohlc_data = ohlc_response.json()

                        # Create a map of dates to OHLC data
                        ohlc_map = {}
                        for timestamp, open_price, high_price, low_price, close_price in ohlc_data:
                            date_key = datetime.fromtimestamp(timestamp / 1000).date()
                            if start_date <= date_key <= end_date:
                                ohlc_map[date_key] = {
                                    "open": Decimal(str(open_price)),
                                    "high": Decimal(str(high_price)),
                                    "low": Decimal(str(low_price)),
                                    "close": Decimal(str(close_price))
                                }

                        # Update price data with OHLC values
                        for price_entry in prices:
                            date_key = price_entry["date"]
                            if date_key in ohlc_map:
                                price_entry.update(ohlc_map[date_key])

                except Exception as e:
                    logger.debug(f"Could not fetch OHLC data for {ticker}: {str(e)}")
                    # Continue with basic price data if OHLC fetch fails

            return sorted(prices, key=lambda x: x["date"])

        except Exception as e:
            logger.error(f"Error fetching historical crypto data for {ticker}: {str(e)}")
            return []

    async def fetch_crypto_conversion_rate(
        self,
        from_crypto: str,
        to_crypto: str,
        currency: str = "USD"
    ) -> Optional[Decimal]:
        """
        Fetch conversion rate between two cryptocurrencies.

        Useful for getting crypto-to-crypto prices (e.g., BTC/ETH).

        Args:
            from_crypto: Source crypto ticker (e.g., BTC, ETH)
            to_crypto: Target crypto ticker (e.g., ETH, USDT)
            currency: Base currency for calculation (USD or EUR)

        Returns:
            Conversion rate as Decimal or None
        """
        try:
            if not (self.is_crypto_ticker(from_crypto) and self.is_crypto_ticker(to_crypto)):
                logger.warning(f"Both tickers must be cryptocurrencies: {from_crypto} -> {to_crypto}")
                return None

            from_coin_id = self._map_ticker_to_coingecko_id(from_crypto)
            to_coin_id = self._map_ticker_to_coingecko_id(to_crypto)

            # Fetch prices for both cryptos in the same currency
            url = f"{self.COINGECKO_API_URL}/simple/price"
            params = {
                "ids": f"{from_coin_id},{to_coin_id}",
                "vs_currencies": currency.lower(),
                "include_24hr_change": "false",
                "include_24hr_vol": "false"
            }

            response = self._make_coingecko_request(url, params, timeout=10)
            data = response.json()

            if from_coin_id not in data or to_coin_id not in data:
                logger.warning(f"Missing price data for crypto conversion: {from_crypto} -> {to_crypto}")
                return None

            from_price = Decimal(str(data[from_coin_id].get(currency.lower(), 0)))
            to_price = Decimal(str(data[to_coin_id].get(currency.lower(), 0)))

            if from_price == 0 or to_price == 0:
                logger.warning(f"Zero price encountered for crypto conversion: {from_crypto} -> {to_crypto}")
                return None

            # Calculate conversion rate: how many units of to_crypto equals 1 unit of from_crypto
            conversion_rate = from_price / to_price

            logger.info(f"Crypto conversion rate {from_crypto}/{to_crypto}: {conversion_rate}")

            return conversion_rate

        except Exception as e:
            logger.error(f"Error fetching crypto conversion rate {from_crypto} -> {to_crypto}: {str(e)}")
            return None

    @staticmethod
    async def fetch_fx_rate(base: str = "EUR", quote: str = "USD") -> Optional[Decimal]:
        """
        Fetch currency exchange rate from Yahoo Finance.

        Args:
            base: Base currency (default: EUR)
            quote: Quote currency (default: USD)

        Returns:
            Exchange rate (e.g., 1.10 for EUR/USD) or None
        """
        try:
            # Yahoo Finance FX ticker format: EURUSD=X
            fx_ticker = f"{base}{quote}=X"
            fx_data = yf.Ticker(fx_ticker)
            hist = fx_data.history(period="1d")

            if hist.empty:
                logger.warning(f"No FX rate data for {fx_ticker}")
                return None

            rate = Decimal(str(hist.iloc[-1]["Close"]))
            logger.info(f"Fetched FX rate {fx_ticker}: {rate}")

            return rate

        except Exception as e:
            logger.error(f"Error fetching FX rate {base}/{quote}: {str(e)}")
            return None

    def fetch_latest_price(self, ticker: str, isin: Optional[str] = None) -> Optional[Dict]:
        """
        Synchronous wrapper to fetch latest price (for Celery tasks).

        Automatically detects if ticker is crypto and uses appropriate API.
        If ISIN is provided, resolves to correct Yahoo Finance ticker.

        Args:
            ticker: Asset ticker symbol (broker format)
            isin: Optional ISIN code for ticker resolution

        Returns:
            Dict with OHLCV data or None
        """
        import asyncio

        # Detect if crypto using comprehensive mapping
        is_crypto = PriceFetcher.is_crypto_ticker(ticker)

        try:
            if is_crypto:
                return asyncio.run(self.fetch_crypto_price(ticker))
            else:
                # Resolve ticker using ISIN if provided
                resolved_ticker = TickerMapper.resolve_ticker(ticker, isin)
                logger.info(f"Fetching price for {ticker} (resolved: {resolved_ticker})")
                return asyncio.run(self.fetch_stock_price(resolved_ticker))
        except Exception as e:
            logger.error(f"Error fetching latest price for {ticker}: {str(e)}")
            return None

    def fetch_historical_prices_sync(
        self,
        ticker: str,
        isin: Optional[str] = None,
        start_date: date = None,
        end_date: date = None
    ) -> List[Dict]:
        """
        Synchronous wrapper to fetch historical prices (for Celery tasks).

        Automatically detects if ticker is crypto and uses appropriate API.
        If ISIN is provided, resolves to correct Yahoo Finance ticker.

        Args:
            ticker: Asset ticker symbol (broker format)
            isin: Optional ISIN code for ticker resolution
            start_date: Start date for historical data
            end_date: End date for historical data

        Returns:
            List of price dictionaries with keys: date, open, high, low, close, volume, source
        """
        import asyncio

        # Detect if crypto using comprehensive mapping
        is_crypto = PriceFetcher.is_crypto_ticker(ticker)

        try:
            if is_crypto:
                return asyncio.run(
                    self.fetch_historical_prices(ticker, start_date, end_date, is_crypto=True)
                )
            else:
                # Resolve ticker using ISIN if provided
                resolved_ticker = TickerMapper.resolve_ticker(ticker, isin) if isin else ticker
                logger.info(f"Fetching historical prices for {ticker} (resolved: {resolved_ticker})")
                return asyncio.run(
                    self.fetch_historical_prices(resolved_ticker, start_date, end_date, is_crypto=False)
                )
        except Exception as e:
            logger.error(f"Error fetching historical prices for {ticker}: {str(e)}")
            return []

    def fetch_realtime_price(self, ticker: str, isin: Optional[str] = None) -> Optional[Dict]:
        """
        Fetch near real-time price for a single ticker.

        Supports both stocks/ETFs (via Yahoo Finance) and cryptocurrencies (via CoinGecko).
        Results are cached for 30 seconds to reduce API load.

        Args:
            ticker: Asset ticker symbol (broker format)
            isin: Optional ISIN code for ticker resolution

        Returns:
            Dict with keys: ticker, isin, current_price, previous_close,
                          change_amount, change_percent, timestamp, source
            None if price cannot be fetched
        """
        # Check cache first
        cache_key = f"{ticker}:{isin or 'none'}"
        cached = self._realtime_cache.get(cache_key)
        if cached:
            return cached

        try:
            # Detect if crypto using comprehensive mapping
            is_crypto = PriceFetcher.is_crypto_ticker(ticker)

            if is_crypto:
                return self._fetch_realtime_crypto_price(ticker, isin, cache_key)
            else:
                return self._fetch_realtime_stock_price(ticker, isin, cache_key)

        except Exception as e:
            logger.error(f"Error fetching real-time price for {ticker}: {str(e)}")
            return None

    def _fetch_realtime_stock_price(self, ticker: str, isin: Optional[str], cache_key: str) -> Optional[Dict]:
        """Fetch real-time price for stocks/ETFs using Yahoo Finance."""
        try:
            # Resolve ticker using ISIN if provided
            resolved_ticker = TickerMapper.resolve_ticker(ticker, isin) if isin else ticker
            logger.info(f"Fetching real-time price for {ticker} (resolved: {resolved_ticker})")

            # Use yfinance Ticker.fast_info for quick access
            stock = yf.Ticker(resolved_ticker)

            # Try to get current price from fast_info
            try:
                current_price = stock.fast_info.get('lastPrice')
                previous_close = stock.fast_info.get('previousClose')
            except Exception:
                # Fallback to regular history if fast_info fails
                logger.debug(f"fast_info failed for {resolved_ticker}, falling back to history")
                hist = stock.history(period="1d", interval="1m")
                if hist.empty:
                    logger.warning(f"No real-time data for {resolved_ticker}")
                    return None
                current_price = float(hist['Close'].iloc[-1])
                # Get previous close from info
                info = stock.info
                previous_close = info.get('previousClose', info.get('regularMarketPreviousClose'))

            if current_price is None or previous_close is None:
                logger.warning(f"Missing price data for {resolved_ticker}")
                return None

            # Convert to Decimal
            current_price = Decimal(str(current_price))
            previous_close = Decimal(str(previous_close))

            # Calculate change
            change_amount = current_price - previous_close
            change_percent = (change_amount / previous_close * 100) if previous_close != 0 else Decimal("0")

            result = {
                "ticker": ticker,
                "isin": isin,
                "current_price": current_price,
                "previous_close": previous_close,
                "change_amount": change_amount,
                "change_percent": change_percent,
                "timestamp": datetime.utcnow(),
                "source": "yahoo"
            }

            # Cache the result
            self._realtime_cache.set(cache_key, result)

            # Rate limiting
            sleep(self.REALTIME_RATE_LIMIT_DELAY)

            return result

        except Exception as e:
            logger.error(f"Error fetching real-time stock price for {ticker}: {str(e)}")
            return None

    def _fetch_realtime_crypto_price(self, ticker: str, isin: Optional[str], cache_key: str) -> Optional[Dict]:
        """Fetch real-time price for cryptocurrencies using CoinGecko."""
        try:
            logger.info(f"Fetching real-time crypto price for {ticker}")

            # For crypto, ISIN is not relevant but we keep it for consistency
            coin_id = PriceFetcher._map_ticker_to_coingecko_id(ticker)

            headers = {}
            if settings.coingecko_api_key:
                headers["x-cg-pro-api-key"] = settings.coingecko_api_key

            # Fetch current price with 24h change data
            url = f"{PriceFetcher.COINGECKO_API_URL}/simple/price"
            params = {
                "ids": coin_id,
                "vs_currencies": "eur,usd",
                "include_24hr_change": "true",
                "include_24hr_vol": "true",
                "include_market_cap": "true"
            }

            response = self._make_coingecko_request(url, params, timeout=10)

            data = response.json()

            if coin_id not in data:
                logger.warning(f"No price data for {ticker} ({coin_id}) from CoinGecko")
                return None

            price_data = data[coin_id]
            current_price = Decimal(str(price_data.get("eur", 0)))
            change_24h = Decimal(str(price_data.get("eur_24h_change", 0)))
            volume_24h = Decimal(str(price_data.get("eur_24h_vol", 0)))
            market_cap = Decimal(str(price_data.get("eur_market_cap", 0)))

            if current_price == 0:
                logger.warning(f"Zero price for {ticker} from CoinGecko")
                return None

            # Calculate previous close from 24h change
            if change_24h != 0:
                previous_close = current_price / (1 + change_24h / 100)
            else:
                previous_close = current_price

            change_amount = current_price - previous_close
            change_percent = change_24h

            result = {
                "ticker": ticker,
                "isin": isin,
                "current_price": current_price,
                "previous_close": previous_close,
                "change_amount": change_amount,
                "change_percent": change_percent,
                "timestamp": datetime.utcnow(),
                "source": "coingecko",
                "volume_24h": int(volume_24h),
                "market_cap": int(market_cap)
            }

            # Cache the result
            self._realtime_cache.set(cache_key, result)

            return result

        except Exception as e:
            logger.error(f"Error fetching real-time crypto price for {ticker}: {str(e)}")
            return None

    def fetch_realtime_prices_batch(
        self,
        tickers: List[Tuple[str, Optional[str]]]
    ) -> List[Dict]:
        """
        Fetch real-time prices for multiple tickers in parallel.

        Uses ThreadPoolExecutor for concurrent fetching with rate limiting.

        Args:
            tickers: List of (ticker, isin) tuples

        Returns:
            List of price dictionaries (successful fetches only)
        """
        if not tickers:
            return []

        logger.info(f"Fetching real-time prices for {len(tickers)} tickers")

        results = []
        with ThreadPoolExecutor(max_workers=self.REALTIME_MAX_WORKERS) as executor:
            # Submit all tasks
            future_to_ticker = {
                executor.submit(self.fetch_realtime_price, ticker, isin): (ticker, isin)
                for ticker, isin in tickers
            }

            # Collect results as they complete
            for future in as_completed(future_to_ticker):
                ticker, isin = future_to_ticker[future]
                try:
                    price_data = future.result()
                    if price_data:
                        results.append(price_data)
                except Exception as e:
                    logger.error(f"Error fetching price for {ticker}: {str(e)}")

        logger.info(f"Successfully fetched {len(results)} out of {len(tickers)} real-time prices")
        return results

    # Comprehensive cryptocurrency ticker mappings
    CRYPTO_TICKER_MAP: ClassVar[Dict[str, str]] = {
        # Major cryptocurrencies
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "USDT": "tether",
        "USDC": "usd-coin",
        "BNB": "binancecoin",
        "SOL": "solana",
        "XRP": "ripple",
        "ADA": "cardano",
        "DOGE": "dogecoin",
        "DOT": "polkadot",
        "MATIC": "matic-network",

        # DeFi tokens
        "UNI": "uniswap",
        "LINK": "chainlink",
        "AAVE": "aave",
        "MKR": "maker",
        "COMP": "compound-governance-token",
        "SUSHI": "sushi",
        "CRV": "curve-dao-token",
        "YFI": "yearn-finance",
        "1INCH": "1inch",

        # Layer 2 & scaling
        "ARB": "arbitrum",
        "OP": "optimism",
        "MANTLE": "mantle",
        "LDO": "lido-dao",

        # Gaming & NFT
        "AXS": "axie-infinity",
        "SAND": "the-sandbox",
        "MANA": "decentraland",
        "ENJ": "enjincoin",
        "GALA": "gala",

        # Privacy
        "XMR": "monero",
        "ZEC": "zcash",
        "DASH": "dash",

        # Exchange tokens
        "FTT": "ftx-token",
        "CRO": "crypto-com-chain",
        "KCS": "kucoin-shares",
        "HT": "huobi-token",

        # Other popular
        "SHIB": "shiba-inu",
        "AVAX": "avalanche-2",
        "ATOM": "cosmos",
        "ALGO": "algorand",
        "VET": "vechain",
        "THETA": "theta-token",
        "FIL": "filecoin",
        "TRX": "tron",
        "ICP": "internet-computer",
        "HBAR": "hedera-hashgraph",
        "EGLD": "elrond-erd-2",
        "XTZ": "tezos",
    }

    @staticmethod
    def is_crypto_ticker(ticker: str) -> bool:
        """
        Check if a ticker symbol is a cryptocurrency.

        Args:
            ticker: Ticker symbol to check

        Returns:
            True if ticker is a known cryptocurrency
        """
        return ticker.upper() in PriceFetcher.CRYPTO_TICKER_MAP

    @staticmethod
    def _map_ticker_to_coingecko_id(ticker: str) -> str:
        """
        Map ticker symbols to CoinGecko IDs.

        Args:
            ticker: Ticker symbol

        Returns:
            CoinGecko ID or lowercased ticker if not found
        """
        return PriceFetcher.CRYPTO_TICKER_MAP.get(ticker.upper(), ticker.lower())
