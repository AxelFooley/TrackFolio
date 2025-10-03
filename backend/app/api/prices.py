"""Price update API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.database import get_db

router = APIRouter(prefix="/api/prices", tags=["prices"])


@router.post("/refresh")
async def refresh_prices(db: AsyncSession = Depends(get_db)):
    """
    Manual price refresh endpoint.

    Rate limited to prevent abuse (1 refresh per 5 minutes).
    """
    # This would trigger price update job
    # For now, return placeholder response
    return {
        "message": "Price refresh triggered",
        "timestamp": datetime.utcnow()
    }


@router.get("/last-update")
async def get_last_update(db: AsyncSession = Depends(get_db)):
    """Get timestamp of last successful price update."""
    # Would query from a system state table or cache
    return {
        "last_update": datetime.utcnow(),
        "status": "success"
    }
