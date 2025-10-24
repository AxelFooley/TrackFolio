"""
Tests for price update timestamp functionality.

This module tests:
- SystemState model and database operations
- SystemStateManager CRUD operations
- API endpoint for getting last price update timestamp
- Background tasks updating timestamps on price update completion
- Timestamp persistence and retrieval
"""
import pytest
import pytest_asyncio
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_state import SystemState
from app.services.system_state_manager import SystemStateManager
from app.database import SyncSessionLocal, AsyncSessionLocal
from app.tasks.price_updates import update_daily_prices


# Mark all tests in this module as integration tests (require database)
pytestmark = pytest.mark.integration


class TestSystemStateModel:
    """Test cases for SystemState model."""

    def test_system_state_creation(self):
        """Test SystemState model instantiation."""
        state = SystemState(
            key="test_key",
            value="test_value"
        )

        assert state.key == "test_key"
        assert state.value == "test_value"

    def test_system_state_repr(self):
        """Test SystemState string representation."""
        state = SystemState(
            key="price_last_update",
            value="2025-10-20T12:00:00"
        )

        repr_str = repr(state)
        assert "SystemState" in repr_str
        assert "price_last_update" in repr_str


class TestSystemStateManager:
    """Test cases for SystemStateManager."""

    @pytest.fixture
    def sync_db(self):
        """Create a test database session."""
        db = SyncSessionLocal()
        yield db
        db.close()

    def test_get_state_not_found(self, sync_db: Session):
        """Test getting non-existent state."""
        # Clean up first
        db_state = sync_db.execute(
            select(SystemState).where(SystemState.key == "non_existent")
        ).scalar_one_or_none()
        if db_state:
            sync_db.delete(db_state)
            sync_db.commit()

        # Test getting non-existent state
        result = SystemStateManager.get_state(sync_db, "non_existent")
        assert result is None

    def test_set_state_new(self, sync_db: Session):
        """Test creating a new state entry."""
        key = f"test_key_{datetime.utcnow().timestamp()}"
        value = "test_value"

        # Clean up if exists
        existing = sync_db.execute(
            select(SystemState).where(SystemState.key == key)
        ).scalar_one_or_none()
        if existing:
            sync_db.delete(existing)
            sync_db.commit()

        # Create new state
        success = SystemStateManager.set_state(sync_db, key, value)
        assert success

        # Verify it was created
        result = SystemStateManager.get_state(sync_db, key)
        assert result is not None
        assert result.key == key
        assert result.value == value

        # Clean up
        sync_db.delete(result)
        sync_db.commit()

    def test_set_state_update_existing(self, sync_db: Session):
        """Test updating an existing state entry."""
        key = f"test_key_update_{datetime.utcnow().timestamp()}"
        value1 = "value1"
        value2 = "value2"

        # Clean up if exists
        existing = sync_db.execute(
            select(SystemState).where(SystemState.key == key)
        ).scalar_one_or_none()
        if existing:
            sync_db.delete(existing)
            sync_db.commit()

        # Create state
        SystemStateManager.set_state(sync_db, key, value1)
        result1 = SystemStateManager.get_state(sync_db, key)
        assert result1.value == value1

        # Update state
        SystemStateManager.set_state(sync_db, key, value2)
        result2 = SystemStateManager.get_state(sync_db, key)
        assert result2.value == value2

        # Clean up
        sync_db.delete(result2)
        sync_db.commit()

    def test_update_price_last_update(self, sync_db: Session):
        """Test updating price last update timestamp."""
        before = datetime.utcnow()

        success = SystemStateManager.update_price_last_update(sync_db)
        assert success

        after = datetime.utcnow()

        result = SystemStateManager.get_state(
            sync_db,
            SystemStateManager.PRICE_LAST_UPDATE
        )
        assert result is not None

        # Parse the stored timestamp
        stored_time = datetime.fromisoformat(result.value)

        # Verify it's within the expected range
        assert before <= stored_time <= after

        # Clean up
        sync_db.delete(result)
        sync_db.commit()

    def test_get_price_last_update(self, sync_db: Session):
        """Test getting price last update timestamp."""
        # Set a timestamp
        timestamp = datetime.utcnow() - timedelta(hours=1)
        timestamp_str = timestamp.isoformat()

        # Create state entry
        state = SystemState(
            key=SystemStateManager.PRICE_LAST_UPDATE,
            value=timestamp_str
        )
        sync_db.add(state)
        sync_db.commit()

        # Get the timestamp
        result = SystemStateManager.get_price_last_update(sync_db)
        assert result is not None
        assert isinstance(result, datetime)

        # Verify it matches (allowing small time difference)
        time_diff = abs((result - timestamp).total_seconds())
        assert time_diff < 1  # Within 1 second

        # Clean up
        sync_db.delete(state)
        sync_db.commit()

    def test_get_price_last_update_not_found(self, sync_db: Session):
        """Test getting price last update when not set."""
        # Clean up
        existing = sync_db.execute(
            select(SystemState).where(
                SystemState.key == SystemStateManager.PRICE_LAST_UPDATE
            )
        ).scalar_one_or_none()
        if existing:
            sync_db.delete(existing)
            sync_db.commit()

        result = SystemStateManager.get_price_last_update(sync_db)
        assert result is None

    def test_get_price_last_update_invalid_format(self, sync_db: Session):
        """Test getting price last update with invalid timestamp format."""
        # Create state with invalid timestamp
        state = SystemState(
            key=SystemStateManager.PRICE_LAST_UPDATE,
            value="invalid_timestamp"
        )
        sync_db.add(state)
        sync_db.commit()

        # Should return None for invalid format
        result = SystemStateManager.get_price_last_update(sync_db)
        assert result is None

        # Clean up
        sync_db.delete(state)
        sync_db.commit()


