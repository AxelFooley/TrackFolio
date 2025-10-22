"""
News fetcher service for Alpha Vantage API with advanced caching and rate limiting.

This service provides comprehensive news fetching capabilities with:
- Token bucket rate limiting to prevent API limit bursts
- Smart caching strategies with multiple TTL tiers
- Batch processing for multiple tickers
- Data filtering for high-quality news
- Error handling with exponential backoff
- Health monitoring and usage tracking
"""
import asyncio
import hashlib
import logging
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Any, Set, Tuple
from enum import Enum
import threading
from dataclasses import dataclass
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.config import settings
from app.services.cache import CacheService
from app.models.news import NewsArticle, NewsTickerSentiment, SentimentType, NewsSource

logger = logging.getLogger(__name__)


class NewsQualityLevel(str, Enum):
    """News quality filtering levels."""
    HIGH = "high"  # relevance > 0.7, excludes neutral
    MEDIUM = "medium"  # relevance > 0.5, includes neutral
    LOW = "low"  # all relevance levels
    RECENT = "recent"  # only very recent news
    POPULAR = "popular"  # based on topics coverage


@dataclass
class NewsFetchResult:
    """Container for news fetch results."""
    ticker: str
    articles: List[Dict[str, Any]]
    success: bool
    error_message: Optional[str] = None
    api_calls_made: int = 0
    cached_articles: int = 0
    processed_articles: int = 0
    filter_applied: bool = False


@dataclass
class NewsBatchResult:
    """Container for batch news fetch results."""
    results: List[NewsFetchResult]
    total_api_calls: int
    total_cached_articles: int
    total_processed_articles: int
    failed_tickers: List[str]
    average_processing_time: float
    batch_size: int


class TokenBucket:
    """
    Token bucket rate limiter implementation.

    Prevents API limit bursts by managing tokens in a bucket that refills
    at a constant rate. Alpha Vantage allows 5 calls/minute and 25 calls/day.
    """

    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate  # tokens per second
        self.tokens = capacity
        self.last_refill = time.time()
        self._lock = threading.Lock()

    def consume(self, tokens: int = 1) -> bool:
        """Consume tokens from bucket if available."""
        current_time = time.time()

        with self._lock:
            # Refill tokens based on time elapsed
            time_passed = current_time - self.last_refill
            tokens_to_add = time_passed * self.refill_rate
            self.tokens = min(self.capacity, self.tokens + tokens_to_add)

            # Try to consume tokens
            if self.tokens >= tokens:
                self.tokens -= tokens
                self.last_refill = current_time
                return True

            return False

    def get_tokens_available(self) -> float:
        """Get current available tokens."""
        current_time = time.time()
        with self._lock:
            time_passed = current_time - self.last_refill
            tokens_to_add = time_passed * self.refill_rate
            return min(self.capacity, self.tokens + tokens_to_add)

    def get_wait_time(self, tokens_needed: int = 1) -> float:
        """Calculate wait time until enough tokens are available."""
        if tokens_needed <= self.get_tokens_available():
            return 0.0

        tokens_needed = max(0, tokens_needed - self.get_tokens_available())
        return tokens_needed / self.refill_rate


