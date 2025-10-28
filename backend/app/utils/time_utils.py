"""Time and date utilities for portfolio tracking.

This module provides centralized functions for handling time ranges, date parsing,
and date-related calculations used throughout the application.
"""

from datetime import date, datetime, timedelta
from typing import Optional, Tuple
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)


def parse_time_range(range_str: str) -> Tuple[Optional[date], Optional[date]]:
    """
    Convert time range string to start_date and end_date.

    Date Range Semantics:
    - Ranges use [start_date, end_date) semantics (inclusive start, exclusive end)
    - end_date is ALWAYS today (or current_date context), but typically excluded
    - start_date is calculated backwards from end_date
    - When used in database queries: start_date <= date < end_date
    - EXCEPTION: "YTD" uses inclusive semantics [start_date, end_date]

    Supported formats:
    - "1D": Last 1 day (yesterday to today) - 1 day of data
    - "1W": Last 7 days (7 days ago to today) - 7 days of data
    - "1M": Last 30 days (30 days ago to today) - 30 days of data
    - "3M": Last 90 days (90 days ago to today) - 90 days of data
    - "6M": Last 180 days (180 days ago to today) - 180 days of data
    - "1Y": Last 365 days (365 days ago to today) - 365 days of data
    - "YTD": Year-to-date (from Jan 1 to today, fully inclusive)
    - "ALL": All available data (returns None, None)

    Args:
        range_str: Time range string (case-sensitive, must match exactly)

    Returns:
        Tuple of (start_date, end_date). Returns (None, None) for "ALL".
        - For most ranges: use [start_date, end_date) in queries
        - For "YTD": use [start_date, end_date] in queries

    Raises:
        HTTPException: If range_str is invalid (400 Bad Request)

    Examples:
        >>> # "1M" returns 30 days of historical data
        >>> start, end = parse_time_range("1M")
        >>> start == date.today() - timedelta(days=30)
        True
        >>> end == date.today()
        True

        >>> # "1D" returns yesterday's data (1 day)
        >>> start, end = parse_time_range("1D")
        >>> start == date.today() - timedelta(days=1)
        True
        >>> end == date.today()
        True

        >>> # "1W" returns 7 days of historical data
        >>> start, end = parse_time_range("1W")
        >>> (end - start).days == 7
        True
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


def get_date_range_description(start_date: Optional[date], end_date: Optional[date]) -> str:
    """
    Get human-readable description of a date range.

    Args:
        start_date: Start date or None for open-ended
        end_date: End date or None for open-ended

    Returns:
        Human-readable date range description

    Examples:
        >>> get_date_range_description(date(2024, 1, 1), date(2024, 12, 31))
        'Jan 1, 2024 to Dec 31, 2024'
        >>> get_date_range_description(None, date(2024, 12, 31))
        'Until Dec 31, 2024'
        >>> get_date_range_description(date(2024, 1, 1), None)
        'From Jan 1, 2024'
    """
    if start_date is None and end_date is None:
        return "All time"

    date_format = "%b %d, %Y"

    if start_date is None:
        return f"Until {end_date.strftime(date_format)}"
    elif end_date is None:
        return f"From {start_date.strftime(date_format)}"
    else:
        return f"{start_date.strftime(date_format)} to {end_date.strftime(date_format)}"


def get_last_n_days(n: int) -> Tuple[date, date]:
    """
    Get date range for last n days (inclusive, NOT including today).

    Date Range Semantics:
    - "last n days" means the previous n days BEFORE today (NOT including today)
    - Equivalent to a range of n calendar days ending on yesterday
    - The range is INCLUSIVE on both start_date and end_date
    - end_date = today (but NOT included in the range semantically)
    - start_date = today - timedelta(days=n)
    - IMPORTANT: When used in queries, use start_date <= date < end_date semantics

    Calculation:
    - n=1: Returns [yesterday, today) - 1 day of data (yesterday)
    - n=7: Returns [7 days ago, today) - 7 days of data
    - n=30: Returns [30 days ago, today) - 30 days of data

    This function uses ValueError instead of HTTPException because it may be called
    in non-API contexts (e.g., background tasks, service layer code). API endpoints
    should catch and convert ValueError to HTTPException if needed.

    Args:
        n: Number of days to look back (must be positive integer)

    Returns:
        Tuple of (start_date, end_date) where:
        - start_date = today - n days (inclusive start)
        - end_date = today (exclusive end, usually used as upper bound)
        - Represents the time period [start_date, end_date)

    Raises:
        ValueError: If n is not positive (internal error for non-API contexts)

    Examples:
        >>> # get_last_n_days(1) returns yesterday (1 day of past data)
        >>> start, end = get_last_n_days(1)
        >>> start == date.today() - timedelta(days=1)
        True
        >>> end == date.today()
        True

        >>> # get_last_n_days(7) returns 7 days of past data
        >>> start, end = get_last_n_days(7)
        >>> end == date.today()
        True
        >>> start == date.today() - timedelta(days=7)
        True
        >>> (end - start).days == 7
        True
    """
    if n <= 0:
        raise ValueError("Number of days must be positive")

    end_date = date.today()
    start_date = end_date - timedelta(days=n)
    return start_date, end_date


def get_year_to_date() -> Tuple[date, date]:
    """
    Get date range from start of year to today.

    Returns:
        Tuple of (start_date, end_date) from Jan 1 to today

    Examples:
        >>> start, end = get_year_to_date()
        >>> start.month == 1
        True
        >>> start.day == 1
        True
        >>> end == date.today()
        True
    """
    today = date.today()
    start_date = date(today.year, 1, 1)
    return start_date, today


def parse_date_string(date_str: str, format_str: str = "%Y-%m-%d") -> date:
    """
    Parse a date string into a date object.

    Parsing Semantics:
    - Supports any valid strptime format string
    - Validates that the parsed date is a valid calendar date
    - Returns a date object (not datetime)
    - Raises HTTPException for API contexts, ValueError for internal use

    Args:
        date_str: Date string to parse. Must match format_str exactly.
        format_str: Expected format string (default: "%Y-%m-%d").
                   Supports standard Python strptime format codes.

    Returns:
        Parsed date object

    Raises:
        HTTPException: If date string cannot be parsed (400 Bad Request)
                      Raised in API contexts for proper HTTP error handling

    Valid Date Boundaries:
    - Minimum: date(1, 1, 1) - Year 1 AD
    - Maximum: date(9999, 12, 31) - Year 9999
    - Leap years: February 29 allowed only in leap years

    Examples:
        >>> # ISO format (default)
        >>> parse_date_string("2024-01-15")
        date(2024, 1, 15)

        >>> # US format
        >>> parse_date_string("01/15/2024", "%m/%d/%Y")
        date(2024, 1, 15)

        >>> # European format
        >>> parse_date_string("15-01-2024", "%d-%m-%Y")
        date(2024, 1, 15)

        >>> # Leap year validation
        >>> parse_date_string("2024-02-29")  # Valid (2024 is leap year)
        date(2024, 2, 29)

        >>> # Century boundary
        >>> parse_date_string("1999-12-31")
        date(1999, 12, 31)
        >>> parse_date_string("2000-01-01")
        date(2000, 1, 1)
    """
    try:
        return datetime.strptime(date_str, format_str).date()
    except ValueError as e:
        logger.warning(f"Failed to parse date string '{date_str}' with format '{format_str}': {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid date format. Expected {format_str}, got: {date_str}"
        )
