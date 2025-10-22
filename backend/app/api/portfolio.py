"""Portfolio API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from decimal import Decimal
from datetime import date, timedelta, datetime
from typing import List, Optional

from app.database import get_db
from app.models import Position, PortfolioSnapshot, PriceHistory, CachedMetrics, Benchmark, StockSplit
from app.schemas.portfolio import PortfolioOverview, PortfolioPerformance, PerformanceDataPoint
from app.schemas.position import PositionResponse
from app.services.price_fetcher import PriceFetcher
from app.services.query_optimizer import query_optimizer

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


def calculate_today_change(
    position_quantity: Decimal,
    price_history: list[PriceHistory]
) -> tuple[Optional[Decimal], Optional[float]]:
    """
    Calculate today's change and percentage change for a position.

    Args:
        position_quantity: The quantity of shares held
        price_history: List of price history entries, ordered by date descending

    Returns:
        Tuple of (today_change, today_change_percent)
        - today_change: Total value change in currency units, or None if insufficient data
        - today_change_percent: Percentage change, or None if calculation not possible
    """
    if not price_history or len(price_history) < 2:
        return None, None

    latest_price = price_history[0]
    previous_price = price_history[1]

    # Calculate price change per share
    price_change = latest_price.close - previous_price.close
    today_change = position_quantity * price_change

    # Calculate percentage change based on previous day's value
    previous_day_value = position_quantity * previous_price.close
    if previous_day_value > 0:
        today_change_percent = float((today_change / previous_day_value) * 100)
    else:
        today_change_percent = None

    return today_change, today_change_percent


def parse_time_range(range_str: str) -> tuple[Optional[date], Optional[date]]:
    """
    Convert time range string to start_date and end_date.

    Args:
        range_str: Time range string (1D, 1W, 1M, 3M, 6M, 1Y, YTD, ALL)

    Returns:
        Tuple of (start_date, end_date). Returns (None, None) for ALL.

    Raises:
        HTTPException: If range_str is invalid
    """
    today = date.today()
    end_date = today

    range_mapping = {
        "1D": timedelta(days=1),
        "1W": timedelta(days=7),
        "1M": timedelta(days=30),
        "3M": timedelta(days=90),
        "6M": timedelta(days=180),
        "1Y": timedelta(days=365),
    }

    if range_str == "ALL":
        return None, None
    elif range_str == "YTD":
        start_date = date(today.year, 1, 1)
        return start_date, end_date
    elif range_str in range_mapping:
        start_date = today - range_mapping[range_str]
        return start_date, end_date
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid range parameter. Must be one of: 1D, 1W, 1M, 3M, 6M, 1Y, YTD, ALL. Got: {range_str}"
        )


@router.get("/overview", response_model=PortfolioOverview)
async def get_portfolio_overview(db: AsyncSession = Depends(get_db)):
    """Get portfolio overview metrics for dashboard with intelligent caching."""
    # Use optimized query with caching
    overview_data = await query_optimizer.get_portfolio_overview_optimized(db)

    # Calculate additional metrics if not cached
    total_cost_basis = overview_data['total_cost_basis']
    current_value = overview_data['total_value']
    total_profit = overview_data['total_profit']

    # Calculate average annual return
    if total_cost_basis and total_cost_basis > 0:
        total_return_percent = (total_profit / total_cost_basis) * 100

        # Placeholder for actual annual return calculation
        # This would normally involve time-series analysis of portfolio value over time
        average_annual_return = total_return_percent / 3  # Placeholder 3-year annualization
    else:
        average_annual_return = None
        total_return_percent = None

    # Get currency from first position or default to EUR
    currency = "EUR"  # This should be properly determined from user settings

    return PortfolioOverview(
        current_value=current_value,
        total_profit=total_profit,
        total_cost_basis=total_cost_basis,
        total_return_percent=total_return_percent,
        average_annual_return=average_annual_return,
        today_gain_loss=Decimal('0'),  # Will be calculated with real-time prices
        today_gain_loss_pct=Decimal('0'),  # Will be calculated with real-time prices
        currency=currency,
        snapshot_date=date.today(),
        last_updated=datetime.utcnow()
    )


@router.get("/holdings")
async def get_holdings(
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
    offset: int = 0,
    sort_by: str = "current_value",
    sort_direction: str = "desc"
):
    """Get portfolio holdings with optimized queries and caching."""
    # Use optimized holdings query with caching
    holdings = await query_optimizer.get_holdings_optimized(
        db, limit=limit, offset=offset, sort_by=sort_by, sort_direction=sort_direction
    )

    # Convert to response format
    return holdings


# Export the query optimizer for use in other modules
__all__ = ['query_optimizer']


@router.get("/performance", response_model=PortfolioPerformance)
async def get_performance(
    range: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Get portfolio performance data for charts.

    Args:
        range: Time range string (1D, 1W, 1M, 3M, 6M, 1Y, YTD, ALL). Takes precedence over start_date/end_date.
        start_date: Start date for custom range (used if range is not provided)
        end_date: End date for custom range (used if range is not provided)
        db: Database session

    Returns:
        PortfolioPerformance with portfolio_data and benchmark_data
    """
    # Use range parameter if provided, otherwise fall back to start_date/end_date
    if range:
        start_date, end_date = parse_time_range(range)

    # Build query for portfolio snapshots
    query = select(PortfolioSnapshot).order_by(PortfolioSnapshot.snapshot_date)

    if start_date:
        query = query.where(PortfolioSnapshot.snapshot_date >= start_date)
    if end_date:
        query = query.where(PortfolioSnapshot.snapshot_date <= end_date)

    result = await db.execute(query)
    snapshots = result.scalars().all()

    # Transform snapshots to performance data points
    portfolio_data = [
        PerformanceDataPoint(date=s.snapshot_date, value=s.total_value)
        for s in snapshots
    ]

    # Calculate portfolio metrics
    portfolio_start_value = None
    portfolio_end_value = None
    portfolio_change_amount = None
    portfolio_change_pct = None

    if snapshots:
        if len(snapshots) == 1:
            # Single data point: no change
            portfolio_start_value = snapshots[0].total_value
            portfolio_end_value = snapshots[0].total_value
            portfolio_change_amount = Decimal("0")
            portfolio_change_pct = 0.0
        else:
            # Multiple data points: calculate change
            portfolio_start_value = snapshots[0].total_value
            portfolio_end_value = snapshots[-1].total_value
            portfolio_change_amount = portfolio_end_value - portfolio_start_value

            if portfolio_start_value > 0:
                portfolio_change_pct = float((portfolio_change_amount / portfolio_start_value) * 100)
            else:
                portfolio_change_pct = None

    # Fetch benchmark data if configured
    benchmark_data = []

    # Get active benchmark
    benchmark_result = await db.execute(
        select(Benchmark).limit(1)
    )
    benchmark = benchmark_result.scalar_one_or_none()

    if benchmark:
        # Get benchmark price history for dates that match portfolio snapshot dates
        # This ensures 1:1 alignment between portfolio and benchmark data
        snapshot_dates = [s.snapshot_date for s in snapshots]

        if snapshot_dates:
            benchmark_query = select(PriceHistory).where(
                PriceHistory.ticker == benchmark.ticker,
                PriceHistory.date.in_(snapshot_dates)  # Only dates that have portfolio snapshots
            ).order_by(PriceHistory.date)

            benchmark_prices_result = await db.execute(benchmark_query)
            benchmark_prices = benchmark_prices_result.scalars().all()

            # Transform to performance data points
            benchmark_data = [
                PerformanceDataPoint(date=p.date, value=p.close)
                for p in benchmark_prices
            ]

    # Calculate benchmark metrics
    benchmark_start_price = None
    benchmark_end_price = None
    benchmark_change_amount = None
    benchmark_change_pct = None

    if benchmark and benchmark_data:
        if len(benchmark_data) == 1:
            # Single data point: no change
            benchmark_start_price = benchmark_data[0].value
            benchmark_end_price = benchmark_data[0].value
            benchmark_change_amount = Decimal("0")
            benchmark_change_pct = 0.0
        else:
            # Multiple data points: calculate change
            benchmark_start_price = benchmark_data[0].value
            benchmark_end_price = benchmark_data[-1].value
            benchmark_change_amount = benchmark_end_price - benchmark_start_price

            if benchmark_start_price > 0:
                benchmark_change_pct = float((benchmark_change_amount / benchmark_start_price) * 100)
            else:
                benchmark_change_pct = None

    return PortfolioPerformance(
        portfolio_data=portfolio_data,
        benchmark_data=benchmark_data,
        portfolio_start_value=portfolio_start_value,
        portfolio_end_value=portfolio_end_value,
        portfolio_change_amount=portfolio_change_amount,
        portfolio_change_pct=portfolio_change_pct,
        benchmark_start_price=benchmark_start_price,
        benchmark_end_price=benchmark_end_price,
        benchmark_change_amount=benchmark_change_amount,
        benchmark_change_pct=benchmark_change_pct
    )


