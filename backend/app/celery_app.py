"""
Celery application configuration for background tasks.

Scheduled tasks:
- 23:00 CET: update_daily_prices - Fetch latest prices from APIs
- 23:15 CET: calculate_all_metrics - Calculate IRR and portfolio metrics
- 23:30 CET: create_daily_snapshot - Create daily portfolio snapshots
"""
from celery import Celery
from celery.schedules import crontab
from app.config import settings

# Create Celery instance
celery_app = Celery(
    "portfolio_tracker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.price_updates",
        "app.tasks.metric_calculation",
        "app.tasks.snapshots",
        "app.tasks.auto_backfill"
    ]
)

# Celery configuration
celery_app.conf.update(
    # Timezone
    timezone="Europe/Rome",
    enable_utc=False,

    # Task configuration
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    result_expires=86400,  # 24 hours

    # Worker configuration
    worker_pool="solo",  # Use solo pool to avoid SIGSEGV with curl_cffi in yfinance
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,

    # Retry configuration
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    # Beat schedule
    beat_schedule={
        "update-daily-prices": {
            "task": "app.tasks.price_updates.update_daily_prices",
            "schedule": crontab(hour=23, minute=0),  # 23:00 CET
            "options": {
                "expires": 3600,  # Task expires after 1 hour
            }
        },
        "calculate-all-metrics": {
            "task": "app.tasks.metric_calculation.calculate_all_metrics",
            "schedule": crontab(hour=23, minute=15),  # 23:15 CET
            "options": {
                "expires": 3600,
            }
        },
        "create-daily-snapshot": {
            "task": "app.tasks.snapshots.create_daily_snapshot",
            "schedule": crontab(hour=23, minute=30),  # 23:30 CET
            "options": {
                "expires": 3600,
            }
        },
    },
)

if __name__ == "__main__":
    celery_app.start()
