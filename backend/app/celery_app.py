"""
Celery application configuration for background tasks.

Scheduled tasks:
- Every 5 minutes: update_crypto_prices - Fetch latest crypto prices from Yahoo Finance API
- 23:00 CET: update_daily_prices - Fetch latest prices from APIs
- 23:15 CET: calculate_all_metrics - Calculate IRR and portfolio metrics
- 23:15 CET: calculate_crypto_metrics - Calculate crypto portfolio metrics
- 23:30 CET: create_daily_snapshot - Create daily portfolio snapshots
- 23:30 CET: create_daily_crypto_snapshots - Create daily crypto portfolio snapshots
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
        "app.tasks.auto_backfill",
        "app.tasks.update_crypto_prices",
        "app.tasks.crypto_metric_calculation",
        "app.tasks.crypto_snapshots",
        "app.tasks.blockchain_sync",
        "app.tasks.news_updates"
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
        # Crypto tasks - run frequently for current prices
        "update-crypto-prices": {
            "task": "app.tasks.update_crypto_prices.update_crypto_prices",
            "schedule": crontab(minute="*/5"),  # Every 5 minutes
            "options": {
                "expires": 300,  # Task expires after 5 minutes
            }
        },

        # Traditional asset tasks
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

        # Crypto metrics - run at same time as traditional metrics
        "calculate-crypto-metrics": {
            "task": "app.tasks.crypto_metric_calculation.calculate_crypto_metrics",
            "schedule": crontab(hour=23, minute=15),  # 23:15 CET
            "options": {
                "expires": 3600,
            }
        },

        # Snapshot tasks
        "create-daily-snapshot": {
            "task": "app.tasks.snapshots.create_daily_snapshot",
            "schedule": crontab(hour=23, minute=30),  # 23:30 CET
            "options": {
                "expires": 3600,
            }
        },
        "create-daily-crypto-snapshots": {
            "task": "app.tasks.crypto_snapshots.create_daily_crypto_snapshots",
            "schedule": crontab(hour=23, minute=30),  # 23:30 CET
            "options": {
                "expires": 3600,
            }
        },

        # Blockchain sync tasks - sync wallets every 30 minutes
        "sync-blockchain-wallets": {
            "task": "app.tasks.blockchain_sync.sync_all_wallets",
            "schedule": crontab(minute="*/30"),  # Every 30 minutes
            "options": {
                "expires": 1800,  # Task expires after 30 minutes
            }
        },

        # News update tasks - fetch news for top movers
        "fetch-news-for-movers": {
            "task": "app.tasks.news_updates.fetch_news_for_todays_movers",
            "schedule": crontab(minute="*/15"),  # Every 15 minutes during market hours
            "options": {
                "expires": 900,  # Task expires after 15 minutes
            }
        },

        # News cache refresh - daily at market close
        "refresh-news-cache": {
            "task": "app.tasks.news_updates.refresh_news_cache",
            "schedule": crontab(hour=22, minute=30),  # 22:30 CET (4:30 PM ET)
            "options": {
                "expires": 3600,  # Task expires after 1 hour
            }
        },

        # News cleanup - daily early morning
        "cleanup-old-news": {
            "task": "app.tasks.news_updates.cleanup_old_news_articles",
            "schedule": crontab(hour=2, minute=0),  # 02:00 CET
            "options": {
                "expires": 3600,  # Task expires after 1 hour
            }
        },
    },
)

if __name__ == "__main__":
    celery_app.start()
