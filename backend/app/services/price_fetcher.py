"""
Price fetcher service for Yahoo Finance API.

From PRD Section 3 - Data Sources and Section 4.5 - Price Updates.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
import logging
import yfinance as yf
from time import sleep
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

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
    """Fetch prices from Yahoo Finance API."""

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
        Fetch the latest OHLCV price for a stock or ETF from Yahoo Finance.
        
        Parameters:
            ticker (str): The Yahoo Finance ticker symbol to query.
        
        Returns:
            Optional[Dict[str, Decimal | int | str]]: A dictionary with keys:
                - `open` (Decimal): Opening price for the latest trading period.
                - `high` (Decimal): Highest price for the latest trading period.
                - `low` (Decimal): Lowest price for the latest trading period.
                - `close` (Decimal): Closing price for the latest trading period.
                - `volume` (int): Traded volume for the latest trading period.
                - `source` (str): Data source identifier (always "yahoo").
            Returns `None` if no data is available or an error occurs.
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
    async def fetch_historical_prices(
        ticker: str,
        start_date: date,
        end_date: date
    ) -> List[Dict]:
        """
        Retrieve historical OHLCV price records for the given ticker between start_date and end_date.
        
        Parameters:
            ticker (str): Asset ticker symbol to fetch.
            start_date (date): Inclusive start date for the historical range.
            end_date (date): Inclusive end date for the historical range.
        
        Returns:
            List[Dict]: A list of price records, each containing keys `date`, `open`, `high`, `low`, `close`, `volume`, and `source`; returns an empty list if no data is available or on failure.
        """
        return await PriceFetcher._fetch_stock_historical(ticker, start_date, end_date)

    @staticmethod
    async def _fetch_stock_historical(
        ticker: str,
        start_date: date,
        end_date: date
    ) -> List[Dict]:
        """
        Retrieve historical OHLCV records for a ticker between two dates.
        
        Parameters:
            ticker (str): Ticker symbol to query on Yahoo Finance.
            start_date (date): Inclusive start date for the historical range.
            end_date (date): Exclusive end date for the historical range.
        
        Returns:
            List[Dict]: A list of price records. Each record contains:
                - `date` (date): The trading date.
                - `open` (Decimal): Opening price.
                - `high` (Decimal): Highest price.
                - `low` (Decimal): Lowest price.
                - `close` (Decimal): Closing price.
                - `volume` (int): Traded volume.
                - `source` (str): Data source identifier ("yahoo").
            Returns an empty list if no data is available or an error occurs.
        """
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
    async def fetch_fx_rate(base: str = "EUR", quote: str = "USD") -> Optional[Decimal]:
        """
        Fetch the FX exchange rate for a currency pair from Yahoo Finance.
        
        Parameters:
        	base (str): Base currency code (default "EUR").
        	quote (str): Quote currency code (default "USD").
        
        Returns:
        	Decimal: Exchange rate expressing how many units of `quote` equal one unit of `base` (e.g., 1.10 for EUR/USD), or `None` if the rate is unavailable.
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

        If ISIN is provided, resolves to correct Yahoo Finance ticker.

        Args:
            ticker: Asset ticker symbol (broker format)
            isin: Optional ISIN code for ticker resolution

        Returns:
            Dict with OHLCV data or None
        """
        try:
            # Resolve ticker using ISIN if provided
            resolved_ticker = TickerMapper.resolve_ticker(ticker, isin) if isin else ticker
            logger.info(f"Fetching price for {ticker} (resolved: {resolved_ticker})")
            
            # Check if we're in an async context
            try:
                loop = asyncio.get_running_loop()
                # We're in an async context - use run_coroutine_threadsafe or create new loop
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(
                    lambda: asyncio.run(self.fetch_stock_price(resolved_ticker))
                    ).result()
            except RuntimeError:
                # No running loop - safe to use asyncio.run
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

        If ISIN is provided, resolves to correct Yahoo Finance ticker.
        Calls yfinance directly without going through async methods.

        Args:
            ticker: Asset ticker symbol (broker format)
            isin: Optional ISIN code for ticker resolution
            start_date: Start date for historical data
            end_date: End date for historical data

        Returns:
            List of price dictionaries with keys: date, open, high, low, close, volume, source
        """
        try:
            # Resolve ticker using ISIN if provided
            resolved_ticker = TickerMapper.resolve_ticker(ticker, isin) if isin else ticker
            logger.info(f"Fetching historical prices for {ticker} (resolved: {resolved_ticker})")

            # Fetch directly from yfinance (synchronous)
            stock = yf.Ticker(resolved_ticker)
            hist = stock.history(start=start_date, end=end_date)

            if hist.empty:
                logger.warning(f"No historical data for {resolved_ticker}")
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
        
        Parameters:
            tickers (List[Tuple[str, Optional[str]]]): List of (ticker, isin) pairs to fetch.
        
        Returns:
            List[Dict]: Price dictionaries for tickers that were successfully fetched.
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

    