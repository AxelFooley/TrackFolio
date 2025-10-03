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


@router.get("/{ticker}", response_model=PositionResponse)
async def get_asset_detail(
    ticker: str,
    db: AsyncSession = Depends(get_db)
):
    """Get detailed information for a specific asset (by ticker or ISIN)."""
    # Try ISIN first (if 12 characters)
    if len(ticker) == 12:
        result = await db.execute(
            select(Position).where(Position.isin == ticker)
        )
    else:
        # Try by current_ticker
        result = await db.execute(
            select(Position).where(Position.current_ticker == ticker)
        )

    position = result.scalar_one_or_none()

    if not position:
        raise HTTPException(status_code=404, detail="Asset not found")

    return position


@router.get("/{ticker}/transactions", response_model=List[TransactionResponse])
async def get_asset_transactions(
    ticker: str,
    db: AsyncSession = Depends(get_db)
):
    """Get all transactions for a specific asset."""
    result = await db.execute(
        select(Transaction)
        .where(Transaction.ticker == ticker)
        .order_by(Transaction.operation_date.desc())
    )
    transactions = result.scalars().all()

    return transactions


@router.get("/{ticker}/prices", response_model=List[PriceResponse])
async def get_asset_prices(
    ticker: str,
    limit: int = 365,
    db: AsyncSession = Depends(get_db)
):
    """Get historical price data for a specific asset."""
    result = await db.execute(
        select(PriceHistory)
        .where(PriceHistory.ticker == ticker)
        .order_by(PriceHistory.date.desc())
        .limit(limit)
    )
    prices = result.scalars().all()

    return prices
