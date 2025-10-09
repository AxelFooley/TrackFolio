"""
Blockchain API endpoints for wallet synchronization and management.

This module provides REST API endpoints for:
- Manual wallet synchronization
- Blockchain transaction fetching
- Wallet configuration
- Sync status and monitoring
"""
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, validator
import logging

from app.database import SyncSessionLocal
from app.models.crypto import CryptoPortfolio, CryptoTransaction, CryptoTransactionType
from app.services.blockchain_fetcher import blockchain_fetcher
from app.services.blockchain_deduplication import blockchain_deduplication
from app.tasks.blockchain_sync import sync_wallet_manually, test_blockchain_connection

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/blockchain", tags=["blockchain"])


# Pydantic models for requests and responses
class WalletSyncRequest(BaseModel):
    """Request model for manual wallet synchronization."""
    portfolio_id: int = Field(..., description="Portfolio ID to sync")
    wallet_address: str = Field(..., description="Bitcoin wallet address to sync")
    max_transactions: Optional[int] = Field(100, description="Maximum number of transactions to fetch", ge=1, le=500)
    days_back: Optional[int] = Field(30, description="Number of days to look back", ge=1, le=365)

    @validator('wallet_address')
    def validate_wallet_address(cls, v):
        if not v or not v.strip():
            raise ValueError('Wallet address cannot be empty')
        return v.strip()


class WalletConfigRequest(BaseModel):
    """Request model for wallet configuration."""
    portfolio_id: int = Field(..., description="Portfolio ID")
    wallet_address: str = Field(..., description="Bitcoin wallet address to configure")

    @validator('wallet_address')
    def validate_wallet_address(cls, v):
        if not v or not v.strip():
            raise ValueError('Wallet address cannot be empty')
        return v.strip()


class TransactionResponse(BaseModel):
    """Response model for transaction data."""
    id: int
    portfolio_id: int
    symbol: str
    transaction_type: str
    quantity: float
    price_at_execution: float
    total_amount: float
    currency: str
    fee: float
    fee_currency: Optional[str]
    timestamp: datetime
    exchange: Optional[str]
    transaction_hash: Optional[str]
    notes: Optional[str]

    class Config:
        from_attributes = True


class WalletSyncResponse(BaseModel):
    """Response model for wallet synchronization."""
    status: str
    message: str
    transactions_added: int
    transactions_skipped: int
    transactions_failed: int
    sync_timestamp: datetime


class BlockchainStatusResponse(BaseModel):
    """Response model for blockchain service status."""
    status: str
    message: str
    api_results: Dict[str, bool]
    cache_stats: Dict[str, Any]
    timestamp: datetime


class WalletTransactionsResponse(BaseModel):
    """Response model for wallet transactions."""
    wallet_address: str
    transactions: List[Dict[str, Any]]
    count: int
    total_fetched: int
    status: str
    message: str
    timestamp: datetime


def get_db():
    """Dependency to get database session."""
    db = SyncSessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/sync/wallet", response_model=WalletSyncResponse)
