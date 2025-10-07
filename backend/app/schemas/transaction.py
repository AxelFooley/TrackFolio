"""Transaction schemas."""
from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
import re
import hashlib

from app.models.position import AssetType


def validate_crypto_ticker(ticker: str) -> str:
    """
    Validate and normalize cryptocurrency ticker.

    Args:
        ticker: Raw ticker symbol

    Returns:
        Normalized ticker symbol

    Raises:
        ValueError: If ticker format is invalid
    """
    if not ticker:
        raise ValueError("Ticker is required")

    ticker = ticker.upper().strip()

    # Length validation
    if len(ticker) > 20:
        raise ValueError("Crypto ticker too long (max 20 characters)")

    # Check for invalid characters
    if not re.match(r'^[A-Z0-9\-\/]+$', ticker):
        raise ValueError("Ticker contains invalid characters")

    return ticker


def validate_crypto_isin(isin: str) -> str:
    """
    Validate crypto ISIN-like identifier (XC prefixed).

    Args:
        isin: ISIN identifier

    Returns:
        Validated ISIN

    Raises:
        ValueError: If ISIN format is invalid for crypto
    """
    if not isin:
        return isin  # Optional field

    isin = isin.upper().strip()

    # Crypto ISINs should start with "XC"
    if isin.startswith('XC'):
        if len(isin) != 12:
            raise ValueError("Crypto ISIN must be 12 characters")
        if not re.match(r'^XC[A-Z0-9]{10}$', isin):
            raise ValueError("Invalid crypto ISIN format")
    else:
        # Regular ISIN validation for stocks/ETFs
        if len(isin) != 12:
            raise ValueError("ISIN must be 12 characters")
        if not re.match(r'^[A-Z]{2}[A-Z0-9]{9}[0-9]$', isin):
            raise ValueError("Invalid ISIN format")

    return isin


def validate_crypto_quantity(quantity: Decimal) -> Decimal:
    """
    Validate cryptocurrency quantity with proper precision.

    Args:
        quantity: Transaction quantity

    Returns:
        Validated quantity

    Raises:
        ValueError: If quantity precision is invalid
    """
    if quantity <= 0:
        raise ValueError("Quantity must be greater than 0")

    # Check for excessive decimal places (more than 18)
    if quantity.as_tuple().exponent < -18:
        raise ValueError("Crypto quantity precision too high (max 18 decimal places)")

    return quantity


