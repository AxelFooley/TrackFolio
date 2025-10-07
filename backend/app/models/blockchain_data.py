"""
Blockchain data models for API responses and data structures.

Standardized models for Bitcoin, Ethereum, and other blockchain networks.
"""
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Union, Any
from pydantic import BaseModel, Field, validator
from enum import Enum

from app.models.crypto_paper import BlockchainNetwork


class TransactionStatus(str, Enum):
    """Transaction status enumeration."""
    CONFIRMED = "confirmed"
    PENDING = "pending"
    FAILED = "failed"
    UNKNOWN = "unknown"


class TransactionType(str, Enum):
    """Transaction type enumeration."""
    SENT = "sent"
    RECEIVED = "received"
    TRANSFER = "transfer"
    CONTRACT_CALL = "contract_call"
    CONTRACT_CREATION = "contract_creation"


class AddressType(str, Enum):
    """Address type enumeration."""
    P2PKH = "p2pkh"  # Legacy Bitcoin addresses (1...)
    P2SH = "p2sh"    # SegWit addresses (3...)
    BECH32 = "bech32"  # Native SegWit (bc1...)
    ERC20 = "erc20"  # Ethereum ERC-20 token
    ERC721 = "erc721"  # Ethereum NFT
    ETH = "eth"      # Ethereum native


class TokenInfo(BaseModel):
    """Token information model."""
    symbol: str = Field(..., description="Token symbol (e.g., USDT, USDC)")
    name: str = Field(..., description="Token full name")
    decimals: int = Field(..., description="Number of decimal places")
    contract_address: str = Field(..., description="Smart contract address")
    coingecko_id: Optional[str] = Field(None, description="CoinGecko ID for price data")
    logo_url: Optional[str] = Field(None, description="Token logo URL")


class GasInfo(BaseModel):
    """Gas information for Ethereum transactions."""
    gas_limit: int = Field(..., description="Gas limit for transaction")
    gas_used: Optional[int] = Field(None, description="Gas actually used")
    gas_price: Optional[Decimal] = Field(None, description="Gas price in Gwei")
    max_fee_per_gas: Optional[Decimal] = Field(None, description="EIP-1559 max fee")
    max_priority_fee_per_gas: Optional[Decimal] = Field(None, description="EIP-1559 priority fee")
    total_gas_cost: Optional[Decimal] = Field(None, description="Total gas cost in ETH")


class UTXO(BaseModel):
    """Unspent Transaction Output model for Bitcoin."""
    txid: str = Field(..., description="Transaction hash")
    vout: int = Field(..., description="Output index")
    value: int = Field(..., description="Value in satoshis")
    script_pubkey: str = Field(..., description="Script public key")
    address: str = Field(..., description="Address that can spend this UTXO")
    confirmations: int = Field(..., description="Number of confirmations")
    block_height: Optional[int] = Field(None, description="Block height")


class BlockchainTransaction(BaseModel):
    """Standardized blockchain transaction model."""
    tx_hash: str = Field(..., description="Transaction hash")
    block_hash: Optional[str] = Field(None, description="Block hash")
    block_number: Optional[int] = Field(None, description="Block number")
    block_timestamp: Optional[datetime] = Field(None, description="Block timestamp")
    transaction_type: TransactionType = Field(..., description="Type of transaction")
    status: TransactionStatus = Field(..., description="Transaction status")
    confirmations: int = Field(0, description="Number of confirmations")

    # Address information
    from_address: Optional[str] = Field(None, description="Sender address")
    to_address: Optional[str] = Field(None, description="Receiver address")
    contract_address: Optional[str] = Field(None, description="Smart contract address (if applicable)")

    # Value information
    value: Decimal = Field(..., description="Transaction value in native currency")
    value_usd: Optional[Decimal] = Field(None, description="Value in USD at time of transaction")
    fee: Optional[Decimal] = Field(None, description="Transaction fee")
    fee_usd: Optional[Decimal] = Field(None, description="Fee in USD")

    # Ethereum specific
    gas_info: Optional[GasInfo] = Field(None, description="Gas information (Ethereum only)")
    nonce: Optional[int] = Field(None, description="Transaction nonce (Ethereum only)")

    # Token information
    token_info: Optional[TokenInfo] = Field(None, description="Token information for token transfers")

    # Metadata
    network: BlockchainNetwork = Field(..., description="Blockchain network")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When this record was created")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="When this record was last updated")

    # Raw data for debugging
    raw_data: Optional[Dict[str, Any]] = Field(None, description="Raw API response data")

    @validator('value', 'fee', pre=True)
    def convert_to_decimal(cls, v):
        """Convert numeric values to Decimal."""
        if v is None:
            return None
        if isinstance(v, str):
            return Decimal(v)
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        return v

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: str(v)
        }


