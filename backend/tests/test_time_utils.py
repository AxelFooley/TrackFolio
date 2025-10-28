"""Tests for time_utils module.

Comprehensive tests for date range parsing, date calculations, and formatting utilities.
"""

import pytest
from datetime import date, timedelta, datetime
from fastapi import HTTPException

from app.utils.time_utils import (
    parse_time_range,
    get_date_range_description,
    get_last_n_days,
    get_year_to_date,
    parse_date_string,
)


class TestParseTimeRange:
    """Tests for parse_time_range function."""

    def test_parse_one_day(self):
        """Test parsing '1D' range."""
        start, end = parse_time_range("1D")
        today = date.today()
        assert end == today
        assert start == today - timedelta(days=1)

    def test_parse_one_week(self):
        """Test parsing '1W' range."""
        start, end = parse_time_range("1W")
        today = date.today()
        assert end == today
        assert start == today - timedelta(days=7)

    def test_parse_one_month(self):
        """Test parsing '1M' range."""
        start, end = parse_time_range("1M")
        today = date.today()
        assert end == today
        assert start == today - timedelta(days=30)

    def test_parse_three_months(self):
        """Test parsing '3M' range."""
        start, end = parse_time_range("3M")
        today = date.today()
        assert end == today
        assert start == today - timedelta(days=90)

    def test_parse_six_months(self):
        """Test parsing '6M' range."""
        start, end = parse_time_range("6M")
        today = date.today()
        assert end == today
        assert start == today - timedelta(days=180)

    def test_parse_one_year(self):
        """Test parsing '1Y' range."""
        start, end = parse_time_range("1Y")
        today = date.today()
        assert end == today
        assert start == today - timedelta(days=365)

    def test_parse_year_to_date(self):
        """Test parsing 'YTD' range."""
        start, end = parse_time_range("YTD")
        today = date.today()
        assert end == today
        assert start == date(today.year, 1, 1)

    def test_parse_all_range(self):
        """Test parsing 'ALL' range returns None for both dates."""
        start, end = parse_time_range("ALL")
        assert start is None
        assert end is None

    def test_parse_invalid_range(self):
        """Test parsing invalid range raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            parse_time_range("INVALID")
        assert exc_info.value.status_code == 400
        assert "Invalid range parameter" in exc_info.value.detail

    def test_parse_case_sensitive(self):
        """Test that range parsing is case-sensitive."""
        with pytest.raises(HTTPException):
            parse_time_range("1d")  # lowercase should fail

        with pytest.raises(HTTPException):
            parse_time_range("ytd")  # lowercase should fail

    def test_parse_empty_string(self):
        """Test parsing empty string raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            parse_time_range("")
        assert exc_info.value.status_code == 400

    def test_ytd_is_year_start_to_today(self):
        """Test YTD correctly calculates year to date."""
        start, end = parse_time_range("YTD")
        assert start.month == 1
        assert start.day == 1
        assert end == date.today()


class TestGetDateRangeDescription:
    """Tests for get_date_range_description function."""

    def test_description_with_both_dates(self):
        """Test description when both start and end dates are provided."""
        start = date(2024, 1, 15)
        end = date(2024, 12, 31)
        desc = get_date_range_description(start, end)
        assert "Jan 15, 2024" in desc
        assert "Dec 31, 2024" in desc
        assert " to " in desc

    def test_description_with_start_date_only(self):
        """Test description when only start date is provided."""
        start = date(2024, 1, 15)
        desc = get_date_range_description(start, None)
        assert "From" in desc
        assert "Jan 15, 2024" in desc

    def test_description_with_end_date_only(self):
        """Test description when only end date is provided."""
        end = date(2024, 12, 31)
        desc = get_date_range_description(None, end)
        assert "Until" in desc
        assert "Dec 31, 2024" in desc

    def test_description_with_no_dates(self):
        """Test description when both dates are None."""
        desc = get_date_range_description(None, None)
        assert desc == "All time"

    def test_description_formatting(self):
        """Test date formatting in description."""
        start = date(2024, 1, 1)
        end = date(2024, 1, 31)
        desc = get_date_range_description(start, end)
        # Should be formatted as "Mon DD, YYYY"
        assert "Jan" in desc
        assert "2024" in desc