class NewsRateLimiter:
    """
    Multi-layered rate limiter for Alpha Vantage news API.

    Handles both per-minute and per-day rate limits.
    """

    def __init__(self):
        # Alpha Vantage limits: 5 calls/minute, 25 calls/day
        self.minute_bucket = TokenBucket(capacity=5, refill_rate=5/60)  # 5 tokens per minute
        self.day_bucket = TokenBucket(capacity=25, refill_rate=25/(24*3600))  # 25 tokens per day

        # Usage tracking
        self.daily_calls = 0
        self.minute_calls = 0
        self.last_reset_time = time.time()
        self.last_minute_reset = time.time()

        # Cache tracking
        self.cache_hits = 0
        self.cache_misses = 0

        self._lock = threading.Lock()

    def can_make_request(self) -> bool:
        """Check if we can make an API call without exceeding rate limits."""
        current_time = time.time()

        with self._lock:
            # Reset minute counter if more than 60 seconds have passed
            if current_time - self.last_minute_reset >= 60:
                self.minute_calls = 0
                self.last_minute_reset = current_time

            # Check daily limit
            if self.daily_calls >= settings.alpha_vantage_requests_per_day:
                logger.debug(f"Daily rate limit reached: {self.daily_calls}/{settings.alpha_vantage_requests_per_day}")
                return False

            # Check minute limit
            if self.minute_calls >= settings.alpha_vantage_requests_per_minute:
                logger.debug(f"Minute rate limit reached: {self.minute_calls}/{settings.alpha_vantage_requests_per_minute}")
                return False

            return True

    def record_request(self) -> None:
        """Record that an API call was made."""
        with self._lock:
            self.minute_calls += 1
            self.daily_calls += 1
            logger.debug(f"Recorded API call: minute={self.minute_calls}, day={self.daily_calls}")

    def record_cache_hit(self) -> None:
        """Record a cache hit."""
        with self._lock:
            self.cache_hits += 1

    def record_cache_miss(self) -> None:
        """Record a cache miss."""
        with self._lock:
            self.cache_misses += 1

    def get_wait_time(self) -> float:
        """Calculate how long to wait before making the next request."""
        if self.can_make_request():
            return 0.0

        # Wait based on day limit
        if self.daily_calls >= settings.alpha_vantage_requests_per_day:
            next_day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            wait_time = (next_day - datetime.now()).total_seconds()
            return wait_time

        # Wait based on minute limit
        if self.minute_calls >= settings.alpha_vantage_requests_per_minute:
            time_since_last_minute_reset = time.time() - self.last_minute_reset
            wait_time = max(0, 60 - time_since_last_minute_reset)
            return wait_time

        return 0.0

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get current rate limiter statistics."""
        return {
            "daily_calls": self.daily_calls,
            "daily_limit": settings.alpha_vantage_requests_per_day,
            "minute_calls": self.minute_calls,
            "minute_limit": settings.alpha_vantage_requests_per_minute,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": self.cache_hits / max(1, self.cache_hits + self.cache_misses),
            "wait_time_seconds": self.get_wait_time()
        }


class NewsFetcherService:
    """
    Advanced news fetching service with smart caching, rate limiting, and filtering.

    Features:
    - Token bucket rate limiting
    - Multi-tier caching strategy
    - Batch processing for multiple tickers
    - Quality-based filtering
    - Exponential backoff retry logic
    - Comprehensive error handling
    """

    # Cache TTL settings (in seconds)
    CACHE_TIER_1 = 900   # 15 minutes - very fresh news
    CACHE_TIER_2 = 3600  # 1 hour - recent news
    CACHE_TIER_3 = 86400  # 24 hours - general news
    BATCH_CACHE_TTL = 600  # 10 minutes for batch results

    # Quality filtering thresholds
    HIGH_RELEVANCE_THRESHOLD = Decimal('0.7')
    MEDIUM_RELEVANCE_THRESHOLD = Decimal('0.5')
    CONFIDENCE_THRESHOLD = Decimal('0.8')

    # API settings
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 1.0
    MAX_RETRY_DELAY = 30.0

    def __init__(self):
        self.rate_limiter = NewsRateLimiter()
        self.cache_service = CacheService()
        self.session = requests.Session()

        # Session configuration
        self.session.headers.update({
            'User-Agent': 'TrackFolio-News-Fetcher/1.0',
            'Accept': 'application/json',
        })

        # Batch processing settings
        self.max_batch_size = 5  # Alpha Vantage limit
        self.max_concurrent_requests = 3

        logger.info("NewsFetcherService initialized successfully")

    def _generate_cache_key(self, ticker: str, quality: str = "default", limit: int = 50) -> str:
        """Generate cache key for news request."""
        key_components = [ticker.lower()]
        if quality != "default":
            key_components.append(f"qual:{quality}")
        key_components.append(f"limit:{limit}")
        return f"news:fetch:{':'.join(key_components)}"

    def _generate_batch_cache_key(self, tickers: List[str], quality: str = "default") -> str:
        """Generate cache key for batch news request."""
        ticker_key = ":".join(sorted([t.lower() for t in tickers]))
        return f"news:batch:{ticker_key}:qual:{quality}"

    def _should_filter_out_article(self, article: Dict[str, Any], quality: NewsQualityLevel) -> bool:
        """
        Determine if an article should be filtered out based on quality settings.

        Args:
            article: Article data from API
            quality: Quality filtering level

        Returns:
            True if article should be filtered out
        """
        if quality == NewsQualityLevel.LOW:
            return False

        # Check relevance score
        relevance = article.get('overall_sentiment_score', 0)
        if isinstance(relevance, str):
            try:
                relevance = Decimal(relevance)
            except (ValueError, TypeError):
                relevance = Decimal('0.5')  # Default to medium

        # Check sentiment label
        sentiment_label = article.get('overall_sentiment_label', '').lower()

        if quality == NewsQualityLevel.HIGH:
            # High quality: relevance > 0.7 and exclude neutral sentiment
            if relevance < self.HIGH_RELEVANCE_THRESHOLD:
                return True
            return sentiment_label == 'neutral'

        elif quality == NewsQualityLevel.MEDIUM:
            # Medium quality: relevance > 0.5, include neutral
            return relevance < self.MEDIUM_RELEVANCE_THRESHOLD

        elif quality == NewsQualityLevel.RECENT:
            # Recent: only filter out very old articles (if we had timestamp data)
            return False

        elif quality == NewsQualityLevel.POPULAR:
            # Popular: articles with multiple topics are preferred
            topics = article.get('topics', [])
            if isinstance(topics, list) and len(topics) < 2:
                return True

        return False

    def _filter_and_enrich_articles(
        self,
        articles: List[Dict[str, Any]],
        quality: NewsQualityLevel
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Filter articles based on quality criteria and enrich them with additional metadata.

        Args:
            articles: Raw articles from API
            quality: Quality filtering level

        Returns:
            Tuple of (filtered_articles, enrichment_stats)
        """
        if not articles:
            return [], {}

        filtered_articles = []
        stats = {
            'total': len(articles),
            'filtered_out': 0,
            'relevance_scores': [],
            'sentiment_distribution': {'positive': 0, 'negative': 0, 'neutral': 0}
        }

        for article in articles:
            # Apply filtering
            if self._should_filter_out_article(article, quality):
                stats['filtered_out'] += 1
                continue

            # Enrich article with additional metadata
            enriched_article = self._enrich_article(article)
            filtered_articles.append(enriched_article)

            # Update statistics
            relevance = article.get('overall_sentiment_score', 0)
            if isinstance(relevance, (int, float)):
                stats['relevance_scores'].append(float(relevance))

            sentiment = article.get('overall_sentiment_label', '').lower()
            if sentiment in ['positive', 'negative', 'neutral']:
                stats['sentiment_distribution'][sentiment] += 1

        return filtered_articles, stats

    def _enrich_article(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """Add enrichment metadata to article."""
        # Add quality score
        relevance_score = article.get('overall_sentiment_score', 0)
        if isinstance(relevance_score, str):
            try:
                relevance_score = Decimal(relevance_score)
            except (ValueError, TypeError):
                relevance_score = Decimal('0.5')

        # Calculate quality metrics
        quality_score = self._calculate_article_quality(article)

        # Add enrichment fields
        enriched_article = article.copy()
        enriched_article.update({
            'enriched_at': datetime.now(timezone.utc).isoformat(),
            'quality_score': float(quality_score),
            'relevance_score': float(relevance_score) if isinstance(relevance_score, (int, float)) else 0.5,
            'word_count': len(article.get('summary', article.get('title', '')).split()),
            'has_image': bool(article.get('banner_image')),
            'topic_count': len(article.get('topics', [])),
            'source_reliability': self._assess_source_reliability(article.get('source', 'unknown'))
        })

        return enriched_article

    def _calculate_article_quality(self, article: Dict[str, Any]) -> Decimal:
        """Calculate overall quality score for an article (0.0-1.0)."""
        score = Decimal('0.5')

        # Relevance factor
        relevance = article.get('overall_sentiment_score', 0)
        if isinstance(relevance, (int, float)):
            score = max(score, Decimal(str(relevance)))

        # Content quality
        title = article.get('title', '')
        summary = article.get('summary', '')

        if title and len(title.split()) > 5:
            score += Decimal('0.1')

        if summary and len(summary.split()) > 20:
            score += Decimal('0.1')

        # Visual content
        if article.get('banner_image'):
            score += Decimal('0.1')

        # Topic coverage
        topics = article.get('topics', [])
        if isinstance(topics, list):
            score += min(Decimal('0.2'), len(topics) * Decimal('0.05'))

        return min(Decimal('1.0'), max(Decimal('0.0'), score))

    def _assess_source_reliability(self, source_name: str) -> Decimal:
        """Assess source reliability (0.0-1.0)."""
        if not source_name:
            return Decimal('0.5')

        source_lower = source_name.lower()

        # High reliability sources
        reliable_sources = [
            'reuters', 'bloomberg', 'cnbc', 'associated press', 'financial times',
            'wall street journal', 'barron\'s'
        ]

        # Medium reliability sources
        medium_sources = [
            'yahoo finance', 'market watch', 'seeking alpha', 'investing.com',
            'market news', 'business insider'
        ]

        # Check for reliable sources
        for reliable in reliable_sources:
            if reliable in source_lower:
                return Decimal('0.9')

        for medium in medium_sources:
            if medium in source_lower:
                return Decimal('0.7')

        return Decimal('0.5')

    def _make_api_request(self, ticker: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Make API request to Alpha Vantage with proper error handling."""
        if not settings.alpha_vantage_enabled or not settings.alpha_vantage_api_key:
            raise ValueError("Alpha Vantage API not configured")

        # Check rate limits
        if not self.rate_limiter.can_make_request():
            wait_time = self.rate_limiter.get_wait_time()
            logger.warning(f"Rate limit reached, waiting {wait_time:.1f} seconds")
            if wait_time > 0:
                time.sleep(wait_time)

        # Wait for configured delay between requests
        time.sleep(settings.alpha_vantage_request_delay)

        url = settings.alpha_vantage_base_url
        params = {
            'function': 'NEWS_SENTIMENT',
            'symbol': ticker,
            'apikey': settings.alpha_vantage_api_key,
            'limit': limit
        }

        for attempt in range(self.MAX_RETRIES):
            try:
                logger.debug(f"Making news request: ticker={ticker}, limit={limit}, attempt={attempt + 1}")

                response = self.session.get(
                    url,
                    params=params,
                    timeout=settings.alpha_vantage_timeout
                )
                response.raise_for_status()

                data = response.json()

                # Check for API errors
                if 'Error Message' in data:
                    error_msg = data['Error Message']
                    logger.error(f"Alpha Vantage API error: {error_msg}")
                    raise ValueError(f"Alpha Vantage API error: {error_msg}")

                if 'Information' in data:
                    info_msg = data['Information']
                    logger.warning(f"Alpha Vantage API info: {info_msg}")
                    if "API call frequency" in info_msg:
                        # Hit rate limit, wait longer
                        wait_time = self.rate_limiter.get_wait_time()
                        time.sleep(wait_time)
                        continue
                    raise ValueError(f"Alpha Vantage API info: {info_msg}")

                self.rate_limiter.record_request()

                # Extract news articles
                feed = data.get('feed', [])
                if not feed:
                    logger.warning(f"No news articles found for {ticker}")
                    return []

                logger.info(f"Fetched {len(feed)} raw articles for {ticker}")
                return feed

            except requests.exceptions.RequestException as e:
                logger.warning(f"News request attempt {attempt + 1} failed for {ticker}: {str(e)}")
                if attempt < self.MAX_RETRIES - 1:
                    # Exponential backoff
                    retry_delay = min(self.MAX_RETRY_DELAY,
                                   self.INITIAL_RETRY_DELAY * (2 ** attempt))
                    logger.info(f"Retrying in {retry_delay:.1f} seconds")
                    time.sleep(retry_delay)
                else:
                    raise

        raise Exception(f"Max retries exceeded for news request: {ticker}")

    def _fetch_single_ticker(
        self,
        ticker: str,
        quality: NewsQualityLevel = NewsQualityLevel.HIGH,
        limit: int = 50
    ) -> NewsFetchResult:
        """
        Fetch news for a single ticker with caching and filtering.

        Args:
            ticker: Stock ticker symbol
            quality: Quality filtering level
            limit: Maximum number of articles to fetch

        Returns:
            NewsFetchResult with processed articles and metadata
        """
        start_time = time.time()
        result = NewsFetchResult(
            ticker=ticker,
            articles=[],
            success=False,
            api_calls_made=0,
            cached_articles=0,
            processed_articles=0
        )

        try:
            # Check cache first
            cache_key = self._generate_cache_key(ticker, quality.value, limit)
            cached_data = self.cache_service.get(cache_key)

            if cached_data:
                logger.debug(f"Cache hit for news: {ticker} (quality: {quality.value})")
                self.rate_limiter.record_cache_hit()
                result.cached_articles = len(cached_data.get('articles', []))
                result.articles = cached_data['articles']
                result.processed_articles = result.cached_articles
                result.filter_applied = cached_data.get('filter_applied', False)
                result.success = True
                return result

            self.rate_limiter.record_cache_miss()

            # Fetch from API
            raw_articles = self._make_api_request(ticker, limit)
            result.api_calls_made = 1

            # Apply quality filtering
            filtered_articles, filter_stats = self._filter_and_enrich_articles(
                raw_articles, quality
            )

            result.articles = filtered_articles
            result.processed_articles = len(filtered_articles)
            result.filter_applied = True

            # Cache the result
            cache_data = {
                'articles': filtered_articles,
                'filter_stats': filter_stats,
                'quality': quality.value,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'filter_applied': True
            }
            self.cache_service.set(cache_key, cache_data, self.CACHE_TIER_2)

            # Log processing results
            logger.info(
                f"Processed news for {ticker}: {len(raw_articles)} raw -> "
                f"{len(filtered_articles)} filtered articles "
                f"(quality: {quality.value})"
            )

            result.success = True

        except Exception as e:
            logger.error(f"Error fetching news for {ticker}: {str(e)}")
            result.error_message = str(e)
            result.success = False

        # Calculate processing time
        processing_time = time.time() - start_time
        logger.debug(f"News fetch for {ticker} took {processing_time:.2f} seconds")

        return result

    def fetch_news_batch(
        self,
        tickers: List[str],
        quality: NewsQualityLevel = NewsQualityLevel.HIGH,
        limit: int = 50
    ) -> NewsBatchResult:
        """
        Fetch news for multiple tickers in batches with parallel processing.

        Args:
            tickers: List of stock ticker symbols
            quality: Quality filtering level
            limit: Maximum number of articles per ticker

        Returns:
            NewsBatchResult with aggregated results
        """
        if not tickers:
            return NewsBatchResult(
                results=[],
                total_api_calls=0,
                total_cached_articles=0,
                total_processed_articles=0,
                failed_tickers=[],
                average_processing_time=0.0,
                batch_size=0
            )

        # Split tickers into batches to avoid API limits
        batch_size = self.max_batch_size
        ticker_batches = [tickers[i:i + batch_size] for i in range(0, len(tickers), batch_size)]

        all_results = []
        total_api_calls = 0
        total_cached_articles = 0
        total_processed_articles = 0
        failed_tickers = []
        start_time = time.time()

        logger.info(f"Fetching news batch for {len(tickers)} tickers in {len(ticker_batches)} batches")

        # Process each batch sequentially to avoid overwhelming the API
        for batch_idx, batch in enumerate(ticker_batches):
            logger.debug(f"Processing batch {batch_idx + 1}/{len(ticker_batches)}: {batch}")

            # Process tickers in parallel within the batch
            with ThreadPoolExecutor(max_workers=self.max_concurrent_requests) as executor:
                future_to_ticker = {
                    executor.submit(self._fetch_single_ticker, ticker, quality, limit): ticker
                    for ticker in batch
                }

                for future in as_completed(future_to_ticker):
                    ticker = future_to_ticker[future]
                    try:
                        result = future.result()
                        all_results.append(result)

                        total_api_calls += result.api_calls_made
                        total_cached_articles += result.cached_articles
                        total_processed_articles += result.processed_articles

                        if not result.success:
                            failed_tickers.append(ticker)

                    except Exception as e:
                        logger.error(f"Error processing ticker {ticker}: {str(e)}")
                        failed_tickers.append(ticker)

        total_time = time.time() - start_time
        average_time = total_time / max(1, len(tickers))

        logger.info(
            f"News batch completed: {len(all_results)} results, "
            f"{total_api_calls} API calls, {len(failed_tickers)} failed tickers"
        )

        return NewsBatchResult(
            results=all_results,
            total_api_calls=total_api_calls,
            total_cached_articles=total_cached_articles,
            total_processed_articles=total_processed_articles,
            failed_tickers=failed_tickers,
            average_processing_time=average_time,
            batch_size=len(tickers)
        )

    def get_news_summary(self, ticker: str, days: int = 7) -> Dict[str, Any]:
        """
        Get a summary of recent news for a ticker.

        Args:
            ticker: Stock ticker symbol
            days: Number of days to look back

        Returns:
            News summary statistics
        """
        cache_key = f"news:summary:{ticker}:{days}"
        cached_data = self.cache_service.get(cache_key)

        if cached_data:
            logger.debug(f"Cache hit for news summary: {ticker}")
            return cached_data

        try:
            # Fetch recent high-quality news
            result = self._fetch_single_ticker(
                ticker,
                NewsQualityLevel.HIGH,
                limit=20
            )

            if not result.success:
                return {"error": result.error_message, "ticker": ticker}

            # Calculate summary statistics
            articles = result.articles
            summary = {
                "ticker": ticker,
                "total_articles": len(articles),
                "total_api_calls": result.api_calls_made,
                "filtered_articles": result.processed_articles,
                "average_relevance": 0.0,
                "sentiment_distribution": {"positive": 0, "negative": 0, "neutral": 0},
                "top_sources": {},
                "recent_articles": [],
                "summary_generated_at": datetime.now(timezone.utc).isoformat()
            }

            if articles:
                # Calculate average relevance
                relevance_scores = []
                for article in articles:
                    rel_score = article.get('relevance_score', 0.0)
                    if isinstance(rel_score, (int, float)):
                        relevance_scores.append(rel_score)

                summary["average_relevance"] = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.0

                # Count sentiment distribution
                for article in articles:
                    sentiment = article.get('overall_sentiment_label', '').lower()
                    if sentiment in ['positive', 'negative', 'neutral']:
                        summary["sentiment_distribution"][sentiment] += 1

                # Top sources
                source_counts = {}
                for article in articles:
                    source = article.get('source_name', article.get('source', 'unknown'))
                    source_counts[source] = source_counts.get(source, 0) + 1

                summary["top_sources"] = dict(sorted(source_counts.items(), key=lambda x: x[1], reverse=True)[:5])

                # Recent articles (last 3)
                summary["recent_articles"] = articles[:3]

            # Cache the summary
            self.cache_service.set(cache_key, summary, self.CACHE_TIER_3)

            return summary

        except Exception as e:
            logger.error(f"Error generating news summary for {ticker}: {str(e)}")
            return {"error": str(e), "ticker": ticker}

    def get_health_status(self) -> Dict[str, Any]:
        """
        Get comprehensive health status of the news fetcher service.

        Returns:
            Health status dictionary
        """
        rate_limiter_stats = self.rate_limiter.get_usage_stats()

        return {
            "service_name": "NewsFetcherService",
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "rate_limiter": rate_limiter_stats,
            "cache_service": {
                "available": self.cache_service.available,
                "cache_hit_rate": rate_limiter_stats["cache_hit_rate"]
            },
            "configuration": {
                "max_batch_size": self.max_batch_size,
                "max_concurrent_requests": self.max_concurrent_requests,
                "max_retries": self.MAX_RETRIES,
                "cache_tiers": {
                    "tier_1": self.CACHE_TIER_1,
                    "tier_2": self.CACHE_TIER_2,
                    "tier_3": self.CACHE_TIER_3
                }
            },
            "quality_thresholds": {
                "high_relevance": float(self.HIGH_RELEVANCE_THRESHOLD),
                "medium_relevance": float(self.MEDIUM_RELEVANCE_THRESHOLD),
                "confidence": float(self.CONFIDENCE_THRESHOLD)
            }
        }

    def clear_cache(self, ticker: Optional[str] = None) -> int:
        """
        Clear news cache for a specific ticker or all tickers.

        Args:
            ticker: Optional ticker to clear cache for. If None, clears all news cache.

        Returns:
            Number of cache keys cleared
        """
        if ticker:
            pattern = f"news:fetch:{ticker.lower()}:*"
            count = self.cache_service.clear_pattern(pattern)
            logger.info(f"Cleared {count} cache entries for ticker: {ticker}")
            return count
        else:
            # Clear all news cache
            patterns = [
                "news:fetch:*",
                "news:batch:*",
                "news:summary:*"
            ]
            total_cleared = 0
            for pattern in patterns:
                total_cleared += self.cache_service.clear_pattern(pattern)

            logger.info(f"Cleared {total_cleared} total news cache entries")
            return total_cleared

    def reset_rate_limits(self) -> None:
        """Reset rate limit tracking (useful for testing or maintenance)."""
        self.rate_limiter.daily_calls = 0
        self.rate_limiter.minute_calls = 0
        self.rate_limiter.cache_hits = 0
        self.rate_limiter.cache_misses = 0
        logger.info("News fetcher rate limits have been reset")


# Global service instance
_news_fetcher_service = None


def get_news_fetcher_service() -> NewsFetcherService:
    """Get the global news fetcher service instance."""
    global _news_fetcher_service
    if _news_fetcher_service is None:
        _news_fetcher_service = NewsFetcherService()
    return _news_fetcher_service