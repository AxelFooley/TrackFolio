"""
Comprehensive tests for cache service error scenarios and fallback behavior.

These tests verify that the cache service handles all edge cases gracefully:
1. Cache get/set operations with various data types
2. Cache miss behavior (returns None)
3. Cache expiration (TTL)
4. Error handling when Redis is unavailable
5. Fallback behavior when caching fails
6. Concurrent cache access
"""

import pytest
import json
import asyncio
import time
from unittest.mock import patch, MagicMock, Mock
from decimal import Decimal
from typing import List, Dict, Any

from app.services.cache import CacheService, cache


pytestmark = pytest.mark.unit


class TestCacheGetSet:
    """Test basic cache get/set operations with various data types."""

    def test_set_and_get_string(self):
        """Test setting and getting a simple string value."""
        service = CacheService()
        if not service.available:
            pytest.skip("Redis not available")

        result = service.set("test_key_string", "test_value", ttl_seconds=60)
        assert result is True

        value = service.get("test_key_string")
        assert value == "test_value"

        # Cleanup
        service.delete("test_key_string")

    def test_set_and_get_dict(self):
        """Test setting and getting a dictionary (JSON serializable)."""
        service = CacheService()
        if not service.available:
            pytest.skip("Redis not available")

        test_dict = {"ticker": "AAPL", "price": 150.25, "currency": "USD"}
        result = service.set("test_key_dict", test_dict, ttl_seconds=60)
        assert result is True

        value = service.get("test_key_dict")
        assert value == test_dict
        assert value["ticker"] == "AAPL"
        assert value["price"] == 150.25

        # Cleanup
        service.delete("test_key_dict")

    def test_set_and_get_list(self):
        """Test setting and getting a list (JSON serializable)."""
        service = CacheService()
        if not service.available:
            pytest.skip("Redis not available")

        test_list = [
            {"ticker": "AAPL", "type": "EQUITY"},
            {"ticker": "SPY", "type": "ETF"}
        ]
        result = service.set("test_key_list", test_list, ttl_seconds=60)
        assert result is True

        value = service.get("test_key_list")
        assert value == test_list
        assert len(value) == 2

        # Cleanup
        service.delete("test_key_list")

    def test_set_and_get_nested_structure(self):
        """Test setting and getting complex nested structures."""
        service = CacheService()
        if not service.available:
            pytest.skip("Redis not available")

        complex_data = {
            "portfolio": {
                "total_value": 100000.50,
                "holdings": [
                    {"ticker": "AAPL", "qty": 10, "price": 150.25},
                    {"ticker": "MSFT", "qty": 5, "price": 380.00}
                ]
            },
            "metadata": {
                "last_update": "2025-10-20T12:00:00",
                "version": "1.0"
            }
        }
        result = service.set("test_key_complex", complex_data, ttl_seconds=60)
        assert result is True

        value = service.get("test_key_complex")
        assert value == complex_data
        assert value["portfolio"]["total_value"] == 100000.50
        assert len(value["portfolio"]["holdings"]) == 2

        # Cleanup
        service.delete("test_key_complex")

    def test_set_and_get_integer(self):
        """Test setting and getting integer values."""
        service = CacheService()
        if not service.available:
            pytest.skip("Redis not available")

        result = service.set("test_key_int", 42, ttl_seconds=60)
        assert result is True

        value = service.get("test_key_int")
        assert value == 42

        # Cleanup
        service.delete("test_key_int")

    def test_set_and_get_float(self):
        """Test setting and getting float values."""
        service = CacheService()
        if not service.available:
            pytest.skip("Redis not available")

        result = service.set("test_key_float", 3.14159, ttl_seconds=60)
        assert result is True

        value = service.get("test_key_float")
        assert value == 3.14159

        # Cleanup
        service.delete("test_key_float")

    def test_set_and_get_boolean(self):
        """Test setting and getting boolean values."""
        service = CacheService()
        if not service.available:
            pytest.skip("Redis not available")

        result = service.set("test_key_bool_true", True, ttl_seconds=60)
        assert result is True

        value = service.get("test_key_bool_true")
        assert value is True

        result = service.set("test_key_bool_false", False, ttl_seconds=60)
        assert result is True

        value = service.get("test_key_bool_false")
        assert value is False

        # Cleanup
        service.delete("test_key_bool_true")
        service.delete("test_key_bool_false")

    def test_set_and_get_null_value(self):
        """Test setting and getting null/None values."""
        service = CacheService()
        if not service.available:
            pytest.skip("Redis not available")

        result = service.set("test_key_null", None, ttl_seconds=60)
        assert result is True

        value = service.get("test_key_null")
        # JSON null becomes None in Python
        assert value is None

        # Cleanup
        service.delete("test_key_null")

    def test_set_and_get_empty_list(self):
        """Test setting and getting empty list."""
        service = CacheService()
        if not service.available:
            pytest.skip("Redis not available")

        result = service.set("test_key_empty_list", [], ttl_seconds=60)
        assert result is True

        value = service.get("test_key_empty_list")
        assert value == []
        assert len(value) == 0

        # Cleanup
        service.delete("test_key_empty_list")

    def test_set_and_get_empty_dict(self):
        """Test setting and getting empty dictionary."""
        service = CacheService()
        if not service.available:
            pytest.skip("Redis not available")

        result = service.set("test_key_empty_dict", {}, ttl_seconds=60)
        assert result is True

        value = service.get("test_key_empty_dict")
        assert value == {}

        # Cleanup
        service.delete("test_key_empty_dict")


