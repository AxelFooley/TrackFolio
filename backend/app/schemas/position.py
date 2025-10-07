"""Position schemas."""
from pydantic import BaseModel, Field, field_validator, field_serializer
from datetime import datetime
from decimal import Decimal
from typing import Optional
import re

from app.models.position import AssetType
from app.schemas.transaction import ManualTransactionCreate


class PositionResponse(BaseModel):
    """Schema for position response."""
    id: int = Field(..., description="Position ID")
    ticker: str = Field(..., description="Asset ticker symbol")
    asset_type: AssetType = Field(..., description="Asset type: stock, etf, or crypto")
    isin: Optional[str] = Field(None, description="ISIN identifier (XC prefixed for crypto)")
    description: str = Field(..., description="Asset description")
    quantity: Decimal = Field(..., description="Current quantity held")
    average_cost: Decimal = Field(..., description="Average cost per unit including fees")
    cost_basis: Decimal = Field(..., description="Total cost basis (quantity × average_cost)")
    current_price: Optional[Decimal] = Field(None, description="Current market price")
    current_value: Optional[Decimal] = Field(None, description="Current market value (quantity × current_price)")
    unrealized_gain: Optional[Decimal] = Field(None, description="Unrealized gain/loss in EUR")
    return_percentage: Optional[float] = Field(None, description="Return percentage (unrealized_gain / cost_basis × 100)")
    irr: Optional[float] = Field(None, description="Internal Rate of Return (annualized)")
    today_change: Optional[Decimal] = Field(None, description="Today's price change in EUR")
    today_change_percent: Optional[float] = Field(None, description="Today's percentage change")
    last_calculated_at: datetime = Field(..., description="When position was last calculated")
    exchange: Optional[str] = Field(None, description="Crypto exchange (for crypto assets)")
    wallet_address: Optional[str] = Field(None, description="Wallet address (for crypto assets)")

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

        # Normalize input first: trim and uppercase
        v = v.strip().upper()
        asset_type = info.data.get('asset_type')

        if asset_type == AssetType.CRYPTO:
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

    @field_validator('quantity')
    @classmethod
    def validate_quantity_precision(cls, v, info):
        """Validate quantity precision based on asset type."""
        if v is None:
            return v

        asset_type = info.data.get('asset_type')
        ticker = info.data.get('ticker', '')

        # Check precision limits
        if asset_type == AssetType.CRYPTO or ManualTransactionCreate._is_crypto_ticker(ticker):
            # Crypto can have up to 18 decimal places
            if v.as_tuple().exponent < -18:
                raise ValueError("Crypto quantity precision too high (max 18 decimal places)")
        else:
            # Traditional assets typically don't need more than 8 decimal places
            if v.as_tuple().exponent < -8:
                raise ValueError("Traditional asset quantity precision too high (max 8 decimal places)")

        return v

    @field_validator('exchange')
    @classmethod
    def validate_exchange(cls, v, info):
        """Validate crypto exchange name."""
        if not v:
            return v

        asset_type = info.data.get('asset_type')

        if asset_type == AssetType.CRYPTO:
            v = v.upper().strip()
            if len(v) > 50:
                raise ValueError("Exchange name too long (max 50 characters)")

            # Allow alphanumeric, spaces, and common characters
            if not re.match(r'^[A-Z0-9\s\-\.\&]+$', v):
                raise ValueError("Exchange name contains invalid characters")

            return v

        # Exchange should only be set for crypto assets
        raise ValueError("Exchange should only be specified for crypto assets")

    @field_validator('wallet_address')
    @classmethod
    def validate_wallet_address(cls, v, info):
        """Validate crypto wallet address."""
        if not v:
            return v

        asset_type = info.data.get('asset_type')
        ticker = info.data.get('ticker', '')

        if asset_type == AssetType.CRYPTO or ManualTransactionCreate._is_crypto_ticker(ticker):
            v = v.strip()

            # Basic length validation (most addresses are between 26-90 characters)
            if len(v) < 26 or len(v) > 90:
                raise ValueError("Wallet address length invalid (expected 26-90 characters)")

            # Allow alphanumeric characters and common address symbols
            if not re.match(r'^[a-zA-Z0-9]+$', v):
                raise ValueError("Wallet address contains invalid characters")

            return v

        # Wallet address should only be set for crypto assets
        raise ValueError("Wallet address should only be specified for crypto assets")

    @field_serializer('asset_type')
    def serialize_asset_type(self, value: AssetType) -> str:
        """Serialize AssetType enum to string."""
        return value.value if isinstance(value, AssetType) else str(value)

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "ticker": "BTC",
                    "isin": "XC1A2B3C4D5E6",
                    "description": "Bitcoin",
                    "asset_type": "crypto",
                    "quantity": "0.025",
                    "average_cost": "38640.00",
                    "cost_basis": "966.00",
                    "current_price": "43000.00",
                    "current_value": "1075.00",
                    "unrealized_gain": "109.00",
                    "return_percentage": 11.28,
                    "irr": 15.5,
                    "today_change": "500.00",
                    "today_change_percent": 1.18,
                    "last_calculated_at": "2025-01-15T16:30:00Z",
                    "exchange": "COINBASE",
                    "wallet_address": "1A2b3C4d5E6f7G8h9I0jK1lM2n3O4p5Q6r"
                },
                {
                    "id": 2,
                    "ticker": "AAPL",
                    "isin": "US0378331005",
                    "description": "Apple Inc.",
                    "asset_type": "stock",
                    "quantity": "10",
                    "average_cost": "162.28",
                    "cost_basis": "1622.85",
                    "current_price": "178.50",
                    "current_value": "1785.00",
                    "unrealized_gain": "162.15",
                    "return_percentage": 10.0,
                    "irr": 12.3,
                    "today_change": "3.00",
                    "today_change_percent": 1.71,
                    "last_calculated_at": "2025-01-15T16:30:00Z"
                }
            ]
        }
    }


