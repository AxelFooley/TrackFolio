"""
Pytest configuration for test suite.

Handles pytest-asyncio configuration and shared fixtures.
"""
import pytest


@pytest.fixture(scope="session")
def event_loop_policy():
    """Set the event loop policy for the entire session."""
    import asyncio
    import platform

    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.get_event_loop_policy()
