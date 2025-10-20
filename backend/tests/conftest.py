"""
Pytest configuration for test suite.

Handles pytest-asyncio configuration and shared fixtures.
"""
import pytest

# Configure pytest-asyncio to use function-scoped event loops
def pytest_configure(config):
    """Configure pytest with asyncio mode."""
    config.addinivalue_line(
        "asyncio_mode", "auto"
    )


@pytest.fixture(scope="session")
def event_loop_policy():
    """Set the event loop policy for the entire session."""
    import asyncio
    import platform

    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.get_event_loop_policy()
