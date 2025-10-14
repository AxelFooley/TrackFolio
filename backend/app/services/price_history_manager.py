"""
Price History Management Service.

Optimizes price data fetching by maintaining comprehensive historical data
in the database and minimizing external API calls.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Set
import logging
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from app.database import SyncSessionLocal
from app.models.position import Position
from app.models.crypto import CryptoTransaction, CryptoTransactionType
from app.models import PriceHistory
from app.services.price_fetcher import PriceFetcher
from app.services.currency_converter import get_exchange_rate

logger = logging.getLogger(__name__)


class PriceHistoryManager:
    """
    Manages comprehensive price history for all assets in the portfolio.

    This service:
    1. Fetches complete historical data for all symbols in bulk
    2. Maintains a comprehensive price history database
    3. Provides efficient querying for frontend charts
    4. Updates current prices only when needed
    """

    def __init__(self):
        self.price_fetcher = PriceFetcher()

    def get_all_active_symbols(self) -> Set[str]:
        """
        Get all unique symbols from both traditional and crypto portfolios.

        Returns:
            Set of all active ticker symbols
        """
        symbols = set()
        db = SyncSessionLocal()

        try:
            # Get traditional asset symbols
            result = db.execute(
                select(Position.current_ticker)
                .where(Position.quantity > 0)
                .distinct()
            )
            traditional_symbols = [row[0] for row in result.all() if row[0]]
            symbols.update(traditional_symbols)

            # Get crypto symbols
            result = db.execute(
                select(CryptoTransaction.symbol)
                .where(
                    CryptoTransaction.transaction_type.in_([
                        CryptoTransactionType.BUY,
                        CryptoTransactionType.SELL,
                        CryptoTransactionType.TRANSFER_IN
                    ])
                )
                .distinct()
            )
            crypto_symbols = [row[0] for row in result.all() if row[0]]
            symbols.update(crypto_symbols)

            logger.info(f"Found {len(symbols)} active symbols: {sorted(symbols)}")
            return symbols

        except Exception as e:
            logger.error(f"Error getting active symbols: {e}")
            return set()
        finally:
            db.close()

    def fetch_and_store_complete_history(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        force_update: bool = False
    ) -> Dict[str, int]:
        """
        Fetch and store complete historical data for a symbol.

        Args:
            symbol: Ticker symbol to fetch
            start_date: Optional start date (defaults to 5 years ago)
            force_update: Whether to overwrite existing data

        Returns:
            Dict with counts: {'added': X, 'updated': Y, 'skipped': Z}
        """
        if start_date is None:
            # Fetch up to 5 years of history by default
            start_date = date.today() - timedelta(days=5 * 365)

        end_date = date.today()

        logger.info(f"Fetching complete price history for {symbol} from {start_date} to {end_date}")

        db = SyncSessionLocal()
        try:
            # Check what data we already have
            existing_result = db.execute(
                select(PriceHistory)
                .where(
                    and_(
                        PriceHistory.ticker == symbol,
                        PriceHistory.date >= start_date,
                        PriceHistory.date <= end_date
                    )
                )
                .order_by(PriceHistory.date)
            )
            existing_records = existing_result.scalars().all()
            existing_dates = {record.date for record in existing_records}

            # Fetch historical data from Yahoo Finance
            yahoo_symbol = symbol
            # For crypto, Yahoo Finance uses SYMBOL-USD format
            if symbol in ['BTC', 'ETH', 'LTC', 'BCH', 'XRP', 'ADA', 'DOT', 'LINK', 'BNB', 'USDT', 'USDC']:
                yahoo_symbol = f"{symbol}-USD"

            historical_data = self.price_fetcher.fetch_historical_prices_sync(
                ticker=yahoo_symbol,
                start_date=start_date,
                end_date=end_date
            )

            if not historical_data:
                logger.warning(f"No historical data returned for {symbol}")
                return {'added': 0, 'updated': 0, 'skipped': 0}

            added = 0
            updated = 0
            skipped = 0

            for price_data in historical_data:
                price_date = price_data['date']

                # Skip if we already have this data and not forcing update
                if not force_update and price_date in existing_dates:
                    skipped += 1
                    continue

                # Convert to EUR if needed
                price_usd = price_data['close']
                try:
                    usd_to_eur_rate = get_exchange_rate("USD", "EUR")
                    price_eur = price_usd * usd_to_eur_rate
                except Exception as e:
                    logger.warning(f"Failed to get USD->EUR rate for {symbol}: {e}. Using fallback.")
                    price_eur = price_usd * Decimal("0.92")  # Fallback rate

                # Check if record exists
                existing = db.execute(
                    select(PriceHistory)
                    .where(
                        and_(
                            PriceHistory.ticker == symbol,
                            PriceHistory.date == price_date
                        )
                    )
                ).scalar_one_or_none()

                if existing:
                    # Update existing record
                    existing.open = price_eur
                    existing.high = price_eur
                    existing.low = price_eur
                    existing.close = price_eur
                    existing.volume = price_data.get('volume', 0)
                    existing.source = "yahoo"
                    updated += 1
                else:
                    # Create new record
                    price_record = PriceHistory(
                        ticker=symbol,
                        date=price_date,
                        open=price_eur,
                        high=price_eur,
                        low=price_eur,
                        close=price_eur,
                        volume=price_data.get('volume', 0),
                        source="yahoo"
                    )
                    db.add(price_record)
                    added += 1

            # Commit all changes
            db.commit()

            logger.info(f"Price history update for {symbol}: {added} added, {updated} updated, {skipped} skipped")
            return {'added': added, 'updated': updated, 'skipped': skipped}

        except Exception as e:
            db.rollback()
            logger.error(f"Error fetching price history for {symbol}: {e}")
            raise
        finally:
            db.close()

    def update_all_symbols_history(
        self,
        symbols: Optional[List[str]] = None,
        force_update: bool = False
    ) -> Dict[str, Dict[str, int]]:
        """
        Update price history for all symbols or a specific list.

        Args:
            symbols: Optional list of symbols to update (defaults to all active symbols)
            force_update: Whether to overwrite existing data

        Returns:
            Dict mapping symbol to update counts
        """
        if symbols is None:
            symbols = list(self.get_all_active_symbols())

        if not symbols:
            logger.info("No symbols to update")
            return {}

        logger.info(f"Updating price history for {len(symbols)} symbols")

        results = {}
        for symbol in symbols:
            try:
                results[symbol] = self.fetch_and_store_complete_history(symbol, force_update=force_update)
                # Rate limiting between symbols
                import time
                time.sleep(0.2)  # 200ms delay between symbols
            except Exception as e:
                logger.error(f"Failed to update {symbol}: {e}")
                results[symbol] = {'added': 0, 'updated': 0, 'skipped': 0, 'error': str(e)}

        return results

    def get_price_history(
        self,
        symbol: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Get price history for a symbol from our database.

        Args:
            symbol: Ticker symbol
            start_date: Optional start date
            end_date: Optional end date
            limit: Optional limit on number of records

        Returns:
            List of price dictionaries
        """
        db = SyncSessionLocal()
        try:
            query = select(PriceHistory).where(PriceHistory.ticker == symbol)

            if start_date:
                query = query.where(PriceHistory.date >= start_date)
            if end_date:
                query = query.where(PriceHistory.date <= end_date)

            query = query.order_by(PriceHistory.date.desc())

            if limit:
                query = query.limit(limit)

            result = db.execute(query)
            records = result.scalars().all()

            return [
                {
                    'date': record.date,
                    'open': float(record.open),
                    'high': float(record.high),
                    'low': float(record.low),
                    'close': float(record.close),
                    'volume': record.volume
                }
                for record in records
            ]

        except Exception as e:
            logger.error(f"Error getting price history for {symbol}: {e}")
            return []
        finally:
            db.close()

    def get_date_range_for_symbol(self, symbol: str) -> Optional[Dict[str, date]]:
        """
        Get the available date range for a symbol in our database.

        Args:
            symbol: Ticker symbol

        Returns:
            Dict with 'earliest' and 'latest' dates, or None if no data
        """
        db = SyncSessionLocal()
        try:
            result = db.execute(
                select(
                    func.min(PriceHistory.date).label('earliest'),
                    func.max(PriceHistory.date).label('latest')
                )
                .where(PriceHistory.ticker == symbol)
            )
            row = result.first()

            if row and row.earliest and row.latest:
                return {
                    'earliest': row.earliest,
                    'latest': row.latest
                }
            return None

        except Exception as e:
            logger.error(f"Error getting date range for {symbol}: {e}")
            return None
        finally:
            db.close()

    def ensure_complete_coverage(self, symbols: Optional[List[str]] = None) -> Dict[str, bool]:
        """
        Ensure we have complete price history coverage for all symbols.

        Checks for gaps in historical data and fills them if needed.

        Args:
            symbols: Optional list of symbols to check (defaults to all active symbols)

        Returns:
            Dict mapping symbol to whether coverage is complete
        """
        if symbols is None:
            symbols = list(self.get_all_active_symbols())

        results = {}
        five_years_ago = date.today() - timedelta(days=5 * 365)

        for symbol in symbols:
            try:
                date_range = self.get_date_range_for_symbol(symbol)

                if not date_range:
                    # No data at all, fetch everything
                    logger.info(f"No historical data for {symbol}, fetching complete history")
                    self.fetch_and_store_complete_history(symbol)
                    results[symbol] = True
                else:
                    # Check if we have full coverage
                    if date_range['earliest'] <= five_years_ago:
                        results[symbol] = True
                        logger.info(f"Complete coverage for {symbol}")
                    else:
                        # Fill the gap
                        logger.info(f"Filling historical gap for {symbol}")
                        self.fetch_and_store_complete_history(symbol)
                        results[symbol] = True

            except Exception as e:
                logger.error(f"Error ensuring coverage for {symbol}: {e}")
                results[symbol] = False

        return results


# Create a singleton instance
price_history_manager = PriceHistoryManager()