class ManualTransactionCreate(BaseModel):
    """Schema for creating a transaction manually via the frontend."""
    operation_date: date
    ticker: str = Field(..., min_length=1, max_length=20, description="Asset ticker symbol")
    type: str = Field(..., pattern="^(buy|sell)$", description="Transaction type: buy or sell")
    quantity: Decimal = Field(..., gt=0, description="Number of shares or crypto units")
    amount: Decimal = Field(..., gt=0, description="Price per share/unit in currency")
    currency: str = Field(default="EUR", description="Transaction currency")
    fees: Decimal = Field(default=Decimal("0"), ge=0, description="Transaction fees")
    asset_type: Optional[AssetType] = Field(None, description="Asset type (auto-detected if not provided)")
    isin: Optional[str] = Field(None, description="ISIN identifier (generated for crypto if not provided)")

    @field_validator('ticker')
    @classmethod
    def validate_ticker(cls, v):
        """Validate ticker format for both traditional assets and crypto."""
        if not v:
            raise ValueError("Ticker is required")

        v = v.upper().strip()

        # Check if it's a crypto ticker
        is_crypto = cls._is_crypto_ticker(v)

        if is_crypto:
            return validate_crypto_ticker(v)

        # Traditional asset validation
        if len(v) > 10:
            raise ValueError("Traditional asset ticker too long (max 10 characters)")

        if not re.match(r'^[A-Z0-9\.]+$', v):
            raise ValueError("Ticker contains invalid characters")

        return v

    @field_validator('currency')
    @classmethod
    def validate_currency(cls, v):
        """Validate currency code."""
        if not v:
            raise ValueError("Currency is required")

        v = v.upper().strip()
        if not re.match(r'^[A-Z]{3}$', v):
            raise ValueError("Currency must be a valid 3-letter code")

        # Support common crypto currencies
        supported_currencies = {
            'EUR', 'USD', 'GBP', 'CHF', 'JPY',  # Traditional
            'BTC', 'ETH', 'USDT', 'USDC', 'BNB'  # Crypto
        }

        if v not in supported_currencies:
            raise ValueError(f"Currency {v} not supported")

        return v

    @field_validator('quantity')
    @classmethod
    def validate_quantity_precision(cls, v, info):
        """Validate quantity precision based on asset type."""
        ticker = info.data.get('ticker', '')

        if cls._is_crypto_ticker(ticker):
            return validate_crypto_quantity(v)

        # Traditional assets typically don't need more than 4 decimal places
        if v.as_tuple().exponent < -6:
            raise ValueError("Traditional asset quantity precision too high (max 6 decimal places)")

        return v

    @field_validator('isin')
    @classmethod
    def validate_isin_format(cls, v, info):
        """Validate ISIN format."""
        if not v:
            return v

        ticker = info.data.get('ticker', '')

        if cls._is_crypto_ticker(ticker):
            # For crypto, validate crypto ISIN format
            return validate_crypto_isin(v)

        # Traditional ISIN validation
        return validate_crypto_isin(v)

    @model_validator(mode='after')
    def validate_crypto_transaction(self):
        """Additional validation for crypto transactions."""
        ticker = self.ticker.upper().strip()

        if self._is_crypto_ticker(ticker):
            # Auto-generate crypto ISIN if not provided
            if not self.isin:
                self.isin = self._generate_crypto_isin(ticker)

            # Ensure crypto transactions use appropriate precision
            if self.quantity.as_tuple().exponent < -18:
                raise ValueError("Crypto quantity precision too high (max 18 decimal places)")

        return self

    @staticmethod
    def _is_crypto_ticker(ticker: str) -> bool:
        """Check if ticker represents a cryptocurrency."""
        if not ticker:
            return False

        ticker = ticker.upper().strip()

        # Check for crypto patterns
        if '-' in ticker or '/' in ticker:
            return True

        # Known crypto patterns
        crypto_patterns = [
            r'^[A-Z]{2,5}USD$',  # Direct pair like BTCUSD
            r'^[A-Z]{2,5}USDT$',  # Tether pairs
            r'^[A-Z]{2,5}EUR$',   # Euro pairs
        ]

        for pattern in crypto_patterns:
            if re.match(pattern, ticker):
                return True

        # Known crypto tickers
        known_crypto = {
            'BTC', 'ETH', 'USDT', 'USDC', 'BNB', 'SOL', 'ADA', 'XRP', 'DOT', 'DOGE',
            'AVAX', 'MATIC', 'LINK', 'UNI', 'ATOM', 'LTC', 'SHIB', 'TRX', 'XLM',
            'FIL', 'ETC', 'VET', 'THETA', 'ICP', 'HBAR', 'EGLD', 'FTT', 'ALGO',
            'AAVE', 'CAKE', 'MANA', 'SAND', 'AXS', 'LUNA', 'CRV', 'COMP', 'MKR'
        }

        return ticker in known_crypto

    @staticmethod
    def _generate_crypto_isin(ticker: str) -> str:
        """Generate crypto ISIN-like identifier."""
        content = f"CRYPTO-{ticker}"
        hash_obj = hashlib.sha256(content.encode())
        hash_hex = hash_obj.hexdigest()[:10]
        return f"XC{hash_hex}".upper()

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "operation_date": "2025-01-15",
                    "ticker": "BTC",
                    "type": "buy",
                    "quantity": "0.025",
                    "amount": "1050.50",
                    "currency": "USD",
                    "fees": "2.50",
                    "asset_type": "crypto",
                    "isin": "XC1A2B3C4D5E6"
                },
                {
                    "operation_date": "2025-01-15",
                    "ticker": "AAPL",
                    "type": "buy",
                    "quantity": "10",
                    "amount": "175.50",
                    "currency": "USD",
                    "fees": "1.00",
                    "asset_type": "stock",
                    "isin": "US0378331005"
                }
            ]
        }
    }


