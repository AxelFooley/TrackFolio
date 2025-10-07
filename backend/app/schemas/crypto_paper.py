"""
Crypto Paper Wallet schemas for request/response models.
"""
from pydantic import BaseModel, Field, validator
from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional
from enum import Enum


class CryptoTransactionType(str, Enum):
    """Crypto transaction type enumeration matching the database model."""
    BUY = "buy"
    SELL = "sell"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"


# Portfolio Schemas
class CryptoPaperPortfolioCreate(BaseModel):
    """Schema for creating a new crypto paper portfolio."""
    name: str = Field(..., min_length=1, max_length=100, description="Portfolio name")
    description: Optional[str] = Field(None, max_length=500, description="Optional portfolio description")


class CryptoPaperPortfolioUpdate(BaseModel):
    """Schema for updating a crypto paper portfolio."""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Portfolio name")
    description: Optional[str] = Field(None, max_length=500, description="Optional portfolio description")


class CryptoPaperMetrics(BaseModel):
    """Schema for portfolio metrics."""
    total_value: Decimal = Field(..., description="Total current value of portfolio")
    cost_basis: Decimal = Field(..., description="Total cost basis of all positions")
    unrealized_pl: Decimal = Field(..., description="Unrealized profit/loss")
    realized_pl: Decimal = Field(..., description="Realized profit/loss")
    total_pl: Decimal = Field(..., description="Total profit/loss (realized + unrealized)")
    irr: Optional[Decimal] = Field(None, description="Internal Rate of Return")
    total_invested: Decimal = Field(..., description="Total amount invested")
    quantity_change: Decimal = Field(..., description="Net quantity change (buys - sells)")

    class Config:
        from_attributes = True


class CryptoPaperPortfolioResponse(BaseModel):
    """Schema for portfolio response with metrics."""
    id: int
    name: str
    description: Optional[str]
    user_id: int
    created_at: datetime
    updated_at: datetime
    metrics: Optional[CryptoPaperMetrics] = Field(None, description="Portfolio metrics")

    class Config:
        from_attributes = True


class CryptoPaperPortfolioList(BaseModel):
    """Schema for list of portfolios with basic metrics."""
    portfolios: List[CryptoPaperPortfolioResponse]
    total_count: int


# Transaction Schemas
class CryptoPaperTransactionCreate(BaseModel):
    """Schema for creating a new crypto transaction."""
    symbol: str = Field(..., min_length=1, max_length=20, description="Crypto symbol like BTC, ETH")
    transaction_type: CryptoTransactionType = Field(..., description="Type of transaction")
    quantity: Decimal = Field(..., gt=0, description="Quantity of crypto asset")
    price_at_execution: Decimal = Field(..., gt=0, description="Price per unit at execution")
    currency: str = Field(default="USD", pattern="^(USD|EUR)$", description="Currency code")
    fee: Decimal = Field(default=Decimal("0"), ge=0, description="Transaction fee")
    timestamp: datetime = Field(..., description="When the transaction occurred")

    @validator('symbol')
    def validate_symbol(cls, v):
        """Validate crypto symbol format."""
        if not v or len(v.strip()) == 0:
            raise ValueError('Symbol cannot be empty')
        return v.upper().strip()

    @validator('quantity')
    def validate_quantity(cls, v):
        """Validate quantity is positive."""
        if v <= 0:
            raise ValueError('Quantity must be greater than 0')
        return v

    @validator('price_at_execution')
    def validate_price(cls, v):
        """Validate price is positive."""
        if v <= 0:
            raise ValueError('Price must be greater than 0')
        return v


