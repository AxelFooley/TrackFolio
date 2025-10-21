"""
Pytest configuration for test suite.

Handles pytest-asyncio configuration and shared fixtures.
"""
import sys
import os
from pathlib import Path

import pytest

# Add the app directory to sys.path for imports
app_dir = Path(__file__).parent.parent
if str(app_dir) not in sys.path:
    sys.path.insert(0, str(app_dir))


def pytest_configure(config):
    """Register custom markers dynamically."""
    config.addinivalue_line(
        "markers", "integration: integration tests that require external services"
    )
    config.addinivalue_line(
        "markers", "unit: unit tests with mocked dependencies"
    )


@pytest.fixture(scope="session")
def event_loop_policy():
    """Set the event loop policy for the entire session."""
    import asyncio
    import platform

    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.get_event_loop_policy()
