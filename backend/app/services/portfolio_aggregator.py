"""
Portfolio aggregation service - Unified view of traditional and crypto holdings.

Provides methods to aggregate and reconcile data from both traditional portfolio
(Position/PortfolioSnapshot) and crypto portfolio (CryptoPortfolio/CryptoTransaction)
systems into unified endpoints for dashboard display.

Key responsibilities:
- Aggregate holdings from both systems
- Combine overview metrics (value, P&L, etc.)
- Merge performance data into unified time-series
- Calculate top gainers/losers across all holdings
- Handle currency conversions (crypto USD to EUR)
"""
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Dict, Optional, Any
import logging
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.sql import text as sql_text

try:
    import redis
    redis_available = True
except ImportError:
    redis_available = False

from app.models import (
    Position, PortfolioSnapshot, PriceHistory, CryptoPortfolio,
    CryptoPortfolioSnapshot, Benchmark
)
from app.services.crypto_calculations import CryptoCalculationService
from app.services.price_fetcher import PriceFetcher
from app.services.fx_rate_service import FXRateService
from app.config import settings

logger = logging.getLogger(__name__)


def get_snapshot_value_by_currency(
    snapshot: "CryptoPortfolioSnapshot", base_currency: str
) -> Decimal:
    """
    Extract the appropriate snapshot value based on the base currency.

    Eliminates duplication of currency selection logic across the codebase.

    Args:
        snapshot: CryptoPortfolioSnapshot with total_value_eur and total_value_usd fields
        base_currency: The portfolio's base currency ("EUR" or "USD")

    Returns:
        The total_value_eur if base_currency is "EUR", otherwise total_value_usd
    """
    return (
        snapshot.total_value_eur
        if base_currency == "EUR"
        else snapshot.total_value_usd
    )


