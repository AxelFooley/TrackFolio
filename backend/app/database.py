"""
Database connection setup and session management.
"""
from typing import AsyncGenerator
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, sessionmaker
import os


# Database URL from environment variable
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://portfolio:portfolio@localhost:5432/portfolio_db"
)

# Convert to async URL for asyncpg
ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")


# Declarative Base class
class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


# Synchronous engine (for Alembic migrations)
sync_engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

# Synchronous session factory
SyncSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=sync_engine
)


# Asynchronous engine (for FastAPI)
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

# Asynchronous session factory
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


# Dependency for FastAPI endpoints
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function to get database session.

    Usage in FastAPI:
        @app.get("/")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Synchronous session context manager (for Celery tasks)
def get_sync_db():
    """
    Context manager to get synchronous database session.

    Usage in Celery tasks:
        with get_sync_db() as db:
            ...
    """
    db = SyncSessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# Create all tables (used for testing, migrations should be preferred)
async def create_tables():
    """Create all database tables. Use migrations in production."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# Drop all tables (used for testing only)
async def drop_tables():
    """Drop all database tables. DANGER: Use only in testing."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