class TransactionCreate(BaseModel):
    """Schema for creating a transaction manually."""
    operation_date: date
    value_date: date
    transaction_type: str = Field(..., pattern="^(buy|sell)$", description="Transaction type: buy or sell")
    ticker: str = Field(..., min_length=1, max_length=20, description="Asset ticker symbol")
    isin: Optional[str] = Field(None, description="ISIN identifier (generated for crypto if not provided)")
    description: str = Field(..., min_length=1, description="Transaction description")
    quantity: Decimal = Field(..., gt=0, description="Number of shares or crypto units")
    price_per_share: Decimal = Field(..., gt=0, description="Price per share/unit")
    amount_eur: Decimal = Field(..., description="Total amount in EUR")
    amount_currency: Decimal = Field(default=Decimal("0"), description="Total amount in original currency")
    currency: str = Field(default="EUR", description="Original transaction currency")
    fees: Decimal = Field(default=Decimal("0"), ge=0, description="Transaction fees")
    order_reference: Optional[str] = Field(None, description="Order reference (auto-generated if not provided)")
    asset_type: Optional[AssetType] = Field(None, description="Asset type (auto-detected if not provided)")

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
            return validate_crypto_ticker(v)

        # Traditional asset validation
        if len(v) > 10:
            raise ValueError("Traditional asset ticker too long (max 10 characters)")

        if not re.match(r'^[A-Z0-9\.]+$', v):
            raise ValueError("Ticker contains invalid characters")

        return v

    @field_validator('currency')
    @classmethod
    def validate_currency(cls, v):
        """Validate currency code."""
        if not v:
            raise ValueError("Currency is required")

        v = v.upper().strip()
        if not re.match(r'^[A-Z]{3}$', v):
            raise ValueError("Currency must be a valid 3-letter code")

        # Support common crypto currencies
        supported_currencies = {
            'EUR', 'USD', 'GBP', 'CHF', 'JPY',  # Traditional
            'BTC', 'ETH', 'USDT', 'USDC', 'BNB'  # Crypto
        }

        if v not in supported_currencies:
            raise ValueError(f"Currency {v} not supported")

        return v

    @field_validator('quantity')
    @classmethod
    def validate_quantity_precision(cls, v, info):
        """Validate quantity precision based on asset type."""
        ticker = info.data.get('ticker', '')

        if ManualTransactionCreate._is_crypto_ticker(ticker):
            return validate_crypto_quantity(v)

        # Traditional assets typically don't need more than 4 decimal places
        if v.as_tuple().exponent < -6:
            raise ValueError("Traditional asset quantity precision too high (max 6 decimal places)")

        return v

    @field_validator('isin')
    @classmethod
    def validate_isin_format(cls, v, info):
        """Validate ISIN format."""
        if not v:
            return v

        ticker = info.data.get('ticker', '')

        if ManualTransactionCreate._is_crypto_ticker(ticker):
            # For crypto, validate crypto ISIN format
            return validate_crypto_isin(v)

        # Traditional ISIN validation
        return validate_crypto_isin(v)

    @model_validator(mode='after')
    def validate_crypto_transaction(self):
        """Additional validation for crypto transactions."""
        ticker = self.ticker.upper().strip()

        if ManualTransactionCreate._is_crypto_ticker(ticker):
            # Auto-generate crypto ISIN if not provided
            if not self.isin:
                self.isin = ManualTransactionCreate._generate_crypto_isin(ticker)

            # Ensure crypto transactions use appropriate precision
            if self.quantity.as_tuple().exponent < -18:
                raise ValueError("Crypto quantity precision too high (max 18 decimal places)")

        return self

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "operation_date": "2025-01-15",
                    "value_date": "2025-01-15",
                    "transaction_type": "buy",
                    "ticker": "BTC",
                    "isin": "XC1A2B3C4D5E6",
                    "description": "Bitcoin purchase",
                    "quantity": "0.025",
                    "price_per_share": "42000.00",
                    "amount_eur": "966.00",
                    "amount_currency": "1050.00",
                    "currency": "USD",
                    "fees": "2.50",
                    "order_reference": "COINBASE-12345",
                    "asset_type": "crypto"
                },
                {
                    "operation_date": "2025-01-15",
                    "value_date": "2025-01-15",
                    "transaction_type": "buy",
                    "ticker": "AAPL",
                    "isin": "US0378331005",
                    "description": "Apple Inc. purchase",
                    "quantity": "10",
                    "price_per_share": "175.50",
                    "amount_eur": "1622.85",
                    "amount_currency": "1755.00",
                    "currency": "USD",
                    "fees": "1.00",
                    "order_reference": "DIRECTA-67890",
                    "asset_type": "stock"
                }
            ]
        }
    }


