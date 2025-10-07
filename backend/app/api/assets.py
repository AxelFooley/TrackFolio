"""Assets API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.database import get_db
from app.models import Position, Transaction, PriceHistory
from app.schemas.position import PositionResponse
from app.schemas.transaction import TransactionResponse
from app.schemas.price import PriceResponse

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.get("/{identifier}", response_model=PositionResponse)
async def get_asset_detail(
    identifier: str,
    db: AsyncSession = Depends(get_db)
):
    """Get detailed information for a specific asset (by ticker or ISIN)."""
    # Try different strategies to find the asset

    # Strategy 1: Check if it's a crypto ISIN (starts with XC)
    if identifier.upper().startswith("XC"):
        result = await db.execute(
            select(Position).where(Position.isin == identifier.upper())
        )
        position = result.scalar_one_or_none()
        if position:
            return position

    # Strategy 2: Check if it's a standard ISIN (12 characters)
    if len(identifier) == 12:
        result = await db.execute(
            select(Position).where(Position.isin == identifier.upper())
        )
        position = result.scalar_one_or_none()
        if position:
            return position

    # Strategy 3: Try by current_ticker (case-insensitive)
    result = await db.execute(
        select(Position).where(Position.current_ticker == identifier.upper())
    )
    position = result.scalar_one_or_none()
    if position:
        return position

    # Strategy 4: Check if it might be a crypto ticker and normalize
    from app.services.crypto_csv_parser import CryptoCSVParser
    if CryptoCSVParser.is_crypto_transaction(identifier):
        normalized_ticker = CryptoCSVParser.normalize_crypto_ticker(identifier)
        result = await db.execute(
            select(Position).where(Position.current_ticker == normalized_ticker)
        )
        position = result.scalar_one_or_none()
        if position:
            return position

    raise HTTPException(status_code=404, detail=f"Asset '{identifier}' not found")


@router.get("/{identifier}/transactions", response_model=List[TransactionResponse])
async def get_asset_transactions(
    identifier: str,
    db: AsyncSession = Depends(get_db)
):
    """Get all transactions for a specific asset."""
    # Try to find the asset first to get the correct ISIN
    try:
        # Reuse the asset lookup logic
        position = await get_asset_detail(identifier, db)
        # If we found a position, use its ISIN to get all transactions
        result = await db.execute(
            select(Transaction)
            .where(Transaction.isin == position.isin)
            .order_by(Transaction.operation_date.desc())
        )
        transactions = result.scalars().all()
        return transactions
    except HTTPException:
        # If position not found, try direct ticker search
        from app.services.crypto_csv_parser import CryptoCSVParser

        # Check if it's a crypto ticker and normalize
        ticker_to_search = identifier
        if CryptoCSVParser.is_crypto_transaction(identifier):
            ticker_to_search = CryptoCSVParser.normalize_crypto_ticker(identifier)

        result = await db.execute(
            select(Transaction)
            .where(Transaction.ticker == ticker_to_search.upper())
            .order_by(Transaction.operation_date.desc())
        )
        transactions = result.scalars().all()
        return transactions


@router.get("/{identifier}/prices", response_model=List[PriceResponse])
async def get_asset_prices(
    identifier: str,
    limit: int = 365,
    db: AsyncSession = Depends(get_db)
):
    """Get historical price data for a specific asset."""
    # Try to find the asset first to get the correct ticker
    try:
        # Reuse the asset lookup logic
        position = await get_asset_detail(identifier, db)
        # Use the position's current ticker for price lookup
        ticker_to_search = position.current_ticker
    except HTTPException:
        # If position not found, normalize the identifier as a ticker
        from app.services.crypto_csv_parser import CryptoCSVParser
        ticker_to_search = identifier
        if CryptoCSVParser.is_crypto_transaction(identifier):
            ticker_to_search = CryptoCSVParser.normalize_crypto_ticker(identifier)

    result = await db.execute(
        select(PriceHistory)
        .where(PriceHistory.ticker == ticker_to_search.upper())
        .order_by(PriceHistory.date.desc())
        .limit(limit)
    )
    prices = result.scalars().all()

    return prices
