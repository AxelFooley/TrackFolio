"""
Position model - Current holdings and aggregate position data.
"""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Numeric, DateTime, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column
import enum

from app.database import Base


class AssetType(str, enum.Enum):
    """Asset type enumeration."""
    STOCK = "stock"
    ETF = "etf"
    CRYPTO = "crypto"


class Position(Base):
    """
    Position model representing current holdings for each asset.

    Based on PRD Section 6 - Database Schema.
    Aggregates transaction data to show current position state.
    """
    __tablename__ = "positions"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Asset identification
    current_ticker: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Current ticker symbol (may change after splits)"
    )
    isin: Mapped[str] = mapped_column(
        String(12),
        nullable=False,
        unique=True,
        index=True,
        comment="ISIN - unique identifier for the security"
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)

    # Asset classification
    asset_type: Mapped[AssetType] = mapped_column(
        SQLEnum(AssetType, native_enum=False),
        nullable=False
    )

    # Position details
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8),
        nullable=False,
        comment="Current number of shares held"
    )

    average_cost: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8),
        nullable=False,
        comment="Average cost per share including fees"
    )

    cost_basis: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=2),
        nullable=False,
        comment="Total amount invested including fees"
    )

    # Metadata
    last_calculated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="Last time position was recalculated from transactions"
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return (
            f"Position(id={self.id!r}, "
            f"isin={self.isin!r}, "
            f"ticker={self.current_ticker!r}, "
            f"type={self.asset_type.value!r}, "
            f"quantity={self.quantity!r}, "
            f"avg_cost={self.average_cost!r})"
        )
