"""
Integration example for CoinCap service with existing PriceFetcher.

This module shows how to integrate CoinCap cryptocurrency data
with the existing price fetching infrastructure.
"""
from decimal import Decimal
from datetime import date, datetime
from typing import Dict, List, Optional
import logging

from .price_fetcher import PriceFetcher
from .coincap import coincap_service

logger = logging.getLogger(__name__)


class UnifiedPriceFetcher:
    """
    Unified price fetcher that combines Yahoo Finance and CoinCap APIs.

    This class extends the existing price fetching capabilities to include
    cryptocurrency data from CoinCap while maintaining compatibility with
    the existing portfolio tracking system.
    """

    def __init__(self):
        """Initialize unified price fetcher."""
        self.yahoo_fetcher = PriceFetcher()
        self.coincap_service = coincap_service

    def fetch_current_price(self, ticker: str, asset_type: str = "stock", currency: str = "eur") -> Optional[Dict]:
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
                # Use CoinCap for cryptocurrencies
                result = self.coincap_service.get_current_price(ticker, currency)
                if result:
                    logger.info(f"Fetched crypto price for {ticker}: {result['price']} {result['currency']}")
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
                        eur_rate = self.yahoo_fetcher.fetch_fx_rate("USD", "EUR")
                        if eur_rate:
                            price_eur = result['close'] * eur_rate
                            result['close'] = price_eur
                            result['currency'] = 'EUR'
                            logger.info(f"Converted to EUR: {price_eur}")

                    return result
                else:
                    logger.warning(f"Failed to fetch stock price for {ticker}")
                    return None

        except Exception as e:
            logger.error(f"Error fetching price for {ticker}: {e}")
            return None

    def fetch_historical_prices(
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
                # Use CoinCap for cryptocurrencies
                result = self.coincap_service.get_historical_prices(ticker, start_date, end_date, currency)
                logger.info(f"Fetched {len(result)} crypto price points for {ticker}")
                return result
            else:
                # Use Yahoo Finance for stocks, ETFs, etc.
                result = self.yahoo_fetcher.fetch_historical_prices_sync(ticker, start_date=start_date, end_date=end_date)
                logger.info(f"Fetched {len(result)} stock price points for {ticker}")

                # Convert to target currency if needed
                if currency.lower() == "eur" and result:
                    eur_rate = self.yahoo_fetcher.fetch_fx_rate("USD", "EUR")
                    if eur_rate:
                        for price_point in result:
                            price_point['close'] = price_point['close'] * eur_rate
                            price_point['open'] = price_point['open'] * eur_rate
                            price_point['high'] = price_point['high'] * eur_rate
                            price_point['low'] = price_point['low'] * eur_rate
                            price_point['currency'] = 'EUR'
                        logger.info(f"Converted {len(result)} price points to EUR")

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
        # Check if it's a known cryptocurrency
        coincapec_id = self.coincap_service.map_symbol_to_coincec_id(ticker)
        if coincapec_id:
            return "crypto"

        # Check for common ETF patterns
        if ticker.endswith('.L') or ticker.startswith('I') or ticker.startswith('VTI') or ticker.startswith('SPY'):
            return "etf"

        # Default to stock
        return "stock"

    def fetch_price_with_auto_detection(self, ticker: str, currency: str = "eur") -> Optional[Dict]:
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

        return self.fetch_current_price(ticker, asset_type, currency)

    def get_supported_cryptocurrencies(self) -> List[Dict]:
        """
        Get list of supported cryptocurrencies from CoinCap.

        Returns:
            List of cryptocurrency assets
        """
        try:
            return self.coincap_service.get_supported_symbols()
        except Exception as e:
            logger.error(f"Error getting supported cryptocurrencies: {e}")
            return []

    def test_all_services(self) -> Dict[str, bool]:
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

        # Test CoinCap
        try:
            coincap_result = self.coincap_service.test_connection()
            results['coincap'] = coincap_result
        except Exception as e:
            logger.error(f"CoinCap test failed: {e}")
            results['coincap'] = False

        # Test mixed assets
        try:
            stock_price = self.fetch_price_with_auto_detection('AAPL')
            crypto_price = self.fetch_price_with_auto_detection('BTC')
            results['mixed_assets'] = stock_price is not None and crypto_price is not None
        except Exception as e:
            logger.error(f"Mixed assets test failed: {e}")
            results['mixed_assets'] = False

        return results


# Create singleton instance for use across the application
unified_price_fetcher = UnifiedPriceFetcher()


# Example usage functions
def example_usage():
    """Example usage of the unified price fetcher."""

    # Test all services
    status = unified_price_fetcher.test_all_services()
    print("Service Status:", status)

    # Fetch stock price (auto-detected)
    apple_price = unified_price_fetcher.fetch_price_with_auto_detection('AAPL')
    if apple_price:
        print(f"AAPL Price: {apple_price['close']} {apple_price.get('currency', 'USD')}")

    # Fetch crypto price (auto-detected)
    btc_price = unified_price_fetcher.fetch_price_with_auto_detection('BTC')
    if btc_price:
        print(f"BTC Price: {btc_price['price']} {btc_price['currency']}")

    # Fetch historical data
    from datetime import timedelta
    end_date = date.today()
    start_date = end_date - timedelta(days=30)

    eth_history = unified_price_fetcher.fetch_historical_prices(
        'ETH', start_date, end_date, 'crypto', 'eur'
    )
    print(f"ETH Historical Prices: {len(eth_history)} data points")

    # Get supported cryptocurrencies
    cryptos = unified_price_fetcher.get_supported_cryptocurrencies()
    print(f"Supported Cryptocurrencies: {len(cryptos)} assets")


if __name__ == "__main__":
    example_usage()