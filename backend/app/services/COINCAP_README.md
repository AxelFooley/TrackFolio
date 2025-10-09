# CoinCap API Service

This service provides a wrapper for the CoinCap cryptocurrency API with caching, error handling, and currency conversion.

## Overview

The CoinCap service (`coincap.py`) provides access to cryptocurrency price data from CoinCap API, following the established patterns in the TrackFolio codebase.

## Features

- **Symbol Mapping**: Maps common crypto symbols (BTC, ETH, etc.) to CoinCap asset IDs
- **Current Prices**: Fetches real-time cryptocurrency prices with currency conversion
- **Historical Data**: Retrieves historical price data for portfolio calculations
- **Redis Caching**: Intelligent caching with configurable TTL
- **Error Handling**: Comprehensive error handling with retry logic
- **Rate Limiting**: Built-in rate limiting to respect API limits
- **Currency Conversion**: Automatic USD to EUR conversion

## API Details

### Base URL
- `https://api.coincap.io/v2/`

### Authentication
- No API key required (free tier)
- Rate limited but more generous than CoinGecko

### Key Endpoints
- `GET /assets` - List all assets
- `GET /assets/{id}` - Get specific asset details
- `GET /assets/{id}/history` - Get historical price data

## Usage Examples

### Basic Usage

```python
from app.services.coincap import coincap_service

# Get current Bitcoin price in EUR
btc_price = coincap_service.get_current_price('BTC', 'eur')
print(f"BTC price: €{btc_price['price']}")

# Get historical Ethereum prices
from datetime import date, timedelta
end_date = date.today()
start_date = end_date - timedelta(days=30)

eth_prices = coincap_service.get_historical_prices('ETH', start_date, end_date, 'usd')
print(f"Retrieved {len(eth_prices)} price points")

# Map symbol to CoinCap ID
coincapec_id = coincap_service.map_symbol_to_coincec_id('ADA')
print(f"ADA CoinCap ID: {coincapec_id}")
```

### Integration with Price Fetcher

```python
from app.services.coincap import CoinCapService

# Create service instance
coincap = CoinCapService()

# Test connection
if coincap.test_connection():
    print("CoinCap API is accessible")

    # Get supported symbols
    assets = coincap.get_supported_symbols()
    print(f"Found {len(assets)} supported assets")
```

## Configuration

### Cache TTL Settings
- `CURRENT_PRICE_CACHE_TTL`: 300 seconds (5 minutes)
- `HISTORICAL_PRICE_CACHE_TTL`: 86400 seconds (24 hours)
- `SYMBOL_MAPPING_CACHE_TTL`: 3600 seconds (1 hour)

### Rate Limiting
- `RATE_LIMIT_DELAY`: 0.1 seconds between requests
- `MAX_RETRIES`: 3 attempts
- `REQUEST_TIMEOUT`: 30 seconds

## Data Structures

### Current Price Response
```python
{
    'symbol': 'BTC',
    'coincapec_id': 'bitcoin',
    'price': Decimal('50000.00'),
    'currency': 'EUR',
    'price_usd': Decimal('54347.83'),
    'market_cap_usd': Decimal('1050000000000'),
    'volume_24h_usd': Decimal('25000000000'),
    'change_percent_24h': Decimal('2.5'),
    'timestamp': datetime.datetime(2024, 1, 15, 10, 30),
    'source': 'coincap'
}
```

### Historical Price Response
```python
[
    {
        'date': datetime.date(2024, 1, 15),
        'symbol': 'BTC',
        'coincapec_id': 'bitcoin',
        'price': Decimal('50000.00'),
        'currency': 'EUR',
        'price_usd': Decimal('54347.83'),
        'timestamp': datetime.datetime(2024, 1, 15, 0, 0),
        'source': 'coincap'
    },
    # ... more data points
]
```

## Symbol Mappings

The service includes comprehensive symbol mappings for common cryptocurrencies:

| Symbol | CoinCap ID | Name |
|--------|------------|------|
| BTC | bitcoin | Bitcoin |
| ETH | ethereum | Ethereum |
| ADA | cardano | Cardano |
| SOL | solana | Solana |
| DOT | polkadot | Polkadot |
| MATIC | polygon | Polygon |
| ... | ... | ... |

Over 300+ symbol mappings are included for comprehensive coverage.

## Caching

### Redis Integration
- Uses the same Redis instance as the rest of the application
- Cache keys follow pattern: `coincap:{prefix}:{args}`
- Automatic cache invalidation based on TTL
- Graceful fallback when Redis is unavailable

### Cache Keys
- Symbol mapping: `coincap:symbol_mapping:{symbol}`
- Current price: `coincap:current_price:{symbol}:{currency}`
- Historical prices: `coincap:historical_prices:{symbol}:{start}:{end}:{currency}`

## Error Handling

### Retry Logic
- Exponential backoff: `delay = base_delay * (2 ** attempt)`
- Maximum 3 retries per request
- Detailed error logging

### Graceful Degradation
- Returns `None` for failed API calls
- Logs appropriate error messages
- Falls back to cached data when available
- Continues operation when Redis is unavailable

## Currency Conversion

### USD to EUR
- Attempts to use existing price fetcher FX rates
- Falls back to hardcoded rate (0.92) for development
- Extensible for additional currency pairs

### Supported Currencies
- `usd`: Default (native CoinCap currency)
- `eur`: Converted using FX rates

## Integration Points

### With Existing Services
- Inherits logging patterns from `price_fetcher.py`
- Uses same Redis configuration from `config.py`
- Follows async/sync patterns established in codebase
- Compatible with existing portfolio calculations

### Database Integration
- Can be used to populate `price_history` table
- Supports ISIN-based asset identification
- Compatible with existing transaction models

## Testing

### Unit Tests
```bash
# Run basic API tests
python3 test_coincap_simple.py

# Run full service tests (requires Redis)
python3 test_coincap_service.py
```

### Manual Testing
```python
# Test individual methods
coincap_service.test_connection()
coincap_service.map_symbol_to_coincec_id('BTC')
coincap_service.get_current_price('ETH', 'eur')
```

## Troubleshooting

### Common Issues

1. **API Connection Failed**
   - Check internet connectivity
   - Verify CoinCap API status
   - Check DNS resolution for `api.coincap.io`

2. **Redis Connection Failed**
   - Verify Redis is running
   - Check `redis_url` configuration
   - Service will continue without caching

3. **Symbol Not Found**
   - Check symbol spelling
   - Verify symbol is supported by CoinCap
   - Check symbol mapping table

4. **Currency Conversion Failed**
   - Verify price fetcher is working
   - Check FX rate availability
   - Fallback rate will be used

### Debug Logging
```python
import logging
logging.getLogger('app.services.coincap').setLevel(logging.DEBUG)
```

## Performance Considerations

### Optimization Tips
- Leverage Redis caching to reduce API calls
- Use batch operations where possible
- Monitor rate limit usage
- Cache symbol mappings aggressively

### Rate Limits
- CoinCap is more generous than CoinGecko
- Built-in rate limiting prevents abuse
- Cache TTLs optimize for portfolio use cases

## Future Enhancements

### Potential Improvements
1. **Additional Exchanges**: Support for more crypto exchanges
2. **Real-time Updates**: WebSocket integration for live prices
3. **Portfolio Integration**: Direct integration with portfolio calculations
4. **Alert System**: Price alerts and notifications
5. **Advanced Caching**: Cache warming and invalidation strategies

### API Expansion
- Support for additional time intervals
- More granular historical data
- Market depth and order book data
- On-chain metrics integration

## Dependencies

- `requests`: HTTP client library
- `redis`: Caching backend
- `pickle`: Serialization for Redis
- `decimal`: Precise financial calculations
- `datetime`: Date/time handling

## Security Considerations

- No API keys required (reduces credential exposure)
- HTTPS encryption for all API calls
- Input validation for all parameters
- Rate limiting prevents abuse
- Error messages don't expose sensitive information