class AddressBalance(BaseModel):
    """Address balance information."""
    address: str = Field(..., description="Blockchain address")
    network: BlockchainNetwork = Field(..., description="Blockchain network")
    balance: Decimal = Field(..., description="Balance in native currency")
    balance_usd: Optional[Decimal] = Field(None, description="Balance in USD")

    # Token balances (for Ethereum/EVM chains)
    token_balances: List[Dict[str, Any]] = Field(default_factory=list, description="Token balances")

    # UTXO information (for Bitcoin)
    utxo_count: Optional[int] = Field(None, description="Number of UTXOs")
    unconfirmed_balance: Optional[Decimal] = Field(None, description="Unconfirmed balance")

    # Metadata
    last_updated: datetime = Field(default_factory=datetime.utcnow, description="When balance was last updated")
    address_type: Optional[AddressType] = Field(None, description="Type of address")
    is_valid: bool = Field(True, description="Whether address format is valid")

    @validator('balance', 'unconfirmed_balance', pre=True)
    def convert_to_decimal(cls, v):
        """Convert numeric values to Decimal."""
        if v is None:
            return None
        if isinstance(v, str):
            return Decimal(v)
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        return v

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: str(v)
        }


class AddressInfo(BaseModel):
    """Comprehensive address information."""
    address: str = Field(..., description="Blockchain address")
    network: BlockchainNetwork = Field(..., description="Blockchain network")
    address_type: AddressType = Field(..., description="Type of address")
    is_valid: bool = Field(True, description="Whether address format is valid")

    # Balance information
    current_balance: AddressBalance = Field(..., description="Current balance information")

    # Transaction summary
    total_transactions: int = Field(0, description="Total number of transactions")
    total_received: Decimal = Field(Decimal("0"), description="Total amount received")
    total_sent: Decimal = Field(Decimal("0"), description="Total amount sent")

    # Activity information
    first_tx_hash: Optional[str] = Field(None, description="First transaction hash")
    first_tx_timestamp: Optional[datetime] = Field(None, description="First transaction timestamp")
    last_tx_hash: Optional[str] = Field(None, description="Last transaction hash")
    last_tx_timestamp: Optional[datetime] = Field(None, description="Last transaction timestamp")

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When this record was created")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="When this record was last updated")

    @validator('total_received', 'total_sent', pre=True)
    def convert_to_decimal(cls, v):
        """Convert numeric values to Decimal."""
        if v is None:
            return None
        if isinstance(v, str):
            return Decimal(v)
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        return v

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: str(v)
        }


class BlockchainErrorResponse(BaseModel):
    """Error response from blockchain API."""
    error_code: str = Field(..., description="API error code")
    error_message: str = Field(..., description="Error message")
    provider: str = Field(..., description="API provider name")
    request_url: str = Field(..., description="Request URL that failed")
    request_params: Optional[Dict[str, Any]] = Field(None, description="Request parameters")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When error occurred")

    # Rate limiting information
    rate_limit_remaining: Optional[int] = Field(None, description="Remaining API calls")
    rate_limit_reset: Optional[datetime] = Field(None, description="When rate limit resets")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class NetworkStats(BaseModel):
    """Network statistics and health information."""
    network: BlockchainNetwork = Field(..., description="Blockchain network")
    provider: str = Field(..., description="Data provider")

    # Block information
    latest_block_number: int = Field(..., description="Latest block number")
    latest_block_hash: str = Field(..., description="Latest block hash")
    latest_block_timestamp: datetime = Field(..., description="Latest block timestamp")

    # Network health
    is_healthy: bool = Field(True, description="Whether network is responding normally")
    response_time_ms: int = Field(..., description="API response time in milliseconds")

    # Rate limiting
    rate_limit_remaining: Optional[int] = Field(None, description="Remaining API calls")
    rate_limit_limit: Optional[int] = Field(None, description="Total API calls allowed")

    # Metadata
    checked_at: datetime = Field(default_factory=datetime.utcnow, description="When stats were checked")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class BatchBalanceRequest(BaseModel):
    """Batch balance request model."""
    addresses: List[str] = Field(..., description="List of addresses to query")
    network: BlockchainNetwork = Field(..., description="Blockchain network")
    include_tokens: bool = Field(False, description="Include token balances for EVM chains")

    @validator('addresses')
    def validate_addresses(cls, v):
        """Validate address list."""
        if not v:
            raise ValueError("Address list cannot be empty")
        if len(v) > 100:  # Most APIs have batch limits
            raise ValueError("Cannot query more than 100 addresses at once")
        return v


class BatchBalanceResponse(BaseModel):
    """Batch balance response model."""
    network: BlockchainNetwork = Field(..., description="Blockchain network")
    provider: str = Field(..., description="Data provider")

    # Results
    balances: List[AddressBalance] = Field(..., description="Address balances")
    errors: List[BlockchainErrorResponse] = Field(default_factory=list, description="Errors for failed addresses")

    # Summary
    total_addresses: int = Field(..., description="Total addresses requested")
    successful_queries: int = Field(..., description="Successfully queried addresses")
    failed_queries: int = Field(..., description="Failed queries")

    # Performance
    response_time_ms: int = Field(..., description="Total response time in milliseconds")
    cached_results: int = Field(0, description="Number of results returned from cache")

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow, description="When response was created")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: str(v)
        }