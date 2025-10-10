"""
Crypto portfolio calculation service.

Provides comprehensive portfolio calculations for crypto assets including:
- Portfolio metrics (value, cost basis, P&L)
- IRR calculations
- Holdings aggregation
- Performance tracking
- FIFO accounting for realized gains/losses
"""
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import numpy_financial as npf

from app.models.crypto import CryptoPortfolio, CryptoTransaction, CryptoTransactionType
from app.schemas.crypto import (
    CryptoPortfolioMetrics,
    CryptoHolding,
    CryptoPerformanceData,
    CryptoCurrency
)
from app.services.price_fetcher import PriceFetcher

logger = logging.getLogger(__name__)


class CryptoCalculationService:
    """Service for calculating crypto portfolio metrics."""

    def __init__(self, db: AsyncSession):
        """Initialize with database session."""
        self.db = db

    async def calculate_portfolio_metrics(self, portfolio_id: int) -> Optional[CryptoPortfolioMetrics]:
        """
        Calculate comprehensive portfolio metrics for a crypto portfolio.

        Args:
            portfolio_id: ID of the crypto portfolio

        Returns:
            CryptoPortfolioMetrics object or None if portfolio not found
        """
        try:
            # Get portfolio
            portfolio_result = await self.db.execute(
                select(CryptoPortfolio).where(CryptoPortfolio.id == portfolio_id)
            )
            portfolio = portfolio_result.scalar_one_or_none()

            if not portfolio:
                logger.warning(f"Portfolio {portfolio_id} not found")
                return None

            # Get all transactions for the portfolio
            transactions_result = await self.db.execute(
                select(CryptoTransaction)
                .where(CryptoTransaction.portfolio_id == portfolio_id)
                .order_by(CryptoTransaction.timestamp)
            )
            transactions = transactions_result.scalars().all()

            if not transactions:
                # Return empty metrics for portfolio with no transactions
                return CryptoPortfolioMetrics(
                    portfolio_id=portfolio_id,
                    base_currency=portfolio.base_currency.value,
                    total_cost_basis=Decimal("0"),
                    realized_gain_loss=Decimal("0"),
                    total_deposits=Decimal("0"),
                    total_withdrawals=Decimal("0"),
                    holdings_count=0,
                    transaction_count=0
                )

            # Calculate base metrics
            cost_basis = Decimal("0")
            realized_gain_loss = Decimal("0")
            total_deposits = Decimal("0")
            total_withdrawals = Decimal("0")

            # Calculate holdings using FIFO
            holdings = await self._calculate_holdings(transactions)
            holdings_value = Decimal("0")

            # Get current prices for all holdings
            symbols = list(holdings.keys())
            if symbols:
                current_prices = await self._get_current_prices(symbols, portfolio.base_currency.value)

                for symbol, holding_data in holdings.items():
                    current_price = current_prices.get(symbol, {}).get('price')
                    if current_price:
                        current_value = holding_data['quantity'] * current_price
                        holdings_value += current_value
                        holdings[symbol]['current_price'] = current_price
                        holdings[symbol]['current_value'] = current_value
                        holdings[symbol]['unrealized_gain_loss'] = current_value - holding_data['cost_basis']
                        holdings[symbol]['unrealized_gain_loss_pct'] = float(
                            ((current_value - holding_data['cost_basis']) / holding_data['cost_basis']) * 100
                        ) if holding_data['cost_basis'] > 0 else 0

            # Calculate deposits and withdrawals
            for tx in transactions:
                if tx.transaction_type in [CryptoTransactionType.BUY, CryptoTransactionType.TRANSFER_IN]:
                    total_deposits += tx.total_amount
                elif tx.transaction_type in [CryptoTransactionType.SELL, CryptoTransactionType.TRANSFER_OUT]:
                    total_withdrawals += tx.total_amount

            # Calculate realized gains/losses using FIFO
            fifo_queues = defaultdict(list)  # symbol -> list of (quantity, price, timestamp)

            for tx in transactions:
                if tx.transaction_type in [CryptoTransactionType.BUY, CryptoTransactionType.TRANSFER_IN]:
                    # Add to FIFO queue
                    fifo_queues[tx.symbol].append((tx.quantity, tx.price_at_execution, tx.timestamp))
                    cost_basis += tx.total_amount
                elif tx.transaction_type in [CryptoTransactionType.SELL, CryptoTransactionType.TRANSFER_OUT]:
                    # Process FIFO
                    remaining_quantity = tx.quantity
                    realized_proceeds = Decimal("0")
                    realized_cost = Decimal("0")

                    queue = fifo_queues.get(tx.symbol, [])
                    while remaining_quantity > 0 and queue:
                        lot_quantity, lot_price, lot_timestamp = queue[0]

                        if lot_quantity <= remaining_quantity:
                            # Consume entire lot
                            realized_proceeds += lot_quantity * tx.price_at_execution
                            realized_cost += lot_quantity * lot_price
                            remaining_quantity -= lot_quantity
                            queue.pop(0)
                        else:
                            # Partial lot consumption
                            realized_proceeds += remaining_quantity * tx.price_at_execution
                            realized_cost += remaining_quantity * lot_price
                            queue[0] = (lot_quantity - remaining_quantity, lot_price, lot_timestamp)
                            remaining_quantity = 0

                    if realized_cost > 0:
                        realized_gain_loss += realized_proceeds - realized_cost

            # Calculate total profit/loss against current holdings cost basis
            current_cost_basis = sum(h['cost_basis'] for h in holdings.values())
            total_profit_loss = holdings_value - current_cost_basis
            total_profit_loss_pct = float(
                (total_profit_loss / current_cost_basis) * 100
            ) if current_cost_basis > 0 else 0
            # Calculate IRR
            irr = await self._calculate_irr(transactions, holdings_value)

            # Calculate asset allocation
            asset_allocation = []
            if holdings_value > 0:
                for symbol, holding_data in holdings.items():
                    if holding_data.get('current_value'):
                        allocation_pct = float((holding_data['current_value'] / holdings_value) * 100)
                        asset_allocation.append({
                            'symbol': symbol,
                            'value': holding_data['current_value'],
                            'percentage': allocation_pct
                        })
                asset_allocation.sort(key=lambda x: x['percentage'], reverse=True)

            # Calculate currency breakdown
            currency_breakdown = []
            if holdings_value > 0:
                for symbol, holding_data in holdings.items():
                    if holding_data.get('current_value'):
                        currency_allocation_pct = float((holding_data['current_value'] / holdings_value) * 100)
                        currency_breakdown.append({
                            'currency': portfolio.base_currency.value,
                            'symbol': symbol,
                            'value': holding_data['current_value'],
                            'percentage': currency_allocation_pct
                        })

            return CryptoPortfolioMetrics(
                portfolio_id=portfolio_id,
                base_currency=portfolio.base_currency.value,
                total_value=holdings_value,
                total_cost_basis=cost_basis,
                total_profit_loss=total_profit_loss,
                total_profit_loss_pct=total_profit_loss_pct,
                unrealized_gain_loss=total_profit_loss,
                realized_gain_loss=realized_gain_loss,
                total_deposits=total_deposits,
                total_withdrawals=total_withdrawals,
                internal_rate_of_return=irr,
                holdings_count=len(holdings),
                transaction_count=len(transactions),
                asset_allocation=asset_allocation,
                currency_breakdown=currency_breakdown
            )

        except Exception as e:
            logger.error(f"Error calculating portfolio metrics for {portfolio_id}: {e}")
            return None

    async def calculate_holdings(self, portfolio_id: int) -> List[CryptoHolding]:
        """
        Calculate current holdings for a crypto portfolio.

        Args:
            portfolio_id: ID of the crypto portfolio

        Returns:
            List of CryptoHolding objects
        """
        try:
            # Get all transactions
            transactions_result = await self.db.execute(
                select(CryptoTransaction)
                .where(CryptoTransaction.portfolio_id == portfolio_id)
                .order_by(CryptoTransaction.timestamp)
            )
            transactions = transactions_result.scalars().all()

            if not transactions:
                return []

            # Calculate holdings
            holdings_data = await self._calculate_holdings(transactions)

            # Get current prices
            symbols = list(holdings_data.keys())
            current_prices = await self._get_current_prices(symbols, "EUR")  # Default to EUR

            # Convert to CryptoHolding objects
            holdings = []
            for symbol, data in holdings_data.items():
                current_price = current_prices.get(symbol, {}).get('price')
                current_value = data['quantity'] * current_price if current_price else None

                holding = CryptoHolding(
                    symbol=symbol,
                    quantity=data['quantity'],
                    average_cost=data['average_cost'],
                    cost_basis=data['cost_basis'],
                    current_price=current_price,
                    current_value=current_value,
                    unrealized_gain_loss=current_value - data['cost_basis'] if current_value else None,
                    unrealized_gain_loss_pct=float(
                        ((current_value - data['cost_basis']) / data['cost_basis']) * 100
                    ) if current_value and data['cost_basis'] > 0 else None,
                    first_purchase_date=data['first_purchase_date'],
                    last_transaction_date=data['last_transaction_date']
                )
                holdings.append(holding)

            return holdings

        except Exception as e:
            logger.error(f"Error calculating holdings for portfolio {portfolio_id}: {e}")
            return []

    async def calculate_performance_history(
        self,
        portfolio_id: int,
        start_date: date,
        end_date: date
    ) -> List[CryptoPerformanceData]:
        """
        Calculate portfolio performance history over a date range.

        Args:
            portfolio_id: ID of the crypto portfolio
            start_date: Start date for performance data
            end_date: End date for performance data

        Returns:
            List of CryptoPerformanceData objects
        """
        try:
            # Get all transactions up to end_date
            transactions_result = await self.db.execute(
                select(CryptoTransaction)
                .where(
                    CryptoTransaction.portfolio_id == portfolio_id,
                    CryptoTransaction.timestamp <= datetime.combine(end_date, datetime.max.time())
                )
                .order_by(CryptoTransaction.timestamp)
            )
            transactions = transactions_result.scalars().all()

            # Generate daily performance data
            performance_data = []
            current_date = start_date

            while current_date <= end_date:
                # Filter transactions up to current date
                transactions_up_to_date = [
                    tx for tx in transactions
                    if tx.timestamp.date() <= current_date
                ]

                # Calculate holdings up to current date
                holdings = await self._calculate_holdings(transactions_up_to_date)

                # Get historical prices for current date
                symbols = list(holdings.keys())
                # Get portfolio base currency
                portfolio_result = await self.db.execute(
                    select(CryptoPortfolio).where(CryptoPortfolio.id == portfolio_id)
                )
                portfolio = portfolio_result.scalar_one_or_none()
                base_currency = portfolio.base_currency.value if portfolio else "EUR"

                historical_prices = await self._get_historical_prices(
                    symbols,
                    current_date,
                    current_date,
                    base_currency
                )

                # Calculate portfolio value
                portfolio_value = Decimal("0")
                cost_basis = sum(h['cost_basis'] for h in holdings.values())

                for symbol, holding_data in holdings.items():
                    price_data = historical_prices.get(symbol, [{}])
                    if price_data and 'price' in price_data[0]:
                        portfolio_value += holding_data['quantity'] * price_data[0]['price']

                profit_loss = portfolio_value - cost_basis
                profit_loss_pct = float(
                    (profit_loss / cost_basis) * 100
                ) if cost_basis > 0 else 0

                performance_data.append(CryptoPerformanceData(
                    date=current_date,
                    portfolio_value=portfolio_value,
                    cost_basis=cost_basis,
                    profit_loss=profit_loss,
                    profit_loss_pct=profit_loss_pct
                ))

                current_date += timedelta(days=1)

            return performance_data

        except Exception as e:
            logger.error(f"Error calculating performance history for portfolio {portfolio_id}: {e}")
            return []

    async def _calculate_holdings(self, transactions: List[CryptoTransaction]) -> Dict[str, Dict]:
        """
        Calculate holdings from transactions using FIFO method.

        Args:
            transactions: List of crypto transactions

        Returns:
            Dictionary of holdings data by symbol
        """
        holdings = {}

        for tx in transactions:
            symbol = tx.symbol

            if symbol not in holdings:
                holdings[symbol] = {
                    'quantity': Decimal("0"),
                    'cost_basis': Decimal("0"),
                    'average_cost': Decimal("0"),
                    'first_purchase_date': None,
                    'last_transaction_date': None,
                    'realized_gain_loss': Decimal("0"),
                    'transactions': []
                }

            # Handle different transaction types
            if tx.transaction_type in [CryptoTransactionType.BUY, CryptoTransactionType.TRANSFER_IN]:
                holdings[symbol]['quantity'] += tx.quantity
                holdings[symbol]['cost_basis'] += tx.total_amount
                holdings[symbol]['last_transaction_date'] = tx.timestamp.date()

                if not holdings[symbol]['first_purchase_date']:
                    holdings[symbol]['first_purchase_date'] = tx.timestamp.date()

            elif tx.transaction_type in [CryptoTransactionType.SELL, CryptoTransactionType.TRANSFER_OUT]:
                holdings[symbol]['quantity'] -= tx.quantity
                holdings[symbol]['last_transaction_date'] = tx.timestamp.date()

                # Remove holding if quantity reaches zero
                if holdings[symbol]['quantity'] <= 0:
                    del holdings[symbol]
                    continue

            # Recalculate average cost
            if holdings[symbol]['quantity'] > 0:
                holdings[symbol]['average_cost'] = (
                    holdings[symbol]['cost_basis'] / holdings[symbol]['quantity']
                )

        return holdings

    async def _get_current_prices(self, symbols: List[str], currency: str) -> Dict[str, Dict]:
        """
        Get current prices for multiple symbols using Yahoo Finance.

        Args:
            symbols: List of crypto symbols
            currency: Target currency

        Returns:
            Dictionary of price data by symbol
        """
        prices = {}
        price_fetcher = PriceFetcher()

        for symbol in symbols:
            try:
                # Add appropriate suffix for crypto symbols on Yahoo Finance
                yahoo_symbol = f"{symbol}-USD" if symbol not in ['USDT', 'USDC'] else f"{symbol}-USD"

                # Use Yahoo Finance to fetch current price
                price_data = price_fetcher.fetch_realtime_price(yahoo_symbol)

                if price_data and price_data.get('current_price'):
                    price = price_data['current_price']

                    # Convert to target currency if needed (Yahoo returns USD)
                    if currency.lower() == 'eur':
                        # Get USD to EUR conversion rate
                        eur_rate = await self._get_usd_to_eur_rate()
                        if eur_rate:
                            price = price * eur_rate
                        else:
                            logger.warning(f"Could not convert {symbol} price to EUR, using USD")

                    prices[symbol] = {
                        'symbol': symbol,
                        'price': price,
                        'currency': currency.upper(),
                        'price_usd': price_data['current_price'],
                        'timestamp': datetime.utcnow(),
                        'source': 'yahoo'
                    }
                else:
                    # No fallback - if Yahoo Finance fails, we don't add the price
                    logger.warning(f"Could not fetch price for {symbol} from Yahoo Finance - skipping")
            except Exception as e:
                logger.warning(f"Error getting current price for {symbol}: {e}")

        return prices

    async def _get_historical_prices(
        self,
        symbols: List[str],
        start_date: date,
        end_date: date,
        currency: str
    ) -> Dict[str, List[Dict]]:
        """
        Get historical prices for multiple symbols using Yahoo Finance.

        Args:
            symbols: List of crypto symbols
            start_date: Start date
            end_date: End date
            currency: Target currency

        Returns:
            Dictionary of historical price data by symbol
        """
        prices = {}
        price_fetcher = PriceFetcher()

        for symbol in symbols:
            try:
                # Add appropriate suffix for crypto symbols on Yahoo Finance
                yahoo_symbol = f"{symbol}-USD" if symbol not in ['USDT', 'USDC'] else f"{symbol}-USD"

                # Use Yahoo Finance to fetch historical prices
                price_data = price_fetcher.fetch_historical_prices_sync(
                    yahoo_symbol,
                    start_date=start_date,
                    end_date=end_date
                )

                if price_data:
                    # Convert to target currency if needed (Yahoo returns USD)
                    if currency.lower() == 'eur':
                        eur_rate = await self._get_usd_to_eur_rate()
                        if eur_rate:
                            for data_point in price_data:
                                data_point['price'] = data_point['close'] * eur_rate
                                data_point['currency'] = 'EUR'
                        else:
                            for data_point in price_data:
                                data_point['price'] = data_point['close']
                                data_point['currency'] = 'USD'
                    else:
                        for data_point in price_data:
                            data_point['price'] = data_point['close']
                            data_point['currency'] = 'USD'

                    # Format to match expected structure
                    formatted_data = []
                    for data_point in price_data:
                        formatted_data.append({
                            'date': data_point['date'],
                            'symbol': symbol,
                            'price': data_point['price'],
                            'currency': data_point['currency'],
                            'price_usd': data_point['close'],
                            'timestamp': datetime.utcnow(),
                            'source': 'yahoo'
                        })

                    prices[symbol] = formatted_data
                else:
                    logger.warning(f"No historical data available for {symbol}")
            except Exception as e:
                logger.warning(f"Error getting historical prices for {symbol}: {e}")

        return prices

    async def _get_usd_to_eur_rate(self) -> Optional[Decimal]:
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

    async def _calculate_irr(self, transactions: List[CryptoTransaction], current_value: Decimal) -> Optional[float]:
        """
        Calculate Internal Rate of Return for the portfolio.

        Args:
            transactions: List of transactions
            current_value: Current portfolio value

        Returns:
            IRR as a percentage or None if calculation fails
        """
        try:
            # Prepare cash flows
            cash_flows = []
            dates = []

            # Add transactions
            for tx in transactions:
                if tx.transaction_type == CryptoTransactionType.BUY:
                    cash_flows.append(-float(tx.total_amount))
                elif tx.transaction_type == CryptoTransactionType.SELL:
                    cash_flows.append(float(tx.total_amount))
                else:
                    continue  # Skip transfers for IRR calculation

                dates.append(tx.timestamp.date())

            if not cash_flows:
                return None

            # Add current value
            cash_flows.append(float(current_value))
            dates.append(date.today())

            # Sort by date
            sorted_data = sorted(zip(dates, cash_flows), key=lambda x: x[0])
            sorted_dates = [d for d, _ in sorted_data]
            sorted_flows = [cf for _, cf in sorted_data]

            # Calculate IRR using numpy_financial
            try:
                irr_decimal = npf.irr(sorted_flows)
                irr_percentage = irr_decimal * 100
                return irr_percentage
            except Exception as e:
                logger.warning(f"Error calculating IRR: {e}")
                return None

        except Exception as e:
            logger.error(f"Error in IRR calculation: {e}")
            return None

    async def calculate_portfolio_summary(self, portfolio_id: int) -> Dict[str, Any]:
        """
        Get a comprehensive summary of a crypto portfolio.

        Args:
            portfolio_id: ID of the crypto portfolio

        Returns:
            Dictionary with portfolio summary data
        """
        try:
            # Get portfolio
            portfolio_result = await self.db.execute(
                select(CryptoPortfolio).where(CryptoPortfolio.id == portfolio_id)
            )
            portfolio = portfolio_result.scalar_one_or_none()

            if not portfolio:
                return {}

            # Calculate metrics
            metrics = await self.calculate_portfolio_metrics(portfolio_id)
            holdings = await self.calculate_holdings(portfolio_id)

            # Get recent transactions (last 10)
            recent_transactions_result = await self.db.execute(
                select(CryptoTransaction)
                .where(CryptoTransaction.portfolio_id == portfolio_id)
                .order_by(CryptoTransaction.timestamp.desc())
                .limit(10)
            )
            recent_transactions = recent_transactions_result.scalars().all()

            return {
                'portfolio': portfolio,
                'metrics': metrics,
                'holdings': holdings,
                'recent_transactions': recent_transactions
            }

        except Exception as e:
            logger.error(f"Error calculating portfolio summary for {portfolio_id}: {e}")
            return {}