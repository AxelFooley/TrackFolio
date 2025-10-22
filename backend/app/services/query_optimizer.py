"""
Query optimization service with intelligent caching and batch loading.

Provides optimized database queries with automatic caching and batch processing
to reduce database load and improve performance.
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Union
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from functools import wraps

from app.services.cache import cache
from app.services.cache_decorators import cache_result, cache_manager
from app.models import Position, Transaction, PriceHistory, PortfolioSnapshot

logger = logging.getLogger(__name__)


class QueryOptimizer:
    """Optimized query executor with caching and batch loading."""

    def __init__(self):
        self.query_stats = {
            'total_queries': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'query_times': [],
            'batch_operations': 0
        }

    async def execute_cached_query(
        self,
        query_func,
        cache_key: str,
        ttl_seconds: int = 300,
        invalidate_on: Optional[List[str]] = None
    ) -> Any:
        """
        Execute a database query with intelligent caching.

        Args:
            query_func: Async function that executes the database query
            cache_key: Cache key for the result
            ttl_seconds: Time to live in seconds
            invalidate_on: List of conditions that should invalidate cache

        Returns:
            Query result
        """
        self.query_stats['total_queries'] += 1

        # Check cache first
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            self.query_stats['cache_hits'] += 1
            logger.debug(f"Cache hit for query: {cache_key}")
            return cached_result

        self.query_stats['cache_misses'] += 1
        logger.debug(f"Cache miss for query: {cache_key}")

        # Execute query
        start_time = datetime.utcnow()
        try:
            result = await query_func()
            end_time = datetime.utcnow()
            query_duration = (end_time - start_time).total_seconds()

            self.query_stats['query_times'].append(query_duration)
            logger.debug(f"Query executed in {query_duration:.3f}s: {cache_key}")

            # Cache the result
            cache.set(cache_key, result, ttl_seconds=ttl_seconds)
            return result

        except Exception as e:
            logger.error(f"Query failed for {cache_key}: {e}")
            raise

    async def batch_load_positions_with_prices(
        self,
        db: AsyncSession,
        position_ids: List[int],
        price_days: int = 2
    ) -> Dict[int, Dict]:
        """
        Batch load positions with their latest prices to avoid N+1 queries.

        Args:
            db: Database session
            position_ids: List of position IDs to load
            price_days: Number of days of price history to load

        Returns:
            Dictionary mapping position IDs to position data with prices
        """
        if not position_ids:
            return {}

        self.query_stats['batch_operations'] += 1
        logger.debug(f"Batch loading {len(position_ids)} positions with prices")

        # Create cache key
        cache_key = f"batch_positions_prices:{hash(tuple(sorted(position_ids)))}:{price_days}"

        # Check cache first
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result

        # Batch load positions
        positions_result = await db.execute(
            select(Position)
            .where(Position.id.in_(position_ids))
            .options(selectinload(Position.transactions))
        )
        positions = positions_result.scalars().all()

        # Extract tickers for price loading
        tickers = [pos.current_ticker for pos in positions if pos.current_ticker]

        # Batch load latest prices
        price_result = await db.execute(
            select(PriceHistory)
            .where(PriceHistory.ticker.in_(tickers))
            .order_by(PriceHistory.ticker, PriceHistory.date.desc())
        )
        price_records = price_result.scalars().all()

        # Create price lookup (latest 2 days for each ticker)
        price_by_ticker = {}
        for record in price_records:
            ticker = record.ticker
            if ticker not in price_by_ticker:
                price_by_ticker[ticker] = []
            price_by_ticker[ticker].append(record)

        # Build result
        result = {}
        for position in positions:
            position_data = {
                'id': position.id,
                'ticker': position.current_ticker,
                'quantity': position.quantity,
                'average_cost': position.average_cost,
                'current_value': position.current_value,
                'unrealized_gain': position.unrealized_gain,
                'transactions': position.transactions,
                'latest_prices': price_by_ticker.get(position.current_ticker, [])
            }
            result[position.id] = position_data

        # Cache result with 5-minute TTL
        cache.set(cache_key, result, ttl_seconds=300)
        return result

    async def get_portfolio_overview_optimized(
        self,
        db: AsyncSession,
        user_id: Optional[int] = None
    ) -> Dict:
        """
        Optimized portfolio overview with multiple caching strategies.

        Args:
            db: Database session
            user_id: User ID (for multi-user support)

        Returns:
            Portfolio overview data
        """
        cache_key = f"portfolio_overview:{user_id or 'default'}"

        # Try cache first
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result

        # Execute optimized query
        try:
            # Get total holdings count (for quick overview)
            holdings_count = await db.scalar(
                select(func.count(Position.id))
            )

            # Get total portfolio value with aggregation
            portfolio_summary = await db.execute(
                select(
                    func.sum(Position.current_value).label('total_value'),
                    func.sum(Position.unrealized_gain).label('total_profit'),
                    func.sum(Position.cost_basis).label('total_cost_basis')
                )
            )
            summary_data = portfolio_summary.first()

            # Get current date for daily snapshot
            today = datetime.utcnow().date()

            # Get latest performance snapshot
            performance_snapshot = await db.execute(
                select(PortfolioSnapshot)
                .where(PortfolioSnapshot.snapshot_date == today)
                .order_by(PortfolioSnapshot.created_at.desc())
                .limit(1)
            )
            snapshot = performance_snapshot.scalar_one_or_none()

            result = {
                'total_value': summary_data.total_value or Decimal('0'),
                'total_profit': summary_data.total_profit or Decimal('0'),
                'total_cost_basis': summary_data.total_cost_basis or Decimal('0'),
                'holdings_count': holdings_count,
                'current_date': today.isoformat(),
                'snapshot': {
                    'daily_return': snapshot.daily_return if snapshot else None,
                    'total_return': snapshot.total_return if snapshot else None,
                } if snapshot else None,
            }

            # Cache with 5-minute TTL
            cache.set(cache_key, result, ttl_seconds=300)
            return result

        except Exception as e:
            logger.error(f"Error getting portfolio overview: {e}")
            raise

    async def get_holdings_optimized(
        self,
        db: AsyncSession,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = 'current_value',
        sort_direction: str = 'desc'
    ) -> List[Position]:
        """
        Optimized holdings query with caching and pagination.

        Args:
            db: Database session
            limit: Maximum number of records to return
            offset: Offset for pagination
            sort_by: Field to sort by
            sort_direction: Sort direction ('asc' or 'desc')

        Returns:
            List of positions
        """
        # Create cache key
        cache_key = f"holdings:{limit}:{offset}:{sort_by}:{sort_direction}"

        # Check cache first
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result

        # Build query dynamically
        query = select(Position)

        # Apply sorting
        if sort_by == 'current_value':
            sort_column = Position.current_value
        elif sort_by == 'quantity':
            sort_column = Position.quantity
        elif sort_by == 'ticker':
            sort_column = Position.current_ticker
        else:
            sort_column = Position.current_value

        if sort_direction == 'desc':
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # Apply pagination
        query = query.limit(limit).offset(offset)

        # Execute query
        result = await db.execute(query)
        holdings = result.scalars().all()

        # Cache with 1-minute TTL for frequently changing data
        cache.set(cache_key, holdings, ttl_seconds=60)
        return holdings

    def get_query_stats(self) -> Dict:
        """Get query performance statistics."""
        stats = self.query_stats.copy()

        # Calculate average query time
        if stats['query_times']:
            stats['avg_query_time'] = sum(stats['query_times']) / len(stats['query_times'])
        else:
            stats['avg_query_time'] = 0

        # Calculate cache hit rate
        if stats['total_queries'] > 0:
            stats['cache_hit_rate'] = stats['cache_hits'] / stats['total_queries']
        else:
            stats['cache_hit_rate'] = 0

        return stats

    def clear_cache_for_position(self, position_id: int) -> bool:
        """
        Clear cache entries related to a specific position.

        Args:
            position_id: Position ID to clear cache for

        Returns:
            True if cache was cleared, False otherwise
        """
        patterns = [
            f"batch_positions_prices:*{position_id}*",
            f"portfolio_overview:*{position_id}*",
            f"holdings:*{position_id}*",
        ]

        total_cleared = 0
        for pattern in patterns:
            count = cache.clear_pattern(pattern)
            total_cleared += count

        return total_cleared > 0

    async def invalidate_portfolio_cache_on_transaction(
        self,
        db: AsyncSession,
        transaction_id: int
    ) -> bool:
        """
        Invalidate portfolio cache when a transaction is added/updated.

        Args:
            db: Database session
            transaction_id: Transaction ID that triggered invalidation

        Returns:
            True if cache was invalidated, False otherwise
        """
        try:
            # Get the transaction to determine which position it affects
            transaction_result = await db.execute(
                select(Transaction)
                .where(Transaction.id == transaction_id)
            )
            transaction = transaction_result.scalar_one_or_none()

            if not transaction:
                return False

            # Clear cache for the affected position
            success = cache_manager.invalidate_portfolio_cache()

            logger.info(f"Invalidated portfolio cache due to transaction {transaction_id}")
            return success

        except Exception as e:
            logger.error(f"Error invalidating portfolio cache: {e}")
            return False


# Global query optimizer instance
query_optimizer = QueryOptimizer()


def with_query_optimization(func):
    """
    Decorator to apply query optimization to database functions.

    Args:
        func: Database function to optimize
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        return await query_optimizer.execute_cached_query(
            lambda: func(*args, **kwargs),
            cache_key=f"{func.__name__}:{hash(str(args) + str(kwargs))}",
            ttl_seconds=300
        )
    return wrapper