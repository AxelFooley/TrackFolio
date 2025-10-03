"""Price schemas."""
from pydantic import BaseModel
from datetime import date, datetime
from decimal import Decimal
from typing import Optional


class PriceResponse(BaseModel):
    """Schema for price data response."""
    ticker: str
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    source: str
    created_at: datetime

    class Config:
        from_attributes = True
