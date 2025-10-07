"""
Background tasks package.

All tasks are scheduled via Celery Beat in celery_app.py.
"""
from app.tasks.price_updates import update_daily_prices
from app.tasks.metric_calculation import calculate_all_metrics
from app.tasks.snapshots import create_daily_snapshot
from app.tasks.crypto_price_updates import (
    update_crypto_prices,
    update_crypto_price_for_symbol,
    backfill_crypto_prices,
    refresh_crypto_cache
)

__all__ = [
    "update_daily_prices",
    "calculate_all_metrics",
    "create_daily_snapshot",
    "update_crypto_prices",
    "update_crypto_price_for_symbol",
    "backfill_crypto_prices",
    "refresh_crypto_cache",
]
