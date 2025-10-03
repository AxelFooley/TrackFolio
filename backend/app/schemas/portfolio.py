"""Portfolio schemas."""
from pydantic import BaseModel
from decimal import Decimal
from typing import Optional, List
from datetime import date


class PortfolioOverview(BaseModel):
    """Schema for portfolio overview dashboard."""
    current_value: Decimal
    total_cost_basis: Decimal
    total_profit: Decimal
    average_annual_return: Optional[float]
    today_gain_loss: Optional[Decimal]
    today_gain_loss_pct: Optional[float]


class PerformanceDataPoint(BaseModel):
    """Single data point for performance chart."""
    date: date
    value: Decimal


class PortfolioPerformance(BaseModel):
    """Schema for portfolio performance data."""
    portfolio_data: List[PerformanceDataPoint]
    benchmark_data: List[PerformanceDataPoint]
    portfolio_start_value: Optional[Decimal] = None
    portfolio_end_value: Optional[Decimal] = None
    portfolio_change_amount: Optional[Decimal] = None
    portfolio_change_pct: Optional[float] = None
    benchmark_start_price: Optional[Decimal] = None
    benchmark_end_price: Optional[Decimal] = None
    benchmark_change_amount: Optional[Decimal] = None
    benchmark_change_pct: Optional[float] = None
