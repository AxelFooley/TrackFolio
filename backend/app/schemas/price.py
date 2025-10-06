"""Price schemas."""
from pydantic import BaseModel, Field, field_serializer
from datetime import date as date_type, datetime
from decimal import Decimal
from typing import Optional, List


class PriceResponse(BaseModel):
    """Schema for price data response."""
    ticker: str
    date: date_type
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    source: str
    created_at: datetime

    class Config:
        from_attributes = True


class RealtimePriceResponse(BaseModel):
    """Schema for real-time price data response."""
    ticker: str = Field(..., description="Asset ticker symbol")
    isin: Optional[str] = Field(None, description="ISIN code if available")
    current_price: Decimal = Field(..., description="Current market price")
    previous_close: Decimal = Field(..., description="Previous day closing price")
    change_amount: Decimal = Field(..., description="Absolute price change from previous close")
    change_percent: Decimal = Field(..., description="Percentage price change from previous close")
    timestamp: datetime = Field(..., description="Time when price was fetched")

    @field_serializer('current_price', 'previous_close', 'change_amount', 'change_percent')
    def serialize_decimal(self, value: Decimal) -> float:
        """Convert Decimal to float for JSON serialization."""
        return float(value)

    class Config:
        json_schema_extra = {
            "example": {
                "ticker": "AAPL",
                "isin": "US0378331005",
                "current_price": 175.43,
                "previous_close": 174.50,
                "change_amount": 0.93,
                "change_percent": 0.53,
                "timestamp": "2025-10-03T14:30:00Z"
            }
        }


class RealtimePricesResponse(BaseModel):
    """Schema for batch real-time prices response."""
    prices: List[RealtimePriceResponse] = Field(..., description="List of real-time prices")
    fetched_count: int = Field(..., description="Number of prices successfully fetched")
    total_count: int = Field(..., description="Total number of positions requested")
    timestamp: datetime = Field(..., description="Time when batch fetch was initiated")

    class Config:
        json_schema_extra = {
            "example": {
                "prices": [
                    {
                        "ticker": "AAPL",
                        "isin": "US0378331005",
                        "current_price": "175.43",
                        "previous_close": "174.50",
                        "change_amount": "0.93",
                        "change_percent": "0.53",
                        "timestamp": "2025-10-03T14:30:00Z"
                    }
                ],
                "fetched_count": 1,
                "total_count": 1,
                "timestamp": "2025-10-03T14:30:00Z"
            }
        }


class HistoricalPriceResponse(BaseModel):
    """Schema for historical price data response for manual transaction workflow."""
    ticker: str = Field(..., description="Asset ticker symbol")
    date: date_type = Field(..., description="Date of the price data", alias="date")
    price: Optional[Decimal] = Field(None, description="Close price for the specified date")
    currency: Optional[str] = Field(None, description="Currency of the price")
    is_historical: bool = Field(..., description="Whether this is historical data or current price")
    error: Optional[str] = Field(None, description="Error message if price fetching failed")

    @field_serializer('price')
    def serialize_decimal(self, value: Optional[Decimal]) -> Optional[float]:
        """Convert Decimal to float for JSON serialization."""
        return float(value) if value is not None else None

    class Config:
        json_schema_extra = {
            "example": {
                "ticker": "AAPL",
                "date": "2024-01-15",
                "price": 185.50,
                "currency": "USD",
                "is_historical": True,
                "error": None
            }
        }
