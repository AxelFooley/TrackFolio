"""
Crypto portfolio API endpoints.

Comprehensive API for managing crypto portfolios, transactions, and analytics.
Follows existing codebase patterns with proper error handling and async database sessions.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Optional
import logging

from app.database import get_db
from app.models.crypto import CryptoPortfolio, CryptoTransaction, CryptoTransactionType
from app.schemas.crypto import (
    CryptoPortfolioCreate,
    CryptoPortfolioUpdate,
    CryptoPortfolioResponse,
    CryptoPortfolioList,
    CryptoTransactionCreate,
    CryptoTransactionUpdate,
    CryptoTransactionResponse,
    CryptoTransactionList,
    CryptoPortfolioMetrics,
    CryptoHolding,
    CryptoPortfolioPerformance,
    CryptoPriceData,
    CryptoHistoricalPrice,
    CryptoPriceResponse,
    CryptoPriceHistoryResponse,
)
from app.services.crypto_calculations import CryptoCalculationService
from app.services.price_fetcher import PriceFetcher
from app.tasks.blockchain_sync import sync_wallet_manually
from app.config import settings
from app.utils.time_utils import (
    adjust_end_date_for_data_availability,
    parse_time_range
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/crypto", tags=["crypto"])


async def _get_usd_to_eur_rate() -> Optional[Decimal]:
    """
    Obtain the USD→EUR conversion rate, using PriceFetcher and falling back to Decimal('0.92') when unavailable.

    Returns:
        Decimal: Conversion rate from USD to EUR; returns Decimal('0.92') if fetching fails or no rate is available.
    """
    try:
        price_fetcher = PriceFetcher()
        rate = await price_fetcher.fetch_fx_rate("USD", "EUR")
        if rate:
            return rate
        else:
            # Fallback to a reasonable approximation
            logger.warning("Using fallback USD to EUR rate (0.92)")
            return Decimal("0.92")
    except Exception as e:
        logger.error(f"Error getting USD to EUR rate: {e}")
        return Decimal("0.92")  # Fallback rate


# Portfolio Management Endpoints

@router.post("/portfolios", response_model=CryptoPortfolioResponse, status_code=201)
async def create_crypto_portfolio(
    portfolio_data: CryptoPortfolioCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new crypto portfolio with the provided data.

    Validates that no existing portfolio uses the same name, persists the new portfolio
    with is_active set to True, and returns the created portfolio. Raises HTTP 400 if
    a portfolio name conflict is found; raises HTTP 500 on unexpected errors.

    Returns:
        The created CryptoPortfolio instance.
    """
    try:
        # Check if portfolio with same name already exists for user
        existing_result = await db.execute(
            select(CryptoPortfolio).where(CryptoPortfolio.name == portfolio_data.name)
        )
        existing_portfolio = existing_result.scalar_one_or_none()

        if existing_portfolio:
            raise HTTPException(
                status_code=400,
                detail="Portfolio with this name already exists"
            )

        # Create new portfolio
        portfolio = CryptoPortfolio(
            name=portfolio_data.name,
            description=portfolio_data.description,
            base_currency=portfolio_data.base_currency,
            wallet_address=portfolio_data.wallet_address,
            is_active=True
        )

        db.add(portfolio)
        await db.commit()
        await db.refresh(portfolio)

        # Backfill snapshots from first transaction date to today (or just today if no transactions yet)
        # Use a Celery task to backfill snapshots asynchronously (avoids sync/async issues)
        try:
            from app.tasks.crypto_snapshots import backfill_crypto_portfolio_snapshots
            # Schedule the backfill task which will handle both empty and populated portfolios
            backfill_crypto_portfolio_snapshots.delay(
                portfolio_id=portfolio.id
            )
            logger.info(f"Scheduled automatic snapshot backfill for new crypto portfolio {portfolio.id}")
        except Exception as e:
            logger.error(f"Failed to schedule snapshot backfill for portfolio {portfolio.id}: {e}")
            # Don't fail portfolio creation if snapshot scheduling fails

        # Trigger automatic full sync if wallet address is provided
        if portfolio.wallet_address:
            try:
                # Start background sync task with no limits (fetch all history)
                sync_wallet_manually.delay(
                    wallet_address=portfolio.wallet_address,
                    portfolio_id=portfolio.id,
                    max_transactions=None,  # No limit - fetch all transactions
                    days_back=None           # No date limit - fetch complete history
                )
                logger.info(
                    f"Started automatic full sync for new portfolio {portfolio.id} "
                    f"with wallet {portfolio.wallet_address}"
                )
            except Exception as e:
                logger.error(f"Failed to start automatic sync for wallet {portfolio.wallet_address}: {e}")
                # Don't fail the portfolio creation, just log the error

        return portfolio

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create portfolio: {str(e)}")


@router.get("/portfolios", response_model=CryptoPortfolioList)
async def list_crypto_portfolios(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    skip: int = Query(0, ge=0, description="Number of portfolios to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of portfolios to return"),
    db: AsyncSession = Depends(get_db)
):
    """
    List crypto portfolios with optional active-state filtering and pagination.

    Retrieves portfolios from the database, includes per-portfolio aggregated metrics
    (value, cost basis, profit/loss, transaction count) and a wallet_sync_status block
    that indicates whether a wallet is configured and recent blockchain transaction counts.

    Parameters:
        is_active (Optional[bool]): If provided, filter portfolios by their active status.
        skip (int): Number of portfolios to skip (offset).
        limit (int): Maximum number of portfolios to return.

    Returns:
        CryptoPortfolioList: An object containing the list of portfolio responses with
        attached metrics and wallet sync status, and the total matching portfolio count.
    """
    try:
        query = select(CryptoPortfolio)

        # Apply filters
        if is_active is not None:
            query = query.where(CryptoPortfolio.is_active == is_active)

        # Count total portfolios
        count_query = select(func.count()).select_from(query.subquery())
        total_count_result = await db.execute(count_query)
        total_count = total_count_result.scalar()

        # Apply pagination
        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        portfolios = result.scalars().all()

        # Calculate metrics for each portfolio
        calc_service = CryptoCalculationService(db)
        portfolio_responses = []

        for portfolio in portfolios:
            metrics = await calc_service.calculate_portfolio_metrics(portfolio.id)

            # Get wallet sync status if wallet address is configured
            wallet_sync_status = None
            if portfolio.wallet_address:
                try:
                    # Get recent blockchain transaction count for sync status
                    blockchain_tx_count = await db.execute(
                        select(func.count(CryptoTransaction.id))
                        .where(
                            and_(
                                CryptoTransaction.portfolio_id == portfolio.id,
                                CryptoTransaction.exchange == 'Bitcoin Blockchain',
                                CryptoTransaction.timestamp >= datetime.utcnow() - timedelta(days=7)
                            )
                        )
                    )
                    recent_blockchain_txs = blockchain_tx_count.scalar() or 0

                    wallet_sync_status = {
                        "wallet_configured": True,
                        "wallet_address": portfolio.wallet_address,
                        "recent_blockchain_transactions": recent_blockchain_txs,
                        "last_sync_check": datetime.utcnow().isoformat()
                    }
                except Exception as e:
                    logger.warning(f"Failed to get wallet sync status for portfolio {portfolio.id}: {e}")
                    wallet_sync_status = {
                        "wallet_configured": True,
                        "wallet_address": portfolio.wallet_address,
                        "status": "error",
                        "error": "Failed to check sync status"
                    }
            else:
                wallet_sync_status = {
                    "wallet_configured": False
                }

            # Build portfolio response with currency-specific fields
            base_currency_str = (
                portfolio.base_currency.value if hasattr(portfolio.base_currency, 'value')
                else str(portfolio.base_currency)
            )
            portfolio_dict = {
                "id": portfolio.id,
                "name": portfolio.name,
                "description": portfolio.description,
                "is_active": portfolio.is_active,
                "base_currency": portfolio.base_currency,
                "wallet_address": portfolio.wallet_address,
                "created_at": portfolio.created_at,
                "updated_at": portfolio.updated_at,
                # Add currency-specific fields for frontend compatibility
                "total_value_usd": metrics.total_value if metrics and base_currency_str == 'USD' else None,
                "total_value_eur": metrics.total_value if metrics and base_currency_str == 'EUR' else None,
                "total_profit_usd": metrics.total_profit_loss if metrics and base_currency_str == 'USD' else None,
                "total_profit_eur": metrics.total_profit_loss if metrics and base_currency_str == 'EUR' else None,
                "profit_percentage_usd": metrics.total_profit_loss_pct if metrics and base_currency_str == 'USD' else None,
                "profit_percentage_eur": metrics.total_profit_loss_pct if metrics and base_currency_str == 'EUR' else None,
                # Keep original fields for backward compatibility
                "total_value": metrics.total_value if metrics else None,
                "total_cost_basis": metrics.total_cost_basis if metrics else None,
                "total_profit_loss": metrics.total_profit_loss if metrics else None,
                "total_profit_loss_pct": metrics.total_profit_loss_pct if metrics else None,
                "transaction_count": metrics.transaction_count if metrics else 0,
                "wallet_sync_status": wallet_sync_status
            }
            portfolio_responses.append(CryptoPortfolioResponse(**portfolio_dict))

        return CryptoPortfolioList(
            portfolios=portfolio_responses,
            total_count=total_count
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list portfolios: {str(e)}")


@router.get("/portfolios/{portfolio_id}", response_model=CryptoPortfolioResponse)
async def get_crypto_portfolio(
    portfolio_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve a detailed portfolio including computed metrics and wallet sync status.

    Parameters:
        portfolio_id (int): ID of the portfolio to retrieve.

    Returns:
        CryptoPortfolioResponse: Portfolio object with all currency-specific fields
        populated based on base_currency and wallet_sync_status.

    Raises:
        HTTPException: 404 if the portfolio is not found; 500 if an unexpected error occurs while retrieving.
    """
    try:
        calc_service = CryptoCalculationService(db)

        # Get portfolio
        portfolio_result = await db.execute(
            select(CryptoPortfolio).where(CryptoPortfolio.id == portfolio_id)
        )
        portfolio = portfolio_result.scalar_one_or_none()

        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        # Get metrics
        metrics = await calc_service.calculate_portfolio_metrics(portfolio_id)

        # Get wallet sync status
        wallet_sync_status = None
        if portfolio.wallet_address:
            try:
                # Get recent blockchain transaction count for sync status
                blockchain_tx_count = await db.execute(
                    select(func.count(CryptoTransaction.id))
                    .where(
                        and_(
                            CryptoTransaction.portfolio_id == portfolio_id,
                            CryptoTransaction.exchange == 'Bitcoin Blockchain',
                            CryptoTransaction.timestamp >= datetime.utcnow() - timedelta(days=7)
                        )
                    )
                )
                recent_blockchain_txs = blockchain_tx_count.scalar() or 0

                # Get total blockchain transactions
                total_blockchain_tx_count = await db.execute(
                    select(func.count(CryptoTransaction.id))
                    .where(
                        and_(
                            CryptoTransaction.portfolio_id == portfolio_id,
                            CryptoTransaction.exchange == 'Bitcoin Blockchain'
                        )
                    )
                )
                total_blockchain_txs = total_blockchain_tx_count.scalar() or 0

                # Get last blockchain transaction date
                last_blockchain_tx_result = await db.execute(
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

                wallet_sync_status = {
                    "wallet_configured": True,
                    "wallet_address": portfolio.wallet_address,
                    "recent_blockchain_transactions": recent_blockchain_txs,
                    "total_blockchain_transactions": total_blockchain_txs,
                    "last_blockchain_transaction": last_blockchain_tx.isoformat() if last_blockchain_tx else None,
                    "last_sync_check": datetime.utcnow().isoformat()
                }
            except Exception as e:
                logger.warning(f"Failed to get wallet sync status for portfolio {portfolio_id}: {e}")
                wallet_sync_status = {
                    "wallet_configured": True,
                    "wallet_address": portfolio.wallet_address,
                    "status": "error",
                    "error": "Failed to check sync status"
                }
        else:
            wallet_sync_status = {
                "wallet_configured": False
            }

        # Convert to CryptoPortfolioResponse with currency-specific fields
        base_currency_str = (
                portfolio.base_currency.value if hasattr(portfolio.base_currency, 'value')
                else str(portfolio.base_currency)
            )
        portfolio_response = CryptoPortfolioResponse(
            id=portfolio.id,
            name=portfolio.name,
            description=portfolio.description,
            is_active=portfolio.is_active,
            base_currency=portfolio.base_currency,
            wallet_address=portfolio.wallet_address,
            created_at=portfolio.created_at,
            updated_at=portfolio.updated_at,
            # Add currency-specific fields for frontend compatibility
            total_value_usd=metrics.total_value if metrics and base_currency_str == 'USD' else None,
            total_value_eur=metrics.total_value if metrics and base_currency_str == 'EUR' else None,
            total_profit_usd=metrics.total_profit_loss if metrics and base_currency_str == 'USD' else None,
            total_profit_eur=metrics.total_profit_loss if metrics and base_currency_str == 'EUR' else None,
            profit_percentage_usd=metrics.total_profit_loss_pct if metrics and base_currency_str == 'USD' else None,
            profit_percentage_eur=metrics.total_profit_loss_pct if metrics and base_currency_str == 'EUR' else None,
            # Keep original fields for backward compatibility
            total_value=metrics.total_value if metrics else None,
            total_cost_basis=metrics.total_cost_basis if metrics else None,
            total_profit_loss=metrics.total_profit_loss if metrics else None,
            total_profit_loss_pct=metrics.total_profit_loss_pct if metrics else None,
            transaction_count=metrics.transaction_count if metrics else 0,
            wallet_sync_status=wallet_sync_status
        )

        return portfolio_response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get portfolio: {str(e)}")


@router.put("/portfolios/{portfolio_id}", response_model=CryptoPortfolioResponse)
async def update_crypto_portfolio(
    portfolio_id: int,
    portfolio_update: CryptoPortfolioUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update the fields of an existing crypto portfolio.

    Updates only the fields provided in `portfolio_update`, sets the portfolio's `updated_at`
    timestamp to the current UTC time, persists the changes, and returns the refreshed portfolio.

    Parameters:
        portfolio_id (int): ID of the portfolio to update.
        portfolio_update (CryptoPortfolioUpdate): Fields to update; only set fields are applied.
        db (AsyncSession): Database session dependency (omitted from docs when generating user-facing API docs).

    Returns:
        CryptoPortfolio: The updated portfolio instance after commit and refresh.

    Raises:
        HTTPException: 404 if the portfolio does not exist.
        HTTPException: 400 if another portfolio already uses the requested name.
        HTTPException: 500 if an unexpected error occurs while updating (transaction is rolled back).
    """
    try:
        # Get existing portfolio
        result = await db.execute(
            select(CryptoPortfolio).where(CryptoPortfolio.id == portfolio_id)
        )
        portfolio = result.scalar_one_or_none()

        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        # Check for name conflicts
        if portfolio_update.name and portfolio_update.name != portfolio.name:
            existing_result = await db.execute(
                select(CryptoPortfolio).where(
                    CryptoPortfolio.name == portfolio_update.name,
                    CryptoPortfolio.id != portfolio_id
                )
            )
            existing_portfolio = existing_result.scalar_one_or_none()

            if existing_portfolio:
                raise HTTPException(
                    status_code=400,
                    detail="Portfolio with this name already exists"
                )

        # Update portfolio fields
        update_data = portfolio_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(portfolio, field, value)

        portfolio.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(portfolio)

        return portfolio

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update portfolio: {str(e)}")


@router.delete("/portfolios/{portfolio_id}", status_code=204)
async def delete_crypto_portfolio(
    portfolio_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete the crypto portfolio identified by portfolio_id and its associated transactions.

    Raises:
        HTTPException: 404 if the portfolio does not exist.
        HTTPException: 500 if deletion fails.
    """
    try:
        # Check if portfolio exists
        result = await db.execute(
            select(CryptoPortfolio).where(CryptoPortfolio.id == portfolio_id)
        )
        portfolio = result.scalar_one_or_none()

        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        # Delete portfolio (cascades to transactions)
        await db.delete(portfolio)
        await db.commit()

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete portfolio: {str(e)}")


# Transaction Management Endpoints

@router.post("/portfolios/{portfolio_id}/transactions", response_model=CryptoTransactionResponse, status_code=201)
async def create_crypto_transaction(
    portfolio_id: int,
    transaction_data: CryptoTransactionCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create and persist a crypto transaction for the specified portfolio.

    Validates that the portfolio exists and is active, rejects duplicate transaction hashes when provided,
computes the transaction total (quantity * price_at_execution), saves the transaction, and returns
the persisted CryptoTransaction with database-populated fields.

    Parameters:
        portfolio_id (int): ID of the portfolio to which the transaction will be added.
        transaction_data (CryptoTransactionCreate): Transaction payload containing
            symbol, quantity, price, timestamp, and optional fields.

    Returns:
        CryptoTransaction: The created and refreshed transaction instance with persisted fields populated.

    Raises:
        HTTPException: 404 if the portfolio is not found.
        HTTPException: 400 if the portfolio is inactive or a transaction with the same hash already exists.
        HTTPException: 500 if an unexpected error occurs while persisting the transaction.
    """
    try:
        # Verify portfolio exists
        portfolio_result = await db.execute(
            select(CryptoPortfolio).where(CryptoPortfolio.id == portfolio_id)
        )
        portfolio = portfolio_result.scalar_one_or_none()

        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        if not portfolio.is_active:
            raise HTTPException(status_code=400, detail="Cannot add transactions to inactive portfolio")

        # Validate transaction data
        if transaction_data.transaction_hash:
            # Check for duplicate transaction hash
            existing_hash_result = await db.execute(
                select(CryptoTransaction).where(
                    CryptoTransaction.transaction_hash == transaction_data.transaction_hash
                )
            )
            existing_hash = existing_hash_result.scalar_one_or_none()

            if existing_hash:
                raise HTTPException(
                    status_code=400,
                    detail="Transaction with this hash already exists"
                )

        # Calculate total amount
        total_amount = transaction_data.quantity * transaction_data.price_at_execution

        # Create transaction
        transaction = CryptoTransaction(
            portfolio_id=portfolio_id,
            symbol=transaction_data.symbol.upper(),
            transaction_type=transaction_data.transaction_type,
            quantity=transaction_data.quantity,
            price_at_execution=transaction_data.price_at_execution,
            currency=transaction_data.currency,
            total_amount=total_amount,
            fee=transaction_data.fee,
            fee_currency=transaction_data.fee_currency,
            timestamp=transaction_data.timestamp,
            exchange=transaction_data.exchange,
            transaction_hash=transaction_data.transaction_hash,
            notes=transaction_data.notes
        )

        db.add(transaction)
        await db.commit()
        await db.refresh(transaction)

        return transaction

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create transaction: {str(e)}")


@router.get("/portfolios/{portfolio_id}/transactions", response_model=CryptoTransactionList)
async def list_crypto_transactions(
    portfolio_id: int,
    symbol: Optional[str] = Query(None, description="Filter by crypto symbol"),
    transaction_type: Optional[CryptoTransactionType] = Query(None, description="Filter by transaction type"),
    start_date: Optional[datetime] = Query(None, description="Filter transactions from this date"),
    end_date: Optional[datetime] = Query(None, description="Filter transactions to this date"),
    skip: int = Query(0, ge=0, description="Number of transactions to skip"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of transactions to return"),
    db: AsyncSession = Depends(get_db)
):
    """
    List transactions belonging to a crypto portfolio, with optional filtering and pagination.

    Filters may be applied by symbol (case-insensitive), transaction type, and timestamp range. The result is
ordered by timestamp descending and paginated using skip/limit.

    Parameters:
        portfolio_id (int): ID of the portfolio whose transactions are returned.
        symbol (Optional[str]): Filter by crypto symbol (case-insensitive).
        transaction_type (Optional[CryptoTransactionType]): Filter by transaction type.
        start_date (Optional[datetime]): Include transactions on or after this timestamp.
        end_date (Optional[datetime]): Include transactions on or before this timestamp.
        skip (int): Number of transactions to skip (offset).
        limit (int): Maximum number of transactions to return.
        db (AsyncSession): Database session dependency.

    Returns:
        CryptoTransactionList: Object containing `transactions` (list of CryptoTransaction) and `total_count` (int).

    Raises:
        HTTPException: 404 if the portfolio does not exist; 500 for unexpected errors.
    """
    try:
        # Verify portfolio exists
        portfolio_result = await db.execute(
            select(CryptoPortfolio).where(CryptoPortfolio.id == portfolio_id)
        )
        portfolio = portfolio_result.scalar_one_or_none()

        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        # Build query
        query = select(CryptoTransaction).where(CryptoTransaction.portfolio_id == portfolio_id)

        # Apply filters
        if symbol:
            query = query.where(CryptoTransaction.symbol == symbol.upper())
        if transaction_type:
            query = query.where(CryptoTransaction.transaction_type == transaction_type)
        if start_date:
            query = query.where(CryptoTransaction.timestamp >= start_date)
        if end_date:
            query = query.where(CryptoTransaction.timestamp <= end_date)

        # Count total transactions
        count_query = select(func.count()).select_from(query.subquery())
        total_count_result = await db.execute(count_query)
        total_count = total_count_result.scalar()

        # Apply pagination and ordering
        query = query.order_by(CryptoTransaction.timestamp.desc()).offset(skip).limit(limit)
        result = await db.execute(query)
        transactions = result.scalars().all()

        return CryptoTransactionList(
            items=transactions,
            total=total_count,
            skip=skip,
            limit=limit
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list transactions: {str(e)}")


@router.put("/transactions/{transaction_id}", response_model=CryptoTransactionResponse)
async def update_crypto_transaction(
    transaction_id: int,
    transaction_update: CryptoTransactionUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update fields of an existing crypto transaction.

    If `quantity` or `price_at_execution` are changed, `total_amount` is recalculated. If `symbol` is updated
it will be normalized to upper-case.

    Parameters:
        transaction_update (CryptoTransactionUpdate): Fields to update; unset fields are ignored.

    Returns:
        CryptoTransaction: The updated transaction record.

    Raises:
        HTTPException: With status 404 if the transaction does not exist.
        HTTPException: With status 400 if another transaction already uses the provided `transaction_hash`.
        HTTPException: With status 500 for other failures during the update.
    """
    try:
        # Get existing transaction
        result = await db.execute(
            select(CryptoTransaction).where(CryptoTransaction.id == transaction_id)
        )
        transaction = result.scalar_one_or_none()

        if not transaction:
            raise HTTPException(status_code=404, detail="Transaction not found")

        # Check for duplicate transaction hash
        if transaction_update.transaction_hash and transaction_update.transaction_hash != transaction.transaction_hash:
            existing_hash_result = await db.execute(
                select(CryptoTransaction).where(
                    CryptoTransaction.transaction_hash == transaction_update.transaction_hash,
                    CryptoTransaction.id != transaction_id
                )
            )
            existing_hash = existing_hash_result.scalar_one_or_none()

            if existing_hash:
                raise HTTPException(
                    status_code=400,
                    detail="Transaction with this hash already exists"
                )

        # Update transaction fields
        update_data = transaction_update.dict(exclude_unset=True)

        # Recalculate total amount if quantity or price changed
        if 'quantity' in update_data or 'price_at_execution' in update_data:
            quantity = update_data.get('quantity', transaction.quantity)
            price = update_data.get('price_at_execution', transaction.price_at_execution)
            update_data['total_amount'] = quantity * price

        for field, value in update_data.items():
            if field == 'symbol':
                setattr(transaction, field, value.upper())
            else:
                setattr(transaction, field, value)

        transaction.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(transaction)

        return transaction

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update transaction: {str(e)}")


@router.delete("/transactions/{transaction_id}", status_code=204)
async def delete_crypto_transaction(
    transaction_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete the crypto transaction with the given ID.

    Raises:
        HTTPException: 404 if no transaction with the specified ID exists.
        HTTPException: 500 if the deletion fails due to an internal error.
    """
    try:
        # Check if transaction exists
        result = await db.execute(
            select(CryptoTransaction).where(CryptoTransaction.id == transaction_id)
        )
        transaction = result.scalar_one_or_none()

        if not transaction:
            raise HTTPException(status_code=404, detail="Transaction not found")

        # Delete transaction
        await db.delete(transaction)
        await db.commit()

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete transaction: {str(e)}")


# Wallet Sync Status Endpoint

@router.get("/portfolios/{portfolio_id}/wallet-sync-status")
async def get_wallet_sync_status(
    portfolio_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get wallet synchronization status for a crypto portfolio.

    Returns detailed information about the wallet sync state including:
    - Current sync status (synced, syncing, error, never, disabled)
    - Last sync timestamp
    - Transaction counts (total and recent)
    - Error messages if applicable

    Parameters:
        portfolio_id (int): ID of the portfolio to check wallet sync status for.

    Returns:
        dict: Wallet sync status information with keys:
            - status: Current sync state
            - last_sync: ISO timestamp of last successful sync (optional)
            - transaction_count: Total blockchain transactions synced (optional)
            - error_message: Error details if status is 'error' (optional)

    Raises:
        HTTPException: 404 if the portfolio does not exist; 500 for unexpected errors.
    """
    try:
        # Check if wallet is currently syncing (Redis-based real-time status)
        logger.info(f"Checking Redis sync status for portfolio {portfolio_id}")
        try:
            import redis
            import json

            # Connect to Redis directly
            redis_client = redis.from_url(settings.redis_url, decode_responses=True)
            key = f"wallet_sync:{portfolio_id}"
            value = redis_client.get(key)
            logger.info(f"Redis key {key}: {value}")

            if value:
                try:
                    sync_status = json.loads(value)
                    logger.info(f"Parsed sync status: {sync_status}")
                    if sync_status.get("status") == "syncing":
                        logger.info(f"Returning syncing status for portfolio {portfolio_id}")
                        return {
                            "status": "syncing",
                            "last_sync": None,
                            "transaction_count": None,
                            "error_message": None,
                            "task_id": sync_status.get("task_id"),
                            "started_at": sync_status.get("started_at")
                        }
                except json.JSONDecodeError:
                    logger.warning(f"Invalid sync status JSON for portfolio {portfolio_id}")
                    # Clear invalid data
                    redis_client.delete(key)
        except Exception as e:
            logger.error(f"Error checking Redis sync status for portfolio {portfolio_id}: {e}")
            # Continue with normal status checking if Redis fails
        # Verify portfolio exists
        portfolio_result = await db.execute(
            select(CryptoPortfolio).where(CryptoPortfolio.id == portfolio_id)
        )
        portfolio = portfolio_result.scalar_one_or_none()

        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        # If no wallet address configured, return disabled status
        if not portfolio.wallet_address:
            return {
                "status": "disabled",
                "last_sync": None,
                "transaction_count": None,
                "error_message": None
            }

        try:
            # Get total blockchain transactions for this portfolio
            total_blockchain_tx_count = await db.execute(
                select(func.count(CryptoTransaction.id))
                .where(
                    and_(
                        CryptoTransaction.portfolio_id == portfolio_id,
                        CryptoTransaction.exchange == 'Bitcoin Blockchain'
                    )
                )
            )
            total_blockchain_txs = total_blockchain_tx_count.scalar() or 0

            # Get last blockchain transaction date
            last_blockchain_tx_result = await db.execute(
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

            # Determine sync status based on transaction data and sync timestamp
            if total_blockchain_txs == 0:
                status = "never"
                last_sync_time = None
            else:
                status = "synced"
                # Use the stored wallet_last_sync_time if available, otherwise fall back to last blockchain transaction
                last_sync_time = portfolio.wallet_last_sync_time if portfolio.wallet_last_sync_time else last_blockchain_tx

            return {
                "status": status,
                "last_sync": last_sync_time.isoformat() if last_sync_time else None,
                "transaction_count": total_blockchain_txs,
                "error_message": None
            }

        except Exception as e:
            logger.error(f"Error fetching wallet sync status for portfolio {portfolio_id}: {e}")
            return {
                "status": "error",
                "last_sync": None,
                "transaction_count": None,
                "error_message": f"Failed to retrieve wallet sync status: {str(e)}"
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get wallet sync status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get wallet sync status: {str(e)}")


# Metrics and Analytics Endpoints

@router.get("/portfolios/{portfolio_id}/metrics", response_model=CryptoPortfolioMetrics)
async def get_crypto_portfolio_metrics(
    portfolio_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve computed metrics for a crypto portfolio.

    Parameters:
        portfolio_id (int): ID of the portfolio to compute metrics for.

    Returns:
        CryptoPortfolioMetrics: Calculated portfolio metrics for the given portfolio.

    Raises:
        HTTPException: 404 if the portfolio does not exist.
        HTTPException: 500 if an unexpected error prevents metrics calculation.
    """
    try:
        calc_service = CryptoCalculationService(db)
        metrics = await calc_service.calculate_portfolio_metrics(portfolio_id)

        if not metrics:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        return metrics

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate portfolio metrics: {str(e)}")


@router.get("/portfolios/{portfolio_id}/holdings", response_model=List[CryptoHolding])
async def get_crypto_portfolio_holdings(
    portfolio_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve current crypto holdings for a portfolio.

    Returns:
        List[CryptoHolding]: Current holdings for the specified portfolio.

    Raises:
        HTTPException: 404 if the portfolio does not exist; 500 if holdings calculation fails.
    """
    try:
        calc_service = CryptoCalculationService(db)
        holdings = await calc_service.calculate_holdings(portfolio_id)

        if holdings is None:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        return holdings

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate holdings: {str(e)}")


@router.get("/portfolios/{portfolio_id}/holdings/{symbol}", response_model=CryptoHolding)
async def get_crypto_holding(
    portfolio_id: int,
    symbol: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve a specific crypto holding by symbol for a portfolio.

    Parameters:
        portfolio_id (int): ID of the portfolio.
        symbol (str): Crypto symbol (e.g., BTC, ETH).

    Returns:
        CryptoHolding: The holding for the specified symbol.

    Raises:
        HTTPException: 404 if the portfolio does not exist or symbol not held; 500 if calculation fails.
    """
    try:
        calc_service = CryptoCalculationService(db)
        holdings = await calc_service.calculate_holdings(portfolio_id)

        if holdings is None:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        # Find the specific holding by symbol (case-insensitive)
        symbol_upper = symbol.upper()
        holding = next((h for h in holdings if h.symbol == symbol_upper), None)

        if not holding:
            raise HTTPException(status_code=404, detail=f"No holdings found for symbol {symbol}")

        return holding

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get holding: {str(e)}")


@router.get("/portfolios/{portfolio_id}/performance")
async def get_crypto_portfolio_performance(
    portfolio_id: int,
    range: str = Query("1M", regex="^(1D|1W|1M|3M|6M|1Y|ALL)$", description="Time range for performance data"),
    db: AsyncSession = Depends(get_db)
):
    """
    Return time-series performance snapshots for a crypto portfolio over a preset range.

    Parameters:
        range (str): Time window for performance. Allowed values: "1D", "1W", "1M", "3M", "6M", "1Y", "ALL".

    Returns:
        List[dict]: A list of daily performance points with keys:
            - `date` (str): ISO-8601 date string.
            - `portfolio_value` (float): Portfolio value on that date.
            - `cost_basis` (float): Cost basis on that date.
            - `profit_loss` (float): Absolute profit or loss on that date.
            - `profit_loss_pct` (float): Profit or loss as a percentage.

    Raises:
        HTTPException: 404 if the portfolio does not exist; 500 if performance data cannot be retrieved.
    """
    try:
        # Verify portfolio exists
        portfolio_result = await db.execute(
            select(CryptoPortfolio).where(CryptoPortfolio.id == portfolio_id)
        )
        portfolio = portfolio_result.scalar_one_or_none()

        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        # Calculate date range based on range parameter
        original_end_date = datetime.utcnow().date()
        end_date = original_end_date

        # Adjust end_date to exclude dates that likely don't have market data yet
        if end_date >= date.today():
            end_date = adjust_end_date_for_data_availability(date.today(), days_buffer=2)
            logger.info(f"API: Adjusted end_date from {original_end_date} to {end_date} for data availability")

        # Parse time range using centralized utility function
        # Using parse_time_range to ensure consistency across the application
        parsed_start_date, _ = parse_time_range(range)

        if parsed_start_date is None:
            # For "ALL" range, use a reasonable default (5 years back from end_date)
            start_date = end_date - timedelta(days=365 * 5)
        else:
            start_date = parsed_start_date

        logger.info(f"API: Using date range {start_date} to {end_date} for performance calculation")

        calc_service = CryptoCalculationService(db)
        performance_data = await calc_service.calculate_performance_history(
            portfolio_id, start_date, end_date
        )

        # If no performance data, return empty array
        if not performance_data:
            return []

        # Convert to frontend-compatible format
        frontend_performance_data = []
        for data_point in performance_data:
            frontend_performance_data.append({
                "date": data_point.date.isoformat() if hasattr(data_point.date, 'isoformat') else str(data_point.date),
                "portfolio_value": float(data_point.portfolio_value) if data_point.portfolio_value else 0.0,
                "cost_basis": float(data_point.cost_basis) if data_point.cost_basis else 0.0,
                "profit_loss": float(data_point.profit_loss) if data_point.profit_loss else 0.0,
                "profit_loss_pct": float(data_point.profit_loss_pct) if data_point.profit_loss_pct is not None else 0.0,
                "currency": data_point.currency or portfolio.base_currency.value
            })

        return frontend_performance_data

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get portfolio performance: {str(e)}")


@router.get("/portfolios/{portfolio_id}/history", response_model=CryptoPortfolioPerformance)
async def get_crypto_portfolio_history(
    portfolio_id: int,
    start_date: date = Query(..., description="Start date for performance data"),
    end_date: date = Query(..., description="End date for performance data"),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve time-series performance for a crypto portfolio over a given date range.

    Parameters:
        portfolio_id (int): ID of the portfolio to query.
        start_date (date): Inclusive start date for the performance range; must be on or before end_date.
        end_date (date): Inclusive end date for the performance range; must be on or after start_date.

    Returns:
        CryptoPortfolioPerformance: Object containing:
            - portfolio_id: the requested portfolio id
            - performance_data: list of performance points (ordered by date)
            - start_value: portfolio value at the start date or None if no data
            - end_value: portfolio value at the end date or None if no data
            - total_return: end_value minus start_value or None
            - total_return_pct: percentage return (0 if start_value is 0) or None

    Raises:
        HTTPException: 400 if start_date is after end_date.
        HTTPException: 404 if the portfolio does not exist.
        HTTPException: 500 for unexpected errors while fetching or computing history.
    """
    try:
        # Validate date range
        if start_date > end_date:
            raise HTTPException(status_code=400, detail="Start date must be before end date")

        # Verify portfolio exists
        portfolio_result = await db.execute(
            select(CryptoPortfolio).where(CryptoPortfolio.id == portfolio_id)
        )
        portfolio = portfolio_result.scalar_one_or_none()

        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        calc_service = CryptoCalculationService(db)
        performance_data = await calc_service.calculate_performance_history(
            portfolio_id, start_date, end_date
        )

        # Calculate summary metrics
        start_value = None
        end_value = None
        total_return = None
        total_return_pct = None

        if performance_data:
            start_value = performance_data[0].portfolio_value
            end_value = performance_data[-1].portfolio_value
            total_return = end_value - start_value
            total_return_pct = float(
                (total_return / start_value) * 100
            ) if start_value > 0 else 0

        return CryptoPortfolioPerformance(
            portfolio_id=portfolio_id,
            performance_data=performance_data,
            start_value=start_value,
            end_value=end_value,
            total_return=total_return,
            total_return_pct=total_return_pct
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get portfolio history: {str(e)}")


# Price Data Endpoints

@router.get("/prices", response_model=CryptoPriceResponse)
async def get_crypto_prices(
    symbols: str = Query(..., description="Comma-separated list of crypto symbols (e.g., BTC,ETH,ADA)"),
    currency: str = Query("eur", pattern="^(eur|usd)$", description="Target currency"),
):
    """
    Retrieve current prices for the given comma-separated crypto symbols and return them in the requested currency.

    Symbols are normalized to uppercase; symbols without a valid current price are omitted. If currency is "EUR",
USD prices are converted using the USD→EUR rate helper. Raises an HTTPException with status 400 when
no symbols are provided or when more than 50 symbols are supplied.

    Returns:
        CryptoPriceResponse: Contains a list of `CryptoPriceData` entries (one per symbol with available price),
                             the response currency (uppercase), and a timestamp.

    Raises:
        HTTPException: Status 400 if the symbols list is empty or exceeds 50 symbols.
    """
    # Parse and validate symbols
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not symbol_list:
        raise HTTPException(status_code=400, detail="At least one symbol is required")
    if len(symbol_list) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 symbols allowed per request")

    price_fetcher = PriceFetcher()
    tickers = [(f"{s}-USD", None) for s in symbol_list]
    batch_results = price_fetcher.fetch_realtime_prices_batch(tickers)
    by_ticker = {d["ticker"]: d for d in batch_results if d and d.get("ticker")}

    conversion_rate = None
    if currency.upper() != "USD":
        conversion_rate = await _get_usd_to_eur_rate()

    prices: list[CryptoPriceData] = []
    for s in symbol_list:
        data = by_ticker.get(f"{s}-USD")
        if not data or not data.get("current_price"):
            continue
        price = data["current_price"]
        if currency.upper() != "USD" and conversion_rate:
            price = price * conversion_rate
        prices.append(CryptoPriceData(
            symbol=s,
            price=price,
            currency=currency.upper(),
            price_usd=data["current_price"],
            market_cap_usd=None,
            volume_24h_usd=None,
            change_percent_24h=float(data.get("change_percent", 0)) if data.get("change_percent") else None,
            timestamp=data.get("timestamp", datetime.utcnow()),
            source="yahoo",
        ))

    return CryptoPriceResponse(
        prices=prices,
        currency=currency.upper(),
        timestamp=datetime.utcnow(),
    )


@router.get("/prices/history", response_model=CryptoPriceHistoryResponse)
async def get_crypto_price_history(
    symbol: str = Query(..., description="Crypto symbol (e.g., BTC, ETH)"),
    start_date: date = Query(..., description="Start date for historical data"),
    end_date: date = Query(..., description="End date for historical data"),
    currency: str = Query("eur", pattern="^(eur|usd)$", description="Target currency"),
):
    """
    Retrieve historical daily close prices for a cryptocurrency over a specified date range.

    Parameters:
        symbol (str): Crypto symbol (e.g., "BTC", "ETH").
        start_date (date): Start date for the historical range (inclusive).
        end_date (date): End date for the historical range (inclusive).
        currency (str): Target currency for returned prices ("EUR" or "USD").

    Returns:
        CryptoPriceHistoryResponse: Response containing the requested symbol, target currency,
        a list of `CryptoHistoricalPrice` records (each with date, symbol, price in the requested
        currency, price_usd, timestamp, and source), and `total_count` equal to the number of returned entries.

    Raises:
        HTTPException: Raised with status 400 for invalid input (e.g., invalid symbol, start_date > end_date,
        or a date range longer than 365 days), or with status 500 for unexpected failures while fetching or
        processing historical price data.
    """
    try:
        # Validate inputs
        if not symbol or len(symbol) > 20:
            raise HTTPException(status_code=400, detail="Invalid symbol")

        if start_date > end_date:
            raise HTTPException(status_code=400, detail="Start date must be before end date")

        # Limit date range to prevent excessive requests
        days_diff = (end_date - start_date).days
        if days_diff > 365:
            raise HTTPException(status_code=400, detail="Date range cannot exceed 365 days")

        # Get historical prices from Yahoo Finance (USD)
        price_fetcher = PriceFetcher()
        yahoo_symbol = f"{symbol}-USD"
        historical_prices = await price_fetcher.fetch_historical_prices(
            yahoo_symbol, start_date=start_date, end_date=end_date
        )

        conversion_rate = None
        if currency.upper() != "USD":
            conversion_rate = await _get_usd_to_eur_rate()

        prices = []
        for dp in historical_prices:
            px = dp["close"]
            px_conv = px * conversion_rate if (conversion_rate and currency.upper() != "USD") else px
            prices.append(CryptoHistoricalPrice(
                date=dp["date"],
                symbol=symbol.upper(),
                price=px_conv,
                currency=currency.upper(),
                price_usd=dp["close"],
                timestamp=datetime.utcnow(),
                source=dp.get("source", "yahoo"),
            ))

        return CryptoPriceHistoryResponse(
            symbol=symbol,
            currency=currency.upper(),
            prices=prices,
            total_count=len(prices)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get crypto price history: {str(e)}")


@router.get("/supported-symbols")
async def get_supported_crypto_symbols():
    """Get list of supported cryptocurrency symbols."""
    try:
        # Return a curated list of popular cryptocurrencies supported by Yahoo Finance
        # This is a reasonable approach since Yahoo Finance supports most major cryptos
        supported_assets = [
            {"symbol": "BTC", "name": "Bitcoin", "yahoo_symbol": "BTC-USD"},
            {"symbol": "ETH", "name": "Ethereum", "yahoo_symbol": "ETH-USD"},
            {"symbol": "BNB", "name": "Binance Coin", "yahoo_symbol": "BNB-USD"},
            {"symbol": "XRP", "name": "Ripple", "yahoo_symbol": "XRP-USD"},
            {"symbol": "ADA", "name": "Cardano", "yahoo_symbol": "ADA-USD"},
            {"symbol": "SOL", "name": "Solana", "yahoo_symbol": "SOL-USD"},
            {"symbol": "DOGE", "name": "Dogecoin", "yahoo_symbol": "DOGE-USD"},
            {"symbol": "DOT", "name": "Polkadot", "yahoo_symbol": "DOT-USD"},
            {"symbol": "MATIC", "name": "Polygon", "yahoo_symbol": "MATIC-USD"},
            {"symbol": "SHIB", "name": "Shiba Inu", "yahoo_symbol": "SHIB-USD"},
            {"symbol": "AVAX", "name": "Avalanche", "yahoo_symbol": "AVAX-USD"},
            {"symbol": "LINK", "name": "Chainlink", "yahoo_symbol": "LINK-USD"},
            {"symbol": "UNI", "name": "Uniswap", "yahoo_symbol": "UNI-USD"},
            {"symbol": "LTC", "name": "Litecoin", "yahoo_symbol": "LTC-USD"},
            {"symbol": "ATOM", "name": "Cosmos", "yahoo_symbol": "ATOM-USD"},
            {"symbol": "XLM", "name": "Stellar", "yahoo_symbol": "XLM-USD"},
            {"symbol": "BCH", "name": "Bitcoin Cash", "yahoo_symbol": "BCH-USD"},
            {"symbol": "FIL", "name": "Filecoin", "yahoo_symbol": "FIL-USD"},
            {"symbol": "TRX", "name": "TRON", "yahoo_symbol": "TRX-USD"},
            {"symbol": "ETC", "name": "Ethereum Classic", "yahoo_symbol": "ETC-USD"},
            {"symbol": "XMR", "name": "Monero", "yahoo_symbol": "XMR-USD"},
            {"symbol": "USDT", "name": "Tether", "yahoo_symbol": "USDT-USD"},
            {"symbol": "USDC", "name": "USD Coin", "yahoo_symbol": "USDC-USD"},
            {"symbol": "AAVE", "name": "Aave", "yahoo_symbol": "AAVE-USD"},
            {"symbol": "MKR", "name": "Maker", "yahoo_symbol": "MKR-USD"},
            {"symbol": "COMP", "name": "Compound", "yahoo_symbol": "COMP-USD"},
            {"symbol": "SUSHI", "name": "Sushi", "yahoo_symbol": "SUSHI-USD"},
            {"symbol": "ICP", "name": "Internet Computer", "yahoo_symbol": "ICP-USD"},
            {"symbol": "HBAR", "name": "Hedera", "yahoo_symbol": "HBAR-USD"},
            {"symbol": "VET", "name": "VeChain", "yahoo_symbol": "VET-USD"},
            {"symbol": "THETA", "name": "Theta", "yahoo_symbol": "THETA-USD"},
            {"symbol": "ALGO", "name": "Algorand", "yahoo_symbol": "ALGO-USD"},
            {"symbol": "LRC", "name": "Loopring", "yahoo_symbol": "LRC-USD"},
            {"symbol": "ENJ", "name": "Enjin Coin", "yahoo_symbol": "ENJ-USD"},
            {"symbol": "CRO", "name": "Cronos", "yahoo_symbol": "CRO-USD"},
            {"symbol": "MANA", "name": "Decentraland", "yahoo_symbol": "MANA-USD"},
            {"symbol": "SAND", "name": "The Sandbox", "yahoo_symbol": "SAND-USD"},
            {"symbol": "AXS", "name": "Axie Infinity", "yahoo_symbol": "AXS-USD"},
            {"symbol": "GALA", "name": "Gala", "yahoo_symbol": "GALA-USD"},
            {"symbol": "CHZ", "name": "Chiliz", "yahoo_symbol": "CHZ-USD"},
            {"symbol": "NEAR", "name": "NEAR Protocol", "yahoo_symbol": "NEAR-USD"},
            {"symbol": "EGLD", "name": "MultiversX", "yahoo_symbol": "EGLD-USD"},
            {"symbol": "FTT", "name": "FTX Token", "yahoo_symbol": "FTT-USD"},
            {"symbol": "HOT", "name": "Holo", "yahoo_symbol": "HOT-USD"},
            {"symbol": "AR", "name": "Arweave", "yahoo_symbol": "AR-USD"},
            {"symbol": "STX", "name": "Stacks", "yahoo_symbol": "STX-USD"},
            {"symbol": "RUNE", "name": "THORChain", "yahoo_symbol": "RUNE-USD"},
            {"symbol": "ZEC", "name": "Zcash", "yahoo_symbol": "ZEC-USD"},
            {"symbol": "KSM", "name": "Kusama", "yahoo_symbol": "KSM-USD"},
            {"symbol": "KAVA", "name": "Kava", "yahoo_symbol": "KAVA-USD"},
            {"symbol": "WAVES", "name": "Waves", "yahoo_symbol": "WAVES-USD"},
            {"symbol": "QTUM", "name": "Qtum", "yahoo_symbol": "QTUM-USD"},
            {"symbol": "XTZ", "name": "Tezos", "yahoo_symbol": "XTZ-USD"},
            {"symbol": "EOS", "name": "EOS", "yahoo_symbol": "EOS-USD"},
            {"symbol": "BTG", "name": "Bitcoin Gold", "yahoo_symbol": "BTG-USD"},
            {"symbol": "BSV", "name": "Bitcoin SV", "yahoo_symbol": "BSV-USD"},
            {"symbol": "NEO", "name": "NEO", "yahoo_symbol": "NEO-USD"},
            {"symbol": "MIOTA", "name": "IOTA", "yahoo_symbol": "MIOTA-USD"},
            {"symbol": "ZIL", "name": "Zilliqa", "yahoo_symbol": "ZIL-USD"},
            {"symbol": "BAT", "name": "Basic Attention Token", "yahoo_symbol": "BAT-USD"},
            {"symbol": "GRT", "name": "The Graph", "yahoo_symbol": "GRT-USD"},
            {"symbol": "OCEAN", "name": "Ocean Protocol", "yahoo_symbol": "OCEAN-USD"},
            {"symbol": "KNC", "name": "Kyber Network", "yahoo_symbol": "KNC-USD"},
            {"symbol": "ZRX", "name": "0x", "yahoo_symbol": "ZRX-USD"},
            {"symbol": "BAND", "name": "Band Protocol", "yahoo_symbol": "BAND-USD"},
            {"symbol": "RLC", "name": "iExec RLC", "yahoo_symbol": "RLC-USD"},
            {"symbol": "LPT", "name": "Livepeer", "yahoo_symbol": "LPT-USD"},
            {"symbol": "STORJ", "name": "Storj", "yahoo_symbol": "STORJ-USD"},
            {"symbol": "COTI", "name": "COTI", "yahoo_symbol": "COTI-USD"}
        ]

        return {
            "symbols": supported_assets,
            "total_count": len(supported_assets),
            "timestamp": datetime.utcnow()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get supported symbols: {str(e)}")


@router.get("/health")
async def crypto_health_check():
    """
    Checks availability of external crypto services and returns a health summary.

    Returns:
        A dict with the following keys:
        - status (str): One of "healthy", "degraded", or "unhealthy".
        - services (dict): Mapping of service names to their status ("healthy" or "unhealthy").
        - timestamp (datetime): UTC datetime when the check was performed.
        - error (str, optional): Error message present when status is "unhealthy".
    """
    try:
        # Test Yahoo Finance connection
        price_fetcher = PriceFetcher()
        test_price = price_fetcher.fetch_realtime_price("BTC-USD")
        yahoo_healthy = test_price is not None

        return {
            "status": "healthy" if yahoo_healthy else "degraded",
            "services": {
                "yahoo_finance": "healthy" if yahoo_healthy else "unhealthy"
            },
            "timestamp": datetime.utcnow()
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow()
        }
