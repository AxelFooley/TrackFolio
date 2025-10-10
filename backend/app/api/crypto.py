"""
Crypto portfolio API endpoints.

Comprehensive API for managing crypto portfolios, transactions, and analytics.
Follows existing codebase patterns with proper error handling and async database sessions.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func, and_
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
    CryptoPerformanceData,
    CryptoPortfolioPerformance,
    CryptoPriceData,
    CryptoHistoricalPrice,
    CryptoPriceRequest,
    CryptoPriceResponse,
    CryptoPriceHistoryRequest,
    CryptoPriceHistoryResponse,
    CryptoPortfolioSummary,
    CryptoError
)
from app.services.crypto_calculations import CryptoCalculationService
from app.services.price_fetcher import PriceFetcher

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/crypto", tags=["crypto"])


async def _get_usd_to_eur_rate() -> Optional[Decimal]:
    """
    Get USD to EUR conversion rate using Yahoo Finance.

    Returns:
        USD to EUR conversion rate or None if failed
    """
    try:
        price_fetcher = PriceFetcher()
        import asyncio
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
    """Create a new crypto portfolio."""
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
    """List crypto portfolios with optional filtering and pagination."""
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

            portfolio_dict = {
                "id": portfolio.id,
                "name": portfolio.name,
                "description": portfolio.description,
                "is_active": portfolio.is_active,
                "base_currency": portfolio.base_currency,
                "wallet_address": portfolio.wallet_address,
                "created_at": portfolio.created_at,
                "updated_at": portfolio.updated_at,
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


@router.get("/portfolios/{portfolio_id}", response_model=CryptoPortfolioSummary)
async def get_crypto_portfolio(
    portfolio_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get detailed crypto portfolio information with metrics and holdings."""
    try:
        calc_service = CryptoCalculationService(db)
        summary = await calc_service.calculate_portfolio_summary(portfolio_id)

        if not summary or not summary.get('portfolio'):
            raise HTTPException(status_code=404, detail="Portfolio not found")

        # Add wallet sync status to portfolio response
        portfolio = summary['portfolio']
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

        # Add wallet sync status to the portfolio object
        if hasattr(portfolio, '__dict__'):
            portfolio.__dict__['wallet_sync_status'] = wallet_sync_status
        else:
            # For SQLAlchemy objects, we'll add this in the response serialization
            summary['wallet_sync_status'] = wallet_sync_status

        return summary

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
    """Update crypto portfolio details."""
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
    """Delete a crypto portfolio and all its transactions."""
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
    """Add a transaction to a crypto portfolio."""
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
    """List transactions for a crypto portfolio with filtering and pagination."""
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
            transactions=transactions,
            total_count=total_count
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
    """Update a crypto transaction."""
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
    """Delete a crypto transaction."""
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


# Metrics and Analytics Endpoints

