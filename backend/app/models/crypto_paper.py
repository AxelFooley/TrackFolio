"""
Crypto Paper Wallet models - Stores crypto portfolio transactions.
"""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Numeric, DateTime, Enum as SQLEnum, Index, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.database import Base


class CryptoTransactionType(str, enum.Enum):
    """Crypto transaction type enumeration."""
    BUY = "buy"
    SELL = "sell"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"


class CryptoPaperPortfolio(Base):
    """
    Crypto Paper Portfolio model representing a collection of crypto transactions.

    Used for tracking crypto paper wallet holdings separate from stock portfolios.
    """
    __tablename__ = "crypto_paper_portfolios"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Portfolio details
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Portfolio name for identification"
    )
    description: Mapped[str] = mapped_column(
        String(500),
        nullable=True,
        comment="Optional portfolio description"
    )

    # User identification (for future multi-user support)
    user_id: Mapped[int] = mapped_column(
        nullable=False,
        default=1,
        index=True,
        comment="User ID, defaults to 1 for single-user setup"
    )

    # Timestamps
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

    # Relationships (can be added later if needed)
    # transactions: Mapped[list["CryptoPaperTransaction"]] = relationship(
    #     "CryptoPaperTransaction",
    #     back_populates="portfolio",
    #     cascade="all, delete-orphan"
    # )

    def __repr__(self) -> str:
        return (
            f"CryptoPaperPortfolio(id={self.id!r}, "
            f"name={self.name!r}, "
            f"user_id={self.user_id!r})"
        )


class CryptoPaperTransaction(Base):
    """
    Crypto Paper Transaction model representing crypto buy/sell/transfer operations.

    Similar to Transaction model but adapted for crypto assets with CoinGecko integration.
    """
    __tablename__ = "crypto_paper_transactions"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Foreign key to portfolio
    portfolio_id: Mapped[int] = mapped_column(
        ForeignKey("crypto_paper_portfolios.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Asset identification
    symbol: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Crypto symbol like BTC, ETH"
    )
    coingecko_id: Mapped[str] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="CoinGecko ID for API calls"
    )

    # Transaction details
    transaction_type: Mapped[CryptoTransactionType] = mapped_column(
        SQLEnum(CryptoTransactionType, native_enum=False),
        nullable=False,
        index=True
    )

    # Quantities and prices
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8),
        nullable=False,
        comment="Quantity of crypto asset"
    )
    price_at_execution: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8),
        nullable=False,
        comment="Price per unit at time of execution"
    )

    # Currency and amounts
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="USD",
        comment="USD or EUR"
    )

    # Fees
    fee: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=2),
        nullable=False,
        default=0,
        comment="Transaction fee"
    )

    # Transaction timestamp
    timestamp: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
        comment="When the transaction occurred"
    )

    # Metadata timestamps
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

    # Relationships (can be added later if needed)
    # portfolio: Mapped["CryptoPaperPortfolio"] = relationship(
    #     "CryptoPaperPortfolio",
    #     back_populates="transactions"
    # )

    # Composite indexes for common queries
    __table_args__ = (
        Index('ix_crypto_transactions_portfolio_symbol', 'portfolio_id', 'symbol'),
        Index('ix_crypto_transactions_portfolio_type', 'portfolio_id', 'transaction_type'),
        Index('ix_crypto_transactions_symbol_date', 'symbol', 'timestamp'),
        Index('ix_crypto_transactions_type_date', 'transaction_type', 'timestamp'),
    )

    def __repr__(self) -> str:
        return (
            f"CryptoPaperTransaction(id={self.id!r}, "
            f"portfolio_id={self.portfolio_id!r}, "
            f"symbol={self.symbol!r}, "
            f"type={self.transaction_type.value!r}, "
            f"quantity={self.quantity!r}, "
            f"timestamp={self.timestamp!r})"
        )