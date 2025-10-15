"""Crypto portfolio schemas."""
from pydantic import BaseModel, Field, field_validator, ValidationInfo
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
from enum import Enum


class CryptoTransactionType(str, Enum):
    """Crypto transaction type enumeration."""
    BUY = "buy"
    SELL = "sell"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"


class CryptoCurrency(str, Enum):
    """Supported currencies for crypto transactions."""
    EUR = "EUR"
    USD = "USD"


# Portfolio Schemas
class CryptoPortfolioCreate(BaseModel):
    """Schema for creating a crypto portfolio."""
    name: str = Field(..., min_length=1, max_length=100, description="Portfolio name")
    description: Optional[str] = Field(None, max_length=500, description="Portfolio description")
    base_currency: CryptoCurrency = Field(CryptoCurrency.USD, description="Base currency")
    wallet_address: Optional[str] = Field(None, max_length=100, description="Bitcoin wallet address for paper wallet integration")


class CryptoPortfolioUpdate(BaseModel):
    """Schema for updating a crypto portfolio."""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Portfolio name")
    description: Optional[str] = Field(None, max_length=500, description="Portfolio description")
    is_active: Optional[bool] = Field(None, description="Whether the portfolio is active")
    base_currency: Optional[CryptoCurrency] = Field(None, description="Base currency")
    wallet_address: Optional[str] = Field(None, max_length=100, description="Bitcoin wallet address for paper wallet integration")


class CryptoPortfolioResponse(BaseModel):
    """Schema for crypto portfolio response."""
    id: int
    name: str
    description: Optional[str]
    is_active: bool
    base_currency: CryptoCurrency
    wallet_address: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # Optional computed fields (legacy)
    total_value: Optional[Decimal] = None
    total_cost_basis: Optional[Decimal] = None
    total_profit_loss: Optional[Decimal] = None
    total_profit_loss_pct: Optional[float] = None
    transaction_count: Optional[int] = None

    # Frontend-compatible fields
    total_value_usd: Optional[float] = None
    total_value_eur: Optional[float] = None
    total_profit_usd: Optional[float] = None
    total_profit_eur: Optional[float] = None
    profit_percentage_usd: Optional[float] = None
    profit_percentage_eur: Optional[float] = None

    # Wallet sync status
    wallet_sync_status: Optional[Dict[str, Any]] = None

    model_config = {"from_attributes": True}


class CryptoPortfolioList(BaseModel):
    """Schema for list of crypto portfolios."""
    portfolios: List[CryptoPortfolioResponse]
    total_count: int


# Transaction Schemas
class CryptoTransactionCreate(BaseModel):
    """Schema for creating a crypto transaction."""
    symbol: str = Field(..., min_length=1, max_length=20, description="Crypto symbol (e.g., BTC, ETH)")
    transaction_type: CryptoTransactionType
    quantity: Decimal = Field(..., gt=0, description="Quantity of crypto asset")
    price_at_execution: Decimal = Field(..., gt=0, description="Price per unit at execution")
    currency: CryptoCurrency = Field(..., description="Currency used for transaction")
    fee: Decimal = Field(0, ge=0, description="Transaction fee")
    fee_currency: Optional[str] = Field(None, max_length=10, description="Currency of the fee")
    timestamp: datetime = Field(..., description="When the transaction occurred")
    exchange: Optional[str] = Field(None, max_length=50, description="Exchange or platform")
    transaction_hash: Optional[str] = Field(None, max_length=100, description="Blockchain transaction hash")
    notes: Optional[str] = Field(None, max_length=1000, description="Additional notes")

    @field_validator('symbol')
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """
        Normalize a crypto symbol by trimming surrounding whitespace and converting to uppercase.
        
        Parameters:
            v (str): The input symbol to normalize.
        
        Returns:
            str: The normalized symbol (trimmed and uppercased).
        """
        return v.upper().strip()


class CryptoTransactionUpdate(BaseModel):
    """Schema for updating a crypto transaction."""
    transaction_type: Optional[CryptoTransactionType] = None
    quantity: Optional[Decimal] = Field(None, gt=0, description="Quantity of crypto asset")
    price_at_execution: Optional[Decimal] = Field(None, gt=0, description="Price per unit at execution")
    currency: Optional[CryptoCurrency] = None
    fee: Optional[Decimal] = Field(None, ge=0, description="Transaction fee")
    fee_currency: Optional[str] = Field(None, max_length=10, description="Currency of the fee")
    timestamp: Optional[datetime] = None
    exchange: Optional[str] = Field(None, max_length=50, description="Exchange or platform")
    transaction_hash: Optional[str] = Field(None, max_length=100, description="Blockchain transaction hash")
    notes: Optional[str] = Field(None, max_length=1000, description="Additional notes")