class PositionCreate(BaseModel):
    """Schema for creating a position (typically auto-generated)."""
    ticker: str = Field(..., min_length=1, max_length=20, description="Asset ticker symbol")
    asset_type: AssetType = Field(..., description="Asset type: stock, etf, or crypto")
    isin: str = Field(..., min_length=12, max_length=12, description="ISIN identifier")
    description: str = Field(..., min_length=1, description="Asset description")
    quantity: Decimal = Field(..., gt=0, description="Current quantity held")
    average_cost: Decimal = Field(..., gt=0, description="Average cost per unit including fees")
    cost_basis: Decimal = Field(..., gt=0, description="Total cost basis")
    exchange: Optional[str] = Field(None, description="Crypto exchange (for crypto assets)")
    wallet_address: Optional[str] = Field(None, description="Wallet address (for crypto assets)")

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
        """Validate ISIN format and ensure it is present."""
        if not v:
            raise ValueError("ISIN is required")

        # Normalize input first: trim and uppercase
        v = v.strip().upper()
        asset_type = info.data.get('asset_type')

        if asset_type == AssetType.CRYPTO:
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

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "ticker": "BTC",
                    "isin": "XC1A2B3C4D5E6",
                    "description": "Bitcoin",
                    "asset_type": "crypto",
                    "quantity": "0.025",
                    "average_cost": "38640.00",
                    "cost_basis": "966.00",
                    "exchange": "COINBASE",
                    "wallet_address": "1A2b3C4d5E6f7G8h9I0jK1lM2n3O4p5Q6r"
                },
                {
                    "ticker": "AAPL",
                    "isin": "US0378331005",
                    "description": "Apple Inc.",
                    "asset_type": "stock",
                    "quantity": "10",
                    "average_cost": "162.28",
                    "cost_basis": "1622.85"
                }
            ]
        }
    }


class PositionUpdate(BaseModel):
    """Schema for updating position fields."""
    quantity: Optional[Decimal] = Field(None, gt=0, description="Current quantity held")
    average_cost: Optional[Decimal] = Field(None, gt=0, description="Average cost per unit including fees")
    cost_basis: Optional[Decimal] = Field(None, gt=0, description="Total cost basis")
    exchange: Optional[str] = Field(None, description="Crypto exchange (for crypto assets)")
    wallet_address: Optional[str] = Field(None, description="Wallet address (for crypto assets)")

    @field_validator('quantity')
    @classmethod
    def validate_quantity_precision(cls, v):
        """Validate quantity precision with permissive 18-decimal limit."""
        if v is None:
            return v

        # Check precision limits (same as PositionResponse)
        if v.as_tuple().exponent < -18:
            raise ValueError("Quantity precision too high (max 18 decimal places)")

        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "quantity": "0.030",
                    "average_cost": "38500.00",
                    "cost_basis": "1155.00"
                },
                {
                    "quantity": "12",
                    "average_cost": "165.00",
                    "cost_basis": "1980.00"
                }
            ]
        }
    }
