# NewsFetcherService Usage Guide

This guide provides comprehensive information on using the NewsFetcherService for fetching and filtering financial news with advanced caching and rate limiting.

## Overview

The NewsFetcherService provides a sophisticated solution for fetching financial news from Alpha Vantage API with:

- **Token Bucket Rate Limiting**: Prevents API limit bursts (5 calls/min, 25 calls/day)
- **Multi-Tier Caching**: Intelligent caching with different TTL tiers
- **Batch Processing**: Efficient handling of multiple tickers in parallel
- **Quality Filtering**: Multiple quality levels to filter relevant news
- **Error Handling**: Robust error handling with exponential backoff
- **Health Monitoring**: Comprehensive health tracking and monitoring

## Quick Start

### Basic Usage

```python
from app.services.news_fetcher import get_news_fetcher_service
from app.services.news_fetcher import NewsQualityLevel

# Get service instance
service = get_news_fetcher_service()

# Fetch news for single ticker
result = service._fetch_single_ticker(
    ticker="AAPL",
    quality=NewsQualityLevel.HIGH,
    limit=10
)

if result.success:
    print(f"Found {len(result.articles)} articles")
    for article in result.articles:
        print(f"- {article['title']} (relevance: {article.get('relevance_score', 0):.2f})")
else:
    print(f"Error: {result.error_message}")
```

### Batch Processing

```python
# Fetch news for multiple tickers
tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
batch_result = service.fetch_news_batch(
    tickers=tickers,
    quality=NewsQualityLevel.HIGH,
    limit=15
)

print(f"Processed {len(batch_result.results)} tickers")
print(f"Total articles: {batch_result.total_processed_articles}")
print(f"Failed tickers: {batch_result.failed_tickers}")
print(f"Average processing time: {batch_result.average_processing_time:.2f}s")
```

### News Summary

```python
# Get comprehensive news summary
summary = service.get_news_summary(
    ticker="AAPL",
    days=7
)

print(f"Total articles: {summary['total_articles']}")
print(f"Average relevance: {summary['average_relevance']:.2f}")
print(f"Sentiment distribution: {summary['sentiment_distribution']}")
```

## Quality Filtering Levels

The service supports 5 quality filtering levels:

### High Quality (`high`)
- **Relevance threshold**: > 0.7
- **Sentiment filter**: Excludes neutral sentiment
- **Use case**: Investment decisions requiring high signal-to-noise ratio
- **API efficiency**: Most filtering, fewer results but higher quality

### Medium Quality (`medium`)
- **Relevance threshold**: > 0.5
- **Sentiment filter**: Includes neutral sentiment
- **Use case**: General market awareness and sentiment tracking
- **API efficiency**: Balanced approach

### Low Quality (`low`)
- **Relevance threshold**: No minimum
- **Sentiment filter**: No filtering
- **Use case**: Comprehensive news coverage and research
- **API efficiency**: Returns all articles, includes low relevance content

### Recent (`recent`)
- **Relevance threshold**: No minimum
- **Sentiment filter**: No filtering
- **Use case**: Breaking news and market events
- **API efficiency**: Focuses on very recent articles

### Popular (`popular`)
- **Relevance threshold**: No minimum
- **Sentiment filter**: No filtering
- **Use case**: Trending topics and popular market discussions
- **API efficiency**: Prefers articles with multiple topics

## API Endpoints

### Single Ticker News Fetch

```bash
POST /api/news/fetch
Content-Type: application/json

{
  "ticker": "AAPL",
  "quality": "high",
  "limit": 50
}
```

### Batch News Fetch

```bash
POST /api/news/batch
Content-Type: application/json

{
  "tickers": ["AAPL", "MSFT", "GOOGL"],
  "quality": "high",
  "limit": 20
}
```

### News Summary

```bash
POST /api/news/summary
Content-Type: application/json

{
  "ticker": "AAPL",
  "days": 7
}
```

### Health Check

```bash
GET /api/news/health
```

### Cache Management

```bash
# Clear cache for specific ticker
DELETE /api/news/cache?ticker=AAPL

# Clear all news cache
DELETE /api/news/cache

# Get quality levels info
GET /api/news/quality-levels

# Get supported sources info
GET /api/news/supported-sources
```

## Response Format

### Single Ticker Response

