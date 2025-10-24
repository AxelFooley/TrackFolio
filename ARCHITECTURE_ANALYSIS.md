# TrackFolio Portfolio Architecture Analysis

## Executive Summary

This document provides a comprehensive analysis of the TrackFolio portfolio tracking application's current architecture, specifically focusing on how traditional and cryptocurrency holdings are fetched, structured, and displayed. The analysis identifies the current systems, their data structures, components, and gaps that exist between the two parallel systems.

---

## 1. Traditional Holdings System Architecture

### 1.1 API Endpoints

#### Portfolio Overview (`/api/portfolio/overview`)
**File**: `/backend/app/api/portfolio.py` (line 94)

**Response Model**: `PortfolioOverview`
```python
{
    current_value: Decimal,                    # Current portfolio market value
    total_cost_basis: Decimal,                 # Total amount invested
    total_profit: Decimal,                     # Unrealized gain/loss
    average_annual_return: Optional[float],    # Calculated from cached metrics
    today_gain_loss: Optional[Decimal],        # Daily change in absolute terms
    today_gain_loss_pct: Optional[float]       # Daily change in percentage
}
```

**Data Flow**:
1. Fetches all Position records from database
2. For each position, retrieves latest PriceHistory (current ticker)
3. Queries CachedMetrics table for portfolio-level metrics
4. Calculates today's gain/loss by comparing latest vs. previous day prices
5. Returns aggregated portfolio metrics

#### Holdings List (`/api/portfolio/holdings`)
**File**: `/backend/app/api/portfolio.py` (line 186)

**Response Model**: `List[PositionResponse]`
```python
{
    id: int,
    ticker: str,                           # Current ticker (after splits)
    isin: Optional[str],                   # 12-character ISIN
    description: str,
    asset_type: str,                       # "stock", "etf", "crypto"
    quantity: Decimal,
    average_cost: Decimal,                 # Per-share average cost
    cost_basis: Decimal,                   # Total invested (quantity * average_cost)
    current_price: Optional[Decimal],      # Latest close price
    current_value: Optional[Decimal],      # quantity * current_price
    unrealized_gain: Optional[Decimal],    # current_value - cost_basis
    return_percentage: Optional[float],    # (unrealized_gain / cost_basis) * 100
    irr: Optional[float],                  # Internal Rate of Return (from CachedMetrics)
    today_change: Optional[Decimal],       # Absolute change today
    today_change_percent: Optional[float], # Percentage change today
    last_calculated_at: datetime,
    currency: str                          # Default "USD"
}
```

**Data Flow**:
1. Fetches all Position records
2. For each position:
   - Gets latest 2 PriceHistory records (current, previous)
   - Queries CachedMetrics for position IRR
   - Calculates current values and changes
   - Uses `calculate_today_change()` helper function
3. Returns list of enriched position responses

#### Performance Data (`/api/portfolio/performance`)
**File**: `/backend/app/api/portfolio.py` (line 260)

**Response Model**: `PortfolioPerformance`
```python
{
    portfolio_data: List[PerformanceDataPoint],      # Historical portfolio values
    benchmark_data: List[PerformanceDataPoint],      # Benchmark comparison
    portfolio_start_value: Optional[Decimal],
    portfolio_end_value: Optional[Decimal],
    portfolio_change_amount: Optional[Decimal],
    portfolio_change_pct: Optional[float],
    benchmark_start_price: Optional[Decimal],
    benchmark_end_price: Optional[Decimal],
    benchmark_change_amount: Optional[Decimal],
    benchmark_change_pct: Optional[float]
}

where PerformanceDataPoint = {
    date: date,
    value: Decimal
}
```

**Data Flow**:
1. Parses time range parameter (1D, 1W, 1M, 3M, 6M, 1Y, YTD, ALL)
2. Queries PortfolioSnapshot table filtered by date range
3. Transforms snapshots to PerformanceDataPoint objects
4. If benchmark is configured:
   - Fetches PriceHistory for benchmark ticker on snapshot dates
   - Transforms to PerformanceDataPoint objects
