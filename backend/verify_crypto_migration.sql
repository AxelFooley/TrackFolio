-- Verification script for crypto optimization migration
-- Run this script after deploying the crypto optimization migration
-- to verify all indexes were created correctly

-- Check that all crypto-related indexes exist
SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND indexname LIKE '%crypto%'
ORDER BY tablename, indexname;

-- Expected results should include:
-- ix_transactions_crypto_isin
-- ix_transactions_crypto_tickers
-- ix_transactions_crypto_history
-- ix_positions_crypto_isin
-- ix_positions_crypto_type
-- ix_positions_crypto_portfolio
-- ix_price_history_crypto_tickers
-- ix_price_history_crypto_source
-- ix_price_history_crypto_range
-- ix_cached_metrics_crypto
-- ix_stock_splits_crypto

-- Verify partial indexes by checking index conditions
SELECT
    i.relname as index_name,
    am.amname as index_type,
    pg_get_indexdef(i.oid) as index_definition,
    pg_catalog.pg_get_expr(i.indpred, i.indrelid) as where_clause
FROM pg_class t
JOIN pg_index ix ON t.oid = ix.indrelid
JOIN pg_class i ON i.oid = ix.indexrelid
JOIN pg_am am ON i.relam = am.oid
WHERE t.relname IN ('transactions', 'positions', 'price_history', 'cached_metrics', 'stock_splits')
  AND i.relname LIKE '%crypto%'
ORDER BY t.relname, i.relname;

-- Test query performance (run with EXPLAIN ANALYZE in production)
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM transactions
WHERE isin LIKE 'XC%'
ORDER BY operation_date DESC
LIMIT 10;

EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM positions
WHERE asset_type = 'crypto'
ORDER BY current_ticker;

EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM price_history
WHERE ticker = 'BTC'
  AND date >= '2024-01-01'
ORDER BY date DESC
LIMIT 100;

-- Check index usage statistics
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE indexname LIKE '%crypto%'
ORDER BY idx_scan DESC;

-- Verify migration version
SELECT version_num FROM alembic_version;

-- Summary query to show crypto data distribution
SELECT
    'Transactions' as table_name,
    COUNT(*) as total_rows,
    COUNT(CASE WHEN isin LIKE 'XC%' THEN 1 END) as crypto_rows,
    ROUND(100.0 * COUNT(CASE WHEN isin LIKE 'XC%' THEN 1 END) / COUNT(*), 2) as crypto_percentage
FROM transactions
UNION ALL
SELECT
    'Positions' as table_name,
    COUNT(*) as total_rows,
    COUNT(CASE WHEN asset_type = 'crypto' THEN 1 END) as crypto_rows,
    ROUND(100.0 * COUNT(CASE WHEN asset_type = 'crypto' THEN 1 END) / COUNT(*), 2) as crypto_percentage
FROM positions
UNION ALL
SELECT
    'Price History (Major Crypto)' as table_name,
    COUNT(*) as total_rows,
    COUNT(CASE WHEN ticker IN ('BTC', 'ETH', 'BNB', 'ADA', 'SOL', 'XRP', 'DOT', 'DOGE', 'AVAX', 'MATIC',
                             'BTC-USD', 'ETH-USD', 'BNB-USD', 'ADA-USD', 'SOL-USD', 'XRP-USD') THEN 1 END) as crypto_rows,
    ROUND(100.0 * COUNT(CASE WHEN ticker IN ('BTC', 'ETH', 'BNB', 'ADA', 'SOL', 'XRP', 'DOT', 'DOGE', 'AVAX', 'MATIC',
                             'BTC-USD', 'ETH-USD', 'BNB-USD', 'ADA-USD', 'SOL-USD', 'XRP-USD') THEN 1 END) / COUNT(*), 2) as crypto_percentage
FROM price_history
WHERE ticker IN ('BTC', 'ETH', 'BNB', 'ADA', 'SOL', 'XRP', 'DOT', 'DOGE', 'AVAX', 'MATIC',
                'BTC-USD', 'ETH-USD', 'BNB-USD', 'ADA-USD', 'SOL-USD', 'XRP-USD');

-- Storage impact analysis
SELECT
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) as index_size,
    pg_relation_size(indexrelid) as index_size_bytes
FROM pg_stat_user_indexes
WHERE indexname LIKE '%crypto%'
ORDER BY pg_relation_size(indexrelid) DESC;