@router.get("/portfolios/{portfolio_id}/metrics", response_model=CryptoPortfolioMetrics)
async def get_crypto_portfolio_metrics(
    portfolio_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get comprehensive metrics for a crypto portfolio."""
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
    """Get current holdings for a crypto portfolio."""
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


@router.get("/portfolios/{portfolio_id}/performance")
async def get_crypto_portfolio_performance(
    portfolio_id: int,
    range: str = Query("1M", regex="^(1D|1W|1M|3M|6M|1Y|ALL)$", description="Time range for performance data"),
    db: AsyncSession = Depends(get_db)
):
    """Get performance data for a crypto portfolio within a time range."""
    try:
        # Verify portfolio exists
        portfolio_result = await db.execute(
            select(CryptoPortfolio).where(CryptoPortfolio.id == portfolio_id)
        )
        portfolio = portfolio_result.scalar_one_or_none()

        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        # Calculate date range based on range parameter
        end_date = datetime.utcnow().date()

        if range == "1D":
            start_date = end_date - timedelta(days=1)
        elif range == "1W":
            start_date = end_date - timedelta(weeks=1)
        elif range == "1M":
            start_date = end_date - timedelta(days=30)
        elif range == "3M":
            start_date = end_date - timedelta(days=90)
        elif range == "6M":
            start_date = end_date - timedelta(days=180)
        elif range == "1Y":
            start_date = end_date - timedelta(days=365)
        else:  # ALL
            start_date = end_date - timedelta(days=365 * 5)  # 5 years max

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
                "profit_loss_pct": float(data_point.profit_loss_pct) if data_point.profit_loss_pct is not None else 0.0
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
    """Get historical performance data for a crypto portfolio."""
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
    currency: str = Query("eur", regex="^(eur|usd)$", description="Target currency"),
    db: AsyncSession = Depends(get_db)
):
    """Get current prices for multiple cryptocurrencies using Yahoo Finance."""
    try:
        # Parse symbols
        symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]

        if not symbol_list:
            raise HTTPException(status_code=400, detail="At least one symbol is required")

        if len(symbol_list) > 50:
            raise HTTPException(status_code=400, detail="Maximum 50 symbols allowed per request")

@router.get("/prices", response_model=CryptoPriceResponse)
async def get_crypto_prices(
    symbols: str = Query(..., description="Comma-separated list of crypto symbols (e.g., BTC,ETH,ADA)"),
    currency: str = Query("eur", pattern="^(eur|usd)$", description="Target currency"),
):
    # Get prices from Yahoo Finance
    price_fetcher = PriceFetcher()
    # Build batch tickers
    tickers = [(f"{s}-USD", None) for s in symbol_list]
    # Execute sync fetches in threadpool inside helper
    batch = price_fetcher.fetch_realtime_prices_batch(tickers)

    eur_rate = None
    if currency.lower() == 'eur':
        eur_rate = await _get_usd_to_eur_rate()

    prices = []
    for s, data in zip(symbol_list, batch):
        if not data or not data.get('current_price'):
            continue
        price = data['current_price']
        if currency.lower() == 'eur' and eur_rate:
            price *= eur_rate
        prices.append(CryptoPriceData(
            symbol=s,
            price=price,
            currency=currency.upper(),
            price_usd=data['current_price'],
            market_cap_usd=None,
            volume_24h_usd=None,
            change_percent_24h=(
                float(data.get('change_percent', 0))
                if data.get('change_percent')
                else None
            ),
            timestamp=data.get('timestamp', datetime.utcnow()),
            source='yahoo'
        ))
                logger.warning(f"Failed to get price for {symbol}: {e}")
                # Continue with other symbols
                continue

        return CryptoPriceResponse(
            prices=prices,
            currency=currency.upper(),
            timestamp=datetime.utcnow()
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get crypto prices: {str(e)}")


@router.get("/prices/history", response_model=CryptoPriceHistoryResponse)
async def get_crypto_price_history(
    symbol: str = Query(..., description="Crypto symbol (e.g., BTC, ETH)"),
    start_date: date = Query(..., description="Start date for historical data"),
    end_date: date = Query(..., description="End date for historical data"),
    currency: str = Query("eur", regex="^(eur|usd)$", description="Target currency"),
    db: AsyncSession = Depends(get_db)
):
    """Get historical price data for a cryptocurrency using Yahoo Finance."""
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

        # Get historical prices from Yahoo Finance
        price_fetcher = PriceFetcher()
        yahoo_symbol = f"{symbol}-USD"

        historical_prices = await price_fetcher.fetch_historical_prices(
            yahoo_symbol,
            start_date=start_date,
            end_date=end_date
        )
            for data_point in historical_prices
        ]

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


# Utility Endpoints

@router.post("/portfolios/{portfolio_id}/refresh-prices")
async def refresh_crypto_prices(
    portfolio_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Trigger a refresh of crypto prices for a portfolio."""
    try:
        # Verify portfolio exists
        portfolio_result = await db.execute(
            select(CryptoPortfolio).where(CryptoPortfolio.id == portfolio_id)
        )
        portfolio = portfolio_result.scalar_one_or_none()

        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        # Get unique symbols from portfolio transactions
        symbols_result = await db.execute(
            select(func.distinct(CryptoTransaction.symbol))
            .where(CryptoTransaction.portfolio_id == portfolio_id)
        )
        symbols = [row[0] for row in symbols_result.all()]

        if not symbols:
            return {
                "status": "success",
                "message": "No crypto symbols found in portfolio to refresh",
                "portfolio_id": portfolio_id,
                "symbols_updated": [],
                "prices_updated": 0
            }

        # Trigger price update task (synchronous for now)
        from app.tasks.update_crypto_prices import update_crypto_price_for_symbol
        updated_symbols = []
        failed_symbols = []

        for symbol in symbols:
            try:
                # Trigger price update for this symbol
                task_result = update_crypto_price_for_symbol(symbol)
                if task_result.get("status") == "success":
                    updated_symbols.append(symbol)
                else:
                    failed_symbols.append(symbol)
            except Exception as e:
                logger.error(f"Failed to update price for {symbol}: {e}")
                failed_symbols.append(symbol)

        return {
            "status": "success",
            "message": f"Price refresh completed for {len(updated_symbols)} symbols",
            "portfolio_id": portfolio_id,
            "symbols_updated": updated_symbols,
            "symbols_failed": failed_symbols,
            "prices_updated": len(updated_symbols),
            "timestamp": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to refresh crypto prices: {str(e)}")


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
    """Health check for crypto services."""
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