5. Calculates summary metrics (start value, end value, change %)

#### Position Detail (`/api/portfolio/positions/{identifier}`)
**File**: `/backend/app/api/portfolio.py` (line 391)

**Response**: PositionResponse + stock split history
- Accepts ISIN (12 chars) or ticker as identifier
- Includes split history showing ticker evolution

### 1.2 Database Models

**Position Model** (`/backend/app/models/position.py`)
```python
class Position(Base):
    id: int (primary key)
    current_ticker: str (indexed)          # Current ticker (post-splits)
    isin: Optional[str]                    # 12-char ISIN (unique)
    description: str
    asset_type: AssetType                  # STOCK, ETF, CRYPTO
    quantity: Decimal (precision 20, scale 8)
    average_cost: Decimal                  # Per-share cost including fees
    cost_basis: Decimal                    # Total invested
    last_calculated_at: datetime
    updated_at: datetime
```

**Related Models**:
- `PriceHistory`: (ticker, date) -> close price
- `CachedMetrics`: (metric_type, metric_key) -> metric_value (JSON)
- `PortfolioSnapshot`: (user_id, snapshot_date) -> total_value
- `StockSplit`: Historical split information by ISIN

### 1.3 Data Aggregation Services

**PositionManager** (`/backend/app/services/position_manager.py`)
- Recalculates position metrics from transactions
- Updates cost basis and average cost
- Handles stock split detection
- Uses database-level locking for concurrency

**FinancialCalculations** (`/backend/app/services/calculations.py`)
- Computes IRR (Internal Rate of Return)
- Calculates TWR (Time-Weighted Return)
- Determines average cost basis

---

## 2. Cryptocurrency Holdings System Architecture

### 2.1 API Endpoints

#### Portfolio List (`/api/crypto/portfolios`)
**File**: `/backend/app/api/crypto.py` (line 138)

**Response Model**: `CryptoPortfolioList`
```python
{
    portfolios: List[CryptoPortfolioResponse],
    total_count: int
}

where CryptoPortfolioResponse = {
    id: int,
    name: str,
    description: Optional[str],
    is_active: bool,
    base_currency: CryptoCurrency ("EUR" | "USD"),
    wallet_address: Optional[str],
    created_at: datetime,
    updated_at: datetime,
    
    # Currency-specific computed fields
    total_value_usd: Optional[Decimal],
    total_value_eur: Optional[Decimal],
    total_profit_usd: Optional[Decimal],
    total_profit_eur: Optional[Decimal],
    profit_percentage_usd: Optional[float],
    profit_percentage_eur: Optional[float],
    
    # Original fields (backward compatibility)
    total_value: Optional[Decimal],
    total_cost_basis: Optional[Decimal],
    total_profit_loss: Optional[Decimal],
    total_profit_loss_pct: Optional[float],
    transaction_count: Optional[int],
    
    # Wallet sync status
    wallet_sync_status: Dict[str, Any]
}
```

**Data Flow**:
1. Queries CryptoPortfolio records (with pagination)
2. For each portfolio:
   - Calls `CryptoCalculationService.calculate_portfolio_metrics()`
   - Retrieves wallet sync status if wallet address configured
3. Returns aggregated metrics for each portfolio

#### Portfolio Detail (`/api/crypto/portfolios/{portfolio_id}`)
**File**: `/backend/app/api/crypto.py` (line 255)

**Response Model**: `CryptoPortfolioResponse` (same as above)

#### Portfolio Holdings (`/api/crypto/portfolios/{portfolio_id}/holdings`)
**File**: `/backend/app/api/crypto.py` (line 940)

**Response Model**: `List[CryptoHolding]`
```python
{
    symbol: str,                              # Crypto symbol (BTC, ETH, etc.)
    quantity: Decimal,
    average_cost: Decimal,
    cost_basis: Decimal,
    current_price: Optional[Decimal],
    current_value: Optional[Decimal],
    unrealized_gain_loss: Optional[Decimal],
    unrealized_gain_loss_pct: Optional[float],
    realized_gain_loss: Optional[Decimal],    # From FIFO accounting
    first_purchase_date: Optional[date],
    last_transaction_date: Optional[date],
    currency: Optional[CryptoCurrency]
}
```

