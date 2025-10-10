"""
Crypto wallet management service.

Provides functionality for managing Bitcoin paper wallets in crypto portfolios:
- Wallet address validation
- Wallet balance tracking
- Transaction synchronization
- Wallet status monitoring
"""
import logging
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
        """Initialize with database session."""
        self.db = db

    async def configure_wallet_for_portfolio(
        self,
        portfolio_id: int,
        wallet_address: str
    ) -> Dict[str, Any]:
        """
        Configure a Bitcoin wallet address for a crypto portfolio.

        Args:
            portfolio_id: ID of the crypto portfolio
            wallet_address: Bitcoin wallet address

        Returns:
            Configuration result with status and details
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
        Get comprehensive wallet status for a portfolio.

        Args:
            portfolio_id: ID of the crypto portfolio

        Returns:
            Wallet status information
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
            api_status = blockchain_fetcher.test_api_connection()

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
        Get wallet balance history for a portfolio.

        Args:
            portfolio_id: ID of the crypto portfolio
            days_back: Number of days to look back

        Returns:
            Balance history data
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
        Manually trigger wallet synchronization.

        Args:
            portfolio_id: ID of the crypto portfolio
            max_transactions: Maximum number of transactions to fetch
            days_back: Number of days to look back

        Returns:
            Sync result with status and details
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
            result = blockchain_fetcher.fetch_transactions(
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
        Remove wallet configuration from a portfolio.

        Args:
            portfolio_id: ID of the crypto portfolio

        Returns:
            Removal result
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
        Basic Bitcoin address validation.

        Args:
            address: Bitcoin address to validate

        Returns:
            True if address format appears valid, False otherwise
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
        Get a summary of wallet transactions for analytics.

        Args:
            portfolio_id: ID of the crypto portfolio
            days_back: Number of days to look back

        Returns:
            Transaction summary data
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
                "average_daily_transactions": round(total_transactions / days_back, 2),
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