class TestGetLastNDays:
    """Tests for get_last_n_days function."""

    def test_get_last_7_days(self):
        """Test getting last 7 days."""
        start, end = get_last_n_days(7)
        today = date.today()
        assert end == today
        assert start == today - timedelta(days=7)

    def test_get_last_30_days(self):
        """Test getting last 30 days."""
        start, end = get_last_n_days(30)
        today = date.today()
        assert end == today
        assert start == today - timedelta(days=30)

    def test_get_last_1_day(self):
        """Test getting last 1 day."""
        start, end = get_last_n_days(1)
        today = date.today()
        assert end == today
        assert start == today - timedelta(days=1)

    def test_get_last_365_days(self):
        """Test getting last 365 days."""
        start, end = get_last_n_days(365)
        today = date.today()
        assert end == today
        assert start == today - timedelta(days=365)

    def test_invalid_zero_days(self):
        """Test that zero days raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            get_last_n_days(0)
        assert "must be positive" in str(exc_info.value)

    def test_invalid_negative_days(self):
        """Test that negative days raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            get_last_n_days(-5)
        assert "must be positive" in str(exc_info.value)

    def test_large_number_of_days(self):
        """Test getting a large number of days."""
        start, end = get_last_n_days(3650)  # ~10 years
        today = date.today()
        assert end == today
        assert start == today - timedelta(days=3650)


class TestGetYearToDate:
    """Tests for get_year_to_date function."""

    def test_ytd_current_year(self):
        """Test year-to-date for current year."""
        start, end = get_year_to_date()
        today = date.today()
        assert end == today
        assert start == date(today.year, 1, 1)

    def test_ytd_start_is_january_1(self):
        """Test that YTD start is always January 1."""
        start, end = get_year_to_date()
        assert start.month == 1
        assert start.day == 1

    def test_ytd_end_is_today(self):
        """Test that YTD end is always today."""
        start, end = get_year_to_date()
        assert end == date.today()

    def test_ytd_january_1(self):
        """Test YTD when today is January 1 (edge case)."""
        # This test may pass or fail depending on when it's run
        # but the function should handle it correctly
        start, end = get_year_to_date()
        assert start <= end


class TestParseDateString:
    """Tests for parse_date_string function."""

    def test_parse_iso_format(self):
        """Test parsing ISO format date (YYYY-MM-DD)."""
        result = parse_date_string("2024-01-15")
        assert result == date(2024, 1, 15)

    def test_parse_with_custom_format(self):
        """Test parsing with custom format string."""
        result = parse_date_string("01/15/2024", "%m/%d/%Y")
        assert result == date(2024, 1, 15)

    def test_parse_different_custom_format(self):
        """Test parsing with another custom format."""
        result = parse_date_string("15-01-2024", "%d-%m-%Y")
        assert result == date(2024, 1, 15)

    def test_parse_invalid_date_string(self):
        """Test parsing invalid date string raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            parse_date_string("invalid-date")
        assert exc_info.value.status_code == 400
        assert "Invalid date format" in exc_info.value.detail

    def test_parse_wrong_format(self):
        """Test parsing with wrong format raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            parse_date_string("2024-01-15", "%m/%d/%Y")
        assert exc_info.value.status_code == 400

    def test_parse_invalid_month(self):
        """Test parsing with invalid month raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            parse_date_string("2024-13-15")  # Month 13 is invalid
        assert exc_info.value.status_code == 400

    def test_parse_invalid_day(self):
        """Test parsing with invalid day raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            parse_date_string("2024-02-30")  # Feb 30 is invalid
        assert exc_info.value.status_code == 400

    def test_parse_leap_year_date(self):
        """Test parsing leap year February 29."""
        result = parse_date_string("2024-02-29")  # 2024 is a leap year
        assert result == date(2024, 2, 29)

    def test_parse_non_leap_year_feb_29(self):
        """Test parsing February 29 in non-leap year raises HTTPException."""
        with pytest.raises(HTTPException):
            parse_date_string("2023-02-29")  # 2023 is not a leap year

    def test_parse_empty_string(self):
        """Test parsing empty string raises HTTPException."""
        with pytest.raises(HTTPException) as exc_info:
            parse_date_string("")
        assert exc_info.value.status_code == 400

    def test_parse_various_dates(self):
        """Test parsing various valid dates."""
        test_cases = [
            ("2024-01-01", date(2024, 1, 1)),
            ("2024-12-31", date(2024, 12, 31)),
            ("2000-06-15", date(2000, 6, 15)),
        ]
        for date_str, expected in test_cases:
            result = parse_date_string(date_str)
            assert result == expected