**Data Flow**:
1. Calls `CryptoCalculationService.calculate_holdings(portfolio_id)`
2. Uses FIFO accounting to determine holdings and realized gains
3. Fetches current prices from PriceFetcher
4. Calculates unrealized gains and allocations
5. Returns enriched holdings list

#### Individual Holding (`/api/crypto/portfolios/{portfolio_id}/holdings/{symbol}`)
**File**: `/backend/app/api/crypto.py` (line 968)

**Response Model**: `CryptoHolding`
- Filters holdings list by symbol (case-insensitive)

#### Portfolio Performance (`/api/crypto/portfolios/{portfolio_id}/performance`)
**File**: `/backend/app/api/crypto.py` (line 1010)

**Response Model**: `List[CryptoPerformanceData]`
```python
{
    date: date,
    portfolio_value: Decimal,
    cost_basis: Decimal,
    profit_loss: Decimal,
    profit_loss_pct: float
}
```

**Data Flow**:
1. Parses time range parameter
2. Queries CryptoPortfolioSnapshot records filtered by date range
3. Transforms to CryptoPerformanceData objects
4. Returns time-series performance data

#### Portfolio Metrics (`/api/crypto/portfolios/{portfolio_id}/metrics`)
**File**: `/backend/app/api/crypto.py` (estimated around line 1060+)

**Response Model**: `CryptoPortfolioMetrics`
```python
{
    portfolio_id: int,
    base_currency: str,
    
    # Value metrics
    total_value: Optional[Decimal],
    total_cost_basis: Decimal,
    total_profit_loss: Optional[Decimal],
    total_profit_loss_pct: Optional[float],
    
    # Performance metrics
    unrealized_gain_loss: Optional[Decimal],
    realized_gain_loss: Decimal,
    total_deposits: Decimal,
    total_withdrawals: Decimal,
    
    # IRR calculations
    internal_rate_of_return: Optional[float],
    time_weighted_return: Optional[float],
    
    # Holdings breakdown
    holdings_count: int,
    transaction_count: int,
    
    # Currency breakdown
    currency_breakdown: List[dict],
    
    # Asset allocation
    asset_allocation: List[dict],
    
    # Performance insights
    best_performer: Optional[dict],
    worst_performer: Optional[dict],
    largest_position: Optional[dict]
}
```

### 2.2 Database Models

**CryptoPortfolio Model** (`/backend/app/models/crypto.py`)
```python
class CryptoPortfolio(Base):
    id: int (primary key)
    name: str
    description: Optional[str]
    is_active: bool
    base_currency: CryptoCurrency (EUR, USD)
    wallet_address: Optional[str]           # Bitcoin wallet for sync
    wallet_last_sync_time: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    transactions: Relationship[List[CryptoTransaction]]
```

**CryptoTransaction Model**
```python
class CryptoTransaction(Base):
    id: int
    portfolio_id: int (FK to CryptoPortfolio)
    symbol: str
    transaction_type: CryptoTransactionType (BUY, SELL, TRANSFER_IN, TRANSFER_OUT)
    quantity: Decimal (precision 20, scale 8)
    price_at_execution: Decimal
    currency: CryptoCurrency
    total_amount: Decimal
    fee: Decimal
    fee_currency: Optional[str]
    timestamp: datetime
    exchange: Optional[str]
    transaction_hash: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
```

**Related Models**:
- `CryptoPortfolioSnapshot`: Daily portfolio snapshots for performance tracking
- `CryptoPriceData`: Current and historical crypto prices

### 2.3 Data Aggregation Services

**CryptoCalculationService** (`/backend/app/services/crypto_calculations.py`)

**Key Methods**:
1. `calculate_portfolio_metrics(portfolio_id)` 
   - Calculates comprehensive portfolio metrics
   - Uses FIFO for holdings and realized gains
   - Fetches current prices
   - Computes IRR and TWR
   - Returns CryptoPortfolioMetrics

