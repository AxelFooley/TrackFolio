"""
Bitcoin blockchain transaction fetcher service.

This service fetches Bitcoin transactions from blockchain APIs
and converts them to the existing CryptoTransaction format.
"""
import hashlib
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
import logging
import requests
import json
import redis
import pickle
from urllib.parse import urljoin

from app.config import settings
from app.models.crypto import CryptoTransaction, CryptoTransactionType, CryptoCurrency

logger = logging.getLogger(__name__)


class BlockchainFetcherService:
    """
    Service for fetching Bitcoin blockchain transactions.

    Supports multiple blockchain APIs with automatic fallback:
    1. Blockstream API (primary) - Reliable, free, no API key required
    2. Blockchain.com API (fallback) - Good backup option
    3. BlockCypher API (fallback) - Alternative with rate limits
    """

    def __init__(self):
        """Initialize blockchain fetcher with Redis caching and configuration."""
        self._sessions = {}
        self._last_request_time = {}
        self._redis_client = None

        # Initialize API configuration from settings
        self.APIS = {
            'blockstream': {
                'base_url': settings.blockstream_api_url,
                'rate_limit': settings.blockchain_rate_limit_requests_per_second,
                'timeout': settings.blockchain_request_timeout_seconds,
                'max_retries': settings.blockchain_max_retries
            },
            'blockchain_com': {
                'base_url': settings.blockchain_com_api_url,
                'rate_limit': settings.blockchain_rate_limit_requests_per_second * 0.5,  # More conservative
                'timeout': settings.blockchain_request_timeout_seconds,
                'max_retries': settings.blockchain_max_retries
            },
            'blockcypher': {
                'base_url': settings.blockcypher_api_url,
                'rate_limit': settings.blockchain_rate_limit_requests_per_second * 0.33,  # Much more conservative
                'timeout': settings.blockchain_request_timeout_seconds,
                'max_retries': settings.blockchain_max_retries - 1
            }
        }

        # Initialize Redis connection
        try:
            self._redis_client = redis.from_url(settings.redis_url, decode_responses=False)
            self._redis_client.ping()
            logger.info("Blockchain fetcher: Connected to Redis")
        except Exception as e:
            logger.warning(f"Blockchain fetcher: Could not connect to Redis: {e}. Caching will be disabled.")
            self._redis_client = None

        # Initialize HTTP sessions for each API
        for api_name, config in self.APIS.items():
            session = requests.Session()
            session.timeout = config['timeout']
            self._sessions[api_name] = session
            self._last_request_time[api_name] = 0

    # Cache TTL (seconds) - from configuration
    TRANSACTION_CACHE_TTL = settings.blockchain_transaction_cache_ttl
    ADDRESS_CACHE_TTL = settings.blockchain_address_cache_ttl

    # Transaction limits
    MAX_TRANSACTIONS_PER_REQUEST = 50  # Blockstream limit
    MAX_HISTORY_DAYS = 365  # Don't fetch more than 1 year of history by default

    def _get_cache_key(self, prefix: str, *args) -> str:
        """Generate cache key for Redis."""
        return f"blockchain:{prefix}:{':'.join(str(arg) for arg in args)}"

    def _cache_get(self, key: str) -> Optional[Any]:
        """Get data from Redis cache."""
        if not self._redis_client:
            return None

        try:
            cached_data = self._redis_client.get(key)
            if cached_data:
                return pickle.loads(cached_data)
        except Exception as e:
            logger.warning(f"Error getting data from cache: {e}")
        return None

    def _cache_set(self, key: str, data: Any, ttl: int) -> None:
        """Set data in Redis cache."""
        if not self._redis_client:
            return

        try:
            serialized_data = pickle.dumps(data)
            self._redis_client.setex(key, ttl, serialized_data)
        except Exception as e:
            logger.warning(f"Error setting data in cache: {e}")

    def _rate_limit(self, api_name: str) -> None:
        """Implement rate limiting for specific API."""
        current_time = time.time()
        api_config = self.APIS[api_name]

        time_since_last = current_time - self._last_request_time[api_name]
        rate_limit_delay = 1.0 / api_config['rate_limit']

        if time_since_last < rate_limit_delay:
            sleep_time = rate_limit_delay - time_since_last
            logger.debug(f"Rate limiting {api_name}: sleeping for {sleep_time:.3f} seconds")
            time.sleep(sleep_time)

        self._last_request_time[api_name] = time.time()

    def _make_request(self, api_name: str, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Make HTTP request to blockchain API with retry logic.

        Args:
            api_name: Name of the API to use
            endpoint: API endpoint
            params: Query parameters

        Returns:
            JSON response data or None if failed
        """
        api_config = self.APIS[api_name]
        session = self._sessions[api_name]

        url = urljoin(api_config['base_url'], endpoint)

        for attempt in range(api_config['max_retries']):
            try:
                # Rate limiting
                self._rate_limit(api_name)

                logger.debug(f"{api_name} API request: {url} (attempt {attempt + 1})")

                response = session.get(url, params=params)
                response.raise_for_status()

                data = response.json()
                logger.debug(f"{api_name} API response received successfully")
                return data

            except requests.exceptions.RequestException as e:
                wait_time = 2 ** attempt  # Exponential backoff
                logger.warning(
                    f"{api_name} API request failed (attempt {attempt + 1}/{api_config['max_retries']}): {e}. "
                    f"Retrying in {wait_time} seconds..."
                )

                if attempt < api_config['max_retries'] - 1:
                    time.sleep(wait_time)
                else:
                    logger.error(f"{api_name} API request failed after {api_config['max_retries']} attempts: {e}")
                    return None

            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode {api_name} API response: {e}")
                return None

    def _validate_bitcoin_address(self, address: str) -> bool:
        """
        Validate Bitcoin address format.

        Args:
            address: Bitcoin address to validate

        Returns:
            True if valid, False otherwise
        """
        # Basic validation for Bitcoin addresses
        # This is a simplified validation - in production, you might want more sophisticated validation
        try:
            # Check length (Bitcoin addresses are typically 26-62 characters)
            if not (26 <= len(address) <= 62):
                return False

            # Check basic address patterns and character sets
            if address.startswith('1') or address.startswith('3'):
                # Legacy/SegWit addresses - use Base58 character set
                valid_chars = set('123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz')
                if not all(c in valid_chars for c in address):
                    return False
                return True
            elif address.startswith('bc1'):
                # Bech32 addresses - use different character set (lowercase only + numbers)
                # Remove the 'bc1' prefix for character validation
                bech32_part = address[3:]  # Remove 'bc1' prefix
                valid_chars = set('023456789acdefghjklmnpqrstuvwxyzqpzry9x8gf2tvdw0s3jn54khce6mua7l')
                if not all(c in valid_chars for c in bech32_part):
                    return False
                return True

            return False

        except Exception as e:
            logger.warning(f"Error validating Bitcoin address {address}: {e}")
            return False

    def _generate_transaction_hash(self, tx_data: Dict) -> str:
        """
        Generate a unique hash for transaction deduplication.

        Args:
            tx_data: Transaction data dictionary

        Returns:
            SHA256 hash of key transaction fields
        """
        # Create a string with key fields for hashing
        hash_string = f"{tx_data.get('txid', '')}{tx_data.get('timestamp', '')}{tx_data.get('value', '')}{tx_data.get('address', '')}"

        return hashlib.sha256(hash_string.encode()).hexdigest()

    def _detect_transaction_type(self, tx_data: Dict, wallet_address: str) -> CryptoTransactionType:
        """
        Detect transaction type based on transaction flow.

        Args:
            tx_data: Transaction data from blockchain API
            wallet_address: The wallet address being tracked

        Returns:
            Detected transaction type
        """
        # This is a simplified detection logic
        # In a real implementation, you'd want more sophisticated analysis

        # For now, we'll classify based on the direction of Bitcoin flow
        # Positive value = incoming (transfer_in or buy)
        # Negative value = outgoing (transfer_out or sell)

        value = tx_data.get('value', 0)

        if value > 0:
            return CryptoTransactionType.TRANSFER_IN
        elif value < 0:
            return CryptoTransactionType.TRANSFER_OUT
        else:
            # Default to transfer_in for zero-value transactions
            return CryptoTransactionType.TRANSFER_IN

    def _convert_blockstream_transaction(self, tx_data: Dict, wallet_address: str) -> Optional[Dict]:
        """
        Convert Blockstream transaction format to internal format.

        Args:
            tx_data: Transaction data from Blockstream API
            wallet_address: The wallet address being tracked

        Returns:
            Formatted transaction data or None if conversion failed
        """
        try:
            # Extract relevant data
            txid = tx_data.get('txid')
            status = tx_data.get('status', {})
            block_time = status.get('block_time', 0)

            if not txid or not block_time:
                logger.warning(f"Missing required fields in transaction data: {tx_data}")
                return None

            # Convert timestamp to datetime
            timestamp = datetime.fromtimestamp(block_time)

            # Calculate the value for this wallet address
            # This is simplified - you'd want to properly parse inputs/outputs
            total_value = 0
            for vout in tx_data.get('vout', []):
                # Check if this output belongs to our wallet
                scriptpubkey = vout.get('scriptpubkey', '')
                # This is simplified - proper address detection would require script parsing
                # For now, we'll use the transaction value
                total_value += vout.get('value', 0)

            # Convert from BTC to satoshis for precision
            value_satoshis = int(total_value * 100000000)
            quantity = Decimal(str(total_value))

            # For now, we'll estimate the price based on the transaction date
            # In a real implementation, you'd fetch historical price data
            estimated_price = Decimal("1.0")  # Placeholder

            # Detect transaction type
            tx_type = self._detect_transaction_type(tx_data, wallet_address)

            return {
                'transaction_hash': txid,
                'timestamp': timestamp,
                'transaction_type': tx_type,
                'symbol': 'BTC',
                'quantity': quantity,
                'price_at_execution': estimated_price,
                'total_amount': quantity * estimated_price,
                'currency': CryptoCurrency.USD,
                'fee': Decimal("0"),
                'fee_currency': None,
                'exchange': 'Bitcoin Blockchain',
                'notes': f'Transaction {tx_type.value} detected from blockchain data',
                'raw_data': tx_data  # Store raw data for debugging
            }

        except Exception as e:
            logger.error(f"Error converting Blockstream transaction: {e}")
            return None

    def _convert_blockchaincom_transaction(self, tx_data: Dict, wallet_address: str) -> Optional[Dict]:
        """
        Convert Blockchain.com transaction format to internal format.

        Args:
            tx_data: Transaction data from Blockchain.com API
            wallet_address: The wallet address being tracked

        Returns:
            Formatted transaction data or None if conversion failed
        """
        try:
            # Extract relevant data
            tx_hash = tx_data.get('hash')
            timestamp_ms = tx_data.get('time', 0) * 1000  # Convert to milliseconds
            result = tx_data.get('result', 0)  # Net change in wallet balance for this transaction

            if not tx_hash or not timestamp_ms:
                logger.warning(f"Missing required fields in transaction data: {tx_data}")
                return None

            # Convert timestamp to datetime
            timestamp = datetime.fromtimestamp(timestamp_ms / 1000)

            # Calculate the actual amount received/sent by our wallet
            # Look through outputs to find those belonging to our wallet
            wallet_total = 0
            for output in tx_data.get('out', []):
                if output.get('addr') == wallet_address:
                    wallet_total += output.get('value', 0)

            # Convert from satoshis to BTC
            quantity = Decimal(str(abs(wallet_total))) / Decimal('100000000')

            # Detect transaction type based on result (positive = incoming, negative = outgoing)
            if result > 0:
                tx_type = CryptoTransactionType.TRANSFER_IN
            elif result < 0:
                tx_type = CryptoTransactionType.TRANSFER_OUT
            else:
                # Zero result - check if we have outputs (likely incoming)
                tx_type = CryptoTransactionType.TRANSFER_IN if wallet_total > 0 else CryptoTransactionType.TRANSFER_OUT

            # For now, we'll estimate the price
            estimated_price = Decimal("1.0")  # Placeholder

            return {
                'transaction_hash': tx_hash,
                'timestamp': timestamp,
                'transaction_type': tx_type,
                'symbol': 'BTC',
                'quantity': quantity,
                'price_at_execution': estimated_price,
                'total_amount': quantity * estimated_price,
                'currency': CryptoCurrency.USD,
                'fee': Decimal("0"),
                'fee_currency': None,
                'exchange': 'Bitcoin Blockchain',
                'notes': f'Transaction {tx_type.value} detected from blockchain data',
                'raw_data': tx_data  # Store raw data for debugging
            }

        except Exception as e:
            logger.error(f"Error converting Blockchain.com transaction: {e}")
            return None

    def _convert_blockcypher_transaction(self, tx_data: Dict, wallet_address: str) -> Optional[Dict]:
        """
        Convert BlockCypher transaction format to internal format.

        Args:
            tx_data: Transaction data from BlockCypher API
            wallet_address: The wallet address being tracked

        Returns:
            Formatted transaction data or None if conversion failed
        """
        try:
            # Extract relevant data
            tx_hash = tx_data.get('hash')
            confirmed = tx_data.get('confirmed', '')
            total_value = tx_data.get('total', 0)
            fees = tx_data.get('fees', 0)

            if not tx_hash:
                logger.warning(f"Missing required fields in transaction data: {tx_data}")
                return None

            # Convert timestamp to datetime
            if confirmed:
                timestamp = datetime.fromisoformat(confirmed.replace('Z', '+00:00'))
            else:
                timestamp = datetime.utcnow()

            # Convert from satoshis to BTC
            quantity = Decimal(str(total_value)) / Decimal('100000000')
            fee_amount = Decimal(str(fees)) / Decimal('100000000')

            # For now, we'll estimate the price
            estimated_price = Decimal("1.0")  # Placeholder

            # Detect transaction type
            tx_type = self._detect_transaction_type(tx_data, wallet_address)

            return {
                'transaction_hash': tx_hash,
                'timestamp': timestamp,
                'transaction_type': tx_type,
                'symbol': 'BTC',
                'quantity': abs(quantity),
                'price_at_execution': estimated_price,
                'total_amount': abs(quantity) * estimated_price,
                'currency': CryptoCurrency.USD,
                'fee': fee_amount,
                'fee_currency': 'BTC',
                'exchange': 'Bitcoin Blockchain',
                'notes': f'Transaction {tx_type.value} detected from blockchain data',
                'raw_data': tx_data  # Store raw data for debugging
            }

        except Exception as e:
            logger.error(f"Error converting BlockCypher transaction: {e}")
            return None

    def fetch_transactions(
        self,
        wallet_address: str,
        portfolio_id: int,
        max_transactions: int = 100,
        days_back: int = None
    ) -> Dict[str, Any]:
        """
        Fetch transactions for a Bitcoin wallet address.

        Args:
            wallet_address: Bitcoin wallet address to fetch transactions for
            portfolio_id: Portfolio ID to associate transactions with
            max_transactions: Maximum number of transactions to fetch
            days_back: Number of days to look back (default: 30)

        Returns:
            Dictionary with fetched transactions and metadata
        """
        if not self._validate_bitcoin_address(wallet_address):
            raise ValueError(f"Invalid Bitcoin address: {wallet_address}")

        if days_back is None:
            days_back = 30

        logger.info(f"Fetching transactions for Bitcoin address {wallet_address} (max: {max_transactions}, days: {days_back})")

        # Check cache first
        cache_key = self._get_cache_key("transactions", wallet_address, max_transactions, days_back)
        cached_result = self._cache_get(cache_key)
        if cached_result:
            logger.info(f"Cache hit for wallet transactions: {wallet_address}")
            return cached_result

        # Try different APIs in order
        apis_to_try = ['blockstream', 'blockchain_com', 'blockcypher']

        for api_name in apis_to_try:
            try:
                logger.info(f"Trying {api_name} API for wallet {wallet_address}")
                result = self._fetch_transactions_from_api(
                    api_name, wallet_address, portfolio_id, max_transactions, days_back
                )

                if result and result.get('transactions'):
                    logger.info(f"Successfully fetched {len(result['transactions'])} transactions using {api_name} API")

                    # Cache the result
                    self._cache_set(cache_key, result, self.TRANSACTION_CACHE_TTL)

                    return result

            except Exception as e:
                logger.warning(f"Failed to fetch transactions using {api_name} API: {e}")
                continue

        # All APIs failed
        error_msg = f"Failed to fetch transactions from all blockchain APIs for wallet {wallet_address}"
        logger.error(error_msg)
        raise Exception(error_msg)

    def _fetch_transactions_from_api(
        self,
        api_name: str,
        wallet_address: str,
        portfolio_id: int,
        max_transactions: int,
        days_back: int
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch transactions from a specific blockchain API.

        Args:
            api_name: Name of the API to use
            wallet_address: Bitcoin wallet address
            portfolio_id: Portfolio ID
            max_transactions: Maximum number of transactions to fetch
            days_back: Number of days to look back

        Returns:
            Dictionary with transactions and metadata
        """
        if api_name == 'blockstream':
            return self._fetch_from_blockstream(wallet_address, portfolio_id, max_transactions, days_back)
        elif api_name == 'blockchain_com':
            return self._fetch_from_blockchain_com(wallet_address, portfolio_id, max_transactions, days_back)
        elif api_name == 'blockcypher':
            return self._fetch_from_blockcypher(wallet_address, portfolio_id, max_transactions, days_back)
        else:
            raise ValueError(f"Unknown API: {api_name}")

    def _fetch_from_blockstream(
        self,
        wallet_address: str,
        portfolio_id: int,
        max_transactions: int,
        days_back: int
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch transactions using Blockstream API.

        Args:
            wallet_address: Bitcoin wallet address
            portfolio_id: Portfolio ID
            max_transactions: Maximum number of transactions
            days_back: Number of days to look back

        Returns:
            Dictionary with transactions and metadata
        """
        try:
            # Calculate date threshold
            date_threshold = datetime.utcnow() - timedelta(days=days_back)
            threshold_timestamp = int(date_threshold.timestamp())

            transactions = []
            last_txid = None

            while len(transactions) < max_transactions:
                # Build request URL
                endpoint = f"/address/{wallet_address}/txs"
                params = {
                    'limit': min(self.MAX_TRANSACTIONS_PER_REQUEST, max_transactions - len(transactions))
                }

                if last_txid:
                    params['last_seen_txid'] = last_txid

                # Make request
                data = self._make_request('blockstream', endpoint, params)

                if not data:
                    break

                # Process transactions
                for tx_data in data:
                    # Check transaction timestamp
                    if tx_data.get('status', {}).get('block_time', 0) < threshold_timestamp:
                        return self._build_result(transactions, 'success', 'Fetched all transactions within date range')

                    # Convert transaction format
                    converted_tx = self._convert_blockstream_transaction(tx_data, wallet_address)

                    if converted_tx:
                        # Add portfolio ID
                        converted_tx['portfolio_id'] = portfolio_id

                        # Add to results
                        transactions.append(converted_tx)

                        if len(transactions) >= max_transactions:
                            break

                # Check if there are more transactions
                if len(data) < self.MAX_TRANSACTIONS_PER_REQUEST:
                    break

                # Set last_txid for pagination
                last_txid = data[-1]['txid']

            return self._build_result(transactions, 'success', f'Fetched {len(transactions)} transactions')

        except Exception as e:
            logger.error(f"Error fetching from Blockstream API: {e}")
            return self._build_result([], 'error', str(e))

    def _fetch_from_blockchain_com(
        self,
        wallet_address: str,
        portfolio_id: int,
        max_transactions: int,
        days_back: int
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch transactions using Blockchain.info API.

        Args:
            wallet_address: Bitcoin wallet address
            portfolio_id: Portfolio ID
            max_transactions: Maximum number of transactions
            days_back: Number of days to look back

        Returns:
            Dictionary with transactions and metadata
        """
        try:
            # Calculate date threshold
            date_threshold = datetime.utcnow() - timedelta(days=days_back)
            threshold_timestamp = int(date_threshold.timestamp() * 1000)  # Blockchain.info uses milliseconds

            # Build request URL - use the correct rawaddr endpoint structure
            endpoint = f"/rawaddr/{wallet_address}"
            params = {
                'limit': min(max_transactions, 50)  # Blockchain.info has a 50 transaction limit
            }

            # Make request
            data = self._make_request('blockchain_com', endpoint, params)

            if not data:
                return self._build_result([], 'error', 'No data received from Blockchain.info API')

            transactions = []

            # Process transactions
            for tx_data in data.get('txs', []):
                # Check transaction timestamp
                if tx_data.get('time', 0) * 1000 < threshold_timestamp:
                    continue

                # Convert transaction format
                converted_tx = self._convert_blockchaincom_transaction(tx_data, wallet_address)

                if converted_tx:
                    # Add portfolio ID
                    converted_tx['portfolio_id'] = portfolio_id

                    # Add to results
                    transactions.append(converted_tx)

                    if len(transactions) >= max_transactions:
                        break

            return self._build_result(transactions, 'success', f'Fetched {len(transactions)} transactions')

        except Exception as e:
            logger.error(f"Error fetching from Blockchain.info API: {e}")
            return self._build_result([], 'error', str(e))

    def _fetch_from_blockcypher(
        self,
        wallet_address: str,
        portfolio_id: int,
        max_transactions: int,
        days_back: int
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch transactions using BlockCypher API.

        Args:
            wallet_address: Bitcoin wallet address
            portfolio_id: Portfolio ID
            max_transactions: Maximum number of transactions
            days_back: Number of days to look back

        Returns:
            Dictionary with transactions and metadata
        """
        try:
            # Calculate date threshold
            date_threshold = datetime.utcnow() - timedelta(days=days_back)

            # Build request URL
            endpoint = f"/addrs/{wallet_address}/full"
            params = {
                'limit': min(max_transactions, 50),  # BlockCypher has a 50 transaction limit
                'before': date_threshold.isoformat()
            }

            # Make request
            data = self._make_request('blockcypher', endpoint, params)

            if not data:
                return self._build_result([], 'error', 'No data received from BlockCypher API')

            transactions = []

            # Process transactions
            for tx_data in data.get('txs', []):
                # Convert transaction format
                converted_tx = self._convert_blockcypher_transaction(tx_data, wallet_address)

                if converted_tx:
                    # Add portfolio ID
                    converted_tx['portfolio_id'] = portfolio_id

                    # Add to results
                    transactions.append(converted_tx)

                    if len(transactions) >= max_transactions:
                        break

            return self._build_result(transactions, 'success', f'Fetched {len(transactions)} transactions')

        except Exception as e:
            logger.error(f"Error fetching from BlockCypher API: {e}")
            return self._build_result([], 'error', str(e))

    def _build_result(
        self,
        transactions: List[Dict],
        status: str,
        message: str
    ) -> Dict[str, Any]:
        """
        Build result dictionary for API responses.

        Args:
            transactions: List of transaction dictionaries
            status: Status of the operation
            message: Message describing the result

        Returns:
            Result dictionary
        """
        return {
            'status': status,
            'message': message,
            'transactions': transactions,
            'count': len(transactions),
            'timestamp': datetime.utcnow()
        }

    def test_api_connection(self) -> Dict[str, bool]:
        """
        Test connection to all blockchain APIs.

        Returns:
            Dictionary with API names as keys and connection status as values
        """
        results = {}

        for api_name in self.APIS.keys():
            try:
                if api_name == 'blockstream':
                    # Test with a simple request
                    data = self._make_request('blockstream', '/blocks')
                    results[api_name] = data is not None
                elif api_name == 'blockchain_com':
                    # Test with a simple request using the correct rawaddr endpoint
                    data = self._make_request('blockchain_com', '/rawaddr/1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa')  # Satoshi's address
                    results[api_name] = data is not None
                elif api_name == 'blockcypher':
                    # Test with a simple request
                    data = self._make_request('blockcypher', '/blocks')
                    results[api_name] = data is not None

            except Exception as e:
                logger.error(f"Error testing {api_name} API connection: {e}")
                results[api_name] = False

        logger.info(f"API connection test results: {results}")
        return results


# Create a singleton instance
blockchain_fetcher = BlockchainFetcherService()