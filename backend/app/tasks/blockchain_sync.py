"""
Blockchain wallet synchronization tasks.

This module handles automatic synchronization of Bitcoin wallet transactions
from blockchain APIs to the crypto portfolio system.
"""
from celery import shared_task
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import select, func, and_, or_
from sqlalchemy.exc import IntegrityError
from typing import Optional
import logging
import time

from app.celery_app import celery_app
from app.database import SyncSessionLocal
from app.models.crypto import CryptoPortfolio, CryptoTransaction, CryptoTransactionType, CryptoCurrency
from app.services.blockchain_fetcher import blockchain_fetcher
from app.services.blockchain_deduplication import blockchain_deduplication
from app.services.price_fetcher import PriceFetcher
from app.config import settings

logger = logging.getLogger(__name__)


def get_usd_to_eur_rate() -> Optional[Decimal]:
    """
    Retrieve the USD-to-EUR exchange rate using Yahoo Finance FX data.
    
    Fetches the EUR/USD rate and returns its reciprocal so the result represents how many EUR equal 1 USD.
    
    Returns:
        Decimal: Amount of EUR per 1 USD (e.g., Decimal('0.92')), or `None` if the rate could not be obtained.
    """
    try:
        price_fetcher = PriceFetcher()

        # Get EUR/USD rate from Yahoo Finance (EURUSD=X)
        # This gives us 1 EUR = X USD, so we need to invert it
        import asyncio
        eur_usd_rate = asyncio.run(price_fetcher.fetch_fx_rate("EUR", "USD"))

        if eur_usd_rate and eur_usd_rate > 0:
            usd_to_eur_rate = Decimal("1") / eur_usd_rate
            logger.debug(f"Fetched USD to EUR rate: {usd_to_eur_rate}")
            return usd_to_eur_rate
        else:
            logger.warning("Could not fetch EUR/USD rate from Yahoo Finance")
            return None

    except Exception as e:
        logger.error(f"Error getting USD to EUR conversion rate: {e}")
        return None


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 300},
    retry_backoff=True,
    retry_backoff_max=1800,
    retry_jitter=True
)
def sync_all_wallets(self):
    """
    Orchestrates a full synchronization for all configured Bitcoin wallets and returns a summary of the global results.
    
    Runs synchronization across every portfolio that has a Bitcoin wallet address and aggregates per-wallet outcomes into a single result.
    
    Returns:
        dict: Summary containing overall status, counts (added/skipped/failed/fetched), and per-wallet result details.
    """
    return _sync_bitcoin_wallets_impl()


# Alias for backwards compatibility
sync_bitcoin_wallets = sync_all_wallets


