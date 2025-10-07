"""
Crypto Paper Wallet models - Stores crypto portfolio transactions and wallet connections.
"""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Numeric, DateTime, Enum as SQLEnum, Index, ForeignKey, Boolean, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.database import Base


class CryptoTransactionType(str, enum.Enum):
    """Crypto transaction type enumeration."""
    BUY = "buy"
    SELL = "sell"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"


class WalletConnectionType(str, enum.Enum):
    """Wallet connection type enumeration."""
    ADDRESS_ONLY = "address_only"
    SEED_PHRASE = "seed_phrase"
    HARDWARE_WALLET = "hardware_wallet"
    SOFTWARE_WALLET = "software_wallet"
    EXCHANGE_API = "exchange_api"


class BlockchainNetwork(str, enum.Enum):
    """Blockchain network enumeration."""
    BITCOIN = "bitcoin"
    ETHEREUM = "ethereum"
    POLYGON = "polygon"
    BSC = "bsc"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"


class WalletConnectionStatus(str, enum.Enum):
    """Wallet connection status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    SYNCING = "syncing"
    DISABLED = "disabled"


class SyncStatus(str, enum.Enum):
    """Sync status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


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

    # Relationships
    wallet_connections: Mapped[list["WalletConnection"]] = relationship(
        "WalletConnection",
        back_populates="portfolio",
        cascade="all, delete-orphan"
    )
    transactions: Mapped[list["CryptoPaperTransaction"]] = relationship(
        "CryptoPaperTransaction",
        back_populates="portfolio",
        cascade="all, delete-orphan"
    )

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

    # Relationships
    portfolio: Mapped["CryptoPaperPortfolio"] = relationship(
        "CryptoPaperPortfolio",
        back_populates="transactions"
    )

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


class WalletConnection(Base):
    """
    Wallet Connection model representing connections to crypto wallets.

    Stores connection details and metadata for different types of wallet connections.
    """
    __tablename__ = "wallet_connections"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Foreign key to portfolio
    portfolio_id: Mapped[int] = mapped_column(
        ForeignKey("crypto_paper_portfolios.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Connection details
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="User-defined name for this wallet connection"
    )
    connection_type: Mapped[WalletConnectionType] = mapped_column(
        SQLEnum(WalletConnectionType, native_enum=False),
        nullable=False,
        index=True,
        comment="Type of wallet connection"
    )
    status: Mapped[WalletConnectionStatus] = mapped_column(
        SQLEnum(WalletConnectionStatus, native_enum=False),
        nullable=False,
        default=WalletConnectionStatus.ACTIVE,
        index=True,
        comment="Current status of the wallet connection"
    )

    # Connection metadata
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=True,
        comment="Wallet provider (e.g., MetaMask, Ledger, Trezor, etc.)"
    )
    network: Mapped[BlockchainNetwork] = mapped_column(
        SQLEnum(BlockchainNetwork, native_enum=False),
        nullable=False,
        index=True,
        comment="Blockchain network this wallet operates on"
    )

    # Security fields (for future encryption implementation)
    encrypted_credentials: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="Encrypted connection credentials (future implementation)"
    )
    public_key: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Public key or identifier for the wallet"
    )
    address_validation_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
        comment="Hash for validating wallet addresses"
    )

    # Configuration
    auto_sync_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether to automatically sync transactions from this wallet"
    )
    sync_frequency_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=60,
        comment="Frequency in minutes for automatic syncing"
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
    last_sync_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=True,
        comment="Timestamp of the last successful sync"
    )

    # Relationships
    portfolio: Mapped["CryptoPaperPortfolio"] = relationship(
        "CryptoPaperPortfolio",
        back_populates="wallet_connections"
    )
    addresses: Mapped[list["WalletAddress"]] = relationship(
        "WalletAddress",
        back_populates="wallet_connection",
        cascade="all, delete-orphan"
    )
    sync_statuses: Mapped[list["WalletSyncStatus"]] = relationship(
        "WalletSyncStatus",
        back_populates="wallet_connection",
        cascade="all, delete-orphan"
    )

    # Composite indexes
    __table_args__ = (
        Index('ix_wallet_connections_portfolio_type', 'portfolio_id', 'connection_type'),
        Index('ix_wallet_connections_network_status', 'network', 'status'),
        Index('ix_wallet_connections_provider_type', 'provider', 'connection_type'),
    )

    def __repr__(self) -> str:
        return (
            f"WalletConnection(id={self.id!r}, "
            f"portfolio_id={self.portfolio_id!r}, "
            f"name={self.name!r}, "
            f"type={self.connection_type.value!r}, "
            f"network={self.network.value!r}, "
            f"status={self.status.value!r})"
        )


