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
        """
        Create a CryptoCalculationService bound to a database session.
        
        Parameters:
            db (AsyncSession): Async SQLAlchemy session used for database queries and mutations by the service.
        """
        self.db = db

    async def calculate_portfolio_metrics(self, portfolio_id: int) -> Optional[CryptoPortfolioMetrics]:
        """
        Compute comprehensive metrics for a crypto portfolio identified by portfolio_id.
        
        Calculates current holdings using FIFO, fetches current prices, computes total value, cost basis,
        realized and unrealized gains/losses, deposits and withdrawals, asset allocation, currency breakdown,
        and internal rate of return. Returns None if the portfolio does not exist or if an error occurs during calculation.
        
        Parameters:
            portfolio_id (int): Database identifier of the crypto portfolio to analyze.
        
        Returns:
            CryptoPortfolioMetrics or None: Aggregated portfolio metrics when successful, or `None` if the portfolio
            is not found or a processing error occurred.
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

            # Calculate performance insights
            best_performer = {"symbol": "", "asset_name": "", "return_percentage": 0, "current_value": Decimal("0")}
            worst_performer = {"symbol": "", "asset_name": "", "return_percentage": 0, "current_value": Decimal("0")}
            largest_position = {"symbol": "", "asset_name": "", "current_value": Decimal("0"), "return_percentage": 0}

            if holdings:
                # Best performer (highest return percentage)
                best_holdings = sorted(
                    [(symbol, data) for symbol, data in holdings.items() if data.get('unrealized_gain_loss_pct') is not None],
                    key=lambda x: x[1]['unrealized_gain_loss_pct'],
                    reverse=True
                )
                if best_holdings:
                    symbol, data = best_holdings[0]
                    best_performer = {
                        'symbol': symbol,
                        'asset_name': symbol,  # Could be enhanced with asset name lookup
                        'return_percentage': data['unrealized_gain_loss_pct'],
                        'current_value': data.get('current_value', Decimal('0'))
                    }

                # Worst performer (lowest return percentage)
                worst_holdings = sorted(
                    [(symbol, data) for symbol, data in holdings.items() if data.get('unrealized_gain_loss_pct') is not None],
                    key=lambda x: x[1]['unrealized_gain_loss_pct']
                )
                if worst_holdings:
                    symbol, data = worst_holdings[0]
                    worst_performer = {
                        'symbol': symbol,
                        'asset_name': symbol,  # Could be enhanced with asset name lookup
                        'return_percentage': data['unrealized_gain_loss_pct'],
                        'current_value': data.get('current_value', Decimal('0'))
                    }

                # Largest position (highest current value)
                largest_holdings = sorted(
                    [(symbol, data) for symbol, data in holdings.items() if data.get('current_value')],
                    key=lambda x: x[1]['current_value'],
                    reverse=True
                )
                if largest_holdings:
                    symbol, data = largest_holdings[0]
                    largest_position = {
                        'symbol': symbol,
                        'asset_name': symbol,  # Could be enhanced with asset name lookup
                        'current_value': data['current_value'],
                        'return_percentage': data.get('unrealized_gain_loss_pct', 0)
                    }

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
                currency_breakdown=currency_breakdown,
                best_performer=best_performer,
                worst_performer=worst_performer,
                largest_position=largest_position
            )

        except Exception as e:
            logger.error(f"Error calculating portfolio metrics for {portfolio_id}: {e}")
            return None

    async def calculate_holdings(self, portfolio_id: int) -> List[CryptoHolding]:
        """
        Build current crypto holdings for a portfolio and enrich each holding with current price and unrealized P/L.

        Parameters:
            portfolio_id (int): ID of the portfolio to compute holdings for.

        Returns:
            List[CryptoHolding]: A list of holdings where each entry includes symbol, quantity, average cost, cost basis,
            current price (if available), current value (if price available), unrealized gain/loss and unrealized gain/loss
            percentage (if calculable), first purchase date, and last transaction date.
        """
        try:
            # Get portfolio to determine base currency
            portfolio_result = await self.db.execute(
                select(CryptoPortfolio).where(CryptoPortfolio.id == portfolio_id)
            )
            portfolio = portfolio_result.scalar_one_or_none()

            if not portfolio:
                logger.warning(f"Portfolio {portfolio_id} not found")
                return []

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

            # Get current prices using portfolio's base currency
            symbols = list(holdings_data.keys())
            current_prices = await self._get_current_prices(symbols, portfolio.base_currency.value)

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
                    last_transaction_date=data['last_transaction_date'],
                    currency=portfolio.base_currency
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
        Compute daily portfolio performance between start_date and end_date inclusive.

        Parameters:
            portfolio_id (int): ID of the crypto portfolio to evaluate.
            start_date (date): Inclusive start date for the performance series.
            end_date (date): Inclusive end date for the performance series.

        Returns:
            List[CryptoPerformanceData]: One entry per calendar date from start_date to end_date containing portfolio value, cost basis, profit/loss, and profit/loss percentage for that date.
        """
        try:
            # Adjust end_date to exclude today and yesterday (likely no market data)
            today = date.today()
            original_end_date = end_date
            if end_date >= today:
                # If end_date is today or future, set it to two days ago to ensure data availability
                end_date = today - timedelta(days=2)
                logger.info(f"Adjusted end_date from {original_end_date} to {end_date} for data availability")

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

            # Get portfolio base currency
            portfolio_result = await self.db.execute(
                select(CryptoPortfolio).where(CryptoPortfolio.id == portfolio_id)
            )
            portfolio = portfolio_result.scalar_one_or_none()

            if not portfolio:
                return []

            base_currency = portfolio.base_currency.value

            # Calculate holdings up to end_date to determine which symbols we need
            holdings = await self._calculate_holdings(transactions)
            symbols = list(holdings.keys())

            # If no symbols, return empty performance data
            if not symbols:
                return []

            # Fetch historical prices for the entire date range to enable forward-filling
            all_historical_prices = {}
            if symbols:
                # Get prices for the full date range (we'll need these for forward-filling)
                all_historical_prices = await self._get_historical_prices(
                    symbols,
                    start_date,
                    end_date,
                    base_currency
                )

            # Generate daily performance data
            performance_data = []
            current_date = start_date

            # Keep track of the last known prices for forward-filling
            last_known_prices = {}

            while current_date <= end_date:
                # Filter transactions up to current date
                transactions_up_to_date = [
                    tx for tx in transactions
                    if tx.timestamp.date() <= current_date
                ]

                # Calculate holdings up to current date
                holdings = await self._calculate_holdings(transactions_up_to_date)

                # Calculate portfolio value
                portfolio_value = Decimal("0")
                cost_basis = sum(h['cost_basis'] for h in holdings.values())

                # For each symbol, try to get price for current date, or use last known price
                for symbol, holding_data in holdings.items():
                    symbol_prices = all_historical_prices.get(symbol, [])

                    # Try to find price for current date
                    current_price = None
                    if symbol_prices:
                        for price_data in symbol_prices:
                            if price_data['date'] == current_date:
                                current_price = price_data['price']
                                break

                    # If no price for current date, use last known price (forward-fill)
                    if current_price is None and symbol in last_known_prices:
                        current_price = last_known_prices[symbol]

                    # If we found a price (current or forward-filled), use it
                    if current_price is not None:
                        portfolio_value += holding_data['quantity'] * current_price
                        last_known_prices[symbol] = current_price

                profit_loss = portfolio_value - cost_basis
                profit_loss_pct = float(
                    (profit_loss / cost_basis) * 100
                ) if cost_basis > 0 else 0

                # Only add performance data if we have some portfolio value or cost basis
                if portfolio_value > 0 or cost_basis > 0:
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
        Build current holdings per symbol by applying FIFO to the provided transactions.
        
        Parameters:
            transactions: Ordered list of portfolio crypto transactions (chronological) used to derive remaining lots.
        
        Returns:
            Dict mapping symbol (str) to a holding dict containing:
                - quantity (Decimal): total remaining quantity for the symbol.
                - cost_basis (Decimal): sum of remaining lots' cost.
                - average_cost (Decimal): cost_basis divided by quantity.
                - first_purchase_date (date|None): date of the earliest purchase/transfer-in for the symbol, or None if unknown.
                - last_transaction_date (date|None): date of the most recent transaction processed for the symbol, or None if unknown.
                - realized_gain_loss (Decimal): initialized to Decimal('0') for remaining holdings.
                - transactions (List): placeholder list for related transaction entries (may be empty).
        """
        # FIFO lots per symbol: list[(qty, price, ts)]
        lots: Dict[str, list[Tuple[Decimal, Decimal, datetime]]] = defaultdict(list)
        meta: Dict[str, Dict] = {}

        for tx in transactions:
            s = tx.symbol
            if s not in meta:
                meta[s] = {
                    'first_purchase_date': None,
                    'last_transaction_date': None,
                }

            if tx.transaction_type in [CryptoTransactionType.BUY, CryptoTransactionType.TRANSFER_IN]:
                lots[s].append((tx.quantity, tx.price_at_execution, tx.timestamp))
                meta[s]['last_transaction_date'] = tx.timestamp.date()
                if not meta[s]['first_purchase_date']:
                    meta[s]['first_purchase_date'] = tx.timestamp.date()

            elif tx.transaction_type in [CryptoTransactionType.SELL, CryptoTransactionType.TRANSFER_OUT]:
                remaining = tx.quantity
                q = lots.get(s, [])
                while remaining > 0 and q:
                    lot_qty, lot_price, lot_ts = q[0]
                    if lot_qty <= remaining:
                        remaining -= lot_qty
                        q.pop(0)
                    else:
                        q[0] = (lot_qty - remaining, lot_price, lot_ts)
                        remaining = Decimal("0")
                lots[s] = q
                meta[s]['last_transaction_date'] = tx.timestamp.date()

        # Build holdings from remaining lots
        holdings: Dict[str, Dict] = {}
        for s, q in lots.items():
            if not q:
                continue
            total_qty = sum(lq for lq, _, _ in q)
            if total_qty <= 0:
                continue
            cost_basis = sum(lq * lp for lq, lp, _ in q)
            holdings[s] = {
                'quantity': total_qty,
                'cost_basis': cost_basis,
                'average_cost': cost_basis / total_qty,
                'first_purchase_date': meta[s]['first_purchase_date'],
                'last_transaction_date': meta[s]['last_transaction_date'],
                'realized_gain_loss': Decimal("0"),
                'transactions': []
            }

        return holdings

    async def _get_current_prices(self, symbols: List[str], currency: str) -> Dict[str, Dict]:
        """
        Fetch current market prices for the provided crypto symbols and return per-symbol price metadata converted to the requested currency.
        
        Parameters:
            symbols (List[str]): Crypto symbols to query (e.g., "BTC", "ETH").
            currency (str): Target currency code for returned prices (e.g., "EUR" or "USD").
        
        Returns:
            Dict[str, Dict]: Mapping from symbol to a metadata dictionary containing:
                - `symbol`: the queried symbol
                - `price`: current price expressed in `currency`
                - `currency`: the `currency` code used
                - `price_usd`: source price in USD as returned by the provider
                - `timestamp`: UTC timestamp when the price was recorded
                - `source`: price data source identifier
        
        Notes:
            Symbols for which no price could be obtained are omitted from the returned dictionary.
        """
        prices = {}
        price_fetcher = PriceFetcher()

        for symbol in symbols:
            try:
                # Construct ticker with target currency
                yahoo_symbol = f"{symbol}-{currency.upper()}"

                # Use Yahoo Finance to fetch current price
                price_data = price_fetcher.fetch_realtime_price(yahoo_symbol)

                if price_data and price_data.get('current_price'):
                    price = price_data['current_price']

                    prices[symbol] = {
                        'symbol': symbol,
                        'price': price,
                        'currency': currency.upper(),
                        'price_usd': price_data.get('price_usd', price_data.get('current_price')),
                        'timestamp': datetime.utcnow(),
                        'source': 'yahoo'
                    }
                else:
                    logger.warning(f"Could not fetch price for {symbol}-{currency.upper()} from Yahoo Finance - skipping")
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
        Fetch historical price series for multiple symbols from Yahoo Finance and convert prices to the requested currency.

        Parameters:
            symbols (List[str]): Crypto symbols to fetch (e.g., "BTC", "ETH").
            start_date (date): Inclusive start date for historical data.
            end_date (date): Inclusive end date for historical data.
            currency (str): Target currency for returned prices; case-insensitive. If 'EUR', USD prices are converted to EUR using the service's USD→EUR rate; otherwise prices are returned in USD.

        Returns:
            Dict[str, List[Dict]]: Mapping from symbol to a list of price records. Each record contains:
                - 'date' (date): The date of the price point.
                - 'symbol' (str): The original symbol.
                - 'price' (Decimal/float): Price in the requested currency.
                - 'currency' (str): Currency code of 'price' ('EUR' or 'USD').
                - 'price_usd' (Decimal/float): The original USD close price from the source.
                - 'timestamp' (datetime): Retrieval timestamp (UTC).
                - 'source' (str): Data source identifier ('yahoo').

        Notes:
            If no data is available for the requested range, tries to fetch a wider range to get some data.
        """
        prices = {}
        price_fetcher = PriceFetcher()

        # Fetch prices in target currency using currency-aware tickers
        for symbol in symbols:
            try:
                # Construct ticker with target currency
                yahoo_symbol = f"{symbol}-{currency.upper()}"

                # Use Yahoo Finance to fetch historical prices
                price_data = await PriceFetcher.fetch_historical_prices(
                    yahoo_symbol,
                    start_date=start_date,
                    end_date=end_date
                )

                if price_data:
                    # Format to match expected structure
                    formatted_data = []
                    for data_point in price_data:
                        formatted_data.append({
                            'date': data_point['date'],
                            'symbol': symbol,
                            'price': data_point['close'],
                            'currency': currency.upper(),
                            'price_usd': data_point.get('price_usd', data_point['close']),
                            'timestamp': datetime.utcnow(),
                            'source': 'yahoo'
                        })

                    prices[symbol] = formatted_data
                    logger.info(f"Found {len(formatted_data)} price points for {symbol} in {currency.upper()}")
                else:
                    logger.warning(f"No historical data available for {symbol}-{currency.upper()}")
            except Exception as e:
                logger.warning(f"Error getting historical prices for {symbol}-{currency.upper()}: {e}")

        return prices

    async def _get_usd_to_eur_rate(self) -> Optional[Decimal]:
        """
        Retrieve the USD to EUR conversion rate from Yahoo Finance.
        
        Attempts to fetch the FX rate and returns it; if no rate is available or an error occurs, returns a fallback Decimal("0.92").
        
        Returns:
            Decimal: USD→EUR conversion rate, or Decimal("0.92") as a fallback when the fetched rate is unavailable or an error occurs.
        """
        try:
            price_fetcher = PriceFetcher()
            import asyncio
            rate = await PriceFetcher.fetch_fx_rate("USD", "EUR")
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
        Compute the portfolio's internal rate of return (IRR) from transaction cash flows and current value.
        
        Builds cash flows from transactions (treats BUY as cash outflow, SELL as cash inflow, skips transfers), appends the provided current_value as the final cash inflow dated today, and computes the IRR on the resulting ordered cash flows.
        
        Parameters:
            transactions (List[CryptoTransaction]): Chronological list of portfolio transactions used to build cash flows.
            current_value (Decimal): Current total portfolio value included as the final cash inflow.
        
        Returns:
            Optional[float]: IRR expressed as a percentage (e.g., 12.5 for 12.5%), or `None` if there are no cash flows or the IRR cannot be computed.
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
        Produce a consolidated view of a crypto portfolio including its metadata, computed metrics, current holdings, and the most recent transactions.
        
        Returns:
            A dictionary with keys:
              - 'portfolio': the CryptoPortfolio instance for the requested ID.
              - 'metrics': computed CryptoPortfolioMetrics or None if metrics could not be calculated.
              - 'holdings': list of CryptoHolding objects representing current holdings.
              - 'recent_transactions': list of up to 10 most recent CryptoTransaction objects.
            Returns an empty dictionary if the portfolio is not found or an error occurs.
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