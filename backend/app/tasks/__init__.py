"""
Background tasks package.

All tasks are scheduled via Celery Beat in celery_app.py.
"""
from app.tasks.price_updates import update_daily_prices
from app.tasks.metric_calculation import calculate_all_metrics
from app.tasks.snapshots import create_daily_snapshot

__all__ = [
    "update_daily_prices",
    "calculate_all_metrics",
    "create_daily_snapshot",
]