class WalletAddress(Base):
    """
    Wallet Address model representing individual addresses being monitored.

    Stores addresses and their metadata for transaction monitoring.
    """
    __tablename__ = "wallet_addresses"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Foreign key to wallet connection
    wallet_connection_id: Mapped[int] = mapped_column(
        ForeignKey("wallet_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Address details
    address: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Blockchain address being monitored"
    )
    address_label: Mapped[str] = mapped_column(
        String(100),
        nullable=True,
        comment="User-defined label for this address"
    )
    network: Mapped[BlockchainNetwork] = mapped_column(
        SQLEnum(BlockchainNetwork, native_enum=False),
        nullable=False,
        index=True,
        comment="Blockchain network for this address"
    )

    # Validation and metadata
    is_valid: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether the address format is valid"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether this address is actively monitored"
    )
    balance_satoshi: Mapped[int] = mapped_column(
        Integer,
        nullable=True,
        default=0,
        comment="Current balance in satoshi/wei (when available)"
    )
    last_transaction_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
        comment="Hash of the last processed transaction"
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
    last_sync_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=True,
        comment="Timestamp of the last successful sync for this address"
    )

    # Relationships
    wallet_connection: Mapped["WalletConnection"] = relationship(
        "WalletConnection",
        back_populates="addresses"
    )

    # Composite indexes
    __table_args__ = (
        Index('ix_wallet_addresses_connection_address', 'wallet_connection_id', 'address'),
        Index('ix_wallet_addresses_network_active', 'network', 'is_active'),
        Index('ix_wallet_addresses_address_valid', 'address', 'is_valid'),
    )

    def __repr__(self) -> str:
        return (
            f"WalletAddress(id={self.id!r}, "
            f"wallet_connection_id={self.wallet_connection_id!r}, "
            f"address={self.address[:10]}...{self.address[-8:]!r}, "
            f"network={self.network.value!r}, "
            f"is_active={self.is_active!r})"
        )


class WalletSyncStatus(Base):
    """
    Wallet Sync Status model for tracking synchronization operations.

    Stores history and status of wallet synchronization attempts.
    """
    __tablename__ = "wallet_sync_statuses"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Foreign key to wallet connection
    wallet_connection_id: Mapped[int] = mapped_column(
        ForeignKey("wallet_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Sync operation details
    sync_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of sync operation (full, incremental, balance, etc.)"
    )
    status: Mapped[SyncStatus] = mapped_column(
        SQLEnum(SyncStatus, native_enum=False),
        nullable=False,
        default=SyncStatus.PENDING,
        index=True,
        comment="Current status of the sync operation"
    )

    # Results and statistics
    transactions_found: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of transactions found during sync"
    )
    transactions_processed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of transactions successfully processed"
    )
    new_transactions: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of new transactions added to portfolio"
    )

    # Error handling
    error_message: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if sync failed"
    )
    error_details: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed error information for debugging"
    )

    # Timing information
    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="When the sync operation started"
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=True,
        comment="When the sync operation completed (if successful)"
    )
    duration_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=True,
        comment="Total duration of the sync operation in seconds"
    )

    # Metadata
    sync_metadata: Mapped[str] = mapped_column(
        Text,
        nullable=True,
        comment="JSON metadata about the sync operation"
    )
    triggered_by: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="system",
        comment="What triggered this sync (system, user, scheduled, etc.)"
    )

    # Relationships
    wallet_connection: Mapped["WalletConnection"] = relationship(
        "WalletConnection",
        back_populates="sync_statuses"
    )

    # Composite indexes
    __table_args__ = (
        Index('ix_wallet_sync_statuses_connection_status', 'wallet_connection_id', 'status'),
        Index('ix_wallet_sync_statuses_type_started', 'sync_type', 'started_at'),
        Index('ix_wallet_sync_statuses_started_desc', 'started_at'),
    )

    def __repr__(self) -> str:
        return (
            f"WalletSyncStatus(id={self.id!r}, "
            f"wallet_connection_id={self.wallet_connection_id!r}, "
            f"sync_type={self.sync_type!r}, "
            f"status={self.status.value!r}, "
            f"transactions_processed={self.transactions_processed!r})"
        )