def _sync_bitcoin_wallets_impl():
    """
    Synchronizes all active Bitcoin wallets' transactions into the database.
    
    Finds active portfolios with wallet addresses, runs per-wallet synchronization (adds new transactions, skips duplicates, records failures), and returns an aggregated summary of the run. If blockchain synchronization is disabled in settings, returns a disabled status without performing work.
    
    Returns:
        dict: Summary of the synchronization run. Common keys:
            - status (str): "success" when run completed, or "disabled" if sync is turned off.
            - message (str): Human-readable summary.
            - wallets_synced (int): Number of wallets processed.
            - total_transactions_added (int): Count of new transactions inserted.
            - total_transactions_skipped (int): Count of transactions skipped (duplicates or integrity conflicts).
            - total_wallets_failed (int): Count of wallets that failed during processing.
            - sync_timestamp (str): ISO-8601 UTC timestamp of the run.
            - wallet_results (list): Per-wallet result objects with portfolio_id, portfolio_name, wallet_address and their individual status/counts.
        When synchronization is disabled, the dict contains "status": "disabled", "message", and zeroed counts.
    """
    # Check if blockchain sync is enabled
    if not settings.blockchain_sync_enabled:
        logger.info("Blockchain synchronization is disabled in settings")
        return {
            "status": "disabled",
            "message": "Blockchain synchronization is disabled",
            "wallets_synced": 0,
            "total_transactions": 0
        }

    logger.info("Starting Bitcoin wallet synchronization task")

    db = SyncSessionLocal()

    try:
        # Get all portfolios with Bitcoin wallet addresses
        result = db.execute(
            select(CryptoPortfolio)
            .where(
                and_(
                    CryptoPortfolio.is_active == True,
                    CryptoPortfolio.wallet_address.isnot(None)
                )
            )
        )
        portfolios = result.scalars().all()

        if not portfolios:
            logger.info("No active Bitcoin wallets found. Skipping sync.")
            return {
                "status": "success",
                "message": "No active Bitcoin wallets found",
                "wallets_synced": 0,
                "total_transactions": 0
            }

        logger.info(f"Found {len(portfolios)} Bitcoin wallets to sync")

        # Track overall results
        total_transactions = 0
        total_skipped = 0
        total_failed = 0
        wallet_results = []

        # Sync each wallet (using config defaults for automatic syncs)
        for portfolio in portfolios:
            try:
                wallet_result = sync_single_wallet(
                    portfolio.wallet_address,
                    portfolio.id,
                    db,
                    max_transactions=settings.blockchain_max_transactions_per_sync,
                    days_back=settings.blockchain_sync_days_back
                )

                wallet_results.append({
                    "portfolio_id": portfolio.id,
                    "portfolio_name": portfolio.name,
                    "wallet_address": portfolio.wallet_address,
                    **wallet_result
                })

                total_transactions += wallet_result.get("transactions_added", 0)
                total_skipped += wallet_result.get("transactions_skipped", 0)
                total_failed += wallet_result.get("transactions_failed", 0)

                logger.info(
                    f"Synced wallet {portfolio.wallet_address}: "
                    f"+{wallet_result.get('transactions_added', 0)} "
                    f"skipped {wallet_result.get('transactions_skipped', 0)} "
                    f"failed {wallet_result.get('transactions_failed', 0)}"
                )

                # Rate limiting between wallets
                time.sleep(2)

            except Exception as e:
                logger.error(f"Failed to sync wallet {portfolio.wallet_address}: {e}")
                wallet_results.append({
                    "portfolio_id": portfolio.id,
                    "portfolio_name": portfolio.name,
                    "wallet_address": portfolio.wallet_address,
                    "status": "error",
                    "error": str(e),
                    "transactions_added": 0,
                    "transactions_skipped": 0,
                    "transactions_failed": 0
                })
                total_failed += 1

        # Build summary
        summary = {
            "status": "success",
            "message": f"Synced {len(portfolios)} Bitcoin wallets",
            "wallets_synced": len(portfolios),
            "total_transactions_added": total_transactions,
            "total_transactions_skipped": total_skipped,
            "total_wallets_failed": total_failed,
            "sync_timestamp": datetime.utcnow().isoformat(),
            "wallet_results": wallet_results
        }

        logger.info(
            f"Bitcoin wallet sync complete: "
            f"{len(portfolios)} wallets, "
            f"{total_transactions} new transactions, "
            f"{total_skipped} skipped, "
            f"{total_failed} failed"
        )

        return summary

    except Exception as e:
        logger.error(f"Fatal error in Bitcoin wallet sync task: {e}")
        raise

    finally:
        db.close()