class TransactionUpdate(BaseModel):
    """Schema for updating transaction fields."""
    operation_date: Optional[date] = Field(None, description="Transaction operation date")
    ticker: Optional[str] = Field(None, min_length=1, max_length=20, description="Asset ticker symbol")
    type: Optional[str] = Field(None, pattern="^(buy|sell)$", description="Transaction type: buy or sell")
    quantity: Optional[Decimal] = Field(None, gt=0, description="Number of shares or crypto units")
    amount: Optional[Decimal] = Field(None, gt=0, description="Price per share/unit")
    currency: Optional[str] = Field(None, description="Transaction currency")
    fees: Optional[Decimal] = Field(None, ge=0, description="Transaction fees")

    @field_validator('ticker')
    @classmethod
    def validate_ticker(cls, v):
        """Validate ticker format for both traditional assets and crypto."""
        if not v:
            return v

        v = v.upper().strip()

        # Check if it's a crypto ticker
        is_crypto = ManualTransactionCreate._is_crypto_ticker(v)

        if is_crypto:
            return validate_crypto_ticker(v)

        # Traditional asset validation
        if len(v) > 10:
            raise ValueError("Traditional asset ticker too long (max 10 characters)")

        if not re.match(r'^[A-Z0-9\.]+$', v):
            raise ValueError("Ticker contains invalid characters")

        return v

    @field_validator('currency')
    @classmethod
    def validate_currency(cls, v):
        """Validate currency code."""
        if not v:
            return v

        v = v.upper().strip()
        if not re.match(r'^[A-Z]{3}$', v):
            raise ValueError("Currency must be a valid 3-letter code")

        # Support common crypto currencies
        supported_currencies = {
            'EUR', 'USD', 'GBP', 'CHF', 'JPY',  # Traditional
            'BTC', 'ETH', 'USDT', 'USDC', 'BNB'  # Crypto
        }

        if v not in supported_currencies:
            raise ValueError(f"Currency {v} not supported")

        return v

    @field_validator('quantity')
    @classmethod
    def validate_quantity_precision(cls, v, info):
        """Validate quantity precision based on asset type."""
        if v is None:
            return v

        ticker = info.data.get('ticker', '')

        if ticker and ManualTransactionCreate._is_crypto_ticker(ticker):
            return validate_crypto_quantity(v)

        # Traditional assets typically don't need more than 4 decimal places
        if v.as_tuple().exponent < -6:
            raise ValueError("Traditional asset quantity precision too high (max 6 decimal places)")

        return v


