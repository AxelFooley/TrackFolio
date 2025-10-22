"""
News update tasks for fetching and processing news articles for portfolio holdings.

This module provides Celery tasks for fetching news articles, particularly
focused on top movers (gainers/losers) from the portfolio.
"""
from celery import shared_task
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy import select, and_, func
from sqlalchemy.exc import IntegrityError
import logging
import time
from typing import List, Dict, Any, Optional

from app.celery_app import celery_app
from app.database import SyncSessionLocal
from app.models import Position, Transaction, PriceHistory
from app.models.news import NewsArticle, NewsTickerSentiment, SentimentType, NewsSource
from app.services.news_fetcher import NewsFetcherService, NewsQualityLevel
from app.services.system_state_manager import SystemStateManager

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 5},
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True
)
def fetch_news_for_todays_movers(self):
    """
    Fetch news for today's top movers (gainers and losers) from portfolio holdings.

    This task identifies holdings with the largest daily percentage changes and
    fetches relevant news articles for those tickers. Supports both scheduled
    execution and manual triggering.

    Returns:
        dict: Summary of news fetched including ticker counts, article counts,
              processing times, and any failures.
    """
    logger.info("Starting news fetch for today's movers task")

    db = SyncSessionLocal()
    news_fetcher = NewsFetcherService()

    try:
        # Get active positions with recent price data
        active_positions = _get_active_positions_with_price_data(db)

        if not active_positions:
            logger.info("No active positions with price data found. Skipping news fetch.")
            return {
                "status": "success",
                "message": "No active positions with price data",
                "tickers_processed": 0,
                "articles_fetched": 0,
                "articles_stored": 0,
                "failed_tickers": []
            }

        # Identify top movers (top 3 gainers and top 3 losers)
        top_movers = _identify_top_movers(active_positions)

        logger.info(f"Found {len(top_movers)} top movers to fetch news for: {list(top_movers.keys())}")

        if not top_movers:
            logger.info("No significant movers found to fetch news for")
            return {
                "status": "success",
                "message": "No significant movers found",
                "tickers_processed": 0,
                "articles_fetched": 0,
                "articles_stored": 0,
                "failed_tickers": []
            }

        # Fetch news for movers in batches
        results = _fetch_news_for_tickers_batch(
            news_fetcher,
            list(top_movers.keys()),
            quality=NewsQualityLevel.HIGH,
            limit=20  # Limit to focus on most relevant news
        )

        # Process and store the fetched news
        processing_stats = _process_and_store_news_results(db, results, top_movers)

        # Update last news update timestamp
        try:
            SystemStateManager.update_news_last_update(db)
            logger.info("Updated news last update timestamp")
        except Exception as e:
            logger.error(f"Failed to update news last update timestamp: {e}")
            # Don't fail the entire task if timestamp update fails

        # Compile final summary
        summary = {
            "status": "success",
            "message": "News fetch completed",
            "tickers_processed": len(results),
            "articles_fetched": results.get('total_processed_articles', 0),
            "articles_stored": processing_stats['articles_stored'],
            "articles_duplicates": processing_stats['articles_duplicates'],
            "articles_filtered": processing_stats['articles_filtered'],
            "failed_tickers": results.get('failed_tickers', []),
            "processing_time_seconds": processing_stats['processing_time'],
            "top_movers": top_movers,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        logger.info(
            f"News fetch complete: {summary['tickers_processed']} tickers, "
            f"{summary['articles_fetched']} articles fetched, "
            f"{summary['articles_stored']} articles stored"
        )

        return summary

    except Exception:
        logger.exception("Fatal error in news fetch for movers task")
        raise

    finally:
        db.close()


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 5},
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True
)
def fetch_news_for_ticker(self, ticker: str, quality: str = "high", limit: int = 50):
    """
    Fetch news for a specific ticker.

    Parameters:
        ticker (str): Stock ticker symbol to fetch news for
        quality (str): Quality level ('low', 'medium', 'high', 'recent', 'popular')
        limit (int): Maximum number of articles to fetch

    Returns:
        dict: Result with fetch status and statistics
    """
    logger.info(f"Starting news fetch for ticker: {ticker}")

    db = SyncSessionLocal()
    news_fetcher = NewsFetcherService()

    try:
        # Validate quality parameter
        quality_level = _parse_quality_level(quality)
        if quality_level is None:
            raise ValueError(f"Invalid quality level: {quality}")

        # Fetch news for the single ticker
        result = news_fetcher._fetch_single_ticker(ticker, quality_level, limit)

        if not result.success:
            logger.error(f"Failed to fetch news for {ticker}: {result.error_message}")
            return {
                "status": "failed",
                "ticker": ticker,
                "error_message": result.error_message,
                "articles_fetched": 0,
                "articles_stored": 0
            }

        # Store the fetched articles
        articles_stored = _store_news_articles(db, result.articles, ticker)

        # Update last update time for this ticker
        try:
            _update_ticker_news_timestamp(db, ticker)
        except Exception as e:
            logger.warning(f"Failed to update timestamp for {ticker}: {e}")

        logger.info(f"Successfully processed news for {ticker}: {len(result.articles)} fetched, {articles_stored} stored")

        return {
            "status": "success",
            "ticker": ticker,
            "articles_fetched": len(result.articles),
            "articles_stored": articles_stored,
            "quality": quality_level.value,
            "processing_time": result.get("processing_time", 0)
        }

    except Exception:
        logger.exception(f"Error fetching news for {ticker}")
        raise

    finally:
        db.close()


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 2, 'countdown': 10}
)
def cleanup_old_news_articles(self, days_to_keep: int = 30):
    """
    Clean up old news articles to prevent database bloat.

    Parameters:
        days_to_keep (int): Number of days to keep articles (default: 30)

    Returns:
        dict: Summary of cleanup operation
    """
    logger.info(f"Starting cleanup of news articles older than {days_to_keep} days")

    db = SyncSessionLocal()

    try:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)

        # Count articles to be deleted
        count_result = db.execute(
            select(func.count(NewsArticle.id))
            .where(NewsArticle.published_at < cutoff_date)
        ).scalar()

        if count_result == 0:
            logger.info("No old news articles to clean up")
            return {
                "status": "success",
                "articles_deleted": 0,
                "cutoff_date": cutoff_date.isoformat(),
                "message": "No articles to delete"
            }

        logger.info(f"Found {count_result} articles to delete")

        # Delete articles (cascade will delete related sentiment records)
        delete_result = db.execute(
            select(NewsArticle)
            .where(NewsArticle.published_at < cutoff_date)
        ).scalars().all()

        # Use batch delete for better performance
        articles_to_delete = list(delete_result)
        deleted_count = 0

        for i in range(0, len(articles_to_delete), 100):  # Batch size 100
            batch = articles_to_delete[i:i + 100]
            for article in batch:
                db.delete(article)
                deleted_count += 1

            if i % 500 == 0:  # Commit every 500 articles
                db.commit()
                logger.info(f"Deleted {deleted_count}/{count_result} articles")

        # Final commit
        db.commit()

        logger.info(f"Cleanup completed: {deleted_count} articles deleted")

        return {
            "status": "success",
            "articles_deleted": deleted_count,
            "cutoff_date": cutoff_date.isoformat(),
            "processing_time": datetime.now(timezone.utc).isoformat()
        }

    except Exception:
        logger.exception("Error during news cleanup")
        db.rollback()
        raise

    finally:
        db.close()


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 5},
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True
)
def refresh_news_cache(self):
    """
    Refresh news cache for all portfolio tickers to ensure fresh data.

    Returns:
        dict: Summary of cache refresh operation
    """
    logger.info("Starting news cache refresh task")

    db = SyncSessionLocal()
    news_fetcher = NewsFetcherService()

    try:
        # Get all active tickers
        active_tickers = _get_active_tickers(db)

        if not active_tickers:
            logger.info("No active tickers found for cache refresh")
            return {
                "status": "success",
                "tickers_processed": 0,
                "cache_hits": 0,
                "cache_misses": 0,
                "errors": []
            }

        logger.info(f"Refreshing news cache for {len(active_tickers)} tickers")

        # Clear cache for all tickers first
        cache_cleared = news_fetcher.clear_cache()
        logger.info(f"Cleared {cache_cleared} cache entries")

        # Fetch news for all tickers
        results = _fetch_news_for_tickers_batch(
            news_fetcher,
            active_tickers,
            quality=NewsQualityLevel.MEDIUM,  # Use medium quality for cache refresh
            limit=10  # Limit for cache refresh to be faster
        )

        summary = {
            "status": "success",
            "tickers_processed": len(results.get('results', [])),
            "cache_hits": results.get('total_cached_articles', 0),
            "cache_misses": results.get('total_api_calls', 0),
            "articles_fetched": results.get('total_processed_articles', 0),
            "failed_tickers": results.get('failed_tickers', []),
            "processing_time": results.get('average_processing_time', 0) * len(active_tickers)
        }

        logger.info(f"Cache refresh complete: {summary}")

        return summary

    except Exception:
        logger.exception("Error during news cache refresh")
        raise

    finally:
        db.close()


