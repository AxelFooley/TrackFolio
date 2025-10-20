"""
Transaction API endpoints.

Handles CSV import, transaction CRUD operations.
"""
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.exc import IntegrityError
from typing import List, Optional, Tuple
from datetime import datetime
import logging
import asyncio
import requests.exceptions

from app.database import get_db
from app.models import Transaction, TransactionType
from app.schemas.transaction import (
    TransactionResponse,
    TransactionCreate,
    ManualTransactionCreate,
    TransactionUpdate,
    TransactionImportSummary
)
from app.services.csv_parser import DirectaCSVParser
from app.services.deduplication import DeduplicationService
from app.services.position_manager import PositionManager
from app.services.price_fetcher import PriceFetcher
from app.services.calculations import FinancialCalculations
from app.services.currency_converter import get_exchange_rate
import yfinance as yf
from decimal import Decimal

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/transactions", tags=["transactions"])


async def fetch_ticker_metadata(ticker: str) -> Tuple[Optional[str], str]:
    """
    Fetch ISIN and description from Yahoo Finance for a given ticker.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Tuple of (isin, description). ISIN may be None if not found.
    """
    try:
        # Run blocking yfinance call in executor with timeout
        loop = asyncio.get_event_loop()

        def get_info():
            stock = yf.Ticker(ticker)
            return stock.info

        # Add timeout to prevent hanging
        info = await asyncio.wait_for(loop.run_in_executor(None, get_info), timeout=5.0)

        # Get ISIN from Yahoo Finance info
        isin = info.get('isin')

        # Get description (prefer longName, fallback to shortName, then ticker)
        description = info.get('longName') or info.get('shortName') or ticker

        logger.info(f"Fetched metadata for {ticker}: ISIN={isin}, Description={description}")
        return isin, description

    except asyncio.TimeoutError:
        logger.warning(f"Timeout fetching metadata for {ticker}. Using ticker as description.")
        return None, ticker
    except requests.exceptions.RequestException as e:
        logger.warning(f"Network error fetching metadata for {ticker}: {str(e)}. Using ticker as description.")
        return None, ticker


