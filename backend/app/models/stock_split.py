"""
StockSplit model - Track stock split events.
"""
from datetime import date, datetime
from sqlalchemy import String, Integer, Date, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StockSplit(Base):
    """
    Stock split tracking model.

    Tracks when a stock splits and how the ticker changes.
    """
    __tablename__ = "stock_splits"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # ISIN of the security that split
    isin: Mapped[str] = mapped_column(String(12), nullable=False, index=True)

    # Split date
    split_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Split ratio: numerator:denominator (e.g., 3:1 means 3 new shares for 1 old)
    split_ratio_numerator: Mapped[int] = mapped_column(Integer, nullable=False)
    split_ratio_denominator: Mapped[int] = mapped_column(Integer, nullable=False)

    # Ticker before and after split
    old_ticker: Mapped[str] = mapped_column(String(50), nullable=True)
    new_ticker: Mapped[str] = mapped_column(String(50), nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint('isin', 'split_date', name='uq_stock_split_isin_date'),
    )

    def __repr__(self) -> str:
        return (
            f"StockSplit(isin={self.isin!r}, "
            f"date={self.split_date!r}, "
            f"ratio={self.split_ratio_numerator}:{self.split_ratio_denominator})"
        )
