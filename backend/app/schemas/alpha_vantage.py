"""
Alpha Vantage API response schemas.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class BaseAlphaVantageResponse(BaseModel):
    """Base response schema for Alpha Vantage API calls."""
    status: str = Field(..., description="API call status")
    symbol: Optional[str] = Field(None, description="Stock symbol")
    error: Optional[str] = Field(None, description="Error message if any")


class CompanyOverviewResponse(BaseAlphaVantageResponse):
    """Response schema for company overview data."""
    data: Dict[str, Any] = Field(..., description="Company overview data")


class EarningsResponse(BaseAlphaVantageResponse):
    """Response schema for earnings data."""
    data: Dict[str, List[Dict[str, Any]]] = Field(
        ...,
        description="Earnings data with quarterly and annual information"
    )


class NewsArticle(BaseModel):
    """Individual news article schema."""
    title: Optional[str] = Field(None, description="Article title")
    url: Optional[str] = Field(None, description="Article URL")
    source: Optional[str] = Field(None, description="News source")
    time: Optional[str] = Field(None, description="Article publication time")
    summary: Optional[str] = Field(None, description="Article summary")
    banner_image: Optional[str] = Field(None, description="Banner image URL")
    topics: List[Dict[str, Any]] = Field(default_factory=list, description="Article topics")
    overall_sentiment_score: Optional[float] = Field(None, description="Overall sentiment score")
    overall_sentiment_label: Optional[str] = Field(None, description="Sentiment label")


class NewsResponse(BaseAlphaVantageResponse):
    """Response schema for news sentiment data."""
    data: List[NewsArticle] = Field(..., description="List of news articles")


class DailyDataPoint(BaseModel):
    """Daily data point schema."""
    date: str = Field(..., description="Trading date")
    open: float = Field(..., description="Opening price")
    high: float = Field(..., description="Highest price")
    low: float = Field(..., description="Lowest price")
    close: float = Field(..., description="Closing price")
    volume: int = Field(..., description="Trading volume")


class DailyDataResponse(BaseAlphaVantageResponse):
    """Response schema for daily price data."""
    data: List[DailyDataPoint] = Field(..., description="Daily price data")
    outputsize: str = Field(..., description="Data output size used")


class IntradayDataPoint(BaseModel):
    """Intraday data point schema."""
    timestamp: str = Field(..., description="Timestamp")
    open: float = Field(..., description="Opening price")
    high: float = Field(..., description="Highest price")
    low: float = Field(..., description="Lowest price")
    close: float = Field(..., description="Closing price")
    volume: int = Field(..., description="Trading volume")


class IntradayDataResponse(BaseAlphaVantageResponse):
    """Response schema for intraday price data."""
    data: List[IntradayDataPoint] = Field(..., description="Intraday price data")
    interval: str = Field(..., description="Data interval")
    outputsize: str = Field(..., description="Data output size used")


class RateLimitUsage(BaseModel):
    """Rate limit usage information."""
    minute_calls: int = Field(..., description="Current minute API calls")
    minute_limit: int = Field(..., description="Minute API call limit")
    day_calls: int = Field(..., description="Current day API calls")
    day_limit: int = Field(..., description="Day API call limit")


class RateLimitResponse(BaseModel):
    """Response schema for rate limit information."""
    status: str = Field(..., description="API call status")
    data: RateLimitUsage = Field(..., description="Rate limit usage information")


class LatestPriceResponse(BaseAlphaVantageResponse):
    """Response schema for latest price data."""
    data: Optional[Dict[str, Any]] = Field(None, description="Latest price data")


class AlphaVantageStatus(BaseModel):
    """Alpha Vantage service status."""
    enabled: bool = Field(..., description="Whether Alpha Vantage is enabled")
    api_key_configured: bool = Field(..., description="Whether API key is configured")
    fallback_to_yahoo: bool = Field(..., description="Whether fallback to Yahoo is enabled")
    rate_minute_calls: Optional[int] = Field(None, description="Current minute API calls")
    rate_minute_limit: int = Field(..., description="Minute API call limit")
    rate_day_calls: Optional[int] = Field(None, description="Current day API calls")
    rate_day_limit: int = Field(..., description="Day API call limit")


class AlphaVantageStatusResponse(BaseModel):
    """Response schema for Alpha Vantage status."""
    status: str = Field(..., description="API call status")
    data: AlphaVantageStatus = Field(..., description="Alpha Vantage status information")