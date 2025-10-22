"""
News fetcher service response schemas.
"""
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field, validator
from decimal import Decimal
from datetime import datetime


class NewsQualityFilter(BaseModel):
    """Quality filtering options for news articles."""
    level: str = Field(..., description="Quality filtering level")

    @validator('level')
    def validate_level(cls, v):
        valid_levels = ['high', 'medium', 'low', 'recent', 'popular']
        if v not in valid_levels:
            raise ValueError(f"Invalid quality level. Must be one of: {valid_levels}")
        return v


class NewsArticleDetail(BaseModel):
    """Detailed news article schema with enrichment metadata."""
    title: Optional[str] = Field(None, description="Article title")
    url: Optional[str] = Field(None, description="Article URL")
    source: Optional[str] = Field(None, description="News source")
    source_name: Optional[str] = Field(None, description="Source name/organization")
    time: Optional[str] = Field(None, description="Article publication time")
    summary: Optional[str] = Field(None, description="Article summary")
    banner_image: Optional[str] = Field(None, description="Banner image URL")
    topics: List[Dict[str, Any]] = Field(default_factory=list, description="Article topics")
    overall_sentiment_score: Optional[float] = Field(None, description="Overall sentiment score")
    overall_sentiment_label: Optional[str] = Field(None, description="Sentiment label")

    # Enrichment fields
    enriched_at: str = Field(..., description="When article was enriched")
    quality_score: float = Field(..., description="Quality score (0.0-1.0)")
    relevance_score: float = Field(..., description="Relevance score (0.0-1.0)")
    word_count: int = Field(..., description="Number of words in content")
    has_image: bool = Field(..., description="Whether article has image")
    topic_count: int = Field(..., description="Number of topics covered")
    source_reliability: float = Field(..., description="Source reliability score (0.0-1.0)")


class NewsFetchResult(BaseModel):
    """Individual ticker news fetch result."""
    ticker: str = Field(..., description="Stock ticker symbol")
    articles: List[NewsArticleDetail] = Field(..., description="Processed news articles")
    success: bool = Field(..., description="Whether the fetch was successful")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    api_calls_made: int = Field(0, description="Number of API calls made")
    cached_articles: int = Field(0, description="Number of articles from cache")
    processed_articles: int = Field(0, description="Number of articles after filtering")
    filter_applied: bool = Field(False, description="Whether quality filtering was applied")


class NewsFilterStats(BaseModel):
    """News filtering statistics."""
    total: int = Field(..., description="Total articles before filtering")
    filtered_out: int = Field(..., description="Articles filtered out")
    relevance_scores: List[float] = Field(default_factory=list, description="Relevance scores")
    sentiment_distribution: Dict[str, int] = Field(
        default_factory=dict, description="Sentiment distribution"
    )


class NewsBatchResult(BaseModel):
    """Batch news fetch result."""
    results: List[NewsFetchResult] = Field(..., description="Individual ticker results")
    total_api_calls: int = Field(..., description="Total API calls across all tickers")
    total_cached_articles: int = Field(..., description="Total articles from cache")
    total_processed_articles: int = Field(..., description="Total articles after filtering")
    failed_tickers: List[str] = Field(default_factory=list, description="Tickers that failed")
    average_processing_time: float = Field(..., description="Average processing time per ticker")
    batch_size: int = Field(..., description="Total number of tickers requested")


class NewsSentimentSummary(BaseModel):
    """Sentiment analysis summary for a ticker."""
    positive_sentiment: int = Field(0, description="Number of positive articles")
    negative_sentiment: int = Field(0, description="Number of negative articles")
    neutral_sentiment: int = Field(0, description="Number of neutral articles")
    overall_sentiment: str = Field("neutral", description="Overall sentiment classification")
    confidence_score: float = Field(0.0, description="Confidence in sentiment analysis")


class NewsSourceSummary(BaseModel):
    """News source summary."""
    source_name: str = Field(..., description="Source name")
    article_count: int = Field(..., description="Number of articles from this source")
    average_reliability: float = Field(..., description="Average source reliability")
    most_recent_article: Optional[datetime] = Field(None, description="Most recent article")


class NewsSummary(BaseModel):
    """Comprehensive news summary for a ticker."""
    ticker: str = Field(..., description="Stock ticker symbol")
    total_articles: int = Field(..., description="Total articles found")
    total_api_calls: int = Field(0, description="API calls made")
    filtered_articles: int = Field(0, description="Articles after filtering")
    average_relevance: float = Field(0.0, description="Average relevance score")
    sentiment_summary: NewsSentimentSummary = Field(..., description="Sentiment analysis")
    top_sources: List[NewsSourceSummary] = Field(..., description="Top news sources")
    recent_articles: List[NewsArticleDetail] = Field(..., description="Recent articles")
    summary_generated_at: str = Field(..., description="When summary was generated")
    quality_tier: str = Field("high", description="Quality tier used")


class NewsHealthMetrics(BaseModel):
    """Service health and performance metrics."""
    service_name: str = Field(..., description="Service name")
    status: str = Field(..., description="Service status")
    timestamp: str = Field(..., description="Health check timestamp")
    rate_limiter: Dict[str, Any] = Field(..., description="Rate limiter statistics")
    cache_service: Dict[str, Any] = Field(..., description="Cache service status")
    configuration: Dict[str, Any] = Field(..., description="Service configuration")
    quality_thresholds: Dict[str, float] = Field(..., description="Quality filtering thresholds")


class CacheClearResponse(BaseModel):
    """Response for cache clear operation."""
    status: str = Field(..., description="Operation status")
    ticker: Optional[str] = Field(None, description="Ticker if cleared specific cache")
    cache_keys_cleared: int = Field(..., description="Number of cache keys cleared")
    operation: str = Field(..., description="Operation performed")


class RateLimitResetResponse(BaseModel):
    """Response for rate limit reset operation."""
    status: str = Field(..., description="Operation status")
    message: str = Field(..., description="Reset confirmation message")
    rate_limiter_stats: Dict[str, Any] = Field(..., description="Rate limiter statistics after reset")


class NewsFetchRequest(BaseModel):
    """Request schema for news fetching."""
    ticker: str = Field(..., description="Stock ticker symbol")
    quality: str = Field("high", description="Quality filtering level")
    limit: int = Field(50, ge=1, le=100, description="Maximum number of articles")


class NewsBatchFetchRequest(BaseModel):
    """Request schema for batch news fetching."""
    tickers: List[str] = Field(..., description="List of stock ticker symbols")
    quality: str = Field("high", description="Quality filtering level")
    limit: int = Field(50, ge=1, le=100, description="Maximum articles per ticker")


class NewsSummaryRequest(BaseModel):
    """Request schema for news summary."""
    ticker: str = Field(..., description="Stock ticker symbol")
    days: int = Field(7, ge=1, le=30, description="Number of days to look back")


class BaseNewsResponse(BaseModel):
    """Base response schema for news endpoints."""
    status: str = Field(..., description="API call status")
    message: Optional[str] = Field(None, description="Response message")
    timestamp: str = Field(..., description="Response timestamp")


class SuccessNewsResponse(BaseNewsResponse):
    """Successful news response."""
    data: Union[NewsFetchResult, NewsBatchResult, NewsSummary, NewsHealthMetrics, Dict[str, Any]] = Field(..., description="Response data")


class ErrorNewsResponse(BaseNewsResponse):
    """Error news response."""
    detail: str = Field(..., description="Error details")
    error_code: Optional[str] = Field(None, description="Error code")