@router.get("/positions/{identifier}")
async def get_position(
    identifier: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get position by ISIN or ticker.

    Args:
        identifier: ISIN (12 chars) or ticker symbol

    Returns:
        Position details with split history
    """
    # Try ISIN first (if 12 characters, assume ISIN)
    if len(identifier) == 12:
        result = await db.execute(
            select(Position).where(Position.isin == identifier)
        )
        position = result.scalar_one_or_none()
    else:
        # Try by current_ticker
        result = await db.execute(
            select(Position).where(Position.current_ticker == identifier)
        )
        position = result.scalar_one_or_none()

    if not position:
        raise HTTPException(status_code=404, detail="Position not found")

    # Get latest price and previous day's price
    price_result = await db.execute(
        select(PriceHistory)
        .where(PriceHistory.ticker == position.current_ticker)
        .order_by(PriceHistory.date.desc())
        .limit(2)  # Get latest and previous day's price
    )
    price_history = price_result.scalars().all()

    # Get cached metrics
    metrics_result = await db.execute(
        select(CachedMetrics)
        .where(
            CachedMetrics.metric_type == "position_metrics",
            CachedMetrics.metric_key == position.current_ticker
        )
    )
    cached_metrics = metrics_result.scalar_one_or_none()

    # Calculate current values
    latest_price = price_history[0] if price_history else None
    current_price = latest_price.close if latest_price else None
    current_value = position.quantity * current_price if current_price else None
    unrealized_gain = current_value - position.cost_basis if current_value else None
    return_percentage = (
        float((current_value - position.cost_basis) / position.cost_basis)
        if current_value and position.cost_basis > 0
        else None
    )

    # Calculate today's change using helper function
    today_change, today_change_percent = calculate_today_change(
        position.quantity,
        price_history
    )

    # Get IRR from cached metrics
    irr = None
    if cached_metrics and cached_metrics.metric_value:
        irr = cached_metrics.metric_value.get("irr")

    # Get split history
    result = await db.execute(
        select(StockSplit)
        .where(StockSplit.isin == position.isin)
        .order_by(StockSplit.split_date)
    )
    splits = result.scalars().all()

    return {
        "id": position.id,
        "isin": position.isin,
        "ticker": position.current_ticker,  # Return as 'ticker' for backwards compat
        "description": position.description,
        "asset_type": position.asset_type.value,
        "quantity": position.quantity,
        "average_cost": position.average_cost,
        "cost_basis": position.cost_basis,
        "current_price": current_price,
        "current_value": current_value,
        "unrealized_gain": unrealized_gain,
        "return_percentage": return_percentage,
        "irr": irr,
        "today_change": today_change,
        "today_change_percent": today_change_percent,
        "last_calculated_at": position.last_calculated_at,
        "splits": [
            {
                "date": str(s.split_date),
                "ratio": f"{s.split_ratio_numerator}:{s.split_ratio_denominator}",
                "old_ticker": s.old_ticker,
                "new_ticker": s.new_ticker
            }
            for s in splits
        ] if splits else []
    }