```json
{
  "status": "success",
  "data": {
    "ticker": "AAPL",
    "articles": [
      {
        "title": "Apple Reports Strong Q4 Earnings",
        "url": "https://example.com/article1",
        "source": "Reuters",
        "time": "2024-01-15T10:30:00Z",
        "summary": "Apple announced record quarterly earnings...",
        "topics": [
          {"topic": "earnings", "relevance_score": 0.8},
          {"topic": "technology", "relevance_score": 0.6}
        ],
        "overall_sentiment_score": 0.7,
        "overall_sentiment_label": "positive",
        "enriched_at": "2024-01-15T10:35:00Z",
        "quality_score": 0.85,
        "relevance_score": 0.7,
        "word_count": 150,
        "has_image": true,
        "topic_count": 2,
        "source_reliability": 0.9
      }
    ],
    "success": true,
    "api_calls_made": 1,
    "cached_articles": 0,
    "processed_articles": 1,
    "filter_applied": true
  },
  "message": "Successfully fetched 1 articles for AAPL",
  "timestamp": "2024-01-15T10:35:00Z"
}
```

### Batch Response

```json
{
  "status": "success",
  "data": {
    "batch_result": {
      "results": [...],
      "total_api_calls": 3,
      "total_cached_articles": 0,
      "total_processed_articles": 25,
      "failed_tickers": [],
      "average_processing_time": 2.34,
      "batch_size": 3
    },
    "individual_results": [...],
    "summary": {
      "total_tickers": 3,
      "successful_tickers": 3,
      "failed_tickers": 0,
      "total_api_calls": 3,
      "total_articles": 25,
      "total_cached_articles": 0,
      "average_processing_time": 2.34,
      "cache_hit_rate": 0.0
    }
  },
  "message": "Batch news completed: 3 tickers, all successful",
  "timestamp": "2024-01-15T10:35:00Z"
}
```

## Configuration

### Environment Variables

The service uses the following environment variables from `app.config`:

```bash
# Alpha Vantage Configuration
ALPHA_VANTAGE_API_KEY=your_api_key_here
ALPHA_VANTAGE_ENABLED=true
ALPHA_VANTAGE_REQUESTS_PER_MINUTE=4
ALPHA_VANTAGE_REQUESTS_PER_DAY=20
ALPHA_VANTAGE_REQUEST_DELAY=15.0
ALPHA_VANTAGE_TIMEOUT=30
ALPHA_VANTAGE_MAX_RETRIES=3
ALPHA_VANTAGE_RETRY_DELAY=1.0

# Cache Configuration (via CacheService)
REDIS_URL=redis://localhost:6379/0
```

### Customization

You can modify the service behavior by extending the class:

```python
class CustomNewsFetcherService(NewsFetcherService):
    def __init__(self):
        super().__init__()
        # Customize batch size
        self.max_batch_size = 3  # Smaller batch size
        self.max_concurrent_requests = 2  # Fewer concurrent requests

    def _should_filter_out_article(self, article, quality):
        # Add custom filtering logic
        if custom_condition(article):
            return True
        return super()._should_filter_out_article(article, quality)
```

## Rate Limiting Strategy

The service implements a sophisticated rate limiting system:

### Token Bucket Algorithm
- **Minute bucket**: 5 tokens, refills at 5/60 tokens per second
- **Day bucket**: 25 tokens, refills at 25/(24*3600) tokens per second
- **Consumption**: Each API call consumes 1 token
- **Waiting**: Automatically waits if insufficient tokens available

### Usage Monitoring

```python
# Get rate limiter statistics
stats = service.rate_limiter.get_usage_stats()
print(f"Daily calls: {stats['daily_calls']}/{stats['daily_limit']}")
print(f"Cache hit rate: {stats['cache_hit_rate']:.2%}")
print(f"Wait time: {stats['wait_time_seconds']:.1f}s")
```

## Caching Strategy

### Multi-Tier Caching
- **Tier 1 (15 min)**: Very fresh news for active monitoring
- **Tier 2 (1 hour)**: Recent news for regular analysis
- **Tier 3 (24 hours)**: General news for historical context

### Cache Keys

```python
# Single ticker cache key
key = f"news:fetch:{ticker.lower()}:qual:{quality}:limit:{limit}"

# Batch cache key
key = f"news:batch:{':'.join(sorted(tickers))}:qual:{quality}"

# Summary cache key
key = f"news:summary:{ticker}:{days}"
```