async def sync_wallet(
    request: WalletSyncRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Manually trigger synchronization for a Bitcoin wallet.

    This endpoint:
    1. Validates the portfolio and wallet address
    2. Starts a background task to fetch transactions
    3. Returns immediate response with task status

    Args:
        request: Wallet sync request parameters
        background_tasks: FastAPI background tasks
        db: Database session

    Returns:
        Sync response with status information
    """
    try:
        # Verify portfolio exists
        portfolio = db.execute(
            select(CryptoPortfolio).where(CryptoPortfolio.id == request.portfolio_id)
        ).scalar_one_or_none()

        if not portfolio:
            raise HTTPException(
                status_code=404,
                detail=f"Portfolio with ID {request.portfolio_id} not found"
            )

        # Verify wallet address matches portfolio (if already configured)
        if portfolio.wallet_address and portfolio.wallet_address != request.wallet_address:
            raise HTTPException(
                status_code=400,
                detail=f"Wallet address does not match portfolio. "
                       f"Portfolio has {portfolio.wallet_address}, "
                       f"request has {request.wallet_address}"
            )

        # Start background sync task
        task = sync_wallet_manually.delay(
            wallet_address=request.wallet_address,
            portfolio_id=request.portfolio_id
        )

        logger.info(
            f"Started manual sync task {task.id} for wallet {request.wallet_address} "
            f"(portfolio {request.portfolio_id})"
        )

        return WalletSyncResponse(
            status="started",
            message=f"Sync task started for wallet {request.wallet_address}",
            transactions_added=0,
            transactions_skipped=0,
            transactions_failed=0,
            sync_timestamp=datetime.utcnow()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting wallet sync: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start wallet sync: {str(e)}"
        )


@router.post("/config/wallet")
async def configure_wallet(
    request: WalletConfigRequest,
    db: Session = Depends(get_db)
):
    """
    Configure or update a Bitcoin wallet address for a portfolio.

    Args:
        request: Wallet configuration request
        db: Database session

    Returns:
        Configuration status response
    """
    try:
        # Verify portfolio exists
        portfolio = db.execute(
            select(CryptoPortfolio).where(CryptoPortfolio.id == request.portfolio_id)
        ).scalar_one_or_none()

        if not portfolio:
            raise HTTPException(
                status_code=404,
                detail=f"Portfolio with ID {request.portfolio_id} not found"
            )

        # Validate wallet address using the model's validator
        try:
            # The model will validate the address format
            portfolio.wallet_address = request.wallet_address
            db.commit()
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=str(e)
            )

        # Clear deduplication cache for this portfolio
        blockchain_deduplication.clear_portfolio_cache(request.portfolio_id)

        logger.info(
            f"Configured wallet address {request.wallet_address} for portfolio {request.portfolio_id}"
        )

        return {
            "status": "success",
            "message": f"Wallet address configured successfully",
            "portfolio_id": request.portfolio_id,
            "wallet_address": request.wallet_address,
            "timestamp": datetime.utcnow()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error configuring wallet: {e}")
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to configure wallet: {str(e)}"
        )


@router.get("/wallet/{wallet_address}/transactions", response_model=WalletTransactionsResponse)
async def get_wallet_transactions(
    wallet_address: str,
    portfolio_id: int = Query(..., description="Portfolio ID"),
    max_transactions: int = Query(50, description="Maximum transactions to fetch", ge=1, le=200),
    days_back: int = Query(30, description="Days to look back", ge=1, le=365),
    db: Session = Depends(get_db)
):
    """
    Fetch transactions for a Bitcoin wallet without storing them.

    This endpoint only fetches and returns transaction data without
    adding it to the database. Useful for preview purposes.

    Args:
        wallet_address: Bitcoin wallet address
        portfolio_id: Portfolio ID for context
        max_transactions: Maximum number of transactions to fetch
        days_back: Number of days to look back
        db: Database session

    Returns:
        Wallet transactions response
    """
    try:
        # Verify portfolio exists
        portfolio = db.execute(
            select(CryptoPortfolio).where(CryptoPortfolio.id == portfolio_id)
        ).scalar_one_or_none()

        if not portfolio:
            raise HTTPException(
                status_code=404,
                detail=f"Portfolio with ID {portfolio_id} not found"
            )

        # Fetch transactions from blockchain API
        result = blockchain_fetcher.fetch_transactions(
            wallet_address=wallet_address,
            portfolio_id=portfolio_id,
            max_transactions=max_transactions,
            days_back=days_back
        )

        if result['status'] != 'success':
            raise HTTPException(
                status_code=400,
                detail=f"Failed to fetch transactions: {result.get('message', 'Unknown error')}"
            )

        # Filter out existing transactions
        existing_hashes = blockchain_deduplication.get_portfolio_transaction_hashes(portfolio_id)
        unique_transactions = []
        duplicate_count = 0

        for tx in result['transactions']:
            if tx.get('transaction_hash') and tx['transaction_hash'] in existing_hashes:
                duplicate_count += 1
            else:
                unique_transactions.append(tx)

        return WalletTransactionsResponse(
            wallet_address=wallet_address,
            transactions=unique_transactions,
            count=len(unique_transactions),
            total_fetched=result.get('count', 0),
            status="success",
            message=f"Fetched {len(unique_transactions)} new transactions, {duplicate_count} duplicates filtered",
            timestamp=datetime.utcnow()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching wallet transactions: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch wallet transactions: {str(e)}"
        )


@router.get("/status", response_model=BlockchainStatusResponse)
async def get_blockchain_status():
    """
    Get the status of blockchain services and APIs.

    Returns:
        Blockchain service status including API connectivity and cache stats
    """
    try:
        # Test API connections
        api_results = blockchain_fetcher.test_api_connection()

        # Get cache statistics
        cache_stats = blockchain_deduplication.get_cache_stats()

        # Determine overall status
        connected_apis = sum(1 for status in api_results.values() if status)
        total_apis = len(api_results)

        if connected_apis == 0:
            status = "error"
            message = "No blockchain APIs are reachable"
        elif connected_apis < total_apis:
            status = "warning"
            message = f"Only {connected_apis}/{total_apis} blockchain APIs are reachable"
        else:
            status = "success"
            message = "All blockchain APIs are reachable"

        return BlockchainStatusResponse(
            status=status,
            message=message,
            api_results=api_results,
            cache_stats=cache_stats,
            timestamp=datetime.utcnow()
        )

    except Exception as e:
        logger.error(f"Error getting blockchain status: {e}")
        return BlockchainStatusResponse(
            status="error",
            message=f"Failed to get blockchain status: {str(e)}",
            api_results={},
            cache_stats={},
            timestamp=datetime.utcnow()
        )


@router.post("/test-connection")
async def test_blockchain_apis():
    """
    Test connectivity to all blockchain APIs.

    This endpoint can be used to diagnose API connectivity issues.

    Returns:
        API connection test results
    """
    try:
        # Start background task for connection testing
        task = test_blockchain_connection.delay()

        return {
            "status": "started",
            "message": "Blockchain API connection test started",
            "task_id": task.id,
            "timestamp": datetime.utcnow()
        }

    except Exception as e:
        logger.error(f"Error starting blockchain API test: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start API test: {str(e)}"
        )


@router.get("/portfolio/{portfolio_id}/transactions")
async def get_portfolio_blockchain_transactions(
    portfolio_id: int,
    limit: int = Query(50, description="Maximum transactions to return", ge=1, le=200),
    offset: int = Query(0, description="Number of transactions to skip", ge=0),
    db: Session = Depends(get_db)
):
    """
    Get blockchain transactions for a portfolio.

    Args:
        portfolio_id: Portfolio ID
        limit: Maximum number of transactions to return
        offset: Number of transactions to skip
        db: Database session

    Returns:
        List of blockchain transactions for the portfolio
    """
    try:
        # Verify portfolio exists
        portfolio = db.execute(
            select(CryptoPortfolio).where(CryptoPortfolio.id == portfolio_id)
        ).scalar_one_or_none()

        if not portfolio:
            raise HTTPException(
                status_code=404,
                detail=f"Portfolio with ID {portfolio_id} not found"
            )

        # Get blockchain transactions (those with exchange = 'Bitcoin Blockchain')
        result = db.execute(
            select(CryptoTransaction)
            .where(
                and_(
                    CryptoTransaction.portfolio_id == portfolio_id,
                    CryptoTransaction.exchange == 'Bitcoin Blockchain'
                )
            )
            .order_by(CryptoTransaction.timestamp.desc())
            .limit(limit)
            .offset(offset)
        )

        transactions = result.scalars().all()

        # Get total count
        total_count = db.execute(
            select(func.count(CryptoTransaction.id))
            .where(
                and_(
                    CryptoTransaction.portfolio_id == portfolio_id,
                    CryptoTransaction.exchange == 'Bitcoin Blockchain'
                )
            )
        ).scalar()

        return {
            "portfolio_id": portfolio_id,
            "wallet_address": portfolio.wallet_address,
            "transactions": [TransactionResponse.from_orm(tx) for tx in transactions],
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "timestamp": datetime.utcnow()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting portfolio blockchain transactions: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get portfolio transactions: {str(e)}"
        )


@router.delete("/portfolio/{portfolio_id}/cache")
async def clear_portfolio_cache(portfolio_id: int, db: Session = Depends(get_db)):
    """
    Clear deduplication cache for a portfolio.

    This can be useful if you suspect duplicate detection is not working correctly.

    Args:
        portfolio_id: Portfolio ID
        db: Database session

    Returns:
        Cache clearing status
    """
    try:
        # Verify portfolio exists
        portfolio = db.execute(
            select(CryptoPortfolio).where(CryptoPortfolio.id == portfolio_id)
        ).scalar_one_or_none()

        if not portfolio:
            raise HTTPException(
                status_code=404,
                detail=f"Portfolio with ID {portfolio_id} not found"
            )

        # Clear cache
        blockchain_deduplication.clear_portfolio_cache(portfolio_id)

        logger.info(f"Cleared blockchain cache for portfolio {portfolio_id}")

        return {
            "status": "success",
            "message": f"Cache cleared for portfolio {portfolio_id}",
            "portfolio_id": portfolio_id,
            "timestamp": datetime.utcnow()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing portfolio cache: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear portfolio cache: {str(e)}"
        )


@router.get("/portfolio/{portfolio_id}/sync-history")
async def get_sync_history(
    portfolio_id: int,
    days: int = Query(30, description="Days of history to fetch", ge=1, le=365),
    db: Session = Depends(get_db)
):
    """
    Get synchronization history for a portfolio.

    Args:
        portfolio_id: Portfolio ID
        days: Number of days of history to fetch
        db: Database session

    Returns:
        Sync history for the portfolio
    """
    try:
        # Verify portfolio exists
        portfolio = db.execute(
            select(CryptoPortfolio).where(CryptoPortfolio.id == portfolio_id)
        ).scalar_one_or_none()

        if not portfolio:
            raise HTTPException(
                status_code=404,
                detail=f"Portfolio with ID {portfolio_id} not found"
            )

        # Get recent blockchain transactions
        since_date = datetime.utcnow() - timedelta(days=days)

        result = db.execute(
            select(CryptoTransaction)
            .where(
                and_(
                    CryptoTransaction.portfolio_id == portfolio_id,
                    CryptoTransaction.exchange == 'Bitcoin Blockchain',
                    CryptoTransaction.timestamp >= since_date
                )
            )
            .order_by(CryptoTransaction.timestamp.desc())
        )

        transactions = result.scalars().all()

        # Group transactions by date
        sync_history = {}
        for tx in transactions:
            date_key = tx.timestamp.date().isoformat()
            if date_key not in sync_history:
                sync_history[date_key] = {
                    "date": date_key,
                    "transaction_count": 0,
                    "total_amount": 0.0,
                    "transaction_types": {}
                }

            sync_history[date_key]["transaction_count"] += 1
            sync_history[date_key]["total_amount"] += float(tx.total_amount)

            tx_type = tx.transaction_type.value
            if tx_type not in sync_history[date_key]["transaction_types"]:
                sync_history[date_key]["transaction_types"][tx_type] = 0
            sync_history[date_key]["transaction_types"][tx_type] += 1

        # Convert to list and sort by date
        history_list = sorted(sync_history.values(), key=lambda x: x["date"], reverse=True)

        return {
            "portfolio_id": portfolio_id,
            "wallet_address": portfolio.wallet_address,
            "sync_history": history_list,
            "total_days": len(history_list),
            "total_transactions": len(transactions),
            "period_days": days,
            "timestamp": datetime.utcnow()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting sync history: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get sync history: {str(e)}"
        )