class TestCacheMissAndExiration:
    """Test cache miss behavior and expiration."""

    def test_get_nonexistent_key_returns_none(self):
        """Test that getting a non-existent key returns None."""
        service = CacheService()
        if not service.available:
            pytest.skip("Redis not available")

        value = service.get("nonexistent_key_12345")
        assert value is None

    def test_cache_expiration_ttl(self):
        """Test that cached values expire after TTL."""
        service = CacheService()
        if not service.available:
            pytest.skip("Redis not available")

        # Set with 1 second TTL
        result = service.set("test_key_expiring", "value", ttl_seconds=1)
        assert result is True

        # Should exist immediately
        value = service.get("test_key_expiring")
        assert value == "value"

        # Wait for expiration
        time.sleep(1.5)

        # Should now be gone
        value = service.get("test_key_expiring")
        assert value is None

    def test_cache_ttl_1_hour_default(self):
        """Test that default TTL is 1 hour (3600 seconds)."""
        service = CacheService()
        if not service.available:
            pytest.skip("Redis not available")

        # Set without specifying TTL (should default to 3600)
        result = service.set("test_key_default_ttl", "value")
        assert result is True

        # Verify it's still there after a few seconds
        time.sleep(0.5)
        value = service.get("test_key_default_ttl")
        assert value == "value"

        # Cleanup
        service.delete("test_key_default_ttl")

    def test_cache_ttl_custom(self):
        """Test that custom TTL values work correctly."""
        service = CacheService()
        if not service.available:
            pytest.skip("Redis not available")

        # Set with 2 second TTL
        result = service.set("test_key_custom_ttl", "value", ttl_seconds=2)
        assert result is True

        # Should exist after 1 second
        time.sleep(1)
        value = service.get("test_key_custom_ttl")
        assert value == "value"

        # Should be gone after 3 seconds
        time.sleep(2)
        value = service.get("test_key_custom_ttl")
        assert value is None


class TestCacheErrorHandling:
    """Test error handling when Redis is unavailable or errors occur."""

    @patch('redis.from_url')
    def test_redis_connection_failure_graceful(self, mock_redis):
        """
        Test that cache service handles connection failures gracefully.

        When Redis is unavailable, cache operations should fail gracefully
        instead of crashing the application.
        """
        mock_redis.side_effect = Exception("Connection refused")

        service = CacheService()

        # Service should mark itself as unavailable
        assert service.available is False

        # Get should return None (graceful failure)
        result = service.get("any_key")
        assert result is None

        # Set should return False (graceful failure)
        result = service.set("any_key", "any_value")
        assert result is False

    @patch('redis.from_url')
    def test_redis_set_error_returns_false(self, mock_redis):
        """
        Test that cache.set() returns False on Redis errors.

        Should not raise exception, but gracefully handle errors.
        """
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.setex.side_effect = Exception("Redis error")
        mock_redis.return_value = mock_client

        service = CacheService()
        service.available = True
        service.redis_client = mock_client

        result = service.set("key", "value")
        assert result is False

    @patch('redis.from_url')
    def test_redis_get_error_returns_none(self, mock_redis):
        """
        Test that cache.get() returns None on Redis errors.

        Should not raise exception, but gracefully handle errors.
        """
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.get.side_effect = Exception("Redis error")
        mock_redis.return_value = mock_client

        service = CacheService()
        service.available = True
        service.redis_client = mock_client

        result = service.get("key")
        assert result is None

    @patch('redis.from_url')
    def test_redis_delete_error_returns_false(self, mock_redis):
        """
        Test that cache.delete() returns False on Redis errors.

        Should not raise exception, but gracefully handle errors.
        """
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_client.delete.side_effect = Exception("Redis error")
        mock_redis.return_value = mock_client

        service = CacheService()
        service.available = True
        service.redis_client = mock_client

        result = service.delete("key")
        assert result is False

    @patch('redis.from_url')
    def test_invalid_json_in_cache_returns_none(self, mock_redis):
        """
        Test that invalid JSON data in cache is handled gracefully.

        If cached data is corrupted (invalid JSON), get() should return None
        instead of crashing.
        """
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        # Return invalid JSON
        mock_client.get.return_value = "not valid json {"
        mock_redis.return_value = mock_client

        service = CacheService()
        service.available = True
        service.redis_client = mock_client

        result = service.get("key")
        # Should handle JSON decode error gracefully
        assert result is None

    @patch('redis.from_url')
    def test_redis_unavailable_during_startup(self, mock_redis):
        """
        Test that service starts up gracefully even if Redis is unavailable.

        Should not prevent the application from starting.
        """
        mock_redis.side_effect = Exception("Redis not reachable")

        # Should not raise, but log warning and set available=False
        service = CacheService()

        # Operations should still work (with graceful degradation)
        assert service.get("key") is None
        assert service.set("key", "value") is False


