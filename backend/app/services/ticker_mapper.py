"""
Ticker mapping service - Maps broker tickers to Yahoo Finance tickers using ISIN.

Simple approach: Try ISIN directly with Yahoo Finance.
"""
from typing import Optional
import logging
import yfinance as yf

logger = logging.getLogger(__name__)


class TickerMapper:
    """Maps broker tickers to Yahoo Finance tickers using ISIN."""

    # Manual mapping cache (can be moved to database later)
    _manual_mappings = {
        "X.WBIT": "BTCW.L",  # WisdomTree Bitcoin ETP (GB00BJYDH287)
    }

    @staticmethod
    def resolve_ticker(ticker: str, isin: Optional[str] = None) -> str:
        """
        Resolve broker ticker to Yahoo Finance ticker.

        Strategy:
        1. Check manual mappings first
        2. If ISIN provided, try ISIN directly with Yahoo Finance
        3. Fall back to original ticker

        Args:
            ticker: Broker ticker symbol
            isin: ISIN code (e.g., IE00B4L5Y983)

        Returns:
            Yahoo Finance ticker symbol
        """
        # Check manual mappings first
        if ticker in TickerMapper._manual_mappings:
            mapped = TickerMapper._manual_mappings[ticker]
            logger.debug(f"Using manual mapping: {ticker} -> {mapped}")
            return mapped

        # If no ISIN, use ticker as-is
        if not isin:
            logger.debug(f"No ISIN provided for {ticker}, using as-is")
            return ticker

        # Try ISIN directly with Yahoo Finance
        logger.info(f"Trying to use ISIN {isin} directly for {ticker}")
        return isin

    @staticmethod
    def add_manual_mapping(broker_ticker: str, yahoo_ticker: str):
        """
        Add a manual ticker mapping.

        Args:
            broker_ticker: Ticker as shown by broker
            yahoo_ticker: Correct Yahoo Finance ticker
        """
        TickerMapper._manual_mappings[broker_ticker] = yahoo_ticker
        logger.info(f"Added manual mapping: {broker_ticker} -> {yahoo_ticker}")

    @staticmethod
    def clear_cache():
        """Clear manual mappings."""
        TickerMapper._manual_mappings.clear()
