"""
Unit tests for Security Service.

Tests encryption/decryption operations, key management, and utility functions.
"""

import pytest
import json
import os
from unittest.mock import patch, MagicMock

from app.services.security_service import SecurityService, SecurityError
from app.config import settings


class TestSecurityService:
    """Test cases for SecurityService."""

    @pytest.fixture
    def security_service(self):
        """Create a SecurityService instance for testing."""
        return SecurityService()

    @pytest.fixture
    def test_encryption_key(self):
        """Provide a test encryption key."""
        return "test_encryption_key_32_characters_long_123456"

    @pytest.fixture
    def mock_settings(self, test_encryption_key):
        """Mock settings with test encryption key."""
        mock_settings = MagicMock()
        mock_settings.encryption_key = test_encryption_key
        mock_settings.environment = "test"
        return mock_settings

    def test_encrypt_string(self, security_service, mock_settings):
        """Test encryption of string data."""
        with patch('app.services.security_service.settings', mock_settings):
            test_data = "sensitive_wallet_data"
            encrypted = security_service.encrypt(test_data)

            # Verify encrypted data is different from original
            assert encrypted != test_data
            assert isinstance(encrypted, str)
            assert len(encrypted) > 0

            # Verify it's base64 encoded (should only contain valid chars)
            assert all(c.isalnum() or c in '+/=' for c in encrypted)

    def test_encrypt_dictionary(self, security_service, mock_settings):
        """Test encryption of dictionary data."""
        with patch('app.services.security_service.settings', mock_settings):
            test_data = {
                "private_key": "abc123",
                "seed_phrase": "word1 word2 word3",
                "api_key": "def456"
            }
            encrypted = security_service.encrypt(test_data)

            # Verify encrypted data is different from original
            assert encrypted != json.dumps(test_data)
            assert isinstance(encrypted, str)
            assert len(encrypted) > 0

    def test_decrypt_string(self, security_service, mock_settings):
        """Test decryption of string data."""
        with patch('app.services.security_service.settings', mock_settings):
            original_data = "sensitive_wallet_data"
            encrypted = security_service.encrypt(original_data)
            decrypted = security_service.decrypt(encrypted)

            assert decrypted == original_data

    def test_decrypt_dictionary(self, security_service, mock_settings):
        """Test decryption of dictionary data."""
        with patch('app.services.security_service.settings', mock_settings):
            original_data = {
                "private_key": "abc123",
                "seed_phrase": "word1 word2 word3",
                "api_key": "def456"
            }
            encrypted = security_service.encrypt(original_data)
            decrypted = security_service.decrypt(encrypted)

            assert decrypted == original_data

    def test_decrypt_invalid_base64(self, security_service, mock_settings):
        """Test decryption with invalid base64 data."""
        with patch('app.services.security_service.settings', mock_settings):
            with pytest.raises(SecurityError, match="Failed to decrypt"):
                security_service.decrypt("invalid_base64!")

    def test_decrypt_tampered_data(self, security_service, mock_settings):
        """Test decryption with tampered data."""
        with patch('app.services.security_service.settings', mock_settings):
            original_data = "test_data"
            encrypted = security_service.encrypt(original_data)

            # Tamper with the encrypted data
            tampered = encrypted[:-5] + "XXXXX"

            with pytest.raises(SecurityError, match="Invalid authentication tag"):
                security_service.decrypt(tampered)

    def test_encrypt_decrypt_roundtrip(self, security_service, mock_settings):
        """Test multiple encrypt/decrypt roundtrips."""
        with patch('app.services.security_service.settings', mock_settings):
            test_cases = [
                "simple_string",
                "string with spaces and symbols!@#$%",
                "unicode_test_ßäöü",
                {"key": "value", "number": 42, "nested": {"data": "test"}},
                [],
                123  # Will be converted to string
            ]

            for test_data in test_cases:
                encrypted = security_service.encrypt(test_data)
                decrypted = security_service.decrypt(encrypted)

                # Convert non-dict data to expected format
                if isinstance(test_data, dict):
                    assert decrypted == test_data
                else:
                    assert str(decrypted) == str(test_data)

    def test_hash_address(self, security_service):
        """Test address hashing."""
        address1 = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        address2 = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"  # Same as address1
        address3 = "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2"  # Different

        hash1 = security_service.hash_address(address1)
        hash2 = security_service.hash_address(address2)
        hash3 = security_service.hash_address(address3)

        # Same addresses should have same hash
        assert hash1 == hash2
        # Different addresses should have different hashes
        assert hash1 != hash3
        # Hash should be 64 characters (SHA-256 hex)
        assert len(hash1) == 64
        # Hash should be hex
        assert all(c in '0123456789abcdef' for c in hash1)

    def test_generate_secure_token(self, security_service):
        """Test secure token generation."""
        token1 = security_service.generate_secure_token()
        token2 = security_service.generate_secure_token()

        # Tokens should be different
        assert token1 != token2
        # Default token should be 64 characters (32 bytes * 2 for hex)
        assert len(token1) == 64
        # Token should be hex
        assert all(c in '0123456789abcdef' for c in token1)

        # Test custom length
        token_short = security_service.generate_secure_token(16)
        assert len(token_short) == 32  # 16 bytes * 2 for hex

    def test_mask_sensitive_data(self, security_service):
        """Test sensitive data masking."""
        # Test with long data
        long_data = "abcdefghijklmnopqrstuvwxyz"
        masked = security_service.mask_sensitive_data(long_data, 4)
        assert masked == "abcd****************wxyz"

        # Test with short data
        short_data = "abc"
        masked = security_service.mask_sensitive_data(short_data, 2)
        assert masked == "***"

        # Test with empty data
        empty_data = ""
        masked = security_service.mask_sensitive_data(empty_data, 4)
        assert masked == ""

        # Test with None
        masked = security_service.mask_sensitive_data(None, 4)
        assert masked == ""

    def test_validate_encryption_setup_success(self, security_service, mock_settings):
        """Test successful encryption setup validation."""
        with patch('app.services.security_service.settings', mock_settings):
            result = security_service.validate_encryption_setup()

            assert result["valid"] is True
            assert result["encryption_configured"] is True
            assert result["test_encryption_passed"] is True
            assert len(result["errors"]) == 0

    def test_validate_encryption_setup_no_key(self, security_service):
        """Test validation failure when no encryption key is configured."""
        mock_settings = MagicMock()
        mock_settings.encryption_key = ""
        mock_settings.environment = "test"

        with patch('app.services.security_service.settings', mock_settings):
            result = security_service.validate_encryption_setup()

            assert result["valid"] is False
            assert result["encryption_configured"] is False
            assert "ENCRYPTION_KEY environment variable not set" in result["errors"]

    def test_validate_encryption_setup_test_failure(self, security_service, mock_settings):
        """Test validation failure when test encryption fails."""
        with patch('app.services.security_service.settings', mock_settings):
            # Mock the encrypt method to raise an exception
            original_encrypt = security_service.encrypt
            security_service.encrypt = MagicMock(side_effect=Exception("Test error"))

            try:
                result = security_service.validate_encryption_setup()

                assert result["valid"] is False
                assert result["test_encryption_passed"] is False
                assert "Test encryption failed" in result["errors"][0]
            finally:
                # Restore original method
                security_service.encrypt = original_encrypt

    def test_prepare_for_key_rotation(self, security_service):
        """Test key rotation preparation."""
        result = security_service.prepare_for_key_rotation()

        assert result["current_key_version"] == 1
        assert result["supported_versions"] == [1]
        assert result["rotation_ready"] is True
        assert "note" in result

    def test_key_derivation_production(self, security_service):
        """Test key derivation in production environment."""
        mock_settings = MagicMock()
        mock_settings.encryption_key = "test_key"
        mock_settings.environment = "production"

        with patch('app.services.security_service.settings', mock_settings):
            # Reset the cached key to force re-derivation
            security_service._encryption_key = None
            key = security_service.encryption_key

            assert len(key) == 32  # 256 bits
            assert isinstance(key, bytes)

    def test_key_derivation_development(self, security_service):
        """Test key derivation in development environment."""
        mock_settings = MagicMock()
        mock_settings.encryption_key = "test_key"
        mock_settings.environment = "development"

        with patch('app.services.security_service.settings', mock_settings):
            # Reset the cached key to force re-derivation
            security_service._encryption_key = None

            with patch('app.services.security_service.logger') as mock_logger:
                key = security_service.encryption_key
                # Should log warning about development key
                mock_logger.warning.assert_called_once()

            assert len(key) == 32  # 256 bits
            assert isinstance(key, bytes)

    def test_encryption_without_key(self, security_service):
        """Test encryption failure when no key is available."""
        mock_settings = MagicMock()
        mock_settings.encryption_key = ""
        mock_settings.environment = "test"

        with patch('app.services.security_service.settings', mock_settings):
            # Reset the cached key
            security_service._encryption_key = None

            with pytest.raises(SecurityError, match="ENCRYPTION_KEY environment variable is required"):
                security_service.encrypt("test_data")

    def test_empty_string_encryption(self, security_service, mock_settings):
        """Test encryption of empty string."""
        with patch('app.services.security_service.settings', mock_settings):
            encrypted = security_service.encrypt("")
            decrypted = security_service.decrypt(encrypted)

            assert decrypted == ""

    def test_large_data_encryption(self, security_service, mock_settings):
        """Test encryption of large data."""
        with patch('app.services.security_service.settings', mock_settings):
            # Create a large string (1KB)
            large_data = "A" * 1024
            encrypted = security_service.encrypt(large_data)
            decrypted = security_service.decrypt(encrypted)

            assert decrypted == large_data