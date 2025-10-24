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
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, validator
import logging

from app.database import SyncSessionLocal
from app.models.crypto import CryptoPortfolio, CryptoTransaction
from app.services.blockchain_fetcher import blockchain_fetcher, BlockchainFetchError
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
    max_transactions: Optional[int] = Field(
        None,
        description="Maximum number of transactions to fetch (None for unlimited)",
        ge=1,
        le=500
    )
    days_back: Optional[int] = Field(
        None,
        description="Number of days to look back (None for all history)",
        ge=1,
        le=365
    )

    @validator('wallet_address')
    def validate_wallet_address(cls, v):
        """
        Validate and normalize a wallet address string.

        Strips surrounding whitespace and ensures the resulting address is not empty.

        Parameters:
            v (str): Wallet address input to validate.

        Returns:
            str: The wallet address with surrounding whitespace removed.

        Raises:
            ValueError: If the wallet address is empty or contains only whitespace.
        """
        if not v or not v.strip():
            raise ValueError('Wallet address cannot be empty')
        return v.strip()


class WalletConfigRequest(BaseModel):
    """Request model for wallet configuration."""
    portfolio_id: int = Field(..., description="Portfolio ID")
    wallet_address: str = Field(..., description="Bitcoin wallet address to configure")

    @validator('wallet_address')
    def validate_wallet_address(cls, v):
        """
        Validate and normalize a wallet address string.

        Strips surrounding whitespace and ensures the resulting address is not empty.

        Parameters:
            v (str): Wallet address input to validate.

        Returns:
            str: The wallet address with surrounding whitespace removed.

        Raises:
            ValueError: If the wallet address is empty or contains only whitespace.
        """
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
    """
    Provide a database session for a request and ensure it is closed when the request completes.

    Returns:
        db (Session): A SQLAlchemy session connected to the application's database.
    """
    db = SyncSessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/sync/wallet", response_model=WalletSyncResponse)
