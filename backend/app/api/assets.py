"""Assets API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import yfinance as yf
import logging

from app.database import get_db
from app.models import Position, Transaction, PriceHistory
from app.schemas.position import PositionResponse
from app.schemas.transaction import TransactionResponse
from app.schemas.price import PriceResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.get("/search", response_model=List[dict])
async def search_assets(
    q: str = Query(..., min_length=1, description="Search query for ticker symbol or company name")
):
    """
    Search for ticker symbols using Yahoo Finance.

    Returns a list of matching stocks, ETFs, and other securities with their names and symbols.
    This helps users find and add securities to their portfolio.
    """
    try:
        search_results = []

        # Common stocks and ETFs
        common_assets = [
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

        # Filter common assets by query
        query_lower = q.lower()
        for item in common_assets:
            if (query_lower in item["ticker"].lower() or
                query_lower in item["name"].lower()):
                search_results.append(item)

        # If we have fewer than 5 results, try to fetch additional info from yfinance
        if len(search_results) < 5:
            try:
                # Try to get info for the exact ticker query
                ticker_obj = yf.Ticker(q.upper())
                info = ticker_obj.info

                if info and info.get('symbol'):
                    ticker_name = info.get('longName') or info.get('shortName') or info.get('symbol')
                    ticker_type = info.get('quoteType', 'UNKNOWN')

                    # Check if not already in results
                    if not any(r['ticker'] == info['symbol'] for r in search_results):
                        search_results.append({
                            "ticker": info['symbol'],
                            "name": ticker_name,
                            "type": ticker_type
                        })
            except Exception as e:
                logger.debug(f"Could not fetch ticker info for {q}: {str(e)}")

        # Limit results to 10
        return search_results[:10]

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
