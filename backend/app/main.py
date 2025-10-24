"""
FastAPI main application.

Portfolio Tracker backend API.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import time
from typing import Dict, Any

from app.config import settings
from app.api import (
    transactions_router,
    portfolio_router,
    assets_router,
    prices_router,
    benchmark_router,
    crypto_router,
    blockchain_router
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# Health check cache (in-memory, short TTL)
_health_cache: Dict[str, Dict[str, Any]] = {}
_HEALTH_CACHE_TTL = 30  # 30 seconds TTL for health checks

def _get_cache_key() -> str:
    """Generate cache key for health check."""
    return f"health:{settings.environment}"


def _is_cache_valid(timestamp: float) -> bool:
    """Check if cache entry is still valid."""
    return time.time() - timestamp < _HEALTH_CACHE_TTL


def _get_cached_health() -> Dict[str, Any] | None:
    """Get cached health data if valid."""
    cache_key = _get_cache_key()
    if cache_key in _health_cache:
        cached_data = _health_cache[cache_key]
        if _is_cache_valid(cached_data["timestamp"]):
            logger.debug("Using cached health check data")
            return cached_data["data"]
        else:
            # Remove expired cache entry
            del _health_cache[cache_key]
    return None


def _cache_health_data(data: Dict[str, Any]) -> None:
    """Cache health check data with timestamp."""
    cache_key = _get_cache_key()
    _health_cache[cache_key] = {
        "data": data,
        "timestamp": time.time()
    }
    logger.debug("Cached health check data")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="Self-hosted portfolio tracking with performance analytics",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(transactions_router)
app.include_router(portfolio_router)
app.include_router(assets_router)
app.include_router(prices_router)
app.include_router(benchmark_router)
app.include_router(crypto_router)
app.include_router(blockchain_router)


@app.get("/api/health")
async def health_check():
    """Health check endpoint with database migration status and caching."""
    # Check cache first
    cached_health = _get_cached_health()
    if cached_health:
        return cached_health

    # No valid cache, perform health check
    from app.database import AsyncSessionLocal
    from sqlalchemy import text

    health_data = {
        "status": "healthy",
        "app": settings.app_name,
        "environment": settings.environment,
        "database": "unknown",
        "cached": False
    }

    # Check database connectivity and migration status
    try:
        async with AsyncSessionLocal() as session:
            # Test basic database connectivity first
            try:
                await session.execute(text("SELECT 1"))
            except Exception as conn_error:
                logger.warning(f"Database connection failed: {conn_error}")
                health_data["database"] = "connection_failed"
                health_data["database_error"] = f"Connection failed: {str(conn_error)}"
                return health_data

            # Check if alembic_version table exists and get current revision
            try:
                result = await session.execute(
                    text("SELECT version_num FROM alembic_version LIMIT 1")
                )
                current_revision = result.scalar()

                if current_revision:
                    health_data["database"] = "connected"
                    health_data["migration_revision"] = current_revision
                else:
                    health_data["database"] = "connected_no_migrations"
            except Exception as table_error:
                # Check if this is specifically a "table does not exist" error
                error_str = str(table_error).lower()
                if any(keyword in error_str for keyword in ["does not exist", "no such table", "relation", "table"]):
                    logger.debug("alembic_version table not found (expected for first deployment)")
                    health_data["database"] = "connected_no_migrations"
                else:
                    # Other SQL error (permissions, corrupted table, etc.)
                    logger.warning(f"Database query failed: {table_error}")
                    health_data["database"] = "query_failed"
                    health_data["database_error"] = f"Query failed: {str(table_error)}"

    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
        health_data["database"] = "error"
        health_data["database_error"] = f"Unexpected error: {str(e)}"

    # Cache the result (even errors, to avoid repeated failed queries)
    _cache_health_data(health_data)
    logger.debug("Health check completed and cached")

    return health_data


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Portfolio Tracker API",
        "docs": "/api/docs",
        "health": "/api/health"
    }


# Startup event
@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    logger.info(f"Starting {settings.app_name} in {settings.environment} mode")
    logger.info(f"Allowed origins: {settings.allowed_origins}")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    logger.info("Shutting down Portfolio Tracker API")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=settings.log_level.lower()
    )
