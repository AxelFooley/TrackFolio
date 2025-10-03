"""
CachedMetrics model - Stores calculated metrics with expiry for performance.
"""
from datetime import datetime
from sqlalchemy import String, DateTime, JSON, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from typing import Dict, Any

from app.database import Base


class CachedMetrics(Base):
    """
    CachedMetrics model for storing expensive calculations with TTL.

    Based on PRD Section 6 - Database Schema.
    Used to cache IRR calculations, portfolio returns, and other metrics
    to avoid repeated expensive computations.
    """
    __tablename__ = "cached_metrics"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Metric identification
    metric_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of metric: position_irr, portfolio_return, etc."
    )

    metric_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Key identifier: ticker or 'global'"
    )

    # Metric data (flexible JSON storage)
    metric_value: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        comment="Flexible JSON storage for different metric types"
    )

    # Timing
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="When the metric was calculated"
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
        comment="When the metric expires and needs recalculation"
    )

    # Composite unique constraint and indexes
    __table_args__ = (
        UniqueConstraint('metric_type', 'metric_key', name='uix_metric_type_key'),
        Index('ix_cached_metrics_type_key', 'metric_type', 'metric_key'),
        Index('ix_cached_metrics_expires', 'expires_at'),
    )

    def __repr__(self) -> str:
        return (
            f"CachedMetrics(id={self.id!r}, "
            f"type={self.metric_type!r}, "
            f"key={self.metric_key!r}, "
            f"expires_at={self.expires_at!r})"
        )

    @property
    def is_expired(self) -> bool:
        """Check if the cached metric has expired."""
        return datetime.utcnow() > self.expires_at
