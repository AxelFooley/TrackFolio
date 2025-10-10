"""
Blockchain transaction deduplication service.

This service handles detection and prevention of duplicate blockchain transactions
by maintaining a registry of processed transaction hashes and providing utilities
for transaction matching and deduplication.
"""
import hashlib
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
import logging
import redis
import pickle

from app.config import settings
from app.database import SyncSessionLocal
from app.models.crypto import CryptoTransaction
from sqlalchemy import text

logger = logging.getLogger(__name__)


class BlockchainDeduplicationService:
    """
    Service for deduplicating blockchain transactions.

    This service:
    1. Maintains a registry of processed transaction hashes
    2. Provides utilities for transaction matching
    3. Handles duplicate detection and prevention
    4. Supports both in-memory and Redis-based caching
    """

    # Cache configuration - from settings
    from app.config import settings
    HASH_CACHE_TTL = settings.blockchain_deduplication_cache_ttl
    BULK_CACHE_SIZE = 1000      # Maximum hashes to cache in memory

    def __init__(self):
        """
        Initialize the deduplication service and attempt to establish a Redis connection.
        
        Sets up in-memory caches for portfolio transaction hashes and their timestamps. If a Redis connection cannot be established, falls back to in-memory caching and logs the failure.
        """
        self._redis_client = None
        self._memory_cache: Dict[str, Set[str]] = {}  # portfolio_id -> set of hashes
        self._cache_timestamps: Dict[str, datetime] = {}

        # Initialize Redis connection
        try:
            self._redis_client = redis.from_url(settings.redis_url, decode_responses=False)
            self._redis_client.ping()
            logger.info("Blockchain deduplication: Connected to Redis")
        except Exception as e:
            logger.warning(f"Blockchain deduplication: Could not connect to Redis: {e}. Using in-memory caching only.")
            self._redis_client = None

    def _get_cache_key(self, portfolio_id: int) -> str:
        """Generate cache key for portfolio transaction hashes."""
        return f"blockchain:dedup:portfolio:{portfolio_id}:hashes"

    def _get_portfolio_hashes_from_db(self, portfolio_id: int) -> Set[str]:
        """
        Retrieve all non-null transaction hashes for the given portfolio from the database.
        
        Returns:
            Set[str]: A set of transaction hash strings for the portfolio. Returns an empty set if no hashes are found or if a database error occurs.
        """
        db = SyncSessionLocal()
        try:
            result = db.execute(
                "SELECT transaction_hash FROM crypto_transactions "
                "WHERE portfolio_id = :portfolio_id AND transaction_hash IS NOT NULL",
                {"portfolio_id": portfolio_id}
            )
            return {row[0] for row in result.all() if row[0]}
        except Exception as e:
            logger.error(f"Error fetching portfolio hashes from database: {e}")
            return set()
        finally:
            db.close()

    def get_portfolio_transaction_hashes(self, portfolio_id: int) -> Set[str]:
        """
        Retrieve the set of known transaction hashes for a portfolio, checking caches before querying the database.
        
        Returns:
            A set of transaction hash strings belonging to the specified portfolio.
        """
        # Check Redis cache first
        if self._redis_client:
            try:
                cache_key = self._get_cache_key(portfolio_id)
                members = self._redis_client.smembers(cache_key)
                if members:
                    hashes = {m.decode('utf-8') if isinstance(m, bytes) else m for m in members}
                    logger.debug(f"Cache hit for portfolio {portfolio_id} hashes: {len(hashes)}")
                    return hashes
            except Exception as e:
                logger.warning(f"Error getting hashes from Redis cache: {e}")

        # Check memory cache
        if portfolio_id in self._memory_cache:
            cache_age = datetime.utcnow() - self._cache_timestamps.get(portfolio_id, datetime.min)
            if cache_age < timedelta(minutes=30):  # Memory cache valid for 30 minutes
                logger.debug(f"Memory cache hit for portfolio {portfolio_id} hashes: {len(self._memory_cache[portfolio_id])}")
                return self._memory_cache[portfolio_id]

        # Fetch from database
        hashes = self._get_portfolio_hashes_from_db(portfolio_id)

        # Update caches
        self._update_cache(portfolio_id, hashes)

        logger.info(f"Fetched {len(hashes)} transaction hashes for portfolio {portfolio_id}")
        return hashes

    def _update_cache(self, portfolio_id: int, hashes: Set[str]) -> None:
        """
        Update both Redis and memory caches with transaction hashes.

        Args:
            portfolio_id: Portfolio ID
            hashes: Set of transaction hashes
        """
        # Update Redis cache
        if self._redis_client:
            try:
                cache_key = self._get_cache_key(portfolio_id)
                serialized_data = pickle.dumps(hashes)
                self._redis_client.setex(cache_key, self.HASH_CACHE_TTL, serialized_data)
            except Exception as e:
                logger.warning(f"Error updating Redis cache: {e}")

        # Update memory cache
        self._memory_cache[portfolio_id] = hashes
        self._cache_timestamps[portfolio_id] = datetime.utcnow()

        # Clean up memory cache if it gets too large
        if len(self._memory_cache) > self.BULK_CACHE_SIZE:
            self._cleanup_memory_cache()

    def _cleanup_memory_cache(self) -> None:
        """
        Remove oldest portfolio entries from the in-memory cache when it grows beyond the configured BULK_CACHE_SIZE.
        
        When the number of cached portfolios exceeds BULK_CACHE_SIZE, this method retains only the most recently updated half of the entries and discards older ones. It updates both _memory_cache and _cache_timestamps and logs the resulting cache size.
        """
        if len(self._memory_cache) <= self.BULK_CACHE_SIZE:
            return

        # Sort by timestamp and remove oldest entries
        sorted_items = sorted(
            self._cache_timestamps.items(),
            key=lambda x: x[1]
        )

        # Keep only the most recent half
        items_to_keep = sorted_items[self.BULK_CACHE_SIZE // 2:]

        self._memory_cache = {
            portfolio_id: self._memory_cache[portfolio_id]
            for portfolio_id, _ in items_to_keep
        }

        self._cache_timestamps = {
            portfolio_id: timestamp
            for portfolio_id, timestamp in items_to_keep
        }

        logger.info(f"Cleaned up memory cache: {len(self._memory_cache)} portfolios cached")

    def is_duplicate_transaction(self, portfolio_id: int, transaction_hash: str) -> bool:
        """
        Determine whether a transaction hash already exists for the given portfolio.
        
        Parameters:
            portfolio_id (int): Identifier of the portfolio to check.
            transaction_hash (str): Transaction hash to look up.
        
        Returns:
            True if the transaction hash already exists for the portfolio, False otherwise.
        """
        if not transaction_hash:
            return False

        existing_hashes = self.get_portfolio_transaction_hashes(portfolio_id)
        return transaction_hash in existing_hashes

    def add_transaction_hash(self, portfolio_id: int, transaction_hash: str) -> None:
        """
        Add a transaction hash to the portfolio's deduplication registry.
        
        If `transaction_hash` is falsy or already present for the portfolio, the method does nothing; otherwise it updates the service caches for the portfolio.
        """
        if not transaction_hash:
            return

        # Get current hashes
        existing_hashes = self.get_portfolio_transaction_hashes(portfolio_id)

        # Add new hash if not already present
        if transaction_hash not in existing_hashes:
            existing_hashes.add(transaction_hash)
            self._update_cache(portfolio_id, existing_hashes)
            logger.debug(f"Added new transaction hash {transaction_hash} to portfolio {portfolio_id}")

    def add_transaction_hashes_bulk(self, portfolio_id: int, transaction_hashes: List[str]) -> int:
        """
        Add multiple transaction hashes to the registry.

        Args:
            portfolio_id: Portfolio ID
            transaction_hashes: List of transaction hashes to add

        Returns:
            Number of new hashes added
        """
        if not transaction_hashes:
            return 0

        # Get current hashes
        existing_hashes = self.get_portfolio_transaction_hashes(portfolio_id)

        # Add new hashes
        new_hashes = set()
        for tx_hash in transaction_hashes:
            if tx_hash and tx_hash not in existing_hashes:
                existing_hashes.add(tx_hash)
                new_hashes.add(tx_hash)

        # Update cache if new hashes were added
        if new_hashes:
            self._update_cache(portfolio_id, existing_hashes)
            logger.info(f"Added {len(new_hashes)} new transaction hashes to portfolio {portfolio_id}")

        return len(new_hashes)

    def filter_duplicate_transactions(
        self,
        portfolio_id: int,
        transactions: List[Dict[str, any]]
    ) -> Tuple[List[Dict[str, any]], List[str]]:
        """
        Filter out transactions that appear to already exist for a given portfolio.
        
        Parameters:
            portfolio_id (int): Identifier of the portfolio whose existing transactions are used for deduplication.
            transactions (List[Dict[str, any]]): List of transaction dictionaries; each may include a 'transaction_hash' key used to identify duplicates.
        
        Returns:
            Tuple[List[Dict[str, any]], List[str]]: A tuple where the first element is the list of transactions that are not duplicates, and the second element is the list of transaction hashes that were identified as duplicates.
        """
        existing_hashes = self.get_portfolio_transaction_hashes(portfolio_id)
        unique_transactions = []
        duplicate_hashes = []

        for tx_data in transactions:
            tx_hash = tx_data.get('transaction_hash')
            if tx_hash and tx_hash in existing_hashes:
                duplicate_hashes.append(tx_hash)
                logger.debug(f"Filtering duplicate transaction: {tx_hash}")
            else:
                unique_transactions.append(tx_data)

        if duplicate_hashes:
            logger.info(f"Filtered out {len(duplicate_hashes)} duplicate transactions for portfolio {portfolio_id}")

        return unique_transactions, duplicate_hashes

    def generate_transaction_fingerprint(
        self,
        tx_data: Dict[str, any],
        portfolio_id: int
    ) -> str:
        """
        Create a deterministic fingerprint for a transaction using key identifying fields.
        
        Parameters:
            tx_data (Dict[str, any]): Transaction dictionary; expected keys include
                'symbol', 'timestamp', 'quantity', 'transaction_type',
                'exchange', and 'transaction_hash'. Missing keys are treated as empty.
            portfolio_id (int): Portfolio identifier included in the fingerprint to scope it.
        
        Returns:
            fingerprint (str): SHA-256 hex digest of the concatenated identifying fields.
        """
        # Create a string with key fields for fingerprinting
        fingerprint_fields = [
            str(portfolio_id),
            tx_data.get('symbol', ''),
            str(tx_data.get('timestamp', '')),
            str(tx_data.get('quantity', '')),
            str(tx_data.get('transaction_type', '')),
            tx_data.get('exchange', ''),
            tx_data.get('transaction_hash', '')
        ]

        fingerprint_string = '|'.join(fingerprint_fields)
        return hashlib.sha256(fingerprint_string.encode()).hexdigest()

    def find_potential_duplicates(
        self,
        portfolio_id: int,
        transactions: List[Dict[str, any]],
        similarity_threshold: float = 0.8
    ) -> List[Tuple[Dict[str, any], Dict[str, any]]]:
        """
        Find transactions that are likely duplicates by comparing input transactions against the portfolio's recent transactions.
        
        Compares each provided transaction to recent transactions for the given portfolio (last 30 days) and returns pairs whose similarity meets or exceeds the similarity_threshold.
        
        Parameters:
            portfolio_id (int): Portfolio identifier whose recent transactions are used for comparison.
            transactions (List[Dict[str, any]]): Transactions to check for potential duplicates.
            similarity_threshold (float): Minimum similarity score between 0.0 and 1.0 required to consider a pair a potential duplicate.
        
        Returns:
            List[Tuple[Dict[str, any], Dict[str, any]]]: List of pairs (input_transaction, existing_transaction) that meet or exceed the similarity_threshold.
        """
        # Get existing transactions from database
        db = SyncSessionLocal()
        try:
            # Get recent transactions from the database
            recent_days = 30
            since_date = datetime.utcnow() - timedelta(days=recent_days)

            result = db.execute(
                """
                SELECT symbol, timestamp, quantity, transaction_type, exchange, transaction_hash
                FROM crypto_transactions
                WHERE portfolio_id = :portfolio_id
                AND timestamp >= :since_date
                ORDER BY timestamp DESC
                """,
                {"portfolio_id": portfolio_id, "since_date": since_date}
            )
            existing_txs = result.all()

            if not existing_txs:
                return []

            # Check for similar transactions
            potential_duplicates = []

            for tx_data in transactions:
                for existing_tx in existing_txs:
                    similarity = self._calculate_transaction_similarity(tx_data, existing_tx)
                    if similarity >= similarity_threshold:
                        potential_duplicates.append((tx_data, existing_tx))
                        break

            logger.info(f"Found {len(potential_duplicates)} potential duplicate transaction pairs")
            return potential_duplicates

        except Exception as e:
            logger.error(f"Error finding potential duplicates: {e}")
            return []

        finally:
            db.close()

    def _calculate_transaction_similarity(
        self,
        tx1: Dict[str, any] | tuple,
        tx2: Dict[str, any] | tuple
    ) -> float:
        """
        Compute a normalized similarity score between two transactions.
        
        Both inputs may be a mapping with keys `symbol`, `timestamp`, `quantity`, `transaction_type`, `exchange`, and `transaction_hash`,
        or a tuple with that exact ordering: (symbol, timestamp, quantity, transaction_type, exchange, transaction_hash).
        
        Parameters:
            tx1: First transaction as a dict or tuple (see accepted shapes above).
            tx2: Second transaction as a dict or tuple (see accepted shapes above).
        
        Returns:
            A float between 0.0 and 1.0 where higher values indicate greater similarity.
        """
        # Extract fields from database tuple if needed
        if isinstance(tx1, tuple):
            tx1_dict = {
                'symbol': tx1[0],
                'timestamp': tx1[1],
                'quantity': tx1[2],
                'transaction_type': tx1[3],
                'exchange': tx1[4],
                'transaction_hash': tx1[5]
            }
        else:
            tx1_dict = tx1

        if isinstance(tx2, tuple):
            tx2_dict = {
                'symbol': tx2[0],
                'timestamp': tx2[1],
                'quantity': tx2[2],
                'transaction_type': tx2[3],
                'exchange': tx2[4],
                'transaction_hash': tx2[5]
            }
        else:
            tx2_dict = tx2

        # Calculate similarity based on key fields
        similarity_score = 0.0
        total_weight = 0.0

        # Symbol match (weight: 0.2)
        if tx1_dict.get('symbol') and tx2_dict.get('symbol'):
            if tx1_dict['symbol'] == tx2_dict['symbol']:
                similarity_score += 0.2
        total_weight += 0.2

        # Timestamp proximity (weight: 0.3)
        if tx1_dict.get('timestamp') and tx2_dict.get('timestamp'):
            time_diff = abs(tx1_dict['timestamp'] - tx2_dict['timestamp'])
            # If timestamps are within 1 hour, consider it a match
            if time_diff.total_seconds() < 3600:
                similarity_score += 0.3
            elif time_diff.total_seconds() < 86400:  # Within 1 day
                similarity_score += 0.15
        total_weight += 0.3

        # Quantity match (weight: 0.3)
        if tx1_dict.get('quantity') and tx2_dict.get('quantity'):
            qty1 = float(tx1_dict['quantity'])
            qty2 = float(tx2_dict['quantity'])
            if qty1 > 0 and qty2 > 0:
                qty_diff = abs(qty1 - qty2) / max(qty1, qty2)
                if qty_diff < 0.01:  # Less than 1% difference
                    similarity_score += 0.3
                elif qty_diff < 0.1:  # Less than 10% difference
                    similarity_score += 0.15
        total_weight += 0.3

        # Transaction type match (weight: 0.1)
        if tx1_dict.get('transaction_type') and tx2_dict.get('transaction_type'):
            if str(tx1_dict['transaction_type']) == str(tx2_dict['transaction_type']):
                similarity_score += 0.1
        total_weight += 0.1

        # Exchange match (weight: 0.1)
        if tx1_dict.get('exchange') and tx2_dict.get('exchange'):
            if tx1_dict['exchange'] == tx2_dict['exchange']:
                similarity_score += 0.1
        total_weight += 0.1

        # Transaction hash match (bonus: 0.2)
        if (tx1_dict.get('transaction_hash') and tx2_dict.get('transaction_hash') and
            tx1_dict['transaction_hash'] == tx2_dict['transaction_hash']):
            similarity_score += 0.2

        # Normalize score
        return similarity_score / (total_weight + 0.2)  # +0.2 for potential bonus

    def clear_portfolio_cache(self, portfolio_id: int) -> None:
        """
        Clear both Redis and in-memory deduplication caches for the given portfolio.
        
        Removes the Redis key for the portfolio if a Redis client is available, and deletes any in-memory cache entries and their timestamps.
        """
        # Clear Redis cache
        if self._redis_client:
            try:
                cache_key = self._get_cache_key(portfolio_id)
                self._redis_client.delete(cache_key)
            except Exception as e:
                logger.warning(f"Error clearing Redis cache for portfolio {portfolio_id}: {e}")

        # Clear memory cache
        if portfolio_id in self._memory_cache:
            del self._memory_cache[portfolio_id]
        if portfolio_id in self._cache_timestamps:
            del self._cache_timestamps[portfolio_id]

        logger.info(f"Cleared deduplication cache for portfolio {portfolio_id}")

    def get_cache_stats(self) -> Dict[str, any]:
        """
        Return runtime statistics about in-memory and Redis-backed deduplication caches.
        
        Returns:
            dict: A mapping with these keys:
                - memory_cache_size (int): Number of portfolios stored in the in-memory cache.
                - memory_cache_portfolios (List[int|str]): Portfolio identifiers present in the in-memory cache.
                - redis_connected (bool): True if a Redis client is available, False otherwise.
                - total_cached_hashes (int): Total count of transaction hashes across all in-memory portfolio caches.
                - redis_cache_keys (int | str, optional): Number of Redis keys matching the deduplication pattern when Redis is available; set to the string `'error'` if key counting failed or omitted when Redis is not configured.
        """
        stats = {
            'memory_cache_size': len(self._memory_cache),
            'memory_cache_portfolios': list(self._memory_cache.keys()),
            'redis_connected': self._redis_client is not None,
            'total_cached_hashes': sum(len(hashes) for hashes in self._memory_cache.values())
        }

        # Add Redis stats if available
        if self._redis_client:
            try:
                # Count Redis keys for blockchain deduplication
                redis_keys = self._redis_client.keys("blockchain:dedup:portfolio:*:hashes")
                stats['redis_cache_keys'] = len(redis_keys)
            except Exception as e:
                logger.warning(f"Error getting Redis cache stats: {e}")
                stats['redis_cache_keys'] = 'error'

        return stats


# Create a singleton instance
blockchain_deduplication = BlockchainDeduplicationService()