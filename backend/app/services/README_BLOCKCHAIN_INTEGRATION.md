# Blockchain Integration Services

This document provides a comprehensive overview of the blockchain integration services implemented for Phase 2.1 of the wallet integration system.

## Overview

The blockchain integration services provide unified, multi-chain support for Bitcoin and Ethereum/EVM-compatible networks with comprehensive error handling, caching, and rate limiting.

## Architecture

### Core Components

1. **API Manager** (`api_manager.py`)
   - Centralized rate limiting and caching
   - Provider fallback mechanisms
   - Redis-based caching
   - Health monitoring

2. **Blockchain Service Base** (`blockchain_service.py`)
   - Abstract base class for all blockchain integrations
   - Factory pattern for service instantiation
   - Unified interface across networks

3. **Network-Specific Services**
   - **Bitcoin Service** (`bitcoin_integration.py`)
   - **Ethereum/EVM Service** (`ethereum_integration.py`)

4. **Data Models** (`blockchain_data.py`)
   - Standardized response models
   - Pydantic-based validation
   - Type safety and serialization

5. **Error Handling** (`blockchain_error_handler.py`)
   - Comprehensive error classification
   - Centralized logging and metrics
   - Health monitoring

## Supported Networks

### Bitcoin
- **Network**: Bitcoin mainnet
- **Providers**: blockchain.com, blockcypher.com, blockstream.info (fallback)
- **Features**: Balance queries, transaction history, UTXO management, address validation
- **Address Types**: P2PKH, P2SH, Bech32

### Ethereum/EVM Networks
- **Ethereum**: ETH transactions, ERC-20 tokens
- **Polygon**: MATIC transactions, Polygon tokens
- **BSC**: BNB transactions, BEP-20 tokens
- **Arbitrum**: ETH transactions, Arbitrum tokens
- **Optimism**: ETH transactions, Optimism tokens

**Features**:
- Balance queries (native and tokens)
- Transaction details
- Gas price estimation
- Smart contract interactions
- Address validation

## Configuration

### Environment Variables

```bash
# Bitcoin API Keys
BLOCKCHAIN_API_KEY=""              # blockchain.com API key
BLOCKCYPHER_API_KEY=""             # blockcypher.com API key
BITCOIN_RATE_LIMIT=30              # API calls per minute

# Ethereum/EVM API Keys
ALCHEMY_API_KEY=""                 # Alchemy API key (primary)
INFURA_PROJECT_ID=""               # Infura Project ID (fallback)
ANKR_API_KEY=""                    # Ankr API key (fallback)
ETHEREUM_RATE_LIMIT=60             # API calls per minute

# Network RPC URLs (auto-configured if API keys provided)
BITCOIN_RPC_URL="https://blockstream.info/api"
ETHEREUM_RPC_URL=""
POLYGON_RPC_URL=""
BSC_RPC_URL=""
ARBITRUM_RPC_URL=""
OPTIMISM_RPC_URL=""

# Caching
BLOCKCHAIN_CACHE_TTL_SECONDS=300   # 5 minutes for balances
BLOCKCHAIN_TX_CACHE_TTL_SECONDS=3600 # 1 hour for transactions

# Rate Limits (per network)
BITCOIN_RATE_PER_MINUTE=30
ETHEREUM_RATE_PER_MINUTE=60
POLYGON_RATE_PER_MINUTE=60
BSC_RATE_PER_MINUTE=60
ARBITRUM_RATE_PER_MINUTE=60
OPTIMISM_RATE_PER_MINUTE=60
```

## Usage Examples

### Basic Usage

```python
from app.services.blockchain_service import blockchain_service
from app.models.crypto_paper import BlockchainNetwork

# Initialize services
await blockchain_service.initialize()

# Bitcoin balance query
balance = await blockchain_service.get_balance(
    address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
    network=BlockchainNetwork.BITCOIN
)

# Ethereum balance with tokens
eth_balance = await blockchain_service.get_balance(
    address="0x742d35Cc6634C0532925a3b8D4C9db96C4b4Db45",
    network=BlockchainNetwork.ETHEREUM,
    include_tokens=True
)

# Cleanup
await blockchain_service.cleanup()
```

### Batch Operations

```python
from app.models.blockchain_data import BatchBalanceRequest

# Bitcoin batch query
bitcoin_request = BatchBalanceRequest(
    addresses=["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "..."],
    network=BlockchainNetwork.BITCOIN
)

result = await blockchain_service.get_batch_balances(bitcoin_request)
print(f"Successful: {result.successful_queries}/{result.total_addresses}")
```

### Direct Service Usage

```python
from app.services.bitcoin_integration import BitcoinService
from app.services.ethereum_integration import EthereumService

# Bitcoin service
bitcoin_service = BitcoinService()
balance = await bitcoin_service.get_balance("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")

# Ethereum service
ethereum_service = EthereumService(BlockchainNetwork.ETHEREUM)
gas_price = await ethereum_service.get_gas_price()
```

## API Endpoints

The blockchain services provide the following capabilities:

### Address Operations
- **validate_address()**: Validate address format and type
- **get_balance()**: Get native currency balance
- **get_balance_with_tokens()**: Get balance with ERC-20 tokens (EVM only)
- **get_address_info()**: Get comprehensive address information