2. `calculate_holdings(portfolio_id)`
   - Aggregates holdings by symbol using FIFO
   - Calculates cost basis and average cost per holding
   - Fetches current prices and computes values
   - Returns list of CryptoHolding

3. `_calculate_holdings(transactions)`
   - Internal method implementing FIFO logic
   - Tracks quantity and cost per symbol

4. `_get_current_prices(symbols, currency)`
   - Fetches prices from PriceFetcher
   - Handles currency conversion

---

## 3. Frontend Dashboard Architecture

### 3.1 Dashboard Page (`/frontend/src/app/page.tsx`)

**Components Used**:
```
DashboardPage
├── PortfolioOverview
├── TodaysMovers
├── PerformanceChart
├── HoldingsTable
└── AddTransactionModal
```

### 3.2 Dashboard Components

#### PortfolioOverview Component
**File**: `/frontend/src/components/Dashboard/PortfolioOverview.tsx`

**Data Dependencies**:
- Hook: `usePortfolioOverview()` - fetches `/api/portfolio/overview`
- Hook: `useHoldings()` - fetches `/api/portfolio/holdings`
- Hook: `useRealtimePrices(symbols)` - fetches real-time prices from `/api/prices/realtime`

**Displayed Metrics**:
1. Current Value (with real-time indicator)
2. Total Profit (with percentage)
3. Avg Annual Return
4. Today's Change (with percentage)

**Data Flow**:
1. Fetches overview and holdings data
2. Extracts ticker symbols from holdings
3. Fetches real-time prices for each symbol
4. Calculates updated portfolio metrics using real-time data
5. Merges real-time metrics with fallback to API data
6. Displays live data indicator when available

#### TodaysMovers Component
**File**: `/frontend/src/components/Dashboard/TodaysMovers.tsx`

**Data Dependencies**:
- Hook: `useHoldings()` - fetches holdings
- Hook: `useRealtimePrices(symbols)` - fetches real-time prices

**Logic**:
1. Fetches all holdings
2. Merges with real-time price data
3. Calculates today's change for each holding
4. Filters holdings with change data
5. Sorts by today's change percentage
6. Returns top 3 gainers and top 3 losers

**Display**:
- Shows ticker, current value, daily change amount, daily change percentage
- Color-coded (green for gainers, red for losers)

#### HoldingsTable Component
**File**: `/frontend/src/components/Dashboard/HoldingsTable.tsx`

**Data Dependencies**:
- Hook: `useHoldings()` - fetches holdings
- Hook: `useRealtimePrices(symbols)` - fetches real-time prices

**Features**:
- Sortable table by multiple fields
- Merges real-time prices with holdings data
- Clickable rows to navigate to asset detail page
- Displays: ticker, quantity, average cost, current price, current value, unrealized gain, return %, today's change

#### PerformanceChart Component
**File**: `/frontend/src/components/Dashboard/PerformanceChart.tsx`

**Data Dependencies**:
- Hook: `usePerformanceData(range)` - fetches `/api/portfolio/performance`
- Uses Recharts for visualization

### 3.3 React Query Hooks

**Portfolio Hooks** (`/frontend/src/hooks/usePortfolio.ts`):
```typescript
usePortfolioOverview()      // GET /api/portfolio/overview
useHoldings()               // GET /api/portfolio/holdings
usePerformanceData(range)   // GET /api/portfolio/performance?range=...
```

**Cache Strategy**:
- staleTime: 60000ms (1 minute)
- Data refetches after this time or on manual trigger

### 3.4 Real-Time Price Integration

**Hook** (`/frontend/src/hooks/useRealtimePrices.ts`):
```typescript
const { realtimePrices, isLoading, lastUpdate } = useRealtimePrices(symbols)
```

**Map Structure**:
```typescript
realtimePrices: Map<symbol, {
    symbol: string
    current_price: number
    previous_close: number
    change_amount?: number
    change_percent?: number
    currency: string
    last_updated: string
}>
```

