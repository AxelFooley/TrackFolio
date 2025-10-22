"""
Tests for NewsFetcherService.
"""
import pytest
import time
from unittest.mock import Mock, patch, AsyncMock
from decimal import Decimal
from datetime import datetime, timezone

from app.services.news_fetcher import (
    NewsFetcherService,
    TokenBucket,
    NewsRateLimiter,
    NewsQualityLevel,
    NewsFetchResult,
    NewsBatchResult
)
from app.schemas.news_fetcher import NewsQualityFilter


class TestTokenBucket:
    """Test TokenBucket implementation."""

    def test_token_bucket_initialization(self):
        """Test token bucket initialization."""
        bucket = TokenBucket(capacity=5, refill_rate=5/60)
        assert bucket.capacity == 5
        assert bucket.refill_rate == 5/60
        assert bucket.tokens == 5

    def test_token_consumption(self):
        """Test token consumption."""
        bucket = TokenBucket(capacity=5, refill_rate=5/60)

        # Consume tokens
        assert bucket.consume(1) == True
        assert bucket.consume(2) == True
        assert bucket.consume(3) == False  # Not enough tokens

    def test_token_refill(self):
        """Test token refill over time."""
        bucket = TokenBucket(capacity=5, refill_rate=5)  # 5 tokens per second

        # Consume all tokens
        bucket.consume(5)
        assert bucket.get_tokens_available() == 0

        # Wait a bit and check refill
        time.sleep(0.2)
        assert bucket.get_tokens_available() > 0
        assert bucket.get_tokens_available() <= 1

    def test_wait_time_calculation(self):
        """Test wait time calculation."""
        bucket = TokenBucket(capacity=5, refill_rate=5/60)

        # Consume all tokens
        bucket.consume(5)

        # Should wait to refill
        wait_time = bucket.get_wait_time(1)
        assert wait_time > 0


class TestNewsRateLimiter:
    """Test NewsRateLimiter implementation."""

    def test_rate_limiter_initialization(self):
        """Test rate limiter initialization."""
        limiter = NewsRateLimiter()
        assert limiter.daily_calls == 0
        assert limiter.minute_calls == 0
        assert limiter.cache_hits == 0
        assert limiter.cache_misses == 0

    def test_can_make_request_success(self):
        """Test successful request check."""
        limiter = NewsRateLimiter()
        assert limiter.can_make_request() == True

    def test_can_make_request_daily_limit(self):
        """Test daily limit hit."""
        limiter = NewsRateLimiter()
        limiter.daily_calls = settings.alpha_vantage_requests_per_day
        assert limiter.can_make_request() == False

    def test_can_make_request_minute_limit(self):
        """Test minute limit hit."""
        limiter = NewsRateLimiter()
        limiter.minute_calls = settings.alpha_vantage_requests_per_minute
        assert limiter.can_make_request() == False

    def test_record_request(self):
        """Test request recording."""
        limiter = NewsRateLimiter()
        initial_calls = limiter.daily_calls

        limiter.record_request()

        assert limiter.daily_calls == initial_calls + 1
        assert limiter.minute_calls == 1

    def test_record_cache_hit(self):
        """Test cache hit recording."""
        limiter = NewsRateLimiter()
        initial_hits = limiter.cache_hits

        limiter.record_cache_hit()

        assert limiter.cache_hits == initial_hits + 1

    def test_get_usage_stats(self):
        """Test usage statistics."""
        limiter = NewsRateLimiter()

        # Make some requests
        limiter.record_request()
        limiter.record_request()

        # Record cache hits
        limiter.record_cache_hit()

        stats = limiter.get_usage_stats()

        assert stats['daily_calls'] == 2
        assert stats['minute_calls'] == 2
        assert stats['cache_hits'] == 1
        assert stats['cache_hit_rate'] == 1.0