class CryptoPaperTransactionUpdate(BaseModel):
    """Schema for updating a crypto transaction."""
    symbol: Optional[str] = Field(None, min_length=1, max_length=20, description="Crypto symbol like BTC, ETH")
    transaction_type: Optional[CryptoTransactionType] = Field(None, description="Type of transaction")
    quantity: Optional[Decimal] = Field(None, gt=0, description="Quantity of crypto asset")
    price_at_execution: Optional[Decimal] = Field(None, gt=0, description="Price per unit at execution")
    currency: Optional[str] = Field(None, pattern="^(USD|EUR)$", description="Currency code")
    fee: Optional[Decimal] = Field(None, ge=0, description="Transaction fee")
    timestamp: Optional[datetime] = Field(None, description="When the transaction occurred")

    @validator('symbol')
    def validate_symbol(cls, v):
        """Validate crypto symbol format."""
        if v is not None:
            if not v or len(v.strip()) == 0:
                raise ValueError('Symbol cannot be empty')
            return v.upper().strip()
        return v

    @validator('quantity')
    def validate_quantity(cls, v):
        """Validate quantity is positive."""
        if v is not None and v <= 0:
            raise ValueError('Quantity must be greater than 0')
        return v

    @validator('price_at_execution')
    def validate_price(cls, v):
        """Validate price is positive."""
        if v is not None and v <= 0:
            raise ValueError('Price must be greater than 0')
        return v


class CryptoPaperTransactionResponse(BaseModel):
    """Schema for transaction response."""
    id: int
    portfolio_id: int
    symbol: str
    coingecko_id: Optional[str]
    transaction_type: str
    quantity: Decimal
    price_at_execution: Decimal
    currency: str
    fee: Decimal
    timestamp: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CryptoPaperTransactionList(BaseModel):
    """Schema for paginated list of transactions."""
    transactions: List[CryptoPaperTransactionResponse]
    total_count: int
    page: int
    page_size: int
    total_pages: int


# Holdings and Analytics Schemas
class CryptoPaperHolding(BaseModel):
    """Schema for current position in a crypto asset."""
    symbol: str
    quantity: Decimal
    average_cost: Decimal
    current_price: Decimal
    current_value: Decimal
    total_cost: Decimal
    unrealized_pl: Decimal
    unrealized_pl_percent: Decimal
    currency: str
    last_updated: datetime

    class Config:
        from_attributes = True


class CryptoPaperHistoryPoint(BaseModel):
    """Schema for historical portfolio value point."""
    date: date
    total_value: Decimal
    cost_basis: Decimal
    total_pl: Decimal

    class Config:
        from_attributes = True


class CryptoPaperHistory(BaseModel):
    """Schema for historical portfolio value data."""
    history: List[CryptoPaperHistoryPoint]
    start_date: date
    end_date: date
    total_points: int


# Price Schemas
class CryptoPriceResponse(BaseModel):
    """Schema for current crypto price response."""
    symbol: str
    coingecko_id: Optional[str]
    current_price: Decimal
    currency: str
    market_cap: Optional[Decimal] = None
    volume_24h: Optional[Decimal] = None
    change_24h: Optional[Decimal] = None
    change_24h_percent: Optional[Decimal] = None
    last_updated: datetime


class CryptoPriceHistoryResponse(BaseModel):
    """Schema for crypto price history response."""
    symbol: str
    currency: str
    history: List[CryptoPaperHistoryPoint]
    total_points: int


# Summary Schemas
class CryptoPaperSummary(BaseModel):
    """Schema for portfolio summary with holdings count."""
    id: int
    name: str
    description: Optional[str]
    total_value: Decimal
    total_pl: Decimal
    total_pl_percent: Decimal
    holdings_count: int
    last_updated: datetime

    class Config:
        from_attributes = True


class CryptoPaperDashboard(BaseModel):
    """Schema for dashboard view with multiple portfolios."""
    portfolios: List[CryptoPaperSummary]
    total_value_all: Decimal
    total_pl_all: Decimal
    last_updated: datetime


# Performance Schemas
class CryptoPerformanceDataPoint(BaseModel):
    """Schema for performance data point."""
    date: str
    value_usd: Decimal


class CryptoPortfolioPerformance(BaseModel):
    """Schema for portfolio performance data."""
    portfolio_data: List[CryptoPerformanceDataPoint]
    start_value: Decimal
    end_value: Decimal
    change_amount: Decimal
    change_pct: Decimal