class TestIntegration:
    """Integration tests combining multiple utilities."""

    def test_parse_time_range_and_get_description(self):
        """Test parsing time range and getting description."""
        start, end = parse_time_range("1M")
        description = get_date_range_description(start, end)
        assert "to" in description
        assert start is not None
        assert end is not None

    def test_get_last_n_days_and_get_description(self):
        """Test getting last N days and getting description."""
        start, end = get_last_n_days(30)
        description = get_date_range_description(start, end)
        assert description is not None
        assert "to" in description

    def test_year_to_date_description(self):
        """Test YTD date range description."""
        start, end = get_year_to_date()
        description = get_date_range_description(start, end)
        today = date.today()
        assert str(today.year) in description

    def test_all_ranges_return_valid_descriptions(self):
        """Test that all time range presets produce valid descriptions."""
        ranges = ["1D", "1W", "1M", "3M", "6M", "1Y", "YTD"]
        for range_str in ranges:
            start, end = parse_time_range(range_str)
            description = get_date_range_description(start, end)
            assert description is not None
            assert len(description) > 0

    def test_parse_date_and_use_in_range(self):
        """Test parsing a date and using it in a range description."""
        parsed = parse_date_string("2024-01-15")
        today = date.today()
        description = get_date_range_description(parsed, today)
        assert "Jan 15, 2024" in description


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_parse_time_range_leap_year_ytd(self):
        """Test YTD parsing in leap year."""
        start, end = parse_time_range("YTD")
        # Start should always be Jan 1, even in leap years
        assert start.month == 1
        assert start.day == 1

    def test_last_n_days_spans_month_boundary(self):
        """Test that last N days correctly spans month boundaries."""
        start, end = get_last_n_days(31)
        # Should span at least one month boundary
        assert (end.month != start.month) or (end.year != start.year)

    def test_description_same_day(self):
        """Test description when start and end are the same day."""
        same_day = date.today()
        description = get_date_range_description(same_day, same_day)
        assert same_day.strftime("%b %d, %Y") in description

    def test_date_string_with_leading_zeros(self):
        """Test parsing dates with leading zeros."""
        result = parse_date_string("2024-01-05")
        assert result == date(2024, 1, 5)

    def test_very_old_date(self):
        """Test parsing very old dates."""
        result = parse_date_string("1900-01-01")
        assert result == date(1900, 1, 1)

    def test_future_date(self):
        """Test parsing future dates."""
        future = date.today() + timedelta(days=365)
        date_str = future.strftime("%Y-%m-%d")
        result = parse_date_string(date_str)
        assert result == future


class TestGetLastNDaysBoundary:
    """Comprehensive boundary tests for get_last_n_days function."""

    def test_last_1_day_semantics(self):
        """Test that get_last_n_days(1) returns yesterday (1 day of past data)."""
        start, end = get_last_n_days(1)
        today = date.today()
        # Semantics: "last 1 day" = yesterday to today [yesterday, today)
        assert start == today - timedelta(days=1)
        assert end == today
        assert (end - start).days == 1

    def test_last_1_day_date_difference(self):
        """Test that get_last_n_days(1) spans 1 day (yesterday to today)."""
        start, end = get_last_n_days(1)
        # Yesterday to today is a 1-day span
        assert (end - start).days == 1

    def test_last_2_days_semantics(self):
        """Test that get_last_n_days(2) returns 2 days of historical data."""
        start, end = get_last_n_days(2)
        today = date.today()
        # Semantics: "last 2 days" = 2 days ago to today [2d ago, today)
        assert end == today
        assert start == today - timedelta(days=2)
        # Verify the date difference
        assert (end - start).days == 2

    def test_last_n_days_always_ends_on_today(self):
        """Test that end_date is always today."""
        for n in [1, 7, 30, 90, 365]:
            start, end = get_last_n_days(n)
            assert end == date.today()

    def test_last_n_days_start_before_end(self):
        """Test that start_date is always before end_date."""
        for n in [1, 2, 7, 30, 365]:
            start, end = get_last_n_days(n)
            assert start < end

    def test_last_n_days_correct_calculation(self):
        """Test that start_date = today - timedelta(days=n)."""
        for n in [1, 7, 30, 90, 180, 365]:
            start, end = get_last_n_days(n)
            expected_start = date.today() - timedelta(days=n)
            assert start == expected_start

    def test_last_n_days_spans_correct_interval(self):
        """Test that the interval spans exactly n days."""
        for n in [1, 7, 30, 90, 365]:
            start, end = get_last_n_days(n)
            # The difference should be exactly n days
            assert (end - start).days == n

    def test_last_n_days_spans_month_boundary(self):
        """Test that last N days correctly spans month boundaries."""
        # 31-day range should definitely cross month boundary
        start, end = get_last_n_days(31)
        # Verify month difference (may span 1 or 2 months)
        assert (end.month != start.month) or (end.year != start.year)

    def test_last_n_days_spans_year_boundary(self):
        """Test that last N days can span year boundary."""
        # 365-day range from today can span year boundary if run near year-end
        start, end = get_last_n_days(365)
        assert end == date.today()
        assert (end - start).days == 365

    def test_last_n_days_large_number(self):
        """Test get_last_n_days with large number of days."""
        start, end = get_last_n_days(3650)  # ~10 years
        assert end == date.today()
        assert (end - start).days == 3650
        assert start < end


