"""
Enhanced PriceFetcher with crypto support using Yahoo Finance.

This module extends the existing price fetching capabilities to include
cryptocurrency data from Yahoo Finance while maintaining compatibility with
the existing portfolio tracking system.
"""
from decimal import Decimal
from datetime import date, datetime
from typing import Dict, List, Optional
import logging
import asyncio

from .price_fetcher import PriceFetcher

logger = logging.getLogger(__name__)


class UnifiedPriceFetcher:
    """
    Unified price fetcher that handles both traditional assets and cryptocurrencies.

    This class extends the existing price fetching capabilities to include
    cryptocurrency data from Yahoo Finance while maintaining compatibility with
    the existing portfolio tracking system.
    """

    def __init__(self):
        """
        Create a UnifiedPriceFetcher and initialize its internal Yahoo Finance fetcher.

        Sets self.yahoo_fetcher to a new PriceFetcher instance used for interacting with Yahoo Finance.
        """
        self.yahoo_fetcher = PriceFetcher()

    async def fetch_current_price(self, ticker: str, asset_type: str = "stock", currency: str = "eur") -> Optional[Dict]:
        """
        Fetch the current market price for a ticker, supporting stocks, ETFs, and cryptocurrencies.

        Parameters:
            ticker (str): Asset ticker symbol. For crypto provide the base symbol (e.g., "BTC"); the method will query the corresponding USD pair.
            asset_type (str): Asset category: "stock", "etf", or "crypto".
            currency (str): Target currency for the returned price, either "eur" or "usd". When "eur", USD prices are converted to EUR; on conversion failure a fallback rate is applied.

        Returns:
            dict or None: A dictionary with price data (keys vary by asset type; e.g., `"current_price"` for crypto, `"close"` for stocks/ETFs). Returns `None` if fetching fails.
        """
        try:
            if asset_type.lower() == "crypto":
                # Use Yahoo Finance for cryptocurrencies with appropriate currency suffix
                if currency.lower() == "eur":
                    yahoo_symbol = f"{ticker}-EUR"
                else:
                    yahoo_symbol = f"{ticker}-USD"
                result = await asyncio.to_thread(self.yahoo_fetcher.fetch_realtime_price, yahoo_symbol)
                if result and result.get("current_price"):
                    # Set the correct currency based on what we fetched
                    if currency.lower() == "eur":
                        result["currency"] = "EUR"
                    else:
                        result["currency"] = "USD"

                    logger.info(f"Fetched crypto price for {ticker}: {result['current_price']} {result.get('currency', 'USD')}")
                    return result
                else:
                    logger.warning(f"Failed to fetch crypto price for {ticker}")
                    return None
            else:
                # Use Yahoo Finance for stocks, ETFs, etc.
                result = self.yahoo_fetcher.fetch_latest_price(ticker)
                if result:
                    logger.info(f"Fetched stock price for {ticker}: {result['close']} USD")

                    # Convert to target currency if needed
                    if currency.lower() == "eur":
                        try:
                            eur_rate = await self.yahoo_fetcher.fetch_fx_rate("USD", "EUR")
                            if eur_rate:
                                price_eur = result['close'] * eur_rate
                                result['close'] = price_eur
                                result['currency'] = 'EUR'
                                logger.info(f"Converted to EUR: {price_eur}")
                        except Exception as e:
                            logger.warning(f"Error converting to EUR: {e}, using fallback rate")
                            # Fallback conversion
                            price_eur = result['close'] * Decimal("0.92")
                            result['close'] = price_eur
                            result['currency'] = 'EUR'

                    return result
                else:
                    logger.warning(f"Failed to fetch stock price for {ticker}")
                    return None

        except Exception as e:
            logger.error(f"Error fetching price for {ticker}: {e}")
            return None

    async def fetch_historical_prices(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
        asset_type: str = "stock",
        currency: str = "eur"
    ) -> List[Dict]:
        """
        Fetch historical price series for a ticker, optionally converting prices to EUR.

        Parameters:
            ticker (str): Asset symbol (for crypto the plain symbol, e.g. "BTC").
            start_date (date): Inclusive start date for the historical range.
            end_date (date): Inclusive end date for the historical range.
            asset_type (str): Asset category; expected values include "stock" or "crypto".
            currency (str): Target currency for returned prices, either "eur" or "usd".

        Returns:
            List[Dict]: A list of price point dictionaries. Each dictionary contains numeric
            keys 'open', 'high', 'low', 'close', a date-like 'date' (as provided by the source),
            and a 'currency' string. If conversion to EUR is requested the prices and 'currency'
            will reflect that conversion. Returns an empty list on error.
        """
        try:
            if asset_type.lower() == "crypto":
                # Use Yahoo Finance for cryptocurrencies with appropriate currency suffix
                if currency.lower() == "eur":
                    yahoo_symbol = f"{ticker}-EUR"
                else:
                    yahoo_symbol = f"{ticker}-USD"
                result = await self.yahoo_fetcher.fetch_historical_prices(yahoo_symbol, start_date=start_date, end_date=end_date)
                logger.info(f"Fetched {len(result)} crypto price points for {ticker}")

                # Set the correct currency for all price points
                if result:
                    target_currency = "EUR" if currency.lower() == "eur" else "USD"
                    for price_point in result:
                        price_point['currency'] = target_currency
                    logger.info(f"Set currency to {target_currency} for {len(result)} crypto price points")

                return result
            else:
                # Use Yahoo Finance for stocks, ETFs, etc.
                result = await self.yahoo_fetcher.fetch_historical_prices(ticker, start_date=start_date, end_date=end_date)
                logger.info(f"Fetched {len(result)} stock price points for {ticker}")

                # Convert to target currency if needed
                if currency.lower() == "eur" and result:
                    try:
                        eur_rate = await self.yahoo_fetcher.fetch_fx_rate("USD", "EUR")
                        if eur_rate:
                            for price_point in result:
                                price_point['close'] = price_point['close'] * eur_rate
                                price_point['open'] = price_point['open'] * eur_rate
                                price_point['high'] = price_point['high'] * eur_rate
                                price_point['low'] = price_point['low'] * eur_rate
                                price_point['currency'] = 'EUR'
                            logger.info(f"Converted {len(result)} price points to EUR")
                    except Exception as e:
                        logger.warning(f"Error converting to EUR: {e}, using fallback rate")
                        # Fallback conversion
                        for price_point in result:
                            price_point['close'] = price_point['close'] * Decimal("0.92")
                            price_point['open'] = price_point['open'] * Decimal("0.92")
                            price_point['high'] = price_point['high'] * Decimal("0.92")
                            price_point['low'] = price_point['low'] * Decimal("0.92")
                            price_point['currency'] = 'EUR'

                return result

        except Exception as e:
            logger.error(f"Error fetching historical prices for {ticker}: {e}")
            return []

    def detect_asset_type(self, ticker: str) -> str:
        """
        Determine the asset type for a given ticker symbol.

        Returns:
        	`crypto`, `etf`, or `stock` indicating the detected asset type. `crypto` is returned when the ticker (uppercased) matches a curated set of cryptocurrency symbols; `etf` is returned for tickers that match common ETF patterns (e.g., ending with `.L` or starting with `I`, `VTI`, `SPY`); otherwise `stock` is returned.
        """
        # Common cryptocurrency symbols (list could be expanded)
        crypto_symbols = {
            'BTC', 'ETH', 'BNB', 'XRP', 'ADA', 'SOL', 'DOGE', 'DOT', 'MATIC', 'SHIB',
            'AVAX', 'LINK', 'UNI', 'LTC', 'ATOM', 'XLM', 'BCH', 'FIL', 'TRX', 'ETC',
            'XMR', 'USDT', 'USDC', 'AAVE', 'MKR', 'COMP', 'SUSHI', 'ICP', 'HBAR',
            'VET', 'THETA', 'ALGO', 'LRC', 'ENJ', 'CRO', 'MANA', 'SAND', 'AXS',
            'GALA', 'CHZ', 'NEAR', 'EGLD', 'FTT', 'HOT', 'AR', 'STX', 'RUNE',
            'ZEC', 'KSM', 'KAVA', 'WAVES', 'QTUM', 'XTZ', 'EOS', 'BTG', 'BSV',
            'NEO', 'MIOTA', 'ZIL', 'BAT', 'GRT', 'OCEAN', 'KNC', 'ZRX', 'BAND',
            'RLC', 'LPT', 'STORJ', 'COTI'
        }

        if ticker.upper() in crypto_symbols:
            return "crypto"

        # Check for common ETF patterns (London-listed or specific major ETFs)
        if ticker.endswith('.L') or ticker in {'VTI', 'SPY', 'VOO', 'IVV', 'QQQ'}:
            return "etf"

        # Default to stock
        return "stock"

    async def fetch_price_with_auto_detection(self, ticker: str, currency: str = "eur") -> Optional[Dict]:
        """
        Automatically detect the asset type for a ticker and fetch its current price.

        Parameters:
            ticker (str): Asset ticker symbol to fetch.
            currency (str): Target currency for the returned price; expected values are "eur" or "usd".

        Returns:
            dict: Fetched price data for the detected asset type, or `None` if the fetch failed.
        """
        asset_type = self.detect_asset_type(ticker)
        logger.info(f"Auto-detected {ticker} as {asset_type}")

        return await self.fetch_current_price(ticker, asset_type, currency)

    def get_supported_cryptocurrencies(self) -> List[Dict]:
        """
        Return a curated list of popular cryptocurrencies supported by Yahoo Finance.

        Each item in the returned list is a dictionary with the following keys:
        - `symbol`: short ticker symbol (e.g., "BTC")
        - `name`: human-readable name (e.g., "Bitcoin")
        - `yahoo_symbol`: Yahoo Finance symbol (e.g., "BTC-USD")

        Returns:
            List[Dict]: List of cryptocurrency descriptor dictionaries.
        """
        try:
            # Return curated list of popular cryptocurrencies supported by Yahoo Finance
            crypto_symbols = [
                {"symbol": "BTC", "name": "Bitcoin", "yahoo_symbol": "BTC-USD"},
                {"symbol": "ETH", "name": "Ethereum", "yahoo_symbol": "ETH-USD"},
                {"symbol": "BNB", "name": "Binance Coin", "yahoo_symbol": "BNB-USD"},
                {"symbol": "XRP", "name": "Ripple", "yahoo_symbol": "XRP-USD"},
                {"symbol": "ADA", "name": "Cardano", "yahoo_symbol": "ADA-USD"},
                {"symbol": "SOL", "name": "Solana", "yahoo_symbol": "SOL-USD"},
                {"symbol": "DOGE", "name": "Dogecoin", "yahoo_symbol": "DOGE-USD"},
                {"symbol": "DOT", "name": "Polkadot", "yahoo_symbol": "DOT-USD"},
                {"symbol": "MATIC", "name": "Polygon", "yahoo_symbol": "MATIC-USD"},
                {"symbol": "SHIB", "name": "Shiba Inu", "yahoo_symbol": "SHIB-USD"},
                {"symbol": "AVAX", "name": "Avalanche", "yahoo_symbol": "AVAX-USD"},
                {"symbol": "LINK", "name": "Chainlink", "yahoo_symbol": "LINK-USD"},
                {"symbol": "UNI", "name": "Uniswap", "yahoo_symbol": "UNI-USD"},
                {"symbol": "LTC", "name": "Litecoin", "yahoo_symbol": "LTC-USD"},
                {"symbol": "ATOM", "name": "Cosmos", "yahoo_symbol": "ATOM-USD"},
                {"symbol": "XLM", "name": "Stellar", "yahoo_symbol": "XLM-USD"},
                {"symbol": "BCH", "name": "Bitcoin Cash", "yahoo_symbol": "BCH-USD"},
                {"symbol": "FIL", "name": "Filecoin", "yahoo_symbol": "FIL-USD"},
                {"symbol": "TRX", "name": "TRON", "yahoo_symbol": "TRX-USD"},
                {"symbol": "ETC", "name": "Ethereum Classic", "yahoo_symbol": "ETC-USD"},
                {"symbol": "XMR", "name": "Monero", "yahoo_symbol": "XMR-USD"},
                {"symbol": "USDT", "name": "Tether", "yahoo_symbol": "USDT-USD"},
                {"symbol": "USDC", "name": "USD Coin", "yahoo_symbol": "USDC-USD"}
            ]
            return crypto_symbols
        except Exception as e:
            logger.error(f"Error getting supported cryptocurrencies: {e}")
            return []

    async def test_all_services(self) -> Dict[str, bool]:
        """
        Run a set of connectivity and fetch tests for configured price services.

        Performs simple success checks for Yahoo Finance spot fetch, Yahoo Finance crypto realtime fetch, and mixed asset lookup via the fetch_price_with_auto_detection helper.

        Returns:
            Dict[str, bool]: Mapping of test names to `True` if the test succeeded or `False` if it failed.
            Known keys:
              - "yahoo_finance": basic Yahoo Finance latest price fetch for AAPL
              - "yahoo_finance_crypto": Yahoo Finance realtime crypto fetch for BTC-USD
              - "mixed_assets": combined auto-detected fetches for AAPL (stock) and BTC (crypto)
        """
        results = {}

        # Test Yahoo Finance
        try:
            yahoo_result = await self.yahoo_fetcher.fetch_latest_price('AAPL')
            results['yahoo_finance'] = yahoo_result is not None
        except Exception as e:
            logger.error(f"Yahoo Finance test failed: {e}")
            results['yahoo_finance'] = False

        # Test crypto via Yahoo Finance (both USD and EUR)
        try:
            crypto_result_usd = await asyncio.to_thread(self.yahoo_fetcher.fetch_realtime_price, 'BTC-USD')
            crypto_result_eur = await asyncio.to_thread(self.yahoo_fetcher.fetch_realtime_price, 'BTC-EUR')
            results['yahoo_finance_crypto'] = crypto_result_usd is not None and crypto_result_eur is not None
        except Exception as e:
            logger.error(f"Yahoo Finance crypto test failed: {e}")
            results['yahoo_finance_crypto'] = False

        # Test mixed assets
        try:
            stock_price = await self.fetch_price_with_auto_detection('AAPL')
            crypto_price_usd = await self.fetch_price_with_auto_detection('BTC', 'usd')
            crypto_price_eur = await self.fetch_price_with_auto_detection('BTC', 'eur')
            results['mixed_assets'] = stock_price is not None and crypto_price_usd is not None and crypto_price_eur is not None
        except Exception as e:
            logger.error(f"Mixed assets test failed: {e}")
            results['mixed_assets'] = False

        return results