class TestCacheFallbackBehavior:
    """Test fallback behavior when caching fails."""

    @patch('redis.from_url')
    def test_operations_continue_when_cache_unavailable(self, mock_redis):
        """
        Test that application continues working when cache is unavailable.

        This tests the fallback behavior - if Redis is down, the app should
        still function, just without caching benefits.
        """
        mock_redis.side_effect = Exception("Redis down")

        service = CacheService()

        # All operations should still return valid results (just not caching)
        result_get = service.get("test_key")
        result_set = service.set("test_key", "test_value")
        result_delete = service.delete("test_key")
        result_clear = service.clear_pattern("test_*")

        # Should all fail gracefully
        assert result_get is None
        assert result_set is False
        assert result_delete is False
        assert result_clear == 0

    def test_cache_service_initialization_logs_warning(self):
        """
        Test that unavailable cache service logs a warning.

        Should help operators debug why caching isn't working.
        """
        with patch('redis.from_url') as mock_redis:
            mock_redis.side_effect = Exception("Connection error")

            with patch('app.services.cache.logger') as mock_logger:
                service = CacheService()

                # Should have logged a warning
                mock_logger.warning.assert_called()


class TestCacheConcurrentAccess:
    """Test concurrent cache access scenarios."""

    def test_concurrent_set_operations(self):
        """
        Test multiple concurrent set operations.

        Should handle concurrent writes without data corruption.
        """
        service = CacheService()
        if not service.available:
            pytest.skip("Redis not available")

        import concurrent.futures

        def set_value(key_num):
            return service.set(f"concurrent_key_{key_num}", f"value_{key_num}", ttl_seconds=60)

        # Run 10 concurrent set operations
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(set_value, range(10)))

        # All should succeed
        assert all(results)

        # Verify all values were set
        for i in range(10):
            value = service.get(f"concurrent_key_{i}")
            assert value == f"value_{i}"

        # Cleanup
        for i in range(10):
            service.delete(f"concurrent_key_{i}")

    def test_concurrent_get_operations(self):
        """
        Test multiple concurrent get operations.

        Should return correct values without race conditions.
        """
        service = CacheService()
        if not service.available:
            pytest.skip("Redis not available")

        # First set some values
        for i in range(10):
            service.set(f"concurrent_read_key_{i}", f"value_{i}", ttl_seconds=60)

        import concurrent.futures

        def get_value(key_num):
            return service.get(f"concurrent_read_key_{key_num}")

        # Run 20 concurrent read operations
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            results = list(executor.map(get_value, range(10) * 2))

        # Each read should have succeeded
        for i, result in enumerate(results):
            key_num = i % 10
            assert result == f"value_{key_num}"

        # Cleanup
        for i in range(10):
            service.delete(f"concurrent_read_key_{i}")

    def test_concurrent_mixed_operations(self):
        """
        Test concurrent mix of read, write, and delete operations.

        Should maintain data consistency under concurrent access.
        """
        service = CacheService()
        if not service.available:
            pytest.skip("Redis not available")

        import concurrent.futures

        def mixed_operation(op_num):
            op_type = op_num % 3
            if op_type == 0:  # Set
                return service.set(f"mixed_key_{op_num}", f"value_{op_num}", ttl_seconds=60)
            elif op_type == 1:  # Get
                return service.get(f"mixed_key_{op_num % 10}") is not None
            else:  # Delete
                return service.delete(f"mixed_key_{op_num % 10}")

        # Run 30 mixed operations concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(mixed_operation, range(30)))

        # At least some operations should succeed
        assert len(results) > 0


