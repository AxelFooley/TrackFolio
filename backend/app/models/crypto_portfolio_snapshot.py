"""
Crypto portfolio snapshot model - Daily snapshots of crypto portfolio value for historical charts.
"""
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import String, Numeric, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CryptoPortfolioSnapshot(Base):
    """
    CryptoPortfolioSnapshot model storing daily crypto portfolio valuation snapshots.

    Similar to PortfolioSnapshot but specifically for crypto portfolios.
    Used for crypto performance charts and historical tracking.
    """
    __tablename__ = "crypto_portfolio_snapshots"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Foreign key to crypto portfolio
    portfolio_id: Mapped[int] = mapped_column(
        ForeignKey("crypto_portfolios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated crypto portfolio ID"
    )

    # Snapshot date (unique per portfolio)
    snapshot_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="Date of the snapshot"
    )

    # Portfolio values
    total_value_eur: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=2),
        nullable=False,
        comment="Total portfolio value in EUR"
    )

    total_value_usd: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=2),
        nullable=False,
        comment="Total portfolio value in USD"
    )

    total_cost_basis: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=2),
        nullable=False,
        comment="Total cost basis in portfolio base currency"
    )

    # Currency information
    base_currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        comment="Portfolio base currency (EUR/USD)"
    )

    # Holdings breakdown (JSON string of asset allocation)
    holdings_breakdown: Mapped[str] = mapped_column(
        String(2000),
        nullable=True,
        comment="JSON string of holdings breakdown by symbol"
    )

    # Performance metrics
    total_return_pct: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=4),
        nullable=True,
        comment="Total return percentage"
    )

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="When the snapshot was created"
    )

    # Unique constraint on portfolio_id and snapshot_date
    __table_args__ = (
        UniqueConstraint('portfolio_id', 'snapshot_date', name='uix_crypto_portfolio_snapshot_date'),
    )

    def __repr__(self) -> str:
        """
        Return a concise string representation of the crypto portfolio snapshot for debugging.
        
        Returns:
            str: String containing the snapshot's `id`, `portfolio_id`, `snapshot_date`, `total_value_eur`, and `total_value_usd`.
        """
        return (
            f"CryptoPortfolioSnapshot(id={self.id!r}, "
            f"portfolio_id={self.portfolio_id!r}, "
            f"date={self.snapshot_date!r}, "
            f"value_eur={self.total_value_eur!r}, "
            f"value_usd={self.total_value_usd!r})"
        )