# Create singleton instance for use across the application
unified_price_fetcher = UnifiedPriceFetcher()


# Example usage functions
async def example_usage():
    """
    Demonstrates common operations of the UnifiedPriceFetcher.

    Runs service health checks, fetches an auto-detected stock price and an auto-detected crypto price, retrieves recent historical prices for a crypto asset, and obtains the curated list of supported cryptocurrencies. Intended for example or manual testing; prints results to standard output.
    """

    # Test all services
    status = await unified_price_fetcher.test_all_services()
    print("Service Status:", status)

    # Fetch stock price (auto-detected)
    apple_price = await unified_price_fetcher.fetch_price_with_auto_detection('AAPL')
    if apple_price:
        print(f"AAPL Price: {apple_price['close']} {apple_price.get('currency', 'USD')}")

    # Fetch crypto price (auto-detected)
    btc_price = await unified_price_fetcher.fetch_price_with_auto_detection('BTC')
    if btc_price:
        print(f"BTC Price: {btc_price['current_price']} {btc_price.get('currency', 'USD')}")
    # Fetch historical data
    from datetime import timedelta
    end_date = date.today()
    start_date = end_date - timedelta(days=30)

    eth_history = await unified_price_fetcher.fetch_historical_prices(
        'ETH', start_date, end_date, 'crypto', 'eur'
    )
    print(f"ETH Historical Prices: {len(eth_history)} data points")

    # Get supported cryptocurrencies
    cryptos = unified_price_fetcher.get_supported_cryptocurrencies()
    print(f"Supported Cryptocurrencies: {len(cryptos)} assets")


if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())