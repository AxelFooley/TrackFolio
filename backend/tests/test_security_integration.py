"""
Integration tests for Security Service with Wallet Models.

Tests how the security service integrates with the wallet connection models
for encryption and validation operations.
"""

import pytest
from unittest.mock import patch, MagicMock

from app.services.security_service import security_service, SecurityError
from app.utils.crypto_validations import address_validator
from app.models.crypto_paper import WalletConnection, WalletAddress, BlockchainNetwork


class TestSecurityIntegration:
    """Test cases for security service integration with wallet models."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings with test encryption key."""
        mock_settings = MagicMock()
        mock_settings.encryption_key = "test_encryption_key_32_characters_long_123456"
        mock_settings.environment = "test"
        return mock_settings

    @pytest.fixture
    def wallet_credentials(self):
        """Sample wallet credentials for testing."""
        return {
            "api_key": "test_api_key_12345",
            "private_key": "test_private_key_abcdef",
            "seed_phrase": "word1 word2 word3 word4 word5 word6",
            "password": "test_password_789"
        }

    @pytest.fixture
    def sample_addresses(self):
        """Sample blockchain addresses for testing."""
        return {
            "bitcoin_p2pkh": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            "bitcoin_p2sh": "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy",
            "bitcoin_bech32": "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq",
            "ethereum": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb9",
            "polygon": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb9",
        }

    def test_wallet_connection_encryption_roundtrip(self, mock_settings, wallet_credentials):
        """Test complete encryption/decryption cycle for wallet credentials."""
        with patch('app.services.security_service.settings', mock_settings):
            # Encrypt credentials
            encrypted_credentials = security_service.encrypt(wallet_credentials)
            assert encrypted_credentials != wallet_credentials
            assert isinstance(encrypted_credentials, str)

            # Decrypt credentials
            decrypted_credentials = security_service.decrypt(encrypted_credentials)
            assert decrypted_credentials == wallet_credentials

    def test_wallet_connection_model_integration(self, mock_settings, wallet_credentials):
        """Test integration with WalletConnection model."""
        with patch('app.services.security_service.settings', mock_settings):
            # Encrypt credentials for storage
            encrypted_credentials = security_service.encrypt(wallet_credentials)

            # Simulate creating a wallet connection
            wallet_connection = WalletConnection(
                portfolio_id=1,
                name="Test Wallet",
                connection_type="software_wallet",
                network=BlockchainNetwork.ETHEREUM,
                encrypted_credentials=encrypted_credentials,
                public_key="0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb9"
            )

            # Verify the encrypted data is stored
            assert wallet_connection.encrypted_credentials == encrypted_credentials

            # Decrypt credentials for use
            decrypted_credentials = security_service.decrypt(wallet_connection.encrypted_credentials)
            assert decrypted_credentials == wallet_credentials

    def test_wallet_address_validation_integration(self, sample_addresses):
        """Test address validation integration with WalletAddress model."""
        # Test Bitcoin address validation
        bitcoin_address = sample_addresses["bitcoin_p2pkh"]
        is_valid, error = address_validator.validate_address(bitcoin_address, "bitcoin")
        assert is_valid

        # Create WalletAddress with validation
        wallet_address = WalletAddress(
            wallet_connection_id=1,
            address=bitcoin_address,
            network=BlockchainNetwork.BITCOIN,
            is_valid=is_valid,
            address_validation_hash=security_service.hash_address(bitcoin_address)
        )

        assert wallet_address.is_valid is True
        assert wallet_address.address_validation_hash is not None
        assert len(wallet_address.address_validation_hash) == 64  # SHA-256 hex

    def test_address_hash_consistency(self, sample_addresses):
        """Test that address hashes are consistent."""
        bitcoin_address = sample_addresses["bitcoin_p2pkh"]

        # Generate hash twice
        hash1 = security_service.hash_address(bitcoin_address)
        hash2 = security_service.hash_address(bitcoin_address)

        # Hashes should be identical
        assert hash1 == hash2

        # Hash should be different for different addresses
        ethereum_address = sample_addresses["ethereum"]
        eth_hash = security_service.hash_address(ethereum_address)
        assert hash1 != eth_hash

    def test_wallet_connection_encryption_error_handling(self, mock_settings):
        """Test error handling in wallet connection encryption."""
        with patch('app.services.security_service.settings', mock_settings):
            # Test with tampered data
            original_data = {"test": "data"}
            encrypted = security_service.encrypt(original_data)

            # Tamper with encrypted data
            tampered = encrypted[:-5] + "XXXXX"

            # Should raise SecurityError
            with pytest.raises(SecurityError, match="Invalid authentication tag"):
                security_service.decrypt(tampered)

    def test_sensitive_data_masking(self, mock_settings, wallet_credentials):
        """Test sensitive data masking for logging."""
        with patch('app.services.security_service.settings', mock_settings):
            # Test masking different types of sensitive data
            api_key = wallet_credentials["api_key"]
            masked_key = security_service.mask_sensitive_data(api_key)

            # Should show first and last 4 characters
            assert masked_key.startswith(api_key[:4])
            assert masked_key.endswith(api_key[-4:])
            assert "*" in masked_key
            assert len(masked_key) == len(api_key)

            # Test with short data
            short_data = "abc"
            masked_short = security_service.mask_sensitive_data(short_data)
            assert masked_short == "***"

    def test_multiple_wallet_encryption(self, mock_settings):
        """Test encrypting multiple different wallet credentials."""
        with patch('app.services.security_service.settings', mock_settings):
            wallets = [
                {"name": "Wallet1", "key": "key1"},
                {"name": "Wallet2", "key": "key2"},
                {"name": "Wallet3", "key": "key3"},
            ]

            encrypted_wallets = []
            for wallet in wallets:
                encrypted = security_service.encrypt(wallet)
                encrypted_wallets.append(encrypted)

                # All encrypted values should be different
                assert encrypted not in encrypted_wallets[:-1]

            # Decrypt and verify all wallets
            for i, encrypted in enumerate(encrypted_wallets):
                decrypted = security_service.decrypt(encrypted)
                assert decrypted == wallets[i]

    def test_address_validation_for_all_networks(self, sample_addresses):
        """Test address validation for all supported networks."""
        test_cases = [
            ("bitcoin_p2pkh", "bitcoin"),
            ("bitcoin_p2sh", "bitcoin"),
            ("bitcoin_bech32", "bitcoin"),
            ("ethereum", "ethereum"),
            ("polygon", "polygon"),
        ]

        for address_key, network in test_cases:
            address = sample_addresses[address_key]
            is_valid, error = address_validator.validate_address(address, network)

            assert is_valid, f"Address {address} should be valid for network {network}"
            assert error is None

            # Get detailed info
            info = address_validator.get_address_info(address, network)
            assert info["is_valid"] is True
            assert info["network"] == network
            assert info["address_type"] is not None

    def test_security_validation_setup(self, mock_settings):
        """Test security service validation setup."""
        with patch('app.services.security_service.settings', mock_settings):
            result = security_service.validate_encryption_setup()

            assert result["valid"] is True
            assert result["encryption_configured"] is True
            assert result["test_encryption_passed"] is True
            assert len(result["errors"]) == 0

    def test_wallet_connection_key_rotation_preparation(self, mock_settings):
        """Test key rotation preparation for wallet connections."""
        with patch('app.services.security_service.settings', mock_settings):
            rotation_info = security_service.prepare_for_key_rotation()

            assert rotation_info["current_key_version"] == 1
            assert rotation_info["supported_versions"] == [1]
            assert rotation_info["rotation_ready"] is True

    def test_large_wallet_data_encryption(self, mock_settings):
        """Test encryption of large wallet data sets."""
        with patch('app.services.security_service.settings', mock_settings):
            # Create a large wallet data set
            large_wallet_data = {
                "transactions": [
                    {
                        "hash": f"0x{'a' * 64}",
                        "from": f"0x{'b' * 40}",
                        "to": f"0x{'c' * 40}",
                        "value": "1000000000000000000",
                        "gas": "21000",
                        "gasPrice": "20000000000",
                    }
                    for _ in range(1000)  # 1000 transactions
                ],
                "contracts": [
                    {
                        "address": f"0x{'d' * 40}",
                        "abi": [{"type": "function", "name": f"func_{i}"} for i in range(100)]
                    }
                    for _ in range(50)  # 50 contracts
                ]
            }

            # Encrypt and decrypt
            encrypted = security_service.encrypt(large_wallet_data)
            decrypted = security_service.decrypt(encrypted)

            assert decrypted == large_wallet_data

    def test_concurrent_encryption_operations(self, mock_settings, wallet_credentials):
        """Test multiple concurrent encryption operations."""
        import threading
        import time

        results = []
        errors = []

        def encrypt_decrypt_task(task_id):
            try:
                with patch('app.services.security_service.settings', mock_settings):
                    # Encrypt
                    task_data = f"{wallet_credentials}_{task_id}"
                    encrypted = security_service.encrypt(task_data)

                    # Small delay to simulate real-world usage
                    time.sleep(0.01)

                    # Decrypt
                    decrypted = security_service.decrypt(encrypted)

                    results.append((task_id, task_data == decrypted))
            except Exception as e:
                errors.append((task_id, str(e)))

        # Run multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=encrypt_decrypt_task, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify results
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 10
        assert all(success for task_id, success in results)