class TestNewsFetcherService:
    """Test NewsFetcherService implementation."""

    @pytest.fixture
    def news_service(self):
        """Create NewsFetcherService instance for testing."""
        with patch('app.services.news_fetcher.settings') as mock_settings:
            mock_settings.alpha_vantage_enabled = True
            mock_settings.alpha_vantage_api_key = "test_key"
            mock_settings.alpha_vantage_base_url = "https://test.com"
            mock_settings.alpha_vantage_timeout = 30
            mock_settings.alpha_vantage_requests_per_minute = 5
            mock_settings.alpha_vantage_requests_per_day = 25
            mock_settings.alpha_vantage_request_delay = 0.1
            mock_settings.alpha_vantage_max_retries = 3
            mock_settings.alpha_vantage_retry_delay = 1.0

            service = NewsFetcherService()
            return service

    def test_news_service_initialization(self, news_service):
        """Test news service initialization."""
        assert news_service.rate_limiter is not None
        assert news_service.cache_service is not None
        assert news_service.max_batch_size == 5
        assert news_service.max_concurrent_requests == 3

    def test_generate_cache_key(self, news_service):
        """Test cache key generation."""
        key1 = news_service._generate_cache_key("AAPL", "high", 50)
        key2 = news_service._generate_cache_key("MSFT", "medium", 20)

        assert "news:fetch:aapl:qual:high:limit:50" in key1
        assert "news:fetch:msft:qual:medium:limit:20" in key2
        assert key1 != key2

    def test_generate_batch_cache_key(self, news_service):
        """Test batch cache key generation."""
        key1 = news_service._generate_batch_cache_key(["AAPL", "MSFT"], "high")
        key2 = news_service._generate_batch_cache_key(["GOOGL", "AMZN"], "medium")

        assert "news:batch:aapl:msft:qual:high" in key1
        assert "news:batch:googl:amzn:qual:medium" in key2
        assert key1 != key2

    def test_should_filter_out_article_high_quality(self, news_service):
        """Test high quality article filtering."""
        # Article with high relevance and positive sentiment
        good_article = {
            'overall_sentiment_score': '0.8',
            'overall_sentiment_label': 'positive',
            'topics': [{'topic': 'technology'}]
        }

        # Article with low relevance and neutral sentiment
        bad_article = {
            'overall_sentiment_score': '0.3',
            'overall_sentiment_label': 'neutral',
            'topics': [{'topic': 'technology'}]
        }

        assert news_service._should_filter_out_article(good_article, NewsQualityLevel.HIGH) == False
        assert news_service._should_filter_out_article(bad_article, NewsQualityLevel.HIGH) == True

    def test_should_filter_out_article_medium_quality(self, news_service):
        """Test medium quality article filtering."""
        # Article with medium relevance
        medium_article = {
            'overall_sentiment_score': '0.6',
            'overall_sentiment_label': 'neutral',
            'topics': [{'topic': 'technology'}]
        }

        # Article with low relevance
        low_article = {
            'overall_sentiment_score': '0.3',
            'overall_sentiment_label': 'neutral',
            'topics': [{'topic': 'technology'}]
        }

        assert news_service._should_filter_out_article(medium_article, NewsQualityLevel.MEDIUM) == False
        assert news_service._should_filter_out_article(low_article, NewsQualityLevel.MEDIUM) == True

    def test_enrich_article(self, news_service):
        """Test article enrichment."""
        article = {
            'title': 'Test Article',
            'summary': 'Test summary',
            'overall_sentiment_score': '0.7',
            'overall_sentiment_label': 'positive',
            'topics': [{'topic': 'technology'}],
            'source_name': 'Test Source',
            'banner_image': 'http://example.com/image.jpg'
        }

        enriched = news_service._enrich_article(article)

        assert enriched['enriched_at'] is not None
        assert enriched['quality_score'] > 0
        assert enriched['relevance_score'] == 0.7
        assert enriched['word_count'] > 0
        assert enriched['has_image'] == True
        assert enriched['topic_count'] == 1
        assert 'source_reliability' in enriched

    def test_calculate_article_quality(self, news_service):
        """Test article quality calculation."""
        # High quality article
        high_quality_article = {
            'title': 'Long Title With Many Words',
            'summary': 'Long summary with many words that should increase quality score',
            'overall_sentiment_score': '0.8',
            'topics': [{'topic': 'tech'}, {'topic': 'finance'}],
            'banner_image': 'http://example.com/image.jpg'
        }

        # Low quality article
        low_quality_article = {
            'title': 'Short',
            'summary': 'Short',
            'overall_sentiment_score': '0.3',
            'topics': [],
        }

        high_score = news_service._calculate_article_quality(high_quality_article)
        low_score = news_service._calculate_article_quality(low_quality_article)

        assert high_score > low_score
        assert 0 <= high_score <= 1
        assert 0 <= low_score <= 1

    def test_assess_source_reliability(self, news_service):
        """Test source reliability assessment."""
        # High reliability source
        reliable_source = news_service._assess_source_reliability('Reuters')
        assert reliable_source == Decimal('0.9')

        # Medium reliability source
        medium_source = news_service._assess_source_reliability('Yahoo Finance')
        assert medium_source == Decimal('0.7')

        # Unknown source
        unknown_source = news_service._assess_source_reliability('Unknown Source')
        assert unknown_source == Decimal('0.5')

    @patch('app.services.news_fetcher.NewsFetcherService._make_api_request')
    def test_fetch_single_ticker_success(self, mock_api_request, news_service):
        """Test successful single ticker news fetch."""
        # Mock API response
        mock_api_request.return_value = [
            {
                'title': 'Test Article',
                'overall_sentiment_score': '0.8',
                'overall_sentiment_label': 'positive',
                'topics': [{'topic': 'technology'}],
                'source_name': 'Test Source',
                'summary': 'Test summary',
                'banner_image': 'http://example.com/image.jpg'
            }
        ]

        # Mock cache service to return None (cache miss)
        news_service.cache_service.get.return_value = None

        result = news_service._fetch_single_ticker('AAPL', NewsQualityLevel.HIGH, 10)

        assert result.success == True
        assert result.ticker == 'AAPL'
        assert len(result.articles) == 1
        assert result.api_calls_made == 1
        assert result.processed_articles == 1

    @patch('app.services.news_fetcher.NewsFetcherService._make_api_request')
    def test_fetch_single_ticker_api_failure(self, mock_api_request, news_service):
        """Test single ticker fetch with API failure."""
        # Mock API to raise exception
        mock_api_request.side_effect = Exception("API Error")

        result = news_service._fetch_single_ticker('AAPL', NewsQualityLevel.HIGH, 10)

        assert result.success == False
        assert result.error_message == "API Error"
        assert result.api_calls_made == 0

    def test_fetch_news_batch_empty_tickers(self, news_service):
        """Test batch fetch with empty tickers list."""
        result = news_service.fetch_news_batch([], NewsQualityLevel.HIGH, 10)

        assert len(result.results) == 0
        assert result.total_api_calls == 0
        assert result.total_cached_articles == 0
        assert result.batch_size == 0

    @patch('app.services.news_fetcher.NewsFetcherService._fetch_single_ticker')
    def test_fetch_news_batch_success(self, mock_fetch_single, news_service):
        """Test successful batch news fetch."""
        # Mock successful single ticker fetches
        mock_fetch_single.return_value = NewsFetchResult(
            ticker='AAPL',
            articles=[{'title': 'Article 1'}],
            success=True,
            api_calls_made=1,
            cached_articles=0,
            processed_articles=1,
            filter_applied=True
        )

        result = news_service.fetch_news_batch(['AAPL', 'MSFT'], NewsQualityLevel.HIGH, 10)

        assert len(result.results) == 2
        assert result.total_api_calls == 2
        assert result.total_cached_articles == 0
        assert result.total_processed_articles == 2
        assert len(result.failed_tickers) == 0

    def test_get_health_status(self, news_service):
        """Test health status retrieval."""
        health_status = news_service.get_health_status()

        assert health_status['service_name'] == 'NewsFetcherService'
        assert health_status['status'] == 'healthy'
        assert 'rate_limiter' in health_status
        assert 'cache_service' in health_status
        assert 'configuration' in health_status

    def test_clear_cache_specific_ticker(self, news_service):
        """Test cache clear for specific ticker."""
        news_service.cache_service.clear_pattern.return_value = 5

        result = news_service.clear_cache('AAPL')

        assert result == 5
        news_service.cache_service.clear_pattern.assert_called_once()

    def test_clear_cache_all_tickers(self, news_service):
        """Test cache clear for all tickers."""
        news_service.cache_service.clear_pattern.side_effect = [3, 2, 1]  # Different pattern counts

        result = news_service.clear_cache()

        assert result == 6  # 3 + 2 + 1
        assert news_service.cache_service.clear_pattern.call_count == 3

    def test_reset_rate_limits(self, news_service):
        """Test rate limit reset."""
        # Make some calls to track
        news_service.rate_limiter.record_request()
        news_service.rate_limiter.record_cache_hit()

        # Reset
        news_service.reset_rate_limits()

        assert news_service.rate_limiter.daily_calls == 0
        assert news_service.rate_limiter.minute_calls == 0
        assert news_service.rate_limiter.cache_hits == 0
        assert news_service.rate_limiter.cache_misses == 0

    @patch('app.services.news_fetcher.NewsFetcherService._fetch_single_ticker')
    def test_get_news_summary(self, mock_fetch_single, news_service):
        """Test news summary generation."""
        # Mock successful fetch
        mock_fetch_single.return_value = NewsFetchResult(
            ticker='AAPL',
            articles=[
                {
                    'title': 'Article 1',
                    'overall_sentiment_score': 0.8,
                    'overall_sentiment_label': 'positive',
                    'source_name': 'Test Source',
                    'relevance_score': 0.8,
                    'summary': 'Test summary',
                    'banner_image': 'http://example.com/image.jpg',
                    'topics': [{'topic': 'technology'}]
                }
            ],
            success=True,
            api_calls_made=1,
            cached_articles=0,
            processed_articles=1,
            filter_applied=True
        )

        summary = news_service.get_news_summary('AAPL', 7)

        assert summary['ticker'] == 'AAPL'
        assert summary['total_articles'] == 1
        assert summary['total_api_calls'] == 1
        assert summary['filtered_articles'] == 1
        assert 'average_relevance' in summary
        assert 'sentiment_distribution' in summary
        assert 'top_sources' in summary
        assert 'recent_articles' in summary