def sync_single_wallet(
    wallet_address: str,
    portfolio_id: int,
    db_session,
    max_transactions: Optional[int] = None,
    days_back: Optional[int] = None
) -> dict:
    """
    Sync transactions for a single Bitcoin wallet.

    Args:
        wallet_address: Bitcoin wallet address to sync
        portfolio_id: Portfolio ID to associate transactions with
        db_session: Database session
        max_transactions: Maximum number of transactions to fetch. None = unlimited
        days_back: Number of days to look back. None = unlimited (all history)

    Returns:
        dict: Sync result for this wallet
    """
    # Note: We don't use config defaults here - we pass through None to allow unlimited fetching
    # For automatic scheduled syncs, the sync_all_wallets function will use config defaults
    # For manual syncs, pass None to fetch complete history

    logger.info(f"Syncing Bitcoin wallet {wallet_address} (portfolio {portfolio_id})")

    try:
        # Get existing transaction hashes for this portfolio using deduplication service
        existing_hashes = blockchain_deduplication.get_portfolio_transaction_hashes(portfolio_id)
        logger.info(f"Found {len(existing_hashes)} existing transactions for wallet {wallet_address}")

        # Fetch transactions from blockchain API
        blockchain_result = blockchain_fetcher.fetch_transactions(
            wallet_address=wallet_address,
            portfolio_id=portfolio_id,
            max_transactions=max_transactions,
            days_back=days_back
        )

        if blockchain_result['status'] != 'success':
            return {
                "status": "error",
                "error": blockchain_result.get('message', 'Unknown error'),
                "transactions_added": 0,
                "transactions_skipped": 0,
                "transactions_failed": 0
            }

        blockchain_transactions = blockchain_result.get('transactions', [])
        logger.info(f"Fetched {len(blockchain_transactions)} transactions from blockchain for wallet {wallet_address}")

        # Process and filter transactions
        new_transactions = []
        skipped_transactions = []
        failed_transactions = []

        for tx_data in blockchain_transactions:
            try:
                tx_hash = tx_data.get('transaction_hash')

                # Check for duplicates
                if tx_hash and tx_hash in existing_hashes:
                    logger.debug(f"Skipping duplicate transaction: {tx_hash}")
                    skipped_transactions.append(tx_data)
                    continue

                # Get historical price at transaction time
                price_at_time = get_historical_price_at_time(
                    symbol='BTC',
                    timestamp=tx_data['timestamp'],
                    base_currency='EUR'
                )

                if price_at_time:
                    tx_data['price_at_execution'] = price_at_time
                    tx_data['total_amount'] = tx_data['quantity'] * price_at_time
                    tx_data['currency'] = CryptoCurrency.EUR
                else:
                    # Fallback to current price if historical price not available
                    logger.warning(f"Could not get historical price for transaction {tx_hash}, using current price from Yahoo Finance")
                    try:
                        price_fetcher = PriceFetcher()
                        current_price_data = price_fetcher.fetch_realtime_price('BTC-USD')

                        if current_price_data and current_price_data.get('current_price'):
                            current_price_usd = current_price_data['current_price']

                            # Convert USD to EUR
                            eur_rate = get_usd_to_eur_rate()
                            if eur_rate:
                                current_price_eur = current_price_usd * eur_rate
                                logger.debug(f"Using current Yahoo Finance price for {tx_hash}: {current_price_eur} EUR (converted from {current_price_usd} USD)")
                                tx_data['price_at_execution'] = current_price_eur
                            else:
                                logger.warning(f"Could not get USD to EUR conversion rate, using USD price: {current_price_usd}")
                                tx_data['price_at_execution'] = current_price_usd
                                tx_data['currency'] = CryptoCurrency.USD

                            tx_data['total_amount'] = tx_data['quantity'] * tx_data['price_at_execution']
                            tx_data['currency'] = CryptoCurrency.EUR if eur_rate else CryptoCurrency.USD
                        else:
                            raise Exception("Yahoo Finance returned no price data")

                    except Exception as e:
                        # No fallback - skip transactions without valid price data
                        logger.error(f"Could not get any price data for transaction {tx_hash}: {e}. Skipping transaction.")
                        failed_transactions.append(tx_data)
                        continue

                # Create transaction record
                transaction = CryptoTransaction(
                    portfolio_id=portfolio_id,
                    symbol=tx_data['symbol'],
                    transaction_type=tx_data['transaction_type'],
                    quantity=tx_data['quantity'],
                    price_at_execution=tx_data['price_at_execution'],
                    total_amount=tx_data['total_amount'],
                    currency=tx_data['currency'],
                    fee=tx_data.get('fee', Decimal('0')),
                    fee_currency=tx_data.get('fee_currency'),
                    timestamp=tx_data['timestamp'],
                    exchange=tx_data.get('exchange', 'Bitcoin Blockchain'),
                    transaction_hash=tx_data.get('transaction_hash'),
                    notes=tx_data.get('notes', f'Blockchain transaction: {tx_hash}')
                )

                new_transactions.append(transaction)

            except Exception as e:
                logger.error(f"Error processing transaction {tx_data.get('transaction_hash', 'unknown')}: {e}")
                failed_transactions.append(tx_data)
                continue

        # Save new transactions to database
        transactions_added = 0
        for transaction in new_transactions:
            try:
                db_session.add(transaction)
                db_session.commit()
                transactions_added += 1
                logger.debug(f"Added new transaction: {transaction.transaction_hash}")

            except IntegrityError as e:
                db_session.rollback()
                # This could happen due to race conditions or duplicate hash constraints
                logger.warning(f"Integrity error adding transaction {transaction.transaction_hash}: {e}")
                skipped_transactions.append(transaction.transaction_hash)
                continue

            except Exception as e:
                db_session.rollback()
                logger.error(f"Error saving transaction {transaction.transaction_hash}: {e}")
                failed_transactions.append(transaction.transaction_hash)
                continue

        result = {
            "status": "success",
            "transactions_added": transactions_added,
            "transactions_skipped": len(skipped_transactions),
            "transactions_failed": len(failed_transactions),
            "total_fetched": len(blockchain_transactions),
            "message": f"Added {transactions_added} new transactions for wallet {wallet_address}"
        }

        logger.info(
            f"Wallet {wallet_address} sync complete: "
            f"{transactions_added} added, "
            f"{len(skipped_transactions)} skipped, "
            f"{len(failed_transactions)} failed"
        )

        return result

    except Exception as e:
        logger.error(f"Error syncing wallet {wallet_address}: {e}")
        return {
            "status": "error",
            "error": str(e),
            "transactions_added": 0,
            "transactions_skipped": 0,
            "transactions_failed": 0
        }


