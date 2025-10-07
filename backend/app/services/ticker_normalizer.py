"""
Ticker normalization service.

Handles broker-specific ticker prefixes and formats for both stocks and cryptocurrencies.
"""
import re
import logging

logger = logging.getLogger(__name__)


class TickerNormalizer:
    """Normalize broker-specific ticker formats for stocks and crypto."""

    @staticmethod
    def normalize(ticker: str) -> str:
        """
        Normalize broker-specific ticker prefixes and crypto formats.

        Directa broker patterns:
        - '1TSLA' -> 'TSLA' (post-split prefix)
        - '.GME' -> 'GME' (US stock prefix)
        - 'X.PTX' -> keep as-is (exchange prefix, valid)

        Crypto patterns:
        - 'BTC-USD' -> 'BTC' (trading pair format)
        - 'BTC/USD' -> 'BTC' (trading pair format)
        - 'BTCUSD' -> 'BTC' (direct pair format)
        - 'BTCUSDT' -> 'BTC' (tether pair format)

        Args:
            ticker: Raw ticker from broker or exchange

        Returns:
            Normalized ticker
        """
        if not ticker:
            return ticker

        original = ticker
        ticker = ticker.strip().upper()

        # Check if it's a crypto ticker first
        if TickerNormalizer._is_crypto_format(ticker):
            normalized = TickerNormalizer._normalize_crypto(ticker)
            if normalized != ticker:
                logger.debug(f"Normalized crypto ticker '{original}' -> '{normalized}'")
            return normalized

        # Handle stock broker prefixes (Directa patterns)
        # Remove leading '1' if followed by alphabetic characters
        # (Directa adds '1' prefix after splits)
        if ticker.startswith('1') and len(ticker) > 1:
            rest = ticker[1:]
            # Only remove if rest is pure alpha or starts with valid exchange prefix
            if re.match(r'^[A-Z]+$', rest) or rest.startswith('.'):
                ticker = rest
                logger.debug(f"Normalized '{original}' -> '{ticker}' (removed split prefix)")

        # Remove leading '.' (Directa US stock prefix)
        if ticker.startswith('.'):
            ticker = ticker[1:]
            logger.debug(f"Normalized '{original}' -> '{ticker}' (removed US prefix)")

        return ticker

    @staticmethod
    def _is_crypto_format(ticker: str) -> bool:
        """
        Check if ticker appears to be a cryptocurrency format.

        Args:
            ticker: Ticker symbol

        Returns:
            True if appears to be cryptocurrency format
        """
        if not ticker:
            return False

        # Crypto patterns with separators
        if '-' in ticker or '/' in ticker:
            return True

        # Check for crypto trading pair suffixes
        crypto_suffixes = ['USD', 'USDT', 'EUR', 'GBP', 'BTC', 'ETH']
        for suffix in crypto_suffixes:
            if ticker.endswith(suffix) and len(ticker) > len(suffix):
                base = ticker[:-len(suffix)]
                if len(base) >= 2 and base.isalnum():
                    return True

        # Check against known crypto tickers
        known_crypto = {
            'BTC', 'ETH', 'USDT', 'USDC', 'BNB', 'SOL', 'ADA', 'XRP', 'DOT', 'DOGE',
            'AVAX', 'MATIC', 'LINK', 'UNI', 'ATOM', 'LTC', 'SHIB', 'TRX', 'XLM',
            'FIL', 'ETC', 'VET', 'THETA', 'ICP', 'HBAR', 'EGLD', 'FTT', 'ALGO',
            'AAVE', 'CAKE', 'MANA', 'SAND', 'AXS', 'LUNA', 'CRV', 'COMP', 'MKR'
        }
        return ticker in known_crypto

    @staticmethod
    def _normalize_crypto(ticker: str) -> str:
        """
        Normalize crypto ticker to base asset format.

        Args:
            ticker: Raw crypto ticker

        Returns:
            Normalized base ticker
        """
        if not ticker:
            return ticker

        ticker = ticker.upper().strip()

        # Handle trading pair formats with separators
        separators = ['-', '/', 'USD', 'USDT', 'EUR', 'GBP', 'BTC', 'ETH']

        for sep in separators:
            if sep in ticker:
                # Split and take the first part (base asset)
                parts = ticker.split(sep)
                if parts[0]:
                    return parts[0]

        return ticker

    @staticmethod
    def get_display_ticker(isin: str, current_ticker: str) -> str:
        """
        Get display ticker for UI.

        Args:
            isin: Security ISIN
            current_ticker: Current ticker from database

        Returns:
            Ticker suitable for display
        """
        # For now, just return current_ticker
        # Future: Could add exchange suffixes, etc.
        return current_ticker
