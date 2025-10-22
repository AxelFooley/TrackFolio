"""
Tests for blockchain services including transaction fetching and deduplication.

This module tests:
- Blockchain transaction fetching from multiple APIs
- Transaction parsing and type detection
- Deduplication mechanisms
- Error handling and retry logic
- Configuration integration
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from decimal import Decimal
import time
import redis
import requests


from app.services.blockchain_fetcher import BlockchainFetcherService
from app.services.blockchain_deduplication import BlockchainDeduplicationService
from app.models.crypto import CryptoTransactionType, CryptoCurrency
from app.config import settings


class TestBlockchainFetcherService:
    """Test cases for BlockchainFetcherService."""

    @pytest.fixture
    def blockchain_fetcher(self):
        """
        Create a BlockchainFetcherService configured with a mocked Redis connection for tests.
        
        The mocked Redis client has `ping` returning True, `get` returning None, and `setex` returning True to simulate a reachable Redis with empty cache state.
        
        Returns:
            BlockchainFetcherService: a fetcher instance that uses the mocked Redis client.
        """
        with patch('app.services.blockchain_fetcher.redis.from_url') as mock_redis:
            mock_redis.return_value.ping.return_value = True
            mock_redis.return_value.get.return_value = None
            mock_redis.return_value.setex.return_value = True
            return BlockchainFetcherService()

    @pytest.fixture
    def sample_blockstream_tx(self):
        """
        Provide a representative Blockstream-format transaction used in tests.
        
        Returns:
            dict: A sample transaction dictionary with keys:
                - 'txid' (str): Transaction identifier.
                - 'status' (dict): Contains 'block_time' (int) as a UNIX timestamp.
                - 'vout' (list): List of output dicts, each with:
                    - 'value' (int): Output value in satoshis.
                    - 'scriptpubkey' (str): Output script.
        """
        return {
            'txid': 'test_tx_hash_12345',
            'status': {
            'block_time': 1640995200  # 2022-01-01 00:00:00 UTC
            },
            'vout': [
            {
                'value': 100000,  # 0.001 BTC in satoshis
                'scriptpubkey': 'test_script'
            }
            ]
        }

    @pytest.fixture
    def sample_blockchaincom_tx(self):
        """
        Provide a sample Blockchain.com transaction payload used in tests.
        
        Returns:
            dict: A transaction dict with keys:
                - 'hash' (str): Transaction identifier.
                - 'time' (int): Unix timestamp (seconds).
                - 'result' (int): Net change in satoshis (positive for incoming, negative for outgoing).
        """
        return {
            'hash': 'test_tx_hash_67890',
            'time': 1640995200,  # 2022-01-01 00:00:00 UTC
            'result': 100000000  # 1 BTC net change in satoshis
        }

    def test_validate_bitcoin_address_valid(self, blockchain_fetcher):
        """Test Bitcoin address validation with valid addresses."""
        # Legacy addresses
        assert blockchain_fetcher._validate_bitcoin_address('1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa')
        assert blockchain_fetcher._validate_bitcoin_address('1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2')

        # P2SH addresses
        assert blockchain_fetcher._validate_bitcoin_address('3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy')

        # Bech32 addresses
        assert blockchain_fetcher._validate_bitcoin_address('bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq')
        assert blockchain_fetcher._validate_bitcoin_address('bc1qw508d6qejsy5xg5f8t5q6h7k8s9j0k1l2m3n4o')

    def test_validate_bitcoin_address_invalid(self, blockchain_fetcher):
        """Test Bitcoin address validation with invalid addresses."""
        # Empty string
        assert not blockchain_fetcher._validate_bitcoin_address('')

        # Too short
        assert not blockchain_fetcher._validate_bitcoin_address('1abc')

        # Too long
        assert not blockchain_fetcher._validate_bitcoin_address('1' * 70)

        # Invalid characters
        assert not blockchain_fetcher._validate_bitcoin_address('1abc0def')

        # Invalid prefix
        assert not blockchain_fetcher._validate_bitcoin_address('2abc123def456')

    def test_generate_transaction_hash(self, blockchain_fetcher):
        """Test transaction hash generation for deduplication."""
        tx_data = {
            'txid': 'test_tx_hash',
            'timestamp': 1640995200,
            'value': 1000,
            'address': 'test_address'
        }

        hash1 = blockchain_fetcher._generate_transaction_hash(tx_data)
        hash2 = blockchain_fetcher._generate_transaction_hash(tx_data)

        # Same data should generate same hash
        assert hash1 == hash2

        # Different data should generate different hash
        tx_data_modified = tx_data.copy()
        tx_data_modified['value'] = 2000
        hash3 = blockchain_fetcher._generate_transaction_hash(tx_data_modified)
        assert hash1 != hash3

        # Hash should be a valid SHA256 hash (64 hex characters)
        assert len(hash1) == 64
        assert all(c in '0123456789abcdef' for c in hash1.lower())

    def test_detect_transaction_type(self, blockchain_fetcher):
        """Test transaction type detection."""
        wallet_address = 'test_wallet_address'

        # Positive value should be transfer_in
        tx_data_positive = {'value': 1000}
        assert blockchain_fetcher._detect_transaction_type(tx_data_positive, wallet_address) == CryptoTransactionType.TRANSFER_IN

        # Negative value should be transfer_out
        tx_data_negative = {'value': -1000}
        assert blockchain_fetcher._detect_transaction_type(tx_data_negative, wallet_address) == CryptoTransactionType.TRANSFER_OUT

        # Zero value should default to transfer_in
        tx_data_zero = {'value': 0}
        assert blockchain_fetcher._detect_transaction_type(tx_data_zero, wallet_address) == CryptoTransactionType.TRANSFER_IN

    def test_convert_blockchaincom_transaction_valid(self, blockchain_fetcher, sample_blockchaincom_tx):
        """Test Blockchain.com transaction conversion with valid data."""
        wallet_address = 'test_wallet_address'

        result = blockchain_fetcher._convert_blockchaincom_transaction(sample_blockchaincom_tx, wallet_address)

        assert result is not None
        assert result['transaction_hash'] == 'test_tx_hash_67890'
        assert result['symbol'] == 'BTC'
        assert result['quantity'] == Decimal('1.0')  # 100000000 satoshis = 1 BTC
        assert result['exchange'] == 'Bitcoin Blockchain'
        assert isinstance(result['timestamp'], datetime)
        assert result['transaction_type'] in [CryptoTransactionType.TRANSFER_IN, CryptoTransactionType.TRANSFER_OUT]

    def test_convert_blockchaincom_transaction_invalid(self, blockchain_fetcher):
        """Test Blockchain.com transaction conversion with invalid data."""
        # Missing required fields
        invalid_tx = {'invalid': 'data'}
        wallet_address = 'test_wallet_address'

        result = blockchain_fetcher._convert_blockchaincom_transaction(invalid_tx, wallet_address)
        assert result is None


    def test_build_result(self, blockchain_fetcher):
        """Test result building."""
        transactions = [
            {'tx_hash': 'test1'},
            {'tx_hash': 'test2'}
        ]

        result = blockchain_fetcher._build_result(
            transactions=transactions,
            status='success',
            message='Test message'
        )

        assert result['status'] == 'success'
        assert result['message'] == 'Test message'
        assert result['transactions'] == transactions
        assert result['count'] == 2
        assert isinstance(result['timestamp'], datetime)

    @patch('app.services.blockchain_fetcher.requests.Session.get')
    def test_make_request_success(self, mock_get, blockchain_fetcher):
        """Test successful API request."""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {'data': 'test_data'}
        mock_get.return_value = mock_response

        result = blockchain_fetcher._make_request('/test')

        assert result == {'data': 'test_data'}
        mock_get.assert_called_once()

    @patch('app.services.blockchain_fetcher.requests.Session.get')
    def test_make_request_retry_logic(self, mock_get, blockchain_fetcher):
        """Test API request retry logic."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = [requests.exceptions.RequestException("Network error"), None]
        mock_response.json.return_value = {'data': 'test_data'}
        mock_get.return_value = mock_response

        result = blockchain_fetcher._make_request('/test')

        assert result == {'data': 'test_data'}
        assert mock_get.call_count == 2  # Initial call + 1 retry

    @patch('app.services.blockchain_fetcher.requests.Session.get')
    def test_make_request_max_retries(self, mock_get, blockchain_fetcher):
        """Test API request max retries exceeded."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.exceptions.RequestException("Network error")
        mock_get.return_value = mock_response

        result = blockchain_fetcher._make_request('/test')

        assert result is None
        assert mock_get.call_count == blockchain_fetcher.api_config['max_retries']

    @patch('time.sleep')
    def test_rate_limiting(self, mock_sleep, blockchain_fetcher):
        """Test rate limiting functionality."""
        # Set last request time to simulate rate limiting
        blockchain_fetcher._last_request_time = time.time()

        # This should trigger rate limiting
        blockchain_fetcher._rate_limit()

        # Verify sleep was called (rate limiting was triggered)
        mock_sleep.assert_called()

    @patch('app.services.blockchain_fetcher.BlockchainFetcherService._make_request')
    def test_pagination_fetching(self, mock_make_request, blockchain_fetcher):
        """Test pagination fetching for addresses with many transactions."""
        # Valid Bitcoin address for testing
        wallet_address = '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'

        # Mock multiple pages of transactions
        page1 = {
            'txs': [
                {
                    'hash': f'tx_{i}',
                    'time': 1640995200 + i,
                    'result': 100000,
                    'out': [{'addr': wallet_address, 'value': 100000}]
                }
                for i in range(50)
            ]
        }
        page2 = {
            'txs': [
                {
                    'hash': f'tx_{i}',
                    'time': 1640995200 + i + 50,
                    'result': 100000,
                    'out': [{'addr': wallet_address, 'value': 100000}]
                }
                for i in range(30)
            ]
        }
        page3 = {'txs': []}  # Empty page to signal end

        mock_make_request.side_effect = [page1, page2, page3]

        result = blockchain_fetcher.fetch_transactions(
            wallet_address=wallet_address,
            portfolio_id=1,
            max_transactions=None,  # Fetch all
            days_back=None
        )

        assert result['status'] == 'success'
        assert result['count'] == 80  # 50 + 30 transactions
        assert mock_make_request.call_count == 3  # Three API calls for pagination


class TestBlockchainDeduplicationService:
    """Test cases for BlockchainDeduplicationService."""

    @pytest.fixture
    def deduplication_service(self):
        """Create a deduplication service instance for testing."""
        with patch('app.services.blockchain_deduplication.redis.from_url') as mock_redis, \
             patch('app.services.blockchain_deduplication.SyncSessionLocal') as mock_db, \
             patch('app.services.blockchain_deduplication.BlockchainDeduplicationService._get_portfolio_hashes_from_db') as mock_get_hashes:
            # Configure Redis mocks
            mock_redis.return_value.ping.return_value = True
            mock_redis.return_value.get.return_value = None
            mock_redis.return_value.setex.return_value = True
            mock_redis.return_value.delete.return_value = True
            mock_redis.return_value.keys.return_value = []
            mock_redis.return_value.smembers.return_value = []
            mock_redis.return_value.sadd.return_value = True
            mock_redis.return_value.expire.return_value = True

            # Configure database mock
            mock_db.return_value.__enter__.return_value.execute.return_value.all.return_value = []

            # Mock _get_portfolio_hashes_from_db to return NEW empty set each time (not the same object)
            # This prevents set mutations from affecting subsequent calls
            mock_get_hashes.side_effect = lambda portfolio_id: set()

            # Create service with all mocks active
            service = BlockchainDeduplicationService()

            # Ensure the mock remains active throughout the test by yielding
            yield service

    @pytest.fixture
    def sample_transactions(self):
        """
        Provide a list of sample crypto transaction dictionaries used in tests.
        
        Each dictionary represents a transaction with the following keys:
        - transaction_hash (str): Unique transaction identifier.
        - symbol (str): Asset symbol (e.g., 'BTC').
        - quantity (Decimal): Transaction amount.
        - timestamp (datetime): Transaction timestamp.
        - transaction_type (CryptoTransactionType): IN/OUT transaction type.
        
        Returns:
            list[dict]: Two sample transaction dictionaries for testing.
        """
        return [
            {
                'transaction_hash': 'tx_hash_1',
                'symbol': 'BTC',
                'quantity': Decimal('0.001'),
                'timestamp': datetime(2022, 1, 1),
                'transaction_type': CryptoTransactionType.TRANSFER_IN
            },
            {
                'transaction_hash': 'tx_hash_2',
                'symbol': 'BTC',
                'quantity': Decimal('0.002'),
                'timestamp': datetime(2022, 1, 2),
                'transaction_type': CryptoTransactionType.TRANSFER_OUT
            }
        ]

    def test_generate_transaction_fingerprint(self, deduplication_service):
        """Test transaction fingerprint generation."""
        tx_data = {
            'symbol': 'BTC',
            'timestamp': datetime(2022, 1, 1),
            'quantity': Decimal('0.001'),
            'transaction_type': CryptoTransactionType.TRANSFER_IN,
            'exchange': 'Bitcoin Blockchain',
            'transaction_hash': 'test_hash'
        }
        portfolio_id = 1

        fingerprint1 = deduplication_service.generate_transaction_fingerprint(tx_data, portfolio_id)
        fingerprint2 = deduplication_service.generate_transaction_fingerprint(tx_data, portfolio_id)

        # Same data should generate same fingerprint
        assert fingerprint1 == fingerprint2

        # Different data should generate different fingerprint
        tx_data_modified = tx_data.copy()
        tx_data_modified['quantity'] = Decimal('0.002')
        fingerprint3 = deduplication_service.generate_transaction_fingerprint(tx_data_modified, portfolio_id)
        assert fingerprint1 != fingerprint3

        # Fingerprint should be a valid SHA256 hash
        assert len(fingerprint1) == 64
        assert all(c in '0123456789abcdef' for c in fingerprint1.lower())

    def test_is_duplicate_transaction(self, deduplication_service):
        """Test duplicate transaction detection."""
        portfolio_id = 1
        tx_hash = 'test_tx_hash'

        # Initially should not be a duplicate
        assert not deduplication_service.is_duplicate_transaction(portfolio_id, tx_hash)

        # Add the hash
        deduplication_service.add_transaction_hash(portfolio_id, tx_hash)

        # Now should be detected as duplicate
        assert deduplication_service.is_duplicate_transaction(portfolio_id, tx_hash)

    def test_add_transaction_hash(self, deduplication_service):
        """Test adding transaction hash."""
        portfolio_id = 1
        tx_hash = 'test_tx_hash'

        # Add hash
        deduplication_service.add_transaction_hash(portfolio_id, tx_hash)

        # Verify it was added
        assert tx_hash in deduplication_service.get_portfolio_transaction_hashes(portfolio_id)

    def test_add_transaction_hashes_bulk(self, deduplication_service):
        """Test bulk addition of transaction hashes."""
        portfolio_id = 1
        tx_hashes = ['tx_1', 'tx_2', 'tx_3']

        # Add hashes in bulk
        added_count = deduplication_service.add_transaction_hashes_bulk(portfolio_id, tx_hashes)

        assert added_count == 3
        all_hashes = deduplication_service.get_portfolio_transaction_hashes(portfolio_id)
        for tx_hash in tx_hashes:
            assert tx_hash in all_hashes

        # Test adding some duplicates
        new_hashes = ['tx_3', 'tx_4']  # tx_3 is duplicate
        added_count = deduplication_service.add_transaction_hashes_bulk(portfolio_id, new_hashes)
        assert added_count == 1  # Only tx_4 should be new

    def test_filter_duplicate_transactions(self, deduplication_service, sample_transactions):
        """Test filtering duplicate transactions."""
        portfolio_id = 1

        # Add some existing hashes
        deduplication_service.add_transaction_hash(portfolio_id, 'tx_hash_1')

        # Filter transactions
        unique_txs, duplicate_hashes = deduplication_service.filter_duplicate_transactions(
            portfolio_id, sample_transactions
        )

        # Should have 1 unique transaction and 1 duplicate
        assert len(unique_txs) == 1
        assert len(duplicate_hashes) == 1
        assert duplicate_hashes[0] == 'tx_hash_1'
        assert unique_txs[0]['transaction_hash'] == 'tx_hash_2'

    def test_calculate_transaction_similarity(self, deduplication_service):
        """Test transaction similarity calculation."""
        # Identical transactions should have high similarity
        tx1 = {
            'symbol': 'BTC',
            'timestamp': datetime(2022, 1, 1, 12, 0, 0),
            'quantity': Decimal('0.001'),
            'transaction_type': CryptoTransactionType.TRANSFER_IN,
            'exchange': 'Bitcoin Blockchain',
            'transaction_hash': 'same_hash'
        }
        tx2 = tx1.copy()

        similarity = deduplication_service._calculate_transaction_similarity(tx1, tx2)
        assert similarity >= 0.8  # Should be very high for identical transactions

        # Different transactions should have lower similarity
        tx3 = {
            'symbol': 'ETH',  # Different symbol
            'timestamp': datetime(2022, 1, 1, 12, 0, 0),
            'quantity': Decimal('0.001'),
            'transaction_type': CryptoTransactionType.TRANSFER_IN,
            'exchange': 'Bitcoin Blockchain',
            'transaction_hash': 'different_hash'
        }

        similarity = deduplication_service._calculate_transaction_similarity(tx1, tx3)
        assert similarity < 0.8  # Should be lower for different transactions

    def test_clear_portfolio_cache(self, deduplication_service):
        """Test clearing portfolio cache."""
        portfolio_id = 1
        tx_hash = 'test_tx_hash'

        # Add data to cache
        deduplication_service.add_transaction_hash(portfolio_id, tx_hash)
        assert portfolio_id in deduplication_service._memory_cache

        # Clear cache
        deduplication_service.clear_portfolio_cache(portfolio_id)

        # Verify cache is cleared
        assert portfolio_id not in deduplication_service._memory_cache

    def test_get_cache_stats(self, deduplication_service):
        """Test getting cache statistics."""
        # Add some data to cache
        deduplication_service.add_transaction_hash(1, 'tx_1')
        deduplication_service.add_transaction_hash(2, 'tx_2')

        stats = deduplication_service.get_cache_stats()

        assert 'memory_cache_size' in stats
        assert 'memory_cache_portfolios' in stats
        assert 'redis_connected' in stats
        assert 'total_cached_hashes' in stats
        assert stats['memory_cache_size'] == 2
        assert set(stats['memory_cache_portfolios']) == {1, 2}
        assert stats['total_cached_hashes'] == 2


@pytest.mark.integration
class TestBlockchainIntegration:
    """Integration tests for blockchain services."""

    @pytest.fixture
    def portfolio_data(self):
        """Sample crypto portfolio data."""
        return {
            'id': 1,
            'name': 'Test Bitcoin Portfolio',
            'wallet_address': '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'
        }

    def test_blockchain_sync_workflow(self):
        """Test the complete blockchain sync workflow."""
        # This would be an integration test that tests the entire workflow
        # from fetching transactions to storing them in the database

        # Mock the blockchain fetcher
        with patch('app.services.blockchain_fetcher.blockchain_fetcher.fetch_transactions') as mock_fetch:
            mock_fetch.return_value = {
                'status': 'success',
                'transactions': [
                    {
                        'transaction_hash': 'test_tx_1',
                        'symbol': 'BTC',
                        'quantity': Decimal('0.001'),
                        'price_at_execution': Decimal('50000'),
                        'total_amount': Decimal('50'),
                        'currency': CryptoCurrency.USD,
                        'transaction_type': CryptoTransactionType.TRANSFER_IN,
                        'timestamp': datetime.utcnow(),
                        'exchange': 'Bitcoin Blockchain'
                    }
                ]
            }

            # Mock the deduplication service
            with patch('app.services.blockchain_deduplication.blockchain_deduplication.get_portfolio_transaction_hashes') as mock_hashes:
                mock_hashes.return_value = set()

                # Mock the price prefetching function to return price data
                with patch('app.tasks.blockchain_sync._prefetch_prices_for_dates') as mock_prefetch_prices:
                    # Return a dict mapping date to price
                    mock_prefetch_prices.return_value = {
                        datetime.utcnow().date(): Decimal('50000')
                    }

                    # Import the sync function
                    from app.tasks.blockchain_sync import sync_single_wallet
                    from app.database import SyncSessionLocal

                    # Create a mock database session
                    mock_db = Mock()
                    mock_portfolio = Mock()
                    mock_portfolio.base_currency.value = 'USD'
                    mock_portfolio.wallet_last_sync_time = None
                    mock_result = Mock()
                    mock_result.scalar_one_or_none.return_value = mock_portfolio
                    mock_db.execute.return_value = mock_result
                    mock_db.add.return_value = None
                    mock_db.commit.return_value = None

                    # Test the sync function
                    result = sync_single_wallet(
                        wallet_address='1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa',
                        portfolio_id=1,
                        db_session=mock_db,
                        max_transactions=50,
                        days_back=7
                    )

                    # Verify the result
                    assert result['status'] == 'success'
                    assert result['transactions_added'] >= 0
                    assert result['transactions_skipped'] >= 0
                    assert result['transactions_failed'] == 0

    def test_api_configuration(self):
        """Test that API configuration is loaded correctly."""
        from app.services.blockchain_fetcher import blockchain_fetcher

        # Verify that blockchain.info API is configured
        assert blockchain_fetcher.api_config is not None
        assert 'base_url' in blockchain_fetcher.api_config
        assert 'rate_limit' in blockchain_fetcher.api_config
        assert 'timeout' in blockchain_fetcher.api_config
        assert 'max_retries' in blockchain_fetcher.api_config

        # Verify configuration values for blockchain.info
        assert str(blockchain_fetcher.api_config['base_url']) == str(settings.blockchain_com_api_url)

        # Verify rate limits are configured
        assert blockchain_fetcher.api_config['rate_limit'] > 0
        assert blockchain_fetcher.api_config['timeout'] > 0
        assert blockchain_fetcher.api_config['max_retries'] > 0

    def test_error_handling_workflow(self):
        """Test error handling in the blockchain workflow."""
        # Test what happens when all APIs fail
        with patch('app.services.blockchain_fetcher.blockchain_fetcher.fetch_transactions') as mock_fetch:
            mock_fetch.side_effect = Exception("All APIs failed")

            from app.tasks.blockchain_sync import sync_single_wallet
            mock_db = Mock()

            result = sync_single_wallet(
                wallet_address='1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa',
                portfolio_id=1,
                db_session=mock_db,
                max_transactions=50,
                days_back=7
            )

            # Should handle the error gracefully
            assert result['status'] == 'error'
            assert 'error' in result
            assert result['transactions_added'] == 0


if __name__ == '__main__':
    pytest.main([__file__])