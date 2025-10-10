"""
PriceHistory model - Historical price data for all assets.
"""
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import String, Numeric, Date, DateTime, BigInteger, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PriceHistory(Base):
    """
    PriceHistory model storing historical OHLCV data for assets.

    Based on PRD Section 6 - Database Schema.
    Data fetched from Yahoo Finance API.
    """
    __tablename__ = "price_history"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Asset identification
    ticker: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Asset ticker symbol"
    )

    # Date
    date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
        comment="Price date"
    )

    # OHLCV data
    open: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8),
        nullable=False,
        comment="Opening price"
    )

    high: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8),
        nullable=False,
        comment="Highest price"
    )

    low: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8),
        nullable=False,
        comment="Lowest price"
    )

    close: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8),
        nullable=False,
        comment="Closing price"
    )

    volume: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        comment="Trading volume"
    )

    # Data source
    source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Data source: yahoo"
    )

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    # Composite unique constraint and indexes
    __table_args__ = (
        UniqueConstraint('ticker', 'date', name='uix_ticker_date'),
        Index('ix_price_history_ticker_date', 'ticker', 'date'),
    )

    def __repr__(self) -> str:
        return (
            f"PriceHistory(id={self.id!r}, "
            f"ticker={self.ticker!r}, "
            f"date={self.date!r}, "
            f"close={self.close!r}, "
            f"source={self.source!r})"
        )