**Usage Pattern**:
1. Components extract ticker symbols from holdings
2. Call `useRealtimePrices(symbols)` to fetch real-time prices
3. Merge real-time data with static holdings data
4. Calculate updated values and changes using real-time prices
5. Display with live indicator badge

---

## 4. Data Structure Comparison

### 4.1 Holdings Data Structure

| Aspect | Traditional | Crypto | Gap |
|--------|-------------|--------|-----|
| **Identifier** | ticker + ISIN | symbol | Different uniqueness models |
| **Aggregation** | Per ISIN (unique) | Per symbol (multiple portfolios) | Crypto uses portfolios, traditional doesn't |
| **Cost Basis** | From transactions | FIFO calculated | Different calculation methods |
| **Current Price** | PriceHistory table | Fetched on-demand | Different storage mechanisms |
| **Asset Type** | STOCK, ETF, CRYPTO | Implicit in symbol | Traditional can have CRYPTO type but not fully used |
| **Splits** | Tracked in StockSplit table | Not tracked | Crypto doesn't handle splits |
| **Currency** | Fixed (EUR for portfolio) | Base currency per portfolio | Crypto supports USD/EUR per portfolio |

### 4.2 Portfolio Metrics

| Metric | Traditional | Crypto | Gap |
|--------|-------------|--------|-----|
| **Total Value** | Aggregated from positions | Calculated per portfolio | Different aggregation scopes |
| **Cost Basis** | Sum of position costs | FIFO calculated | Different calculation methods |
| **Profit/Loss** | Simple subtraction | FIFO + unrealized/realized split | Crypto more sophisticated |
| **IRR/TWR** | In CachedMetrics | Calculated on-demand | Different calculation timing |
| **Today's Change** | Calculated from 2 days of prices | Not calculated at portfolio level | Traditional has, crypto lacks |
| **Performance History** | PortfolioSnapshot daily | CryptoPortfolioSnapshot daily | Different snapshot models |
| **Benchmark** | Benchmark table + comparison | Not supported | Traditional has, crypto lacks |
| **Wallet Sync** | Not applicable | Supported (Bitcoin) | Crypto-specific feature |

### 4.3 API Response Patterns

**Traditional Holdings Response**:
```python
# List response with immediate metrics
List[PositionResponse] where each has:
- Calculated values (price, value, gain)
- Metrics (IRR, return %)
- Daily changes
```

**Crypto Holdings Response**:
```python
# List response with different metrics
List[CryptoHolding] where each has:
- Calculated values (similar structure)
- Realized vs unrealized gains split
- Purchase dates (first and last)
- Currency optional field
```

---

## 5. Frontend Data Dependencies

### 5.1 Current Dashboard Data Flow

```
Dashboard Page
├─ usePortfolioOverview()
│  └─ GET /api/portfolio/overview
│     └─ Returns: PortfolioOverview
├─ useHoldings()
│  └─ GET /api/portfolio/holdings
│     └─ Returns: List[PositionResponse]
├─ useRealtimePrices(symbols)
│  └─ GET /api/prices/realtime?symbols=...
│     └─ Returns: RealtimePriceResponse
├─ usePerformanceData(range)
│  └─ GET /api/portfolio/performance?range=...
│     └─ Returns: PortfolioPerformance
└─ Dashboard Components merge data and display
```

### 5.2 Crypto System Data Flow

```
Crypto Portfolio Page
├─ useCryptoPortfolios()
│  └─ GET /api/crypto/portfolios
│     └─ Returns: CryptoPortfolioList
├─ useCryptoPortfolio(id)
│  └─ GET /api/crypto/portfolios/{id}
│     └─ Returns: CryptoPortfolioResponse
├─ useCryptoHoldings(id)
│  └─ GET /api/crypto/portfolios/{id}/holdings
│     └─ Returns: List[CryptoHolding]
├─ useCryptoPerformanceData(id, range)
│  └─ GET /api/crypto/portfolios/{id}/performance
│     └─ Returns: List[CryptoPerformanceData]
└─ useCryptoPortfolioMetrics(id)
   └─ GET /api/crypto/portfolios/{id}/metrics
      └─ Returns: CryptoPortfolioMetrics
```

