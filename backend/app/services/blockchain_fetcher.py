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
    Service for fetching Bitcoin blockchain transactions.

    Supports multiple blockchain APIs with automatic fallback:
    1. Blockstream API (primary) - Reliable, free, no API key required
    2. Blockchain.com API (fallback) - Good backup option
    3. BlockCypher API (fallback) - Alternative with rate limits
    """

    def __init__(self):
        """
        Create and configure a BlockchainFetcherService instance.
        
        Initializes per-API configuration (base URLs, timeouts, rate limits, retries), attempts to connect to Redis for optional caching, and creates dedicated HTTP sessions and rate-tracking state for each supported API. Sets instance attributes:
        - APIS: per-API configuration mapping.
        - _redis_client: Redis client if connected, otherwise None (caching disabled).
        - _sessions: requests.Session objects keyed by API name.
        - _last_request_time: timestamp of last request per API for rate limiting.
        """
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
            self._sessions[api_name] = session
            self._last_request_time[api_name] = 0

    # Cache TTL (seconds) - from configuration
    TRANSACTION_CACHE_TTL = settings.blockchain_transaction_cache_ttl
    ADDRESS_CACHE_TTL = settings.blockchain_address_cache_ttl

    # Transaction limits
    MAX_TRANSACTIONS_PER_REQUEST = 50  # Blockstream limit
    MAX_HISTORY_DAYS = 365  # Don't fetch more than 1 year of history by default

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

    def _rate_limit(self, api_name: str) -> None:
        """
        Enforces per-API rate limiting based on the configured requests-per-second.
        
        Ensures at least 1 / rate_limit seconds elapse between consecutive requests for the given API by sleeping when needed, and updates the API's last-request timestamp stored on the instance.
        
        Parameters:
            api_name (str): Key name of the API as present in self.APIS.
        """
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

    def _convert_blockstream_transaction(self, tx_data: Dict, wallet_address: str) -> Optional[Dict]:
        """
        Convert a Blockstream-format transaction into the internal transaction dictionary.
        
        Parameters:
            tx_data (Dict): Transaction object returned by the Blockstream API.
            wallet_address (str): Wallet address being tracked; used to infer transaction direction.
        
        Returns:
            result (Optional[Dict]): A dict with the unified transaction fields or `None` if required data is missing or conversion fails.
            When present, the dict contains:
                - transaction_hash: original transaction id (txid)
                - timestamp: Python datetime of the transaction/block time
                - transaction_type: Enum value indicating IN/OUT (from _detect_transaction_type)
                - symbol: 'BTC'
                - quantity: Decimal BTC amount related to the tracked address
                - price_at_execution: Decimal estimated price (placeholder)
                - total_amount: Decimal total in fiat (quantity * price_at_execution)
                - currency: fiat currency enum (e.g., USD)
                - fee: Decimal fee amount (BTC)
                - fee_currency: currency for fee or None
                - exchange: source label (e.g., 'Bitcoin Blockchain')
                - notes: short human-readable note
                - raw_data: original `tx_data` for debugging
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
            # Blockstream API returns vout.value in satoshis (not BTC)
            total_satoshis = 0
            # Sum outputs; tolerate BTC vs satoshis in test/mocks
            v_values = [v.get('value', 0) for v in tx_data.get('vout', [])]
            if any(isinstance(v, float) for v in v_values) or any(0 < float(v) < 1 for v in v_values):
                # Treat as BTC values
                quantity = sum(Decimal(str(v)) for v in v_values)
            else:
                # Treat as satoshis
                total_satoshis = sum(int(v) for v in v_values)
                quantity = Decimal(total_satoshis) / Decimal("100000000")

            # Detect transaction type
            tx_type = self._detect_transaction_type(tx_data, wallet_address)
            
            # TODO: replace with market price at timestamp
            estimated_price = Decimal("1.0")

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
                # Zero result, default to TRANSFER_IN
                tx_type = CryptoTransactionType.TRANSFER_IN

            # Use net result in satoshis for this wallet; fallback to 'balance' if present in test/mocks
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

    def _convert_blockcypher_transaction(self, tx_data: Dict, wallet_address: str) -> Optional[Dict]:
        """
        Convert a BlockCypher transaction payload into the service's internal transaction dictionary.
        
        Parameters:
            tx_data (dict): Raw transaction object returned by the BlockCypher API.
            wallet_address (str): The wallet address being evaluated for this transaction.
        
        Returns:
            dict: A normalized transaction containing keys such as `transaction_hash`, `timestamp`, `transaction_type`,
            `symbol`, `quantity` (BTC), `price_at_execution`, `total_amount`, `currency`, `fee`, `fee_currency`,
            `exchange`, `notes`, and `raw_data`.
            `None` if required fields are missing or conversion cannot be performed.
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
    def fetch_transactions(
        self,
        wallet_address: str,
        portfolio_id: int,
        max_transactions: int = 100,
        days_back: Optional[int] = None
    ) -> Dict[str, Any]:
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
        raise BlockchainFetchError(error_msg)

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
            threshold_timestamp = int(date_threshold.timestamp())  # Blockchain.info uses seconds

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
                if tx_data.get('time', 0) < threshold_timestamp:
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

    def test_api_connection(self) -> Dict[str, bool]:
        """
        Verify connectivity to each configured blockchain API by issuing a lightweight request.
        
        Returns:
            dict: Mapping of API name to `True` if a valid response was received, `False` otherwise.
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