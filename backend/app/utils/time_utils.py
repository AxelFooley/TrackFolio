"""
Time utility functions for date range parsing and manipulation.

This module provides common utilities for parsing time ranges (like "1D", "1W", "1M", etc.)
and performing date calculations. These utilities are used across API endpoints to standardize
date range handling.

Examples:
    Parse a time range string:
        >>> from app.utils.time_utils import parse_time_range
        >>> start, end = parse_time_range("1M")
        >>> print(f"Last month: {start} to {end}")

    Get last N days:
        >>> from app.utils.time_utils import get_last_n_days
        >>> start, end = get_last_n_days(30)
        >>> print(f"Last 30 days: {start} to {end}")
"""
from datetime import date, timedelta
from typing import Optional, Tuple
from fastapi import HTTPException


# Supported time range formats
SUPPORTED_RANGES = ["1D", "1W", "1M", "3M", "6M", "1Y", "YTD", "ALL"]


def parse_time_range(range_str: str) -> Tuple[Optional[date], Optional[date]]:
    """
    Convert time range string to start_date and end_date.

    This function parses common time range formats used in portfolio and crypto APIs.
    It returns a tuple of (start_date, end_date) where dates are inclusive.

    Supported formats:
        - "1D": Last 1 day
        - "1W": Last 7 days (1 week)
        - "1M": Last 30 days (1 month)
        - "3M": Last 90 days (3 months)
        - "6M": Last 180 days (6 months)
        - "1Y": Last 365 days (1 year)
        - "YTD": Year-to-date (January 1st of current year to today)
        - "ALL": All available data (returns None, None)

    Args:
        range_str: Time range string (case-insensitive). Must be one of the supported formats.

    Returns:
        Tuple of (start_date, end_date):
            - For time-based ranges: (start_date, today)
            - For "YTD": (January 1st, today)
            - For "ALL": (None, None) indicating no date filtering

    Raises:
        HTTPException: 400 status if range_str is invalid or not supported

    Examples:
        >>> # Get last 30 days
        >>> start, end = parse_time_range("1M")
        >>> assert end == date.today()
        >>> assert (end - start).days == 30

        >>> # Get year-to-date
        >>> start, end = parse_time_range("YTD")
        >>> assert start == date(date.today().year, 1, 1)
        >>> assert end == date.today()

        >>> # Get all data (no filtering)
        >>> start, end = parse_time_range("ALL")
        >>> assert start is None and end is None
    """
    today = date.today()
    end_date = today

    # Map range strings to timedelta objects
    range_mapping = {
        "1D": timedelta(days=1),
        "1W": timedelta(days=7),
        "1M": timedelta(days=30),
        "3M": timedelta(days=90),
        "6M": timedelta(days=180),
        "1Y": timedelta(days=365),
    }

    # Normalize input to uppercase for case-insensitive matching
    range_upper = range_str.upper()

    if range_upper == "ALL":
        return None, None
    elif range_upper == "YTD":
        start_date = date(today.year, 1, 1)
        return start_date, end_date
    elif range_upper in range_mapping:
        start_date = today - range_mapping[range_upper]
        return start_date, end_date
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid range parameter. Must be one of: {', '.join(SUPPORTED_RANGES)}. Got: {range_str}"
        )


def get_last_n_days(n: int) -> Tuple[date, date]:
    """
    Get date range for the last N days.

    This is a convenience function for getting a date range that spans the last N days
    from today. The end date is always today, and the start date is N days ago.

    Args:
        n: Number of days to go back (must be positive)

    Returns:
        Tuple of (start_date, end_date) where:
            - end_date is today
            - start_date is N days before today

    Raises:
        ValueError: If n is not a positive integer

    Examples:
        >>> # Get last 30 days
        >>> start, end = get_last_n_days(30)
        >>> assert end == date.today()
        >>> assert (end - start).days == 30

        >>> # Get last 365 days (1 year)
        >>> start, end = get_last_n_days(365)
        >>> assert (end - start).days == 365
    """
    if n <= 0:
        raise ValueError(f"Number of days must be positive, got: {n}")

    end_date = date.today()
    start_date = end_date - timedelta(days=n)
    return start_date, end_date


def get_date_range_description(start_date: Optional[date], end_date: Optional[date]) -> str:
    """
    Generate a human-readable description of a date range.

    This function provides a user-friendly description of date ranges, useful for
    logging, error messages, and API responses.

    Args:
        start_date: Start date of the range (None means no lower bound)
        end_date: End date of the range (None means no upper bound)

    Returns:
        String description of the date range

    Examples:
        >>> from datetime import date
        >>> desc = get_date_range_description(date(2024, 1, 1), date(2024, 12, 31))
        >>> print(desc)
        "2024-01-01 to 2024-12-31"

        >>> desc = get_date_range_description(None, None)
        >>> print(desc)
        "all time"

        >>> desc = get_date_range_description(date(2024, 1, 1), None)
        >>> print(desc)
        "from 2024-01-01 onwards"
    """
    if start_date is None and end_date is None:
        return "all time"
    elif start_date is None:
        return f"up to {end_date}"
    elif end_date is None:
        return f"from {start_date} onwards"
    else:
        return f"{start_date} to {end_date}"


def calculate_days_between(start_date: date, end_date: date) -> int:
    """
    Calculate the number of days between two dates (inclusive).

    Args:
        start_date: Start date
        end_date: End date

    Returns:
        Number of days between the dates (inclusive of both start and end)

    Raises:
        ValueError: If start_date is after end_date

    Examples:
        >>> from datetime import date
        >>> days = calculate_days_between(date(2024, 1, 1), date(2024, 1, 31))
        >>> assert days == 31  # January has 31 days
    """
    if start_date > end_date:
        raise ValueError(f"start_date ({start_date}) must be before or equal to end_date ({end_date})")

    delta = end_date - start_date
    return delta.days + 1  # +1 to make it inclusive


def is_ytd_range(start_date: date, end_date: date) -> bool:
    """
    Check if a date range represents year-to-date.

    Args:
        start_date: Start date to check
        end_date: End date to check

    Returns:
        True if the range represents year-to-date (starts on Jan 1 of current year
        and ends today or in the future), False otherwise

    Examples:
        >>> from datetime import date
        >>> today = date.today()
        >>> jan_1 = date(today.year, 1, 1)
        >>> assert is_ytd_range(jan_1, today) == True
        >>> assert is_ytd_range(jan_1, date(today.year, 6, 30)) == False
    """
    today = date.today()
    return (
        start_date == date(today.year, 1, 1) and
        end_date >= today
    )


def adjust_end_date_for_data_availability(
    end_date: date,
    days_buffer: int = 2
) -> date:
    """
    Adjust end date to account for data availability delays.

    Market data and crypto prices may not be available for the most recent days.
    This function adjusts the end date backwards by a buffer to ensure data exists.

    Args:
        end_date: Original end date
        days_buffer: Number of days to subtract from end_date (default: 2)

    Returns:
        Adjusted end date (end_date - days_buffer days)

    Examples:
        >>> from datetime import date
        >>> today = date.today()
        >>> adjusted = adjust_end_date_for_data_availability(today, days_buffer=2)
        >>> assert adjusted == today - timedelta(days=2)
    """
    return end_date - timedelta(days=days_buffer)