class TestNewsFetcherIntegration:
    """Integration tests for NewsFetcherService."""

    def test_news_fetcher_service_global_instance(self):
        """Test global news fetcher service instance."""
        from app.services.news_fetcher import get_news_fetcher_service

        service1 = get_news_fetcher_service()
        service2 = get_news_fetcher_service()

        assert service1 is service2  # Should be the same instance

    def test_news_quality_filter_validation(self):
        """Test news quality filter validation."""
        # Valid quality level
        valid_filter = NewsQualityFilter(level='high')
        assert valid_filter.level == 'high'

        # Invalid quality level
        with pytest.raises(ValueError):
            NewsQualityFilter(level='invalid')


# Example usage configuration
EXAMPLE_CONFIG = {
    "service_name": "NewsFetcherService",
    "version": "1.0.0",
    "features": [
        "Token bucket rate limiting",
        "Multi-tier caching",
        "Batch processing",
        "Quality filtering",
        "Error handling with retries"
    ],
    "endpoints": [
        "POST /api/news/fetch - Fetch news for single ticker",
        "POST /api/news/batch - Fetch news for multiple tickers",
        "POST /api/news/summary - Get news summary for ticker",
        "GET /api/news/health - Service health check",
        "DELETE /api/news/cache - Clear news cache",
        "POST /api/news/rate-limits/reset - Reset rate limits",
        "GET /api/news/quality-levels - Get quality levels info",
        "GET /api/news/supported-sources - Get supported sources info"
    ]
}