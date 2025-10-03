"""Position schemas."""
from pydantic import BaseModel
from datetime import datetime
from decimal import Decimal
from typing import Optional


class PositionResponse(BaseModel):
    """Schema for position response."""
    id: int
    ticker: str
    isin: Optional[str]
    description: str
    asset_type: str
    quantity: Decimal
    average_cost: Decimal
    cost_basis: Decimal
    current_price: Optional[Decimal] = None
    current_value: Optional[Decimal] = None
    unrealized_gain: Optional[Decimal] = None
    return_percentage: Optional[float] = None
    irr: Optional[float] = None
    last_calculated_at: datetime

    class Config:
        from_attributes = True
