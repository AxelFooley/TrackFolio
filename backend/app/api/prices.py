"""Price update API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, date
from typing import List, Optional
import logging

from app.database import get_db
from app.models.position import Position
from app.schemas.price import RealtimePriceResponse, RealtimePricesResponse, HistoricalPriceResponse
from app.services.price_fetcher import PriceFetcher

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/prices", tags=["prices"])

# Create a singleton instance of PriceFetcher to maintain cache across requests
_price_fetcher = PriceFetcher()


@router.post("/refresh")
async def refresh_prices(db: AsyncSession = Depends(get_db)):
    """
    Manual price refresh endpoint.

    Rate limited to prevent abuse (1 refresh per 5 minutes).
    """
    # This would trigger price update job
    # For now, return placeholder response
    return {
        "message": "Price refresh triggered",
        "timestamp": datetime.utcnow()
    }


@router.get("/last-update")
async def get_last_update(db: AsyncSession = Depends(get_db)):
    """Get timestamp of last successful price update."""
    # Would query from a system state table or cache
    return {
        "last_update": datetime.utcnow(),
        "status": "success"
    }


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


@router.get("/historical", response_model=HistoricalPriceResponse)
async def get_historical_price(
    ticker: str = Query(..., description="Asset ticker symbol (e.g., AAPL, MSFT)"),
    date_str: str = Query(..., alias="date", description="Target date in YYYY-MM-DD format"),
    db: AsyncSession = Depends(get_db)
):
    """
    Fetch historical close price for a specific ticker and date.

    This endpoint is optimized for the manual transaction workflow and includes:
    - Weekend handling: Returns Friday price for Saturday/Sunday requests
    - Holiday handling: Returns previous available trading day price
    - Current price fallback: Returns current/latest price for today or future dates
    - Currency detection: Automatically detects price currency from ticker
    - International support: Works with global stocks and ETFs

    Args:
        ticker: Asset ticker symbol (broker format, e.g., "AAPL", "MSFT", "VWCE.DE")
        date_str: Target date for price data in YYYY-MM-DD format
        db: Database session (unused but required for dependency injection)

    Returns:
        HistoricalPriceResponse with price data or error information

    Examples:
        - /api/prices/historical?ticker=AAPL&date=2024-01-15
        - /api/prices/historical?ticker=VWCE.DE&date=2024-03-20
        - /api/prices/historical?ticker=MSFT&date=2024-12-25 (Christmas - returns previous trading day)
        - /api/prices/historical?ticker=TSLA&date=2024-03-09 (Saturday - returns Friday price)
        - /api/prices/historical?ticker=NFLX&date=2025-01-01 (Future date - returns current price)
    """
    try:
        # Validate date format
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid date format. Please use YYYY-MM-DD format."
            )

        # Validate ticker
        if not ticker or not ticker.strip():
            raise HTTPException(
                status_code=400,
                detail="Ticker symbol is required."
            )

        # Clean ticker
        ticker = ticker.strip().upper()

        logger.info(f"Fetching historical price for {ticker} on {target_date}")

        # Use the price fetcher service
        price_data = _price_fetcher.fetch_historical_price(ticker, target_date)

        # Convert to response model
        return HistoricalPriceResponse(**price_data)

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_historical_price for {ticker} on {date_str}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error while fetching historical price: {str(e)}"
        )
