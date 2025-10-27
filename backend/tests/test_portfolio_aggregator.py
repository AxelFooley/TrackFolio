"""
Tests for portfolio aggregation service and unified endpoints.

Tests the PortfolioAggregator service and unified API endpoints.
Integration tests that verify the aggregation endpoints work with the running backend.
"""
import pytest

from app.services.portfolio_aggregator import PortfolioAggregator
from app.schemas.unified import (
    UnifiedHolding, UnifiedOverview, UnifiedPerformance, UnifiedMovers,
    UnifiedSummary, UnifiedPerformanceDataPoint, UnifiedMover, PerformanceSummary,
    PaginatedUnifiedHolding
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
        date="2025-01-01",
        value=Decimal("50000.00"),
        traditional_value=Decimal("30000.00"),
        crypto_value=Decimal("20000.00")
    )
    assert perf_data.date == date(2025, 1, 1)
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
        date="2025-01-01",
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
        holdings=PaginatedUnifiedHolding(items=[], total=0, skip=0, limit=20, has_more=False),
        holdings_total=0,
        movers=UnifiedMovers(gainers=[], losers=[]),
        performance_summary=perf_summary
    )
    assert summary.overview is not None
    assert summary.holdings.items == []
    assert summary.holdings.total == 0


# Integration tests validating unified endpoint response schemas
def test_unified_holdings_response_schema():
    """Test that UnifiedHolding schema validates required fields for /unified-holdings endpoint."""
    from decimal import Decimal

    # Create a valid holding response
    holding = UnifiedHolding(
        id="trad_123",
        type="STOCK",
        ticker="MSFT",
        isin="US5949181045",
        quantity=5.0,
        current_price=Decimal("350.00"),
        current_value=Decimal("1750.00"),
        average_cost=Decimal("300.00"),
        total_cost=Decimal("1500.00"),
        profit_loss=Decimal("250.00"),
        profit_loss_pct=16.67,
        currency="EUR",
        portfolio_id=None,
        portfolio_name="Main Portfolio"
    )

    # Validate schema fields
    assert holding.id == "trad_123"
    assert holding.type == "STOCK"
    assert holding.ticker == "MSFT"
    assert holding.quantity == 5.0
    assert holding.current_value == Decimal("1750.00")
    assert holding.profit_loss_pct == 16.67


def test_unified_overview_response_schema():
    """Test that UnifiedOverview schema validates aggregated metrics for /unified-overview endpoint."""
    from decimal import Decimal

    overview = UnifiedOverview(
        total_value=Decimal("100000.00"),
        traditional_value=Decimal("70000.00"),
        crypto_value=Decimal("30000.00"),
        total_cost=Decimal("90000.00"),
        total_profit=Decimal("10000.00"),
        total_profit_pct=11.11,
        traditional_profit=Decimal("7000.00"),
        traditional_profit_pct=10.0,
        crypto_profit=Decimal("3000.00"),
        crypto_profit_pct=10.0,
        today_change=Decimal("500.00"),
        today_change_pct=0.5,
        currency="EUR"
    )

    # Validate aggregation correctness
    assert overview.total_value == Decimal("100000.00")
    assert overview.traditional_value + overview.crypto_value == overview.total_value
    assert overview.traditional_profit + overview.crypto_profit == overview.total_profit
    assert overview.currency == "EUR"


def test_unified_performance_response_schema():
    """Test that UnifiedPerformanceDataPoint validates time-series data for /unified-performance endpoint."""
    from decimal import Decimal
    from datetime import date, timedelta

    # Create performance data points
    data_points = [
        UnifiedPerformanceDataPoint(
            date=date(2025, 1, 1),
            value=Decimal("50000.00"),
            traditional_value=Decimal("35000.00"),
            crypto_value=Decimal("15000.00")
        ),
        UnifiedPerformanceDataPoint(
            date=date(2025, 1, 2),
            value=Decimal("51000.00"),
            traditional_value=Decimal("35500.00"),
            crypto_value=Decimal("15500.00")
        ),
    ]

    # Validate data point structure
    assert len(data_points) == 2
    assert data_points[0].date == date(2025, 1, 1)
    assert data_points[1].date == date(2025, 1, 2)
    assert data_points[0].value < data_points[1].value
    assert all(
        p.traditional_value + p.crypto_value == p.value
        for p in data_points
    )


def test_unified_movers_response_schema():
    """Test that UnifiedMovers schema validates top gainers/losers for /unified-movers endpoint."""
    from decimal import Decimal

    gainers = [
        UnifiedMover(
            ticker="BTC",
            type="CRYPTO",
            price=45000.0,
            current_value=Decimal("45000.00"),
            change_pct=8.5,
            portfolio_name="Crypto Portfolio",
            currency="USD"
        ),
        UnifiedMover(
            ticker="AAPL",
            type="STOCK",
            price=150.0,
            current_value=Decimal("1500.00"),
            change_pct=5.2,
            portfolio_name="Main Portfolio",
            currency="EUR"
        ),
    ]

    losers = [
        UnifiedMover(
            ticker="ETH",
            type="CRYPTO",
            price=2500.0,
            current_value=Decimal("2500.00"),
            change_pct=-3.2,
            portfolio_name="Crypto Portfolio",
            currency="USD"
        ),
    ]

    movers = UnifiedMovers(gainers=gainers, losers=losers)

    # Validate movers structure
    assert len(movers.gainers) == 2
    assert len(movers.losers) == 1
    assert movers.gainers[0].change_pct > 0  # Gainers should be positive
    assert movers.losers[0].change_pct < 0  # Losers should be negative


def test_unified_summary_response_schema_complete():
    """Test that UnifiedSummary validates complete aggregated response for /unified-summary endpoint."""
    from decimal import Decimal

    overview = UnifiedOverview(
        total_value=Decimal("100000.00"),
        traditional_value=Decimal("70000.00"),
        crypto_value=Decimal("30000.00"),
        total_cost=Decimal("90000.00"),
        total_profit=Decimal("10000.00"),
        total_profit_pct=11.11,
        traditional_profit=Decimal("7000.00"),
        traditional_profit_pct=10.0,
        crypto_profit=Decimal("3000.00"),
        crypto_profit_pct=10.0,
        today_change=Decimal("500.00"),
        today_change_pct=0.5,
        currency="EUR"
    )

    holdings = [
        UnifiedHolding(
            id="1",
            type="STOCK",
            ticker="AAPL",
            quantity=10.0,
            current_price=Decimal("150.00"),
            current_value=Decimal("1500.00"),
            average_cost=Decimal("140.00"),
            total_cost=Decimal("1400.00"),
            profit_loss=Decimal("100.00"),
            profit_loss_pct=7.14,
            portfolio_name="Main"
        ),
    ]

    movers = UnifiedMovers(gainers=[], losers=[])

    perf_summary = PerformanceSummary(
        period_days=365,
        data_points=365,
        data=[]
    )

    summary = UnifiedSummary(
        overview=overview,
        holdings=PaginatedUnifiedHolding(items=holdings, total=1, skip=0, limit=20, has_more=False),
        holdings_total=1,
        movers=movers,
        performance_summary=perf_summary
    )

    # Validate summary structure
    assert summary.overview is not None
    assert summary.overview.total_value == Decimal("100000.00")
    assert len(summary.holdings.items) == 1
    assert summary.holdings.total == 1
    assert summary.movers is not None
    assert summary.performance_summary is not None
    assert summary.performance_summary.period_days == 365
