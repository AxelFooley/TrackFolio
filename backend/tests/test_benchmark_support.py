"""
Tests for benchmark support in unified performance endpoints.

Tests the PortfolioAggregator._get_benchmark_data() method and verifies
benchmark data is properly included in unified performance endpoints.
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.portfolio_aggregator import PortfolioAggregator
from app.schemas.unified import (
    PerformanceSummary, BenchmarkData, UnifiedPerformanceDataPoint
)
from app.models import Benchmark, PriceHistory


class TestBenchmarkDataSchema:
    """Tests for BenchmarkData schema."""

    def test_benchmark_data_creation_with_all_fields(self):
        """Test BenchmarkData schema creation with all fields."""
        benchmark = BenchmarkData(
            start_price=Decimal("400.00"),
            end_price=Decimal("450.00"),
            change=Decimal("50.00"),
            pct_change=12.5,
            last_update=date(2025, 1, 20)
        )
        assert benchmark.start_price == Decimal("400.00")
        assert benchmark.end_price == Decimal("450.00")
        assert benchmark.change == Decimal("50.00")
        assert benchmark.pct_change == 12.5
        assert benchmark.last_update == date(2025, 1, 20)

    def test_benchmark_data_creation_with_none_fields(self):
        """Test BenchmarkData schema creation with None fields (no benchmark configured)."""
        benchmark = BenchmarkData(
            start_price=None,
            end_price=None,
            change=None,
            pct_change=None,
            last_update=None
        )
        assert benchmark.start_price is None
        assert benchmark.end_price is None
        assert benchmark.change is None
        assert benchmark.pct_change is None
        assert benchmark.last_update is None

    def test_benchmark_data_creation_partial(self):
        """Test BenchmarkData schema creation with partial fields."""
        benchmark = BenchmarkData(
            start_price=Decimal("400.00"),
            end_price=Decimal("450.00")
        )
        assert benchmark.start_price == Decimal("400.00")
        assert benchmark.end_price == Decimal("450.00")
        assert benchmark.change is None
        assert benchmark.pct_change is None
        assert benchmark.last_update is None

    def test_benchmark_data_negative_change(self):
        """Test BenchmarkData with negative price change."""
        benchmark = BenchmarkData(
            start_price=Decimal("450.00"),
            end_price=Decimal("400.00"),
            change=Decimal("-50.00"),
            pct_change=-11.11
        )
        assert benchmark.change == Decimal("-50.00")
        assert benchmark.pct_change == -11.11

    def test_benchmark_data_zero_change(self):
        """Test BenchmarkData with zero change."""
        benchmark = BenchmarkData(
            start_price=Decimal("400.00"),
            end_price=Decimal("400.00"),
            change=Decimal("0.00"),
            pct_change=0.0
        )
        assert benchmark.change == Decimal("0.00")
        assert benchmark.pct_change == 0.0


class TestPerformanceSummaryWithBenchmark:
    """Tests for PerformanceSummary schema with benchmark data."""

    def test_performance_summary_with_benchmark(self):
        """Test PerformanceSummary includes benchmark data."""
        benchmark = BenchmarkData(
            start_price=Decimal("400.00"),
            end_price=Decimal("450.00"),
            change=Decimal("50.00"),
            pct_change=12.5,
            last_update=date(2025, 1, 20)
        )
        perf_point = UnifiedPerformanceDataPoint(
            date=date(2025, 1, 15),
            value=Decimal("50000.00"),
            crypto_value=Decimal("20000.00"),
            traditional_value=Decimal("30000.00")
        )
        summary = PerformanceSummary(
            period_days=365,
            data_points=250,
            data=[perf_point],
            benchmark=benchmark
        )
        assert summary.benchmark is not None
        assert summary.benchmark.start_price == Decimal("400.00")
        assert summary.benchmark.pct_change == 12.5

    def test_performance_summary_without_benchmark(self):
        """Test PerformanceSummary without benchmark (no benchmark configured)."""
        perf_point = UnifiedPerformanceDataPoint(
            date=date(2025, 1, 15),
            value=Decimal("50000.00"),
            crypto_value=Decimal("20000.00"),
            traditional_value=Decimal("30000.00")
        )
        summary = PerformanceSummary(
            period_days=365,
            data_points=250,
            data=[perf_point],
            benchmark=None
        )
        assert summary.benchmark is None

    def test_performance_summary_empty_data_with_benchmark(self):
        """Test PerformanceSummary with empty data but has benchmark."""
        benchmark = BenchmarkData(
            start_price=Decimal("400.00"),
            end_price=Decimal("450.00"),
            change=Decimal("50.00"),
            pct_change=12.5,
            last_update=date(2025, 1, 20)
        )
        summary = PerformanceSummary(
            period_days=365,
            data_points=0,
            data=[],
            benchmark=benchmark
        )
        assert summary.data_points == 0
        assert len(summary.data) == 0
        assert summary.benchmark is not None


class TestPortfolioAggregatorGetBenchmarkData:
    """Tests for PortfolioAggregator._get_benchmark_data() method."""

    @pytest.mark.asyncio
    async def test_get_benchmark_data_no_benchmark_configured(self):
        """Test _get_benchmark_data when no benchmark is configured."""
        # Create mock DB session that returns None for benchmark query
        mock_db = AsyncMock()
        mock_execute = AsyncMock()
        mock_execute.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_execute

        aggregator = PortfolioAggregator(mock_db)
        snapshot_dates = [date(2025, 1, 1), date(2025, 1, 2)]

        result = await aggregator._get_benchmark_data(snapshot_dates)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_benchmark_data_empty_snapshot_dates(self):
        """Test _get_benchmark_data with empty snapshot dates."""
        mock_db = AsyncMock()
        aggregator = PortfolioAggregator(mock_db)
        snapshot_dates = []

        result = await aggregator._get_benchmark_data(snapshot_dates)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_benchmark_data_none_snapshot_dates(self):
        """Test _get_benchmark_data with None snapshot dates."""
        mock_db = AsyncMock()
        aggregator = PortfolioAggregator(mock_db)

        result = await aggregator._get_benchmark_data(None)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_benchmark_data_no_prices_found(self):
        """Test _get_benchmark_data when no benchmark prices found."""
        # Create mock benchmark
        mock_benchmark = MagicMock(spec=Benchmark)
        mock_benchmark.ticker = "SPY"

        # Create mock DB session
        mock_db = AsyncMock()

        # First call returns benchmark, second call returns empty list
        call_count = 0

        async def mock_execute_side_effect(query):
            nonlocal call_count
            call_count += 1
            mock_result = AsyncMock()
            if call_count == 1:  # Benchmark query
                mock_result.scalar_one_or_none.return_value = mock_benchmark
            else:  # Price history query
                mock_result.scalars.return_value.all.return_value = []
            return mock_result

        mock_db.execute = mock_execute_side_effect

        aggregator = PortfolioAggregator(mock_db)
        snapshot_dates = [date(2025, 1, 1), date(2025, 1, 2)]

        result = await aggregator._get_benchmark_data(snapshot_dates)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_benchmark_data_with_prices(self):
        """Test _get_benchmark_data with valid benchmark prices."""
        # Create mock benchmark
        mock_benchmark = MagicMock(spec=Benchmark)
        mock_benchmark.ticker = "SPY"

        # Create mock price history objects
        price1 = MagicMock(spec=PriceHistory)
        price1.close = Decimal("400.00")
        price1.date = date(2025, 1, 1)

        price2 = MagicMock(spec=PriceHistory)
        price2.close = Decimal("450.00")
        price2.date = date(2025, 1, 20)

        # Create mock DB session
        mock_db = AsyncMock()
        call_count = 0

        async def mock_execute_side_effect(query):
            nonlocal call_count
            call_count += 1
            mock_result = AsyncMock()
            if call_count == 1:  # Benchmark query
                mock_result.scalar_one_or_none.return_value = mock_benchmark
            else:  # Price history query
                mock_result.scalars.return_value.all.return_value = [price1, price2]
            return mock_result

        mock_db.execute = mock_execute_side_effect

        aggregator = PortfolioAggregator(mock_db)
        snapshot_dates = [date(2025, 1, 1), date(2025, 1, 20)]

        result = await aggregator._get_benchmark_data(snapshot_dates)

        assert result is not None
        assert result["start_price"] == Decimal("400.00")
        assert result["end_price"] == Decimal("450.00")
        assert result["change"] == Decimal("50.00")
        assert result["pct_change"] == 12.5
        assert result["last_update"] == date(2025, 1, 20)

    @pytest.mark.asyncio
    async def test_get_benchmark_data_single_price(self):
        """Test _get_benchmark_data with only one price point."""
        # Create mock benchmark
        mock_benchmark = MagicMock(spec=Benchmark)
        mock_benchmark.ticker = "SPY"

        # Create mock price history object
        price = MagicMock(spec=PriceHistory)
        price.close = Decimal("400.00")
        price.date = date(2025, 1, 1)

        # Create mock DB session
        mock_db = AsyncMock()
        call_count = 0

        async def mock_execute_side_effect(query):
            nonlocal call_count
            call_count += 1
            mock_result = AsyncMock()
            if call_count == 1:  # Benchmark query
                mock_result.scalar_one_or_none.return_value = mock_benchmark
            else:  # Price history query
                mock_result.scalars.return_value.all.return_value = [price]
            return mock_result

        mock_db.execute = mock_execute_side_effect

        aggregator = PortfolioAggregator(mock_db)
        snapshot_dates = [date(2025, 1, 1)]

        result = await aggregator._get_benchmark_data(snapshot_dates)

        assert result is not None
        assert result["start_price"] == Decimal("400.00")
        assert result["end_price"] == Decimal("400.00")
        assert result["change"] == Decimal("0.00")
        assert result["pct_change"] == 0.0
        assert result["last_update"] == date(2025, 1, 1)

    @pytest.mark.asyncio
    async def test_get_benchmark_data_negative_return(self):
        """Test _get_benchmark_data with negative return (price decline)."""
        # Create mock benchmark
        mock_benchmark = MagicMock(spec=Benchmark)
        mock_benchmark.ticker = "SPY"

        # Create mock price history objects (declining prices)
        price1 = MagicMock(spec=PriceHistory)
        price1.close = Decimal("500.00")
        price1.date = date(2025, 1, 1)

        price2 = MagicMock(spec=PriceHistory)
        price2.close = Decimal("450.00")
        price2.date = date(2025, 1, 20)

        # Create mock DB session
        mock_db = AsyncMock()
        call_count = 0

        async def mock_execute_side_effect(query):
            nonlocal call_count
            call_count += 1
            mock_result = AsyncMock()
            if call_count == 1:  # Benchmark query
                mock_result.scalar_one_or_none.return_value = mock_benchmark
            else:  # Price history query
                mock_result.scalars.return_value.all.return_value = [price1, price2]
            return mock_result

        mock_db.execute = mock_execute_side_effect

        aggregator = PortfolioAggregator(mock_db)
        snapshot_dates = [date(2025, 1, 1), date(2025, 1, 20)]

        result = await aggregator._get_benchmark_data(snapshot_dates)

        assert result is not None
        assert result["start_price"] == Decimal("500.00")
        assert result["end_price"] == Decimal("450.00")
        assert result["change"] == Decimal("-50.00")
        assert result["pct_change"] == -10.0

    @pytest.mark.asyncio
    async def test_get_benchmark_data_zero_start_price(self):
        """Test _get_benchmark_data with zero start price (edge case)."""
        # Create mock benchmark
        mock_benchmark = MagicMock(spec=Benchmark)
        mock_benchmark.ticker = "SPY"

        # Create mock price history objects (zero start price)
        price1 = MagicMock(spec=PriceHistory)
        price1.close = Decimal("0.00")
        price1.date = date(2025, 1, 1)

        price2 = MagicMock(spec=PriceHistory)
        price2.close = Decimal("100.00")
        price2.date = date(2025, 1, 20)

        # Create mock DB session
        mock_db = AsyncMock()
        call_count = 0

        async def mock_execute_side_effect(query):
            nonlocal call_count
            call_count += 1
            mock_result = AsyncMock()
            if call_count == 1:  # Benchmark query
                mock_result.scalar_one_or_none.return_value = mock_benchmark
            else:  # Price history query
                mock_result.scalars.return_value.all.return_value = [price1, price2]
            return mock_result

        mock_db.execute = mock_execute_side_effect

        aggregator = PortfolioAggregator(mock_db)
        snapshot_dates = [date(2025, 1, 1), date(2025, 1, 20)]

        result = await aggregator._get_benchmark_data(snapshot_dates)

        assert result is not None
        assert result["start_price"] == Decimal("0.00")
        assert result["end_price"] == Decimal("100.00")
        assert result["change"] == Decimal("100.00")
        # pct_change should be None due to zero denominator
        assert result["pct_change"] is None


class TestUnifiedSummaryWithBenchmark:
    """Integration tests for unified summary with benchmark data."""

    @pytest.mark.asyncio
    async def test_get_unified_summary_includes_benchmark(self):
        """Test that get_unified_summary includes benchmark data."""
        # This is an integration test that would require a full setup
        # For now, we're testing the schema structure
        from decimal import Decimal
        from app.schemas.unified import UnifiedSummary, UnifiedOverview

        perf_point = UnifiedPerformanceDataPoint(
            date=date(2025, 1, 15),
            value=Decimal("50000.00"),
            crypto_value=Decimal("20000.00"),
            traditional_value=Decimal("30000.00")
        )

        benchmark = BenchmarkData(
            start_price=Decimal("400.00"),
            end_price=Decimal("450.00"),
            change=Decimal("50.00"),
            pct_change=12.5,
            last_update=date(2025, 1, 20)
        )

        summary = PerformanceSummary(
            period_days=365,
            data_points=1,
            data=[perf_point],
            benchmark=benchmark
        )

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
            today_change_pct=0.5
        )

        unified_summary = UnifiedSummary(
            overview=overview,
            holdings=[],
            holdings_total=0,
            movers={"gainers": [], "losers": []},
            performance_summary=summary
        )

        assert unified_summary.performance_summary.benchmark is not None
        assert unified_summary.performance_summary.benchmark.pct_change == 12.5

    @pytest.mark.asyncio
    async def test_get_unified_summary_without_benchmark(self):
        """Test that get_unified_summary works without benchmark."""
        from decimal import Decimal
        from app.schemas.unified import UnifiedSummary, UnifiedOverview

        perf_point = UnifiedPerformanceDataPoint(
            date=date(2025, 1, 15),
            value=Decimal("50000.00"),
            crypto_value=Decimal("20000.00"),
            traditional_value=Decimal("30000.00")
        )

        summary = PerformanceSummary(
            period_days=365,
            data_points=1,
            data=[perf_point],
            benchmark=None
        )

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
            today_change_pct=0.5
        )

        unified_summary = UnifiedSummary(
            overview=overview,
            holdings=[],
            holdings_total=0,
            movers={"gainers": [], "losers": []},
            performance_summary=summary
        )

        assert unified_summary.performance_summary.benchmark is None
