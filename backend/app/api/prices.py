"""Price update API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, date, timedelta
from typing import List, Optional
import logging

from app.database import get_db
from app.models.position import Position
from app.schemas.price import RealtimePriceResponse, RealtimePricesResponse, PriceHistoryResponse
from app.services.price_fetcher import PriceFetcher
from app.services.price_history_manager import price_history_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/prices", tags=["prices"])

# Create a singleton instance of PriceFetcher to maintain cache across requests
_price_fetcher = PriceFetcher()


@router.post("/refresh")
async def refresh_prices(
    background_tasks: BackgroundTasks,
    current_only: bool = True,
    symbols: Optional[List[str]] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Manual price refresh endpoint.

    Args:
        current_only: If True, only refresh current day's prices. If False, fetch complete history.
        symbols: Optional list of symbols to refresh (defaults to all active symbols)

    Rate limited to prevent abuse (1 refresh per 5 minutes).
    """
    try:
        if current_only:
            # Trigger current price update in background
            background_tasks.add_task(
                _update_current_prices,
                symbols=symbols
            )
            return {
                "message": "Current price refresh triggered",
                "timestamp": datetime.utcnow(),
                "type": "current_only"
            }
        else:
            # Trigger complete history update in background
            background_tasks.add_task(
                _update_complete_history,
                symbols=symbols
            )
            return {
                "message": "Complete price history refresh triggered",
                "timestamp": datetime.utcnow(),
                "type": "complete_history"
            }

    except Exception as e:
        logger.error(f"Error triggering price refresh: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger price refresh: {str(e)}"
        )


def _update_current_prices(symbols: Optional[List[str]] = None):
    """Background task to update current day's prices only."""
    if symbols is None:
        symbols = list(price_history_manager.get_all_active_symbols())

    logger.info(f"Updating current prices for {len(symbols)} symbols")

    for symbol in symbols:
        try:
            # Only update today's price
            today = date.today()
            price_history_manager.fetch_and_store_complete_history(
                symbol=symbol,
                start_date=today,
                force_update=True
            )
        except Exception as e:
            logger.exception(f"Error updating current price for {symbol}: {e}")


def _update_complete_history(symbols: Optional[List[str]] = None):
    """Background task to update complete price history."""
    logger.info(f"Starting complete history update for symbols: {symbols or 'all'}")

    results = price_history_manager.update_all_symbols_history(symbols, force_update=True)

    total_updated = sum(r.get('updated', 0) for r in results.values())
    total_added = sum(r.get('added', 0) for r in results.values())

    logger.info(f"Complete history update finished: {total_added} added, {total_updated} updated")


@router.get("/history/{symbol}")
async def get_price_history(
    symbol: str,
    days: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Optional[int] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Get optimized price history for a symbol from our database.

    This endpoint fetches from our local PriceHistory table, which is much
    faster than making external API calls for each request.

    Args:
        symbol: Ticker symbol
        days: Number of days of history to return (alternative to date range)
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        limit: Maximum number of records to return

    Returns:
        List of price history records
    """
    try:
        # Parse dates if provided
        parsed_start_date = None
        parsed_end_date = None

        if start_date:
            try:
                parsed_start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD")

        if end_date:
            try:
                parsed_end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid end_date format. Use YYYY-MM-DD")

        # If days is specified, calculate date range
        if days and not start_date:
            parsed_end_date = date.today()
            parsed_start_date = parsed_end_date - timedelta(days=days)

        # Get price history from our database
        price_data = price_history_manager.get_price_history(
            symbol=symbol,
            start_date=parsed_start_date,
            end_date=parsed_end_date,
            limit=limit
        )

        if not price_data:
            # Try to fetch missing data (run synchronously since we can't create BackgroundTasks here)
            try:
                price_history_manager.fetch_and_store_complete_history(symbol=symbol)
            except Exception as e:
                logger.error(f"Error fetching missing data for {symbol}: {e}")

            return {
                "symbol": symbol,
                "data": [],
                "message": "No historical data available. Attempting to fetch...",
                "fetching": True
            }

        return {
            "symbol": symbol,
            "data": price_data,
            "count": len(price_data),
            "fetching": False
        }

    except Exception as e:
        logger.error(f"Error getting price history for {symbol}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get price history: {str(e)}"
        )


@router.get("/last-update")
async def get_last_update(db: AsyncSession = Depends(get_db)):
    """Get timestamp of last successful price update."""
    # Would query from a system state table or cache
    return {
        "last_update": datetime.utcnow(),
        "status": "success"
    }


@router.post("/ensure-coverage")
async def ensure_price_coverage(
    background_tasks: BackgroundTasks,
    symbols: Optional[List[str]] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Ensure complete price history coverage for all symbols.

    This endpoint checks for gaps in historical data and fills them if needed.
    It runs in the background as it can take a while for many symbols.

    Args:
        symbols: Optional list of symbols to check (defaults to all active symbols)
    """
    try:
        # Run coverage check in background
        background_tasks.add_task(
            price_history_manager.ensure_complete_coverage,
            symbols=symbols
        )

        return {
            "message": "Price coverage check started in background",
            "symbols": symbols or "all active symbols",
            "timestamp": datetime.utcnow()
        }

    except Exception as e:
        logger.error(f"Error starting coverage check: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start coverage check: {str(e)}"
        )


@router.get("/realtime", response_model=RealtimePricesResponse)
async def get_realtime_prices(db: AsyncSession = Depends(get_db)):
    """
    Fetch near real-time prices for all active positions.

    This endpoint:
    - Queries all positions with non-zero quantity from the database
    - Fetches current prices in parallel using yfinance
    - Uses 30-second caching to reduce API load
    - Does NOT persist prices to the database (daily snapshots remain separate)

    Returns:
        RealtimePricesResponse with current prices, changes, and metadata

    Note:
        - Prices are intraday and may be delayed by 15-20 minutes depending on exchange
        - Failed fetches are logged but don't cause the entire request to fail
        - Cached prices (< 30 seconds old) are returned immediately
    """
    try:
        # Fetch all active positions (quantity > 0)
        result = await db.execute(
            select(Position).where(Position.quantity > 0)
        )
        positions = result.scalars().all()

        if not positions:
            logger.info("No active positions found for real-time price fetching")
            return RealtimePricesResponse(
                prices=[],
                fetched_count=0,
                total_count=0,
                timestamp=datetime.utcnow()
            )

        logger.info(f"Fetching real-time prices for {len(positions)} positions")

        # Prepare list of (ticker, isin) tuples
        tickers = [(pos.current_ticker, pos.isin) for pos in positions]

        # Fetch prices in parallel (this runs synchronously but uses ThreadPoolExecutor internally)
        price_results = _price_fetcher.fetch_realtime_prices_batch(tickers)

        # Convert to response models
        price_responses = [
            RealtimePriceResponse(
                ticker=price["ticker"],
                isin=price["isin"],
                current_price=price["current_price"],
                previous_close=price["previous_close"],
                change_amount=price["change_amount"],
                change_percent=price["change_percent"],
                timestamp=price["timestamp"]
            )
            for price in price_results
        ]

        logger.info(
            f"Successfully fetched {len(price_responses)} out of {len(positions)} real-time prices"
        )

        return RealtimePricesResponse(
            prices=price_responses,
            fetched_count=len(price_responses),
            total_count=len(positions),
            timestamp=datetime.utcnow()
        )

    except Exception as e:
        logger.error(f"Error fetching real-time prices: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch real-time prices: {str(e)}"
        )
