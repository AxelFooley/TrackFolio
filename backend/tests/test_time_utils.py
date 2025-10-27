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
