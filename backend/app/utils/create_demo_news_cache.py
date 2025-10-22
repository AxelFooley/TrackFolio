#!/usr/bin/env python3
"""
Demo script to create sample cached news data for testing rate limit fallback.
"""
import json
import sys
import os
from datetime import datetime, timezone

# Set up Python path for container execution
sys.path.insert(0, '/app')

from app.services.cache import CacheService
from app.config import settings

def create_demo_news_cache():
    """Create demo news cache entries for testing."""

    cache = CacheService()

    if not cache.available:
        print("Redis cache not available - cannot create demo data")
        return

    # Demo articles for AAPL
    demo_articles_aapl = [
        {
            "title": "Apple Reports Strong Q4 Earnings",
            "summary": "Apple Inc. reported better-than-expected quarterly earnings driven by strong iPhone sales.",
            "source": "Reuters",
            "source_name": "Reuters",
            "url": "https://reuters.com/article/apple-q4-earnings",
            "banner_image": "https://example.com/apple.jpg",
            "overall_sentiment_label": "positive",
            "overall_sentiment_score": "0.85",
            "ticker_sentiment": [
                {"ticker": "AAPL", "relevance_score": "0.92", "ticker_sentiment_label": "positive"}
            ],
            "time_published": "20251022T093000",
            "topics": [
                {"topic": "Earnings", "relevance_score": "0.95"},
                {"topic": "Technology", "relevance_score": "0.88"}
            ],
            "enriched_at": datetime.now(timezone.utc).isoformat(),
            "quality_score": 0.92,
            "relevance_score": 0.85,
            "word_count": 45,
            "has_image": True,
            "topic_count": 2,
            "source_reliability": 0.9
        },
        {
            "title": "Apple Vision Pro Sales Meet Expectations",
            "summary": "Apple's Vision Pro headset sales are meeting company expectations in the first quarter of availability.",
            "source": "CNBC",
            "source_name": "CNBC",
            "url": "https://cnbc.com/article/apple-vision-pro-sales",
            "banner_image": "https://example.com/vision-pro.jpg",
            "overall_sentiment_label": "positive",
            "overall_sentiment_score": "0.72",
            "ticker_sentiment": [
                {"ticker": "AAPL", "relevance_score": "0.89", "ticker_sentiment_label": "positive"}
            ],
            "time_published": "20251022T143000",
            "topics": [
                {"topic": "Product Launch", "relevance_score": "0.91"},
                {"topic": "Consumer Electronics", "relevance_score": "0.84"}
            ],
            "enriched_at": datetime.now(timezone.utc).isoformat(),
            "quality_score": 0.88,
            "relevance_score": 0.72,
            "word_count": 38,
            "has_image": True,
            "topic_count": 2,
            "source_reliability": 0.9
        },
        {
            "title": "Analysts Maintain Buy Rating on Apple Stock",
            "summary": "Multiple analysts maintain their buy ratings on Apple stock despite market volatility.",
            "source": "Bloomberg",
            "source_name": "Bloomberg",
            "url": "https://bloomberg.com/article/apple-analyst-ratings",
            "banner_image": "https://example.com/apple-stock.jpg",
            "overall_sentiment_label": "positive",
            "overall_sentiment_score": "0.68",
            "ticker_sentiment": [
                {"ticker": "AAPL", "relevance_score": "0.95", "ticker_sentiment_label": "positive"}
            ],
            "time_published": "20251022T160000",
            "topics": [
                {"topic": "Stock Analysis", "relevance_score": "0.93"},
                {"topic": "Investment", "relevance_score": "0.87"}
            ],
            "enriched_at": datetime.now(timezone.utc).isoformat(),
            "quality_score": 0.85,
            "relevance_score": 0.68,
            "word_count": 42,
            "has_image": True,
            "topic_count": 2,
            "source_reliability": 0.9
        }
    ]

    # Demo articles for MSFT
    demo_articles_msft = [
        {
            "title": "Microsoft Azure Growth Accelerates",
            "summary": "Microsoft's Azure cloud computing platform shows accelerated growth in the latest quarter.",
            "source": "Financial Times",
            "source_name": "Financial Times",
            "url": "https://ft.com/article/microsoft-azure-growth",
            "banner_image": "https://example.com/azure.jpg",
            "overall_sentiment_label": "positive",
            "overall_sentiment_score": "0.79",
            "ticker_sentiment": [
                {"ticker": "MSFT", "relevance_score": "0.91", "ticker_sentiment_label": "positive"}
            ],
            "time_published": "20251022T103000",
            "topics": [
                {"topic": "Cloud Computing", "relevance_score": "0.94"},
                {"topic": "Business Growth", "relevance_score": "0.86"}
            ],
            "enriched_at": datetime.now(timezone.utc).isoformat(),
            "quality_score": 0.90,
            "relevance_score": 0.79,
            "word_count": 40,
            "has_image": True,
            "topic_count": 2,
            "source_reliability": 0.9
        }
    ]

    # Create cache entries with different keys for testing fallback
    cache_entries = [
        # Exact match cache entries
        ("news:fetch:aapl:limit:50:qual:high", demo_articles_aapl),
        ("news:fetch:msft:limit:50:qual:high", demo_articles_msft),

        # Different quality levels
        ("news:fetch:aapl:limit:50:qual:medium", demo_articles_aapl[:2]),
        ("news:fetch:aapl:limit:50:qual:low", demo_articles_aapl),

        # Different limits
        ("news:fetch:aapl:limit:100:qual:high", demo_articles_aapl),

        # Summary cache entries
        ("news:summary:AAPL:7", {
            "ticker": "AAPL",
            "total_articles": len(demo_articles_aapl),
            "average_relevance": 0.75,
            "sentiment_distribution": {"positive": 3, "negative": 0, "neutral": 0},
            "top_sources": {"Reuters": 1, "CNBC": 1, "Bloomberg": 1},
            "recent_articles": demo_articles_aapl,
            "summary_generated_at": datetime.now(timezone.utc).isoformat()
        }),

        ("news:summary:MSFT:7", {
            "ticker": "MSFT",
            "total_articles": len(demo_articles_msft),
            "average_relevance": 0.79,
            "sentiment_distribution": {"positive": 1, "negative": 0, "neutral": 0},
            "top_sources": {"Financial Times": 1},
            "recent_articles": demo_articles_msft,
            "summary_generated_at": datetime.now(timezone.utc).isoformat()
        })
    ]

    # Store each cache entry
    for cache_key, articles in cache_entries:
        if isinstance(articles, list):
            cache_data = {
                'articles': articles,
                'filter_stats': {
                    'total': len(articles),
                    'filtered_out': 0,
                    'relevance_scores': [a.get('relevance_score', 0.5) for a in articles],
                    'sentiment_distribution': {'positive': len(articles), 'negative': 0, 'neutral': 0}
                },
                'quality': 'high',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'filter_applied': True
            }
        else:
            cache_data = articles

        success = cache.set(cache_key, cache_data, ttl_seconds=3600)  # 1 hour TTL
        if success:
            print(f"✓ Created cache entry: {cache_key}")
        else:
            print(f"✗ Failed to create cache entry: {cache_key}")

    print(f"\nCreated {len(cache_entries)} demo cache entries for testing rate limit fallback")
    print("You can now test the news API endpoints to see the fallback behavior")

if __name__ == "__main__":
    create_demo_news_cache()