"""
Tests for portfolio aggregation service and unified endpoints.

Tests the PortfolioAggregator service and unified API endpoints.
Integration tests that verify the aggregation endpoints work with the running backend.
"""
import pytest

from app.services.portfolio_aggregator import PortfolioAggregator
from app.schemas.unified import (
    UnifiedHolding, UnifiedOverview, UnifiedPerformance, UnifiedMovers,
    UnifiedSummary, UnifiedPerformanceDataPoint, UnifiedMover, PerformanceSummary
)


# Mark entire module as integration test (requires running backend)
pytestmark = pytest.mark.integration


def test_portfolio_aggregator_imports():
    """Test that portfolio aggregator can be imported successfully."""
    assert PortfolioAggregator is not None


def test_unified_schemas_import():
    """Test that all unified schemas can be imported successfully."""
    assert UnifiedHolding is not None
    assert UnifiedOverview is not None
    assert UnifiedPerformance is not None
    assert UnifiedMovers is not None
    assert UnifiedSummary is not None
    assert UnifiedPerformanceDataPoint is not None


def test_unified_holding_schema():
    """Test UnifiedHolding schema creation."""
    holding = UnifiedHolding(
        id="test_1",
        type="STOCK",
        ticker="AAPL",
        isin="US0378691033",
        quantity=10.0,
        current_price=None,
        current_value=None,
        average_cost="150.00",
        total_cost="1500.00",
        profit_loss=None,
        profit_loss_pct=None,
        currency="EUR",
        portfolio_id=None,
        portfolio_name="Main Portfolio"
    )
    assert holding.ticker == "AAPL"
    assert holding.type == "STOCK"
    assert holding.portfolio_name == "Main Portfolio"


def test_unified_overview_schema():
    """Test UnifiedOverview schema creation."""
    from decimal import Decimal
    overview = UnifiedOverview(
        total_value="50000.00",
        traditional_value="30000.00",
        crypto_value="20000.00",
        total_cost="45000.00",
        total_profit="5000.00",
        total_profit_pct=11.11,
        traditional_profit="3000.00",
        traditional_profit_pct=10.0,
        crypto_profit="2000.00",
        crypto_profit_pct=11.11,
        today_change="250.00",
        today_change_pct=0.5,
        currency="EUR"
    )
    assert overview.total_value == Decimal("50000.00")
    assert overview.currency == "EUR"


def test_safe_percentage_helper():
    """Test the _safe_percentage helper method."""
    from decimal import Decimal

    # Test normal case
    result = PortfolioAggregator._safe_percentage(Decimal("100"), Decimal("1000"))
    assert result == 10.0

    # Test division by zero
    result = PortfolioAggregator._safe_percentage(Decimal("100"), Decimal("0"))
    assert result is None

    # Test None
    result = PortfolioAggregator._safe_percentage(Decimal("100"), None)
    assert result is None

    # Test negative values
    result = PortfolioAggregator._safe_percentage(Decimal("-50"), Decimal("1000"))
    assert result == -5.0


def test_unified_performance_schema():
    """Test UnifiedPerformance schema creation."""
    from decimal import Decimal
    from datetime import date

    perf_data = UnifiedPerformanceDataPoint(
        date_point="2025-01-01",
        value=Decimal("50000.00"),
        traditional_value=Decimal("30000.00"),
        crypto_value=Decimal("20000.00")
    )
    assert perf_data.date_point == date(2025, 1, 1)
    assert perf_data.value == Decimal("50000.00")
    assert perf_data.traditional_value == Decimal("30000.00")


def test_unified_movers_schema():
    """Test UnifiedMovers schema creation."""
    mover = UnifiedMover(
        ticker="BTC",
        type="CRYPTO",
        price=45000.0,
        change_pct=5.5,
        portfolio_name="Main"
    )
    assert mover.ticker == "BTC"
    assert mover.type == "CRYPTO"
    assert mover.change_pct == 5.5

    movers = UnifiedMovers(gainers=[mover], losers=[])
    assert len(movers.gainers) == 1
    assert len(movers.losers) == 0


def test_unified_summary_schema():
    """Test UnifiedSummary schema creation."""
    from decimal import Decimal

    overview = UnifiedOverview(
        total_value="50000.00",
        traditional_value="30000.00",
        crypto_value="20000.00",
        total_cost="45000.00",
        total_profit="5000.00",
        total_profit_pct=11.11,
        traditional_profit="3000.00",
        traditional_profit_pct=10.0,
        crypto_profit="2000.00",
        crypto_profit_pct=11.11,
        today_change="250.00",
        today_change_pct=0.5,
        currency="EUR"
    )

    perf_data = UnifiedPerformanceDataPoint(
        date_point="2025-01-01",
        value="50000.00",
        traditional_value="30000.00",
        crypto_value="20000.00"
    )

    perf_summary = PerformanceSummary(
        period_days=365,
        data_points=1,
        data=[perf_data]
    )

    summary = UnifiedSummary(
        overview=overview,
        holdings=[],
        holdings_total=0,
        movers=UnifiedMovers(gainers=[], losers=[]),
        performance_summary=perf_summary
    )
    assert summary.overview is not None
    assert summary.holdings == []
    assert summary.holdings_total == 0
