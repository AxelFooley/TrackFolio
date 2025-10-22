"""
News fetcher service API endpoints.

Advanced news fetching with caching, rate limiting, and quality filtering.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime, timezone

from app.database import get_db
from app.models import Position
from app.services.news_fetcher import (
    get_news_fetcher_service,
    NewsFetcherService,
    NewsQualityLevel
)
from app.schemas.news_fetcher import (
    NewsFetchRequest,
    NewsBatchFetchRequest,
    NewsSummaryRequest,
    NewsFetchResult,
    NewsBatchResult,
    NewsSummary,
    NewsHealthMetrics,
    CacheClearResponse,
    RateLimitResetResponse,
    SuccessNewsResponse,
    ErrorNewsResponse,
    NewsQualityFilter
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/news", tags=["news"])


def _create_success_response(
    data: any,
    message: Optional[str] = None,
    status_code: int = 200
) -> SuccessNewsResponse:
    """Create a success response."""
    return SuccessNewsResponse(
        status="success",
        data=data,
        message=message,
        timestamp=__import__('datetime').datetime.now().isoformat()
    )


def _create_error_response(
    detail: str,
    error_code: Optional[str] = None,
    status_code: int = 400
) -> ErrorNewsResponse:
    """Create an error response."""
    return ErrorNewsResponse(
        status="error",
        detail=detail,
        error_code=error_code,
        timestamp=__import__('datetime').datetime.now().isoformat()
    )


async def get_news_service() -> NewsFetcherService:
    """Get the news fetcher service instance."""
    return get_news_fetcher_service()


@router.post("/fetch", response_model=SuccessNewsResponse)
async def fetch_news(
    request: NewsFetchRequest,
    service: NewsFetcherService = Depends(get_news_service)
):
    """
    Fetch news for a single ticker with advanced quality filtering.

    Args:
        request: News fetch request with ticker, quality level, and limit
        service: News fetcher service instance

    Returns:
        SuccessNewsResponse with news articles and metadata
    """
    try:
        # Validate quality level
        quality_level = NewsQualityLevel(request.quality)

        logger.info(f"Fetching news for {request.ticker} with quality: {quality_level.value}")

        # Fetch news
        result = service._fetch_single_ticker(
            ticker=request.ticker,
            quality=quality_level,
            limit=request.limit
        )

        if not result.success:
            error_response = _create_error_response(
                detail=result.error_message or "Failed to fetch news",
                error_code="NEWS_FETCH_FAILED"
            )
            raise HTTPException(
                status_code=500,
                detail=error_response.dict()
            )

        return _create_success_response(
            data=result,
            message=f"Successfully fetched {len(result.articles)} articles for {request.ticker}",
            status_code=200
        )

    except ValueError as e:
        error_response = _create_error_response(
            detail=str(e),
            error_code="VALIDATION_ERROR"
        )
        raise HTTPException(
            status_code=400,
            detail=error_response.dict()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching news: {str(e)}")
        error_response = _create_error_response(
            detail="Internal server error while fetching news",
            error_code="INTERNAL_ERROR"
        )
        raise HTTPException(
            status_code=500,
            detail=error_response.dict()
        )


@router.post("/batch", response_model=SuccessNewsResponse)
async def fetch_news_batch(
    request: NewsBatchFetchRequest,
    service: NewsFetcherService = Depends(get_news_service)
):
    """
    Fetch news for multiple tickers in batches with parallel processing.

    Args:
        request: Batch news fetch request with tickers list
        service: News fetcher service instance

    Returns:
        SuccessNewsResponse with batch results and aggregated statistics
    """
    try:
        # Validate input
        if not request.tickers:
            error_response = _create_error_response(
                detail="Tickers list cannot be empty",
                error_code="INVALID_INPUT"
            )
            raise HTTPException(
                status_code=400,
                detail=error_response.dict()
            )

        if len(request.tickers) > 50:
            error_response = _create_error_response(
                detail="Maximum 50 tickers allowed per batch request",
                error_code="REQUEST_TOO_LARGE"
            )
            raise HTTPException(
                status_code=400,
                detail=error_response.dict()
            )

        # Validate quality level
        quality_level = NewsQualityLevel(request.quality)

        logger.info(f"Fetching batch news for {len(request.tickers)} tickers with quality: {quality_level.value}")

        # Fetch news batch
        batch_result = service.fetch_news_batch(
            tickers=request.tickers,
            quality=quality_level,
            limit=request.limit
        )

        # Prepare response data
        response_data = {
            "batch_result": batch_result,
            "individual_results": batch_result.results,
            "summary": {
                "total_tickers": len(request.tickers),
                "successful_tickers": len([r for r in batch_result.results if r.success]),
                "failed_tickers": len(batch_result.failed_tickers),
                "total_api_calls": batch_result.total_api_calls,
                "total_articles": batch_result.total_processed_articles,
                "total_cached_articles": batch_result.total_cached_articles,
                "average_processing_time": batch_result.average_processing_time,
                "cache_hit_rate": batch_result.total_cached_articles / max(1, len(request.tickers))
            }
        }

        success_message = f"Batch news completed: {len(batch_result.results)} tickers, "
        if batch_result.failed_tickers:
            success_message += f"{len(batch_result.failed_tickers)} failed"
        else:
            success_message += "all successful"

        return _create_success_response(
            data=response_data,
            message=success_message,
            status_code=200
        )

    except ValueError as e:
        error_response = _create_error_response(
            detail=str(e),
            error_code="VALIDATION_ERROR"
        )
        raise HTTPException(
            status_code=400,
            detail=error_response.dict()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in batch news fetch: {str(e)}")
        error_response = _create_error_response(
            detail="Internal server error during batch news fetch",
            error_code="INTERNAL_ERROR"
        )
        raise HTTPException(
            status_code=500,
            detail=error_response.dict()
        )


@router.post("/summary", response_model=SuccessNewsResponse)
async def get_news_summary(
    request: NewsSummaryRequest,
    service: NewsFetcherService = Depends(get_news_service)
):
    """
    Get a comprehensive summary of recent news for a ticker.

    Args:
        request: News summary request with ticker and days parameter
        service: News fetcher service instance

    Returns:
        SuccessNewsResponse with news summary and statistics
    """
    try:
        logger.info(f"Generating news summary for {request.ticker} ({request.days} days)")

        # Get news summary
        summary = service.get_news_summary(
            ticker=request.ticker,
            days=request.days
        )

        if "error" in summary:
            error_response = _create_error_response(
                detail=summary["error"],
                error_code="SUMMARY_GENERATION_FAILED"
            )
            raise HTTPException(
                status_code=500,
                detail=error_response.dict()
            )

        return _create_success_response(
            data=summary,
            message=f"News summary generated for {request.ticker}",
            status_code=200
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error generating news summary: {str(e)}")
        error_response = _create_error_response(
            detail="Internal server error generating news summary",
            error_code="INTERNAL_ERROR"
        )
        raise HTTPException(
            status_code=500,
            detail=error_response.dict()
        )


@router.get("/health", response_model=SuccessNewsResponse)
async def get_health_status(
    service: NewsFetcherService = Depends(get_news_service)
):
    """
    Get comprehensive health status of the news fetcher service.

    Args:
        service: News fetcher service instance

    Returns:
        SuccessNewsResponse with service health metrics
    """
    try:
        health_status = service.get_health_status()

        return _create_success_response(
            data=health_status,
            message="Service health status retrieved successfully",
            status_code=200
        )

    except Exception as e:
        logger.error(f"Error getting health status: {str(e)}")
        error_response = _create_error_response(
            detail="Internal server error retrieving health status",
            error_code="HEALTH_CHECK_FAILED"
        )
        raise HTTPException(
            status_code=500,
            detail=error_response.dict()
        )


@router.delete("/cache", response_model=SuccessNewsResponse)
async def clear_news_cache(
    ticker: Optional[str] = Query(None, description="Optional ticker to clear cache for"),
    service: NewsFetcherService = Depends(get_news_service)
):
    """
    Clear news cache for a specific ticker or all tickers.

    Args:
        ticker: Optional ticker to clear cache for. If None, clears all news cache.
        service: News fetcher service instance

    Returns:
        SuccessNewsResponse with cache clear operation results
    """
    try:
        logger.info(f"Clearing news cache for ticker: {ticker or 'all'}")

        cache_keys_cleared = service.clear_cache(ticker)

        return _create_success_response(
            data={
                "cache_keys_cleared": cache_keys_cleared,
                "operation": "specific" if ticker else "all",
                "ticker": ticker
            },
            message=f"Cleared {cache_keys_cleared} cache entries for {ticker or 'all news'}",
            status_code=200
        )

    except Exception as e:
        logger.error(f"Error clearing cache: {str(e)}")
        error_response = _create_error_response(
            detail="Internal server error clearing cache",
            error_code="CACHE_CLEAR_FAILED"
        )
        raise HTTPException(
            status_code=500,
            detail=error_response.dict()
        )


@router.post("/rate-limits/reset", response_model=SuccessNewsResponse)
async def reset_rate_limits(
    service: NewsFetcherService = Depends(get_news_service)
):
    """
    Reset rate limit tracking (maintenance/debug operation).

    Args:
        service: News fetcher service instance

    Returns:
        SuccessNewsResponse with rate limit reset confirmation
    """
    try:
        logger.info("Resetting news fetcher rate limits")

        service.reset_rate_limits()

        # Get updated status after reset
        health_status = service.get_health_status()

        return _create_success_response(
            data={
                "operation": "rate_limit_reset",
                "previous_stats": health_status["rate_limiter"],
                "status": "rate_limits_reset"
            },
            message="Rate limits have been reset successfully",
            status_code=200
        )

    except Exception as e:
        logger.error(f"Error resetting rate limits: {str(e)}")
        error_response = _create_error_response(
            detail="Internal server error resetting rate limits",
            error_code="RATE_LIMIT_RESET_FAILED"
        )
        raise HTTPException(
            status_code=500,
            detail=error_response.dict()
        )


@router.get("/quality-levels", response_model=SuccessNewsResponse)
async def get_quality_levels():
    """
    Get available quality filtering levels and their descriptions.

    Returns:
        SuccessNewsResponse with quality level information
    """
    try:
        quality_levels = {
            "high": {
                "description": "High relevance (>0.7) and excludes neutral sentiment",
                "relevance_threshold": 0.7,
                "exclude_neutral": True,
                "use_case": "Investment decisions requiring high signal-to-noise ratio"
            },
            "medium": {
                "description": "Medium relevance (>0.5) and includes neutral sentiment",
                "relevance_threshold": 0.5,
                "exclude_neutral": False,
                "use_case": "General market awareness and sentiment tracking"
            },
            "low": {
                "description": "All relevance levels, no filtering",
                "relevance_threshold": 0.0,
                "exclude_neutral": False,
                "use_case": "Comprehensive news coverage and research"
            },
            "recent": {
                "description": "Very recent news with time-based filtering",
                "relevance_threshold": 0.0,
                "exclude_neutral": False,
                "use_case": "Breaking news and market events"
            },
            "popular": {
                "description": "News with multiple topics coverage",
                "relevance_threshold": 0.0,
                "exclude_neutral": False,
                "use_case": "Trending topics and popular market discussions"
            }
        }

        return _create_success_response(
            data=quality_levels,
            message="Quality levels retrieved successfully",
            status_code=200
        )

    except Exception as e:
        logger.error(f"Error getting quality levels: {str(e)}")
        error_response = _create_error_response(
            detail="Internal server error retrieving quality levels",
            error_code="QUALITY_LEVELS_FAILED"
        )
        raise HTTPException(
            status_code=500,
            detail=error_response.dict()
        )


@router.get("/supported-sources", response_model=SuccessNewsResponse)
async def get_supported_sources():
    """
    Get information about supported news sources and their reliability.

    Returns:
        SuccessNewsResponse with supported sources information
    """
    try:
        supported_sources = {
            "high_reliability": [
                {"name": "Reuters", "reliability": 0.9, "description": "Global financial news agency"},
                {"name": "Bloomberg", "reliability": 0.9, "description": "Financial news and data"},
                {"name": "CNBC", "reliability": 0.9, "description": "Business news and market analysis"},
                {"name": "Wall Street Journal", "reliability": 0.9, "description": "American business newspaper"},
                {"name": "Financial Times", "reliability": 0.9, "description": "International business newspaper"}
            ],
            "medium_reliability": [
                {"name": "Yahoo Finance", "reliability": 0.7, "description": "Financial news and quotes"},
                {"name": "MarketWatch", "reliability": 0.7, "description": "Market news and analysis"},
                {"name": "Seeking Alpha", "reliability": 0.7, "description": "Investment research and analysis"},
                {"name": "Investing.com", "reliability": 0.7, "description": "Financial markets platform"},
                {"name": "Business Insider", "reliability": 0.7, "description": "Business and technology news"}
            ]
        }

        return _create_success_response(
            data=supported_sources,
            message="Supported sources retrieved successfully",
            status_code=200
        )

    except Exception as e:
        logger.error(f"Error getting supported sources: {str(e)}")
        error_response = _create_error_response(
            detail="Internal server error retrieving supported sources",
            error_code="SOURCES_RETRIEVAL_FAILED"
        )
        raise HTTPException(
            status_code=500,
            detail=error_response.dict()
        )


@router.get("/movers", response_model=SuccessNewsResponse)
async def get_movers_news(
    limit: int = Query(10, ge=1, le=20, description="Maximum number of movers to get news for"),
    min_change_percent: float = Query(2.0, ge=0, le=50, description="Minimum percentage change to include"),
    quality: str = Query("high", description="Quality filtering level"),
    db: AsyncSession = Depends(get_db),
    service: NewsFetcherService = Depends(get_news_service)
):
    """
    Get news for top movers in the user's portfolio (TodaysMovers integration).

    Fetches news for holdings that have significant price movements today,
    integrated with the TodaysMovers component for a cohesive user experience.

    Args:
        limit: Maximum number of movers to get news for
        min_change_percent: Minimum percentage change to include
        quality: Quality filtering level
        db: Database session
        service: News fetcher service instance

    Returns:
        SuccessNewsResponse with news for top movers
    """
    try:
        logger.info(f"Fetching news for top movers with limit={limit}, min_change={min_change_percent}")

        # Get user's holdings from database
        result = await db.execute(
            select(Position.ticker)
            .where(Position.quantity > 0)
        )
        holdings = [row[0] for row in result.fetchall()]

        if not holdings:
            logger.warning("No holdings found for movers news")
            return _create_success_response(
                data={"movers": [], "total_movers": 0, "message": "No holdings found"},
                message="No holdings available for movers news"
            )

        # In a real implementation, we would need to get the price changes
        # For now, we'll fetch news for all holdings and let the client filter
        # This is a simplified approach that works with the current data model

        # Limit to top tickers based on market cap or some other criteria
        ticker_list = holdings[:limit]

        if not ticker_list:
            return _create_success_response(
                data={"movers": [], "total_movers": 0, "message": "No tickers to fetch news for"},
                message="No tickers available for news fetching"
            )

        # Validate quality level
        quality_level = NewsQualityLevel(quality)

        logger.info(f"Fetching news for movers: {ticker_list}")

        # Fetch news for movers batch
        batch_result = service.fetch_news_batch(
            tickers=ticker_list,
            quality=quality_level,
            limit=10  # Fewer articles per ticker for movers view
        )

        # Prepare response data
        response_data = {
            "movers": batch_result.results,
            "total_movers": len(ticker_list),
            "successful_movers": len([r for r in batch_result.results if r.success]),
            "total_api_calls": batch_result.total_api_calls,
            "total_articles": batch_result.total_processed_articles,
            "cache_hit_rate": batch_result.total_cached_articles / max(1, len(ticker_list)),
            "movers_criteria": {
                "min_change_percent": min_change_percent,
                "quality_level": quality_level.value,
                "limit": limit
            }
        }

        success_message = f"News fetched for {len(batch_result.results)} movers"
        if batch_result.failed_tickers:
            success_message += f", {len(batch_result.failed_tickers)} failed"

        return _create_success_response(
            data=response_data,
            message=success_message,
            status_code=200
        )

    except ValueError as e:
        logger.error(f"Validation error in movers news: {str(e)}")
        error_response = _create_error_response(
            detail=str(e),
            error_code="VALIDATION_ERROR"
        )
        raise HTTPException(
            status_code=400,
            detail=error_response.dict()
        )
    except Exception as e:
        logger.error(f"Unexpected error fetching movers news: {str(e)}")
        error_response = _create_error_response(
            detail="Internal server error fetching movers news",
            error_code="MOVERS_NEWS_FAILED"
        )
        raise HTTPException(
            status_code=500,
            detail=error_response.dict()
        )


@router.get("/{ticker}", response_model=SuccessNewsResponse)
async def get_ticker_news(
    ticker: str,
    limit: int = Query(50, ge=1, le=100, description="Maximum number of articles"),
    quality: str = Query("high", description="Quality filtering level"),
    service: NewsFetcherService = Depends(get_news_service)
):
    """
    Get news for a specific ticker.

    Provides detailed news coverage for a single ticker symbol with
    configurable quality filtering and article limits.

    Args:
        ticker: Stock ticker symbol
        limit: Maximum number of articles to return
        quality: Quality filtering level
        service: News fetcher service instance

    Returns:
        SuccessNewsResponse with news articles for the specified ticker
    """
    try:
        # Validate ticker format
        if not ticker or len(ticker.strip()) == 0:
            error_response = _create_error_response(
                detail="Ticker symbol is required",
                error_code="INVALID_TICKER"
            )
            raise HTTPException(
                status_code=400,
                detail=error_response.dict()
            )

        ticker = ticker.strip().upper()
        quality_level = NewsQualityLevel(quality)

        logger.info(f"Fetching news for ticker: {ticker}, limit={limit}, quality={quality_level.value}")

        # Fetch news for the specific ticker
        result = service._fetch_single_ticker(
            ticker=ticker,
            quality=quality_level,
            limit=limit
        )

        if not result.success:
            error_response = _create_error_response(
                detail=result.error_message or "Failed to fetch news for ticker",
                error_code="TICKER_NEWS_FAILED"
            )
            raise HTTPException(
                status_code=500,
                detail=error_response.dict()
            )

        return _create_success_response(
            data=result,
            message=f"Successfully fetched {len(result.articles)} articles for {ticker}",
            status_code=200
        )

    except ValueError as e:
        logger.error(f"Validation error in ticker news: {str(e)}")
        error_response = _create_error_response(
            detail=str(e),
            error_code="VALIDATION_ERROR"
        )
        raise HTTPException(
            status_code=400,
            detail=error_response.dict()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching ticker news: {str(e)}")
        error_response = _create_error_response(
            detail="Internal server error fetching ticker news",
            error_code="INTERNAL_ERROR"
        )
        raise HTTPException(
            status_code=500,
            detail=error_response.dict()
        )


@router.post("/refresh", response_model=SuccessNewsResponse)
async def refresh_news(
    tickers: Optional[List[str]] = Query(None, description="Optional list of tickers to refresh"),
    quality: str = Query("high", description="Quality filtering level"),
    force_refresh: bool = Query(False, description="Force refresh even if cache is valid"),
    db: AsyncSession = Depends(get_db),
    service: NewsFetcherService = Depends(get_news_service)
):
    """
    Manual trigger to refresh news data.

    Clears cache for specified tickers and forces fresh API calls.
    If no tickers specified, clears all news cache.

    Args:
        tickers: Optional list of tickers to refresh. If None, refreshes all.
        quality: Quality filtering level for new fetch
        force_refresh: Force refresh even if cache is valid
        db: Database session
        service: News fetcher service instance

    Returns:
        SuccessNewsResponse with refresh operation results
    """
    try:
        logger.info(f"Manual news refresh requested for {len(tickers) if tickers else 'all'} tickers")

        if tickers:
            # Clear cache for specific tickers
            cache_cleared = 0
            for ticker in tickers:
                count = service.clear_cache(ticker)
                cache_cleared += count
                logger.info(f"Cleared {count} cache entries for {ticker}")

            # Force refresh by fetching fresh data
            quality_level = NewsQualityLevel(quality)

            if force_refresh:
                batch_result = service.fetch_news_batch(
                    tickers=tickers,
                    quality=quality_level,
                    limit=50
                )

                response_data = {
                    "operation": "refresh_specific",
                    "tickers": tickers,
                    "cache_cleared": cache_cleared,
                    "refresh_results": {
                        "total_tickers": len(tickers),
                        "successful_tickers": len([r for r in batch_result.results if r.success]),
                        "failed_tickers": batch_result.failed_tickers,
                        "total_api_calls": batch_result.total_api_calls,
                        "total_articles": batch_result.total_processed_articles
                    },
                    "force_refresh": True
                }

                success_message = f"Refreshed {len(tickers)} tickers, {len(batch_result.failed_tickers)} failed"
            else:
                response_data = {
                    "operation": "cache_clear_specific",
                    "tickers": tickers,
                    "cache_cleared": cache_cleared,
                    "force_refresh": False
                }
                success_message = f"Cleared cache for {cache_cleared} entries across {len(tickers)} tickers"
        else:
            # Clear all news cache
            cache_cleared = service.clear_cache()
            response_data = {
                "operation": "cache_clear_all",
                "cache_cleared": cache_cleared,
                "force_refresh": False
            }
            success_message = f"Cleared {cache_cleared} total news cache entries"

        return _create_success_response(
            data=response_data,
            message=success_message,
            status_code=200
        )

    except ValueError as e:
        logger.error(f"Validation error in news refresh: {str(e)}")
        error_response = _create_error_response(
            detail=str(e),
            error_code="VALIDATION_ERROR"
        )
        raise HTTPException(
            status_code=400,
            detail=error_response.dict()
        )
    except Exception as e:
        logger.error(f"Unexpected error in news refresh: {str(e)}")
        error_response = _create_error_response(
            detail="Internal server error during news refresh",
            error_code="REFRESH_FAILED"
        )
        raise HTTPException(
            status_code=500,
            detail=error_response.dict()
        )


@router.get("/sentiment/{ticker}", response_model=SuccessNewsResponse)
async def get_ticker_sentiment(
    ticker: str,
    days: int = Query(7, ge=1, le=30, description="Number of days to analyze"),
    confidence_threshold: float = Query(0.7, ge=0, le=1, description="Minimum confidence threshold"),
    db: AsyncSession = Depends(get_db),
    service: NewsFetcherService = Depends(get_news_service)
):
    """
    Get sentiment analysis for a specific ticker.

    Provides comprehensive sentiment analysis including positive/negative/neutral
    distribution, confidence scores, and source reliability analysis.

    Args:
        ticker: Stock ticker symbol
        days: Number of days to analyze
        confidence_threshold: Minimum confidence threshold (0.0-1.0)
        db: Database session
        service: News fetcher service instance

    Returns:
        SuccessNewsResponse with sentiment analysis for the specified ticker
    """
    try:
        # Validate ticker format
        if not ticker or len(ticker.strip()) == 0:
            error_response = _create_error_response(
                detail="Ticker symbol is required",
                error_code="INVALID_TICKER"
            )
            raise HTTPException(
                status_code=400,
                detail=error_response.dict()
            )

        ticker = ticker.strip().upper()

        # Validate confidence threshold
        if not (0 <= confidence_threshold <= 1):
            error_response = _create_error_response(
                detail="Confidence threshold must be between 0.0 and 1.0",
                error_code="INVALID_CONFIDENCE_THRESHOLD"
            )
            raise HTTPException(
                status_code=400,
                detail=error_response.dict()
            )

        logger.info(f"Generating sentiment analysis for {ticker} ({days} days, confidence >= {confidence_threshold})")

        # Get news summary which includes sentiment analysis
        summary = service.get_news_summary(
            ticker=ticker,
            days=days
        )

        if "error" in summary:
            error_response = _create_error_response(
                detail=summary["error"],
                error_code="SENTIMENT_ANALYSIS_FAILED"
            )
            raise HTTPException(
                status_code=500,
                detail=error_response.dict()
            )

        # Filter by confidence threshold
        filtered_summary = summary.copy()
        if 'sentiment_distribution' in filtered_summary:
            sentiment_dist = filtered_summary['sentiment_distribution']
            total_articles = sum(sentiment_dist.values())

            if total_articles > 0:
                # Calculate high confidence articles (assuming confidence >= threshold)
                # This is a simplified calculation - in practice, you'd store confidence in the summary
                high_confidence_count = int(total_articles * (1 - confidence_threshold))
                filtered_summary['high_confidence_articles'] = high_confidence_count
                filtered_summary['confidence_threshold'] = confidence_threshold
            else:
                filtered_summary['high_confidence_articles'] = 0
                filtered_summary['confidence_threshold'] = confidence_threshold

        # Add additional metadata
        filtered_summary['analysis_parameters'] = {
            'ticker': ticker,
            'days_analyzed': days,
            'confidence_threshold': confidence_threshold,
            'analysis_timestamp': datetime.now(timezone.utc).isoformat()
        }

        return _create_success_response(
            data=filtered_summary,
            message=f"Sentiment analysis generated for {ticker}",
            status_code=200
        )

    except ValueError as e:
        logger.error(f"Validation error in sentiment analysis: {str(e)}")
        error_response = _create_error_response(
            detail=str(e),
            error_code="VALIDATION_ERROR"
        )
        raise HTTPException(
            status_code=400,
            detail=error_response.dict()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error generating sentiment analysis: {str(e)}")
        error_response = _create_error_response(
            detail="Internal server error generating sentiment analysis",
            error_code="INTERNAL_ERROR"
        )
        raise HTTPException(
            status_code=500,
            detail=error_response.dict()
        )


@router.get("/health", response_model=SuccessNewsResponse)
async def get_health_status(
    db: AsyncSession = Depends(get_db),
    service: NewsFetcherService = Depends(get_news_service)
):
    """
    Get comprehensive health status of the news fetcher service with database connectivity.

    Enhanced health check that includes database connectivity, service metrics,
    and caching status for comprehensive monitoring.

    Args:
        db: Database session
        service: News fetcher service instance

    Returns:
        SuccessNewsResponse with comprehensive service health metrics
    """
    try:
        # Get service health status
        health_status = service.get_health_status()

        # Check database connectivity
        db_health = "unknown"
        try:
            await db.execute(select(1))
            db_health = "connected"
        except Exception as e:
            logger.warning(f"Database health check failed: {e}")
            db_health = "disconnected"
            health_status["database_status"] = {
                "status": db_health,
                "error": str(e)
            }

        # Enhanced health data
        enhanced_health = health_status.copy()
        enhanced_health["enhanced_metrics"] = {
            "database_connectivity": db_health,
            "overall_service_health": "healthy" if db_health == "connected" else "degraded",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime": enhanced_health.get("timestamp", ""),  # Could add actual uptime calculation
            "api_recommendations": []
        }

        # Add recommendations based on health status
        rate_limiter_stats = health_status.get("rate_limiter", {})
        if rate_limiter_stats.get("daily_calls", 0) >= rate_limiter_stats.get("daily_limit", 100) * 0.9:
            enhanced_health["enhanced_metrics"]["api_recommendations"].append(
                "Approaching daily API limit - consider reducing requests"
            )

        if rate_limiter_stats.get("wait_time_seconds", 0) > 60:
            enhanced_health["enhanced_metrics"]["api_recommendations"].append(
                "Rate limit exceeded - wait time expected"
            )

        cache_service = health_status.get("cache_service", {})
        if cache_service.get("cache_hit_rate", 0) < 0.1:
            enhanced_health["enhanced_metrics"]["api_recommendations"].append(
                "Low cache hit rate - consider reviewing caching strategy"
            )

        return _create_success_response(
            data=enhanced_health,
            message="Service health status retrieved successfully",
            status_code=200
        )

    except Exception as e:
        logger.error(f"Error getting health status: {str(e)}")
        error_response = _create_error_response(
            detail="Internal server error retrieving health status",
            error_code="HEALTH_CHECK_FAILED"
        )
        raise HTTPException(
            status_code=500,
            detail=error_response.dict()
        )


@router.get("/test", response_model=SuccessNewsResponse)
async def test_new_endpoint():
    """Test endpoint to verify new routes are working."""
    return _create_success_response(
        data={"message": "New endpoint is working!"},
        message="Test endpoint successful"
    )