@router.post("/import", response_model=TransactionImportSummary)
async def import_transactions(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload and import Directa CSV file.

    Returns summary of imported transactions and duplicates skipped.
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    try:
        # Read file content
        content = await file.read()
        file_content = content.decode('utf-8')

        # Parse CSV (skips first 9 rows)
        parsed_transactions = DirectaCSVParser.parse(file_content)

        # Check for duplicates
        new_transactions, duplicates = await DeduplicationService.check_duplicates(
            db, parsed_transactions
        )

        # If all transactions are duplicates, return early
        if not new_transactions:
            message = f"All {len(parsed_transactions)} transactions are duplicates. No new transactions imported."
            logger.info(message)
            return TransactionImportSummary(
                total_parsed=len(parsed_transactions),
                imported=0,
                duplicates=len(duplicates),
                message=message
            )

        # Import new transactions
        imported_count = 0
        affected_isins = set()

        try:
            for txn_data in new_transactions:
                # Create Transaction model
                transaction = Transaction(
                    operation_date=txn_data["operation_date"],
                    value_date=txn_data["value_date"],
                    transaction_type=TransactionType(txn_data["transaction_type"]),
                    ticker=txn_data["ticker"],
                    isin=txn_data.get("isin"),
                    description=txn_data["description"],
                    quantity=txn_data["quantity"],
                    price_per_share=txn_data["price_per_share"],
                    amount_eur=txn_data["amount_eur"],
                    amount_currency=txn_data["amount_currency"],
                    currency=txn_data["currency"],
                    fees=txn_data["fees"],
                    order_reference=txn_data["order_reference"],
                    transaction_hash=txn_data["transaction_hash"],
                    imported_at=datetime.utcnow()
                )
                db.add(transaction)
                affected_isins.add(txn_data["isin"])
                imported_count += 1

            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
            if "duplicate key" in error_msg.lower():
                raise HTTPException(
                    status_code=409,
                    detail=f"Duplicate transaction detected. This file may have already been imported. Error: {error_msg}"
                )
            raise

        # Recalculate positions for affected ISINs
        # Use targeted queries instead of loading all transactions into memory
        for isin in affected_isins:
            # Query for a single transaction with this ISIN to get its ticker
            result = await db.execute(
                select(Transaction.ticker)
                .where(Transaction.isin == isin)
                .limit(1)
            )
            ticker = result.scalar_one_or_none()

            await PositionManager.recalculate_position(db, isin=isin, ticker=ticker)

        # Detect and record any new splits
        await PositionManager.detect_and_record_splits(db)

        # Trigger automatic backfill for historical data
        if imported_count > 0:
            from app.tasks.auto_backfill import trigger_automatic_backfill
            trigger_automatic_backfill.delay()  # Async background task
            logger.info("Triggered automatic historical data backfill")

        message = (
            f"Imported {imported_count} new transactions, skipped {len(duplicates)} duplicates. "
            f"Historical price data and portfolio snapshots are being calculated in the background."
        )
        logger.info(message)

        return TransactionImportSummary(
            total_parsed=len(parsed_transactions),
            imported=imported_count,
            duplicates=len(duplicates),
            message=message
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error importing transactions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to import transactions")


@router.post("/", response_model=TransactionResponse)
async def create_transaction(
    transaction_data: ManualTransactionCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new transaction manually.

    Accepts simplified frontend schema and auto-populates all required backend fields:
    - Fetches ISIN and description from Yahoo Finance
    - Calculates amounts in EUR and native currency
    - Generates order_reference
    - Creates transaction_hash and checks for duplicates
    """
    try:
        # 1. Map frontend 'type' to backend 'transaction_type'
        transaction_type = transaction_data.type  # 'buy' or 'sell'

        # 2. Fetch ticker metadata (ISIN and description) from Yahoo Finance
        isin, description = await fetch_ticker_metadata(transaction_data.ticker)

        # 3. Set price_per_share from frontend 'amount' field
        price_per_share = transaction_data.amount

        # 4. Calculate amounts
        amount_currency = transaction_data.quantity * price_per_share

        # 5. Convert to EUR if needed
        if transaction_data.currency == "EUR":
            amount_eur = amount_currency
        else:
            # For non-EUR currencies, fetch FX rate and convert
            try:
                fx_rate = get_exchange_rate(transaction_data.currency, "EUR")
                if fx_rate is None:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Could not fetch exchange rate for {transaction_data.currency} to EUR. Please try again later."
                    )

                amount_eur = amount_currency * fx_rate
                logger.info(f"Converted {amount_currency} {transaction_data.currency} to {amount_eur} EUR using rate {fx_rate}")

            except HTTPException:
                # Re-raise HTTP exceptions as-is
                raise
            except Exception as e:
                logger.exception(f"Error converting {transaction_data.currency} to EUR: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to convert {transaction_data.currency} to EUR. Please try again later."
                )

        # 6. Set value_date to operation_date (manual entries happen on same day)
        value_date = transaction_data.operation_date

        # 7. Generate order_reference with timestamp
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
        order_reference = f"MANUAL-{timestamp}"

        # 8. Generate transaction hash
        transaction_hash = DeduplicationService.calculate_hash(
            operation_date=transaction_data.operation_date,
            ticker=transaction_data.ticker,
            quantity=transaction_data.quantity,
            price_per_share=price_per_share,
            order_reference=order_reference
        )

        # 9. Check for duplicates
        is_dup = await DeduplicationService.is_duplicate(db, transaction_hash)
        if is_dup:
            raise HTTPException(
                status_code=409,
                detail="Duplicate transaction detected. A transaction with the same date, ticker, quantity, price, and order reference already exists."
            )

        # 10. Create Transaction model
        transaction = Transaction(
            operation_date=transaction_data.operation_date,
            value_date=value_date,
            transaction_type=TransactionType(transaction_type),
            ticker=transaction_data.ticker,
            isin=isin,
            description=description,
            quantity=transaction_data.quantity,
            price_per_share=price_per_share,
            amount_eur=amount_eur,
            amount_currency=amount_currency,
            currency=transaction_data.currency,
            fees=transaction_data.fees,
            order_reference=order_reference,
            transaction_hash=transaction_hash,
            imported_at=datetime.utcnow()
        )

        db.add(transaction)
        await db.commit()
        await db.refresh(transaction)

        # 11. Recalculate position for this transaction
        # Use ISIN if available, otherwise use ticker
        await PositionManager.recalculate_position(
            db,
            isin=transaction.isin,
            ticker=transaction.ticker
        )

        # 12. Detect and record any new splits
        await PositionManager.detect_and_record_splits(db)

        # 13. Trigger automatic backfill for historical data
        from app.tasks.auto_backfill import trigger_automatic_backfill
        trigger_automatic_backfill.delay()  # Async background task
        logger.info("Triggered automatic historical data backfill after manual transaction creation")

        logger.info(f"Created manual transaction: {transaction.ticker} on {transaction.operation_date}")
        return transaction

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except IntegrityError as e:
        await db.rollback()
        error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
        if "duplicate key" in error_msg.lower():
            raise HTTPException(
                status_code=409,
                detail=f"Duplicate transaction detected: {error_msg}"
            ) from e
        raise HTTPException(status_code=400, detail=f"Database integrity error: {error_msg}") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}") from e
    except Exception as e:
        logger.exception(f"Error creating transaction: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create transaction") from e


@router.get("/", response_model=List[TransactionResponse])
async def list_transactions(
    skip: int = 0,
    limit: int = 100,
    ticker: str = None,
    db: AsyncSession = Depends(get_db)
):
    """
    List all transactions with optional filtering and pagination.

    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        ticker: Filter by ticker (optional)
    """
    query = select(Transaction).order_by(desc(Transaction.operation_date))

    if ticker:
        query = query.where(Transaction.ticker == ticker)

    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    transactions = result.scalars().all()

    return transactions


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific transaction by ID."""
    result = await db.execute(
        select(Transaction).where(Transaction.id == transaction_id)
    )
    transaction = result.scalar_one_or_none()

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    return transaction


@router.put("/{transaction_id}", response_model=TransactionResponse)
async def update_transaction(
    transaction_id: int,
    transaction_update: TransactionUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update transaction fields.

    Supports updating operation_date, ticker, type, quantity, amount (price_per_share),
    currency, and fees. Handles currency conversion, ticker metadata refresh,
    and transaction hash recalculation.
    """
    result = await db.execute(
        select(Transaction).where(Transaction.id == transaction_id)
    )
    transaction = result.scalar_one_or_none()

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Check if any fields are actually being updated
    updates = {}

    # Update operation_date if provided
    if transaction_update.operation_date is not None:
        updates['operation_date'] = transaction_update.operation_date
        updates['value_date'] = transaction_update.operation_date  # Keep value_date same as operation_date for manual edits

    # Update ticker if provided
    if transaction_update.ticker is not None:
        updates['ticker'] = transaction_update.ticker
        # Fetch new ISIN and description for the new ticker
        isin, description = await fetch_ticker_metadata(transaction_update.ticker)
        updates['isin'] = isin
        updates['description'] = description

    # Update transaction_type if provided
    if transaction_update.type is not None:
        updates['transaction_type'] = TransactionType(transaction_update.type)

    # Update quantity if provided
    if transaction_update.quantity is not None:
        updates['quantity'] = transaction_update.quantity

    # Update price_per_share if provided (frontend sends 'amount')
    if transaction_update.amount is not None:
        updates['price_per_share'] = transaction_update.amount

    # Update currency if provided
    if transaction_update.currency is not None:
        updates['currency'] = transaction_update.currency

    # Update fees if provided
    if transaction_update.fees is not None:
        updates['fees'] = transaction_update.fees

    # If no updates provided, return the transaction as-is
    if not updates:
        return transaction

    # Store original ISIN before applying updates for position recalculation
    original_isin = transaction.isin

    # Apply updates to the transaction object
    for field, value in updates.items():
        setattr(transaction, field, value)

    # Recalculate amounts if quantity, price_per_share, or currency changed
    if 'quantity' in updates or 'price_per_share' in updates or 'currency' in updates:
        # Calculate amount_currency
        amount_currency = transaction.quantity * transaction.price_per_share
        transaction.amount_currency = amount_currency

        # Convert to EUR if needed
        if transaction.currency == "EUR":
            transaction.amount_eur = amount_currency
        else:
            # For non-EUR currencies, fetch FX rate and convert
            try:
                fx_rate = get_exchange_rate(transaction.currency, "EUR")
                if fx_rate is None:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Could not fetch exchange rate for {transaction.currency} to EUR. Please try again later."
                    )

                transaction.amount_eur = amount_currency * fx_rate
                logger.info(f"Converted {amount_currency} {transaction.currency} to {transaction.amount_eur} EUR using rate {fx_rate}")

            except HTTPException:
                raise
            except Exception as e:
                logger.exception(f"Error converting {transaction.currency} to EUR: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to convert {transaction.currency} to EUR. Please try again later."
                )

    # Recalculate transaction hash if any of these fields changed
    hash_fields_changed = any(field in updates for field in ['operation_date', 'ticker', 'quantity', 'price_per_share'])
    if hash_fields_changed:
        # Generate new transaction hash
        new_transaction_hash = DeduplicationService.calculate_hash(
            operation_date=transaction.operation_date,
            ticker=transaction.ticker,
            quantity=transaction.quantity,
            price_per_share=transaction.price_per_share,
            order_reference=transaction.order_reference
        )

        # Check if the new hash would create a duplicate
        is_dup = await DeduplicationService.is_duplicate(db, new_transaction_hash, exclude_id=transaction.id)
        if is_dup:
            raise HTTPException(
                status_code=409,
                detail="Updating this transaction would create a duplicate. A transaction with the same date, ticker, quantity, and price already exists."
            )

        transaction.transaction_hash = new_transaction_hash

    # Update timestamp
    transaction.updated_at = datetime.utcnow()

    # Save changes
    await db.commit()
    await db.refresh(transaction)

    # Recalculate positions for both original and new ISINs
    await PositionManager.recalculate_position(
        db,
        isin=transaction.isin,
        ticker=transaction.ticker
    )

    # Also recalculate original ISIN if it's different and not None
    if original_isin and original_isin != transaction.isin:
        await PositionManager.recalculate_position(
            db,
            isin=original_isin,
            ticker=transaction.ticker  # Use current ticker since ISIN might have been for an old position
        )

    # Detect and record any new splits
    await PositionManager.detect_and_record_splits(db)

    # Trigger background tasks for historical data updates
    from app.tasks.auto_backfill import trigger_automatic_backfill
    trigger_automatic_backfill.delay()
    logger.info(f"Updated transaction {transaction_id}: {transaction.ticker} on {transaction.operation_date}")

    return transaction


@router.delete("/{transaction_id}")
async def delete_transaction(
    transaction_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a transaction and recalculate positions."""
    result = await db.execute(
        select(Transaction).where(Transaction.id == transaction_id)
    )
    transaction = result.scalar_one_or_none()

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    isin = transaction.isin
    ticker = transaction.ticker
    await db.delete(transaction)
    await db.commit()

    # Recalculate position
    await PositionManager.recalculate_position(db, isin=isin, ticker=ticker)

    return {"message": "Transaction deleted successfully"}