---

## 6. Identified Gaps & Inconsistencies

### 6.1 Structural Gaps

1. **Portfolio vs Global Perspective**
   - Traditional: Single global portfolio
   - Crypto: Multiple portfolios with independence
   - Gap: Cannot mix traditional and crypto holdings in single view

2. **Asset Identification**
   - Traditional: ISIN + ticker (primary ISIN)
   - Crypto: Symbol only (e.g., BTC, ETH)
   - Gap: Different uniqueness constraints

3. **Currency Handling**
   - Traditional: Fixed EUR base with FX conversion
   - Crypto: Per-portfolio base currency (EUR/USD)
   - Gap: Traditional doesn't support multi-currency

4. **Metrics Calculation Timing**
   - Traditional: Cached metrics updated daily (23:15)
   - Crypto: Calculated on-demand at query time
   - Gap: Different performance characteristics

5. **Benchmark Support**
   - Traditional: Benchmark tracked with comparison data
   - Crypto: No benchmark support
   - Gap: Asymmetric feature parity

6. **Historical Snapshots**
   - Traditional: PortfolioSnapshot table with daily snapshots
   - Crypto: CryptoPortfolioSnapshot (parallel structure)
   - Gap: Separate snapshot models instead of unified

7. **Transaction Type Handling**
   - Traditional: BUY, SELL, DIVIDEND, FEE
   - Crypto: BUY, SELL, TRANSFER_IN, TRANSFER_OUT
   - Gap: Different transaction models

### 6.2 Feature Gaps

1. **Today's Movers**
   - Available: Traditional holdings only
   - Missing: Crypto holdings comparison
   - Impact: Cannot show top gainers/losers across all assets

2. **Combined Performance**
   - Available: Traditional portfolio performance + optional benchmark
   - Missing: Crypto portfolio performance in main dashboard
   - Impact: No unified performance view

3. **Real-Time Updates**
   - Available: Real-time prices for traditional holdings
   - Missing: Real-time prices integrated into crypto holdings display
   - Impact: Stale crypto price data on dashboard

4. **Wallet Integration**
   - Available: Bitcoin wallet sync for crypto
   - Missing: No wallet support for traditional assets
   - Impact: Asymmetric blockchain integration

5. **Asset Type Consistency**
   - Observed: Position model has "CRYPTO" asset_type
   - Issue: Crypto system is separate; traditional CRYPTO positions not used
   - Impact: Potential for confusion and duplicate systems

### 6.3 Data Flow Inconsistencies

| Aspect | Traditional | Crypto | Issue |
|--------|-------------|--------|-------|
| Metrics Scope | Global | Per-portfolio | Cannot aggregate across portfolios |
| Price Source | Cached PriceHistory | On-demand fetch | Different staleness characteristics |
| Calculation Method | Cached metrics | On-demand calculation | Different CPU load patterns |
| Portfolio Grouping | Implicit global | Explicit portfolio ID | Different data organization |
| Currency Scope | Portfolio-wide | Per-portfolio EUR/USD | Traditional EUR-only |

---

## 7. Key Services & Utilities

### 7.1 Backend Services

**Price Fetching**:
- `PriceFetcher` - Fetches prices from Yahoo Finance and CoinGecko
- `PriceFetcherIntegration` - Multi-source fallback strategy

**Calculations**:
- `FinancialCalculations` - IRR, TWR for traditional assets
- `CryptoCalculationService` - Metrics, holdings, FIFO for crypto

**Position Management**:
- `PositionManager` - Aggregates transactions into positions
- `SplitDetector` - Detects and handles stock splits

**Data Aggregation**:
- `CryptoCalculationService._calculate_holdings()` - FIFO aggregation
- `PositionManager.recalculate_position()` - Traditional aggregation

### 7.2 Frontend Utilities

