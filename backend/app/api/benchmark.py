"""Benchmark API endpoints."""
from typing import Optional, List
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import logging
import yfinance as yf

from app.database import get_db
from app.models import Benchmark, Transaction
from app.schemas.benchmark import BenchmarkCreate, BenchmarkResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/benchmark", tags=["benchmark"])


@router.get("/", response_model=Optional[BenchmarkResponse])
async def get_benchmark(db: AsyncSession = Depends(get_db)):
    """Get current active benchmark. Returns null if not configured."""
    result = await db.execute(select(Benchmark).limit(1))
    benchmark = result.scalar_one_or_none()

    return benchmark  # Returns None if not found, which is valid


@router.post("/", response_model=BenchmarkResponse)
async def set_benchmark(
    benchmark_data: BenchmarkCreate,
    db: AsyncSession = Depends(get_db)
):
    """Set or update the active benchmark (single-row table)."""
    # Delete existing benchmark
    result = await db.execute(select(Benchmark))
    existing = result.scalar_one_or_none()

    if existing:
        await db.delete(existing)

    # Create new benchmark
    benchmark = Benchmark(
        ticker=benchmark_data.ticker,
        description=benchmark_data.description or f"Benchmark: {benchmark_data.ticker}"
    )
    db.add(benchmark)
    await db.commit()
    await db.refresh(benchmark)

    # Trigger historical price fetch for benchmark
    # Find earliest transaction date or use 1 year ago as fallback
    earliest_txn_result = await db.execute(
        select(func.min(Transaction.operation_date))
    )
    earliest_date = earliest_txn_result.scalar_one_or_none()

    if earliest_date:
        start_date = earliest_date
    else:
        # Default to 1 year ago if no transactions
        start_date = date.today() - timedelta(days=365)

    end_date = date.today()

    # Trigger async task to fetch benchmark prices
    logger.info(f"Triggering price fetch for benchmark {benchmark.ticker} from {start_date} to {end_date}")

    # Use Celery task to fetch prices asynchronously
    from app.tasks.price_updates import fetch_prices_for_ticker
    fetch_prices_for_ticker.delay(
        ticker=benchmark.ticker,
        isin=None,  # Benchmarks don't have ISINs
        start_date=str(start_date),
        end_date=str(end_date)
    )

    return benchmark


@router.get("/search", response_model=List[dict])
async def search_tickers(
    q: str = Query(..., min_length=1, description="Search query for ticker symbol or company name")
):
    """
    Search for ticker symbols using Yahoo Finance.

    Returns a list of matching tickers with their names and symbols.
    This helps users select the correct ticker for benchmarks.
    """
    try:
        # Use yfinance to search for tickers
        # This is a simple implementation - for production, consider using a dedicated API
        search_results = []

        # Common benchmark indices and ETFs
        common_benchmarks = [
            {"ticker": "^GSPC", "name": "S&P 500", "type": "INDEX"},
            {"ticker": "^DJI", "name": "Dow Jones Industrial Average", "type": "INDEX"},
            {"ticker": "^IXIC", "name": "NASDAQ Composite", "type": "INDEX"},
            {"ticker": "^FTSE", "name": "FTSE 100", "type": "INDEX"},
            {"ticker": "^GDAXI", "name": "DAX", "type": "INDEX"},
            {"ticker": "^FCHI", "name": "CAC 40", "type": "INDEX"},
            {"ticker": "SPY", "name": "SPDR S&P 500 ETF Trust", "type": "ETF"},
            {"ticker": "VOO", "name": "Vanguard S&P 500 ETF", "type": "ETF"},
            {"ticker": "QQQ", "name": "Invesco QQQ Trust", "type": "ETF"},
            {"ticker": "VTI", "name": "Vanguard Total Stock Market ETF", "type": "ETF"},
            {"ticker": "VWCE.DE", "name": "Vanguard FTSE All-World UCITS ETF", "type": "ETF"},
            {"ticker": "CSPX.L", "name": "iShares Core S&P 500 UCITS ETF", "type": "ETF"},
            {"ticker": "CSSPX.MI", "name": "iShares Core S&P 500 UCITS ETF (Milan)", "type": "ETF"},
            {"ticker": "EUNL.DE", "name": "iShares Core MSCI World UCITS ETF", "type": "ETF"},
            {"ticker": "VUSA.L", "name": "Vanguard S&P 500 UCITS ETF", "type": "ETF"},
        ]

        # Filter common benchmarks by query
        query_lower = q.lower()
        for item in common_benchmarks:
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
        logger.error(f"Error searching for tickers: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error searching for tickers: {str(e)}")