class TestParseTimeRangeBoundary:
    """Comprehensive boundary tests for parse_time_range function."""

    def test_parse_1d_returns_1_day_data(self):
        """Test that '1D' returns 1 day of historical data."""
        start, end = parse_time_range("1D")
        today = date.today()
        # "1D" = yesterday to today [yesterday, today) = 1 day of data
        assert end == today
        assert start == today - timedelta(days=1)
        assert (end - start).days == 1

    def test_parse_1w_is_7_day_range(self):
        """Test that '1W' returns a 7-day range."""
        start, end = parse_time_range("1W")
        # Verify it's exactly 7 days
        assert (end - start).days == 7

    def test_all_ranges_end_on_today(self):
        """Test that all range types end on today's date."""
        today = date.today()
        ranges = ["1D", "1W", "1M", "3M", "6M", "1Y", "YTD"]
        for range_str in ranges:
            start, end = parse_time_range(range_str)
            assert end == today, f"Range {range_str} should end on today"

    def test_all_ranges_start_before_or_equal_end(self):
        """Test that start_date is always <= end_date."""
        ranges = ["1D", "1W", "1M", "3M", "6M", "1Y", "YTD"]
        for range_str in ranges:
            start, end = parse_time_range(range_str)
            assert start <= end, f"Range {range_str} has start > end"

    def test_ytd_when_jan_1(self):
        """Test YTD edge case: when today is January 1."""
        # This test uses current data, but verifies the logic
        start, end = parse_time_range("YTD")
        # YTD should always span from Jan 1 to today
        assert start.month == 1
        assert start.day == 1
        assert end == date.today()
        # On Jan 1, start should equal end
        if date.today().month == 1 and date.today().day == 1:
            assert start == end

    def test_all_ranges_produce_valid_tuples(self):
        """Test that all range types produce valid (start, end) tuples."""
        ranges = ["1D", "1W", "1M", "3M", "6M", "1Y", "YTD"]
        for range_str in ranges:
            start, end = parse_time_range(range_str)
            assert isinstance(start, date), f"Range {range_str} start is not a date"
            assert isinstance(end, date), f"Range {range_str} end is not a date"
            assert start <= end, f"Range {range_str} start > end"

    def test_parse_all_returns_none_tuple(self):
        """Test that 'ALL' range returns (None, None)."""
        start, end = parse_time_range("ALL")
        assert start is None
        assert end is None

    def test_range_accuracy_1m(self):
        """Test that '1M' is exactly 30 days."""
        start, end = parse_time_range("1M")
        assert (end - start).days == 30

    def test_range_accuracy_3m(self):
        """Test that '3M' is exactly 90 days."""
        start, end = parse_time_range("3M")
        assert (end - start).days == 90

    def test_range_accuracy_6m(self):
        """Test that '6M' is exactly 180 days."""
        start, end = parse_time_range("6M")
        assert (end - start).days == 180

    def test_range_accuracy_1y(self):
        """Test that '1Y' is exactly 365 days."""
        start, end = parse_time_range("1Y")
        assert (end - start).days == 365