### Transaction Operations
- **get_transactions()**: Get transaction history for an address
- **get_transaction()**: Get transaction details by hash
- **sync_address()**: Sync address for new transactions

### Network Operations
- **get_network_stats()**: Get network statistics and health
- **health_check()**: Perform health check on providers
- **clear_cache()**: Clear blockchain cache

## Error Handling

The services include comprehensive error handling:

```python
from app.services.blockchain_error_handler import handle_blockchain_error

try:
    balance = await blockchain_service.get_balance(address, network)
except Exception as e:
    error = await handle_blockchain_error(
        error=e,
        network=network,
        address=address
    )
    # Handle error appropriately
```

### Error Categories
- **NETWORK**: Connection and network issues
- **API_ERROR**: Provider API errors
- **VALIDATION**: Invalid input data
- **RATE_LIMIT**: API rate limiting
- **TIMEOUT**: Request timeouts
- **AUTHENTICATION**: Authentication failures
- **PARSING**: Response parsing errors
- **CACHE**: Cache-related errors

## Caching Strategy

### Cache Types
1. **Balance Cache**: 5-minute TTL for address balances
2. **Transaction Cache**: 1-hour TTL for transaction data
3. **Network Stats Cache**: 1-minute TTL for network statistics

### Cache Keys
```
blockchain:{network}:{endpoint}:{params_hash}
```

### Cache Invalidation
- Manual cache clearing available
- Automatic TTL-based expiration
- Network-specific cache clearing

## Rate Limiting

### Implementation
- Token bucket algorithm per provider
- Configurable limits per network
- Automatic delay when limits reached
- Provider rotation on rate limit errors

### Default Limits
- **Bitcoin**: 30 requests/minute
- **Ethereum/EVM**: 60 requests/minute per network

## Testing

### Comprehensive Tests
```bash
# Run full test suite
python backend/app/services/blockchain_tests.py

# Run integration demo
python backend/app/services/blockchain_integration_demo.py
```

### Test Coverage
- Address validation for all networks
- Balance queries
- Batch operations
- Error handling
- Caching performance
- Health monitoring
- Provider fallbacks

## Performance Optimization

### Techniques
1. **Batch Operations**: Parallel processing of multiple requests
2. **Caching**: Redis-based caching with TTL
3. **Connection Pooling**: HTTP connection reuse
4. **Provider Fallbacks**: Automatic failover to backup providers
5. **Rate Limiting**: Intelligent throttling to avoid API limits

### Metrics
- Response time tracking
- Cache hit/miss ratios
- Error rate monitoring
- Provider health scoring

## Security Considerations

### API Key Management
- API keys stored in environment variables
- Key rotation support
- Provider-specific authentication

### Data Protection
- No private key handling (read-only operations)
- Input validation and sanitization
- Rate limiting to prevent abuse

## Integration with Existing System

### Wallet Integration
- Ready for integration with `WalletConnection` and `WalletAddress` models
- Supports multiple wallet types per user
- Transaction history syncing

### Price Integration
- Integrates with existing `PriceFetcher` service
- Support for USD/EUR conversions
- Real-time price updates

### Database Integration
- Ready for storing transaction data
- Sync status tracking
- Audit logging

## Monitoring and Observability

### Logging
- Structured logging with correlation IDs
- Error categorization and tracking
- Performance metrics logging

### Health Checks
- Provider health monitoring
- Network connectivity checks
- Cache health verification

### Metrics
- Error rates by category and provider
- Response time distributions
- Cache performance metrics
- Success/failure ratios

## Future Enhancements

### Planned Features
1. **WebSocket Support**: Real-time transaction monitoring
2. **Additional Networks**: Solana, Avalanche, etc.
3. **DeFi Integration**: Yield farming, liquidity pools
4. **NFT Support**: ERC-721 and ERC-1155 token tracking
5. **Advanced Analytics**: Portfolio performance, P&L calculations

### Scalability Improvements
1. **Horizontal Scaling**: Multiple service instances
2. **Load Balancing**: Intelligent provider selection
3. **Advanced Caching**: Multi-layer caching strategy
4. **Background Sync**: Celery-based transaction syncing

## Troubleshooting

### Common Issues

1. **API Key Errors**
   - Verify environment variables are set
   - Check API key permissions and quotas
   - Validate network configurations

2. **Rate Limiting**
   - Check rate limit configurations
   - Monitor API usage patterns
   - Consider provider upgrades

3. **Cache Issues**
   - Verify Redis connectivity
   - Check cache TTL settings
   - Clear cache if stale data

4. **Network Connectivity**
   - Test provider endpoints
   - Check firewall rules
   - Verify DNS resolution

### Debug Mode
Enable debug logging for detailed troubleshooting:

```python
import logging
logging.getLogger("app.services").setLevel(logging.DEBUG)
```

## Conclusion

The blockchain integration services provide a robust, scalable foundation for multi-chain cryptocurrency portfolio tracking. The implementation prioritizes reliability, performance, and ease of use while maintaining flexibility for future enhancements.

The services are production-ready and include comprehensive testing, error handling, and monitoring capabilities. They can be easily extended to support additional networks and features as the platform grows.