# Helper functions

def _get_active_positions_with_price_data(db) -> List[Dict[str, Any]]:
    """Get active positions with recent price change data."""
    try:
        # Get positions that have both transactions and price history
        result = db.execute(
            select(
                Position,
                func.max(PriceHistory.date).label('last_price_date'),
                func.max(PriceHistory.close).label('last_close'),
                func.lag(PriceHistory.close, 1).over(partition_by=Position.ticker).label('prev_close')
            )
            .join(Transaction, Transaction.ticker == Position.current_ticker)
            .join(PriceHistory, PriceHistory.ticker == Position.current_ticker)
            .where(Position.quantity > 0)
            .group_by(Position.id, Position.current_ticker)
            .having(func.max(PriceHistory.date) >= datetime.now().date() - timedelta(days=2))
        ).all()

        active_positions = []
        for row in result:
            position = row[0]
            last_close = row[2]
            prev_close = row[3] if row[3] else last_close  # Fallback if no previous close

            if last_close and prev_close and prev_close > 0:
                change_percent = ((last_close - prev_close) / prev_close) * 100
                active_positions.append({
                    'ticker': position.current_ticker,
                    'isin': position.isin,
                    'quantity': position.quantity,
                    'current_price': last_close,
                    'change_percent': change_percent,
                    'currency': position.currency or 'EUR'
                })

        return active_positions

    except Exception as e:
        logger.error(f"Error getting active positions: {e}")
        return []


