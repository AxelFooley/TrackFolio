"""
Transaction model - Stores all buy/sell transactions.
"""
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import String, Numeric, Date, DateTime, Enum as SQLEnum, Index
from sqlalchemy.orm import Mapped, mapped_column
import enum

from app.database import Base


class TransactionType(str, enum.Enum):
    """Transaction type enumeration."""
    BUY = "buy"
    SELL = "sell"


class Transaction(Base):
    """
    Transaction model representing a buy or sell operation.

    Based on PRD Section 6 - Database Schema.
    """
    __tablename__ = "transactions"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Dates
    operation_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    value_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Transaction details
    transaction_type: Mapped[TransactionType] = mapped_column(
        SQLEnum(TransactionType, native_enum=False),
        nullable=False
    )

    # Asset identification
    ticker: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    isin: Mapped[str | None] = mapped_column(
        String(12),
        nullable=True,
        index=True,
        comment="ISIN - unique identifier for the security (may be None if not available)"
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)

    # Quantities and prices
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8),
        nullable=False
    )
    price_per_share: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8),
        nullable=False,
        comment="Calculated: amount / quantity"
    )

    # Amounts
    amount_eur: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=2),
        nullable=False,
        comment="Total amount from CSV"
    )
    amount_currency: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=2),
        nullable=False,
        default=0,
        comment="Amount in foreign currency if applicable"
    )

    # Currency
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="EUR",
        comment="EUR or USD"
    )

    # Fees (manually entered after import)
    fees: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=2),
        nullable=False,
        default=0,
        comment="Default 0, manually entered after import"
    )

    # Deduplication fields
    order_reference: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Order ID from broker (can be duplicated for partial fills)"
    )
    transaction_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
        comment="SHA256 hash for duplicate detection (includes quantity+price)"
    )

    # Metadata
    imported_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )
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

    # Composite indexes for common queries
    __table_args__ = (
        Index('ix_transactions_ticker_date', 'ticker', 'operation_date'),
        Index('ix_transactions_type_date', 'transaction_type', 'operation_date'),
    )

    def __repr__(self) -> str:
        return (
            f"Transaction(id={self.id!r}, "
            f"ticker={self.ticker!r}, "
            f"type={self.transaction_type.value!r}, "
            f"quantity={self.quantity!r}, "
            f"date={self.operation_date!r})"
        )