class TestParseDateStringBoundary:
    """Comprehensive boundary tests for parse_date_string function."""

    def test_century_boundary_1999(self):
        """Test parsing century boundary date (Dec 31, 1999)."""
        result = parse_date_string("1999-12-31")
        assert result == date(1999, 12, 31)

    def test_century_boundary_2000(self):
        """Test parsing century boundary date (Jan 1, 2000)."""
        result = parse_date_string("2000-01-01")
        assert result == date(2000, 1, 1)

    def test_month_boundary_january(self):
        """Test parsing first day of January."""
        result = parse_date_string("2024-01-01")
        assert result == date(2024, 1, 1)

    def test_month_boundary_january_31(self):
        """Test parsing last day of January."""
        result = parse_date_string("2024-01-31")
        assert result == date(2024, 1, 31)

    def test_month_boundary_february_leap_year(self):
        """Test parsing last day of February in leap year."""
        result = parse_date_string("2024-02-29")
        assert result == date(2024, 2, 29)

    def test_month_boundary_february_non_leap(self):
        """Test parsing Feb 28 in non-leap year."""
        result = parse_date_string("2023-02-28")
        assert result == date(2023, 2, 28)

    def test_month_boundary_december_31(self):
        """Test parsing last day of year (Dec 31)."""
        result = parse_date_string("2024-12-31")
        assert result == date(2024, 12, 31)

    def test_minimum_valid_date(self):
        """Test parsing minimum valid date (0001-01-01)."""
        result = parse_date_string("0001-01-01")
        assert result == date(1, 1, 1)

    def test_maximum_valid_date(self):
        """Test parsing maximum valid date (9999-12-31)."""
        result = parse_date_string("9999-12-31")
        assert result == date(9999, 12, 31)

    def test_single_digit_months_with_leading_zeros(self):
        """Test parsing single-digit months with leading zeros."""
        test_cases = [
            ("2024-01-15", date(2024, 1, 15)),
            ("2024-02-15", date(2024, 2, 15)),
            ("2024-09-15", date(2024, 9, 15)),
        ]
        for date_str, expected in test_cases:
            result = parse_date_string(date_str)
            assert result == expected

    def test_single_digit_days_with_leading_zeros(self):
        """Test parsing single-digit days with leading zeros."""
        test_cases = [
            ("2024-01-01", date(2024, 1, 1)),
            ("2024-01-05", date(2024, 1, 5)),
            ("2024-01-09", date(2024, 1, 9)),
        ]
        for date_str, expected in test_cases:
            result = parse_date_string(date_str)
            assert result == expected

    def test_invalid_month_13(self):
        """Test that month 13 is rejected."""
        with pytest.raises(HTTPException):
            parse_date_string("2024-13-01")

    def test_invalid_month_0(self):
        """Test that month 0 is rejected."""
        with pytest.raises(HTTPException):
            parse_date_string("2024-00-01")

    def test_invalid_day_32(self):
        """Test that day 32 is rejected."""
        with pytest.raises(HTTPException):
            parse_date_string("2024-01-32")

    def test_invalid_day_0(self):
        """Test that day 0 is rejected."""
        with pytest.raises(HTTPException):
            parse_date_string("2024-01-00")

    def test_invalid_february_30(self):
        """Test that Feb 30 is rejected."""
        with pytest.raises(HTTPException):
            parse_date_string("2024-02-30")

    def test_leap_year_2024(self):
        """Test Feb 29 in leap year 2024."""
        result = parse_date_string("2024-02-29")
        assert result == date(2024, 2, 29)

    def test_leap_year_2000(self):
        """Test Feb 29 in leap year 2000."""
        result = parse_date_string("2000-02-29")
        assert result == date(2000, 2, 29)

    def test_non_leap_year_2023(self):
        """Test that Feb 29 is rejected in non-leap year 2023."""
        with pytest.raises(HTTPException):
            parse_date_string("2023-02-29")

    def test_non_leap_year_2100(self):
        """Test that Feb 29 is rejected in non-leap year 2100."""
        # 2100 is not a leap year (divisible by 100 but not by 400)
        with pytest.raises(HTTPException):
            parse_date_string("2100-02-29")

    def test_leap_year_2400(self):
        """Test Feb 29 in leap year 2400."""
        result = parse_date_string("2400-02-29")
        assert result == date(2400, 2, 29)

    def test_all_30_day_months(self):
        """Test parsing last day of 30-day months."""
        months_30 = [4, 6, 9, 11]  # April, June, Sept, Nov
        for month in months_30:
            date_str = f"2024-{month:02d}-30"
            result = parse_date_string(date_str)
            assert result.month == month
            assert result.day == 30

    def test_all_31_day_months(self):
        """Test parsing last day of 31-day months."""
        months_31 = [1, 3, 5, 7, 8, 10, 12]
        for month in months_31:
            date_str = f"2024-{month:02d}-31"
            result = parse_date_string(date_str)
            assert result.month == month
            assert result.day == 31

    def test_various_formats(self):
        """Test parsing various valid date formats."""
        test_cases = [
            # (date_str, format, expected)
            ("2024-01-15", "%Y-%m-%d", date(2024, 1, 15)),
            ("01/15/2024", "%m/%d/%Y", date(2024, 1, 15)),
            ("15-01-2024", "%d-%m-%Y", date(2024, 1, 15)),
            ("15.01.2024", "%d.%m.%Y", date(2024, 1, 15)),
        ]
        for date_str, fmt, expected in test_cases:
            result = parse_date_string(date_str, fmt)
            assert result == expected
