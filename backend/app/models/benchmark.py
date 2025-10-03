"""
Benchmark model - Stores the active benchmark for portfolio comparison.
"""
from datetime import datetime
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Benchmark(Base):
    """
    Benchmark model for portfolio performance comparison.

    Based on PRD Section 6 - Database Schema.
    Single-row table storing only one active benchmark at a time.
    """
    __tablename__ = "benchmark"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Benchmark details
    ticker: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Benchmark ticker symbol (e.g., SPY for S&P 500)"
    )

    description: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Benchmark description"
    )

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return (
            f"Benchmark(id={self.id!r}, "
            f"ticker={self.ticker!r}, "
            f"description={self.description!r})"
        )
