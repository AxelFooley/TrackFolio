"""Assets API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import yfinance as yf
import logging
import asyncio
from functools import lru_cache
import re

from app.database import get_db
from app.models import Position, Transaction, PriceHistory
from app.schemas.position import PositionResponse
from app.schemas.transaction import TransactionResponse
from app.schemas.price import PriceResponse
from app.services.cache import cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/assets", tags=["assets"])


# Hardcoded list of common assets for quick search
COMMON_ASSETS = [
    {"ticker": "AAPL", "name": "Apple Inc.", "type": "EQUITY"},
    {"ticker": "MSFT", "name": "Microsoft Corporation", "type": "EQUITY"},
    {"ticker": "GOOGL", "name": "Alphabet Inc.", "type": "EQUITY"},
    {"ticker": "AMZN", "name": "Amazon.com Inc.", "type": "EQUITY"},
    {"ticker": "TSLA", "name": "Tesla Inc.", "type": "EQUITY"},
    {"ticker": "META", "name": "Meta Platforms Inc.", "type": "EQUITY"},
    {"ticker": "NVDA", "name": "NVIDIA Corporation", "type": "EQUITY"},
    {"ticker": "JPM", "name": "JPMorgan Chase & Co.", "type": "EQUITY"},
    {"ticker": "V", "name": "Visa Inc.", "type": "EQUITY"},
    {"ticker": "JNJ", "name": "Johnson & Johnson", "type": "EQUITY"},
    {"ticker": "SPY", "name": "SPDR S&P 500 ETF Trust", "type": "ETF"},
    {"ticker": "VOO", "name": "Vanguard S&P 500 ETF", "type": "ETF"},
    {"ticker": "QQQ", "name": "Invesco QQQ Trust", "type": "ETF"},
    {"ticker": "VTI", "name": "Vanguard Total Stock Market ETF", "type": "ETF"},
    {"ticker": "VWCE.DE", "name": "Vanguard FTSE All-World UCITS ETF", "type": "ETF"},
    {"ticker": "CSPX.L", "name": "iShares Core S&P 500 UCITS ETF", "type": "ETF"},
    {"ticker": "EUNL.DE", "name": "iShares Core MSCI World UCITS ETF", "type": "ETF"},
    {"ticker": "VUSA.L", "name": "Vanguard S&P 500 UCITS ETF", "type": "ETF"},
]

# Cache TTL in seconds (1 hour)
SEARCH_CACHE_TTL = 3600


def _fetch_ticker_info_sync(ticker: str) -> dict | None:
    """
    Synchronous function to fetch ticker info from Yahoo Finance.

    This is run in a thread pool to avoid blocking the event loop.

    Args:
        ticker: Ticker symbol to fetch info for

    Returns:
        Dictionary with ticker info or None if error
    """
    try:
        ticker_obj = yf.Ticker(ticker.upper())
        info = ticker_obj.info

        if info and info.get('symbol'):
            ticker_name = info.get('longName') or info.get('shortName') or info.get('symbol')
            ticker_type = info.get('quoteType', 'UNKNOWN')

            return {
                "ticker": info['symbol'],
                "name": ticker_name,
                "type": ticker_type
            }
        return None
    except Exception as e:
        logger.debug(f"Could not fetch ticker info for {ticker}: {str(e)}")
        return None


@router.get("/search", response_model=List[dict])
async def search_assets(
    q: str = Query(
        ...,
        min_length=1,
        max_length=20,
        pattern="^[A-Z0-9.\\-]{1,20}$",
        description="Ticker symbol or company name. Must contain only uppercase letters, numbers, dots, and hyphens."
    )
):
    """
    Search for ticker symbols with caching and async execution.

    Returns a list of matching stocks, ETFs, and other securities with their names and symbols.
    Results are cached for 1 hour to minimize API calls to Yahoo Finance.

    Query string is case-insensitive and matches against ticker symbols and company names.

    **Validation:**
    - Pattern: ^[A-Z0-9.\\-]{1,20}$ (uppercase letters, numbers, dots, hyphens only)
    - Length: 1-20 characters
    - Purpose: Prevent injection attacks and ensure valid ticker symbol format

    Performance:
    - First search: May take up to 5 seconds (Yahoo Finance lookup)
    - Cached results: <100ms
    - No blocking of the event loop
    """
    # Additional security validation - reject SQL injection patterns and dangerous sequences
    if "--" in q or q.startswith("-") or q.endswith("-"):
        raise HTTPException(
            status_code=422,
            detail="Invalid ticker format - consecutive hyphens and leading/trailing hyphens not allowed"
        )

    # Create cache key from query
    cache_key = f"asset_search:{q.upper()}"

    # Try to get from cache first
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        logger.debug(f"Returning cached search results for {q}")
        # Apply limit to cached results to ensure consistency
        return cached_result[:10]

    try:
        search_results = []
        query_lower = q.lower()

        # Filter common assets by query (fast, in-memory)
        for item in COMMON_ASSETS:
            if (query_lower in item["ticker"].lower() or
                query_lower in item["name"].lower()):
                search_results.append(item)

        # If we have fewer than 5 results, try to fetch additional info from yfinance
        # using thread pool to avoid blocking the event loop
        if len(search_results) < 5:
            try:
                loop = asyncio.get_event_loop()
                # Run yfinance call in thread pool with 5 second timeout
                ticker_info = await asyncio.wait_for(
                    loop.run_in_executor(None, _fetch_ticker_info_sync, q),
                    timeout=5.0
                )

                if ticker_info:
                    # Check if not already in results
                    if not any(r['ticker'] == ticker_info['ticker'] for r in search_results):
                        search_results.append(ticker_info)
            except asyncio.TimeoutError:
                logger.debug(f"Timeout fetching ticker info for {q} from Yahoo Finance")
            except Exception as e:
                logger.debug(f"Could not fetch ticker info for {q}: {str(e)}")

        # Limit results to 10
        final_results = search_results[:10]

        # Cache the results for 1 hour
        cache.set(cache_key, final_results, ttl_seconds=SEARCH_CACHE_TTL)

        return final_results

    except Exception as e:
        logger.error(f"Error searching for assets: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error searching for assets: {str(e)}")


@router.get("/{ticker}", response_model=PositionResponse)
async def get_asset_detail(
    ticker: str,
    db: AsyncSession = Depends(get_db)
):
    """Get detailed information for a specific asset (by ticker or ISIN)."""
    # Try ISIN first (if 12 characters)
    if len(ticker) == 12:
        result = await db.execute(
            select(Position).where(Position.isin == ticker)
        )
    else:
        # Try by current_ticker
        result = await db.execute(
            select(Position).where(Position.current_ticker == ticker)
        )

    position = result.scalar_one_or_none()

    if not position:
        raise HTTPException(status_code=404, detail="Asset not found")

    return position


@router.get("/{ticker}/transactions", response_model=List[TransactionResponse])
async def get_asset_transactions(
    ticker: str,
    db: AsyncSession = Depends(get_db)
):
    """Get all transactions for a specific asset."""
    result = await db.execute(
        select(Transaction)
        .where(Transaction.ticker == ticker)
        .order_by(Transaction.operation_date.desc())
    )
    transactions = result.scalars().all()

    return transactions


@router.get("/{ticker}/prices", response_model=List[PriceResponse])
async def get_asset_prices(
    ticker: str,
    limit: int = 365,
    db: AsyncSession = Depends(get_db)
):
    """Get historical price data for a specific asset."""
    result = await db.execute(
        select(PriceHistory)
        .where(PriceHistory.ticker == ticker)
        .order_by(PriceHistory.date.desc())
        .limit(limit)
    )
    prices = result.scalars().all()

    return prices
