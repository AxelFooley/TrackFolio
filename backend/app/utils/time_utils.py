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

    Supported formats:
    - "1D": Last 1 day
    - "1W": Last 7 days
    - "1M": Last 30 days
    - "3M": Last 90 days
    - "6M": Last 180 days
    - "1Y": Last 365 days
    - "YTD": Year-to-date (from Jan 1 to today)
    - "ALL": All available data (returns None, None)

    Args:
        range_str: Time range string (case-sensitive)

    Returns:
        Tuple of (start_date, end_date). Returns (None, None) for "ALL".

    Raises:
        HTTPException: If range_str is invalid (400 Bad Request)

    Examples:
        >>> start, end = parse_time_range("1M")
        >>> start == date.today() - timedelta(days=30)
        True
        >>> parse_time_range("YTD")
        (date(2024, 1, 1), date(...))
        >>> parse_time_range("ALL")
        (None, None)
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
    Get date range for last n days.

    This function uses ValueError instead of HTTPException because it may be called
    in non-API contexts (e.g., background tasks, service layer code). API endpoints
    should catch and convert ValueError to HTTPException if needed.

    Args:
        n: Number of days (must be positive)

    Returns:
        Tuple of (start_date, end_date) representing last n days

    Raises:
        ValueError: If n is not positive (internal error for non-API contexts)

    Examples:
        >>> start, end = get_last_n_days(7)
        >>> end == date.today()
        True
        >>> start == date.today() - timedelta(days=7)
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

    Args:
        date_str: Date string to parse
        format_str: Expected format string (default: "%Y-%m-%d")

    Returns:
        Parsed date object

    Raises:
        HTTPException: If date string cannot be parsed (400 Bad Request)

    Examples:
        >>> parse_date_string("2024-01-15")
        date(2024, 1, 15)
        >>> parse_date_string("01/15/2024", "%m/%d/%Y")
        date(2024, 1, 15)
    """
    try:
        return datetime.strptime(date_str, format_str).date()
    except ValueError as e:
        logger.warning(f"Failed to parse date string '{date_str}' with format '{format_str}': {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid date format. Expected {format_str}, got: {date_str}"
        )
