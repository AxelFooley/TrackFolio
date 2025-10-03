"""
Transaction deduplication service.

Uses SHA256 hash: sha256(date + ticker + quantity + price + order_reference)
as per PRD Section 4.1 - Transaction Management.
"""
import hashlib
from datetime import date
from decimal import Decimal
from typing import Dict, Any, List, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from app.models import Transaction

logger = logging.getLogger(__name__)


class DeduplicationService:
    """Service for detecting and handling duplicate transactions."""

    @staticmethod
    def calculate_hash(
        operation_date: date,
        ticker: str,
        quantity: Decimal,
        price_per_share: Decimal,
        order_reference: str
    ) -> str:
        """
        Calculate SHA256 hash for transaction deduplication.

        Hash formula: sha256(date + ticker + quantity + price + order_reference)

        Args:
            operation_date: Transaction operation date
            ticker: Asset ticker symbol
            quantity: Transaction quantity
            price_per_share: Price per share
            order_reference: Broker's unique order reference

        Returns:
            SHA256 hash as hexadecimal string
        """
        # Create hash string
        hash_input = (
            f"{operation_date.isoformat()}"
            f"{ticker.upper()}"
            f"{quantity:.8f}"
            f"{price_per_share:.8f}"
            f"{order_reference}"
        )

        # Calculate SHA256 hash
        return hashlib.sha256(hash_input.encode()).hexdigest()

    @staticmethod
    def calculate_hash_from_dict(transaction_data: Dict[str, Any]) -> str:
        """
        Calculate hash from transaction dictionary.

        Args:
            transaction_data: Dictionary with transaction data

        Returns:
            SHA256 hash as hexadecimal string
        """
        return DeduplicationService.calculate_hash(
            operation_date=transaction_data["operation_date"],
            ticker=transaction_data["ticker"],
            quantity=transaction_data["quantity"],
            price_per_share=transaction_data["price_per_share"],
            order_reference=transaction_data["order_reference"]
        )

    @staticmethod
    async def check_duplicates(
        db: AsyncSession,
        transactions: List[Dict[str, Any]]
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Check for duplicate transactions against existing database records AND within the batch.

        Args:
            db: Database session
            transactions: List of transaction dictionaries to check

        Returns:
            Tuple of (new_transactions, duplicate_transactions)
        """
        # Calculate hashes for all incoming transactions
        for transaction in transactions:
            transaction["transaction_hash"] = DeduplicationService.calculate_hash_from_dict(transaction)

        # First, check for duplicates WITHIN the batch itself
        # Note: We only check transaction_hash, not order_reference
        # Order references can be duplicated for partial fills
        seen_hashes: Set[str] = set()
        batch_unique_transactions = []
        batch_duplicates = []

        for transaction in transactions:
            hash_val = transaction["transaction_hash"]

            # Check if we've already seen this hash in the current batch
            if hash_val in seen_hashes:
                batch_duplicates.append(transaction)
                logger.debug(
                    f"In-batch duplicate detected: {transaction['ticker']} "
                    f"on {transaction['operation_date']} "
                    f"(order_ref: {transaction['order_reference']})"
                )
            else:
                seen_hashes.add(hash_val)
                batch_unique_transactions.append(transaction)

        # Now check batch-unique transactions against database
        if not batch_unique_transactions:
            logger.info(
                f"Deduplication complete: 0 new, "
                f"{len(batch_duplicates)} duplicates (all in-batch)"
            )
            return [], batch_duplicates

        # Get all transaction hashes from batch-unique data
        incoming_hashes = {t["transaction_hash"] for t in batch_unique_transactions}

        # Query database for existing hashes only
        # We don't check order_reference because it can be duplicated (partial fills)
        result = await db.execute(
            select(Transaction.transaction_hash)
            .where(Transaction.transaction_hash.in_(incoming_hashes))
        )
        existing_records = result.all()

        # Create set of existing hashes
        existing_hashes: Set[str] = {record.transaction_hash for record in existing_records}

        # Separate new and duplicate transactions
        new_transactions = []
        db_duplicates = []

        for transaction in batch_unique_transactions:
            is_duplicate = transaction["transaction_hash"] in existing_hashes

            if is_duplicate:
                db_duplicates.append(transaction)
                logger.debug(
                    f"Database duplicate detected: {transaction['ticker']} "
                    f"on {transaction['operation_date']} "
                    f"(order_ref: {transaction['order_reference']})"
                )
            else:
                new_transactions.append(transaction)

        # Combine all duplicates
        all_duplicates = batch_duplicates + db_duplicates

        logger.info(
            f"Deduplication complete: {len(new_transactions)} new, "
            f"{len(all_duplicates)} duplicates "
            f"({len(batch_duplicates)} in-batch, {len(db_duplicates)} in database)"
        )

        return new_transactions, all_duplicates

    @staticmethod
    async def is_duplicate(
        db: AsyncSession,
        transaction_hash: str
    ) -> bool:
        """
        Check if a single transaction is a duplicate based on hash.

        Args:
            db: Database session
            transaction_hash: Transaction hash

        Returns:
            True if duplicate exists, False otherwise
        """
        result = await db.execute(
            select(Transaction.id)
            .where(Transaction.transaction_hash == transaction_hash)
            .limit(1)
        )

        return result.scalar() is not None
