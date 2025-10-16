# TrackFolio Features

Comprehensive documentation of TrackFolio's capabilities and features.

---

## Table of Contents

1. [Portfolio Management](#portfolio-management)
2. [Performance Calculations](#performance-calculations)
3. [Cryptocurrency Support](#cryptocurrency-support)
4. [Blockchain Wallet Sync](#blockchain-wallet-sync)
5. [Stock Split Detection](#stock-split-detection)
6. [Multi-Currency Support](#multi-currency-support)
7. [Data Import](#data-import)
8. [Automated Background Jobs](#automated-background-jobs)
9. [Benchmarking](#benchmarking)

---

## Portfolio Management

### Overview

TrackFolio provides comprehensive portfolio tracking with support for:
- **Stocks** (equities from global exchanges)
- **ETFs** (Exchange-Traded Funds)
- **Bonds** (fixed income securities)
- **Cryptocurrencies** (5000+ supported)

### ISIN-Based Architecture

All securities are identified using the **International Securities Identification Number (ISIN)**:
- **12-character standard identifier** (letter-number-number combination)
- Unique globally for any security
- Examples:
  - Apple: `US0378331005`
  - BMW: `DE0005140008`
  - Tesla: `US88160R1014`

**Benefits:**
- Handles ticker changes (company renames, mergers)
- Works across different markets and currencies
- Prevents duplicate entries for same security
- International compatibility

### Transaction Management

**Transaction Types:**
- **BUY**: Purchase of securities
- **SELL**: Sale of securities
- **DIVIDEND**: Dividend payments
- **FEE**: Trading fees, account fees, etc.

**Transaction Fields:**
- Operation date (when transaction occurred)
- Value date (settlement date, for currency conversion)
- Ticker symbol
- ISIN (auto-fetched)
- Quantity
- Price per share/unit
- Amount in original currency
- Currency (EUR, USD, etc.)
- Fees

**Deduplication:**
- Automatic duplicate detection using SHA256 hash
- Prevents re-importing same transaction twice
- Handles: date, ticker, quantity, price, fees, order reference

### Holdings Management

**Position Aggregation:**
- All transactions for a security are aggregated
- Average cost calculated automatically
- Position size updated in real-time
- Holdings categorized by asset type

**Allocation Tracking:**
- Percentage of total portfolio value
- Sector allocation (when sector data available)
- Currency allocation
- Asset type breakdown

### Cost Basis Calculation

**Average Cost Method:**
- Sum of all purchase amounts divided by total shares
- Updated with each new purchase
- Excludes dividends and fees from cost basis
- Used for profit/loss calculation

**Example:**
```
Purchase 1: 10 shares @ $100 = $1,000
Purchase 2: 5 shares @ $110 = $550
Average cost: $1,550 / 15 shares = $103.33 per share

If current price is $120:
Total value: 15 × $120 = $1,800
Cost basis: 15 × $103.33 = $1,549.95
Profit: $250.05
Profit %: 16.13%
```

---

## Performance Calculations

### Time-Weighted Return (TWR)

**Purpose:** Fair performance comparison independent of cash flows

**When to Use:**
- Comparing portfolio performance to benchmarks
- Evaluating investment manager performance
- Comparing portfolios with different contribution schedules

**Calculation:**
1. Divide portfolio history into periods separated by cash flows
2. Calculate return for each period
3. Geometrically link all period returns

**Formula:**
```
TWR = [(1 + R₁) × (1 + R₂) × ... × (1 + Rₙ)] - 1
```

**Example:**
```
Start value: $10,000
After 6 months: $11,000 (10% return)
Add contribution: +$5,000 (portfolio now $16,000)
After 1 year: $17,600

R₁ = (11,000 - 10,000) / 10,000 = 0.10 (10%)
R₂ = (17,600 - 16,000) / 16,000 = 0.10 (10%)
TWR = (1.10 × 1.10) - 1 = 0.21 = 21%
```

### Internal Rate of Return (IRR)

**Purpose:** Personal return accounting for timing and size of cash flows

**When to Use:**
- Personal portfolio evaluation
- Understanding true returns including deposits/withdrawals
- Comparing returns with specific contribution patterns

**Calculation:**
- Discount rate where Net Present Value (NPV) of all cash flows = 0
- Accounts for exact timing and amount of each cash flow
- Computed using Newton-Raphson iteration method

**Example:**
```
Initial investment: -$10,000 (today)
Year 1 value: +$11,000 (received)
IRR = rate where NPV = 0

Using IRR formula: -10,000 + 11,000/(1+r) = 0
Solving: r = 0.10 = 10%
```

### Return Metrics

**Daily Return:**
```
Daily Return % = ((Closing Value - Opening Value) / Opening Value) × 100
```

**Period Return:**
```
Period Return % = ((Ending Value - Starting Value + Dividends) / Starting Value) × 100
```

**Annualized Return (CAGR):**
```
CAGR = (Ending Value / Starting Value)^(1/years) - 1
```

### Metric Caching

For performance optimization:
- **Calculation Schedule**: Daily at 23:15 CET
- **Cache TTL**: 24 hours
- **Storage**: PostgreSQL JSON field
- **Includes**: IRR, TWR, portfolio returns, individual position metrics

---

## Cryptocurrency Support

### Crypto Portfolio System

**Separate from Traditional Portfolio:**
- Independent management from stocks/ETFs/bonds
- Dedicated crypto holdings tracking
- Separate performance calculations
- Multi-portfolio support (multiple crypto portfolios)

**Creation:**
```bash
POST /api/crypto/portfolios
{
  "name": "Main Crypto Holdings",
  "base_currency": "USD",
  "wallet_address": "1A1z7agoat3oWVoVQVe4FDvQA9vxL5b4s"  // optional
}
```

### Supported Assets

**Bitcoin & Ethereum:**
- BTC (Bitcoin)
- ETH (Ethereum)

**5000+ Cryptocurrencies:**
- All cryptocurrencies listed on CoinGecko API
- Complete symbol, name, and metadata
- Real-time and historical pricing

**Search Function:**
```bash
GET /api/crypto/search?query=bitcoin
```

Returns: symbol, name, image, market cap, volume

### Transaction Types

**Transfer Operations:**
- **BUY**: Purchase on exchange
- **SELL**: Sale on exchange
- **TRANSFER_IN**: Incoming transfer (wallet to wallet, mining, etc.)
- **TRANSFER_OUT**: Outgoing transfer (withdrawal, gifts, etc.)

**Example:**
```json
{
  "type": "BUY",
  "symbol": "BTC",
  "quantity": 0.5,
  "price": 42000.00,
  "date": "2024-01-15",
  "exchange": "Kraken"
}
```

### High-Precision Calculations

**8-Decimal Precision:**
- Handles fractional Bitcoin and satoshis
- Example: 0.00000001 BTC (1 satoshi)
- Uses PostgreSQL `DECIMAL` type for accuracy
- Prevents floating-point rounding errors

### Holdings Calculation

**From Transactions:**
1. Sum all BUY and TRANSFER_IN quantities
2. Subtract all SELL and TRANSFER_OUT quantities
3. Calculate cost basis from purchase prices
4. Apply current market price for valuation

**Cost Basis for Crypto:**
- Average cost of all purchases (including fees)
- Used for P&L calculation
- Important for tax purposes

### Performance Metrics

**Per Portfolio:**
- Total value (current market price × quantity)
- Total cost basis (sum of purchases)
- Unrealized profit/loss
- Return percentage
- Best and worst performing assets

**Automatic Calculation:**
- Scheduled at 23:15 CET daily
- Real-time calculation on-demand via API
- Cached for 24 hours

---

## Blockchain Wallet Sync

### Feature Overview

**Automatic Bitcoin Wallet Tracking:**
- Monitor Bitcoin addresses for incoming/outgoing transactions
- Auto-import transactions into crypto portfolio
- Track wallet balance changes
- Sync every 30 minutes automatically

### Supported Address Formats

**P2PKH (Pay to Public Key Hash):**
- Legacy format (starts with `1`)
- Example: `1A1z7agoat3oWVoVQVe4FDvQA9vxL5b4s`
- Most compatible

**P2SH (Pay to Script Hash):**
- Multisig and nested segwit (starts with `3`)
- Example: `3J98t1WpEZ73CNmYviecrnyiWrnqRhWNLy`

**Bech32 (Segwit v0):**
- Native segwit (starts with `bc1`)
- Example: `bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq`
- Most efficient

### Data Providers

**Primary Provider: Blockstream API**
- Free, reliable, well-maintained
- No API key required
- Rate limit: ~1 request/second

**Fallback Providers:**
- Blockchain.com API
- BlockCypher API
- Automatic fallback on primary provider failure

### Configuration

**Setup:**
1. Go to Crypto Portfolio > Settings
2. Enter Bitcoin address (P2PKH, P2SH, or Bech32)
3. Save configuration
4. First sync triggers automatically

**Manual Sync:**
```bash
POST /api/blockchain/sync/wallet
{
  "portfolio_id": 1,
  "address": "1A1z7agoat3oWVoVQVe4FDvQA9vxL5b4s"
}
```

### Automatic Sync

**Schedule:** Every 30 minutes

**Process:**
1. Fetch transactions from blockchain
2. Deduplicate against existing transactions
3. Auto-import new transactions as TRANSFER_IN/TRANSFER_OUT
4. Update portfolio holdings
5. Recalculate metrics

**Performance:**
- ~30 seconds for wallet with 100+ transactions
- Background processing (doesn't block UI)
- Logged for debugging

### Deduplication

**Redis-Based Caching:**
- Transaction hash cached to prevent re-import
- TTL: Configurable (default 7 days)
- Handles blockchain reorgs gracefully

**Duplicate Detection:**
- By transaction TXID (unique identifier)
- By date and amount
- Prevents duplicate entries

### Sync Status

**View Status:**
```bash
GET /api/crypto/portfolios/{id}/wallet-sync-status
```

**Returns:**
- Is currently syncing
- Last sync timestamp
- Transaction count
- Wallet balance
- Next sync countdown

---

## Stock Split Detection

### Automatic Detection

TrackFolio automatically detects stock splits and adjusts positions accordingly.

### How It Works

**Detection Method:**
1. Monitor for large quantity changes without corresponding price changes
2. Query Yahoo Finance for stock split history
3. Identify split date and split ratio
4. Update position quantities and prices accordingly

**Example:**
```
Before split:
- Position: 100 shares @ $300 = $30,000

Stock splits 3:1:
- Position: 300 shares @ $100 = $30,000

TrackFolio updates:
- Records stock split event
- Adjusts average cost (accounts for split)
- Updates ticker mapping if needed
```

### Ticker Evolution

**Handles Company Changes:**
- Company rename (GE → GEV)
- Merger/acquisition (new ticker after merger)
- Spin-off (split into multiple companies)
- Reverse split/consolidation

**Ticker Mapping:**
- Old ticker → New ticker mapping
- Date of change
- Split/consolidation ratio
- Used for historical price continuity

### Impact on Calculations

**Average Cost Adjustment:**
```
Before split: 100 @ $300 = $30,000 (avg: $300)
After 3:1 split: 300 @ $100 = $30,000 (avg: $100)

TrackFolio stores: avg_cost = $100 (current)
```

**Profit/Loss Accuracy:**
- Historical transactions use original quantities
- Current holdings use split-adjusted quantities
- P&L calculated correctly across splits

---

## Multi-Currency Support

### Supported Currencies

**Primary:**
- EUR (Euro)
- USD (US Dollar)

**Others:**
- GBP (British Pound)
- CHF (Swiss Franc)
- CAD (Canadian Dollar)
- AUD (Australian Dollar)
- JPY (Japanese Yen)
- And more...

### Exchange Rates

**Automatic Conversion:**
- EUR ↔ USD: Updated daily from Yahoo Finance
- Other pairs: Supported when needed
- Historical rates: Stored for accurate cost basis

**Storage:**
- Date-based exchange rate history
- Used for retroactive conversions
- 24-hour cache on current rate

### Transaction Handling

**Multi-Currency Transactions:**
```json
{
  "operation_date": "2024-01-15",
  "ticker": "AAPL",
  "quantity": 10,
  "price_per_share": 150.50,
  "amount_currency": "USD",
  "currency": "USD",
  "fees": 5.00
}
```

**Conversion to EUR:**
```
USD Amount: $1,505.00 + $5.00 fees = $1,510.00
Exchange Rate (2024-01-15): 1 EUR = 1.090 USD
EUR Amount: $1,510.00 / 1.090 = €1,384.86

Portfolio stores: €1,384.86
```

### Multi-Currency Breakdown

**Portfolio Overview:**
- Total value in reporting currency (EUR)
- Breakdown by currency
- Currency allocations (%)

**Example:**
```
Total Portfolio: €50,000
- EUR Holdings: €20,000 (40%)
- USD Holdings: €30,000 (60%)
- GBP Holdings: €0 (0%)
```

### Reporting Currency

**Default:** EUR

**Change Reporting Currency:**
- Currently: Edit config
- Future: User preference setting

---

## Data Import

### CSV Import System

**Supported Format:**
```csv
date,asset,type,quantity,price,currency
2024-01-15,AAPL,BUY,10,150.50,USD
2024-01-16,GOOGL,BUY,5,140.25,USD
2024-01-17,AAPL,SELL,5,155.00,USD
```

**Field Requirements:**
- `date`: YYYY-MM-DD, DD/MM/YYYY, or MM/DD/YYYY (auto-detected)
- `asset`: Ticker symbol or company name
- `type`: BUY, SELL, DIVIDEND, FEE
- `quantity`: Numeric value (can be decimal)
- `price`: Price per share (ignored for DIVIDEND/FEE)
- `currency`: EUR, USD, or other currency code

### Broker Support

**Directa Format (Primary):**
```
Skip first 9 rows (metadata)
Auto-detect columns
Handle Italian date formats (DD/MM/YYYY)
Multi-currency support
```

**Auto-Detection:**
- Detects format from structure
- Handles different date formats
- Identifies column positions
- Works with or without headers

### Import Process

**Steps:**
1. Upload CSV file
2. Validation: Check format, required fields, data types
3. Deduplication: Compare with existing transactions
4. Preview: Show what will be imported
5. Confirm and import
6. Generate import report

**Validation Checks:**
- Valid dates
- Positive quantities
- Valid asset symbols
- Supported currencies
- Valid transaction types

### Import Report

**Shows:**
```json
{
  "status": "success",
  "imported": 45,
  "duplicates": 3,
  "errors": 1,
  "skipped": 1,
  "details": {
    "duplicate_rows": [2, 5, 7],
    "error_rows": [10],
    "skipped_reasons": ["Invalid date format"]
  }
}
```

---

## Automated Background Jobs

### Celery Task Queue

**Architecture:**
- Redis-backed message broker
- Celery worker pool (solo mode for stability)
- RedBeat scheduler (persistent schedule in Redis)
- Automatic retry on failure

### Scheduled Tasks

**Daily Tasks (CET Timezone):**

#### 23:00 - Price Updates
```python
# Traditional assets
price_updates.price_updates_task()
  ├── Fetch all holdings
  ├── Get current prices from Yahoo Finance
  ├── Store in price_history table
  └── Update cached prices

# Crypto assets (every 5 minutes)
update_crypto_prices.update_crypto_prices_task()
  ├── Fetch all crypto holdings
  ├── Get prices from CoinGecko
  ├── Store in price_history
  └── Update real-time prices
```

#### 23:15 - Metric Calculation
```python
metric_calculation.calculate_metrics_task()
  ├── Recalculate portfolio IRR/TWR
  ├── Calculate individual position metrics
  ├── Update cached_metrics table
  └── Cache for 24 hours

crypto_metric_calculation.calculate_crypto_metrics_task()
  ├── Calculate crypto portfolio metrics
  ├── Individual crypto asset metrics
  └── Cache results
```

#### 23:30 - Daily Snapshots
```python
snapshots.create_snapshot_task()
  ├── Record portfolio total value
  ├── Record cost basis
  ├── Store in portfolio_snapshots
  └── Used for performance charts

crypto_snapshots.create_crypto_snapshot_task()
  ├── Crypto portfolio daily snapshot
  └── Store in crypto_portfolio_snapshots
```

#### Every 5 Minutes - Crypto Prices
- Real-time cryptocurrency price updates
- CoinGecko API calls
- Rate limit aware (1-2 calls per second)

#### Every 30 Minutes - Blockchain Sync
```python
blockchain_sync.sync_all_wallets_task()
  ├── For each configured wallet:
  │   ├── Fetch recent transactions
  │   ├── Deduplicate
  │   ├── Auto-import as TRANSFER_IN/OUT
  │   └── Update balance
  └── Log sync results
```

### Task Monitoring

**View Task Status:**
```bash
# Check active tasks
docker compose exec celery-worker celery -A app.celery_app inspect active

# View scheduled tasks
docker compose logs celery-beat | tail -20

# Check task history
docker compose exec celery-worker celery -A app.celery_app inspect registered

# Monitor Redis queue
docker compose exec redis redis-cli LLEN celery
```

### Logs

**View Task Logs:**
```bash
# Worker logs
docker compose logs celery-worker -f

# Beat scheduler logs
docker compose logs celery-beat -f

# Backend logs (API task triggers)
docker compose logs backend | grep -i task
```

### Failure Handling

**Automatic Retries:**
- Failed tasks retry up to 3 times
- Exponential backoff (5s, 25s, 125s delays)
- Logged for debugging

**Error Scenarios:**
- Network timeout → Retry
- API rate limit → Retry with backoff
- Data validation error → Skip and log
- Database connection error → Retry

**Manual Intervention:**
```bash
# Manually run price update
docker compose exec backend python -c \
  "from app.tasks.price_updates import price_updates_task; price_updates_task.delay()"

# Clear failed tasks
docker compose exec redis redis-cli FLUSHDB  # WARNING: Clears all Redis data
```

---

## Benchmarking

### Active Benchmark

**Single Benchmark Per User:**
- Only one active benchmark at a time
- Used for portfolio comparison
- Affects performance display

### Supported Benchmarks

**Popular Indices:**
- SPY (S&P 500)
- QQQ (NASDAQ-100)
- EFA (MSCI EAFE - International)
- BND (Bond Market)
- GLD (Gold)
- Any ticker with Yahoo Finance data

### Benchmark Comparison

**Displayed Metrics:**
```
Portfolio Performance (TWR): 15.25%
Benchmark Performance (SPY): 12.50%
Outperformance: +2.75%
```

### Configuration

**Set Benchmark:**
```bash
POST /api/benchmark
{
  "ticker": "SPY",
  "description": "S&P 500"
}
```

**Performance Chart:**
- X-axis: Time
- Y-axis: Cumulative return %
- Portfolio line (blue)
- Benchmark line (gray)
- Outperformance area (green shading)

---

## Real-Time Updates

### Frontend Data Fetching

**React Query Hooks:**
- `usePortfolio()` - Dashboard data
- `useHoldings()` - Holdings list
- `usePrices()` - Historical prices
- `useRealtimePrices()` - Current prices
- `useBenchmark()` - Benchmark data

**Update Intervals:**
- Portfolio overview: 5 minutes
- Holdings: 5-10 minutes
- Prices: 1-5 minutes (manual or automatic)
- Real-time prices: Via `/api/prices/realtime` endpoint

### Polling vs. WebSocket

**Current:** REST polling (efficient for small portfolios)

**Future:** WebSocket support for true real-time updates
- Reduce network traffic
- Lower latency
- Better for large portfolios

---

## Data Security

### Local Storage

- All data stored on local machine
- PostgreSQL database with simple credentials (not exposed)
- Redis cache (ephemeral, not sensitive)

### No Data Sharing

- No external telemetry
- No data sent to third parties
- Price data from Yahoo Finance and CoinGecko only

### Backup Strategy

**Recommended:**
```bash
# Daily automated backup
0 2 * * * docker compose exec -T postgres pg_dump -U portfolio portfolio_db | gzip > backups/portfolio_$(date +\%Y\%m\%d).sql.gz
```

See [README.md](README.md) for backup/restore instructions.

---

## Performance Considerations

### Optimization

- **Database Indexes**: Common query patterns indexed
- **Query Caching**: Redis caching of expensive queries
- **Lazy Loading**: Historical data loaded on-demand
- **Pagination**: Large datasets paginated
- **Async/Await**: Non-blocking I/O for FastAPI

### Scalability

**Current Design:**
- Optimized for 100-1000 holdings
- Handles 10,000+ transactions efficiently
- Price history: 5+ years of daily data

**Potential Bottlenecks:**
- Very large portfolios (10,000+ holdings)
- Real-time price updates (move to WebSocket)
- Metric calculations (parallelize with task queue)

### Resource Usage

- **Memory**: ~800MB for all services
- **Disk**: ~500MB + portfolio data
- **CPU**: <5% idle, <20% during calculations
- **Network**: <1MB/hour (price updates + syncs)

---

## Future Enhancements

- [ ] Tax loss harvesting calculator
- [ ] Performance attribution analysis
- [ ] Email/webhook notifications
- [ ] WebSocket for real-time updates
- [ ] Mobile app (React Native)
- [ ] Advanced charting (candlestick, technical indicators)
- [ ] Option portfolio tracking
- [ ] Portfolio rebalancing suggestions
- [ ] Multi-user support (if needed)
- [ ] Margin account tracking
- [ ] Dividend reinvestment tracking
- [ ] Corporate action history