def _identify_top_movers(positions: List[Dict[str, Any]], gainers_count: int = 3, losers_count: int = 3) -> Dict[str, Dict[str, Any]]:
    """Identify top gainers and losers from positions."""
    # Separate gainers and losers
    gainers = [p for p in positions if p.get('change_percent', 0) > 0]
    losers = [p for p in positions if p.get('change_percent', 0) < 0]

    # Sort and take top ones
    top_gainers = sorted(gainers, key=lambda x: x.get('change_percent', 0), reverse=True)[:gainers_count]
    top_losers = sorted(losers, key=lambda x: x.get('change_percent', 0))[:losers_count]

    # Combine results
    top_movers = {}

    for position in top_gainers + top_losers:
        ticker = position['ticker']
        if ticker not in top_movers:  # Avoid duplicates
            top_movers[ticker] = {
                'ticker': ticker,
                'isin': position.get('isin'),
                'change_percent': position.get('change_percent'),
                'currency': position.get('currency'),
                'position_type': 'gainer' if position.get('change_percent', 0) > 0 else 'loser',
                'magnitude': abs(position.get('change_percent', 0))
            }

    return top_movers


def _fetch_news_for_tickers_batch(news_fetcher: NewsFetcherService, tickers: List[str],
                                quality: NewsQualityLevel, limit: int) -> Dict[str, Any]:
    """Fetch news for multiple tickers in batch."""
    try:
        result = news_fetcher.fetch_news_batch(tickers, quality=quality, limit=limit)

        return {
            'results': result.results,
            'total_api_calls': result.total_api_calls,
            'total_cached_articles': result.total_cached_articles,
            'total_processed_articles': result.total_processed_articles,
            'failed_tickers': result.failed_tickers,
            'average_processing_time': result.average_processing_time,
            'batch_size': result.batch_size
        }
    except Exception as e:
        logger.error(f"Error fetching news batch: {e}")
        return {
            'results': [],
            'total_api_calls': 0,
            'total_cached_articles': 0,
            'total_processed_articles': 0,
            'failed_tickers': tickers,  # All tickers failed
            'average_processing_time': 0,
            'batch_size': len(tickers)
        }


def _process_and_store_news_results(db, results: Dict[str, Any], top_movers: Dict[str, Any]) -> Dict[str, Any]:
    """Process and store news results from fetcher."""
    stats = {
        'articles_stored': 0,
        'articles_duplicates': 0,
        'articles_filtered': 0,
        'processing_time': 0
    }

    start_time = time.time()

    for fetch_result in results.get('results', []):
        ticker = fetch_result.ticker
        articles = fetch_result.articles

        if not articles:
            continue

        # Store articles for this ticker
        stored_count, duplicates_count = _store_news_articles_batch(db, articles, ticker)

        stats['articles_stored'] += stored_count
        stats['articles_duplicates'] += duplicates_count
        stats['articles_filtered'] += (len(articles) - stored_count - duplicates_count)

        # Update mover significance based on news relevance
        if ticker in top_movers and articles:
            avg_relevance = sum(a.get('relevance_score', 0) for a in articles) / len(articles)
            top_movers[ticker]['news_relevance'] = avg_relevance

    stats['processing_time'] = time.time() - start_time

    return stats


