# TrackFolio Developer Guide

This guide provides comprehensive documentation for developers working on the TrackFolio portfolio tracker application.

## Table of Contents
1. [Development Workflow](#development-workflow)
2. [Project Architecture](#project-architecture)
3. [Backend Structure](#backend-structure)
4. [Frontend Structure](#frontend-structure)
5. [Database Schema](#database-schema)
6. [Configuration](#configuration)
7. [Testing](#testing)
8. [Debugging](#debugging)
9. [Troubleshooting](#troubleshooting)

## Development Workflow

### Quick Start

```bash
# Use the provided deployment script
./start.sh

# Or manually start services
docker compose up --build
```

### Standard Development Cycle

1. **Make code changes** in your editor
2. **Run linters before rebuilding:**
   ```bash
   # Frontend linting
   docker compose exec frontend npm run lint

   # Backend linting (if pytest available)
   docker compose exec backend pytest
   ```

3. **Rebuild Docker images:**
   ```bash
   docker compose up --build
   ```

4. **Verify changes:**
   ```bash
   # Check service logs
   docker compose logs -f

   # Test specific service
   docker compose logs -f backend
   ```

### Docker Compose Commands

```bash
# View all services
docker compose ps

# View logs for all services
docker compose logs -f

# View logs for specific service
docker compose logs -f backend
docker compose logs -f celery-worker
docker compose logs -f celery-beat
docker compose logs -f frontend
docker compose logs -f postgres
docker compose logs -f redis

# Restart a service
docker compose restart backend
docker compose restart celery-worker

# Stop all services
docker compose down

# Stop and remove volumes (WARNING: deletes all data)
docker compose down -v

# Execute command in container
docker compose exec backend python -c "print('test')"
docker compose exec postgres psql -U portfolio portfolio_db
docker compose exec redis redis-cli
```

### Linting & Code Quality

```bash
# Frontend
docker compose exec frontend npm run lint
docker compose exec frontend npm run lint:fix  # Auto-fix issues

# Backend (if tests configured)
docker compose exec backend pytest
docker compose exec backend flake8 app --max-line-length=127
```

## Project Architecture

### Multi-Service Docker Application

**Services:**
1. **postgres:15-alpine** - PostgreSQL database on internal network
   - User: `portfolio`, Password: `portfolio`
   - Database: `portfolio_db`
   - Health check: every 10 seconds
   - Volume: `postgres_data` (persistent)

2. **redis:7-alpine** - Cache and Celery broker
   - Configuration: Append-only file (AOF) for persistence
   - Health check: every 10 seconds
   - Volume: `redis_data` (persistent)

3. **backend (FastAPI)** - Main API server
   - Port: `127.0.0.1:8000` (localhost only)
   - Image: `trackfolio-backend:latest`
   - Health check: `/api/health` endpoint
   - Depends on: postgres, redis (health checks required)

4. **celery-worker** - Background job processor
   - Image: `trackfolio-celery-worker:latest`
   - Pool: solo (prevents SIGSEGV with yfinance curl_cffi)
   - Depends on: postgres, redis (health checks required)

5. **celery-beat** - Task scheduler
   - Image: `trackfolio-celery-beat:latest`
   - Scheduler: RedBeat (Redis-backed for persistence)
   - Depends on: postgres, redis (health checks required)

6. **frontend (Next.js 14)** - React user interface
   - Port: `127.0.0.1:3000` (localhost only)
   - Image: `trackfolio-frontend:latest`
   - Depends on: backend (HTTP connectivity)

**Network:** All services communicate via internal `portfolio-network` bridge

**Security:** All services bind to `127.0.0.1` (localhost only). Not accessible from internet by design.

---

## Backend Structure

Location: `/backend/app/`

### API Layer (`api/`)

**transactions.py** - Transaction management
- `POST /api/transactions/import` - Import Directa CSV format
- `POST /api/transactions/` - Create manual transaction
- `GET /api/transactions/` - List with pagination/filtering
- `GET /api/transactions/{id}` - Get specific transaction
- `PUT /api/transactions/{id}` - Update transaction
- `DELETE /api/transactions/{id}` - Delete transaction

**portfolio.py** - Portfolio metrics
- `GET /api/portfolio/overview` - Dashboard metrics
- `GET /api/portfolio/holdings` - Current positions
- `GET /api/portfolio/performance` - Historical performance
- `GET /api/portfolio/positions/{identifier}` - Position detail

**assets.py** - Asset information
- `GET /api/assets/{ticker}` - Asset details (ticker or 12-char ISIN)
- `GET /api/assets/{ticker}/transactions` - Asset transactions
- `GET /api/assets/{ticker}/prices` - Historical OHLCV data

**prices.py** - Price management
- `POST /api/prices/refresh` - Manual price update
- `POST /api/prices/ensure-coverage` - Ensure historical coverage
- `GET /api/prices/last-update` - Last update timestamp
- `GET /api/prices/realtime` - Real-time prices for symbols

**benchmark.py** - Benchmark tracking
- `GET /api/benchmark` - Get active benchmark
- `POST /api/benchmark` - Set portfolio benchmark

**crypto.py** - Cryptocurrency management (65+ endpoints)
- Portfolio CRUD: `/api/crypto/portfolios` (GET, POST, PUT, DELETE)
- Holdings: `/api/crypto/portfolios/{id}/holdings`
- Transactions: `/api/crypto/portfolios/{id}/transactions`
- Pricing: `/api/crypto/prices`, `/api/crypto/prices/{symbol}/history`
- Performance: `/api/crypto/portfolios/{id}/performance`
- Search: `/api/crypto/search`

**blockchain.py** - Bitcoin wallet sync
- `POST /api/blockchain/sync/wallet` - Manual sync
- `POST /api/blockchain/config/wallet` - Configure wallet address
- `GET /api/blockchain/wallet/{address}/transactions` - Wallet transactions
- `GET /api/blockchain/status` - Service status

### Services Layer (`services/`)

**price_fetcher.py**
- Multi-source price data (Yahoo Finance, CoinGecko)
- Methods: `fetch_current_prices()`, `fetch_historical_data()`, `fetch_fx_rate()`
- Rate limiting and caching

**price_fetcher_integration.py**
- Wraps multiple fetcher strategies
- Fallback logic between sources

**price_history_manager.py**
- OHLCV data storage and retrieval
- Gap filling for historical data

**csv_parser.py**
- DirectaCSVParser for broker transaction import
- Auto-detection of columns
- Multiple date format support

**deduplication.py**
- Transaction deduplication via SHA256 hash
- Duplicate detection batch processing

**position_manager.py**
- Position aggregation from transactions
- Average cost calculation
- Stock split detection

**calculations.py**
- Time-Weighted Return (TWR) calculation
- Internal Rate of Return (IRR) calculation

**currency_converter.py**
- Foreign exchange rate management
- EUR/USD conversion

**ticker_mapper.py**
- Symbol-to-ISIN mapping
- Normalization

**blockchain_fetcher.py**
- Bitcoin transaction fetching
- Multiple blockchain providers (Blockstream, Blockchain.com, BlockCypher)
- Rate limiting and retry logic

**blockchain_deduplication.py**
- Redis-based deduplication cache
- TTL configuration

**crypto_wallet.py**
- Multi-exchange wallet address tracking
- Balance calculation

**crypto_calculations.py**
- Crypto holdings calculation
- Performance metrics (P&L, return %)

### Background Tasks (`tasks/`)

**price_updates.py**
- Scheduled: 23:00 CET daily
- Fetches traditional asset prices from Yahoo Finance

**update_crypto_prices.py**
- Scheduled: Every 5 minutes
- Fetches crypto prices from CoinGecko

**metric_calculation.py**
- Scheduled: 23:15 CET daily
- Calculates portfolio IRR and returns

**crypto_metric_calculation.py**
- Scheduled: 23:15 CET daily
- Calculates crypto metrics

**snapshots.py**
- Scheduled: 23:30 CET daily
- Creates traditional portfolio snapshots

**crypto_snapshots.py**
- Scheduled: 23:30 CET daily
- Creates crypto portfolio snapshots

**blockchain_sync.py**
- Scheduled: Every 30 minutes
- Syncs Bitcoin wallet transactions

**price_history_update.py**
- Historical price data synchronization

### Database Models (`models/`)

**transaction.py** - Transaction records (ISIN-based)
- BUY/SELL operations with fees
- SHA256 deduplication hash
- Timestamp: operation_date, value_date
- Multi-currency: EUR, USD
- Fields: ticker, ISIN, quantity, price, fees

**position.py** - Current holdings
- Ticker, ISIN, quantity, average_cost
- AssetType: STOCK, ETF, CRYPTO
- Updated by PositionManager

**price_history.py** - Historical OHLCV
- Date-based pricing
- Unique constraint on (ticker, date)

**crypto.py** - Crypto portfolio system
- CryptoPortfolio: base_currency, wallet_address, last_sync_time
- CryptoTransaction: BUY, SELL, TRANSFER_IN, TRANSFER_OUT
- High-precision decimals (8 places)

**crypto_portfolio_snapshot.py** - Daily crypto snapshots

**portfolio_snapshot.py** - Daily traditional snapshots

**cached_metrics.py** - Computed metrics cache
- IRR, returns, other expensive calculations
- TTL-based expiration

**benchmark.py** - Active benchmark record

**stock_split.py** - Stock split history
- Ticker evolution tracking

### Configuration (`config.py`)

Pydantic-based settings with environment variables:

```python
# Application
app_name: str = "Portfolio Tracker"
environment: str = "production"
log_level: str = "INFO"

# Database
database_url: str  # PostgreSQL connection
redis_url: str     # Redis connection

# CORS
allowed_origins: list = ["http://localhost:3000", "http://localhost"]

# Timezone
timezone: str = "Europe/Rome"

# Price Updates
price_update_schedule: str = "0 23 * * *"  # 23:00 CET daily
price_cache_ttl_hours: int = 24

# Metrics
metric_calculation_schedule: str = "15 23 * * *"  # 23:15 CET daily
snapshots_schedule: str = "30 23 * * *"  # 23:30 CET daily

# Celery
celery_broker_url: str  # Redis broker
celery_result_backend: str  # Redis backend

# Rate Limiting
rate_limit_requests: int = 100  # per minute

# Blockchain (new)
blockchain_sync_enabled: bool = True
blockchain_sync_interval_minutes: int = 30
blockchain_max_transactions_per_sync: int = 50
blockchain_sync_days_back: int = 7
blockchain_rate_limit_requests_per_second: float = 1.0
blockchain_request_timeout_seconds: int = 30
```

---

## Frontend Structure

Location: `/frontend/src/`

### Pages (Next.js App Router)

**Dashboard (/)** - Portfolio overview
- Components: PortfolioOverview, HoldingsTable, PerformanceChart, TodaysMovers

**/holdings** - Holdings table
- Detailed position metrics and allocation percentages

**/import** - Transaction import
- CSV file upload with preview and validation

**/asset/[ticker]** - Asset detail page
- Transaction history, price chart, position summary

**/crypto/** - Crypto portfolios list
- Browse and manage crypto portfolios

**/crypto/[id]** - Crypto portfolio detail
- Overview and management

**/crypto/[id]/holdings** - Crypto holdings
- Current crypto positions and allocations

**/crypto/[id]/holdings/[symbol]** - Crypto asset detail
- Individual crypto asset performance

**/crypto/[id]/transactions** - Crypto transaction history
- All trades for a crypto portfolio

**/settings** - Application settings
- Benchmark configuration, preferences

### Components

**Dashboard:**
- `PortfolioOverview` - Key metrics display
- `HoldingsTable` - Position list with filters
- `PerformanceChart` - Historical performance visualization
- `TodaysMovers` - Top gainers/losers

**Asset Pages:**
- `AssetHeader` - Ticker and pricing info
- `PositionSummary` - Holdings summary
- `PriceChart` - Technical price chart
- `TransactionHistory` - Transaction list

**Crypto:**
- `CryptoHoldingsTable` - Crypto positions
- `CryptoPriceChart` - Crypto price visualization
- `CryptoTransactionTable` - Trade history
- `WalletSync` - Wallet sync status

**Shared:**
- `Navbar` - Main navigation
- `TickerAutocomplete` - Symbol search

**UI Components (Radix UI):**
- button, input, dialog, select, table, badge, card, tabs, etc.

### Data Fetching Hooks (React Query)

```typescript
usePortfolio()           // Dashboard data
useHoldings()            // Holdings list
useAsset()               // Asset detail
useTransactions()        // Transaction list
useCrypto()              // Crypto portfolio
usePrices()              // Historical prices
useRealtimePrices()      // Real-time updates
useBenchmark()           // Benchmark management
```

### API Client (`lib/api.ts`)

```typescript
// Base URL from environment
NEXT_PUBLIC_API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api"

// Axios instance
- 30 second timeout
- Type-safe requests/responses
- Custom ApiError class for error handling
```

### Styling

- **Tailwind CSS** - Utility-first CSS framework
- **Recharts** - Data visualization library
- **Radix UI** - Headless UI components for accessibility

---

## Database Schema

### Architecture Decisions

1. **ISIN-based**: Primary identifier for securities (12-character standard)
2. **Deduplication**: SHA256 hash prevents duplicate transactions
3. **Async/Await**: SQLAlchemy 2.0 async support for FastAPI
4. **Composite Indexes**: Common query patterns indexed (ticker+date, type+date)
5. **JSON Metrics**: Flexible cached_metrics table for various calculation types
6. **Dual Sessions**: Async for FastAPI, sync for Celery

### Core Tables

**transactions** - Transaction records
- Primary key: id
- Indexes: (ticker, date), (type, date), (operation_date)
- Unique: transaction_hash per user

**positions** - Current holdings
- Primary key: id
- Indexes: ticker, ISIN
- One per security

**price_history** - Historical OHLCV
- Primary key: (ticker, date)
- Indexes: ticker, date
- One record per day per ticker

**portfolio_snapshots** - Daily snapshots
- Primary key: (user_id, snapshot_date)
- Used for performance charts

**crypto_portfolios** - Crypto holdings containers
- Primary key: id
- Indexes: user_id
- Supports multiple portfolios per user

**crypto_transactions** - Crypto trades
- Primary key: id
- Foreign key: crypto_portfolio_id
- Indexes: (portfolio_id, date)

**cached_metrics** - Performance metrics cache
- Primary key: (metric_type, metric_key)
- TTL-based expiration
- Stores: IRR, TWR, portfolio returns

**benchmarks** - Portfolio benchmarks
- Primary key: id
- One active benchmark per user
- Stores: ticker, description

---

## Configuration

### Environment Variables

All configuration is managed through environment variables in `docker-compose.yml`:

```yaml
# Database
DATABASE_URL: postgresql://portfolio:portfolio@postgres:5432/portfolio_db

# Cache & Queue
REDIS_URL: redis://redis:6379/0
CELERY_BROKER_URL: redis://redis:6379/0
CELERY_RESULT_BACKEND: redis://redis:6379/0

# Application
ENVIRONMENT: production
LOG_LEVEL: INFO
TIMEZONE: Europe/Rome

# Frontend
NEXT_PUBLIC_API_URL: http://localhost:8000/api
NODE_ENV: production

# Allowed Origins (CORS)
ALLOWED_ORIGINS: '["http://localhost:3000", "http://localhost"]'

# Optional: External APIs
COINGECKO_API_KEY: your_api_key_here  # For higher rate limits
```

### Modifying Configuration

Edit `docker-compose.yml` environment sections, then:
```bash
docker compose up --build
```

---

## Testing

### Backend Testing

```bash
# Run all tests
docker compose exec backend pytest

# Run specific test file
docker compose exec backend pytest tests/test_transactions.py

# Run with coverage
docker compose exec backend pytest --cov=app tests/

# Run specific test
docker compose exec backend pytest tests/test_transactions.py::test_import_csv
```

### Frontend Testing

```bash
# Jest/React Testing Library
docker compose exec frontend npm run test

# With coverage
docker compose exec frontend npm run test:coverage
```

### Health Checks

```bash
# Backend health
curl http://localhost:8000/api/health

# Celery worker health
docker compose exec celery-worker celery -A app.celery_app inspect ping

# Celery beat status
docker compose logs celery-beat | tail -20

# Database health
docker compose exec postgres pg_isready -U portfolio

# Redis health
docker compose exec redis redis-cli ping
```

### API Documentation

Interactive API docs available at: `http://localhost:8000/docs` (Swagger UI)

---

## Debugging

### Backend Debugging

```bash
# View backend logs
docker compose logs -f backend

# Inspect database
docker compose exec postgres psql -U portfolio portfolio_db

# Query specific table
docker compose exec postgres psql -U portfolio portfolio_db -c "SELECT * FROM transactions LIMIT 5;"

# Check Redis
docker compose exec redis redis-cli
redis-cli> KEYS *
redis-cli> GET key_name
```

### Celery Debugging

```bash
# Monitor worker tasks
docker compose logs -f celery-worker

# Monitor scheduler
docker compose logs -f celery-beat

# Inspect Celery tasks
docker compose exec celery-worker celery -A app.celery_app inspect active

# Check task queue length
docker compose exec redis redis-cli LLEN celery
```

### Frontend Debugging

```bash
# View frontend logs
docker compose logs -f frontend

# Browser DevTools
- Open http://localhost:3000
- F12 to open DevTools
- Console, Network, Sources tabs for debugging
```

### Database Migrations

```bash
# Create new migration
docker compose exec backend alembic revision --autogenerate -m "description"

# Apply migrations
docker compose exec backend alembic upgrade head

# View migration history
docker compose exec backend alembic history

# Rollback one migration
docker compose exec backend alembic downgrade -1

# Rollback to specific revision
docker compose exec backend alembic downgrade <revision_id>
```

---

## Troubleshooting

### Services Not Starting

```bash
# Check which service failed
docker compose ps

# View logs for failed service
docker compose logs backend
docker compose logs celery-worker
docker compose logs celery-beat
docker compose logs postgres

# Common causes:
# - Port conflicts (3000, 8000)
# - Database not ready (wait 10-15 seconds)
# - Redis connection timeout
# - Dependency health checks failing
```

### Port Conflicts

```bash
# Find process using port 3000 or 8000
lsof -i :3000
lsof -i :8000

# Edit docker-compose.yml ports section
frontend:
  ports:
    - "127.0.0.1:3001:3000"  # Change to 3001

backend:
  ports:
    - "127.0.0.1:8001:8000"  # Change to 8001

# Update frontend environment
NEXT_PUBLIC_API_URL=http://localhost:8001/api
```

### Database Connection Errors

```bash
# Check PostgreSQL is healthy
docker compose exec postgres pg_isready -U portfolio

# Verify credentials in docker-compose.yml
DATABASE_URL: postgresql://portfolio:portfolio@postgres:5432/portfolio_db

# Reset database (WARNING: deletes all data)
docker compose down -v
docker compose up -d
docker compose exec backend alembic upgrade head
```

### Celery Tasks Not Running

```bash
# Check celery-worker is running
docker compose logs celery-worker | tail -30

# Check celery-beat scheduler
docker compose logs celery-beat | tail -30

# Verify Redis connection
docker compose exec redis redis-cli ping

# Restart celery services
docker compose restart celery-worker celery-beat
```

### Price Updates Failing

```bash
# Test Yahoo Finance
docker compose exec backend python -c "import yfinance; print(yfinance.Ticker('AAPL').info['currentPrice'])"

# Test CoinGecko API
docker compose exec backend python -c "from app.services.price_fetcher import fetch_current_prices; print(fetch_current_prices(['BTC']))"

# Check rate limits
docker compose logs backend | grep -i "rate"

# Add CoinGecko API key if needed
# Edit docker-compose.yml and restart
```

### Frontend Shows Error

```bash
# Check backend connectivity
curl http://localhost:8000/api/health

# View frontend logs
docker compose logs frontend

# Rebuild frontend
docker compose build frontend
docker compose restart frontend

# Check NEXT_PUBLIC_API_URL
docker compose exec frontend printenv | grep API_URL
```

### Out of Memory

```bash
# Check Docker resources
docker stats

# Reduce container memory limit in docker-compose.yml
services:
  backend:
    deploy:
      resources:
        limits:
          memory: 512m

# Restart
docker compose up --build
```

---

## CI/CD Pipeline

### GitHub Actions Workflow

The project uses GitHub Actions to build and push Docker images to GitHub Container Registry (GHCR).

**File:** `.github/workflows/build-and-push.yml`

**Triggers:**
- Push to `main` or `dev` branches
- Pull requests to `main` or `dev`

**Build Jobs (Parallel):**
1. **setup** - Determines image tags and names
2. **lint-backend** - Python linting and pytest
3. **lint-frontend** - ESLint and npm linting
4. **build-backend** - Build `trackfolio-backend` image
5. **build-celery-worker** - Build `trackfolio-celery-worker` image
6. **build-celery-beat** - Build `trackfolio-celery-beat` image
7. **build-frontend** - Build `trackfolio-frontend` image
8. **notify** - Report build status

**Image Tagging:**
- `main` branch: tagged as `latest` + short SHA
- `dev` branch: tagged as `dev` + short SHA
- PRs and other branches: tagged by short SHA

**Multi-Platform Builds:**
- linux/amd64 (x86-64)
- linux/arm64 (ARM v8)

**Cache:**
- GitHub Actions cache (type=gha) for faster rebuilds

---

## Quick Reference

### Important Paths

```
TrackFolio/
├── backend/
│   ├── app/
│   │   ├── api/              # API endpoints (6 modules)
│   │   ├── models/           # Database models (11 models)
│   │   ├── services/         # Business logic (13 services)
│   │   ├── tasks/            # Celery tasks (8 tasks)
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── celery_app.py     # Celery configuration
│   │   ├── main.py           # FastAPI entry point
│   │   └── config.py         # Settings
│   ├── alembic/              # Database migrations
│   ├── Dockerfile            # Backend API image
│   ├── Dockerfile.celery-worker
│   ├── Dockerfile.celery-beat
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/              # Next.js pages
│   │   ├── components/       # React components
│   │   ├── lib/              # Utilities and API client
│   │   └── styles/           # Global styles
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
├── CLAUDE.md                 # This file
├── README.md                 # User guide
├── API.md                    # API documentation
└── FEATURES.md               # Feature documentation
```

### Development Checklist

Before committing code:
- [ ] Run linters: `npm run lint` (frontend), `flake8` (backend)
- [ ] Run tests: `pytest` (backend), `npm test` (frontend)
- [ ] Update CHANGELOG if significant changes
- [ ] Add database migration if models changed
- [ ] Test locally: `docker compose up --build`
- [ ] Check logs: `docker compose logs -f`

---

## Support & Resources

- **API Documentation**: http://localhost:8000/docs (when running)
- **GitHub Issues**: https://github.com/AxelFooley/TrackFolio/issues
- **Docker Docs**: https://docs.docker.com/
- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **Next.js Docs**: https://nextjs.org/docs
- **SQLAlchemy Docs**: https://docs.sqlalchemy.org/
- **Celery Docs**: https://docs.celeryproject.io/
- after making changes, before committing, always validate your solution by running the exact same tests that the github workflow is doing in CI. Only commit when all containers linting job pass with no issues.
- when implementing a change in the existing code, always search for duplicated code elsehwere and clean it up.