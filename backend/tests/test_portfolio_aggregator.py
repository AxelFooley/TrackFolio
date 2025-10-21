"""
Tests for portfolio aggregation service and unified endpoints.

Tests the PortfolioAggregator service and unified API endpoints.
Integration tests that verify the aggregation endpoints work with the running backend.
"""
import pytest

from app.services.portfolio_aggregator import PortfolioAggregator
from app.schemas.unified import (
    UnifiedHolding, UnifiedOverview, UnifiedPerformance, UnifiedMovers,
    UnifiedSummary, UnifiedPerformanceDataPoint
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
    assert overview.total_value == "50000.00"
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


def test_api_endpoint_availability():
    """Test that the API endpoints are accessible."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    # Test unified-holdings endpoint
    response = client.get("/api/portfolio/unified-holdings")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

    # Test unified-overview endpoint
    response = client.get("/api/portfolio/unified-overview")
    assert response.status_code == 200
    data = response.json()
    assert "total_value" in data
    assert "currency" in data

    # Test unified-performance endpoint
    response = client.get("/api/portfolio/unified-performance?days=30")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert isinstance(data["data"], list)

    # Test unified-movers endpoint
    response = client.get("/api/portfolio/unified-movers?top_n=5")
    assert response.status_code == 200
    data = response.json()
    assert "gainers" in data
    assert "losers" in data

    # Test unified-summary endpoint
    response = client.get("/api/portfolio/unified-summary")
    assert response.status_code == 200
    data = response.json()
    assert "overview" in data
    assert "holdings" in data
    assert "movers" in data
    assert "performance_summary" in data


def test_api_performance_endpoint_validation():
    """Test unified performance endpoint parameter validation."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    # Test valid range
    response = client.get("/api/portfolio/unified-performance?days=365")
    assert response.status_code == 200

    # Test too many days (should fail validation)
    response = client.get("/api/portfolio/unified-performance?days=10000")
    assert response.status_code == 422

    # Test negative days (should fail validation)
    response = client.get("/api/portfolio/unified-performance?days=-1")
    assert response.status_code == 422


def test_api_movers_endpoint_validation():
    """Test unified movers endpoint parameter validation."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    # Test valid range
    response = client.get("/api/portfolio/unified-movers?top_n=5")
    assert response.status_code == 200

    # Test too many movers (should fail validation)
    response = client.get("/api/portfolio/unified-movers?top_n=100")
    assert response.status_code == 422

    # Test negative movers (should fail validation)
    response = client.get("/api/portfolio/unified-movers?top_n=-1")
    assert response.status_code == 422