def _store_news_articles(db, articles: List[Dict[str, Any]], ticker: str) -> int:
    """Store news articles for a specific ticker."""
    stored_count = 0

    for article_data in articles:
        try:
            # Check if article already exists (prevent duplicates)
            existing = db.execute(
                select(NewsArticle)
                .where(
                    and_(
                        NewsArticle.source == NewsSource.ALPHA_VANTAGE,
                        NewsArticle.article_id == article_data.get('id', '')
                    )
                )
            ).scalar_one_or_none()

            if existing:
                # Update existing article with new data if needed
                _update_existing_article(existing, article_data)
                stored_count += 1
                continue

            # Create new article
            article = _create_news_article(article_data, ticker)
            db.add(article)
            stored_count += 1

        except IntegrityError:
            # Duplicate entry, skip
            db.rollback()
            continue
        except Exception as e:
            logger.warning(f"Error storing article {article_data.get('id', 'unknown')}: {e}")
            continue

    if stored_count > 0:
        db.commit()

    return stored_count


def _store_news_articles_batch(db, articles: List[Dict[str, Any]], ticker: str) -> tuple:
    """Store multiple news articles in batch with better performance."""
    stored_count = 0
    duplicates_count = 0

    try:
        # Batch process articles
        for article_data in articles:
            existing = db.execute(
                select(NewsArticle)
                .where(
                    and_(
                        NewsArticle.source == NewsSource.ALPHA_VANTAGE,
                        NewsArticle.article_id == article_data.get('id', '')
                    )
                )
            ).scalar_one_or_none()

            if existing:
                duplicates_count += 1
                continue

            article = _create_news_article(article_data, ticker)
            db.add(article)
            stored_count += 1

        if stored_count > 0:
            db.commit()

        return stored_count, duplicates_count

    except Exception as e:
        logger.error(f"Error in batch article storage: {e}")
        db.rollback()
        return 0, 0


def _create_news_article(article_data: Dict[str, Any], ticker: str) -> NewsArticle:
    """Create a NewsArticle from API data."""
    # Extract publication datetime
    published_at = article_data.get('time_published')
    if isinstance(published_at, str):
        # Parse ISO format like "20230101T163000"
        try:
            if 'T' in published_at:
                published_at = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
            else:
                published_at = datetime.strptime(published_at, '%Y%m%dT%H%M%S')
        except ValueError:
            published_at = datetime.now(timezone.utc)
    else:
        published_at = datetime.now(timezone.utc)

    return NewsArticle(
        article_id=article_data.get('id', ''),
        title=article_data.get('title'),
        url=article_data.get('url'),
        source=NewsSource.ALPHA_VANTAGE,
        source_name=article_data.get('source'),
        summary=article_data.get('summary'),
        language=article_data.get('language', 'en'),
        published_at=published_at,
        published_date=published_at.date(),
        banner_image_url=article_data.get('banner_image'),
        topics_json=article_data.get('topics'),
        relevance_score=article_data.get('relevance_score'),
        sentiment_score=article_data.get('sentiment_score'),
        sentiment_label=article_data.get('sentiment_label'),
        source_data=article_data.get('source_data')
    )


def _update_existing_article(article: NewsArticle, article_data: Dict[str, Any]):
    """Update existing article with new data."""
    # Update fields that might have changed
    if article_data.get('summary') and not article.summary:
        article.summary = article_data['summary']
    if article_data.get('banner_image') and not article.banner_image_url:
        article.banner_image_url = article_data['banner_image']
    if article_data.get('sentiment_score') and not article.sentiment_score:
        article.sentiment_score = article_data['sentiment_score']
    if article_data.get('sentiment_label') and not article.sentiment_label:
        article.sentiment_label = article_data['sentiment_label']

    article.updated_at = datetime.now(timezone.utc)


def _parse_quality_level(quality: str) -> Optional[NewsQualityLevel]:
    """Parse quality level string to enum."""
    quality_map = {
        'low': NewsQualityLevel.LOW,
        'medium': NewsQualityLevel.MEDIUM,
        'high': NewsQualityLevel.HIGH,
        'recent': NewsQualityLevel.RECENT,
        'popular': NewsQualityLevel.POPULAR
    }
    return quality_map.get(quality.lower())


def _get_active_tickers(db) -> List[str]:
    """Get list of all active tickers."""
    result = db.execute(
        select(Position.current_ticker)
        .where(Position.quantity > 0)
        .distinct()
    ).scalars().all()

    return list(result)


def _update_ticker_news_timestamp(db, ticker: str):
    """Update the last news update timestamp for a specific ticker."""
    # This could be implemented with a separate tracking table if needed
    pass


def get_news_fetcher_health_status() -> Dict[str, Any]:
    """Get health status of news fetcher service."""
    try:
        news_fetcher = NewsFetcherService()
        return news_fetcher.get_health_status()
    except Exception as e:
        logger.error(f"Error getting news fetcher health status: {e}")
        return {
            "service_name": "NewsFetcherService",
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }