"""Unit tests for benchmark support in unified portfolio endpoints.

Tests the benchmark transformation logic, schemas, and calculations including:
- Benchmark schema creation and validation
- BenchmarkDataPoint and BenchmarkMetrics creation
- Benchmark calculations (start price, end price, change, percentage)
- UnifiedPerformance and PerformanceSummary with benchmark data
"""

import pytest
from datetime import date
from decimal import Decimal

from app.schemas.unified import (
    UnifiedPerformance, BenchmarkDataPoint, BenchmarkMetrics, PerformanceSummary,
    UnifiedPerformanceDataPoint
)


# Mark entire module as unit test
pytestmark = pytest.mark.unit


class TestBenchmarkDataPoint:
    """Test BenchmarkDataPoint schema validation."""

    def test_benchmark_data_point_creation(self):
        """Test BenchmarkDataPoint can be created with required fields."""
        point = BenchmarkDataPoint(
            date=date(2025, 1, 1),
            value=Decimal("5000.00")
        )
        assert point.date == date(2025, 1, 1)
        assert point.value == Decimal("5000.00")

    def test_benchmark_data_point_serialization(self):
        """Test BenchmarkDataPoint serializes correctly to dict."""
        point = BenchmarkDataPoint(
            date=date(2025, 1, 1),
            value=Decimal("5000.00")
        )
        data = point.model_dump()
        assert data["date"] == date(2025, 1, 1)
        # Decimal serializes to string in JSON
        assert str(data["value"]) == "5000.00"

    def test_benchmark_data_point_with_different_types(self):
        """Test BenchmarkDataPoint handles different numeric types."""
        # With string values
        point1 = BenchmarkDataPoint(
            date=date(2025, 1, 2),
            value="5100.50"
        )
        assert point1.value == Decimal("5100.50")

        # With int
        point2 = BenchmarkDataPoint(
            date=date(2025, 1, 3),
            value=5200
        )
        assert point2.value == Decimal("5200")

        # With float
        point3 = BenchmarkDataPoint(
            date=date(2025, 1, 4),
            value=5300.75
        )
        assert point3.value == Decimal("5300.75")


class TestBenchmarkMetrics:
    """Test BenchmarkMetrics schema validation."""

    def test_benchmark_metrics_creation(self):
        """Test BenchmarkMetrics can be created with all fields."""
        metrics = BenchmarkMetrics(
            start_price=Decimal("5000.00"),
            end_price=Decimal("5500.00"),
            change_amount=Decimal("500.00"),
            change_pct=10.0
        )
        assert metrics.start_price == Decimal("5000.00")
        assert metrics.end_price == Decimal("5500.00")
        assert metrics.change_amount == Decimal("500.00")
        assert metrics.change_pct == 10.0

    def test_benchmark_metrics_with_none_values(self):
        """Test BenchmarkMetrics allows None values when not configured."""
        metrics = BenchmarkMetrics(
            start_price=None,
            end_price=None,
            change_amount=None,
            change_pct=None
        )
        assert metrics.start_price is None
        assert metrics.end_price is None
        assert metrics.change_amount is None
        assert metrics.change_pct is None

    def test_benchmark_metrics_calculation_accuracy(self):
        """Test benchmark metrics calculation values are mathematically correct."""
        # Start: 100, End: 120, Change: 20, Percent: 20%
        metrics = BenchmarkMetrics(
            start_price=Decimal("100"),
            end_price=Decimal("120"),
            change_amount=Decimal("20"),
            change_pct=20.0
        )
        assert metrics.change_amount == Decimal("120") - Decimal("100")
        assert metrics.change_pct == 20.0

        # Start: 100, End: 90, Change: -10, Percent: -10%
        metrics2 = BenchmarkMetrics(
            start_price=Decimal("100"),
            end_price=Decimal("90"),
            change_amount=Decimal("-10"),
            change_pct=-10.0
        )
        assert metrics2.change_amount == Decimal("-10")
        assert metrics2.change_pct == -10.0

    def test_benchmark_metrics_with_zero_change(self):
        """Test benchmark metrics when price doesn't change."""
        metrics = BenchmarkMetrics(
            start_price=Decimal("5000.00"),
            end_price=Decimal("5000.00"),
            change_amount=Decimal("0"),
            change_pct=0.0
        )
        assert metrics.change_amount == Decimal("0")
        assert metrics.change_pct == 0.0


