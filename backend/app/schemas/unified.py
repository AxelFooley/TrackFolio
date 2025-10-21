"""
Unified portfolio schemas - Request/response models for aggregated endpoints.

Provides Pydantic models for unified portfolio aggregation endpoints that combine
traditional and crypto holdings in a single view.
"""
from pydantic import BaseModel
from decimal import Decimal
from typing import Optional, List
from datetime import date


class UnifiedHolding(BaseModel):
    """Schema for a single unified holding (traditional or crypto)."""

    id: str
    type: str
    ticker: str
    isin: Optional[str] = None
    quantity: float
    current_price: Optional[Decimal] = None
    current_value: Optional[Decimal] = None
    average_cost: Decimal
    total_cost: Decimal
    profit_loss: Optional[Decimal] = None
    profit_loss_pct: Optional[float] = None
    currency: str = "EUR"
    portfolio_id: Optional[str] = None
    portfolio_name: str

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "id": "trad_1",
                "type": "STOCK",
                "ticker": "AAPL",
                "isin": "US0378691033",
                "quantity": 10.5,
                "current_price": "150.25",
                "current_value": "1577.625",
                "average_cost": "140.00",
                "total_cost": "1470.00",
                "profit_loss": "107.625",
                "profit_loss_pct": 7.32,
                "currency": "EUR",
                "portfolio_id": None,
                "portfolio_name": "Main Portfolio"
            }
        }


class UnifiedOverview(BaseModel):
    """Schema for unified portfolio overview."""

    total_value: Decimal
    traditional_value: Decimal
    crypto_value: Decimal
    total_cost: Decimal
    total_profit: Decimal
    total_profit_pct: Optional[float] = None
    traditional_profit: Decimal
    traditional_profit_pct: Optional[float] = None
    crypto_profit: Decimal
    crypto_profit_pct: Optional[float] = None
    today_change: Decimal
    today_change_pct: Optional[float] = None
    currency: str = "EUR"

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "total_value": "50000.00",
                "traditional_value": "30000.00",
                "crypto_value": "20000.00",
                "total_cost": "45000.00",
                "total_profit": "5000.00",
                "total_profit_pct": 11.11,
                "traditional_profit": "3000.00",
                "traditional_profit_pct": 10.00,
                "crypto_profit": "2000.00",
                "crypto_profit_pct": 11.11,
                "today_change": "250.00",
                "today_change_pct": 0.50,
                "currency": "EUR"
            }
        }


class UnifiedPerformanceDataPoint(BaseModel):
    """Single data point in performance time series."""

    date_point: date
    value: Decimal
    crypto_value: Decimal
    traditional_value: Decimal

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "date": "2025-01-01",
                "value": "45000.00",
                "crypto_value": "20000.00",
                "traditional_value": "25000.00"
            }
        }


class UnifiedPerformance(BaseModel):
    """Schema for unified performance data."""

    data: List[UnifiedPerformanceDataPoint]

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "data": [
                    {
                        "date": "2025-01-01",
                        "value": "45000.00",
                        "crypto_value": "20000.00",
                        "traditional_value": "25000.00"
                    }
                ]
            }
        }


class UnifiedMover(BaseModel):
    """Schema for a top mover (gainer or loser)."""

    ticker: str
    type: str
    price: float
    change_pct: float
    portfolio_name: str

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "ticker": "BTC",
                "type": "CRYPTO",
                "price": 45000.0,
                "change_pct": 5.5,
                "portfolio_name": "Crypto Portfolio 1"
            }
        }


class UnifiedMovers(BaseModel):
    """Schema for gainers and losers."""

    gainers: List[UnifiedMover]
    losers: List[UnifiedMover]

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "gainers": [
                    {
                        "ticker": "BTC",
                        "type": "CRYPTO",
                        "price": 45000.0,
                        "change_pct": 5.5,
                        "portfolio_name": "Crypto Portfolio 1"
                    }
                ],
                "losers": []
            }
        }


class PerformanceSummary(BaseModel):
    """Summary of performance data."""

    period_days: int
    data_points: int
    data: List[UnifiedPerformanceDataPoint]

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "period_days": 365,
                "data_points": 250,
                "data": []
            }
        }


class UnifiedSummary(BaseModel):
    """Complete unified portfolio summary."""

    overview: UnifiedOverview
    holdings: List[UnifiedHolding]
    holdings_total: int
    movers: UnifiedMovers
    performance_summary: PerformanceSummary

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "overview": {
                    "total_value": "50000.00",
                    "traditional_value": "30000.00",
                    "crypto_value": "20000.00",
                    "total_cost": "45000.00",
                    "total_profit": "5000.00",
                    "total_profit_pct": 11.11,
                    "traditional_profit": "3000.00",
                    "traditional_profit_pct": 10.00,
                    "crypto_profit": "2000.00",
                    "crypto_profit_pct": 11.11,
                    "today_change": "250.00",
                    "today_change_pct": 0.50,
                    "currency": "EUR"
                },
                "holdings": [],
                "holdings_total": 15,
                "movers": {
                    "gainers": [],
                    "losers": []
                },
                "performance_summary": {
                    "period_days": 365,
                    "data_points": 250,
                    "data": []
                }
            }
        }