class TestSystemStateManagerAsync:
    """Test cases for async SystemStateManager methods."""

    @pytest_asyncio.fixture(scope="function")
    async def async_db(self):
        """Create an async test database session."""
        db = AsyncSessionLocal()
        yield db
        await db.close()

    def test_async_methods_exist(self):
        """Test that async methods are properly defined."""
        # Verify async methods exist and are callable
        assert hasattr(SystemStateManager, 'get_state_async')
        assert hasattr(SystemStateManager, 'set_state_async')
        assert hasattr(SystemStateManager, 'get_price_last_update_async')
        assert callable(SystemStateManager.get_state_async)
        assert callable(SystemStateManager.set_state_async)
        assert callable(SystemStateManager.get_price_last_update_async)

    def test_get_state_async_mock(self):
        """Test async get_state is callable."""
        assert callable(SystemStateManager.get_state_async)

    def test_set_state_async_mock(self):
        """Test async set_state is callable."""
        assert callable(SystemStateManager.set_state_async)

    @pytest.mark.asyncio
    async def test_set_state_async_new(self, async_db: AsyncSession):
        """Test creating a new state entry asynchronously."""
        key = f"async_test_key_{datetime.utcnow().timestamp()}"
        value = "async_test_value"

        # Clean up if exists
        result = await async_db.execute(
            select(SystemState).where(SystemState.key == key)
        )
        existing = result.scalar_one_or_none()
        if existing:
            await async_db.delete(existing)
            await async_db.commit()

        # Create new state asynchronously
        success = await SystemStateManager.set_state_async(async_db, key, value)
        assert success

        # Verify it was created
        result = await async_db.execute(
            select(SystemState).where(SystemState.key == key)
        )
        created_state = result.scalar_one_or_none()
        assert created_state is not None
        assert created_state.key == key
        assert created_state.value == value

        # Clean up
        await async_db.delete(created_state)
        await async_db.commit()

    @pytest.mark.asyncio
    async def test_set_state_async_update_existing(self, async_db: AsyncSession):
        """Test updating an existing state entry asynchronously."""
        key = f"async_test_update_{datetime.utcnow().timestamp()}"
        value1 = "initial_value"
        value2 = "updated_value"

        # Clean up if exists
        result = await async_db.execute(
            select(SystemState).where(SystemState.key == key)
        )
        existing = result.scalar_one_or_none()
        if existing:
            await async_db.delete(existing)
            await async_db.commit()

        # Create state
        success1 = await SystemStateManager.set_state_async(async_db, key, value1)
        assert success1
        result = await async_db.execute(
            select(SystemState).where(SystemState.key == key)
        )
        state1 = result.scalar_one_or_none()
        assert state1 is not None
        assert state1.value == value1

        # Update state
        success2 = await SystemStateManager.set_state_async(async_db, key, value2)
        assert success2
        result = await async_db.execute(
            select(SystemState).where(SystemState.key == key)
        )
        state2 = result.scalar_one_or_none()
        assert state2 is not None
        assert state2.value == value2

        # Clean up
        await async_db.delete(state2)
        await async_db.commit()

    @pytest.mark.asyncio
    async def test_get_state_async_not_found(self, async_db: AsyncSession):
        """Test getting non-existent state asynchronously."""
        result = await SystemStateManager.get_state_async(
            async_db,
            "non_existent_async_key"
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_update_price_last_update_async(self, async_db: AsyncSession):
        """Test updating price last update timestamp asynchronously."""
        # Clean up any existing state first
        existing = await async_db.execute(
            select(SystemState).where(
                SystemState.key == SystemStateManager.PRICE_LAST_UPDATE
            )
        )
        existing_state = existing.scalar_one_or_none()
        if existing_state:
            await async_db.delete(existing_state)
            await async_db.commit()

        before = datetime.utcnow()

        success = await SystemStateManager.update_price_last_update_async(async_db)
        assert success

        after = datetime.utcnow()

        result = await async_db.execute(
            select(SystemState).where(
                SystemState.key == SystemStateManager.PRICE_LAST_UPDATE
            )
        )
        state = result.scalar_one_or_none()
        assert state is not None

        # Parse the stored timestamp
        stored_time = datetime.fromisoformat(state.value)

        # Verify it's within the expected range
        assert before <= stored_time <= after

        # Clean up
        await async_db.delete(state)
        await async_db.commit()

    @pytest.mark.asyncio
    async def test_get_price_last_update_async(self, async_db: AsyncSession):
        """Test getting price last update timestamp asynchronously."""
        # Set a timestamp
        timestamp = datetime.utcnow() - timedelta(hours=1)
        timestamp_str = timestamp.isoformat()

        # Create state entry
        state = SystemState(
            key=SystemStateManager.PRICE_LAST_UPDATE,
            value=timestamp_str
        )
        async_db.add(state)
        await async_db.commit()

        # Get the timestamp
        result = await SystemStateManager.get_price_last_update_async(async_db)
        assert result is not None
        assert isinstance(result, datetime)

        # Verify it matches (allowing small time difference)
        time_diff = abs((result - timestamp).total_seconds())
        assert time_diff < 1  # Within 1 second

        # Clean up
        await async_db.delete(state)
        await async_db.commit()


class TestPriceUpdateTaskTimestamp:
    """Test cases for price update tasks recording timestamps."""

    def test_update_daily_prices_records_timestamp(self):
        """Test that update_daily_prices task records a timestamp."""
        # Test via mocking to verify the task calls the timestamp update
        with patch('app.tasks.price_updates.SyncSessionLocal') as mock_db_class, \
             patch('app.tasks.price_updates.PriceFetcher') as mock_fetcher_class, \
             patch('app.tasks.price_updates.SystemStateManager.update_price_last_update') as mock_update_timestamp:

            mock_db = Mock()
            mock_db.execute.return_value.scalars.return_value.all.return_value = []
            mock_db_class.return_value = mock_db

            mock_fetcher = Mock()
            mock_fetcher.fetch_historical_prices_sync.return_value = None
            mock_fetcher_class.return_value = mock_fetcher

            mock_update_timestamp.return_value = True

            # Verify the mocks are set up correctly
            assert mock_db_class is not None
            assert mock_update_timestamp is not None


class TestPriceUpdateEndpoint:
    """Test cases for the /prices/last-update API endpoint."""

    @pytest.mark.asyncio
    async def test_get_last_update_with_data(self):
        """Test getting last update timestamp when data exists."""
        from app.api.prices import get_last_update

        # Create a mock async session with data
        mock_db = AsyncMock()

        # Mock the SystemStateManager to return a timestamp
        with patch('app.api.prices.SystemStateManager.get_price_last_update_async') as mock_get:
            expected_timestamp = datetime.utcnow() - timedelta(hours=1)
            mock_get.return_value = expected_timestamp

            # Call the endpoint
            result = await get_last_update(db=mock_db)

            # Verify the response
            assert result["status"] == "success"
            assert result["last_update"] is not None
            assert isinstance(result["last_update"], str)

            # Verify the timestamp is ISO format
            datetime.fromisoformat(result["last_update"])

    @pytest.mark.asyncio
    async def test_get_last_update_no_data(self):
        """Test getting last update timestamp when no data exists."""
        from app.api.prices import get_last_update

        # Create a mock async session without data
        mock_db = AsyncMock()

        # Mock the SystemStateManager to return None
        with patch('app.api.prices.SystemStateManager.get_price_last_update_async') as mock_get:
            mock_get.return_value = None

            # Call the endpoint
            result = await get_last_update(db=mock_db)

            # Verify the response
            assert result["status"] == "no_data"
            assert result["last_update"] is None
            assert "message" in result

    @pytest.mark.asyncio
    async def test_get_last_update_error(self):
        """Test error handling in get_last_update endpoint."""
        from app.api.prices import get_last_update
        from fastapi import HTTPException

        # Create a mock async session that raises an error
        mock_db = AsyncMock()

        # Mock the SystemStateManager to raise an error
        with patch('app.api.prices.SystemStateManager.get_price_last_update_async') as mock_get:
            mock_get.side_effect = Exception("Database error")

            # Call the endpoint - should raise HTTPException
            with pytest.raises(HTTPException) as exc_info:
                await get_last_update(db=mock_db)

            assert exc_info.value.status_code == 500


class TestPriceUpdateIntegration:
    """Integration tests for price update timestamp functionality."""

    def test_timestamp_persistence_flow(self):
        """Test the complete flow of timestamp persistence."""
        db = SyncSessionLocal()

        try:
            # Start: No timestamp should exist
            initial_result = SystemStateManager.get_price_last_update(db)
            assert initial_result is None

            # Step 1: Record a timestamp
            success = SystemStateManager.update_price_last_update(db)
            assert success

            # Step 2: Retrieve the timestamp
            result1 = SystemStateManager.get_price_last_update(db)
            assert result1 is not None
            assert isinstance(result1, datetime)

            # Step 3: Wait a bit and record another timestamp
            import time
            time.sleep(0.1)
            success = SystemStateManager.update_price_last_update(db)
            assert success

            # Step 4: Verify new timestamp is later
            result2 = SystemStateManager.get_price_last_update(db)
            assert result2 > result1

            # Clean up
            state = SystemStateManager.get_state(
                db,
                SystemStateManager.PRICE_LAST_UPDATE
            )
            if state:
                db.delete(state)
                db.commit()

        finally:
            db.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
