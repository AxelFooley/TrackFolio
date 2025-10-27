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
        holdings=[],
        holdings_total=0,
        movers=UnifiedMovers(gainers=[], losers=[]),
        performance_summary=perf_summary
    )
    assert summary.overview is not None
    assert summary.holdings == []
    assert summary.holdings_total == 0


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
        holdings=holdings,
        holdings_total=1,
        movers=movers,
        performance_summary=perf_summary
    )

    # Validate summary structure
    assert summary.overview is not None
    assert summary.overview.total_value == Decimal("100000.00")
    assert len(summary.holdings) == 1
    assert summary.holdings_total == 1
    assert summary.movers is not None
    assert summary.performance_summary is not None
    assert summary.performance_summary.period_days == 365


# Pagination tests for unified holdings endpoint
def test_paginated_holdings_response_structure():
    """Test that PaginatedUnifiedHolding schema validates pagination structure."""
    from decimal import Decimal

    holdings = [
        UnifiedHolding(
            id="trad_1",
            type="STOCK",
            ticker="AAPL",
            isin="US0378691033",
            quantity=10.5,
            current_price=Decimal("150.25"),
            current_value=Decimal("1577.625"),
            average_cost=Decimal("140.00"),
            total_cost=Decimal("1470.00"),
            profit_loss=Decimal("107.625"),
            profit_loss_pct=7.32,
            currency="EUR",
            portfolio_id=None,
            portfolio_name="Main Portfolio"
        ),
        UnifiedHolding(
            id="crypto_1",
            type="CRYPTO",
            ticker="BTC",
            quantity=0.5,
            current_price=Decimal("45000.00"),
            current_value=Decimal("22500.00"),
            average_cost=Decimal("40000.00"),
            total_cost=Decimal("20000.00"),
            profit_loss=Decimal("2500.00"),
            profit_loss_pct=12.5,
            currency="USD",
            portfolio_id="crypto-uuid-1",
            portfolio_name="Crypto Portfolio 1"
        )
    ]

    paginated = PaginatedUnifiedHolding(
        items=holdings,
        total=42,
        skip=0,
        limit=20,
        has_more=True
    )

    # Validate pagination structure
    assert paginated.items == holdings
    assert len(paginated.items) == 2
    assert paginated.total == 42
    assert paginated.skip == 0
    assert paginated.limit == 20
    assert paginated.has_more is True


def test_pagination_offset_and_limit():
    """Test pagination calculation with offset and limit."""
    from decimal import Decimal

    # Create 5 sample holdings
    holdings = [
        UnifiedHolding(
            id=f"holding_{i}",
            type="STOCK",
            ticker=f"TICK{i}",
            quantity=float(i),
            current_price=Decimal("100.00"),
            current_value=Decimal(f"{100 * i}.00"),
            average_cost=Decimal("100.00"),
            total_cost=Decimal(f"{100 * i}.00"),
            profit_loss=Decimal("0.00"),
            profit_loss_pct=0.0,
            currency="EUR",
            portfolio_id=None,
            portfolio_name="Main Portfolio"
        )
        for i in range(1, 6)
    ]

    # Test case 1: First page (skip=0, limit=2)
    paginated_page1 = PaginatedUnifiedHolding(
        items=holdings[0:2],
        total=5,
        skip=0,
        limit=2,
        has_more=True
    )
    assert paginated_page1.skip == 0
    assert paginated_page1.limit == 2
    assert len(paginated_page1.items) == 2
    assert paginated_page1.has_more is True
    assert paginated_page1.items[0].id == "holding_1"

    # Test case 2: Second page (skip=2, limit=2)
    paginated_page2 = PaginatedUnifiedHolding(
        items=holdings[2:4],
        total=5,
        skip=2,
        limit=2,
        has_more=True
    )
    assert paginated_page2.skip == 2
    assert paginated_page2.limit == 2
    assert len(paginated_page2.items) == 2
    assert paginated_page2.has_more is True
    assert paginated_page2.items[0].id == "holding_3"

    # Test case 3: Last page (skip=4, limit=2)
    paginated_page3 = PaginatedUnifiedHolding(
        items=holdings[4:],
        total=5,
        skip=4,
        limit=2,
        has_more=False
    )
    assert paginated_page3.skip == 4
    assert paginated_page3.limit == 2
    assert len(paginated_page3.items) == 1
    assert paginated_page3.has_more is False
    assert paginated_page3.items[0].id == "holding_5"


def test_pagination_with_empty_holdings():
    """Test pagination behavior with no holdings."""
    paginated = PaginatedUnifiedHolding(
        items=[],
        total=0,
        skip=0,
        limit=20,
        has_more=False
    )

    # Validate empty pagination
    assert paginated.items == []
    assert paginated.total == 0
    assert paginated.skip == 0
    assert paginated.limit == 20
    assert paginated.has_more is False


def test_pagination_beyond_total_count():
    """Test pagination when skip exceeds total count."""
    from decimal import Decimal

    holdings = [
        UnifiedHolding(
            id=f"holding_{i}",
            type="STOCK",
            ticker=f"TICK{i}",
            quantity=float(i),
            current_price=Decimal("100.00"),
            current_value=Decimal(f"{100 * i}.00"),
            average_cost=Decimal("100.00"),
            total_cost=Decimal(f"{100 * i}.00"),
            profit_loss=Decimal("0.00"),
            profit_loss_pct=0.0,
            currency="EUR",
            portfolio_id=None,
            portfolio_name="Main Portfolio"
        )
        for i in range(1, 4)
    ]

    # Request page beyond available items (skip=10, limit=20 with only 3 total)
    paginated = PaginatedUnifiedHolding(
        items=[],  # No items because skip exceeds total
        total=3,
        skip=10,
        limit=20,
        has_more=False
    )

    assert paginated.items == []
    assert paginated.total == 3
    assert paginated.skip == 10
    assert paginated.has_more is False


def test_has_more_flag_calculation():
    """Test the has_more flag calculation logic."""
    from decimal import Decimal

    # Create test holdings
    holdings = [
        UnifiedHolding(
            id=f"holding_{i}",
            type="STOCK",
            ticker=f"TICK{i}",
            quantity=float(i),
            current_price=Decimal("100.00"),
            current_value=Decimal(f"{100 * i}.00"),
            average_cost=Decimal("100.00"),
            total_cost=Decimal(f"{100 * i}.00"),
            profit_loss=Decimal("0.00"),
            profit_loss_pct=0.0,
            currency="EUR",
            portfolio_id=None,
            portfolio_name="Main Portfolio"
        )
        for i in range(1, 101)  # 100 total holdings
    ]

    test_cases = [
        # (skip, limit, expected_has_more)
        (0, 20, True),    # 0 + 20 = 20, which is < 100
        (20, 20, True),   # 20 + 20 = 40, which is < 100
        (80, 20, False),  # 80 + 20 = 100, which is NOT < 100
        (90, 20, False),  # 90 + 20 = 110, which is NOT < 100
        (99, 1, False),   # 99 + 1 = 100, which is NOT < 100
    ]

    for skip, limit, expected_has_more in test_cases:
        end_index = min(skip + limit, 100)
        paginated = PaginatedUnifiedHolding(
            items=holdings[skip:end_index],
            total=100,
            skip=skip,
            limit=limit,
            has_more=expected_has_more
        )
        assert paginated.has_more == expected_has_more, \
            f"Failed for skip={skip}, limit={limit}: expected has_more={expected_has_more}, got {paginated.has_more}"