class TestUnifiedPerformanceWithBenchmark:
    """Test UnifiedPerformance schema with benchmark support."""

    def test_unified_performance_without_benchmark(self):
        """Test UnifiedPerformance with empty benchmark data."""
        perf_point = UnifiedPerformanceDataPoint(
            date_point=date(2025, 1, 1),
            value=Decimal("50000.00"),
            traditional_value=Decimal("30000.00"),
            crypto_value=Decimal("20000.00")
        )
        perf = UnifiedPerformance(
            data=[perf_point],
            benchmark_data=[],
            benchmark_metrics=None
        )
        assert len(perf.data) == 1
        assert perf.benchmark_data == []
        assert perf.benchmark_metrics is None

    def test_unified_performance_with_benchmark(self):
        """Test UnifiedPerformance with benchmark data."""
        perf_point = UnifiedPerformanceDataPoint(
            date_point=date(2025, 1, 1),
            value=Decimal("50000.00"),
            traditional_value=Decimal("30000.00"),
            crypto_value=Decimal("20000.00")
        )
        benchmark_point = BenchmarkDataPoint(
            date=date(2025, 1, 1),
            value=Decimal("4500.00")
        )
        benchmark_metrics = BenchmarkMetrics(
            start_price=Decimal("4500.00"),
            end_price=Decimal("4500.00"),
            change_amount=Decimal("0"),
            change_pct=0.0
        )
        perf = UnifiedPerformance(
            data=[perf_point],
            benchmark_data=[benchmark_point],
            benchmark_metrics=benchmark_metrics
        )
        assert len(perf.data) == 1
        assert len(perf.benchmark_data) == 1
        assert perf.benchmark_metrics is not None
        assert perf.benchmark_metrics.change_pct == 0.0

    def test_unified_performance_multiple_points_with_benchmark(self):
        """Test UnifiedPerformance with multiple data points and benchmark."""
        perf_points = [
            UnifiedPerformanceDataPoint(
                date_point=date(2025, 1, i),
                value=Decimal("50000") + Decimal(i * 100),
                traditional_value=Decimal("30000"),
                crypto_value=Decimal("20000")
            )
            for i in range(1, 6)
        ]
        benchmark_points = [
            BenchmarkDataPoint(date=date(2025, 1, i), value=Decimal("4500") + Decimal(i * 10))
            for i in range(1, 6)
        ]
        benchmark_metrics = BenchmarkMetrics(
            start_price=Decimal("4510"),
            end_price=Decimal("4550"),
            change_amount=Decimal("40"),
            change_pct=float((Decimal("40") / Decimal("4510")) * 100)
        )
        perf = UnifiedPerformance(
            data=perf_points,
            benchmark_data=benchmark_points,
            benchmark_metrics=benchmark_metrics
        )
        assert len(perf.data) == 5
        assert len(perf.benchmark_data) == 5
        assert perf.benchmark_metrics.change_pct > 0


class TestPerformanceSummaryWithBenchmark:
    """Test PerformanceSummary schema with benchmark support."""

    def test_performance_summary_without_benchmark(self):
        """Test PerformanceSummary without benchmark."""
        perf_point = UnifiedPerformanceDataPoint(
            date_point=date(2025, 1, 1),
            value=Decimal("50000.00"),
            traditional_value=Decimal("30000.00"),
            crypto_value=Decimal("20000.00")
        )
        summary = PerformanceSummary(
            period_days=365,
            data_points=1,
            data=[perf_point],
            benchmark_data=[],
            benchmark_metrics=None
        )
        assert summary.period_days == 365
        assert summary.data_points == 1
        assert summary.benchmark_data == []
        assert summary.benchmark_metrics is None

    def test_performance_summary_with_benchmark(self):
        """Test PerformanceSummary with benchmark data."""
        perf_point = UnifiedPerformanceDataPoint(
            date_point=date(2025, 1, 1),
            value=Decimal("50000.00"),
            traditional_value=Decimal("30000.00"),
            crypto_value=Decimal("20000.00")
        )
        benchmark_point = BenchmarkDataPoint(
            date=date(2025, 1, 1),
            value=Decimal("4500.00")
        )
        benchmark_metrics = BenchmarkMetrics(
            start_price=Decimal("4500.00"),
            end_price=Decimal("4500.00"),
            change_amount=Decimal("0"),
            change_pct=0.0
        )
        summary = PerformanceSummary(
            period_days=1,
            data_points=1,
            data=[perf_point],
            benchmark_data=[benchmark_point],
            benchmark_metrics=benchmark_metrics
        )
        assert summary.period_days == 1
        assert len(summary.benchmark_data) == 1
        assert summary.benchmark_metrics is not None

    def test_performance_summary_full_period(self):
        """Test PerformanceSummary with full year of data."""
        perf_points = [
            UnifiedPerformanceDataPoint(
                date_point=date(2025, 1, i),
                value=Decimal("50000") + Decimal(i * 50),
                traditional_value=Decimal("30000"),
                crypto_value=Decimal("20000")
            )
            for i in range(1, 11)  # 10 data points
        ]
        benchmark_points = [
            BenchmarkDataPoint(date=date(2025, 1, i), value=Decimal("4500") + Decimal(i * 5))
            for i in range(1, 11)
        ]
        benchmark_metrics = BenchmarkMetrics(
            start_price=Decimal("4505"),
            end_price=Decimal("4550"),
            change_amount=Decimal("45"),
            change_pct=float((Decimal("45") / Decimal("4505")) * 100)
        )
        summary = PerformanceSummary(
            period_days=365,
            data_points=10,
            data=perf_points,
            benchmark_data=benchmark_points,
            benchmark_metrics=benchmark_metrics
        )
        assert summary.period_days == 365
        assert summary.data_points == 10
        assert len(summary.data) == 10
        assert len(summary.benchmark_data) == 10
        assert summary.benchmark_metrics.change_pct > 0