async def sync_wallet(
    request: WalletSyncRequest,
    db: Session = Depends(get_db)
):
    """
    Manually trigger synchronization for a Bitcoin wallet and start a background task to fetch transactions.

    Parameters:
        request (WalletSyncRequest): Sync parameters including portfolio_id, wallet_address, max_transactions, and days_back.
        db (Session): Database session dependency.

    Returns:
        WalletSyncResponse: Status and metadata indicating the sync task was started,
                           with initial transaction counts and a timestamp.

    Raises:
        HTTPException: 404 if the portfolio does not exist;
                      400 if the provided wallet address does not match the portfolio;
                      500 on unexpected errors when starting the sync.
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

        # Start background sync task with configurable parameters
        task = sync_wallet_manually.delay(
            wallet_address=request.wallet_address,
            portfolio_id=request.portfolio_id,
            max_transactions=request.max_transactions,
            days_back=request.days_back
        )

        logger.info(
            f"Started manual sync task {task.id} for wallet {request.wallet_address} "
            f"(portfolio {request.portfolio_id}), max_transactions={request.max_transactions}, "
            f"days_back={request.days_back}"
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
    Configure or update the Bitcoin wallet address for a portfolio.

    Automatically triggers a full sync when a wallet address is configured for the first time.

    Parameters:
        request (WalletConfigRequest): Contains `portfolio_id` and the `wallet_address` to set.

    Returns:
        dict: Response with keys `status` ("success"), `message`, `portfolio_id`, `wallet_address`,
              `sync_task_started` (bool), and `timestamp` (UTC).
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

        # Check if this is a new wallet configuration
        is_new_wallet = portfolio.wallet_address is None
        wallet_address_changed = portfolio.wallet_address != request.wallet_address

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

        # Trigger automatic full sync if this is a new wallet or wallet address changed
        sync_task_started = False
        if is_new_wallet or wallet_address_changed:
            try:
                # Start background sync task with no limits (fetch all history)
                task = sync_wallet_manually.delay(
                    wallet_address=request.wallet_address,
                    portfolio_id=request.portfolio_id,
                    max_transactions=None,  # No limit - fetch all transactions
                    days_back=None           # No date limit - fetch complete history
                )

                logger.info(
                    f"Started automatic full sync task {task.id} for new wallet {request.wallet_address} "
                    f"(portfolio {request.portfolio_id})"
                )
                sync_task_started = True

            except Exception as e:
                logger.error(f"Failed to start automatic sync for wallet {request.wallet_address}: {e}")
                # Don't fail the wallet configuration, just log the error

        logger.info(
            f"Configured wallet address {request.wallet_address} for portfolio {request.portfolio_id}"
        )

        response = {
            "status": "success",
            "message": "Wallet address configured successfully",
            "portfolio_id": request.portfolio_id,
            "wallet_address": request.wallet_address,
            "sync_task_started": sync_task_started,
            "timestamp": datetime.utcnow()
        }

        if sync_task_started:
            response["message"] += ". Automatic full sync started."

        return response

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
    Fetches transactions for the given Bitcoin wallet for preview and does not persist them.

    Filters out transactions already present for the portfolio and returns the new unique
    transactions along with counts and a timestamp.

    Returns:
        WalletTransactionsResponse: Response containing the wallet_address, list of unique
                                  transactions, `count` of new transactions, `total_fetched`
                                  from the fetch result, `status`, `message`, and `timestamp`.

    Raises:
        HTTPException: 404 if the portfolio is not found.
        HTTPException: 400 if the blockchain fetch returns an error or no transactions.
        HTTPException: 503 if all blockchain APIs are unavailable.
        HTTPException: 500 for other unexpected errors.
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

        # Check for success: either status is 'success' or transactions are present
        if result.get('status') != 'success' and not result.get('transactions'):
            error_message = result.get('message', 'Unknown error') if isinstance(result, dict) else 'No transactions returned'
            raise HTTPException(
                status_code=400,
                detail=f"Failed to fetch transactions: {error_message}"
            )

        # Filter out existing transactions
        existing_hashes = blockchain_deduplication.get_portfolio_transaction_hashes(portfolio_id)
        unique_transactions = []
        duplicate_count = 0

        for tx in result.get('transactions', []):
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
    except BlockchainFetchError as e:
        logger.error(f"Blockchain fetch error: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"All blockchain APIs unavailable: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error fetching wallet transactions: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch wallet transactions: {str(e)}"
        )


@router.get("/status", response_model=BlockchainStatusResponse)
async def get_blockchain_status():
    """
    Report Blockchain.info API connectivity and deduplication cache statistics.

    Computes status based on Blockchain.info API reachability and includes cache statistics from
    the deduplication layer. If an internal error occurs while gathering results, returns a response
    indicating an error with empty api_results and cache_stats and an explanatory message.

    Returns:
        BlockchainStatusResponse: Object containing `status` ("error" or "success"),
                                 a human-readable `message`, `api_results` with a single entry
                                 for blockchain.info, `cache_stats` from the deduplication store,
                                 and a `timestamp`.
    """
    try:
        # Test API connection
        api_result = blockchain_fetcher.test_api_connection()

        # Get cache statistics
        cache_stats = blockchain_deduplication.get_cache_stats()

        # Determine overall status
        if api_result:
            status = "success"
            message = "Blockchain.info API is reachable"
            api_results = {"blockchain_info": True}
        else:
            status = "error"
            message = "Blockchain.info API is not reachable"
            api_results = {"blockchain_info": False}

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
            api_results={"blockchain_info": False},
            cache_stats={},
            timestamp=datetime.utcnow()
        )


@router.post("/test-connection")
async def test_blockchain_apis():
    """
    Start a background task to test connectivity to Blockchain.info API.

    Returns:
        result (dict): Dictionary with keys:
            - status (str): "started" when the task was scheduled.
            - message (str): Human-readable message about task start.
            - task_id (str): Identifier of the scheduled Celery task.
            - timestamp (datetime): UTC timestamp when the task was scheduled.

    Raises:
        HTTPException: If the background task cannot be started (HTTP 500).
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
    Retrieve blockchain transactions (exchange == "Bitcoin Blockchain") for the given portfolio, applying limit/offset paging.

    Returns:
        A dictionary containing:
        - portfolio_id (int): The requested portfolio ID.
        - wallet_address (str | None): The portfolio's configured wallet address.
        - transactions (list[TransactionResponse]): List of transactions converted to TransactionResponse.
        - total_count (int): Total number of matching blockchain transactions for the portfolio.
        - limit (int): The limit applied to this query.
        - offset (int): The offset applied to this query.
        - timestamp (datetime): UTC timestamp when the response was generated.
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
            "transactions": [TransactionResponse.model_validate(tx, from_attributes=True) for tx in transactions],
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
    Clear the deduplication cache for a given portfolio.

    Parameters:
        portfolio_id (int): ID of the portfolio whose deduplication cache should be cleared.

    Returns:
        dict: Result object containing `status` ("success"), `message`, `portfolio_id`, and `timestamp`.
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
    Retrieve per-day synchronization summaries of blockchain transactions for a portfolio over a recent period.

    Returns a dictionary containing the portfolio id, configured wallet address, a list of daily
    sync summaries (each with date, transaction_count, total_amount, and transaction_types map),
    the number of days with activity, total transactions found, the requested period in days,
    and a timestamp of the response.

    Parameters:
        portfolio_id (int): ID of the portfolio to query.
        days (int): Number of days to include in the history (1–365).

    Returns:
        dict: {
            "portfolio_id": int,
            "wallet_address": str | None,
            "sync_history": List[{
                "date": str,                    # ISO date (YYYY-MM-DD)
                "transaction_count": int,
                "total_amount": float,          # Sum of `total_amount` for that date
                "transaction_types": {str: int} # counts per transaction type
            }],
            "total_days": int,                 # number of days returned (length of sync_history)
            "total_transactions": int,         # total transactions across the period
            "period_days": int,                # requested `days` value
            "timestamp": datetime              # UTC timestamp when response was generated
        }

    Raises:
        HTTPException: 404 if the portfolio is not found; 500 if an unexpected error occurs.
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