from typing import Optional

def get_historical_price_at_time(
    symbol: str,
    timestamp: datetime,
    base_currency: str = 'EUR'
) -> Optional[Decimal]:
    """
    Retrieve the price of a cryptocurrency closest to a given timestamp in the requested currency.
    
    Attempts to obtain a historical price near the provided timestamp and falls back to a current price when historical data is unavailable. Returned value is expressed in the requested base currency; if a conversion from USD to EUR is required but unavailable, the function may return the USD value or None when no price can be determined.
    
    Parameters:
        symbol (str): Cryptocurrency symbol (e.g., 'BTC').
        timestamp (datetime): Target point in time for the price lookup.
        base_currency (str): Desired currency for the returned price (case-insensitive, typically 'EUR' or 'USD').
    
    Returns:
        Decimal or None: Price of the cryptocurrency in the requested base currency, or `None` if no price data could be obtained.
    """
    try:
        # Get date from timestamp
        target_date = timestamp.date()

        # Initialize price fetcher
        price_fetcher = PriceFetcher()

        # Map crypto symbol to Yahoo Finance ticker
        yahoo_ticker = f"{symbol}-USD"
        logger.debug(f"Fetching historical price for {symbol} using Yahoo ticker: {yahoo_ticker}")

        # Try to get historical price from Yahoo Finance for the target date
        # Use a wider range to ensure we capture the data (target date ± 1 day)
        start_date = target_date - timedelta(days=1)
        end_date = target_date + timedelta(days=1)

        historical_prices = price_fetcher.fetch_historical_prices_sync(
            ticker=yahoo_ticker,
            start_date=start_date,
            end_date=end_date
        )

        if historical_prices:
            # Find the price closest to the target timestamp
            closest_price = None
            min_time_diff = float('inf')

            for price_data in historical_prices:
                price_date = price_data.get('date')
                # Create a datetime for the price date (assuming end of day)
                price_time = datetime.combine(price_date, datetime.max.time())

                time_diff = abs((price_time - timestamp).total_seconds())

                if time_diff < min_time_diff:
                    min_time_diff = time_diff
                    closest_price = price_data.get('close')

            if closest_price:
                # Convert USD to EUR if needed
                if base_currency.upper() == 'EUR':
                    eur_rate = get_usd_to_eur_rate()
                    if eur_rate:
                        closest_price_eur = closest_price * eur_rate
                        logger.debug(f"Found historical price for {symbol} at {timestamp}: {closest_price_eur} EUR (converted from {closest_price} USD)")
                        return closest_price_eur
                    else:
                        logger.warning(f"Could not get USD to EUR conversion rate, using USD price: {closest_price}")

                logger.debug(f"Found historical price for {symbol} at {timestamp}: {closest_price}")
                return closest_price

        # Fallback: try to get current price if historical not available
        logger.warning(f"No historical price available for {symbol} at {timestamp}, trying current price")
        current_price_data = price_fetcher.fetch_realtime_price(yahoo_ticker)

        if current_price_data and current_price_data.get('current_price'):
            current_price = current_price_data['current_price']

            # Convert USD to EUR if needed
            if base_currency.upper() == 'EUR':
                eur_rate = get_usd_to_eur_rate()
                if eur_rate:
                    current_price_eur = current_price * eur_rate
                    logger.debug(f"Using current price for {symbol}: {current_price_eur} EUR (converted from {current_price} USD)")
                    return current_price_eur
                else:
                    logger.warning(f"Could not get USD to EUR conversion rate, using USD price: {current_price}")

            logger.debug(f"Using current price for {symbol}: {current_price}")
            return current_price

        return None

    except Exception as e:
        logger.error(f"Error getting historical price for {symbol} at {timestamp}: {e}")
        return None


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 2, 'countdown': 60}
)
def sync_wallet_manually(
    self,
    wallet_address: str,
    portfolio_id: int,
    max_transactions: Optional[int] = None,
    days_back: Optional[int] = None
):
    """
    Manually trigger a synchronization of transactions for a single Bitcoin wallet and return the per-wallet sync result.

    Fetches ALL historical transactions from the blockchain with NO limits on quantity or time period.

    Parameters:
    	wallet_address (str): Bitcoin wallet address to synchronize.
    	portfolio_id (int): ID of the portfolio that must own the wallet.
    	max_transactions (Optional[int]): Maximum number of transactions to fetch. None = unlimited (fetch all).
    	days_back (Optional[int]): Lookback window in days. None = unlimited (fetch from beginning of blockchain).

    Returns:
    	dict: Summary of the sync outcome containing keys such as `status`, `transactions_added`, `transactions_skipped`, `transactions_failed`, and optionally `error` with details when the sync cannot be performed.
    """
    logger.info(
        f"Manual sync triggered for Bitcoin wallet {wallet_address} (portfolio {portfolio_id}), "
        f"max_transactions={max_transactions}, days_back={days_back}"
    )

    db = SyncSessionLocal()

    try:
        # Verify portfolio exists and has this wallet address
        portfolio = db.execute(
            select(CryptoPortfolio)
            .where(
                and_(
                    CryptoPortfolio.id == portfolio_id,
                    CryptoPortfolio.wallet_address == wallet_address,
                    CryptoPortfolio.is_active == True
                )
            )
        ).scalar_one_or_none()

        if not portfolio:
            return {
                "status": "error",
                "error": f"Portfolio {portfolio_id} not found or wallet address doesn't match",
                "transactions_added": 0,
                "transactions_skipped": 0,
                "transactions_failed": 0
            }

        # Sync the wallet with configurable limits for manual sync
        result = sync_single_wallet(
            wallet_address=wallet_address,
            portfolio_id=portfolio_id,
            db_session=db,
            max_transactions=max_transactions,
            days_back=days_back
        )

        logger.info(f"Manual sync completed for wallet {wallet_address}: {result}")
        return result

    except Exception as e:
        logger.error(f"Error in manual wallet sync for {wallet_address}: {e}")
        raise

    finally:
        db.close()


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 1, 'countdown': 30}
)
def test_blockchain_connection(self):
    """
    Test connectivity to configured blockchain API services.
    
    Returns:
        dict: Summary of the connection test. On success includes:
            - status (str): "success"
            - message (str): human-readable summary like "Connected to X/Y blockchain APIs"
            - api_results (dict): mapping of API identifiers to boolean connection results
            - timestamp (str): ISO-formatted UTC timestamp
        On failure includes:
            - status (str): "error"
            - error (str): error message
            - timestamp (str): ISO-formatted UTC timestamp
    """
    logger.info("Testing blockchain API connections")

    try:
        results = blockchain_fetcher.test_api_connection()

        success_count = sum(1 for status in results.values() if status)
        total_count = len(results)

        summary = {
            "status": "success",
            "message": f"Connected to {success_count}/{total_count} blockchain APIs",
            "api_results": results,
            "timestamp": datetime.utcnow().isoformat()
        }

        logger.info(f"Blockchain API connection test: {summary}")
        return summary

    except Exception as e:
        logger.error(f"Error testing blockchain API connections: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }