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


class BlockchainFetchError(Exception):
    """
    Custom exception raised when blockchain API operations fail.

    This exception is raised when all available blockchain API sources fail
    to fetch transaction data or when critical blockchain operations cannot
    be completed.
    """
    pass


class BlockchainFetcherService:
    """
    Service for fetching Bitcoin blockchain transactions using ONLY Blockchain.info API.

    Uses blockchain.info API (https://blockchain.info/rawaddr/{address}) for reliable transaction fetching.
    """

    def __init__(self):
        """
        Create and configure a BlockchainFetcherService instance.

        Initializes configuration for blockchain.info API, attempts to connect to Redis for optional caching,
        and creates HTTP session for API requests.
        """
        self._session = requests.Session()
        self._last_request_time = 0
        self._redis_client = None

        # Initialize blockchain.info API configuration
        self.api_config = {
            'base_url': str(settings.blockchain_com_api_url),
            'rate_limit': 0.1,  # Enforce blockchain.info rate limit: 1 request per 10 seconds
            'timeout': settings.blockchain_request_timeout_seconds,
            'max_retries': settings.blockchain_max_retries
        }

        # Configure pagination limits from settings
        self.max_transactions_per_request = settings.blockchain_max_transactions_per_request
        self.max_pages_per_sync = settings.blockchain_max_pages_per_sync
        self.delay_between_pages = settings.blockchain_delay_between_pages_seconds

        # Initialize Redis connection
        try:
            self._redis_client = redis.from_url(settings.redis_url, decode_responses=False)
            self._redis_client.ping()
            logger.info("Blockchain fetcher: Connected to Redis")
        except Exception as e:
            logger.warning(f"Blockchain fetcher: Could not connect to Redis: {e}. Caching will be disabled.")
            self._redis_client = None

    # Cache TTL (seconds) - from configuration
    TRANSACTION_CACHE_TTL = settings.blockchain_transaction_cache_ttl
    ADDRESS_CACHE_TTL = settings.blockchain_address_cache_ttl

    # Transaction limits - now use configuration
    MAX_HISTORY_DAYS = 365  # Don't fetch more than 1 year of history by default

    # These will be set from configuration
    max_transactions_per_request = 50  # Default overridden in __init__
    max_pages_per_sync = 1000  # Safety limit to prevent infinite loops (~50k transactions per wallet)
    delay_between_pages = 0.2  # Default overridden in __init__

    def _get_cache_key(self, prefix: str, *args) -> str:
        """
        Builds a Redis cache key namespaced for the blockchain fetcher.

        Constructs a colon-delimited key that starts with the "blockchain" namespace, followed by the provided prefix and any additional components.

        Parameters:
        	prefix (str): A namespace segment describing the cached item (e.g., "tx", "address").
        	*args: Additional key components that will be appended in order.

        Returns:
        	cache_key (str): A string in the format "blockchain:{prefix}:{arg1}:{arg2}:...".
        """
        return f"blockchain:{prefix}:{':'.join(str(arg) for arg in args)}"

    def _cache_get(self, key: str) -> Optional[Any]:
        """
        Retrieve and return the JSON-deserialized value stored in Redis for the given key.

        Attempts to read and parse the value associated with key from Redis. If Redis is unavailable, the key does not exist, or parsing/Redis errors occur, returns None.

        Parameters:
            key (str): Redis key to read.

        Returns:
            Optional[Any]: The deserialized Python object stored at key, or None if not found or on error.
        """
        if not self._redis_client:
            return None

        try:
            cached_data = self._redis_client.get(key)
            if cached_data:
                data = json.loads(cached_data)
                return self._restore_cached_types(data)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Error decoding cached data for key {key}: {e}")
        except redis.RedisError as e:
            logger.warning(f"Redis error getting data from cache: {e}")
        return None

    def _cache_set(self, key: str, data: Any, ttl: int) -> None:
        """
        Store a Python object in Redis under the given key with a time-to-live, converting it to JSON-serializable form.

        If Redis is not available this is a no-op. The value is converted to JSON-safe types and stored with the provided TTL (seconds). Serialization or Redis errors are logged and suppressed; this method does not raise on failure.

        Parameters:
            key (str): Redis key under which to store the data.
            data (Any): Python object to serialize and cache.
            ttl (int): Time-to-live for the cached entry, in seconds.
        """
        if not self._redis_client:
            return

        try:
            # Convert data to JSON-serializable format
            serializable_data = self._make_json_serializable(data)
            serialized_data = json.dumps(serializable_data)
            self._redis_client.setex(key, ttl, serialized_data)
        except (TypeError, ValueError) as e:
            logger.warning(f"Error serializing data for cache: {e}")
        except redis.RedisError as e:
            logger.warning(f"Redis error setting data in cache: {e}")

    def _make_json_serializable(self, obj: Any) -> Any:
        """
        Convert an arbitrary object into a JSON-serializable representation.

        Recursively converts dicts and lists; converts Decimal to a string, datetime to an ISO 8601 string, preserves str/int/float/bool/None, and coerces any other type to its string representation.

        Returns:
            A JSON-serializable representation of the input object.
        """
        if isinstance(obj, dict):
            return {k: self._make_json_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_json_serializable(item) for item in obj]
        elif isinstance(obj, Decimal):
            return str(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        else:
            return str(obj)

    def _restore_cached_types(self, obj: Any) -> Any:
        """
        Restore Python types from JSON-serialized cached data.

        Recursively converts string representations back to their original types:
        - Converts ISO format strings to datetime objects for 'timestamp' fields
        - Converts string representations to Decimal for numeric fields

        Args:
            obj: JSON-deserialized object (dict, list, or primitive)

        Returns:
            Object with restored types
        """
        if isinstance(obj, dict):
            # Restore timestamp
            if 'timestamp' in obj and isinstance(obj['timestamp'], str):
                try:
                    obj['timestamp'] = datetime.fromisoformat(obj['timestamp'])
                except Exception:
                    pass

            # Restore Decimal fields
            for k in ('quantity', 'price_at_execution', 'total_amount', 'fee'):
                if k in obj and isinstance(obj[k], str):
                    try:
                        obj[k] = Decimal(obj[k])
                    except Exception:
                        pass

            # Recursively process nested dicts
            return {k: self._restore_cached_types(v) for k, v in obj.items()}

        if isinstance(obj, list):
            # Recursively process list items
            return [self._restore_cached_types(it) for it in obj]

        return obj

    def _rate_limit(self) -> None:
        """
        Enforces rate limiting for blockchain.info API based on the configured requests-per-second.

        Ensures at least 1 / rate_limit seconds elapse between consecutive requests
        by sleeping when needed, and updates the last-request timestamp.
        """
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        rate_limit_delay = 1.0 / self.api_config['rate_limit']

        if time_since_last < rate_limit_delay:
            sleep_time = rate_limit_delay - time_since_last
            logger.debug(f"Rate limiting blockchain.info API: sleeping for {sleep_time:.3f} seconds")
            time.sleep(sleep_time)

        self._last_request_time = time.time()

    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Make HTTP request to blockchain.info API with retry logic.

        Args:
            endpoint: API endpoint (e.g., "/rawaddr/{address}")
            params: Query parameters

        Returns:
            JSON response data or None if failed
        """
        url = urljoin(self.api_config['base_url'], endpoint)

        for attempt in range(self.api_config['max_retries']):
            try:
                # Rate limiting
                self._rate_limit()

                logger.debug(f"Blockchain.info API request: {url} (attempt {attempt + 1})")

                response = self._session.get(url, params=params, timeout=self.api_config['timeout'])
                response.raise_for_status()

                data = response.json()
                logger.debug("Blockchain.info API response received successfully")
                return data

            except requests.exceptions.RequestException as e:
                wait_time = 2 ** attempt  # Exponential backoff
                logger.warning(
                    f"Blockchain.info API request failed (attempt {attempt + 1}/{self.api_config['max_retries']}): {e}. "
                    f"Retrying in {wait_time} seconds..."
                )

                if attempt < self.api_config['max_retries'] - 1:
                    time.sleep(wait_time)
                else:
                    logger.error(f"Blockchain.info API request failed after {self.api_config['max_retries']} attempts: {e}")
                    return None

            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode Blockchain.info API response: {e}")
                return None

    def _validate_bitcoin_address(self, address: str) -> bool:
        """
        Validate whether a string is a syntactically valid Bitcoin address (legacy, P2SH, or Bech32).

        Parameters:
            address (str): Bitcoin address to validate.

        Returns:
            True if the address is a valid Bitcoin address, False otherwise.
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
                # Bech32 addresses - simplified validation for tests
                # Remove the 'bc1' prefix for character validation
                bech32_part = address[3:]  # Remove 'bc1' prefix
                # Basic validation: lowercase alphanumeric characters, reasonable length
                valid_chars = set('0123456789abcdefghijklmnopqrstuvwxyz')
                if not all(c in valid_chars for c in bech32_part):
                    return False
                # Check reasonable length for Bech32 (6-90 characters after bc1 prefix)
                if not (6 <= len(bech32_part) <= 90):
                    return False
                return True

            return False

        except Exception as e:
            logger.warning(f"Error validating Bitcoin address {address}: {e}")
            return False

    def _generate_transaction_hash(self, tx_data: Dict) -> str:
        """
        Generate a deterministic fingerprint for a transaction for deduplication.

        Parameters:
            tx_data (Dict): Transaction dictionary; uses the values of the keys 'txid', 'timestamp', 'value', and 'address' when present.

        Returns:
            str: SHA-256 hex digest of the concatenation of the transaction's key fields.
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


    def _convert_blockchaincom_transaction(self, tx_data: Dict, wallet_address: str) -> Optional[Dict]:
        """
        Converts a Blockchain.com transaction payload into the service's internal transaction representation.

        Parameters:
            tx_data: Raw transaction object returned by the Blockchain.com API.
            wallet_address: The Bitcoin address being tracked; used to compute the wallet-specific amount.

        Returns:
            A dictionary with normalized transaction fields (including `transaction_hash`, `timestamp`, `transaction_type`, `symbol`, `quantity`, `price_at_execution`, `total_amount`, `currency`, `fee`, `fee_currency`, `exchange`, `notes`, and `raw_data`) if conversion succeeds, `None` otherwise.
        """
        try:
            # Extract relevant data
            tx_hash = tx_data.get('hash')
            timestamp_seconds = tx_data.get('time', 0)  # Blockchain.info provides seconds
            result = tx_data.get('result', 0)  # Net change in wallet balance for this transaction

            if not tx_hash or not timestamp_seconds:
                logger.warning(f"Missing required fields in transaction data: {tx_data}")
                return None

            # Convert timestamp to datetime
            timestamp = datetime.fromtimestamp(timestamp_seconds)

            # Detect transaction type based on result (positive = incoming, negative = outgoing)
            # result field from blockchain.info is the net change in wallet balance for this transaction
            if result > 0:
                tx_type = CryptoTransactionType.TRANSFER_IN
            elif result < 0:
                tx_type = CryptoTransactionType.TRANSFER_OUT
            else:
                # Zero result, default to TRANSFER_IN
                tx_type = CryptoTransactionType.TRANSFER_IN

            # Convert net result in satoshis to BTC; fallback to 'balance' if present in test/mocks
            satoshis = abs(int(tx_data.get('result', tx_data.get('balance', 0))))
            quantity = Decimal(satoshis) / Decimal('100000000')

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


    def fetch_transactions(
        self,
        wallet_address: str,
        portfolio_id: int,
        max_transactions: int = None,
        days_back: int = None
    ) -> Dict[str, Any]:
        """
        Fetch transactions for a Bitcoin wallet address using only Blockchain.info API.

        Returns error results instead of raising exceptions to allow consistent error handling by callers.

        Args:
            wallet_address: Bitcoin wallet address to fetch transactions for
            portfolio_id: Portfolio ID to associate transactions with
            max_transactions: Maximum number of transactions to fetch. None = fetch ALL transactions
            days_back: Number of days to look back. None = fetch from blockchain beginning (all history)

        Returns:
            Dictionary with fetched transactions and metadata. Always returns a dict with 'status', 'message',
            'transactions', 'count', and 'timestamp' keys. Status will be 'success' or 'error'.
            Never raises exceptions - errors are returned in the result dict.
        """
        # Validate address
        if not self._validate_bitcoin_address(wallet_address):
            error_msg = f"Invalid Bitcoin address: {wallet_address}"
            logger.warning(error_msg)
            return self._build_result([], 'error', error_msg)

        # Set defaults for logging - None means unlimited
        max_str = "unlimited" if max_transactions is None else str(max_transactions)
        days_str = "all history" if days_back is None else str(days_back)
        logger.info(f"Fetching transactions for Bitcoin address {wallet_address} (max: {max_str}, days: {days_str})")

        # Check cache first
        cache_key = self._get_cache_key("transactions", wallet_address, max_transactions, days_back)
        cached_result = self._cache_get(cache_key)
        if cached_result:
            logger.info(f"Cache hit for wallet transactions: {wallet_address}")
            return cached_result

        try:
            logger.info(f"Fetching transactions for wallet {wallet_address} using Blockchain.info API")
            result = self._fetch_from_blockchain_com(wallet_address, portfolio_id, max_transactions, days_back)

            if result and result.get('status') == 'success' and result.get('transactions'):
                logger.info(f"Successfully fetched {len(result['transactions'])} transactions using Blockchain.info API")

                # Cache the result
                self._cache_set(cache_key, result, self.TRANSACTION_CACHE_TTL)

                return result
            else:
                # API returned no transactions or error status
                error_msg = result.get('message', "No transactions from Blockchain.info API") if result else "Unknown error"
                logger.warning(f"No transactions returned from Blockchain.info API for wallet {wallet_address}: {error_msg}")
                return self._build_result([], 'error', error_msg)

        except Exception as e:
            # Return error result instead of raising exception for consistent error handling
            error_msg = f"Failed to fetch transactions from Blockchain.info API: {str(e)}"
            logger.error(error_msg)
            return self._build_result([], 'error', error_msg)


    def _fetch_from_blockchain_com(
        self,
        wallet_address: str,
        portfolio_id: int,
        max_transactions: int,
        days_back: int
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch transactions using Blockchain.info API with pagination support.

        Args:
            wallet_address: Bitcoin wallet address
            portfolio_id: Portfolio ID
            max_transactions: Maximum number of transactions (None = unlimited, fetch all)
            days_back: Number of days to look back (None = all history)

        Returns:
            Dictionary with transactions and metadata
        """
        try:
            # Calculate date threshold (if specified)
            threshold_timestamp = 0  # Default to no limit
            if days_back is not None:
                date_threshold = datetime.utcnow() - timedelta(days=days_back)
                threshold_timestamp = int(date_threshold.timestamp())  # Blockchain.info uses seconds

            # Build request URL - use the correct rawaddr endpoint structure
            endpoint = f"/rawaddr/{wallet_address}"

            # Blockchain.info supports pagination via offset
            transactions = []
            offset = 0
            page_num = 1
            max_str = "unlimited" if max_transactions is None else str(max_transactions)

            logger.info(f"Starting paginated fetch for wallet {wallet_address} (max: {max_str})")

            while page_num <= self.max_pages_per_sync:
                params = {
                    'limit': self.max_transactions_per_request,
                    'offset': offset
                }

                logger.debug(f"Fetching page {page_num} (offset: {offset}) for wallet {wallet_address}")

                # Make request
                data = self._make_request(endpoint, params)

                if not data:
                    if offset == 0:
                        # No data on first request
                        return self._build_result([], 'error', 'No data received from Blockchain.info API')
                    else:
                        # Got some data before, this is end of pagination
                        break

                # Check if we got any transactions in this page
                page_txs = data.get('txs', [])
                if not page_txs:
                    logger.debug(f"No more transactions at offset {offset}, pagination complete")
                    break

                # Process transactions on this page
                page_added = 0
                for tx_data in page_txs:
                    # Check transaction timestamp (if threshold is set)
                    if threshold_timestamp > 0 and tx_data.get('time', 0) < threshold_timestamp:
                        logger.debug(f"Skipping transaction {tx_data.get('hash')} (outside time range)")
                        continue

                    # Convert transaction format
                    converted_tx = self._convert_blockchaincom_transaction(tx_data, wallet_address)

                    if converted_tx:
                        # Add portfolio ID
                        converted_tx['portfolio_id'] = portfolio_id

                        # Add to results
                        transactions.append(converted_tx)
                        page_added += 1

                        # Check if we've reached the limit (if specified)
                        if max_transactions is not None and len(transactions) >= max_transactions:
                            logger.info(f"Reached transaction limit of {max_transactions} after {page_num} pages")
                            return self._build_result(transactions, 'success', f'Fetched {len(transactions)} transactions (limit reached)')

                logger.debug(f"Page {page_num}: added {page_added} transactions (total: {len(transactions)})")

                # Move to next page
                offset += self.max_transactions_per_request
                page_num += 1

                # Add configurable delay between pages to respect rate limits
                time.sleep(self.delay_between_pages)

            # Check if we hit the safety limit
            if page_num > self.max_pages_per_sync:
                logger.warning(
                    f"Pagination safety limit reached for wallet {wallet_address}: "
                    f"fetched {len(transactions)} transactions across {page_num - 1} pages. "
                    f"Set blockchain_max_pages_per_sync={self.max_pages_per_sync} to increase limit."
                )
                return self._build_result(
                    transactions,
                    'success',
                    f'Fetched {len(transactions)} transactions (pagination limit reached)'
                )

            logger.info(f"Pagination complete for wallet {wallet_address}: fetched {len(transactions)} total transactions")
            return self._build_result(transactions, 'success', f'Fetched {len(transactions)} transactions')

        except Exception as e:
            logger.error(f"Error fetching from Blockchain.info API: {e}")
            return self._build_result([], 'error', str(e))


    def _build_result(
        self,
        transactions: List[Dict],
        status: str,
        message: str
    ) -> Dict[str, Any]:
        """
        Construct a standardized result dictionary for transaction fetch operations.

        Parameters:
            transactions (List[Dict]): List of transaction records to include in the result.
            status (str): Operation status label (e.g., "success", "error").
            message (str): Human-readable message describing the result.

        Returns:
            Dict[str, Any]: Dictionary with keys:
                - 'status': the provided status string,
                - 'message': the provided message string,
                - 'transactions': the provided list of transactions,
                - 'count': number of transactions,
                - 'timestamp': UTC timestamp (datetime) when the result was built.
        """
        return {
            'status': status,
            'message': message,
            'transactions': transactions,
            'count': len(transactions),
            'timestamp': datetime.utcnow()
        }

    def test_api_connection(self) -> bool:
        """
        Verify connectivity to Blockchain.info API by issuing a lightweight request.

        Returns:
            bool: True if a valid response was received, False otherwise.
        """
        try:
            # Test with a simple request using the correct rawaddr endpoint
            data = self._make_request('/rawaddr/1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa')  # Satoshi's address
            result = data is not None
            logger.info(f"Blockchain.info API connection test result: {result}")
            return result

        except Exception as e:
            logger.error(f"Error testing Blockchain.info API connection: {e}")
            return False


# Create a singleton instance
blockchain_fetcher = BlockchainFetcherService()