**API Client** (`/frontend/src/lib/api.ts`):
- Base URL: `NEXT_PUBLIC_API_URL` (default `http://localhost:8000/api`)
- Axios instance with 30-second timeout
- Type-safe request/response wrappers

**Formatting Utilities** (`/frontend/src/lib/utils.ts`):
- `formatCurrency(value, currency)` - Currency formatting
- `formatPercentage(value)` - Percentage formatting
- `formatNumber(value)` - Number formatting

**React Query Integration**:
- Uses `@tanstack/react-query` for caching
- Configurable stale times (mostly 30-60 seconds)
- Automatic cache invalidation on mutations

---

## 8. Current Limitations & Constraints

### 8.1 Data Aggregation Limitations

1. **No Cross-Portfolio Aggregation**
   - Crypto portfolios are isolated
   - Cannot calculate total crypto holdings across portfolios
   - Dashboard only shows traditional portfolio

2. **Price Data Synchronization**
   - Traditional: Cached daily (23:00 CET)
   - Crypto: On-demand fetch
   - Can result in stale or inconsistent prices

3. **Metrics Update Lag**
   - Traditional: Daily batch calculation (23:15 CET)
   - Crypto: Real-time on query
   - Different latency characteristics

### 8.2 System Integration Constraints

1. **Separate Data Models**
   - Position vs CryptoPortfolio/CryptoTransaction
   - PortfolioSnapshot vs CryptoPortfolioSnapshot
   - Different schema designs

2. **API Endpoint Duplication**
   - `/api/portfolio/overview` vs `/api/crypto/portfolios/{id}`
   - `/api/portfolio/holdings` vs `/api/crypto/portfolios/{id}/holdings`
   - Parallel structures instead of unified

3. **Frontend Component Duplication**
   - Traditional dashboard components vs crypto portfolio components
   - Similar logic but separate implementations
   - Code duplication potential

---

## 9. Recommendations for Integration

### 9.1 Short-Term (Non-Breaking)

1. **Add Real-Time Crypto Display**
   - Fetch crypto prices in real-time like traditional holdings
   - Display on dashboard if available

2. **Add Today's Movers for Crypto**
   - Calculate daily changes for crypto holdings
   - Include in TodaysMovers component

3. **Unified Metrics Endpoint**
   - Create `/api/portfolio/combined-metrics` that aggregates both systems
   - Returns summary with traditional + crypto totals

4. **Enhanced Dashboard**
   - Show crypto portfolio summary in dashboard
   - Link to crypto portfolio details

### 9.2 Long-Term (Breaking Changes)

1. **Unified Holdings Model**
   - Create generic Holding model that supports both traditional and crypto
   - Normalize asset identification

2. **Consolidated Portfolio System**
   - Single portfolio with asset categories (traditional, crypto)
   - Unified transaction model

3. **Unified Snapshot Model**
   - Single PortfolioSnapshot for all assets
   - Unified performance calculation

4. **API Consolidation**
   - Single `/api/portfolio/holdings` for all holdings
   - Unified metrics endpoints

---

## 10. Summary

TrackFolio currently operates two parallel portfolio systems:

**Traditional System** (Stock/ETF):
- Single global portfolio
- ISIN-based asset identification
- Daily cached metrics and prices
- Supports benchmarks
- Real-time price integration

**Crypto System**:
- Multiple independent portfolios
- Symbol-based identification
- On-demand metric calculation
- Supports Bitcoin wallet sync
- Per-portfolio base currency (EUR/USD)

**Key Differences**:
- Different aggregation scopes (global vs portfolio-level)
- Different identification schemes (ISIN vs symbol)
- Different pricing models (cached vs on-demand)
- Different snapshot architectures
- Asymmetric feature sets

**Integration Opportunities**:
1. Unified holdings display (dashboard enhancement)
2. Combined performance view (new endpoint)
3. Cross-system search and filtering
4. Consolidated metrics API
5. Long-term: Unified data model

**Current Gaps**:
- No combined portfolio view
- No crypto in main dashboard metrics
- Separate real-time pricing strategies
- Duplicate API and component structures
- Different transaction models
