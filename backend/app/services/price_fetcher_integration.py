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
        """Initialize unified price fetcher."""
        self.yahoo_fetcher = PriceFetcher()

    async def fetch_current_price(self, ticker: str, asset_type: str = "stock", currency: str = "eur") -> Optional[Dict]:
        """
        Fetch current price for any asset type.

        Args:
            ticker: Asset ticker symbol
            asset_type: Type of asset ('stock', 'crypto', 'etf')
            currency: Target currency ('eur' or 'usd')

        Returns:
            Dict with price data or None if failed
        """
        try:
            if asset_type.lower() == "crypto":
                # Use Yahoo Finance for cryptocurrencies with -USD suffix
                yahoo_symbol = f"{ticker}-USD"
                result = self.yahoo_fetcher.fetch_realtime_price(yahoo_symbol)
                if result and result.get("current_price"):
                    price_usd = result["current_price"]

                    # Convert to target currency if needed
                    if currency.lower() == "eur":
                        # Get USD to EUR conversion rate
                        try:
                            eur_rate = await self.yahoo_fetcher.fetch_fx_rate("USD", "EUR")
                            if eur_rate:
                                price_eur = price_usd * eur_rate
                                result["current_price"] = price_eur
                                result["currency"] = "EUR"
                            else:
                                # Fallback conversion
                                price_eur = price_usd * Decimal("0.92")
                                result["current_price"] = price_eur
                                result["currency"] = "EUR"
                        except Exception as e:
                            logger.warning(f"Error converting to EUR: {e}, using fallback rate")
                            # Fallback conversion
                            price_eur = price_usd * Decimal("0.92")
                            result["current_price"] = price_eur
                            result["currency"] = "EUR"

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
        Fetch historical prices for any asset type.

        Args:
            ticker: Asset ticker symbol
            start_date: Start date for historical data
            end_date: End date for historical data
            asset_type: Type of asset ('stock', 'crypto', 'etf')
            currency: Target currency ('eur' or 'usd')

        Returns:
            List of price dictionaries
        """
        try:
            if asset_type.lower() == "crypto":
                # Use Yahoo Finance for cryptocurrencies with -USD suffix
                yahoo_symbol = f"{ticker}-USD"
                result = self.yahoo_fetcher.fetch_historical_prices_sync(yahoo_symbol, start_date=start_date, end_date=end_date)
                logger.info(f"Fetched {len(result)} crypto price points for {ticker}")

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
                            logger.info(f"Converted {len(result)} crypto price points to EUR")
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
            else:
                # Use Yahoo Finance for stocks, ETFs, etc.
                result = self.yahoo_fetcher.fetch_historical_prices_sync(ticker, start_date=start_date, end_date=end_date)
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
        Automatically detect asset type based on ticker.

        Args:
            ticker: Asset ticker symbol

        Returns:
            Detected asset type ('stock', 'crypto', 'etf', 'unknown')
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

        # Check for common ETF patterns
        if ticker.endswith('.L') or ticker.startswith('I') or ticker.startswith('VTI') or ticker.startswith('SPY'):
            return "etf"

        # Default to stock
        return "stock"

    async def fetch_price_with_auto_detection(self, ticker: str, currency: str = "eur") -> Optional[Dict]:
        """
        Fetch price with automatic asset type detection.

        Args:
            ticker: Asset ticker symbol
            currency: Target currency ('eur' or 'usd')

        Returns:
            Dict with price data or None if failed
        """
        asset_type = self.detect_asset_type(ticker)
        logger.info(f"Auto-detected {ticker} as {asset_type}")

        return await self.fetch_current_price(ticker, asset_type, currency)

    def get_supported_cryptocurrencies(self) -> List[Dict]:
        """
        Get list of supported cryptocurrencies.

        Returns:
            List of cryptocurrency assets
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
        Test all connected price services.

        Returns:
            Dict with service status
        """
        results = {}

        # Test Yahoo Finance
        try:
            yahoo_result = self.yahoo_fetcher.fetch_latest_price('AAPL')
            results['yahoo_finance'] = yahoo_result is not None
        except Exception as e:
            logger.error(f"Yahoo Finance test failed: {e}")
            results['yahoo_finance'] = False

        # Test crypto via Yahoo Finance
        try:
            crypto_result = self.yahoo_fetcher.fetch_realtime_price('BTC-USD')
            results['yahoo_finance_crypto'] = crypto_result is not None
        except Exception as e:
            logger.error(f"Yahoo Finance crypto test failed: {e}")
            results['yahoo_finance_crypto'] = False

        # Test mixed assets
        try:
            stock_price = await self.fetch_price_with_auto_detection('AAPL')
            crypto_price = await self.fetch_price_with_auto_detection('BTC')
            results['mixed_assets'] = stock_price is not None and crypto_price is not None
        except Exception as e:
            logger.error(f"Mixed assets test failed: {e}")
            results['mixed_assets'] = False

        return results


# Create singleton instance for use across the application
unified_price_fetcher = UnifiedPriceFetcher()


# Example usage functions
async def example_usage():
    """Example usage of the unified price fetcher."""

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
        print(f"BTC Price: {btc_price['price']} {btc_price['currency']}")

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