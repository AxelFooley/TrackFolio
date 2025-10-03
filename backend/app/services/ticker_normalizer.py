"""
Ticker normalization service.

Handles broker-specific ticker prefixes and formats.
"""
import re
import logging

logger = logging.getLogger(__name__)


class TickerNormalizer:
    """Normalize broker-specific ticker formats."""

    @staticmethod
    def normalize(ticker: str) -> str:
        """
        Normalize broker-specific ticker prefixes.

        Directa broker patterns:
        - '1TSLA' -> 'TSLA' (post-split prefix)
        - '.GME' -> 'GME' (US stock prefix)
        - 'X.PTX' -> keep as-is (exchange prefix, valid)

        Args:
            ticker: Raw ticker from broker

        Returns:
            Normalized ticker
        """
        if not ticker:
            return ticker

        original = ticker
        ticker = ticker.strip().upper()

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
