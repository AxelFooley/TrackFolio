"""Portfolio API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from decimal import Decimal
from datetime import date, timedelta
from typing import List, Optional
import logging

from app.database import get_db
from app.models import Position, PortfolioSnapshot, PriceHistory, CachedMetrics, Benchmark, StockSplit
from app.schemas.portfolio import PortfolioOverview, PortfolioPerformance, PerformanceDataPoint
from app.schemas.position import PositionResponse
from app.schemas.unified import (
    UnifiedHolding, UnifiedOverview, UnifiedMovers,
    UnifiedSummary, UnifiedPerformanceDataPoint
)
from app.services.portfolio_aggregator import PortfolioAggregator

logger = logging.getLogger(__name__)
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
    """Get portfolio overview metrics for dashboard."""
    result = await db.execute(select(Position))
    positions = result.scalars().all()

    if not positions:
        return PortfolioOverview(
            current_value=Decimal("0"),
            total_cost_basis=Decimal("0"),
            total_profit=Decimal("0"),
            average_annual_return=None,
            today_gain_loss=None,
            today_gain_loss_pct=None
        )

    # Calculate total cost basis and current value
    total_cost_basis = Decimal("0")
    current_value = Decimal("0")

    for position in positions:
        total_cost_basis += position.cost_basis

        # Get latest price (use current_ticker)
        price_result = await db.execute(
            select(PriceHistory)
            .where(PriceHistory.ticker == position.current_ticker)
            .order_by(PriceHistory.date.desc())
            .limit(1)
        )
        latest_price = price_result.scalar_one_or_none()

        if latest_price:
            current_value += position.quantity * latest_price.close

    total_profit = current_value - total_cost_basis

    # Get portfolio metrics from cached_metrics
    portfolio_metrics_result = await db.execute(
        select(CachedMetrics)
        .where(
            CachedMetrics.metric_type == "portfolio_metrics",
            CachedMetrics.metric_key == "global"
        )
    )
    portfolio_metrics = portfolio_metrics_result.scalar_one_or_none()

    # Calculate today's gain/loss by summing all positions' today changes
    today_gain_loss = Decimal("0")
    total_previous_value = Decimal("0")

    for position in positions:
        # Get latest and previous prices for each position
        price_result = await db.execute(
            select(PriceHistory)
            .where(PriceHistory.ticker == position.current_ticker)
            .order_by(PriceHistory.date.desc())
            .limit(2)
        )
        price_history = price_result.scalars().all()

        if price_history and len(price_history) >= 2:
            latest_price = price_history[0]
            previous_price = price_history[1]

            # Add to today's change
            price_change = latest_price.close - previous_price.close
            today_gain_loss += position.quantity * price_change

            # Track previous value for percentage calculation
            total_previous_value += position.quantity * previous_price.close

    # Calculate percentage change
    today_gain_loss_pct = None
    if total_previous_value > 0:
        today_gain_loss_pct = float((today_gain_loss / total_previous_value) * 100)

    # Get average annual return from portfolio metrics
    average_annual_return = None
    if portfolio_metrics and portfolio_metrics.metric_value:
        average_annual_return = portfolio_metrics.metric_value.get("portfolio_return")

    return PortfolioOverview(
        current_value=current_value,
        total_cost_basis=total_cost_basis,
        total_profit=total_profit,
        average_annual_return=average_annual_return,
        today_gain_loss=today_gain_loss,
        today_gain_loss_pct=today_gain_loss_pct
    )


@router.get("/holdings", response_model=List[PositionResponse])
async def get_holdings(db: AsyncSession = Depends(get_db)):
    """Get all current holdings/positions with calculated metrics."""
    result = await db.execute(select(Position))
    positions = result.scalars().all()

    response = []

    for position in positions:
        # Get latest and previous prices (use current_ticker)
        price_result = await db.execute(
            select(PriceHistory)
            .where(PriceHistory.ticker == position.current_ticker)
            .order_by(PriceHistory.date.desc())
            .limit(2)  # Get latest and previous day's price
        )
        price_history = price_result.scalars().all()

        # Get cached metrics (IRR, etc.) - use current_ticker for backwards compatibility
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

        response.append(
            PositionResponse(
                id=position.id,
                ticker=position.current_ticker,  # Return current_ticker as 'ticker'
                isin=position.isin,
                description=position.description,
                asset_type=position.asset_type.value,
                quantity=position.quantity,
                average_cost=position.average_cost,
                cost_basis=position.cost_basis,
                current_price=current_price,
                current_value=current_value,
                unrealized_gain=unrealized_gain,
                return_percentage=return_percentage,
                irr=irr,
                today_change=today_change,
                today_change_percent=today_change_percent,
                last_calculated_at=position.last_calculated_at
            )
        )

    return response


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


# Unified Portfolio Endpoints (combining traditional and crypto)

@router.get("/unified-holdings", response_model=List[UnifiedHolding])
async def get_unified_holdings(
    skip: int = Query(0, ge=0, description="Number of holdings to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Max holdings to return"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get unified list of all holdings (traditional and crypto).

    Returns combined positions from traditional portfolio (Position model)
    and all crypto portfolios (CryptoPortfolio/CryptoTransaction).

    Each holding includes current price, value, and performance metrics.

    Args:
        skip: Number of holdings to skip (pagination offset)
        limit: Maximum number of holdings to return (1-1000)

    Returns:
        List of unified holdings with standardized schema
    """
    try:
        aggregator = PortfolioAggregator(db)
        all_holdings = await aggregator.get_unified_holdings()

        # Apply pagination
        paginated_holdings = all_holdings[skip : skip + limit]

        return paginated_holdings
    except Exception as e:
        logger.error(f"Error getting unified holdings: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve unified holdings")


