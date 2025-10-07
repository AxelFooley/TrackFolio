"""
Crypto Paper Wallet API endpoints.

Handles crypto portfolio management, transactions, and analytics.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, and_, or_
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime, date, timedelta
import logging

from app.database import get_db
from app.models.crypto_paper import CryptoPaperPortfolio, CryptoPaperTransaction, CryptoTransactionType
from app.schemas.crypto_paper import (
    CryptoPaperPortfolioCreate,
    CryptoPaperPortfolioResponse,
    CryptoPaperPortfolioList,
    CryptoPaperPortfolioUpdate,
    CryptoPaperTransactionCreate,
    CryptoPaperTransactionResponse,
    CryptoPaperTransactionList,
    CryptoPaperTransactionUpdate,
    CryptoPaperMetrics,
    CryptoPaperHolding,
    CryptoPaperHistory,
    CryptoPaperHistoryPoint,
    CryptoPriceResponse,
    CryptoPriceHistoryResponse,
    CryptoPortfolioPerformance,
    CryptoPerformanceDataPoint
)
from app.services.price_fetcher import PriceFetcher
from app.services.calculations import FinancialCalculations
from decimal import Decimal

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/crypto-paper", tags=["crypto-paper"])


# Portfolio Management Endpoints
@router.post("/portfolios", response_model=CryptoPaperPortfolioResponse)
async def create_portfolio(
    portfolio_data: CryptoPaperPortfolioCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new crypto paper portfolio."""
    try:
        portfolio = CryptoPaperPortfolio(
            name=portfolio_data.name,
            description=portfolio_data.description,
            user_id=1  # Default user for single-user setup
        )

        db.add(portfolio)
        await db.commit()
        await db.refresh(portfolio)

        logger.info(f"Created crypto portfolio: {portfolio.name} (ID: {portfolio.id})")
        return portfolio

    except Exception as e:
        logger.error(f"Error creating crypto portfolio: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create portfolio")


@router.get("/portfolios", response_model=CryptoPaperPortfolioList)
async def list_portfolios(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db)
):
    """List all crypto portfolios with basic metrics."""
    try:
        # Get portfolios
        query = select(CryptoPaperPortfolio).offset(skip).limit(limit)
        result = await db.execute(query)
        portfolios = result.scalars().all()

        # Get total count
        count_query = select(func.count(CryptoPaperPortfolio.id))
        count_result = await db.execute(count_query)
        total_count = count_result.scalar()

        # Calculate basic metrics for each portfolio
        portfolio_responses = []
        for portfolio in portfolios:
            metrics = await calculate_portfolio_metrics(db, portfolio.id)
            portfolio_response = CryptoPaperPortfolioResponse(
                id=portfolio.id,
                name=portfolio.name,
                description=portfolio.description,
                user_id=portfolio.user_id,
                created_at=portfolio.created_at,
                updated_at=portfolio.updated_at,
                metrics=metrics
            )
            portfolio_responses.append(portfolio_response)

        return CryptoPaperPortfolioList(
            portfolios=portfolio_responses,
            total_count=total_count
        )

    except Exception as e:
        logger.error(f"Error listing crypto portfolios: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list portfolios")


