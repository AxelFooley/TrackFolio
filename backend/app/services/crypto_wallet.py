"""
Crypto wallet management service.

Provides functionality for managing Bitcoin paper wallets in crypto portfolios:
- Wallet address validation
- Wallet balance tracking
- Transaction synchronization
- Wallet status monitoring
"""
import logging
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from app.models.crypto import CryptoPortfolio, CryptoTransaction, CryptoTransactionType, CryptoCurrency
from app.services.blockchain_fetcher import blockchain_fetcher
from app.services.blockchain_deduplication import blockchain_deduplication

logger = logging.getLogger(__name__)


class CryptoWalletService:
    """Service for managing crypto wallets in portfolios."""

    def __init__(self, db: AsyncSession):
        """
        Create a CryptoWalletService and retain the provided asynchronous database session for later operations.
        """
        self.db = db

    async def configure_wallet_for_portfolio(
        self,
        portfolio_id: int,
        wallet_address: str
    ) -> Dict[str, Any]:
        """
        Configure a Bitcoin wallet address for a crypto portfolio.
        
        Validates the portfolio exists and the wallet address format, persists the trimmed
        address and updated timestamp, clears deduplication cache for the portfolio, and
        returns a summary of the operation.
        
        Parameters:
            portfolio_id (int): ID of the crypto portfolio to configure.
            wallet_address (str): Bitcoin wallet address to associate with the portfolio.
        
        Returns:
            result (dict): Operation outcome. Typical keys:
                - success (bool): `True` on success, `False` on failure.
                - message (str): Human-readable success message (when successful).
                - error (str): Error message (when failed).
                - portfolio_id (int): The provided portfolio ID.
                - wallet_address (str): The configured address (on success).
                - timestamp (str): ISO8601 timestamp of the operation (on success).
        """
        try:
            # Validate portfolio exists
            portfolio_result = await self.db.execute(
                select(CryptoPortfolio).where(CryptoPortfolio.id == portfolio_id)
            )
            portfolio = portfolio_result.scalar_one_or_none()

            if not portfolio:
                return {
                    "success": False,
                    "error": "Portfolio not found",
                    "portfolio_id": portfolio_id
                }

            # Validate wallet address format (basic validation)
            if not self._validate_bitcoin_address(wallet_address):
                return {
                    "success": False,
                    "error": "Invalid Bitcoin wallet address format",
                    "portfolio_id": portfolio_id
                }

            # Update portfolio with wallet address
            portfolio.wallet_address = wallet_address.strip()
            portfolio.updated_at = datetime.utcnow()

            await self.db.commit()
            await self.db.refresh(portfolio)

            # Clear existing deduplication cache for this portfolio
            blockchain_deduplication.clear_portfolio_cache(portfolio_id)

            logger.info(f"Configured wallet {wallet_address} for portfolio {portfolio_id}")

            return {
                "success": True,
                "message": "Wallet address configured successfully",
                "portfolio_id": portfolio_id,
                "wallet_address": wallet_address,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error configuring wallet for portfolio {portfolio_id}: {e}")
            return {
                "success": False,
                "error": f"Failed to configure wallet: {str(e)}",
                "portfolio_id": portfolio_id
            }

    async def get_wallet_status(self, portfolio_id: int) -> Dict[str, Any]:
        """
        Retrieve status and aggregated statistics for a portfolio's Bitcoin wallet.
        
        Parameters:
            portfolio_id (int): ID of the crypto portfolio to inspect.
        
        Returns:
            dict: A status payload containing:
                - success (bool): `True` on success, `False` on error.
                - wallet_configured (bool): Whether a wallet address is configured for the portfolio.
                - portfolio_id (int): The provided portfolio identifier.
                - wallet_address (str|None): Configured wallet address when present.
                - total_blockchain_transactions (int): Total count of Bitcoin Blockchain transactions for the portfolio.
                - recent_blockchain_transactions_7d (int): Count of Bitcoin Blockchain transactions in the last 7 days.
                - last_blockchain_transaction (str|None): ISO-8601 timestamp of the most recent Bitcoin Blockchain transaction, or `None`.
                - transaction_type_breakdown (list): List of objects with `type` (transaction type name), `count` (int), and `total_amount` (float) summarizing transactions by type.
                - blockchain_api_status (Any): Result of the blockchain API connectivity check.
                - last_sync_check (str): ISO-8601 timestamp of when the status was generated.
                - error (str, optional): Error message when `success` is `False`.
        """
        try:
            # Get portfolio
            portfolio_result = await self.db.execute(
                select(CryptoPortfolio).where(CryptoPortfolio.id == portfolio_id)
            )
            portfolio = portfolio_result.scalar_one_or_none()

            if not portfolio:
                return {
                    "success": False,
                    "error": "Portfolio not found",
                    "portfolio_id": portfolio_id
                }

            if not portfolio.wallet_address:
                return {
                    "success": True,
                    "wallet_configured": False,
                    "portfolio_id": portfolio_id,
                    "message": "No wallet address configured for this portfolio"
                }

            # Get blockchain transaction statistics
            blockchain_tx_count = await self.db.execute(
                select(func.count(CryptoTransaction.id))
                .where(
                    and_(
                        CryptoTransaction.portfolio_id == portfolio_id,
                        CryptoTransaction.exchange == 'Bitcoin Blockchain'
                    )
                )
            )
            total_blockchain_txs = blockchain_tx_count.scalar() or 0

            # Get recent blockchain transactions (last 7 days)
            recent_blockchain_tx_count = await self.db.execute(
                select(func.count(CryptoTransaction.id))
                .where(
                    and_(
                        CryptoTransaction.portfolio_id == portfolio_id,
                        CryptoTransaction.exchange == 'Bitcoin Blockchain',
                        CryptoTransaction.timestamp >= datetime.utcnow() - timedelta(days=7)
                    )
                )
            )
            recent_blockchain_txs = recent_blockchain_tx_count.scalar() or 0

            # Get last blockchain transaction date
            last_blockchain_tx_result = await self.db.execute(
                select(CryptoTransaction.timestamp)
                .where(
                    and_(
                        CryptoTransaction.portfolio_id == portfolio_id,
                        CryptoTransaction.exchange == 'Bitcoin Blockchain'
                    )
                )
                .order_by(CryptoTransaction.timestamp.desc())
                .limit(1)
            )
            last_blockchain_tx = last_blockchain_tx_result.scalar_one_or_none()

            # Get transaction type breakdown
            tx_type_breakdown = await self.db.execute(
                select(
                    CryptoTransaction.transaction_type,
                    func.count(CryptoTransaction.id).label('count'),
                    func.sum(CryptoTransaction.total_amount).label('total_amount')
                )
                .where(
                    and_(
                        CryptoTransaction.portfolio_id == portfolio_id,
                        CryptoTransaction.exchange == 'Bitcoin Blockchain'
                    )
                )
                .group_by(CryptoTransaction.transaction_type)
            )
            tx_type_stats = tx_type_breakdown.all()

            # Test blockchain API connectivity
            api_status = await asyncio.to_thread(blockchain_fetcher.test_api_connection)

            return {
                "success": True,
                "wallet_configured": True,
                "portfolio_id": portfolio_id,
                "wallet_address": portfolio.wallet_address,
                "total_blockchain_transactions": total_blockchain_txs,
                "recent_blockchain_transactions_7d": recent_blockchain_txs,
                "last_blockchain_transaction": last_blockchain_tx.isoformat() if last_blockchain_tx else None,
                "transaction_type_breakdown": [
                    {
                        "type": tx.transaction_type.value,
                        "count": tx.count,
                        "total_amount": float(tx.total_amount) if tx.total_amount else 0
                    }
                    for tx in tx_type_stats
                ],
                "blockchain_api_status": api_status,
                "last_sync_check": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting wallet status for portfolio {portfolio_id}: {e}")
            return {
                "success": False,
                "error": f"Failed to get wallet status: {str(e)}",
                "portfolio_id": portfolio_id
            }

    async def get_wallet_balance_history(
        self,
        portfolio_id: int,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """
        Return the wallet's running balance history and current balance for a portfolio over a lookback period.
        
        Parameters:
            portfolio_id (int): ID of the crypto portfolio to query.
            days_back (int): Number of days to include in the history (default 30).
        
        Returns:
            dict: On success, a dictionary containing:
                - `success` (bool): True.
                - `portfolio_id` (int): The requested portfolio ID.
                - `wallet_address` (str): Configured wallet address.
                - `current_balance` (float): Balance after applying all returned transactions.
                - `balance_history` (list): Ordered list of transaction snapshots. Each entry contains:
                    - `timestamp` (str, ISO 8601): Transaction timestamp.
                    - `transaction_id` (int): Transaction record ID.
                    - `transaction_type` (str): Transaction type (e.g., "BUY", "SELL", "TRANSFER_IN", "TRANSFER_OUT").
                    - `quantity` (float): Quantity changed by the transaction.
                    - `running_balance` (float): Balance after the transaction.
                - `total_transactions` (int): Number of transactions included.
                - `period_days` (int): The requested lookback period in days.
            On failure, a dictionary with:
                - `success` (bool): False.
                - `error` (str): Error message.
                - `portfolio_id` (int): The requested portfolio ID.
        """
        try:
            # Get portfolio
            portfolio_result = await self.db.execute(
                select(CryptoPortfolio).where(CryptoPortfolio.id == portfolio_id)
            )
            portfolio = portfolio_result.scalar_one_or_none()

            if not portfolio or not portfolio.wallet_address:
                return {
                    "success": False,
                    "error": "Portfolio or wallet address not found",
                    "portfolio_id": portfolio_id
                }

            # Calculate balance history from blockchain transactions
            since_date = datetime.utcnow() - timedelta(days=days_back)

            # Get blockchain transactions in date range
            transactions_result = await self.db.execute(
                select(CryptoTransaction)
                .where(
                    and_(
                        CryptoTransaction.portfolio_id == portfolio_id,
                        CryptoTransaction.exchange == 'Bitcoin Blockchain',
                        CryptoTransaction.timestamp >= since_date
                    )
                )
                .order_by(CryptoTransaction.timestamp)
            )
            transactions = transactions_result.scalars().all()

            # Calculate running balance
            balance_history = []
            running_balance = Decimal("0")

            for tx in transactions:
                if tx.transaction_type == CryptoTransactionType.BUY:
                    running_balance += tx.quantity
                elif tx.transaction_type == CryptoTransactionType.SELL:
                    running_balance -= tx.quantity
                elif tx.transaction_type == CryptoTransactionType.TRANSFER_IN:
                    running_balance += tx.quantity
                elif tx.transaction_type == CryptoTransactionType.TRANSFER_OUT:
                    running_balance -= tx.quantity

                balance_history.append({
                    "timestamp": tx.timestamp.isoformat(),
                    "transaction_id": tx.id,
                    "transaction_type": tx.transaction_type.value,
                    "quantity": float(tx.quantity),
                    "running_balance": float(running_balance)
                })

            return {
                "success": True,
                "portfolio_id": portfolio_id,
                "wallet_address": portfolio.wallet_address,
                "current_balance": float(running_balance),
                "balance_history": balance_history,
                "total_transactions": len(transactions),
                "period_days": days_back
            }

        except Exception as e:
            logger.error(f"Error getting wallet balance history for portfolio {portfolio_id}: {e}")
            return {
                "success": False,
                "error": f"Failed to get balance history: {str(e)}",
                "portfolio_id": portfolio_id
            }

    async def sync_wallet_manually(
        self,
        portfolio_id: int,
        max_transactions: int = 50,
        days_back: int = 7
    ) -> Dict[str, Any]:
        """
        Trigger a manual synchronization of blockchain transactions for a portfolio's configured Bitcoin wallet.
        
        Fetches transactions from the blockchain for the portfolio's wallet address, filters duplicates, inserts new CryptoTransaction records, and commits the results.
        
        Parameters:
            portfolio_id (int): ID of the crypto portfolio to sync.
            max_transactions (int): Maximum number of transactions to fetch from the blockchain (default 50).
            days_back (int): Number of days to look back when fetching transactions (default 7).
        
        Returns:
            dict: Summary of the synchronization containing:
                - success (bool): `true` if the sync completed without a top-level failure, `false` otherwise.
                - message (str, optional): Informational message on success.
                - error (str, optional): Error message on failure.
                - portfolio_id (int): The supplied portfolio ID.
                - wallet_address (str, optional): The portfolio's wallet address when available.
                - transactions_imported (int, optional): Number of transactions inserted.
                - transactions_skipped (int, optional): Number of transactions skipped due to duplication.
                - transactions_failed (int, optional): Number of transactions that failed during processing.
                - total_processed (int, optional): Total transactions returned by the fetcher.
                - sync_timestamp (str, optional): ISO-8601 timestamp of when the sync completed.
        """
        try:
            # Get portfolio
            portfolio_result = await self.db.execute(
                select(CryptoPortfolio).where(CryptoPortfolio.id == portfolio_id)
            )
            portfolio = portfolio_result.scalar_one_or_none()

            if not portfolio or not portfolio.wallet_address:
                return {
                    "success": False,
                    "error": "Portfolio or wallet address not found",
                    "portfolio_id": portfolio_id
                }

            # Use blockchain fetcher to get transactions
            result = await asyncio.to_thread(
                blockchain_fetcher.fetch_transactions,
                wallet_address=portfolio.wallet_address,
                portfolio_id=portfolio_id,
                max_transactions=max_transactions,
                days_back=days_back
            )

            if result['status'] != 'success':
                return {
                    "success": False,
                    "error": f"Failed to fetch transactions: {result.get('message', 'Unknown error')}",
                    "portfolio_id": portfolio_id
                }

            # Process transactions through deduplication
            transactions = result.get('transactions', [])
            imported_count = 0
            skipped_count = 0
            error_count = 0

            for tx_data in transactions:
                try:
                    # Check if transaction already exists
                    if blockchain_deduplication.is_duplicate(portfolio_id, tx_data):
                        skipped_count += 1
                        continue

                    # Create new transaction
                    transaction = CryptoTransaction(
                        portfolio_id=portfolio_id,
                        symbol=tx_data.get('symbol', 'BTC'),
                        transaction_type=tx_data.get('transaction_type', CryptoTransactionType.TRANSFER_IN),
                        quantity=Decimal(str(tx_data.get('quantity', 0))),
                        price_at_execution=Decimal(str(tx_data.get('price_at_execution', 0))),
                        currency=tx_data.get('currency', 'EUR'),
                        total_amount=Decimal(str(tx_data.get('total_amount', 0))),
                        fee=Decimal(str(tx_data.get('fee', 0))),
                        fee_currency=tx_data.get('fee_currency'),
                        timestamp=tx_data.get('timestamp', datetime.utcnow()),
                        exchange='Bitcoin Blockchain',
                        transaction_hash=tx_data.get('transaction_hash'),
                        notes=tx_data.get('notes', 'Imported from blockchain')
                    )

                    self.db.add(transaction)

                    # Add to deduplication cache
                    blockchain_deduplication.add_transaction(portfolio_id, tx_data)
                    imported_count += 1

                except Exception as e:
                    logger.error(f"Error processing blockchain transaction: {e}")
                    error_count += 1
                    continue

            # Commit all transactions
            await self.db.commit()

            return {
                "success": True,
                "message": f"Wallet sync completed",
                "portfolio_id": portfolio_id,
                "wallet_address": portfolio.wallet_address,
                "transactions_imported": imported_count,
                "transactions_skipped": skipped_count,
                "transactions_failed": error_count,
                "total_processed": len(transactions),
                "sync_timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error syncing wallet for portfolio {portfolio_id}: {e}")
            return {
                "success": False,
                "error": f"Failed to sync wallet: {str(e)}",
                "portfolio_id": portfolio_id
            }

    async def remove_wallet_configuration(self, portfolio_id: int) -> Dict[str, Any]:
        """
        Remove the configured wallet address from the specified portfolio and clear related deduplication cache.
        
        Parameters:
            portfolio_id (int): ID of the crypto portfolio to update.
        
        Returns:
            dict: Result object with:
                - `success` (bool): `True` if the configuration was removed, `False` otherwise.
                - `message` (str, optional): Human-readable success message when `success` is `True`.
                - `error` (str, optional): Error message when `success` is `False` (e.g., portfolio not found or failure details).
                - `portfolio_id` (int): The provided portfolio ID.
                - `previous_wallet_address` (str | None, optional): The wallet address that was removed when the operation succeeded.
                - `timestamp` (str, optional): ISO-8601 timestamp of the removal when the operation succeeded.
        """
        try:
            # Get portfolio
            portfolio_result = await self.db.execute(
                select(CryptoPortfolio).where(CryptoPortfolio.id == portfolio_id)
            )
            portfolio = portfolio_result.scalar_one_or_none()

            if not portfolio:
                return {
                    "success": False,
                    "error": "Portfolio not found",
                    "portfolio_id": portfolio_id
                }

            # Store old wallet address for logging
            old_wallet_address = portfolio.wallet_address

            # Remove wallet address
            portfolio.wallet_address = None
            portfolio.updated_at = datetime.utcnow()

            await self.db.commit()

            # Clear deduplication cache
            blockchain_deduplication.clear_portfolio_cache(portfolio_id)

            logger.info(f"Removed wallet configuration from portfolio {portfolio_id}")

            return {
                "success": True,
                "message": "Wallet configuration removed successfully",
                "portfolio_id": portfolio_id,
                "previous_wallet_address": old_wallet_address,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error removing wallet configuration for portfolio {portfolio_id}: {e}")
            return {
                "success": False,
                "error": f"Failed to remove wallet configuration: {str(e)}",
                "portfolio_id": portfolio_id
            }

    def _validate_bitcoin_address(self, address: str) -> bool:
        """
        Perform basic format validation of a Bitcoin address.
        
        Validates common Bitcoin address formats: Bech32 addresses starting with "bc1" (checks length and Bech32 character set) and Base58 addresses starting with "1" or "3" (checks length and Base58 character set). This is a syntactic check only; it does not verify checksums or consult external services.
        
        Parameters:
            address (str): Bitcoin address to validate.
        
        Returns:
            bool: `True` if the address appears to be a valid Bitcoin address format, `False` otherwise.
        """
        if not address or not isinstance(address, str):
            return False

        address = address.strip()

        # Bech32 (bc1...) – different charset and length (approx. 42–62)
        if address.startswith('bc1'):
            bech32_part = address[3:]
            valid_bech32 = set('023456789acdefghjklmnpqrstuvwxyzqpzry9x8gf2tvdw0s3jn54khce6mua7l')
            return 42 <= len(address) <= 62 and all(c in valid_bech32 for c in bech32_part)

        # Base58 (legacy '1' / P2SH '3') – length 26–35
        if not (26 <= len(address) <= 35):
            return False
        if address[0] in ('1', '3'):
            valid_base58 = set('123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz')
            return all(c in valid_base58 for c in address)
        return False

    async def get_wallet_transaction_summary(
        self,
        portfolio_id: int,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """
        Produce an aggregated transaction summary for a portfolio's Bitcoin wallet over a lookback period.
        
        Parameters:
            portfolio_id (int): ID of the crypto portfolio to summarize.
            days_back (int): Number of days to include in the summary (default 30).
        
        Returns:
            dict: A payload with the following keys:
                - success (bool): `True` when the summary was produced, `False` on error or if portfolio/wallet is missing.
                - portfolio_id (int): The requested portfolio ID.
                - wallet_address (str): Configured wallet address (present when success is `True`).
                - period_days (int): The requested lookback period in days.
                - total_transactions (int): Count of blockchain transactions in the period.
                - total_volume (float): Sum of `total_amount` for transactions in the period (as float).
                - transaction_counts_by_type (dict): Mapping of transaction type name to count for the period.
                - average_daily_transactions (float): Average transactions per day over `days_back`, rounded to two decimals.
                - summary_period (dict): ISO8601 `start_date` and `end_date` for the summary window.
                - error (str, optional): Error message present when `success` is `False`.
        """
        try:
            # Get portfolio
            portfolio_result = await self.db.execute(
                select(CryptoPortfolio).where(CryptoPortfolio.id == portfolio_id)
            )
            portfolio = portfolio_result.scalar_one_or_none()

            if not portfolio or not portfolio.wallet_address:
                return {
                    "success": False,
                    "error": "Portfolio or wallet address not found",
                    "portfolio_id": portfolio_id
                }

            since_date = datetime.utcnow() - timedelta(days=days_back)

            # Get blockchain transaction statistics
            total_tx_count = await self.db.execute(
                select(func.count(CryptoTransaction.id))
                .where(
                    and_(
                        CryptoTransaction.portfolio_id == portfolio_id,
                        CryptoTransaction.exchange == 'Bitcoin Blockchain',
                        CryptoTransaction.timestamp >= since_date
                    )
                )
            )
            total_transactions = total_tx_count.scalar() or 0

            # Get total volume
            total_volume_result = await self.db.execute(
                select(func.sum(CryptoTransaction.total_amount))
                .where(
                    and_(
                        CryptoTransaction.portfolio_id == portfolio_id,
                        CryptoTransaction.exchange == 'Bitcoin Blockchain',
                        CryptoTransaction.timestamp >= since_date
                    )
                )
            )
            total_volume = total_volume_result.scalar() or Decimal("0")

            # Get transaction counts by type
            tx_counts = await self.db.execute(
                select(
                    CryptoTransaction.transaction_type,
                    func.count(CryptoTransaction.id).label('count')
                )
                .where(
                    and_(
                        CryptoTransaction.portfolio_id == portfolio_id,
                        CryptoTransaction.exchange == 'Bitcoin Blockchain',
                        CryptoTransaction.timestamp >= since_date
                    )
                )
                .group_by(CryptoTransaction.transaction_type)
            )
            transaction_counts = {tx.transaction_type.value: tx.count for tx in tx_counts.all()}

            return {
                "success": True,
                "portfolio_id": portfolio_id,
                "wallet_address": portfolio.wallet_address,
                "period_days": days_back,
                "total_transactions": total_transactions,
                "total_volume": float(total_volume),
                "transaction_counts_by_type": transaction_counts,
    async def get_wallet_transaction_summary(
        self,
        portfolio_id: int,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """
        Produce an aggregated transaction summary for a portfolio's Bitcoin wallet over a lookback period.
        
        Parameters:
            portfolio_id (int): ID of the crypto portfolio to summarize.
            days_back (int): Number of days to include in the summary (default 30).
        
        Returns:
            A dict with transaction stats or an error message.
        """
        try:
            if days_back <= 0:
                return {
                    "success": False,
                    "error": "days_back must be greater than 0",
                    "portfolio_id": portfolio_id
                }

            # Get portfolio
            portfolio_result = await self.db.execute(
                select(CryptoPortfolio).where(CryptoPortfolio.id == portfolio_id)
            )
            ...
                "summary_period": {
                    "start_date": since_date.isoformat(),
                    "end_date": datetime.utcnow().isoformat()
                }
            }

        except Exception as e:
            logger.error(f"Error getting wallet transaction summary for portfolio {portfolio_id}: {e}")
            return {
                "success": False,
                "error": f"Failed to get transaction summary: {str(e)}",
                "portfolio_id": portfolio_id
            }