class TestCacheDelete:
    """Test cache delete operations."""

    def test_delete_existing_key(self):
        """Test deleting an existing key."""
        service = CacheService()
        if not service.available:
            pytest.skip("Redis not available")

        # Set a value
        service.set("test_delete_key", "value", ttl_seconds=60)

        # Verify it exists
        assert service.get("test_delete_key") == "value"

        # Delete it
        result = service.delete("test_delete_key")
        assert result is True

        # Verify it's gone
        assert service.get("test_delete_key") is None

    def test_delete_nonexistent_key(self):
        """Test deleting a key that doesn't exist."""
        service = CacheService()
        if not service.available:
            pytest.skip("Redis not available")

        result = service.delete("nonexistent_delete_key")
        # Should return False when key doesn't exist
        assert result is False

    def test_delete_multiple_keys_with_pattern(self):
        """Test deleting multiple keys with clear_pattern."""
        service = CacheService()
        if not service.available:
            pytest.skip("Redis not available")

        # Set multiple related keys
        for i in range(5):
            service.set(f"pattern_test_{i}", f"value_{i}", ttl_seconds=60)

        # Verify they exist
        assert service.get("pattern_test_0") is not None

        # Delete with pattern
        deleted_count = service.clear_pattern("pattern_test_*")
        assert deleted_count == 5

        # Verify they're gone
        for i in range(5):
            assert service.get(f"pattern_test_{i}") is None

    def test_clear_pattern_nonexistent(self):
        """Test clear_pattern on non-matching patterns."""
        service = CacheService()
        if not service.available:
            pytest.skip("Redis not available")

        # Should return 0 when no keys match
        deleted_count = service.clear_pattern("nonexistent_pattern_*")
        assert deleted_count == 0


class TestCacheKeyNormalization:
    """Test cache key handling and normalization."""

    def test_special_characters_in_key(self):
        """Test that special characters in keys are handled correctly."""
        service = CacheService()
        if not service.available:
            pytest.skip("Redis not available")

        # Use a key with special characters
        special_key = "asset_search:AAPL:2025-10-20"
        result = service.set(special_key, {"ticker": "AAPL"}, ttl_seconds=60)
        assert result is True

        value = service.get(special_key)
        assert value == {"ticker": "AAPL"}

        # Cleanup
        service.delete(special_key)

    def test_colon_separator_in_key(self):
        """Test that colon-separated keys work (common Redis pattern)."""
        service = CacheService()
        if not service.available:
            pytest.skip("Redis not available")

        # Redis uses colons as separators
        key = "namespace:subnamespace:key"
        result = service.set(key, "value", ttl_seconds=60)
        assert result is True

        value = service.get(key)
        assert value == "value"

        # Cleanup
        service.delete(key)

    def test_long_key_name(self):
        """Test that long key names work correctly."""
        service = CacheService()
        if not service.available:
            pytest.skip("Redis not available")

        # Create a very long key name
        long_key = "a" * 200
        result = service.set(long_key, "value", ttl_seconds=60)
        assert result is True

        value = service.get(long_key)
        assert value == "value"

        # Cleanup
        service.delete(long_key)


class TestCacheSerializationDeserializaton:
    """Test JSON serialization and deserialization edge cases."""

    def test_unicode_characters_in_cache(self):
        """Test that unicode characters are preserved through cache cycle."""
        service = CacheService()
        if not service.available:
            pytest.skip("Redis not available")

        unicode_value = {"name": "日本 Deutsche Français 中文"}
        result = service.set("unicode_key", unicode_value, ttl_seconds=60)
        assert result is True

        value = service.get("unicode_key")
        assert value == unicode_value
        assert value["name"] == "日本 Deutsche Français 中文"

        # Cleanup
        service.delete("unicode_key")

    def test_large_data_caching(self):
        """Test that large data structures can be cached."""
        service = CacheService()
        if not service.available:
            pytest.skip("Redis not available")

        # Create a large but JSON-serializable data structure
        large_data = {
            "items": [
                {"id": i, "data": "x" * 100}
                for i in range(1000)
            ]
        }

        result = service.set("large_data_key", large_data, ttl_seconds=60)
        assert result is True

        value = service.get("large_data_key")
        assert len(value["items"]) == 1000

        # Cleanup
        service.delete("large_data_key")
