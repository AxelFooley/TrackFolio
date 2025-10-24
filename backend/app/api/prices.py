"""Price API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, date, timedelta
from typing import Optional
import logging

from app.database import get_db
from app.models.position import Position
from app.schemas.price import RealtimePriceResponse, RealtimePricesResponse
from app.services.price_fetcher import PriceFetcher
from app.services.price_history_manager import price_history_manager
from app.services.system_state_manager import SystemStateManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/prices", tags=["prices"])

# Create a singleton instance of PriceFetcher to maintain cache across requests
_price_fetcher = PriceFetcher()


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
    """
    Get timestamp of last successful price update.

    Returns the persisted last price update timestamp from the database.
    If no price update has been recorded yet, returns None.

    Returns:
        dict with keys:
            - last_update: ISO format datetime string or None
            - status: "success" or "no_data"
    """
    try:
        last_update = await SystemStateManager.get_price_last_update_async(db)

        if last_update:
            return {
                "last_update": last_update.isoformat(),
                "status": "success"
            }
        else:
            return {
                "last_update": None,
                "status": "no_data",
                "message": "No price update has been recorded yet"
            }
    except Exception as e:
        logger.error(f"Error retrieving last price update timestamp: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve last price update timestamp: {str(e)}"
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
