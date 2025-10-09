"""
Crypto portfolio database models - Standalone crypto tracking feature.
"""
import re
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Numeric, DateTime, Enum as SQLEnum, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
import enum

from app.database import Base


class CryptoTransactionType(str, enum.Enum):
    """Crypto transaction type enumeration."""
    BUY = "buy"
    SELL = "sell"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"


class CryptoCurrency(str, enum.Enum):
    """Supported currencies for crypto transactions."""
    EUR = "EUR"
    USD = "USD"


class CryptoPortfolio(Base):
    """
    Crypto portfolio model representing a standalone crypto portfolio.

    This allows users to track cryptocurrency holdings separately from
    traditional investments, with independent transaction history.
    """
    __tablename__ = "crypto_portfolios"

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
    is_active: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        comment="Whether the portfolio is active"
    )

    # Currency settings
    base_currency: Mapped[CryptoCurrency] = mapped_column(
        SQLEnum(CryptoCurrency, native_enum=False),
        nullable=False,
        default=CryptoCurrency.EUR,
        comment="Base currency for the portfolio"
    )

    # Bitcoin wallet address (optional)
    wallet_address: Mapped[str] = mapped_column(
        String(62),
        nullable=True,
        index=True,
        comment="Bitcoin wallet address for paper wallet tracking (optional)"
    )

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="When the portfolio was created"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="When the portfolio was last updated"
    )

    # Relationships
    transactions: Mapped[list["CryptoTransaction"]] = relationship(
        "CryptoTransaction",
        back_populates="portfolio",
        cascade="all, delete-orphan",
        order_by="CryptoTransaction.timestamp.desc()"
    )

    @validates("wallet_address")
    def validate_wallet_address(self, key, wallet_address):
        """
        Validate Bitcoin address format.

        Supports:
        - Legacy addresses (starting with '1')
        - P2SH addresses (starting with '3')
        - Bech32 addresses (starting with 'bc1')

        Args:
            wallet_address: The Bitcoin address to validate

        Returns:
            The validated wallet address

        Raises:
            ValueError: If the address format is invalid
        """
        if wallet_address is None:
            return None

        wallet_address = wallet_address.strip()

        if not wallet_address:
            return None

        # Basic Bitcoin address validation using regex
        # Legacy (P2PKH) addresses: start with '1', 26-35 characters (1 + 25-34 = 26-35 total)
        # P2SH addresses: start with '3', 26-35 characters (3 + 25-34 = 26-35 total)
        # Bech32 addresses: start with 'bc1', 42-62 characters (bc1 + 39-59 = 42-62 total)
        legacy_p2pkh_pattern = r'^1[1-9A-HJ-NP-Za-km-z]{25,34}$'
        p2sh_pattern = r'^3[1-9A-HJ-NP-Za-km-z]{25,34}$'
        bech32_pattern = r'^bc1[02-9ac-hj-np-z]{39,59}$'

        if (re.match(legacy_p2pkh_pattern, wallet_address) or
            re.match(p2sh_pattern, wallet_address) or
            re.match(bech32_pattern, wallet_address)):
            return wallet_address

        raise ValueError(
            f"Invalid Bitcoin address format: {wallet_address}. "
            "Address must start with '1', '3', or 'bc1' and have valid length and characters."
        )

    def __repr__(self) -> str:
        return (
            f"CryptoPortfolio(id={self.id!r}, "
            f"name={self.name!r}, "
            f"currency={self.base_currency.value!r}, "
            f"active={self.is_active!r}, "
            f"wallet_address={self.wallet_address!r})"
        )


class CryptoTransaction(Base):
    """
    Crypto transaction model representing individual crypto transactions.

    Tracks buys, sells, and transfers for cryptocurrencies with high precision
    for quantities and prices typical of crypto assets.
    """
    __tablename__ = "crypto_transactions"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Foreign key to portfolio
    portfolio_id: Mapped[int] = mapped_column(
        ForeignKey("crypto_portfolios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated portfolio ID"
    )

    # Asset identification
    symbol: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Crypto symbol (e.g., BTC, ETH, ADA)"
    )

    # Transaction details
    transaction_type: Mapped[CryptoTransactionType] = mapped_column(
        SQLEnum(CryptoTransactionType, native_enum=False),
        nullable=False,
        comment="Type of transaction"
    )

    # Quantities and prices (high precision for crypto)
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8),
        nullable=False,
        comment="Quantity of crypto asset (positive for all types)"
    )
    price_at_execution: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8),
        nullable=False,
        comment="Price per unit at time of execution"
    )

    # Currency and amounts
    currency: Mapped[CryptoCurrency] = mapped_column(
        SQLEnum(CryptoCurrency, native_enum=False),
        nullable=False,
        comment="Currency used for the transaction"
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=2),
        nullable=False,
        comment="Total value of transaction (quantity * price)"
    )

    # Fees
    fee: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=8),
        nullable=False,
        default=0,
        comment="Transaction fee in crypto asset or base currency"
    )
    fee_currency: Mapped[str] = mapped_column(
        String(10),
        nullable=True,
        comment="Currency of the fee (if different from main transaction)"
    )

    # Transaction timing
    timestamp: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
        comment="When the transaction occurred"
    )

    # Additional details
    exchange: Mapped[str] = mapped_column(
        String(50),
        nullable=True,
        comment="Exchange or platform where transaction occurred"
    )
    transaction_hash: Mapped[str] = mapped_column(
        String(100),
        nullable=True,
        unique=True,
        index=True,
        comment="Blockchain transaction hash for on-chain transactions"
    )
    notes: Mapped[str] = mapped_column(
        String(1000),
        nullable=True,
        comment="Additional notes about the transaction"
    )

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="When the record was created"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="When the record was last updated"
    )

    # Relationships
    portfolio: Mapped["CryptoPortfolio"] = relationship(
        "CryptoPortfolio",
        back_populates="transactions"
    )

    # Composite indexes for common queries
    __table_args__ = (
        Index('ix_crypto_transactions_portfolio_date', 'portfolio_id', 'timestamp'),
        Index('ix_crypto_transactions_symbol_date', 'symbol', 'timestamp'),
        Index('ix_crypto_transactions_type_date', 'transaction_type', 'timestamp'),
    )

    def __repr__(self) -> str:
        return (
            f"CryptoTransaction(id={self.id!r}, "
            f"portfolio_id={self.portfolio_id!r}, "
            f"symbol={self.symbol!r}, "
            f"type={self.transaction_type.value!r}, "
            f"quantity={self.quantity!r}, "
            f"timestamp={self.timestamp!r})"
        )