"""optimize_database_for_crypto_support

Revision ID: d4fd2eaf453f
Revises: 962daa5a5477
Create Date: 2025-10-06 20:28:55.732439+00:00

Optimize database performance for cryptocurrency assets.
Adds specialized indexes for crypto ISINs (XC-prefixed), crypto tickers,
and common crypto query patterns while maintaining compatibility
with existing traditional asset data.

Crypto Optimizations:
- Partial indexes for crypto ISINs (XC% pattern)
- Partial indexes for common crypto ticker patterns
- Composite indexes for crypto-specific queries
- Performance indexes for high-volume crypto price history data
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4fd2eaf453f'
down_revision: Union[str, None] = '962daa5a5477'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add crypto-specific indexes and optimizations."""

    # === TRANSACTIONS TABLE OPTIMIZATIONS ===

    # Partial index for crypto transactions (ISINs starting with XC)
    # This optimizes queries filtering for crypto assets only
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_transactions_crypto_isin
        ON transactions (isin)
        WHERE isin LIKE 'XC%';
    """)

    # Partial index for crypto tickers (common patterns)
    # Covers BTC, ETH, and other major crypto tickers
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_transactions_crypto_tickers
        ON transactions (ticker, operation_date)
        WHERE ticker IN ('BTC', 'ETH', 'BNB', 'ADA', 'SOL', 'XRP', 'DOT', 'DOGE', 'AVAX', 'MATIC',
                         'BTC-USD', 'ETH-USD', 'BNB-USD', 'ADA-USD', 'SOL-USD', 'XRP-USD');
    """)

    # Composite index for crypto transaction history queries
    # Optimizes common pattern: crypto asset + date range + transaction type
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_transactions_crypto_history
        ON transactions (isin, operation_date DESC, transaction_type)
        WHERE isin LIKE 'XC%';
    """)

    # === POSITIONS TABLE OPTIMIZATIONS ===

    # Partial index for crypto positions (ISINs starting with XC)
    # Optimizes queries filtering positions by crypto assets
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_positions_crypto_isin
        ON positions (isin, current_ticker)
        WHERE isin LIKE 'XC%';
    """)

    # Partial index for crypto asset type queries
    # Optimizes queries filtering positions by asset_type = 'crypto'
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_positions_crypto_type
        ON positions (current_ticker, quantity, average_cost)
        WHERE asset_type = 'crypto';
    """)

    # Composite index for crypto portfolio calculations
    # Optimizes queries that calculate crypto portfolio value and performance
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_positions_crypto_portfolio
        ON positions (asset_type, current_ticker, last_calculated_at)
        WHERE asset_type = 'crypto';
    """)

    # === PRICE HISTORY TABLE OPTIMIZATIONS ===

    # Partial index for crypto price history (common crypto tickers)
    # Optimizes price lookups for major cryptocurrencies
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_price_history_crypto_tickers
        ON price_history (ticker, date DESC)
        WHERE ticker IN ('BTC', 'ETH', 'BNB', 'ADA', 'SOL', 'XRP', 'DOT', 'DOGE', 'AVAX', 'MATIC',
                         'BTC-USD', 'ETH-USD', 'BNB-USD', 'ADA-USD', 'SOL-USD', 'XRP-USD');
    """)

    # Partial index for crypto price data from CoinGecko source
    # Optimizes queries filtering crypto data by source
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_price_history_crypto_source
        ON price_history (ticker, date, close, volume)
        WHERE source = 'coingecko';
    """)

    # Composite index for crypto price range queries
    # Optimizes common pattern: crypto ticker + date range for charts
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_price_history_crypto_range
        ON price_history (ticker, date DESC, close, high, low)
        WHERE ticker IN ('BTC', 'ETH', 'BNB', 'ADA', 'SOL', 'XRP', 'DOT', 'DOGE', 'AVAX', 'MATIC',
                         'BTC-USD', 'ETH-USD', 'BNB-USD', 'ADA-USD', 'SOL-USD', 'XRP-USD');
    """)

    # === CACHED METRICS OPTIMIZATIONS ===

    # Partial index for crypto cached metrics
    # Optimizes retrieval of cached crypto calculations (IRR, performance metrics)
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_cached_metrics_crypto
        ON cached_metrics (metric_type, metric_key, calculated_at)
        WHERE metric_key LIKE 'crypto_%' OR metric_key LIKE '%_crypto';
    """)

    # === STOCK SPLITS TABLE OPTIMIZATIONS ===

    # While crypto doesn't have traditional stock splits, this index
    # future-proofs the table for potential crypto token splits or events
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_stock_splits_crypto
        ON stock_splits (isin, split_date, new_ticker)
        WHERE isin LIKE 'XC%';
    """)


def downgrade() -> None:
    """Remove crypto-specific indexes and optimizations."""

    # Drop all crypto-specific indexes in reverse order of creation

    # Stock splits crypto index
    op.drop_index('ix_stock_splits_crypto', table_name='stock_splits', postgresql_concurrently=True)

    # Cached metrics crypto indexes
    op.drop_index('ix_cached_metrics_crypto', table_name='cached_metrics', postgresql_concurrently=True)

    # Price history crypto indexes
    op.drop_index('ix_price_history_crypto_range', table_name='price_history', postgresql_concurrently=True)
    op.drop_index('ix_price_history_crypto_source', table_name='price_history', postgresql_concurrently=True)
    op.drop_index('ix_price_history_crypto_tickers', table_name='price_history', postgresql_concurrently=True)

    # Positions crypto indexes
    op.drop_index('ix_positions_crypto_portfolio', table_name='positions', postgresql_concurrently=True)
    op.drop_index('ix_positions_crypto_type', table_name='positions', postgresql_concurrently=True)
    op.drop_index('ix_positions_crypto_isin', table_name='positions', postgresql_concurrently=True)

    # Transactions crypto indexes
    op.drop_index('ix_transactions_crypto_history', table_name='transactions', postgresql_concurrently=True)
    op.drop_index('ix_transactions_crypto_tickers', table_name='transactions', postgresql_concurrently=True)
    op.drop_index('ix_transactions_crypto_isin', table_name='transactions', postgresql_concurrently=True)
