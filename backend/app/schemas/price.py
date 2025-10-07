"""Price schemas."""
from pydantic import BaseModel, Field, field_serializer, field_validator
from datetime import date as date_type, datetime
from decimal import Decimal
from typing import Optional, List
import re

from app.models.position import AssetType
from app.schemas.transaction import ManualTransactionCreate


class PriceResponse(BaseModel):
    """Schema for price data response."""
    ticker: str = Field(..., description="Asset ticker symbol")
    date: date_type = Field(..., description="Price date")
    open: Decimal = Field(..., gt=0, description="Opening price")
    high: Decimal = Field(..., gt=0, description="Highest price")
    low: Decimal = Field(..., gt=0, description="Lowest price")
    close: Decimal = Field(..., gt=0, description="Closing price")
    volume: int = Field(..., ge=0, description="Trading volume")
    source: str = Field(..., description="Price source (e.g., YAHOO, COINGECKO)")
    created_at: datetime = Field(..., description="When price was recorded")
    market_cap: Optional[Decimal] = Field(None, description="Market capitalization (for crypto)")
    circulating_supply: Optional[Decimal] = Field(None, description="Circulating supply (for crypto)")

    @field_validator('ticker')
    @classmethod
    def validate_ticker(cls, v):
        """Validate ticker format for both traditional assets and crypto."""
        if not v:
            raise ValueError("Ticker is required")

        v = v.upper().strip()

        # Check if it's a crypto ticker
        is_crypto = ManualTransactionCreate._is_crypto_ticker(v)

        if is_crypto:
            # Crypto ticker validation
            if len(v) > 20:
                raise ValueError("Crypto ticker too long (max 20 characters)")

            if not re.match(r'^[A-Z0-9\-\/]+$', v):
                raise ValueError("Crypto ticker contains invalid characters")

            return v

        # Traditional asset validation
        if len(v) > 10:
            raise ValueError("Traditional asset ticker too long (max 10 characters)")

        if not re.match(r'^[A-Z0-9\.]+$', v):
            raise ValueError("Ticker contains invalid characters")

        return v

    @field_validator('source')
    @classmethod
    def validate_source(cls, v):
        """Validate price source."""
        if not v:
            raise ValueError("Price source is required")

        v = v.upper().strip()
        valid_sources = {
            'YAHOO', 'COINGECKO', 'BINANCE', 'COINBASE', 'KRAKEN',
            'ALPHA_VANTAGE', 'IEX_CLOUD', 'MANUAL'
        }

        if v not in valid_sources:
            raise ValueError(f"Invalid price source: {v}")

        return v

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "ticker": "BTC",
                    "date": "2025-01-15",
                    "open": "42000.00",
                    "high": "43500.00",
                    "low": "41500.00",
                    "close": "43000.00",
                    "volume": 1234567890,
                    "source": "COINGECKO",
                    "created_at": "2025-01-15T18:00:00Z",
                    "market_cap": "840000000000",
                    "circulating_supply": "19500000"
                },
                {
                    "ticker": "AAPL",
                    "date": "2025-01-15",
                    "open": "175.00",
                    "high": "179.50",
                    "low": "174.20",
                    "close": "178.50",
                    "volume": 52341000,
                    "source": "YAHOO",
                    "created_at": "2025-01-15T18:00:00Z"
                }
            ]
        }
    }


