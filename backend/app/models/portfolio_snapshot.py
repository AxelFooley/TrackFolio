"""
PortfolioSnapshot model - Daily snapshots of portfolio value for historical charts.
"""
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import String, Numeric, Date, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PortfolioSnapshot(Base):
    """
    PortfolioSnapshot model storing daily portfolio valuation snapshots.

    Based on PRD Section 6 - Database Schema.
    Used for performance charts and historical tracking.
    """
    __tablename__ = "portfolio_snapshots"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Snapshot date (unique)
    snapshot_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        unique=True,
        index=True,
        comment="Date of the snapshot"
    )

    # Portfolio values
    total_value: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=2),
        nullable=False,
        comment="Total portfolio value in EUR"
    )

    total_cost_basis: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=2),
        nullable=False,
        comment="Total cost basis in EUR"
    )

    # Currency (always EUR for this application)
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="EUR",
        comment="Always EUR"
    )

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint('snapshot_date', name='uix_snapshot_date'),
    )

    def __repr__(self) -> str:
        return (
            f"PortfolioSnapshot(id={self.id!r}, "
            f"date={self.snapshot_date!r}, "
            f"value={self.total_value!r}, "
            f"cost_basis={self.total_cost_basis!r})"
        )
