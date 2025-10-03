"""
Transaction API endpoints.

Handles CSV import, transaction CRUD operations.
"""
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.exc import IntegrityError
from typing import List
from datetime import datetime
import logging

from app.database import get_db
from app.models import Transaction, TransactionType
from app.schemas.transaction import (
    TransactionResponse,
    TransactionUpdate,
    TransactionImportSummary
)
from app.services.csv_parser import DirectaCSVParser
from app.services.deduplication import DeduplicationService
from app.services.position_manager import PositionManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/transactions", tags=["transactions"])


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
        for isin in affected_isins:
            await PositionManager.recalculate_position(db, isin)

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
    Update transaction (fees only).

    As per PRD, only fees can be edited after import.
    """
    result = await db.execute(
        select(Transaction).where(Transaction.id == transaction_id)
    )
    transaction = result.scalar_one_or_none()

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Update fees
    transaction.fees = transaction_update.fees
    transaction.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(transaction)

    # Recalculate position for this ISIN
    await PositionManager.recalculate_position(db, transaction.isin)

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
    await db.delete(transaction)
    await db.commit()

    # Recalculate position
    await PositionManager.recalculate_position(db, isin)

    return {"message": "Transaction deleted successfully"}