class RealtimePriceResponse(BaseModel):
    """Schema for real-time price data response."""
    ticker: str = Field(..., description="Asset ticker symbol")
    isin: Optional[str] = Field(None, description="ISIN code if available (XC prefixed for crypto)")
    current_price: Decimal = Field(..., gt=0, description="Current market price")
    previous_close: Decimal = Field(..., gt=0, description="Previous day closing price")
    change_amount: Decimal = Field(..., description="Absolute price change from previous close")
    change_percent: Decimal = Field(..., description="Percentage price change from previous close")
    timestamp: datetime = Field(..., description="Time when price was fetched")
    source: str = Field(..., description="Price source")
    asset_type: Optional[AssetType] = Field(None, description="Asset type")
    volume_24h: Optional[Decimal] = Field(None, description="24-hour trading volume (crypto)")
    market_cap: Optional[Decimal] = Field(None, description="Market capitalization (crypto)")
    circulating_supply: Optional[Decimal] = Field(None, description="Circulating supply (crypto)")

    @field_validator('ticker')
    @classmethod
    def validate_ticker(cls, v):
        """Validate ticker format for both traditional assets and crypto."""
        if not v:
            raise ValueError("Ticker is required")

        v = v.upper().strip()

        # Check if it's a crypto ticker
        is_crypto = ManualTransactionCreate._is_crypto_ticker(v)

        if is_crypto:
            # Crypto ticker validation
            if len(v) > 20:
                raise ValueError("Crypto ticker too long (max 20 characters)")

            if not re.match(r'^[A-Z0-9\-\/]+$', v):
                raise ValueError("Crypto ticker contains invalid characters")

            return v

        # Traditional asset validation
        if len(v) > 10:
            raise ValueError("Traditional asset ticker too long (max 10 characters)")

        if not re.match(r'^[A-Z0-9\.]+$', v):
            raise ValueError("Ticker contains invalid characters")

        return v

    @field_validator('isin')
    @classmethod
    def validate_isin(cls, v, info):
        """Validate ISIN format based on asset type."""
        if not v:
            return v

        # Normalize input to uppercase at the start
        v = v.upper()
        ticker = info.data.get('ticker', '')

        if ManualTransactionCreate._is_crypto_ticker(ticker):
            # Crypto ISIN should start with "XC"
            if not v.startswith('XC'):
                raise ValueError("Crypto ISIN must start with 'XC'")

            if len(v) != 12:
                raise ValueError("Crypto ISIN must be 12 characters")

            if not re.match(r'^XC[A-Z0-9]{10}$', v):
                raise ValueError("Invalid crypto ISIN format")

            return v
        else:
            # Traditional ISIN validation
            if len(v) != 12:
                raise ValueError("ISIN must be 12 characters")

            if not re.match(r'^[A-Z]{2}[A-Z0-9]{9}[0-9]$', v):
                raise ValueError("Invalid ISIN format")

            return v

    @field_validator('source')
    @classmethod
    def validate_source(cls, v):
        """Validate price source."""
        if not v:
            raise ValueError("Price source is required")

        v = v.upper().strip()
        valid_sources = {
            'YAHOO', 'COINGECKO', 'BINANCE', 'COINBASE', 'KRAKEN',
            'ALPHA_VANTAGE', 'IEX_CLOUD', 'MANUAL'
        }

        if v not in valid_sources:
            raise ValueError(f"Invalid price source: {v}")

        return v

    @field_serializer('current_price', 'previous_close', 'change_amount', 'change_percent', 'volume_24h', 'market_cap', 'circulating_supply')
    def serialize_decimal(self, value: Decimal) -> float:
        """Convert Decimal to float for JSON serialization."""
        return float(value) if value is not None else None

    @field_serializer('asset_type')
    def serialize_asset_type(self, value: AssetType) -> str:
        """Serialize AssetType enum to string."""
        return value.value if isinstance(value, AssetType) else str(value)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "ticker": "BTC",
                    "isin": "XC1A2B3C4D5E6",
                    "current_price": "43000.00",
                    "previous_close": "42000.00",
                    "change_amount": "1000.00",
                    "change_percent": "2.38",
                    "timestamp": "2025-01-15T14:30:00Z",
                    "source": "COINGECKO",
                    "asset_type": "crypto",
                    "volume_24h": "25000000000",
                    "market_cap": "840000000000",
                    "circulating_supply": "19500000"
                },
                {
                    "ticker": "AAPL",
                    "isin": "US0378331005",
                    "current_price": "175.43",
                    "previous_close": "174.50",
                    "change_amount": "0.93",
                    "change_percent": "0.53",
                    "timestamp": "2025-01-15T14:30:00Z",
                    "source": "YAHOO",
                    "asset_type": "stock"
                }
            ]
        }
    }


