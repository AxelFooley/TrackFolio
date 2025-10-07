"""API router package."""
from app.api.transactions import router as transactions_router
from app.api.portfolio import router as portfolio_router
from app.api.assets import router as assets_router
from app.api.prices import router as prices_router
from app.api.benchmark import router as benchmark_router
from app.api.crypto_paper import router as crypto_paper_router

__all__ = [
    "transactions_router",
    "portfolio_router",
    "assets_router",
    "prices_router",
    "benchmark_router",
    "crypto_paper_router",
]