class TransactionResponse(BaseModel):
    """Schema for transaction response."""
    id: int = Field(..., description="Transaction ID")
    operation_date: date = Field(..., description="Transaction operation date")
    value_date: date = Field(..., description="Transaction value date")
    transaction_type: str = Field(..., description="Transaction type: buy or sell")
    ticker: str = Field(..., description="Asset ticker symbol")
    isin: Optional[str] = Field(None, description="ISIN identifier")
    description: str = Field(..., description="Transaction description")
    quantity: Decimal = Field(..., description="Number of shares or crypto units")
    price_per_share: Decimal = Field(..., description="Price per share/unit")
    amount_eur: Decimal = Field(..., description="Total amount in EUR")
    amount_currency: Decimal = Field(..., description="Total amount in original currency")
    currency: str = Field(..., description="Original transaction currency")
    fees: Decimal = Field(..., description="Transaction fees")
    order_reference: str = Field(..., description="Order reference")
    transaction_hash: str = Field(..., description="Transaction hash for deduplication")
    imported_at: datetime = Field(..., description="When transaction was imported")
    created_at: datetime = Field(..., description="When transaction was created")
    updated_at: datetime = Field(..., description="When transaction was last updated")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "operation_date": "2025-01-15",
                    "value_date": "2025-01-15",
                    "transaction_type": "buy",
                    "ticker": "BTC",
                    "isin": "XC1A2B3C4D5E6",
                    "description": "Bitcoin purchase",
                    "quantity": "0.025",
                    "price_per_share": "42000.00",
                    "amount_eur": "966.00",
                    "amount_currency": "1050.00",
                    "currency": "USD",
                    "fees": "2.50",
                    "order_reference": "COINBASE-12345",
                    "transaction_hash": "abc123def456",
                    "imported_at": "2025-01-15T10:30:00Z",
                    "created_at": "2025-01-15T10:30:00Z",
                    "updated_at": "2025-01-15T10:30:00Z"
                },
                {
                    "id": 2,
                    "operation_date": "2025-01-15",
                    "value_date": "2025-01-15",
                    "transaction_type": "buy",
                    "ticker": "AAPL",
                    "isin": "US0378331005",
                    "description": "Apple Inc. purchase",
                    "quantity": "10",
                    "price_per_share": "175.50",
                    "amount_eur": "1622.85",
                    "amount_currency": "1755.00",
                    "currency": "USD",
                    "fees": "1.00",
                    "order_reference": "DIRECTA-67890",
                    "transaction_hash": "def456ghi789",
                    "imported_at": "2025-01-15T14:20:00Z",
                    "created_at": "2025-01-15T14:20:00Z",
                    "updated_at": "2025-01-15T14:20:00Z"
                }
            ]
        }
    }


class TransactionImportSummary(BaseModel):
    """Schema for CSV import summary response."""
    total_parsed: int = Field(..., description="Total number of transactions parsed from CSV")
    imported: int = Field(..., description="Number of new transactions imported")
    duplicates: int = Field(..., description="Number of duplicate transactions skipped")
    errors: int = Field(default=0, description="Number of transactions with errors")
    message: str = Field(..., description="Import summary message")
    crypto_detected: bool = Field(default=False, description="Whether crypto transactions were detected")
    crypto_count: int = Field(default=0, description="Number of crypto transactions imported")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "total_parsed": 50,
                    "imported": 45,
                    "duplicates": 3,
                    "errors": 2,
                    "message": "Import completed successfully. 45 new transactions added, 3 duplicates skipped.",
                    "crypto_detected": True,
                    "crypto_count": 15
                },
                {
                    "total_parsed": 25,
                    "imported": 23,
                    "duplicates": 2,
                    "errors": 0,
                    "message": "Import completed successfully. 23 new transactions added, 2 duplicates skipped.",
                    "crypto_detected": False,
                    "crypto_count": 0
                }
            ]
        }
    }