@router.get("/portfolios/{portfolio_id}", response_model=CryptoPaperPortfolioResponse)
async def get_portfolio(
    portfolio_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific portfolio with full metrics."""
    try:
        result = await db.execute(
            select(CryptoPaperPortfolio).where(CryptoPaperPortfolio.id == portfolio_id)
        )
        portfolio = result.scalar_one_or_none()

        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        # Calculate full metrics
        metrics = await calculate_portfolio_metrics(db, portfolio_id)

        return CryptoPaperPortfolioResponse(
            id=portfolio.id,
            name=portfolio.name,
            description=portfolio.description,
            user_id=portfolio.user_id,
            created_at=portfolio.created_at,
            updated_at=portfolio.updated_at,
            metrics=metrics
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting crypto portfolio {portfolio_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get portfolio")


@router.put("/portfolios/{portfolio_id}", response_model=CryptoPaperPortfolioResponse)
async def update_portfolio(
    portfolio_id: int,
    portfolio_update: CryptoPaperPortfolioUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a crypto portfolio."""
    try:
        result = await db.execute(
            select(CryptoPaperPortfolio).where(CryptoPaperPortfolio.id == portfolio_id)
        )
        portfolio = result.scalar_one_or_none()

        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        # Update fields if provided
        if portfolio_update.name is not None:
            portfolio.name = portfolio_update.name
        if portfolio_update.description is not None:
            portfolio.description = portfolio_update.description

        portfolio.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(portfolio)

        # Calculate metrics
        metrics = await calculate_portfolio_metrics(db, portfolio_id)

        logger.info(f"Updated crypto portfolio: {portfolio.name} (ID: {portfolio.id})")
        return CryptoPaperPortfolioResponse(
            id=portfolio.id,
            name=portfolio.name,
            description=portfolio.description,
            user_id=portfolio.user_id,
            created_at=portfolio.created_at,
            updated_at=portfolio.updated_at,
            metrics=metrics
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating crypto portfolio {portfolio_id}: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update portfolio")


@router.delete("/portfolios/{portfolio_id}")
async def delete_portfolio(
    portfolio_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a crypto portfolio and all its transactions."""
    try:
        result = await db.execute(
            select(CryptoPaperPortfolio).where(CryptoPaperPortfolio.id == portfolio_id)
        )
        portfolio = result.scalar_one_or_none()

        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        # Delete portfolio (cascades to transactions)
        await db.delete(portfolio)
        await db.commit()

        logger.info(f"Deleted crypto portfolio: {portfolio.name} (ID: {portfolio.id})")
        return {"message": "Portfolio deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting crypto portfolio {portfolio_id}: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete portfolio")


# Transaction Management Endpoints
@router.post("/portfolios/{portfolio_id}/transactions", response_model=CryptoPaperTransactionResponse)
async def create_transaction(
    portfolio_id: int,
    transaction_data: CryptoPaperTransactionCreate,
    db: AsyncSession = Depends(get_db)
):
    """Add a new transaction to a portfolio."""
    try:
        # Verify portfolio exists
        portfolio_result = await db.execute(
            select(CryptoPaperPortfolio).where(CryptoPaperPortfolio.id == portfolio_id)
        )
        portfolio = portfolio_result.scalar_one_or_none()

        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        # Validate crypto symbol using CoinGecko
        price_fetcher = PriceFetcher()
        coin_id = price_fetcher._map_ticker_to_coingecko_id(transaction_data.symbol)

        # Create transaction
        transaction = CryptoPaperTransaction(
            portfolio_id=portfolio_id,
            symbol=transaction_data.symbol.upper(),
            coingecko_id=coin_id,
            transaction_type=transaction_data.transaction_type,
            quantity=transaction_data.quantity,
            price_at_execution=transaction_data.price_at_execution,
            currency=transaction_data.currency,
            fee=transaction_data.fee,
            timestamp=transaction_data.timestamp
        )

        db.add(transaction)
        await db.commit()
        await db.refresh(transaction)

        logger.info(f"Created crypto transaction: {transaction.symbol} {transaction.transaction_type.value} "
                   f"{transaction.quantity} for portfolio {portfolio_id}")
        return transaction

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating crypto transaction: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create transaction")


@router.get("/portfolios/{portfolio_id}/transactions", response_model=CryptoPaperTransactionList)
async def list_transactions(
    portfolio_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    symbol: Optional[str] = Query(None, description="Filter by crypto symbol"),
    transaction_type: Optional[CryptoTransactionType] = Query(None, description="Filter by transaction type"),
    db: AsyncSession = Depends(get_db)
):
    """List transactions for a portfolio with optional filtering."""
    try:
        # Verify portfolio exists
        portfolio_result = await db.execute(
            select(CryptoPaperPortfolio).where(CryptoPaperPortfolio.id == portfolio_id)
        )
        portfolio = portfolio_result.scalar_one_or_none()

        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        # Build query
        query = select(CryptoPaperTransaction).where(
            CryptoPaperTransaction.portfolio_id == portfolio_id
        ).order_by(desc(CryptoPaperTransaction.timestamp))

        # Apply filters
        if symbol:
            query = query.where(CryptoPaperTransaction.symbol == symbol.upper())
        if transaction_type:
            query = query.where(CryptoPaperTransaction.transaction_type == transaction_type)

        # Apply pagination
        query = query.offset(skip).limit(limit)

        result = await db.execute(query)
        transactions = result.scalars().all()

        # Get total count
        count_query = select(func.count(CryptoPaperTransaction.id)).where(
            CryptoPaperTransaction.portfolio_id == portfolio_id
        )
        if symbol:
            count_query = count_query.where(CryptoPaperTransaction.symbol == symbol.upper())
        if transaction_type:
            count_query = count_query.where(CryptoPaperTransaction.transaction_type == transaction_type)

        count_result = await db.execute(count_query)
        total_count = count_result.scalar()

        total_pages = (total_count + limit - 1) // limit
        current_page = (skip // limit) + 1

        return CryptoPaperTransactionList(
            transactions=transactions,
            total_count=total_count,
            page=current_page,
            page_size=limit,
            total_pages=total_pages
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing crypto transactions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list transactions")


@router.put("/transactions/{transaction_id}", response_model=CryptoPaperTransactionResponse)
async def update_transaction(
    transaction_id: int,
    transaction_update: CryptoPaperTransactionUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a crypto transaction."""
    try:
        result = await db.execute(
            select(CryptoPaperTransaction).where(CryptoPaperTransaction.id == transaction_id)
        )
        transaction = result.scalar_one_or_none()

        if not transaction:
            raise HTTPException(status_code=404, detail="Transaction not found")

        # Update fields if provided
        if transaction_update.symbol is not None:
            transaction.symbol = transaction_update.symbol.upper()
            # Update CoinGecko ID
            price_fetcher = PriceFetcher()
            transaction.coingecko_id = price_fetcher._map_ticker_to_coingecko_id(transaction_update.symbol)

        if transaction_update.transaction_type is not None:
            transaction.transaction_type = transaction_update.transaction_type

        if transaction_update.quantity is not None:
            transaction.quantity = transaction_update.quantity

        if transaction_update.price_at_execution is not None:
            transaction.price_at_execution = transaction_update.price_at_execution

        if transaction_update.currency is not None:
            transaction.currency = transaction_update.currency

        if transaction_update.fee is not None:
            transaction.fee = transaction_update.fee

        if transaction_update.timestamp is not None:
            transaction.timestamp = transaction_update.timestamp

        transaction.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(transaction)

        logger.info(f"Updated crypto transaction: {transaction.symbol} (ID: {transaction.id})")
        return transaction

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating crypto transaction {transaction_id}: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update transaction")


@router.delete("/transactions/{transaction_id}")
async def delete_transaction(
    transaction_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a crypto transaction."""
    try:
        result = await db.execute(
            select(CryptoPaperTransaction).where(CryptoPaperTransaction.id == transaction_id)
        )
        transaction = result.scalar_one_or_none()

        if not transaction:
            raise HTTPException(status_code=404, detail="Transaction not found")

        await db.delete(transaction)
        await db.commit()

        logger.info(f"Deleted crypto transaction: {transaction.symbol} (ID: {transaction.id})")
        return {"message": "Transaction deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting crypto transaction {transaction_id}: {str(e)}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete transaction")


# Metrics & Analytics Endpoints
@router.get("/portfolios/{portfolio_id}/metrics", response_model=CryptoPaperMetrics)
async def get_portfolio_metrics(
    portfolio_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get current portfolio metrics."""
    try:
        # Verify portfolio exists
        portfolio_result = await db.execute(
            select(CryptoPaperPortfolio).where(CryptoPaperPortfolio.id == portfolio_id)
        )
        portfolio = portfolio_result.scalar_one_or_none()

        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        metrics = await calculate_portfolio_metrics(db, portfolio_id)
        return metrics

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating portfolio metrics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to calculate metrics")


@router.get("/portfolios/{portfolio_id}/history", response_model=CryptoPaperHistory)
async def get_portfolio_history(
    portfolio_id: int,
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db)
):
    """Get historical portfolio value data."""
    try:
        # Verify portfolio exists
        portfolio_result = await db.execute(
            select(CryptoPaperPortfolio).where(CryptoPaperPortfolio.id == portfolio_id)
        )
        portfolio = portfolio_result.scalar_one_or_none()

        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        # Get historical data
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        history = await calculate_portfolio_history(db, portfolio_id, start_date, end_date)

        return CryptoPaperHistory(
            history=history,
            start_date=start_date,
            end_date=end_date,
            total_points=len(history)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting portfolio history: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get history")


@router.get("/portfolios/{portfolio_id}/performance", response_model=CryptoPortfolioPerformance)
async def get_portfolio_performance(
    portfolio_id: int,
    days: int = Query(365, ge=1, le=365),
    db: AsyncSession = Depends(get_db)
):
    """Get portfolio performance data for charting."""
    try:
        # Verify portfolio exists
        portfolio_result = await db.execute(
            select(CryptoPaperPortfolio).where(CryptoPaperPortfolio.id == portfolio_id)
        )
        portfolio = portfolio_result.scalar_one_or_none()
        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        # Get historical data
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        history = await calculate_portfolio_history(db, portfolio_id, start_date, end_date)

        # Convert history to performance data points
        performance_data = [
            CryptoPerformanceDataPoint(
                date=str(point.date),
                value_usd=point.total_value
            ) for point in history
        ]

        # Calculate performance metrics
        if len(performance_data) >= 2:
            start_value = performance_data[0].value_usd
            end_value = performance_data[-1].value_usd
            change_amount = end_value - start_value
            change_pct = (change_amount / start_value * Decimal("100")) if start_value > 0 else Decimal("0")
        else:
            start_value = Decimal("0")
            end_value = Decimal("0")
            change_amount = Decimal("0")
            change_pct = Decimal("0")

        return CryptoPortfolioPerformance(
            portfolio_data=performance_data,
            start_value=start_value,
            end_value=end_value,
            change_amount=change_amount,
            change_pct=change_pct
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting portfolio performance: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get performance data")


@router.get("/portfolios/{portfolio_id}/holdings", response_model=List[CryptoPaperHolding])
async def get_portfolio_holdings(
    portfolio_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get current portfolio holdings."""
    try:
        # Verify portfolio exists
        portfolio_result = await db.execute(
            select(CryptoPaperPortfolio).where(CryptoPaperPortfolio.id == portfolio_id)
        )
        portfolio = portfolio_result.scalar_one_or_none()

        if not portfolio:
            raise HTTPException(status_code=404, detail="Portfolio not found")

        holdings = await calculate_portfolio_holdings(db, portfolio_id)
        return holdings

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting portfolio holdings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get holdings")


# Price Endpoints
@router.get("/prices", response_model=List[CryptoPriceResponse])
async def get_crypto_prices(
    symbols: str = Query(..., description="Comma-separated list of crypto symbols (e.g., BTC,ETH)"),
    currency: str = Query("USD", pattern="^(USD|EUR)$", description="Currency for prices"),
    db: AsyncSession = Depends(get_db)
):
    """Get current prices for multiple cryptocurrencies."""
    try:
        symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
        if not symbol_list:
            raise HTTPException(status_code=400, detail="No symbols provided")

        price_fetcher = PriceFetcher()
        prices = []

        for symbol in symbol_list:
            try:
                # Fetch price from CoinGecko
                price_data = await price_fetcher.fetch_crypto_price(symbol)

                if price_data:
                    # Convert currency if needed
                    current_price = price_data["close"]
                    if currency == "USD" and price_data.get("source") == "coingecko":
                        # CoinGecko returns EUR by default, convert to USD
                        fx_rate = await price_fetcher.fetch_fx_rate("EUR", "USD")
                        if fx_rate:
                            current_price = current_price * fx_rate

                    price_response = CryptoPriceResponse(
                        symbol=symbol,
                        coingecko_id=price_fetcher._map_ticker_to_coingecko_id(symbol),
                        current_price=current_price,
                        currency=currency,
                        volume_24h=Decimal(str(price_data.get("volume", 0))),
                        last_updated=datetime.utcnow()
                    )
                    prices.append(price_response)
                else:
                    logger.warning(f"No price data available for {symbol}")

            except Exception as e:
                logger.error(f"Error fetching price for {symbol}: {str(e)}")
                continue

        return prices

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting crypto prices: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get prices")


@router.get("/prices/history", response_model=CryptoPriceHistoryResponse)
async def get_crypto_price_history(
    symbol: str = Query(..., description="Crypto symbol (e.g., BTC)"),
    days: int = Query(30, ge=1, le=365),
    currency: str = Query("USD", pattern="^(USD|EUR)$", description="Currency for prices"),
    db: AsyncSession = Depends(get_db)
):
    """Get historical price data for a cryptocurrency."""
    try:
        symbol = symbol.upper()

        price_fetcher = PriceFetcher()
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        # Fetch historical prices
        historical_prices = await price_fetcher.fetch_historical_prices(
            symbol, start_date, end_date, is_crypto=True
        )

        # Convert currency if needed
        if currency == "USD":
            fx_rate = await price_fetcher.fetch_fx_rate("EUR", "USD")
            if fx_rate:
                for price_point in historical_prices:
                    price_point["open"] = price_point["open"] * fx_rate
                    price_point["high"] = price_point["high"] * fx_rate
                    price_point["low"] = price_point["low"] * fx_rate
                    price_point["close"] = price_point["close"] * fx_rate

        # Convert to history points
        history_points = [
            CryptoPaperHistoryPoint(
                date=price_point["date"],
                total_value=price_point["close"],
                cost_basis=Decimal("0"),  # Not applicable for price history
                total_pl=Decimal("0")     # Not applicable for price history
            )
            for price_point in historical_prices
        ]

        return CryptoPriceHistoryResponse(
            symbol=symbol,
            currency=currency,
            history=history_points,
            total_points=len(history_points)
        )

    except Exception as e:
        logger.error(f"Error getting crypto price history for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get price history")


# Helper Functions
async def calculate_portfolio_metrics(db: AsyncSession, portfolio_id: int) -> CryptoPaperMetrics:
    """Calculate comprehensive portfolio metrics."""
    try:
        # Get all transactions for the portfolio
        result = await db.execute(
            select(CryptoPaperTransaction).where(
                CryptoPaperTransaction.portfolio_id == portfolio_id
            ).order_by(CryptoPaperTransaction.timestamp)
        )
        transactions = result.scalars().all()

        if not transactions:
            return CryptoPaperMetrics(
                total_value=Decimal("0"),
                cost_basis=Decimal("0"),
                unrealized_pl=Decimal("0"),
                realized_pl=Decimal("0"),
                total_pl=Decimal("0"),
                total_invested=Decimal("0"),
                quantity_change=Decimal("0")
            )

        price_fetcher = PriceFetcher()
        total_value = Decimal("0")
        cost_basis = Decimal("0")
        realized_pl = Decimal("0")
        total_invested = Decimal("0")
        quantity_change = Decimal("0")

        # Group transactions by symbol
        symbol_positions = {}

        for txn in transactions:
            symbol = txn.symbol
            if symbol not in symbol_positions:
                symbol_positions[symbol] = {
                    "quantity": Decimal("0"),
                    "total_cost": Decimal("0"),
                    "realized_pl": Decimal("0")
                }

            position = symbol_positions[symbol]

            if txn.transaction_type == CryptoTransactionType.BUY:
                position["quantity"] += txn.quantity
                total_cost = txn.quantity * txn.price_at_execution + txn.fee
                position["total_cost"] += total_cost
                total_invested += total_cost
                quantity_change += txn.quantity

            elif txn.transaction_type == CryptoTransactionType.SELL:
                if position["quantity"] > 0:
                    # Calculate realized P&L using FIFO
                    avg_cost_per_unit = position["total_cost"] / position["quantity"] if position["quantity"] > 0 else Decimal("0")
                    sale_proceeds = txn.quantity * txn.price_at_execution - txn.fee
                    cost_of_sold = txn.quantity * avg_cost_per_unit
                    realized_gain = sale_proceeds - cost_of_sold

                    position["realized_pl"] += realized_gain
                    realized_pl += realized_gain

                    # Update position
                    cost_reduction = cost_of_sold
                    position["total_cost"] -= cost_reduction
                    position["quantity"] -= txn.quantity
                    quantity_change -= txn.quantity

            elif txn.transaction_type == CryptoTransactionType.TRANSFER_IN:
                position["quantity"] += txn.quantity
                quantity_change += txn.quantity

            elif txn.transaction_type == CryptoTransactionType.TRANSFER_OUT:
                position["quantity"] -= txn.quantity
                quantity_change -= txn.quantity

        # Calculate current value and unrealized P&L
        for symbol, position in symbol_positions.items():
            if position["quantity"] > 0:
                try:
                    # Get current price
                    price_data = await price_fetcher.fetch_crypto_price(symbol)
                    if price_data:
                        current_price = price_data["close"]
                        current_value = position["quantity"] * current_price
                        total_value += current_value
                        cost_basis += position["total_cost"]
                except Exception as e:
                    logger.warning(f"Could not fetch price for {symbol}: {str(e)}")

        # Calculate totals
        unrealized_pl = total_value - cost_basis
        total_pl = realized_pl + unrealized_pl

        # Calculate IRR
        irr = None
        try:
            cash_flows = []
            for txn in transactions:
                if txn.transaction_type in [CryptoTransactionType.BUY]:
                    amount = -(txn.quantity * txn.price_at_execution + txn.fee)
                    cash_flows.append((txn.timestamp.date(), amount))

            if cash_flows and total_value > 0:
                irr = FinancialCalculations.calculate_irr(
                    cash_flows, total_value, date.today()
                )
                if irr is not None:
                    irr = Decimal(str(irr))
        except Exception as e:
            logger.warning(f"IRR calculation failed: {str(e)}")

        return CryptoPaperMetrics(
            total_value=total_value,
            cost_basis=cost_basis,
            unrealized_pl=unrealized_pl,
            realized_pl=realized_pl,
            total_pl=total_pl,
            irr=irr,
            total_invested=total_invested,
            quantity_change=quantity_change
        )

    except Exception as e:
        logger.error(f"Error calculating portfolio metrics: {str(e)}")
        raise


async def calculate_portfolio_history(
    db: AsyncSession,
    portfolio_id: int,
    start_date: date,
    end_date: date
) -> List[CryptoPaperHistoryPoint]:
    """Calculate historical portfolio value."""
    try:
        # This is a simplified implementation
        # In a production system, you'd want to store daily snapshots
        # or calculate more efficiently using time buckets

        result = await db.execute(
            select(CryptoPaperTransaction).where(
                and_(
                    CryptoPaperTransaction.portfolio_id == portfolio_id,
                    CryptoPaperTransaction.timestamp >= datetime.combine(start_date, datetime.min.time()),
                    CryptoPaperTransaction.timestamp <= datetime.combine(end_date, datetime.max.time())
                )
            ).order_by(CryptoPaperTransaction.timestamp)
        )
        transactions = result.scalars().all()

        history_points = []
        price_fetcher = PriceFetcher()

        # Generate daily points
        current_date = start_date
        while current_date <= end_date:
            try:
                # Calculate portfolio value for this date
                portfolio_value = Decimal("0")

                # Get all transactions up to this date
                for txn in transactions:
                    if txn.timestamp.date() <= current_date:
                        if txn.transaction_type in [CryptoTransactionType.BUY, CryptoTransactionType.TRANSFER_IN]:
                            # Add to value
                            try:
                                price_data = await price_fetcher.fetch_historical_prices(
                                    txn.symbol, current_date, current_date, is_crypto=True
                                )
                                if price_data:
                                    current_price = price_data[0]["close"]
                                    portfolio_value += txn.quantity * current_price
                            except:
                                pass

                history_point = CryptoPaperHistoryPoint(
                    date=current_date,
                    total_value=portfolio_value,
                    cost_basis=Decimal("0"),  # Simplified
                    total_pl=Decimal("0")      # Simplified
                )
                history_points.append(history_point)

                current_date += timedelta(days=1)

            except Exception as e:
                logger.warning(f"Error calculating history for {current_date}: {str(e)}")
                current_date += timedelta(days=1)

        return history_points

    except Exception as e:
        logger.error(f"Error calculating portfolio history: {str(e)}")
        return []


async def calculate_portfolio_holdings(db: AsyncSession, portfolio_id: int) -> List[CryptoPaperHolding]:
    """Calculate current portfolio holdings."""
    try:
        # Get all transactions
        result = await db.execute(
            select(CryptoPaperTransaction).where(
                CryptoPaperTransaction.portfolio_id == portfolio_id
            ).order_by(CryptoPaperTransaction.timestamp)
        )
        transactions = result.scalars().all()

        # Group by symbol and calculate positions
        symbol_positions = {}

        for txn in transactions:
            symbol = txn.symbol
            if symbol not in symbol_positions:
                symbol_positions[symbol] = {
                    "quantity": Decimal("0"),
                    "total_cost": Decimal("0"),
                    "currency": txn.currency
                }

            position = symbol_positions[symbol]

            if txn.transaction_type == CryptoTransactionType.BUY:
                position["quantity"] += txn.quantity
                position["total_cost"] += txn.quantity * txn.price_at_execution + txn.fee

            elif txn.transaction_type == CryptoTransactionType.SELL:
                if position["quantity"] > 0:
                    avg_cost_per_unit = position["total_cost"] / position["quantity"]
                    cost_reduction = txn.quantity * avg_cost_per_unit
                    position["total_cost"] -= cost_reduction
                    position["quantity"] -= txn.quantity

            elif txn.transaction_type == CryptoTransactionType.TRANSFER_IN:
                position["quantity"] += txn.quantity

            elif txn.transaction_type == CryptoTransactionType.TRANSFER_OUT:
                position["quantity"] -= txn.quantity

        # Create holdings list
        holdings = []
        price_fetcher = PriceFetcher()

        for symbol, position in symbol_positions.items():
            if position["quantity"] > 0:
                try:
                    # Get current price
                    price_data = await price_fetcher.fetch_crypto_price(symbol)
                    current_price = price_data["close"] if price_data else Decimal("0")
                    current_value = position["quantity"] * current_price

                    average_cost = position["total_cost"] / position["quantity"] if position["quantity"] > 0 else Decimal("0")
                    unrealized_pl = current_value - position["total_cost"]
                    unrealized_pl_percent = (unrealized_pl / position["total_cost"] * 100) if position["total_cost"] > 0 else Decimal("0")

                    holding = CryptoPaperHolding(
                        symbol=symbol,
                        quantity=position["quantity"],
                        average_cost=average_cost,
                        current_price=current_price,
                        current_value=current_value,
                        total_cost=position["total_cost"],
                        unrealized_pl=unrealized_pl,
                        unrealized_pl_percent=unrealized_pl_percent,
                        currency=position["currency"],
                        last_updated=datetime.utcnow()
                    )
                    holdings.append(holding)

                except Exception as e:
                    logger.warning(f"Could not calculate holding for {symbol}: {str(e)}")

        return holdings

    except Exception as e:
        logger.error(f"Error calculating portfolio holdings: {str(e)}")
        return []