class CryptoTransactionResponse(BaseModel):
    """Schema for crypto transaction response."""
    id: int
    portfolio_id: int
    symbol: str
    transaction_type: CryptoTransactionType
    quantity: Decimal
    price_at_execution: Decimal
    currency: CryptoCurrency
    total_amount: Decimal
    fee: Decimal
    fee_currency: Optional[str]
    timestamp: datetime
    exchange: Optional[str]
    transaction_hash: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CryptoTransactionList(BaseModel):
    """Schema for list of crypto transactions."""
    items: List[CryptoTransactionResponse]
    total: int


# Holdings and Metrics Schemas
class CryptoHolding(BaseModel):
    """Schema for a crypto holding in a portfolio."""
    symbol: str
    quantity: Decimal
    average_cost: Decimal
    cost_basis: Decimal
    current_price: Optional[Decimal] = None
    current_value: Optional[Decimal] = None
    unrealized_gain_loss: Optional[Decimal] = None
    unrealized_gain_loss_pct: Optional[float] = None
    realized_gain_loss: Optional[Decimal] = None
    first_purchase_date: Optional[date] = None
    last_transaction_date: Optional[date] = None
    currency: str  # Currency of the holding values (matches portfolio base_currency)


class CryptoPortfolioMetrics(BaseModel):
    """Schema for crypto portfolio metrics."""
    portfolio_id: int
    base_currency: str

    # Value metrics
    total_value: Optional[Decimal] = None
    total_cost_basis: Decimal
    total_profit_loss: Optional[Decimal] = None
    total_profit_loss_pct: Optional[float] = None

    # Performance metrics
    unrealized_gain_loss: Optional[Decimal] = None
    realized_gain_loss: Decimal
    total_deposits: Decimal
    total_withdrawals: Decimal

    # IRR calculations
    internal_rate_of_return: Optional[float] = None
    time_weighted_return: Optional[float] = None

    # Holdings breakdown
    holdings_count: int
    transaction_count: int

    # Currency breakdown
    currency_breakdown: List[dict] = Field(default_factory=list)

    # Asset allocation (by value)
    asset_allocation: List[dict] = Field(default_factory=list)

class CryptoPriceData(BaseModel):
    """Schema for crypto price data."""
    symbol: str
    price: Decimal
    currency: str
    price_usd: Optional[Decimal] = None
    market_cap_usd: Optional[Decimal] = None
    volume_24h_usd: Optional[Decimal] = None
    change_percent_24h: Optional[Decimal] = None
    timestamp: datetime
    source: str


class CryptoHistoricalPrice(BaseModel):
    """Schema for historical crypto price data."""
    date: date
    symbol: str
    price: Decimal
    currency: str
    price_usd: Optional[Decimal] = None
    timestamp: datetime
    source: str


class CryptoPerformanceData(BaseModel):
    """Schema for crypto portfolio performance over time."""
    date: date
    portfolio_value: Decimal
    cost_basis: Decimal
    profit_loss: Decimal
    profit_loss_pct: float


class CryptoPortfolioPerformance(BaseModel):
    """Schema for crypto portfolio performance data."""
    portfolio_id: int
    performance_data: List[CryptoPerformanceData]

    # Summary metrics
    start_value: Optional[Decimal] = None
    end_value: Optional[Decimal] = None
    total_return: Optional[Decimal] = None
    total_return_pct: Optional[float] = None
    max_drawdown: Optional[Decimal] = None
    max_drawdown_pct: Optional[float] = None


# Price API Schemas
class CryptoPriceRequest(BaseModel):
    """Schema for crypto price request."""
    symbols: List[str] = Field(..., min_items=1, max_items=100, description="List of crypto symbols")
    currency: CryptoCurrency = Field(CryptoCurrency.USD, description="Target currency")


class CryptoPriceResponse(BaseModel):
    """Schema for crypto price response."""
    prices: List[CryptoPriceData]
    currency: str
    timestamp: datetime


class CryptoPriceHistoryRequest(BaseModel):
    """Schema for crypto price history request."""
    symbol: str = Field(..., min_length=1, max_length=20, description="Crypto symbol")
    start_date: date = Field(..., description="Start date for historical data")
    end_date: date = Field(..., description="End date for historical data")
    currency: CryptoCurrency = Field(CryptoCurrency.USD, description="Target currency")


class CryptoPriceHistoryResponse(BaseModel):
    """Schema for crypto price history response."""
    symbol: str
    currency: str
    prices: List[CryptoHistoricalPrice]
    total_count: int


# Error Response Schemas
class CryptoError(BaseModel):
    """Schema for crypto API error response."""
    error: str
    detail: Optional[str] = None
    timestamp: datetime


# Import/Export Schemas
class CryptoImportResult(BaseModel):
    """Schema for crypto transaction import result."""
    imported_count: int
    skipped_count: int
    error_count: int
    errors: List[str] = Field(default_factory=list)
    total_processed: int

class CryptoPortfolioSummary(BaseModel):
    """Schema for crypto portfolio summary."""
    portfolio: CryptoPortfolioResponse
    metrics: CryptoPortfolioMetrics
    holdings: List[CryptoHolding]
    recent_transactions: List[CryptoTransactionResponse]