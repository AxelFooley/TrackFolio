# TrackFolio API Documentation

Complete REST API reference for TrackFolio. The API is available at `http://localhost:8000/api` when running locally.

**Interactive API Documentation**: Visit `http://localhost:8000/docs` for Swagger UI with live testing

---

## Table of Contents

1. [Health & Status](#health--status)
2. [Transactions](#transactions)
3. [Portfolio](#portfolio)
4. [Assets](#assets)
5. [Prices](#prices)
6. [Benchmarks](#benchmarks)
7. [Cryptocurrency](#cryptocurrency)
8. [Blockchain](#blockchain)
9. [Common Response Formats](#common-response-formats)
10. [Error Handling](#error-handling)

---

## Health & Status

### Health Check

```http
GET /api/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-10-16T23:00:00Z"
}
```

---

## Transactions

### Import CSV

```http
POST /api/transactions/import
```

Upload a CSV file with transactions. Supported formats: standard CSV or Directa broker format.

**Request:**
```
Content-Type: multipart/form-data

file: <CSV file>
```

**CSV Format:**
```
date,asset,type,quantity,price,currency
2024-01-15,AAPL,BUY,10,150.50,USD
2024-01-16,GOOGL,BUY,5,140.25,USD
```

**Response:**
```json
{
  "status": "success",
  "imported": 2,
  "duplicates": 0,
  "errors": []
}
```

### Create Transaction

```http
POST /api/transactions/
```

Manually add a transaction.

**Request:**
```json
{
  "operation_date": "2024-01-15",
  "ticker": "AAPL",
  "quantity": 10,
  "price_per_share": 150.50,
  "amount_currency": "USD",
  "fees": 5.00
}
```

**Response:**
```json
{
  "id": 123,
  "operation_date": "2024-01-15",
  "ticker": "AAPL",
  "isin": "US0378331005",
  "quantity": 10,
  "price_per_share": 150.50,
  "amount_eur": 1387.94,
  "amount_currency": "USD",
  "currency": "USD",
  "fees": 5.00,
  "transaction_hash": "sha256hash...",
  "created_at": "2024-10-16T23:00:00Z"
}
```

### List Transactions

```http
GET /api/transactions/?skip=0&limit=50&ticker=AAPL
```

**Query Parameters:**
- `skip`: Number of records to skip (default: 0)
- `limit`: Number of records to return (default: 50)
- `ticker`: Filter by ticker symbol (optional)
- `type`: Filter by transaction type (optional)

**Response:**
```json
[
  {
    "id": 123,
    "operation_date": "2024-01-15",
    "ticker": "AAPL",
    "isin": "US0378331005",
    "quantity": 10,
    "price_per_share": 150.50,
    "amount_eur": 1387.94,
    "currency": "USD",
    "fees": 5.00
  }
]
```

### Get Transaction

```http
GET /api/transactions/{id}
```

**Response:**
```json
{
  "id": 123,
  "operation_date": "2024-01-15",
  "ticker": "AAPL",
  "isin": "US0378331005",
  "quantity": 10,
  "price_per_share": 150.50,
  "amount_eur": 1387.94,
  "currency": "USD",
  "fees": 5.00,
  "transaction_hash": "sha256hash..."
}
```

### Update Transaction

```http
PUT /api/transactions/{id}
```

**Request:**
```json
{
  "quantity": 15,
  "price_per_share": 155.00
}
```

**Response:** Updated transaction object

### Delete Transaction

```http
DELETE /api/transactions/{id}
```

**Response:**
```json
{
  "status": "success",
  "message": "Transaction deleted"
}
```

---

## Portfolio

### Portfolio Overview

```http
GET /api/portfolio/overview
```

Get comprehensive portfolio metrics.

**Response:**
```json
{
  "total_value": 45000.50,
  "total_cost_basis": 40000.00,
  "total_profit": 5000.50,
  "profit_percentage": 12.51,
  "annual_return_percentage": 8.75,
  "updated_at": "2024-10-16T23:00:00Z",
  "positions_count": 15,
  "benchmark_comparison": {
    "benchmark_ticker": "SPY",
    "benchmark_name": "S&P 500",
    "benchmark_return": 10.25,
    "outperformance": 2.26
  }
}
```

### Holdings

```http
GET /api/portfolio/holdings?sort_by=value
```

Get all current positions.

**Query Parameters:**
- `sort_by`: value, quantity, performance, allocation (default: value)

**Response:**
```json
[
  {
    "ticker": "AAPL",
    "isin": "US0378331005",
    "quantity": 50,
    "current_price": 150.50,
    "total_value": 7525.00,
    "average_cost": 145.00,
    "cost_basis": 7250.00,
    "profit": 275.00,
    "profit_percentage": 3.79,
    "allocation_percentage": 16.72,
    "todays_change_percentage": 1.25
  }
]
```

### Portfolio Performance

```http
GET /api/portfolio/performance?period=1M&metric=TWR
```

Get historical performance data.

**Query Parameters:**
- `period`: 1D, 1W, 1M, 3M, 6M, 1Y, YTD, ALL (default: 1M)
- `metric`: TWR, IRR, CAGR (default: TWR)

**Response:**
```json
{
  "period": "1M",
  "metric": "TWR",
  "value": 5.75,
  "start_date": "2024-09-16",
  "end_date": "2024-10-16",
  "datapoints": [
    {
      "date": "2024-09-16",
      "value": 42000.00,
      "return_percentage": 0.00
    },
    {
      "date": "2024-09-17",
      "value": 42250.00,
      "return_percentage": 0.59
    }
  ]
}
```

### Position Detail

```http
GET /api/portfolio/positions/{identifier}
```

Get details for a specific position. Identifier can be ticker or 12-char ISIN.

**Response:**
```json
{
  "ticker": "AAPL",
  "isin": "US0378331005",
  "quantity": 50,
  "average_cost": 145.00,
  "current_price": 150.50,
  "total_value": 7525.00,
  "cost_basis": 7250.00,
  "profit": 275.00,
  "profit_percentage": 3.79,
  "transactions_count": 5,
  "first_purchase_date": "2023-01-15",
  "latest_update": "2024-10-16T23:00:00Z",
  "price_history": [
    {
      "date": "2024-10-16",
      "open": 149.50,
      "high": 151.00,
      "low": 149.00,
      "close": 150.50,
      "volume": 50000000
    }
  ]
}
```

---

## Assets

### Asset Details

```http
GET /api/assets/{ticker}
```

Get information about an asset. Accepts ticker symbol or 12-char ISIN.

**Response:**
```json
{
  "ticker": "AAPL",
  "isin": "US0378331005",
  "name": "Apple Inc.",
  "asset_type": "STOCK",
  "sector": "Technology",
  "current_price": 150.50,
  "currency": "USD",
  "price_updated_at": "2024-10-16T23:00:00Z",
  "previous_close": 149.75,
  "day_change": 0.75,
  "day_change_percentage": 0.50
}
```

### Asset Transactions

```http
GET /api/assets/{ticker}/transactions?skip=0&limit=50
```

Get all transactions for an asset.

**Response:**
```json
[
  {
    "id": 123,
    "operation_date": "2024-01-15",
    "type": "BUY",
    "quantity": 10,
    "price_per_share": 150.50,
    "total": 1505.00,
    "fees": 5.00
  }
]
```

### Asset Price History

```http
GET /api/assets/{ticker}/prices?start_date=2024-01-01&end_date=2024-10-16
```

Get historical OHLCV data.

**Query Parameters:**
- `start_date`: Start date (YYYY-MM-DD)
- `end_date`: End date (YYYY-MM-DD)

**Response:**
```json
[
  {
    "date": "2024-10-16",
    "open": 149.50,
    "high": 151.00,
    "low": 149.00,
    "close": 150.50,
    "volume": 50000000,
    "source": "Yahoo Finance"
  }
]
```

---

## Prices

### Refresh Prices

```http
POST /api/prices/refresh
```

Manually update current prices.

**Request:**
```json
{
  "current_only": true,
  "tickers": ["AAPL", "GOOGL"]  // optional, refreshes all if omitted
}
```

**Response:**
```json
{
  "status": "success",
  "updated_count": 2,
  "timestamp": "2024-10-16T23:00:00Z"
}
```

### Ensure Coverage

```http
POST /api/prices/ensure-coverage
```

Ensure complete historical price coverage for all holdings.

**Response:**
```json
{
  "status": "success",
  "backfilled_count": 250,
  "timestamp": "2024-10-16T23:00:00Z"
}
```

### Last Update

```http
GET /api/prices/last-update
```

Get timestamp of last price update.

**Response:**
```json
{
  "last_update": "2024-10-16T23:00:00Z",
  "updated_assets": 150
}
```

### Real-Time Prices

```http
GET /api/prices/realtime?tickers=AAPL,GOOGL,BTC
```

Get current prices for multiple symbols.

**Response:**
```json
{
  "AAPL": {
    "price": 150.50,
    "currency": "USD",
    "change": 0.75,
    "change_percent": 0.50,
    "updated_at": "2024-10-16T23:00:00Z"
  },
  "GOOGL": {
    "price": 140.25,
    "currency": "USD",
    "change": -1.50,
    "change_percent": -1.06,
    "updated_at": "2024-10-16T23:00:00Z"
  }
}
```

---

## Benchmarks

### Get Active Benchmark

```http
GET /api/benchmark
```

**Response:**
```json
{
  "id": 1,
  "ticker": "SPY",
  "description": "S&P 500",
  "start_date": "2020-01-01"
}
```

### Set Benchmark

```http
POST /api/benchmark
```

**Request:**
```json
{
  "ticker": "SPY",
  "description": "S&P 500"
}
```

**Response:**
```json
{
  "id": 1,
  "ticker": "SPY",
  "description": "S&P 500",
  "created_at": "2024-10-16T23:00:00Z"
}
```

---

## Cryptocurrency

### List Crypto Portfolios

```http
GET /api/crypto/portfolios
```

**Response:**
```json
[
  {
    "id": 1,
    "name": "Main Portfolio",
    "base_currency": "USD",
    "total_value": 25000.50,
    "total_cost_basis": 20000.00,
    "profit": 5000.50,
    "wallet_address": "1A1z7agoat3oWVoVQVe4FDvQA9vxL5b4s",
    "wallet_last_sync": "2024-10-16T22:30:00Z",
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

### Create Crypto Portfolio

```http
POST /api/crypto/portfolios
```

**Request:**
```json
{
  "name": "Main Portfolio",
  "base_currency": "USD",
  "wallet_address": "1A1z7agoat3oWVoVQVe4FDvQA9vxL5b4s"
}
```

**Response:**
```json
{
  "id": 1,
  "name": "Main Portfolio",
  "base_currency": "USD",
  "wallet_address": "1A1z7agoat3oWVoVQVe4FDvQA9vxL5b4s",
  "created_at": "2024-10-16T23:00:00Z"
}
```

### Get Crypto Portfolio

```http
GET /api/crypto/portfolios/{id}
```

### Update Crypto Portfolio

```http
PUT /api/crypto/portfolios/{id}
```

**Request:**
```json
{
  "name": "Updated Name",
  "wallet_address": "3J98t1WpEZ73CNmYviecrnyiWrnqRhWNLy"
}
```

### Delete Crypto Portfolio

```http
DELETE /api/crypto/portfolios/{id}
```

### List Holdings

```http
GET /api/crypto/portfolios/{id}/holdings
```

**Response:**
```json
[
  {
    "symbol": "BTC",
    "name": "Bitcoin",
    "quantity": 0.5,
    "current_price": 42000.00,
    "total_value": 21000.00,
    "average_cost": 40000.00,
    "cost_basis": 20000.00,
    "profit": 1000.00,
    "profit_percentage": 5.00
  }
]
```

### Get Holdings by Symbol

```http
GET /api/crypto/portfolios/{id}/holdings/{symbol}
```

### Add Transaction

```http
POST /api/crypto/portfolios/{id}/transactions
```

**Request:**
```json
{
  "type": "BUY",
  "symbol": "BTC",
  "quantity": 0.1,
  "price": 42000.00,
  "date": "2024-01-15",
  "exchange": "Kraken"
}
```

### List Transactions

```http
GET /api/crypto/portfolios/{id}/transactions?skip=0&limit=50
```

### Update Transaction

```http
PUT /api/crypto/portfolios/{id}/transactions/{tx_id}
```

### Delete Transaction

```http
DELETE /api/crypto/portfolios/{id}/transactions/{tx_id}
```

### Portfolio Performance

```http
GET /api/crypto/portfolios/{id}/performance?period=1M
```

### Portfolio Metrics

```http
GET /api/crypto/portfolios/{id}/metrics
```

**Response:**
```json
{
  "total_value": 25000.50,
  "total_cost_basis": 20000.00,
  "total_profit": 5000.50,
  "profit_percentage": 25.00,
  "return_percentage": 12.50,
  "best_performer": "BTC",
  "worst_performer": "ETH"
}
```

### Crypto Price History

```http
GET /api/crypto/prices/{symbol}/history?start_date=2024-01-01&end_date=2024-10-16
```

**Response:**
```json
[
  {
    "date": "2024-10-16",
    "price": 42000.00,
    "market_cap": 820000000000,
    "volume": 25000000000
  }
]
```

### Search Crypto

```http
GET /api/crypto/search?query=bitcoin
```

**Response:**
```json
[
  {
    "id": "bitcoin",
    "symbol": "BTC",
    "name": "Bitcoin",
    "image": "https://..."
  }
]
```

---

## Blockchain

### Sync Wallet (Manual)

```http
POST /api/blockchain/sync/wallet
```

Manually trigger wallet synchronization.

**Request:**
```json
{
  "portfolio_id": 1,
  "address": "1A1z7agoat3oWVoVQVe4FDvQA9vxL5b4s"
}
```

**Response:**
```json
{
  "status": "success",
  "address": "1A1z7agoat3oWVoVQVe4FDvQA9vxL5b4s",
  "transactions_synced": 15,
  "last_sync": "2024-10-16T23:00:00Z"
}
```

### Configure Wallet

```http
POST /api/blockchain/config/wallet
```

Configure wallet address for a portfolio.

**Request:**
```json
{
  "portfolio_id": 1,
  "address": "1A1z7agoat3oWVoVQVe4FDvQA9vxL5b4s"
}
```

**Response:**
```json
{
  "portfolio_id": 1,
  "address": "1A1z7agoat3oWVoVQVe4FDvQA9vxL5b4s",
  "configured_at": "2024-10-16T23:00:00Z"
}
```

### Get Wallet Transactions

```http
GET /api/blockchain/wallet/{address}/transactions?limit=50
```

Preview wallet transactions without importing.

**Response:**
```json
[
  {
    "txid": "abc123def456...",
    "date": "2024-10-16",
    "type": "IN",
    "amount": 0.5,
    "confirmations": 6
  }
]
```

### Blockchain Status

```http
GET /api/blockchain/status
```

Get blockchain service status.

**Response:**
```json
{
  "status": "operational",
  "last_sync": "2024-10-16T22:30:00Z",
  "synced_wallets": 3,
  "provider": "blockstream",
  "rate_limit_remaining": 95
}
```

### Get Wallet Sync Status

```http
GET /api/crypto/portfolios/{id}/wallet-sync-status
```

**Response:**
```json
{
  "portfolio_id": 1,
  "address": "1A1z7agoat3oWVoVQVe4FDvQA9vxL5b4s",
  "is_syncing": false,
  "last_sync": "2024-10-16T22:30:00Z",
  "transactions_count": 42,
  "balance": 0.5,
  "next_sync_in": 1800  // seconds
}
```

---

## Common Response Formats

### Success Response

```json
{
  "status": "success",
  "data": {}
}
```

### Paginated Response

```json
{
  "data": [],
  "pagination": {
    "skip": 0,
    "limit": 50,
    "total": 150
  }
}
```

---

## Error Handling

### Error Response

```json
{
  "detail": "Error message describing what went wrong"
}
```

### Common HTTP Status Codes

- `200 OK` - Successful request
- `201 Created` - Resource created successfully
- `400 Bad Request` - Invalid request parameters
- `404 Not Found` - Resource not found
- `409 Conflict` - Duplicate transaction or conflict
- `422 Unprocessable Entity` - Validation error
- `500 Internal Server Error` - Server error

### Validation Errors

```json
{
  "detail": [
    {
      "loc": ["body", "quantity"],
      "msg": "ensure this value is greater than 0",
      "type": "value_error.number.not_gt"
    }
  ]
}
```

---

## Rate Limiting

API endpoints are rate limited to **100 requests per minute** per client.

Rate limit information is included in response headers:
- `X-RateLimit-Limit`: 100
- `X-RateLimit-Remaining`: 99
- `X-RateLimit-Reset`: Unix timestamp

---

## Authentication

Currently, TrackFolio is designed for **single-user local deployment** and does **not require authentication**.

For internet deployment, you should add authentication at the reverse proxy level (nginx, Traefik, etc.) or implement API key authentication.

---

## Example Usage

### Python (requests)

```python
import requests
import json

BASE_URL = "http://localhost:8000/api"

# Get portfolio overview
response = requests.get(f"{BASE_URL}/portfolio/overview")
portfolio = response.json()
print(f"Total value: ${portfolio['total_value']}")

# Get holdings
holdings = requests.get(f"{BASE_URL}/portfolio/holdings").json()
for holding in holdings:
    print(f"{holding['ticker']}: {holding['quantity']} @ ${holding['current_price']}")

# Import transactions
with open("transactions.csv", "rb") as f:
    response = requests.post(
        f"{BASE_URL}/transactions/import",
        files={"file": f}
    )
    print(response.json())
```

### JavaScript (fetch)

```javascript
const BASE_URL = "http://localhost:8000/api";

// Get portfolio overview
const portfolio = await fetch(`${BASE_URL}/portfolio/overview`)
  .then(r => r.json());
console.log(`Total value: $${portfolio.total_value}`);

// Get holdings
const holdings = await fetch(`${BASE_URL}/portfolio/holdings`)
  .then(r => r.json());
holdings.forEach(h => {
  console.log(`${h.ticker}: ${h.quantity} @ $${h.current_price}`);
});

// Import transactions
const formData = new FormData();
formData.append("file", fileInput.files[0]);
const result = await fetch(`${BASE_URL}/transactions/import`, {
  method: "POST",
  body: formData
}).then(r => r.json());
console.log(result);
```

### cURL

```bash
# Get portfolio overview
curl http://localhost:8000/api/portfolio/overview

# Get holdings
curl http://localhost:8000/api/portfolio/holdings

# Get specific asset
curl http://localhost:8000/api/assets/AAPL

# Import transactions
curl -X POST -F "file=@transactions.csv" http://localhost:8000/api/transactions/import
```

---

## Webhooks & Real-Time Updates

Currently, TrackFolio does not support webhooks. For real-time updates, poll the relevant endpoints or check back soon for WebSocket support.

Recommended polling intervals:
- Portfolio overview: 5 minutes
- Real-time prices: 1-5 minutes
- Holdings: 5-30 minutes
- Blockchain wallet sync: 30 minutes (automatic)

---

## OpenAPI/Swagger

Full OpenAPI specification is available at: `http://localhost:8000/openapi.json`

Interactive Swagger UI: `http://localhost:8000/docs`

ReDoc documentation: `http://localhost:8000/redoc`
