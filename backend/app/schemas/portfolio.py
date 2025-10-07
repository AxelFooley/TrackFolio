"""Portfolio schemas."""
from pydantic import BaseModel, Field
from decimal import Decimal
from typing import Optional, List
from datetime import date as date_type

from app.models.position import AssetType


class PortfolioOverview(BaseModel):
    """Schema for portfolio overview dashboard."""
    current_value: Decimal = Field(..., description="Current total portfolio value in EUR")
    total_cost_basis: Decimal = Field(..., description="Total cost basis in EUR")
    total_profit: Decimal = Field(..., description="Total profit/loss in EUR")
    average_annual_return: Optional[float] = Field(None, description="Average annual return percentage")
    today_gain_loss: Optional[Decimal] = Field(None, description="Today's gain/loss in EUR")
    today_gain_loss_pct: Optional[float] = Field(None, description="Today's gain/loss percentage")
    last_updated: Optional[date_type] = Field(None, description="When overview was last calculated")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "current_value": "15000.00",
                    "total_cost_basis": "12000.00",
                    "total_profit": "3000.00",
                    "average_annual_return": 15.5,
                    "today_gain_loss": "250.00",
                    "today_gain_loss_pct": 1.67,
                    "crypto_value": "7500.00",
                    "crypto_cost_basis": "5500.00",
                    "crypto_profit": "2000.00",
                    "stock_value": "7500.00",
                    "stock_cost_basis": "6500.00",
                    "stock_profit": "1000.00",
                    "crypto_percentage": 50.0,
                    "stock_percentage": 50.0,
                    "last_updated": "2025-01-15"
                }
            ]
        }
    }


class PerformanceDataPoint(BaseModel):
    """Single data point for performance chart."""
    date: date_type = Field(..., description="Date of the data point")
    value: Decimal = Field(..., description="Portfolio value on this date")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "date": "2025-01-15",
                    "value": "15000.00",
                    "crypto_value": "7500.00",
                    "stock_value": "7500.00"
                }
            ]
        }
    }


class PortfolioPerformance(BaseModel):
    """Schema for portfolio performance data."""
    portfolio_data: List[PerformanceDataPoint] = Field(..., description="Portfolio performance data points")
    benchmark_data: List[PerformanceDataPoint] = Field(..., description="Benchmark performance data points")
    portfolio_start_value: Optional[Decimal] = Field(None, description="Portfolio value at start date")
    portfolio_end_value: Optional[Decimal] = Field(None, description="Portfolio value at end date")
    portfolio_change_amount: Optional[Decimal] = Field(None, description="Portfolio absolute change")
    portfolio_change_pct: Optional[float] = Field(None, description="Portfolio percentage change")
    benchmark_start_price: Optional[Decimal] = Field(None, description="Benchmark value at start date")
    benchmark_end_price: Optional[Decimal] = Field(None, description="Benchmark value at end date")
    benchmark_change_amount: Optional[Decimal] = Field(None, description="Benchmark absolute change")
    benchmark_change_pct: Optional[float] = Field(None, description="Benchmark percentage change")
    start_date: Optional[date_type] = Field(None, description="Performance start date")
    end_date: Optional[date_type] = Field(None, description="Performance end date")
    days_calculated: Optional[int] = Field(None, description="Number of days in performance calculation")
    annualized_return: Optional[float] = Field(None, description="Annualized return rate")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "portfolio_data": [
                        {
                            "date": "2025-01-01",
                            "value": "12000.00",
                            "crypto_value": "5500.00",
                            "stock_value": "6500.00"
                        },
                        {
                            "date": "2025-01-15",
                            "value": "15000.00",
                            "crypto_value": "7500.00",
                            "stock_value": "7500.00"
                        }
                    ],
                    "benchmark_data": [
                        {
                            "date": "2025-01-01",
                            "value": "100.00"
                        },
                        {
                            "date": "2025-01-15",
                            "value": "102.50"
                        }
                    ],
                    "portfolio_start_value": "12000.00",
                    "portfolio_end_value": "15000.00",
                    "portfolio_change_amount": "3000.00",
                    "portfolio_change_pct": 25.0,
                    "benchmark_start_price": "100.00",
                    "benchmark_end_price": "102.50",
                    "benchmark_change_amount": "2.50",
                    "benchmark_change_pct": 2.5,
                    "start_date": "2025-01-01",
                    "end_date": "2025-01-15",
                    "days_calculated": 14,
                    "annualized_return": 657.5
                }
            ]
        }
    }


class AssetAllocation(BaseModel):
    """Schema for asset allocation breakdown."""
    asset_type: str = Field(..., description="Asset type (crypto, stock, etf)")
    value: Decimal = Field(..., description="Current value in EUR")
    cost_basis: Decimal = Field(..., description="Cost basis in EUR")
    profit: Decimal = Field(..., description="Profit/loss in EUR")
    percentage: float = Field(..., description="Percentage of total portfolio")
    count: int = Field(..., description="Number of positions of this type")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "asset_type": "crypto",
                    "value": "7500.00",
                    "cost_basis": "5500.00",
                    "profit": "2000.00",
                    "percentage": 50.0,
                    "count": 5
                },
                {
                    "asset_type": "stock",
                    "value": "7500.00",
                    "cost_basis": "6500.00",
                    "profit": "1000.00",
                    "percentage": 50.0,
                    "count": 8
                }
            ]
        }
    }


class PortfolioAllocation(BaseModel):
    """Schema for complete portfolio allocation breakdown."""
    total_value: Decimal = Field(..., description="Total portfolio value")
    total_cost_basis: Decimal = Field(..., description="Total portfolio cost basis")
    allocations: List[AssetAllocation] = Field(..., description="Asset type allocations")
    last_updated: date_type = Field(..., description="When allocation was calculated")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "total_value": "15000.00",
                    "total_cost_basis": "12000.00",
                    "allocations": [
                        {
                            "asset_type": "crypto",
                            "value": "7500.00",
                            "cost_basis": "5500.00",
                            "profit": "2000.00",
                            "percentage": 50.0,
                            "count": 5
                        },
                        {
                            "asset_type": "stock",
                            "value": "7500.00",
                            "cost_basis": "6500.00",
                            "profit": "1000.00",
                            "percentage": 50.0,
                            "count": 8
                        }
                    ],
                    "last_updated": "2025-01-15"
                }
            ]
        }
    }
