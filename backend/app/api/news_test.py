"""
Test news API file.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("/test")
async def test_new_endpoint():
    """Test endpoint to verify new routes are working."""
    return {"message": "New endpoint is working!"}


@router.get("/movers")
async def get_movers_news(
    limit: int = Query(10, ge=1, le=20, description="Maximum number of movers to get news for"),
    min_change_percent: float = Query(2.0, ge=0, le=50, description="Minimum percentage change to include")
):
    """Get news for top movers in the user's portfolio (TodaysMovers integration)."""
    return {
        "message": "Movers endpoint working!",
        "limit": limit,
        "min_change_percent": min_change_percent
    }


@router.get("/{ticker}")
async def get_ticker_news(
    ticker: str,
    limit: int = Query(50, ge=1, le=100, description="Maximum number of articles")
):
    """Get news for a specific ticker."""
    return {
        "message": f"News for ticker: {ticker}",
        "ticker": ticker,
        "limit": limit
    }


@router.post("/refresh")
async def refresh_news(
    tickers: Optional[List[str]] = Query(None, description="Optional list of tickers to refresh")
):
    """Manual trigger to refresh news data."""
    return {
        "message": "News refresh working!",
        "tickers": tickers
    }


@router.get("/sentiment/{ticker}")
async def get_ticker_sentiment(
    ticker: str,
    days: int = Query(7, ge=1, le=30, description="Number of days to analyze")
):
    """Get sentiment analysis for a specific ticker."""
    return {
        "message": f"Sentiment analysis for {ticker}",
        "ticker": ticker,
        "days": days
    }