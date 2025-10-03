"""Transaction schemas."""
from pydantic import BaseModel, Field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional


class TransactionCreate(BaseModel):
    """Schema for creating a transaction (not used in CSV import)."""
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
    order_reference: str


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