## Error Handling

The service implements comprehensive error handling:

### Automatic Retry
- **Max retries**: 3 attempts
- **Exponential backoff**: 1s, 2s, 4s delays
- **Rate limit handling**: Waits and retries when hitting API limits

### Error Scenarios

```python
result = service._fetch_single_ticker("AAPL", NewsQualityLevel.HIGH, 10)

if not result.success:
    if "API Error" in result.error_message:
        # Handle API failure
        pass
    elif "Rate limit" in result.error_message:
        # Handle rate limiting
        pass
    elif "Timeout" in result.error_message:
        # Handle timeout
        pass
```

## Performance Optimization

### Batch Processing
- **Max batch size**: 5 tickers (Alpha Vantage limit)
- **Concurrent requests**: 3 parallel requests per batch
- **Sequential batches**: Processes large ticker lists in sequential batches

### Memory Efficiency
- **Lazy loading**: Articles processed on demand
- **Stream processing**: Large results processed in chunks
- **Cache cleanup**: Automatic cache expiration

### Network Optimization
- **Session reuse**: HTTP session for connection pooling
- **Compression**: Supports compressed responses
- **Timeout management**: Configurable timeouts for different operations

## Monitoring and Health

### Health Check

```python
health = service.get_health_status()
print(f"Service status: {health['status']}")
print(f"Cache available: {health['cache_service']['available']}")
print(f"Rate limiter wait time: {health['rate_limiter']['wait_time_seconds']}s")
```

### Metrics Collection

The service tracks:
- **API usage**: Daily and minute call counts
- **Cache performance**: Hit rates and efficiency
- **Processing times**: Average time per operation
- **Error rates**: Success/failure statistics
- **Filtering effectiveness**: Articles filtered by quality level

## Best Practices

### 1. Choose Appropriate Quality Levels
- **Investment decisions**: Use `high` quality level
- **General monitoring**: Use `medium` quality level
- **Research**: Use `low` quality level

### 2. Manage API Usage
- **Monitor rate limits**: Regularly check usage statistics
- **Use caching**: Leverage multi-tier caching to reduce API calls
- **Batch requests**: Use batch processing for multiple tickers
- **Schedule wisely**: Avoid peak usage times

### 3. Error Handling
- **Check success flag**: Always verify `result.success` before processing
- **Handle rate limits**: Implement backoff when near limits
- **Monitor health**: Regular health checks for service stability

### 4. Performance Optimization
- **Use batch processing**: More efficient than individual requests
- **Cache appropriately**: Match TTL to your use case
- **Monitor performance**: Track processing times and optimize accordingly

## Troubleshooting

### Common Issues

1. **Rate Limit Errors**
   ```
   Solution: Check usage stats, increase wait times, or upgrade API plan
   ```

2. **Cache Misses**
   ```
   Solution: Verify Redis connection, check TTL settings
   ```

3. **Timeout Errors**
   ```
   Solution: Increase timeout settings, check network connectivity
   ```

4. **Poor Quality Results**
   ```
   Solution: Adjust quality levels, review filtering thresholds
   ```

### Debug Mode

```python
import logging
logging.getLogger('app.services.news_fetcher').setLevel(logging.DEBUG)

# Enable verbose logging
service = get_news_fetcher_service()
service.max_concurrent_requests = 1  # Sequential processing for debugging
```

## Advanced Usage

### Custom Quality Filtering

```python
class CustomNewsFetcherService(NewsFetcherService):
    def _should_filter_out_article(self, article, quality):
        # Custom filtering logic
        if quality == NewsQualityLevel.HIGH:
            # Additional high-quality criteria
            word_count = len(article.get('summary', '').split())
            if word_count < 50:
                return True
        return super()._should_filter_out_article(article, quality)
```

### Integration with Celery

```python
from celery import shared_task

@shared_task
def fetch_news_task(tickers, quality="high", limit=50):
    service = get_news_fetcher_service()
    batch_result = service.fetch_news_batch(
        tickers=tickers,
        quality=NewsQualityLevel(quality),
        limit=limit
    )
    return batch_result.dict()
```

This comprehensive guide provides everything needed to effectively use the NewsFetcherService in production environments.