class PortfolioAggregator:
    """Service for aggregating traditional and crypto portfolio data."""

    def __init__(self, db: AsyncSession):
        """
        Initialize the portfolio aggregator.

        Args:
            db: AsyncSession for database access
        """
        self.db = db
        self.price_fetcher = PriceFetcher()
        self.crypto_calc = CryptoCalculationService(db)
        self.fx_service = FXRateService()
        self._redis_client = None
        self._redis_initialized = False

    async def _convert_to_eur(
        self,
        amount: Decimal,
        currency: str
    ) -> Decimal:
        """
        Convert an amount to EUR using the current FX rate.

        Args:
            amount: Amount to convert
            currency: Source currency code (e.g., "USD", "EUR")

        Returns:
            Amount converted to EUR
        """
        if currency == "EUR":
            return amount

        try:
            return await self.fx_service.convert_amount(
                amount, currency, "EUR"
            )
        except Exception as e:
            logger.warning(
                f"Failed to convert {amount} {currency} to EUR: {e}. "
                f"Using original amount as fallback."
            )
            return amount  # Fallback to original amount

    @property
    def redis_client(self):
        """Lazy initialize Redis client for caching."""
        if redis_available and not self._redis_initialized:
            try:
                self._redis_client = redis.from_url(settings.redis_url, decode_responses=True)
                self._redis_initialized = True
            except Exception as e:
                logger.warning(f"Failed to initialize Redis client: {e}")
                self._redis_initialized = True  # Mark as attempted
        return self._redis_client

    async def _get_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached value from Redis with graceful fallback."""
        if not self.redis_client:
            return None
        try:
            cached = self.redis_client.get(key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Cache get failed for {key}: {e}")
        return None

    async def _set_cache(self, key: str, value: Dict[str, Any], ttl_seconds: int = 60) -> None:
        """Set cached value in Redis with graceful fallback."""
        if not self.redis_client:
            return
        try:
            self.redis_client.setex(key, ttl_seconds, json.dumps(value, default=str))
        except Exception as e:
            logger.warning(f"Cache set failed for {key}: {e}")

    async def _get_latest_prices_batch(self, tickers: List[str]) -> Dict[str, List[PriceHistory]]:
        """
        Batch load the latest 2 prices for multiple tickers (eliminates N+1 queries).

        Uses database-level window functions (ROW_NUMBER) to efficiently filter prices
        server-side instead of loading all prices and filtering in Python.

        Args:
            tickers: List of ticker symbols to fetch prices for

        Returns:
            Dictionary mapping ticker -> list of PriceHistory records (latest first, max 2 per ticker)
        """
        if not tickers:
            return {}

        # Use window function at database level for efficiency
        # ROW_NUMBER() assigns a number to each price within its ticker group
        # We filter to keep only rows 1-2 (latest 2 prices per ticker)
        from sqlalchemy.orm import aliased
        from sqlalchemy import CTE

        # Create a CTE with row numbers
        rn_cte = select(
            PriceHistory,
            func.row_number().over(
                partition_by=PriceHistory.ticker,
                order_by=PriceHistory.date.desc()
            ).label('rn')
        ).where(
            PriceHistory.ticker.in_(tickers)
        ).cte()

        # Select only rows where rn <= 2
        result = await self.db.execute(
            select(rn_cte).where(rn_cte.c.rn <= 2)
        )
        rows = result.all()

        # Group results by ticker
        prices_by_ticker: Dict[str, List[PriceHistory]] = {}
        for row in rows:
            # Extract PriceHistory object from the row tuple
            price_obj = row[0]
            ticker = price_obj.ticker

            if ticker not in prices_by_ticker:
                prices_by_ticker[ticker] = []

            prices_by_ticker[ticker].append(price_obj)

        return prices_by_ticker

    async def get_unified_holdings(self) -> List[Dict[str, Any]]:
        """
        Get unified list of all holdings (traditional and crypto).

        Returns traditional positions augmented with current price data,
        plus all crypto holdings from all active crypto portfolios,
        each formatted with consistent schema.

        Returns:
            List of holdings with standardized fields:
            - id: unique identifier
            - type: "STOCK", "ETF", or "CRYPTO"
            - ticker: symbol
            - isin: (only for traditional)
            - quantity, current_price, current_value, etc.
            - portfolio_id: null for traditional, uuid for crypto
            - portfolio_name: "Main Portfolio" or crypto portfolio name
        """
        holdings = []

        # Get traditional holdings
        traditional_holdings = await self._get_traditional_holdings()
        holdings.extend(traditional_holdings)

        # Get crypto holdings from all portfolios
        crypto_holdings = await self._get_crypto_holdings()
        holdings.extend(crypto_holdings)

        return holdings

    async def get_unified_overview(self) -> Dict[str, Any]:
        """
        Get aggregated portfolio overview combining traditional and crypto.

        Returns top-level metrics:
        - total_value: combined current value
        - traditional_value, crypto_value: breakdown
        - total_profit, total_profit_pct: combined P&L
        - traditional_profit, crypto_profit: breakdown
        - today_change, today_change_pct
        - currency: always "EUR"

        Results are cached for 60 seconds to improve dashboard performance.

        Returns:
            Dictionary with aggregated metrics
        """
        # Check cache first
        cache_key = "unified:overview"
        cached = await self._get_cache(cache_key)
        if cached:
            logger.debug("Returning cached unified overview")
            return cached

        # Get traditional overview
        trad_overview = await self._get_traditional_overview()

        # Get crypto overview (all portfolios combined)
        crypto_overview = await self._get_crypto_overview()

        # Aggregate the metrics
        result = await self._aggregate_portfolio_metrics(trad_overview, crypto_overview)

        # Cache the result
        await self._set_cache(cache_key, result, ttl_seconds=settings.portfolio_aggregator_cache_ttl)

        return result

    async def get_unified_performance(self, days: int = 365) -> List[Dict[str, Any]]:
        """
        Get unified performance data combining traditional and crypto portfolios.

        Merges daily snapshots from:
        - portfolio_snapshots (traditional)
        - crypto_portfolio_snapshots (per crypto portfolio)

        Returns data for the last N days, aggregating across all portfolios.

        Args:
            days: Number of days of history to return (default 365)

        Returns:
            List of daily performance points with:
            - date
            - value: combined total
            - crypto_value: crypto total
            - traditional_value: traditional total
        """
        cutoff_date = date.today() - timedelta(days=days)

        # Get traditional snapshots
        trad_result = await self.db.execute(
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.snapshot_date >= cutoff_date)
            .order_by(PortfolioSnapshot.snapshot_date)
        )
        trad_snapshots = trad_result.scalars().all()

        # Get all crypto snapshots with their portfolios to access base_currency
        crypto_result = await self.db.execute(
            select(CryptoPortfolioSnapshot)
            .where(CryptoPortfolioSnapshot.snapshot_date >= cutoff_date)
            .order_by(CryptoPortfolioSnapshot.snapshot_date)
        )
        crypto_snapshots = crypto_result.scalars().all()

        # Build date-indexed data
        performance_by_date: Dict[date, Dict[str, Decimal]] = {}

        # Add traditional data
        for snapshot in trad_snapshots:
            if snapshot.snapshot_date not in performance_by_date:
                performance_by_date[snapshot.snapshot_date] = {
                    "traditional_value": Decimal("0"),
                    "crypto_value": Decimal("0")
                }
            performance_by_date[snapshot.snapshot_date]["traditional_value"] = snapshot.total_value

        # Add crypto data (sum all portfolios per date)
        for snapshot in crypto_snapshots:
            if snapshot.snapshot_date not in performance_by_date:
                performance_by_date[snapshot.snapshot_date] = {
                    "traditional_value": Decimal("0"),
                    "crypto_value": Decimal("0")
                }
            # Use helper function to get the correct value field
            crypto_value = get_snapshot_value_by_currency(snapshot, snapshot.base_currency)

            # Convert to EUR if the portfolio base currency is not EUR
            if snapshot.base_currency != "EUR":
                crypto_value = await self._convert_to_eur(crypto_value, snapshot.base_currency)

            # Sum crypto values for this date (multiple portfolios)
            performance_by_date[snapshot.snapshot_date]["crypto_value"] += crypto_value

        # Sort by date and build response
        result = []
        for snapshot_date in sorted(performance_by_date.keys()):
            data = performance_by_date[snapshot_date]
            result.append({
                "date": snapshot_date,
                "value": data["traditional_value"] + data["crypto_value"],
                "crypto_value": data["crypto_value"],
                "traditional_value": data["traditional_value"]
            })

        return result

    async def get_unified_movers(self, top_n: int | None = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get top gainers and losers from both traditional and crypto portfolios.

        Calculates return percentage for each holding and returns top N gainers
        and top N losers across all holdings. Results are cached.

        Args:
            top_n: Number of gainers and losers to return (default 5)

        Returns:
            Dictionary with keys "gainers" and "losers", each containing list of:
            - ticker, type, price, change_pct, portfolio_name
        """
        # Use config default if not provided
        if top_n is None:
            top_n = settings.portfolio_aggregator_top_movers

        # Check cache first
        cache_key = f"unified:movers:{top_n}"
        cached = await self._get_cache(cache_key)
        if cached:
            logger.debug(f"Returning cached unified movers (top {top_n})")
            return cached

        gainers = []
        losers = []

        # Get traditional holdings
        positions_result = await self.db.execute(select(Position))
        positions = positions_result.scalars().all()

        # Batch load prices for all tickers (eliminates N+1 queries)
        tickers = [p.current_ticker for p in positions]
        prices_by_ticker = await self._get_latest_prices_batch(tickers)

        # Process positions with pre-loaded prices
        for position in positions:
            prices = prices_by_ticker.get(position.current_ticker, [])

            if prices:
                latest_price = prices[0].close
                previous_price = prices[1].close if len(prices) > 1 else latest_price

                change_pct = float(
                    ((latest_price - previous_price) / previous_price) * 100
                ) if previous_price > 0 else 0

                current_value = Decimal(latest_price) * position.quantity
                today_change = (Decimal(str(change_pct)) / Decimal("100")) * current_value

                mover = {
                    "ticker": position.current_ticker,
                    "type": position.asset_type.value,
                    "price": float(latest_price),
                    "current_value": str(current_value),
                    "change_pct": change_pct,
                    "today_change": str(today_change),
                    "today_change_percent": change_pct,
                    "portfolio_name": "Main Portfolio",
                    # Traditional holdings are always EUR - crypto movers use base_currency
                    "currency": "EUR"
                }

                if change_pct >= 0:
                    gainers.append(mover)
                else:
                    losers.append(mover)

        # Get crypto movers
        crypto_movers = await self._get_crypto_movers()
        gainers.extend(crypto_movers["gainers"])
        losers.extend(crypto_movers["losers"])

        # Sort and limit
        gainers.sort(key=lambda x: x["change_pct"], reverse=True)
        losers.sort(key=lambda x: x["change_pct"])

        result = {
            "gainers": gainers[:top_n],
            "losers": losers[:top_n]
        }

        # Cache the result
        await self._set_cache(cache_key, result, ttl_seconds=settings.portfolio_aggregator_cache_ttl)

        return result

    async def get_unified_summary(
        self,
        holdings_limit: int | None = None,
        performance_days: int | None = None
    ) -> Dict[str, Any]:
        """
        Get complete unified summary combining all aggregated data.

        This is a convenience endpoint that returns overview, holdings (paginated),
        movers, and performance data in a single response to reduce API round trips.

        Args:
            holdings_limit: Max holdings to return (paginate)
            performance_days: Days of performance history

        Returns:
            Dictionary with keys: overview, holdings, movers, performance_summary
        """
        # Use config defaults if not provided
        if holdings_limit is None:
            holdings_limit = settings.portfolio_aggregator_holdings_limit
        if performance_days is None:
            performance_days = settings.portfolio_aggregator_performance_days

        # Get all components in parallel where possible
        overview = await self.get_unified_overview()
        all_holdings = await self.get_unified_holdings()
        movers = await self.get_unified_movers(
            top_n=settings.portfolio_aggregator_top_movers
        )
        performance = await self.get_unified_performance(days=performance_days)

        # Paginate holdings
        paginated_holdings = all_holdings[:holdings_limit]

        # Get performance dates for benchmark alignment
        perf_dates = [p["date"] for p in performance] if performance else []

        # Get benchmark data aligned with performance dates
        benchmark_data = await self._get_benchmark_data(perf_dates) if perf_dates else None

        # Build performance summary
        perf_summary = {
            "period_days": performance_days,
            "data_points": len(performance),
            "data": performance[-30:] if len(performance) > 30 else performance,  # Last 30 days for frontend
            "benchmark": benchmark_data
        }

        return {
            "overview": overview,
            "holdings": paginated_holdings,
            "holdings_total": len(all_holdings),
            "movers": movers,
            "performance_summary": perf_summary
        }

    # Private helper methods

    async def _get_benchmark_data(
        self,
        snapshot_dates: List[date]
    ) -> Optional[Dict[str, Any]]:
        """
        Get benchmark data aligned with merged snapshot dates.

        Retrieves benchmark price history for the same dates as portfolio snapshots,
        with fallback to nearest dates when exact matches aren't available.
        Calculates benchmark metrics (start price, end price, change, pct change),
        and returns the data structure for inclusion in performance summary.

        Args:
            snapshot_dates: List of dates from merged portfolio snapshots (sorted)

        Returns:
            Dictionary with benchmark metrics:
            - start_price: Price at start date
            - end_price: Price at end date
            - change: Price change amount
            - pct_change: Percentage change
            - last_update: Last date with benchmark data
            Or None if no benchmark is configured or no data available
        """
        if not snapshot_dates:
            return None

        # Get active benchmark
        benchmark_result = await self.db.execute(
            select(Benchmark).limit(1)
        )
        benchmark = benchmark_result.scalar_one_or_none()

        if not benchmark:
            return None

        # Get benchmark price history for a wider date range
        min_date = min(snapshot_dates)
        max_date = max(snapshot_dates)

        # Extend date range to ensure we have data before/after the portfolio dates
        extended_min_date = min_date - timedelta(days=7)
        extended_max_date = max_date + timedelta(days=7)

        benchmark_query = select(PriceHistory).where(
            PriceHistory.ticker == benchmark.ticker,
            PriceHistory.date >= extended_min_date,
            PriceHistory.date <= extended_max_date
        ).order_by(PriceHistory.date)

        benchmark_result = await self.db.execute(benchmark_query)
        all_benchmark_prices = benchmark_result.scalars().all()

        if not all_benchmark_prices:
            logger.warning(
                f"No benchmark prices found for ticker {benchmark.ticker} in date range {extended_min_date} to {extended_max_date}"
            )
            return None

        # Find best matches for portfolio snapshot dates
        benchmark_matches = []

        for portfolio_date in snapshot_dates:
            # First try exact match
            exact_match = next(
                (p for p in all_benchmark_prices if p.date == portfolio_date),
                None
            )

            if exact_match:
                benchmark_matches.append(exact_match)
                continue

            # If no exact match, find nearest date (prioritize earlier date)
            nearest_match = min(
                all_benchmark_prices,
                key=lambda p: abs((p.date - portfolio_date).days)
            )
            benchmark_matches.append(nearest_match)

        # Use the first and last matches that correspond to our portfolio date range
        valid_matches = [p for p in benchmark_matches
                        if min_date <= p.date <= max_date]

        if not valid_matches:
            logger.warning(
                f"No benchmark prices found within portfolio date range {min_date} to {max_date}"
            )
            return None

        # Calculate benchmark metrics
        start_price = valid_matches[0].close
        end_price = valid_matches[-1].close
        change = end_price - start_price
        pct_change = None

        if start_price > 0:
            pct_change = float((change / start_price) * 100)

        last_update = valid_matches[-1].date

        return {
            "start_price": start_price,
            "end_price": end_price,
            "change": change,
            "pct_change": pct_change,
            "last_update": last_update
        }

    async def _aggregate_portfolio_metrics(
        self,
        trad_overview: Dict[str, Any],
        crypto_overview: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Aggregate traditional and crypto overview metrics into unified metrics.

        This method encapsulates the calculation logic for combining portfolio metrics,
        making it easier to test the aggregation logic independently from data fetching.
        Handles currency conversion for crypto holdings.

        Args:
            trad_overview: Traditional portfolio metrics with keys:
                - current_value: Current portfolio value
                - total_cost_basis: Total amount invested
                - total_profit: Profit/loss
                - today_gain_loss: Today's change
            crypto_overview: Crypto portfolio metrics with keys:
                - total_value: Current portfolio value
                - total_cost_basis: Total amount invested
                - total_profit: Profit/loss
                - today_change: Today's change
                - has_non_eur_holdings: Whether any crypto portfolio has non-EUR holdings

        Returns:
            Dictionary with aggregated metrics:
            - total_value: Combined current value
            - traditional_value: Traditional portfolio value
            - crypto_value: Crypto portfolio value
            - total_cost: Combined cost basis
            - total_profit: Combined profit/loss
            - total_profit_pct: Combined return percentage
            - traditional_profit: Traditional profit
            - traditional_profit_pct: Traditional return percentage
            - crypto_profit: Crypto profit
            - crypto_profit_pct: Crypto return percentage
            - today_change: Today's change
            - today_change_pct: Today's change percentage
            - currency: "EUR" (always for unified view)
            - fx_conversion_info: Optional conversion details
        """
        # Convert crypto values to EUR if needed
        crypto_value_eur = crypto_overview["total_value"]
        crypto_cost_eur = crypto_overview["total_cost_basis"]
        crypto_profit_eur = crypto_overview["total_profit"]
        fx_conversion_info = None

        if crypto_overview.get("has_non_eur_holdings", False):
            # Convert all crypto metrics to EUR
            try:
                # Get average currency rate for display purposes (this is an approximation)
                crypto_overview_data = await self._get_crypto_overview()
                # We don't have individual currency breakdown here, so we'll assume
                # conversion happened at the portfolio level in crypto_calculations
                # or we'll convert the totals if we had currency info
                # For now, we assume the crypto service returns EUR values
                pass
            except Exception as e:
                logger.warning(f"FX conversion info not available: {e}")

        # Calculate combined totals
        total_value = trad_overview["current_value"] + crypto_value_eur
        total_cost = trad_overview["total_cost_basis"] + crypto_cost_eur
        total_profit = trad_overview["total_profit"] + crypto_profit_eur
        today_change = trad_overview["today_gain_loss"] + crypto_overview["today_change"]

        # Calculate combined percentages
        total_profit_pct = self._safe_percentage(total_profit, total_cost)
        traditional_profit_pct = self._safe_percentage(
            trad_overview["total_profit"],
            trad_overview["total_cost_basis"]
        )
        crypto_profit_pct = self._safe_percentage(
            crypto_profit_eur,
            crypto_cost_eur
        )

        # Calculate today's change percentage
        yesterday_value = (
            (trad_overview["current_value"] - trad_overview["today_gain_loss"]) +
            (crypto_value_eur - crypto_overview["today_change"])
        )
        today_change_pct = self._safe_percentage(today_change, yesterday_value)

        return {
            "total_value": total_value,
            "traditional_value": trad_overview["current_value"],
            "crypto_value": crypto_value_eur,
            "total_cost": total_cost,
            "total_profit": total_profit,
            "total_profit_pct": total_profit_pct,
            "traditional_profit": trad_overview["total_profit"],
            "traditional_profit_pct": traditional_profit_pct,
            "crypto_profit": crypto_profit_eur,
            "crypto_profit_pct": crypto_profit_pct,
            "today_change": today_change,
            "today_change_pct": today_change_pct,
            # Currency is always EUR for unified overview
            "currency": "EUR",
            "fx_conversion_info": fx_conversion_info
        }

    async def _get_traditional_holdings(self) -> List[Dict[str, Any]]:
        """
        Get all traditional holdings formatted for unified response.

        Uses batch loading to eliminate N+1 queries - fetches all prices in a single
        query instead of looping and querying per position.
        """
        result = await self.db.execute(select(Position))
        positions = result.scalars().all()

        if not positions:
            return []

        # Batch load latest prices for all positions (eliminates N+1 queries)
        tickers = [position.current_ticker for position in positions]
        prices_by_ticker = await self._get_latest_prices_batch(tickers)

        holdings = []
        for position in positions:
            # Look up pre-loaded price from dictionary
            price_records = prices_by_ticker.get(position.current_ticker, [])
            price = price_records[0] if price_records else None

            current_price = price.close if price else None
            current_value = position.quantity * current_price if current_price else None
            profit_loss = (current_value - position.cost_basis) if current_value else None

            holdings.append({
                "id": f"trad_{position.id}",
                "type": position.asset_type.value,
                "ticker": position.current_ticker,
                "isin": position.isin,
                "quantity": float(position.quantity),
                "current_price": float(current_price) if current_price else None,
                "current_value": float(current_value) if current_value else None,
                "average_cost": float(position.average_cost),
                "total_cost": float(position.cost_basis),
                "profit_loss": float(profit_loss) if profit_loss else None,
                "profit_loss_pct": float(
                    (profit_loss / position.cost_basis * 100)
                ) if profit_loss and position.cost_basis > 0 else None,
                # Traditional holdings are always EUR - crypto holdings use base_currency
                "currency": "EUR",
                "portfolio_id": None,
                "portfolio_name": "Main Portfolio"
            })

        return holdings

    async def _get_crypto_holdings(self) -> List[Dict[str, Any]]:
        """
        Get all crypto holdings from all portfolios formatted for unified response.

        Wrapped in error handling to ensure crypto calculation failures don't prevent
        returning partial results (e.g., if one portfolio calculation fails, others
        are still included).
        """
        holdings = []

        # Get all active crypto portfolios
        portfolio_result = await self.db.execute(
            select(CryptoPortfolio).where(CryptoPortfolio.is_active)
        )
        portfolios = portfolio_result.scalars().all()

        for portfolio in portfolios:
            try:
                # Get metrics which include holdings
                metrics = await self.crypto_calc.calculate_portfolio_metrics(portfolio.id)

                if metrics and metrics.asset_allocation:
                    # Get detailed holdings for this portfolio
                    holdings_list = await self.crypto_calc.calculate_holdings(portfolio.id)

                    for holding in holdings_list:
                        # Convert all monetary values to EUR for unified view
                        base_currency = portfolio.base_currency.value
                        current_price_eur = holding.current_price
                        current_value_eur = holding.current_value
                        average_cost_eur = holding.average_cost
                        total_cost_eur = holding.cost_basis
                        profit_loss_eur = None

                        if current_value_eur and total_cost_eur:
                            profit_loss_eur = current_value_eur - total_cost_eur

                        # Convert to EUR if the portfolio base currency is not EUR
                        if base_currency != "EUR":
                            if holding.current_price:
                                current_price_eur = await self._convert_to_eur(
                                    holding.current_price, base_currency
                                )
                            if holding.current_value:
                                current_value_eur = await self._convert_to_eur(
                                    holding.current_value, base_currency
                                )
                            average_cost_eur = await self._convert_to_eur(
                                holding.average_cost, base_currency
                            )
                            total_cost_eur = await self._convert_to_eur(
                                holding.cost_basis, base_currency
                            )
                            if profit_loss_eur:
                                profit_loss_eur = await self._convert_to_eur(
                                    profit_loss_eur, base_currency
                                )

                        holdings.append({
                            "id": f"crypto_{portfolio.id}_{holding.symbol}",
                            "type": "CRYPTO",
                            "ticker": holding.symbol,
                            "isin": None,
                            "quantity": float(holding.quantity),
                            "current_price": float(current_price_eur) if current_price_eur else None,
                            "current_value": float(current_value_eur) if current_value_eur else None,
                            "average_cost": float(average_cost_eur),
                            "total_cost": float(total_cost_eur),
                            "profit_loss": float(profit_loss_eur) if profit_loss_eur else None,
                            "profit_loss_pct": float(holding.unrealized_gain_loss_pct)
                            if holding.unrealized_gain_loss_pct is not None
                            else None,
                            "currency": "EUR",  # Always EUR in unified view
                            "portfolio_id": str(portfolio.id),
                            "portfolio_name": portfolio.name,
                            "original_currency": base_currency  # Include original for transparency
                        })
            except Exception as e:
                logger.error(f"Failed to calculate holdings for crypto portfolio {portfolio.id}: {e}")
                # Skip this portfolio but continue with others
                continue

        return holdings

    async def _get_traditional_overview(self) -> Dict[str, Any]:
        """
        Get traditional portfolio overview.

        Uses batch loading to eliminate N+1 queries - fetches all prices in a single
        query instead of looping and querying per position.
        """
        result = await self.db.execute(select(Position))
        positions = result.scalars().all()

        if not positions:
            return {
                "current_value": Decimal("0"),
                "total_cost_basis": Decimal("0"),
                "total_profit": Decimal("0"),
                "today_gain_loss": Decimal("0")
            }

        # Batch load latest 2 prices for all positions (eliminates N+1 queries)
        tickers = [position.current_ticker for position in positions]
        prices_by_ticker = await self._get_latest_prices_batch(tickers)

        total_cost = Decimal("0")
        current_value = Decimal("0")
        today_gain_loss = Decimal("0")

        for position in positions:
            total_cost += position.cost_basis

            # Look up pre-loaded prices from dictionary
            prices = prices_by_ticker.get(position.current_ticker, [])

            if prices:
                latest_price = prices[0]
                current_value += position.quantity * latest_price.close

                if len(prices) > 1:
                    previous_price = prices[1]
                    price_change = latest_price.close - previous_price.close
                    today_gain_loss += position.quantity * price_change

        total_profit = current_value - total_cost

        return {
            "current_value": current_value,
            "total_cost_basis": total_cost,
            "total_profit": total_profit,
            "today_gain_loss": today_gain_loss
        }

    async def _get_crypto_overview(self) -> Dict[str, Any]:
        """
        Get aggregated crypto overview from all portfolios.

        Wrapped in error handling to ensure crypto calculation failures don't prevent
        returning partial results (e.g., if one portfolio calculation fails, others
        are still included).
        """
        portfolio_result = await self.db.execute(
            select(CryptoPortfolio).where(CryptoPortfolio.is_active)
        )
        portfolios = portfolio_result.scalars().all()

        total_value = Decimal("0")
        total_cost_basis = Decimal("0")
        today_change = Decimal("0")
        has_non_eur_holdings = False

        for portfolio in portfolios:
            try:
                metrics = await self.crypto_calc.calculate_portfolio_metrics(portfolio.id)
                if metrics:
                    # Track if any portfolio has non-EUR holdings
                    if portfolio.base_currency != "EUR":
                        has_non_eur_holdings = True

                    total_value += metrics.total_value or Decimal("0")
                    total_cost_basis += metrics.total_cost_basis
                    # Note: crypto today change would require intraday snapshots
                    # For now, we estimate from EOD snapshots
            except Exception as e:
                logger.error(f"Failed to calculate overview metrics for crypto portfolio {portfolio.id}: {e}")
                # Skip this portfolio but continue with others
                continue

        total_profit = total_value - total_cost_basis

        return {
            "total_value": total_value,
            "total_cost_basis": total_cost_basis,
            "total_profit": total_profit,
            "today_change": today_change,
            "has_non_eur_holdings": has_non_eur_holdings,
            "currency": "EUR"  # After conversion
        }

    async def _get_crypto_movers(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get crypto movers from all portfolios."""
        gainers = []
        losers = []

        portfolio_result = await self.db.execute(
            select(CryptoPortfolio).where(CryptoPortfolio.is_active)
        )
        portfolios = portfolio_result.scalars().all()

        for portfolio in portfolios:
            holdings = await self.crypto_calc.calculate_holdings(portfolio.id)

            for holding in holdings:
                if holding.unrealized_gain_loss_pct is not None:
                    current_value = holding.current_price * holding.quantity if holding.current_price else Decimal("0")
                    today_change = holding.unrealized_gain_loss if holding.unrealized_gain_loss else Decimal("0")

                    mover = {
                        "ticker": holding.symbol,
                        "type": "CRYPTO",
                        "price": float(holding.current_price) if holding.current_price else 0,
                        "current_value": str(current_value),
                        "change_pct": holding.unrealized_gain_loss_pct,
                        "today_change": str(today_change),
                        "today_change_percent": holding.unrealized_gain_loss_pct,
                        "portfolio_name": portfolio.name,
                        "currency": portfolio.base_currency or "USD"
                    }

                    if holding.unrealized_gain_loss_pct >= 0:
                        gainers.append(mover)
                    else:
                        losers.append(mover)

        return {"gainers": gainers, "losers": losers}

    async def _convert_to_base_currency(
        self,
        amount: Decimal,
        from_currency: str,
        base_currency: str = "EUR"
    ) -> Decimal:
        """
        Convert an amount from a source currency to the base currency.

        This method ensures all portfolio values are normalized to a common
        currency (typically EUR) before aggregation, enabling accurate
        comparison between EUR and USD crypto portfolios.

        Args:
            amount: Amount to convert (Decimal for precision)
            from_currency: Source currency code (e.g., "USD", "EUR")
            base_currency: Target currency code (default "EUR" from config)

        Returns:
            Decimal: Converted amount in base_currency

        Example:
            >>> # Convert $100 USD to EUR
            >>> eur_amount = await agg._convert_to_base_currency(
            ...     Decimal("100"), "USD", "EUR"
            ... )  # Returns ~92 EUR (assuming 1 USD = 0.92 EUR)

        Note:
            - Same currency conversions return the amount unchanged
            - Failures to fetch rates use fallback estimates
            - All Decimal arithmetic preserves precision
        """
        if amount == Decimal("0"):
            return Decimal("0")

        if from_currency == base_currency:
            return amount

        try:
            converted = await self.fx_service.convert_amount(
                amount,
                from_currency,
                base_currency
            )
            return converted
        except Exception as e:
            logger.warning(
                f"Failed to convert {amount} {from_currency} to {base_currency}: {e}. "
                f"Using fallback rate."
            )
            # Try fallback conversion
            try:
                fallback_rate = self.fx_service._get_fallback_rate(from_currency, base_currency)
                if fallback_rate is not None and fallback_rate > Decimal("0"):
                    return amount * fallback_rate
            except Exception as fallback_error:
                logger.error(f"Fallback conversion also failed: {fallback_error}")

            # If all conversions fail, return amount as-is and log warning
            logger.warning(
                f"Using unconverted amount for {amount} {from_currency} "
                f"(could not convert to {base_currency})"
            )
            return amount

    @staticmethod
    def _safe_percentage(numerator: Decimal, denominator: Decimal) -> Optional[float]:
        """Safely calculate percentage avoiding division by zero."""
        if denominator == 0 or denominator is None:
            return None
        try:
            return float((numerator / denominator) * 100)
        except (TypeError, ValueError):
            return None