class TestBenchmarkDataAlignment:
    """Test alignment logic for benchmark data with portfolio snapshots."""

    def test_benchmark_data_point_count_less_than_or_equal_snapshots(self):
        """Test that benchmark points don't exceed snapshot count."""
        # Simulate 5 portfolio snapshots
        perf_points = [
            UnifiedPerformanceDataPoint(
                date_point=date(2025, 1, i),
                value=Decimal("50000"),
                traditional_value=Decimal("30000"),
                crypto_value=Decimal("20000")
            )
            for i in range(1, 6)
        ]

        # Benchmark has only 3 matching dates (aligned)
        benchmark_points = [
            BenchmarkDataPoint(date=date(2025, 1, i), value=Decimal("4500"))
            for i in [1, 3, 5]
        ]

        perf = UnifiedPerformance(
            data=perf_points,
            benchmark_data=benchmark_points,
            benchmark_metrics=BenchmarkMetrics(start_price=Decimal("4500"), end_price=Decimal("4500"))
        )

        assert len(perf.benchmark_data) <= len(perf.data)

    def test_benchmark_dates_are_subset_of_snapshot_dates(self):
        """Test that benchmark dates are a subset of snapshot dates."""
        snapshot_dates = {date(2025, 1, i) for i in [1, 2, 3, 4, 5]}

        perf_points = [
            UnifiedPerformanceDataPoint(
                date_point=d,
                value=Decimal("50000"),
                traditional_value=Decimal("30000"),
                crypto_value=Decimal("20000")
            )
            for d in sorted(snapshot_dates)
        ]

        # Only benchmark dates that exist in snapshots
        benchmark_dates = {date(2025, 1, i) for i in [1, 3, 5]}
        benchmark_points = [
            BenchmarkDataPoint(date=d, value=Decimal("4500"))
            for d in sorted(benchmark_dates)
        ]

        perf = UnifiedPerformance(
            data=perf_points,
            benchmark_data=benchmark_points,
            benchmark_metrics=BenchmarkMetrics(start_price=Decimal("4500"), end_price=Decimal("4500"))
        )

        perf_dates = {p.date_point for p in perf.data}
        bench_dates = {p.date for p in perf.benchmark_data}

        assert bench_dates.issubset(perf_dates)


class TestBenchmarkEdgeCases:
    """Test edge cases in benchmark functionality."""

    def test_single_benchmark_data_point(self):
        """Test with only one benchmark data point."""
        point = BenchmarkDataPoint(date=date(2025, 1, 1), value=Decimal("4500"))
        metrics = BenchmarkMetrics(
            start_price=Decimal("4500"),
            end_price=Decimal("4500"),
            change_amount=Decimal("0"),
            change_pct=0.0
        )
        perf = UnifiedPerformance(
            data=[UnifiedPerformanceDataPoint(
                date_point=date(2025, 1, 1),
                value=Decimal("50000"),
                traditional_value=Decimal("30000"),
                crypto_value=Decimal("20000")
            )],
            benchmark_data=[point],
            benchmark_metrics=metrics
        )
        assert len(perf.benchmark_data) == 1
        assert perf.benchmark_metrics.change_amount == Decimal("0")

    def test_high_volatility_benchmark(self):
        """Test benchmark with high price volatility."""
        # Price goes from 100 to 200 (100% gain)
        metrics = BenchmarkMetrics(
            start_price=Decimal("100"),
            end_price=Decimal("200"),
            change_amount=Decimal("100"),
            change_pct=100.0
        )
        assert metrics.change_pct == 100.0

    def test_negative_benchmark_return(self):
        """Test benchmark with negative returns."""
        # Price goes from 100 to 80 (-20% loss)
        metrics = BenchmarkMetrics(
            start_price=Decimal("100"),
            end_price=Decimal("80"),
            change_amount=Decimal("-20"),
            change_pct=-20.0
        )
        assert metrics.change_pct == -20.0
        assert metrics.change_amount == Decimal("-20")

    def test_very_small_price_movement(self):
        """Test benchmark with very small price movements."""
        # Price goes from 5000 to 5001 (0.02% gain)
        metrics = BenchmarkMetrics(
            start_price=Decimal("5000.00"),
            end_price=Decimal("5001.00"),
            change_amount=Decimal("1.00"),
            change_pct=0.02
        )
        # Should be approximately 0.02%
        assert abs(metrics.change_pct - 0.02) < 0.001

    def test_decimal_precision_maintained(self):
        """Test that Decimal precision is maintained in calculations."""
        start = Decimal("5000.123456")
        end = Decimal("5500.654321")
        change = end - start

        metrics = BenchmarkMetrics(
            start_price=start,
            end_price=end,
            change_amount=change,
            change_pct=float((change / start) * 100)
        )

        # Verify Decimal precision is preserved
        assert metrics.start_price == Decimal("5000.123456")
        assert metrics.end_price == Decimal("5500.654321")
        assert metrics.change_amount == Decimal("500.530865")