class RealtimePricesResponse(BaseModel):
    """Schema for batch real-time prices response."""
    prices: List[RealtimePriceResponse] = Field(..., description="List of real-time prices")
    fetched_count: int = Field(..., ge=0, description="Number of prices successfully fetched")
    total_count: int = Field(..., ge=0, description="Total number of positions requested")
    timestamp: datetime = Field(..., description="Time when batch fetch was initiated")
    crypto_count: int = Field(default=0, ge=0, description="Number of crypto assets fetched")
    stock_count: int = Field(default=0, ge=0, description="Number of stock/ETF assets fetched")
    errors: List[str] = Field(default_factory=list, description="List of errors encountered during fetch")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "prices": [
                        {
                            "ticker": "BTC",
                            "isin": "XC1A2B3C4D5E6",
                            "current_price": "43000.00",
                            "previous_close": "42000.00",
                            "change_amount": "1000.00",
                            "change_percent": "2.38",
                            "timestamp": "2025-01-15T14:30:00Z",
                            "source": "COINGECKO",
                            "asset_type": "crypto",
                            "volume_24h": "25000000000",
                            "market_cap": "840000000000",
                            "circulating_supply": "19500000"
                        },
                        {
                            "ticker": "ETH",
                            "isin": "XC7H8I9J0K1L2",
                            "current_price": "2500.00",
                            "previous_close": "2450.00",
                            "change_amount": "50.00",
                            "change_percent": "2.04",
                            "timestamp": "2025-01-15T14:30:00Z",
                            "source": "COINGECKO",
                            "asset_type": "crypto",
                            "volume_24h": "15000000000",
                            "market_cap": "300000000000",
                            "circulating_supply": "120000000"
                        },
                        {
                            "ticker": "AAPL",
                            "isin": "US0378331005",
                            "current_price": "175.43",
                            "previous_close": "174.50",
                            "change_amount": "0.93",
                            "change_percent": "0.53",
                            "timestamp": "2025-01-15T14:30:00Z",
                            "source": "YAHOO",
                            "asset_type": "stock"
                        }
                    ],
                    "fetched_count": 3,
                    "total_count": 3,
                    "timestamp": "2025-01-15T14:30:00Z",
                    "crypto_count": 2,
                    "stock_count": 1,
                    "errors": []
                },
                {
                    "prices": [
                        {
                            "ticker": "AAPL",
                            "isin": "US0378331005",
                            "current_price": "175.43",
                            "previous_close": "174.50",
                            "change_amount": "0.93",
                            "change_percent": "0.53",
                            "timestamp": "2025-01-15T14:30:00Z",
                            "source": "YAHOO",
                            "asset_type": "stock"
                        }
                    ],
                    "fetched_count": 1,
                    "total_count": 2,
                    "timestamp": "2025-01-15T14:30:00Z",
                    "crypto_count": 0,
                    "stock_count": 1,
                    "errors": ["Failed to fetch price for BTC: API rate limit exceeded"]
                }
            ]
        }
    }


class PriceUpdateRequest(BaseModel):
    """Schema for manual price update requests."""
    tickers: List[str] = Field(..., min_items=1, description="List of ticker symbols to update")
    force_refresh: bool = Field(default=False, description="Force refresh even if recently updated")

    @field_validator('tickers')
    @classmethod
    def validate_tickers(cls, v):
        """Validate all ticker symbols."""
        validated_tickers = []
        for ticker in v:
            if not ticker:
                raise ValueError("Ticker cannot be empty")

            ticker = ticker.upper().strip()

            # Check if it's a crypto ticker
            is_crypto = ManualTransactionCreate._is_crypto_ticker(ticker)

            if is_crypto:
                # Crypto ticker validation
                if len(ticker) > 20:
                    raise ValueError(f"Crypto ticker {ticker} too long (max 20 characters)")

                if not re.match(r'^[A-Z0-9\-\/]+$', ticker):
                    raise ValueError(f"Crypto ticker {ticker} contains invalid characters")

                validated_tickers.append(ticker)
            else:
                # Traditional asset validation
                if len(ticker) > 10:
                    raise ValueError(f"Traditional asset ticker {ticker} too long (max 10 characters)")

                if not re.match(r'^[A-Z0-9\.]+$', ticker):
                    raise ValueError(f"Ticker {ticker} contains invalid characters")

                validated_tickers.append(ticker)

        return validated_tickers

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "tickers": ["BTC", "ETH", "AAPL", "GOOGL"],
                    "force_refresh": False
                },
                {
                    "tickers": ["BTC-USD", "ETH-USD"],
                    "force_refresh": True
                }
            ]
        }
    }


class PriceUpdateResponse(BaseModel):
    """Schema for price update response."""
    success_count: int = Field(..., ge=0, description="Number of prices successfully updated")
    failed_count: int = Field(..., ge=0, description="Number of prices that failed to update")
    total_requested: int = Field(..., ge=0, description="Total number of prices requested")
    crypto_updated: int = Field(default=0, ge=0, description="Number of crypto prices updated")
    stocks_updated: int = Field(default=0, ge=0, description="Number of stock/ETF prices updated")
    errors: List[str] = Field(default_factory=list, description="List of errors encountered")
    timestamp: datetime = Field(..., description="Time when update was completed")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success_count": 3,
                    "failed_count": 1,
                    "total_requested": 4,
                    "crypto_updated": 2,
                    "stocks_updated": 1,
                    "errors": ["Failed to update DOGE: API rate limit exceeded"],
                    "timestamp": "2025-01-15T14:35:00Z"
                }
            ]
        }
    }
