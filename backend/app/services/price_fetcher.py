"""
Price fetcher service for Yahoo Finance and CoinGecko APIs.

From PRD Section 3 - Data Sources and Section 4.5 - Price Updates.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
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

    # CoinGecko free tier: 50 calls/minute
    COINGECKO_API_URL = "https://api.coingecko.com/api/v3"
    COINGECKO_RATE_LIMIT_DELAY = 1.5  # seconds between requests

    # Real-time price fetching configuration
    REALTIME_RATE_LIMIT_DELAY = 0.15  # seconds between Yahoo Finance requests
    REALTIME_CACHE_TTL = 30  # seconds
    REALTIME_MAX_WORKERS = 5  # concurrent threads for batch fetching

    def __init__(self):
        """Initialize price fetcher with real-time cache."""
        self._realtime_cache = RealtimePriceCache(ttl_seconds=self.REALTIME_CACHE_TTL)

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

    @staticmethod
    async def fetch_crypto_price(ticker: str) -> Optional[Dict[str, Decimal]]:
        """
        Fetch current price for cryptocurrency from CoinGecko.

        Args:
            ticker: Crypto symbol (e.g., BTC, ETH)

        Returns:
            Dict with price data or None
        """
        try:
            # Map common ticker symbols to CoinGecko IDs
            coin_id = PriceFetcher._map_ticker_to_coingecko_id(ticker)

            headers = {}
            if settings.coingecko_api_key:
                headers["x-cg-pro-api-key"] = settings.coingecko_api_key

            # Fetch current price
            url = f"{PriceFetcher.COINGECKO_API_URL}/simple/price"
            params = {
                "ids": coin_id,
                "vs_currencies": "eur,usd",
                "include_24hr_vol": "true",
                "include_24hr_change": "true"
            }

            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()

            data = response.json()

            if coin_id not in data:
                logger.warning(f"No price data for {ticker} ({coin_id}) from CoinGecko")
                return None

            price_data = data[coin_id]
            close_price = Decimal(str(price_data.get("eur", 0)))

            # CoinGecko doesn't provide OHLC for current day in free tier
            # Use close price for all OHLC values
            return {
                "open": close_price,
                "high": close_price,
                "low": close_price,
                "close": close_price,
                "volume": int(price_data.get("eur_24h_vol", 0)),
                "source": "coingecko"
            }

        except requests.RequestException as e:
            logger.error(f"Error fetching price for {ticker} from CoinGecko: {str(e)}")
            return None
        except (KeyError, ValueError) as e:
            logger.error(f"Error parsing CoinGecko response for {ticker}: {str(e)}")
            return None

    @staticmethod
    async def fetch_historical_prices(
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
            return await PriceFetcher._fetch_crypto_historical(ticker, start_date, end_date)
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

    @staticmethod
    async def _fetch_crypto_historical(
        ticker: str,
        start_date: date,
        end_date: date
    ) -> List[Dict]:
        """Fetch historical crypto prices from CoinGecko."""
        try:
            coin_id = PriceFetcher._map_ticker_to_coingecko_id(ticker)

            headers = {}
            if settings.coingecko_api_key:
                headers["x-cg-pro-api-key"] = settings.coingecko_api_key

            # CoinGecko historical data endpoint
            url = f"{PriceFetcher.COINGECKO_API_URL}/coins/{coin_id}/market_chart/range"

            # Convert dates to UNIX timestamps
            from_timestamp = int(datetime.combine(start_date, datetime.min.time()).timestamp())
            to_timestamp = int(datetime.combine(end_date, datetime.max.time()).timestamp())

            params = {
                "vs_currency": "eur",
                "from": from_timestamp,
                "to": to_timestamp
            }

            # Rate limiting for free tier
            sleep(PriceFetcher.COINGECKO_RATE_LIMIT_DELAY)

            response = requests.get(url, params=params, headers=headers, timeout=30)
            response.raise_for_status()

            data = response.json()
            prices_data = data.get("prices", [])

            prices = []
            for timestamp, price in prices_data:
                price_date = datetime.fromtimestamp(timestamp / 1000).date()
                price_decimal = Decimal(str(price))

                prices.append({
                    "date": price_date,
                    "open": price_decimal,
                    "high": price_decimal,
                    "low": price_decimal,
                    "close": price_decimal,
                    "volume": 0,  # Not available in this endpoint
                    "source": "coingecko"
                })

            return prices

        except Exception as e:
            logger.error(f"Error fetching historical crypto data for {ticker}: {str(e)}")
            return []

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

        # Detect if crypto (simple heuristic)
        is_crypto = ticker.upper() in ["BTC", "ETH", "USDT", "BNB", "SOL", "XRP",
                                        "ADA", "DOGE", "DOT", "MATIC", "SHIB",
                                        "AVAX", "LINK", "UNI", "ATOM"]

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

        # Detect if crypto (simple heuristic)
        is_crypto = ticker.upper() in ["BTC", "ETH", "USDT", "BNB", "SOL", "XRP",
                                        "ADA", "DOGE", "DOT", "MATIC", "SHIB",
                                        "AVAX", "LINK", "UNI", "ATOM"]

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
        Fetch near real-time price for a single ticker using yfinance.

        Uses fast_info for quick intraday price retrieval.
        Results are cached for 30 seconds to reduce API load.

        Args:
            ticker: Stock ticker symbol (broker format)
            isin: Optional ISIN code for ticker resolution

        Returns:
            Dict with keys: ticker, isin, current_price, previous_close,
                          change_amount, change_percent, timestamp
            None if price cannot be fetched
        """
        # Check cache first
        cache_key = f"{ticker}:{isin or 'none'}"
        cached = self._realtime_cache.get(cache_key)
        if cached:
            return cached

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
                "timestamp": datetime.utcnow()
            }

            # Cache the result
            self._realtime_cache.set(cache_key, result)

            # Rate limiting
            sleep(self.REALTIME_RATE_LIMIT_DELAY)

            return result

        except Exception as e:
            logger.error(f"Error fetching real-time price for {ticker}: {str(e)}")
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

    @staticmethod
    def _map_ticker_to_coingecko_id(ticker: str) -> str:
        """
        Map common ticker symbols to CoinGecko IDs.

        Args:
            ticker: Ticker symbol

        Returns:
            CoinGecko ID
        """
        # Common mappings
        ticker_map = {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "USDT": "tether",
            "BNB": "binancecoin",
            "SOL": "solana",
            "XRP": "ripple",
            "ADA": "cardano",
            "DOGE": "dogecoin",
            "DOT": "polkadot",
            "MATIC": "matic-network",
            "SHIB": "shiba-inu",
            "AVAX": "avalanche-2",
            "LINK": "chainlink",
            "UNI": "uniswap",
            "ATOM": "cosmos",
        }

        return ticker_map.get(ticker.upper(), ticker.lower())