@router.get("/unified-overview", response_model=UnifiedOverview)
async def get_unified_overview(db: AsyncSession = Depends(get_db)):
    """
    Get aggregated portfolio overview combining traditional and crypto.

    Returns top-level metrics:
    - total_value: combined current value
    - traditional_value, crypto_value: breakdown
    - total_profit, total_profit_pct: combined P&L
    - traditional_profit, crypto_profit: breakdown by portfolio type
    - today_change, today_change_pct

    Returns:
        Unified overview metrics
    """
    try:
        aggregator = PortfolioAggregator(db)
        overview = await aggregator.get_unified_overview()
        return overview
    except Exception as e:
        logger.error(f"Error getting unified overview: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve unified overview")


@router.get("/unified-performance")
async def get_unified_performance(
    range: Optional[str] = Query(None, description="Time range (1D, 1W, 1M, 3M, 6M, 1Y, YTD, ALL)"),
    days: Optional[int] = Query(None, ge=1, le=3650, description="Number of days of history (alternative to range)"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get unified performance data combining traditional and crypto portfolios.

    Merges daily snapshots from both portfolio systems into a single time-series.
    Returns data matching frontend expectations with portfolio_data and benchmark_data.

    Args:
        range: Time range string (1D, 1W, 1M, 3M, 6M, 1Y, YTD, ALL). Takes precedence over days.
        days: Number of days of history (1-3650, default 365) - used if range not provided

    Returns:
        JSON object with portfolio_data and benchmark_data arrays
    """
    try:
        # Use range parameter if provided, otherwise use days (default 365)
        if range:
            start_date, end_date = parse_time_range(range)
        else:
            # Use days parameter or default to 365
            days_to_fetch = days or 365
            end_date = date.today()
            start_date = end_date - timedelta(days=days_to_fetch)

        # Get traditional portfolio snapshots
        query = select(PortfolioSnapshot).order_by(PortfolioSnapshot.snapshot_date)
        if start_date:
            query = query.where(PortfolioSnapshot.snapshot_date >= start_date)
        if end_date:
            query = query.where(PortfolioSnapshot.snapshot_date <= end_date)

        result = await db.execute(query)
        traditional_snapshots = result.scalars().all()

        # Get crypto snapshots
        from app.models import CryptoPortfolioSnapshot
        crypto_query = select(CryptoPortfolioSnapshot).order_by(CryptoPortfolioSnapshot.snapshot_date)
        if start_date:
            crypto_query = crypto_query.where(CryptoPortfolioSnapshot.snapshot_date >= start_date)
        if end_date:
            crypto_query = crypto_query.where(CryptoPortfolioSnapshot.snapshot_date <= end_date)

        crypto_result = await db.execute(crypto_query)
        crypto_snapshots = crypto_result.scalars().all()

        # Merge snapshots by date
        snapshot_map: dict[date, dict] = {}

        for snapshot in traditional_snapshots:
            if snapshot.snapshot_date not in snapshot_map:
                snapshot_map[snapshot.snapshot_date] = {
                    "date": str(snapshot.snapshot_date),
                    "total": Decimal("0"),
                    "traditional": Decimal("0"),
                    "crypto": Decimal("0")
                }
            snapshot_map[snapshot.snapshot_date]["traditional"] = snapshot.total_value or Decimal("0")
            # Add to total
            snapshot_map[snapshot.snapshot_date]["total"] = (
                snapshot_map[snapshot.snapshot_date]["total"] +
                (snapshot.total_value or Decimal("0"))
            )

        for snapshot in crypto_snapshots:
            if snapshot.snapshot_date not in snapshot_map:
                snapshot_map[snapshot.snapshot_date] = {
                    "date": str(snapshot.snapshot_date),
                    "total": Decimal("0"),
                    "traditional": Decimal("0"),
                    "crypto": Decimal("0")
                }
            # Use the correct value field based on portfolio base_currency
            # If base_currency is EUR, use total_value_eur; if USD, use total_value_usd
            crypto_val = (
                snapshot.total_value_eur
                if snapshot.base_currency == "EUR"
                else snapshot.total_value_usd
            ) or Decimal("0")
            snapshot_map[snapshot.snapshot_date]["crypto"] += crypto_val
            # Add to total
            snapshot_map[snapshot.snapshot_date]["total"] = (
                snapshot_map[snapshot.snapshot_date]["total"] + crypto_val
            )

        # Convert to sorted list
        portfolio_data = [
            {
                "date": p["date"],
                "total": str(p["total"]),
                "traditional": str(p["traditional"]),
                "crypto": str(p["crypto"])
            }
            for p in sorted(snapshot_map.values(), key=lambda x: x["date"])
        ]

        # Get benchmark data if configured (aligned with merged snapshot dates)
        benchmark_data = []
        benchmark_result = await db.execute(select(Benchmark).limit(1))
        benchmark = benchmark_result.scalar_one_or_none()

        if benchmark:
            snapshot_dates = [date.fromisoformat(p["date"]) for p in portfolio_data]
            if snapshot_dates:
                benchmark_query = select(PriceHistory).where(
                    PriceHistory.ticker == benchmark.ticker,
                    PriceHistory.date.in_(snapshot_dates)
                ).order_by(PriceHistory.date)

                benchmark_prices_result = await db.execute(benchmark_query)
                benchmark_prices = benchmark_prices_result.scalars().all()

                benchmark_data = [
                    {
                        "date": str(p.date),
                        "value": str(p.close)
                    }
                    for p in benchmark_prices
                ]

        return {
            "portfolio_data": portfolio_data,
            "benchmark_data": benchmark_data
        }
    except Exception as e:
        logger.error(f"Error getting unified performance: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve unified performance")


@router.get("/unified-movers", response_model=UnifiedMovers)
async def get_unified_movers(
    top_n: int = Query(5, ge=1, le=50, description="Number of top gainers/losers"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get top gainers and losers from both traditional and crypto portfolios.

    Calculates return percentage for each holding and returns the top N gainers
    and top N losers across all holdings, sorted by change percentage.

    Args:
        top_n: Number of gainers and losers to return (1-50, default 5)

    Returns:
        Top gainers and losers
    """
    try:
        aggregator = PortfolioAggregator(db)
        movers = await aggregator.get_unified_movers(top_n=top_n)
        return movers
    except Exception as e:
        logger.error(f"Error getting unified movers: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve unified movers")


@router.get("/unified-summary", response_model=UnifiedSummary)
async def get_unified_summary(
    holdings_limit: int = Query(20, ge=1, le=100, description="Max holdings to return"),
    performance_days: int = Query(365, ge=1, le=3650, description="Days of performance history"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get complete unified summary combining all aggregated data.

    This is a convenience endpoint that returns overview, holdings (paginated),
    movers, and performance data in a single response to reduce API round trips.

    Args:
        holdings_limit: Maximum number of holdings to return (1-100, default 20)
        performance_days: Days of performance history (1-3650, default 365)

    Returns:
        Complete unified portfolio summary
    """
    try:
        aggregator = PortfolioAggregator(db)
        summary = await aggregator.get_unified_summary(
            holdings_limit=holdings_limit,
            performance_days=performance_days
        )

        # Transform performance data to proper schema
        perf_data = [
            UnifiedPerformanceDataPoint(
                date_point=p["date"],
                value=p["value"],
                crypto_value=p["crypto_value"],
                traditional_value=p["traditional_value"]
            )
            for p in summary["performance_summary"]["data"]
        ]

        return UnifiedSummary(
            overview=summary["overview"],
            holdings=summary["holdings"],
            holdings_total=summary["holdings_total"],
            movers=summary["movers"],
            performance_summary={
                "period_days": summary["performance_summary"]["period_days"],
                "data_points": summary["performance_summary"]["data_points"],
                "data": perf_data
            }
        )
    except Exception as e:
        logger.error(f"Error getting unified summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve unified summary")
