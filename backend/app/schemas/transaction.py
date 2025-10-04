"""Transaction schemas."""
from pydantic import BaseModel, Field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional


class ManualTransactionCreate(BaseModel):
    """Schema for creating a transaction manually via the frontend."""
    operation_date: date
    ticker: str
    type: str = Field(..., pattern="^(buy|sell)$")  # Frontend sends "type" not "transaction_type"
    quantity: Decimal = Field(..., gt=0)
    amount: Decimal = Field(..., gt=0)  # This is price_per_share in frontend
    currency: str = "EUR"
    fees: Decimal = Field(default=Decimal("0"), ge=0)


class TransactionCreate(BaseModel):
    """Schema for creating a transaction manually."""
    operation_date: date
    value_date: date
    transaction_type: str = Field(..., pattern="^(buy|sell)$")
    ticker: str
    isin: Optional[str] = None
    description: str
    quantity: Decimal = Field(..., gt=0)
    price_per_share: Decimal = Field(..., gt=0)
    amount_eur: Decimal
    amount_currency: Decimal = Decimal("0")
    currency: str = "EUR"
    fees: Decimal = Decimal("0")
    order_reference: Optional[str] = None  # Auto-generated if not provided


class TransactionUpdate(BaseModel):
    """Schema for updating transaction (fees only)."""
    fees: Decimal = Field(..., ge=0)


class TransactionResponse(BaseModel):
    """Schema for transaction response."""
    id: int
    operation_date: date
    value_date: date
    transaction_type: str
    ticker: str
    isin: Optional[str]
    description: str
    quantity: Decimal
    price_per_share: Decimal
    amount_eur: Decimal
    amount_currency: Decimal
    currency: str
    fees: Decimal
    order_reference: str
    transaction_hash: str
    imported_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TransactionImportSummary(BaseModel):
    """Schema for CSV import summary response."""
    total_parsed: int
    imported: int
    duplicates: int
    message: str
