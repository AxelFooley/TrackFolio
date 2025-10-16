# TrackFolio - Portfolio Tracker

A self-hosted, privacy-focused investment portfolio tracker with advanced performance analytics, TWR/IRR calculations, blockchain wallet sync, cryptocurrency support, and comprehensive stock tracking.

## Features

### Core Portfolio Management
- **Multi-Asset Support**: Track stocks, ETFs, bonds, and cryptocurrencies in a unified portfolio
- **ISIN-Based Architecture**: International Securities Identification Number (12-char) as primary asset identifier
- **Transaction Management**: Import from broker CSVs or add transactions manually
- **Deduplication**: Automatic detection and prevention of duplicate transactions
- **Multi-Currency Support**: Handle transactions in EUR, USD, and other currencies with automatic conversion

### Advanced Performance Metrics
- **Time-Weighted Return (TWR)**: Fair performance comparison independent of cash flows
- **Internal Rate of Return (IRR)**: Personal returns including all cash flows
- **Sector Analysis**: Automatic sector categorization and breakdown
- **Currency Breakdown**: View portfolio composition by currency
- **Benchmark Comparison**: Compare portfolio performance against market indices (S&P 500, NASDAQ, etc.)
- **Daily Snapshots**: Historical tracking of portfolio value and composition for performance charting

### Cryptocurrency Features
- **Crypto Portfolio Management**: Separate crypto trading portfolios with independent tracking
- **Cryptocurrency Support**: Full support for Bitcoin, Ethereum, and 5000+ cryptocurrencies via CoinGecko
- **Blockchain Wallet Sync**: Automatic Bitcoin wallet address tracking and synchronization
- **Wallet Transaction Monitoring**: Track Bitcoin transactions in real-time (every 30 minutes)
- **Multi-Exchange Support**: Track holdings from multiple crypto exchanges
- **High-Precision Calculations**: 8-decimal precision for crypto amounts
- **Crypto Price History**: Complete historical pricing data for technical analysis

### Automated Data Updates
- **Daily Price Updates**: Market data synchronization via Yahoo Finance (23:00 CET daily)
- **Crypto Price Updates**: Real-time cryptocurrency prices updated every 5 minutes
- **Blockchain Sync**: Bitcoin wallet transactions synced every 30 minutes
- **Automatic Calculations**: Portfolio metrics calculated daily at 23:15 CET
- **Daily Portfolio Snapshots**: Historical snapshots created at 23:30 CET daily

### Stock & Asset Intelligence
- **Stock Split Detection**: Automatic detection and handling of stock splits with ticker evolution tracking
- **Forex Conversion**: Real-time EUR/USD exchange rate integration
- **Price History**: Complete OHLCV (Open, High, Low, Close, Volume) data for all assets
- **Asset Search**: Quick ticker and ISIN lookup

### Privacy & Security
- **Self-Hosted**: Runs entirely on your local machine, no data sharing
- **Localhost Only**: All services bind to 127.0.0.1 (not accessible from internet by default)
- **No Authentication Required**: Single-user local deployment (add your own reverse proxy for internet deployment)
- **Data Ownership**: You own and control 100% of your financial data

### User Experience
- **Web Dashboard**: Modern React interface with real-time updates
- **CSV Import**: Easy transaction import from broker statements (Directa format supported)
- **Holdings Overview**: Current positions with allocation percentages and real-time changes
- **Asset Details**: Individual asset performance, price charts, and full transaction history
- **Settings Panel**: Customize benchmark selection and application preferences

---

## Prerequisites

- **Docker** (version 20.10 or higher)
- **Docker Compose** (version 2.0 or higher)
- **2GB RAM** minimum (4GB recommended for smooth performance)
- **5GB disk space** (for database and price history)

---

## Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/AxelFooley/TrackFolio.git
cd TrackFolio
```

### 2. Start Application

```bash
# Using deployment script (recommended)
./start.sh

# Or manually with Docker Compose
docker compose up --build
```

The script will:
- Build all 4 Docker images (backend, celery-worker, celery-beat, frontend)
- Start all services (PostgreSQL, Redis, Backend, Frontend, Celery workers)
- Run database migrations
- Create initial portfolio snapshot

### 3. Access Application

Once all services are running (~30 seconds):
- **Frontend**: http://localhost:3000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/health

---

## Manual Setup (Without start.sh)

If you prefer manual control:

```bash
# Build all Docker images
docker compose build

# Start services
docker compose up -d

# Wait for database to be ready
sleep 10

# Run database migrations
docker compose exec backend alembic upgrade head

# Check service status
docker compose ps
```

---

## Configuration

### Environment Variables

All configuration is managed through `docker-compose.yml` environment variables:

**Core Settings:**
- `ENVIRONMENT`: production/development
- `LOG_LEVEL`: INFO (default), DEBUG for troubleshooting
- `TIMEZONE`: Europe/Rome (adjust as needed)

**Database:**
- `DATABASE_URL`: PostgreSQL connection (default: `postgresql://portfolio:portfolio@postgres:5432/portfolio_db`)
- `REDIS_URL`: Redis connection (default: `redis://redis:6379/0`)

**External APIs:**
- `COINGECKO_API_KEY`: Optional CoinGecko API key for higher cryptocurrency rate limits
  - Get free key from: https://www.coingecko.com/en/api

**Frontend:**
- `NEXT_PUBLIC_API_URL`: API base URL (default: `http://localhost:8000/api`)

**Blockchain (Bitcoin Wallet Sync):**
- `BLOCKCHAIN_SYNC_ENABLED`: Enable/disable wallet sync (default: true)
- `BLOCKCHAIN_SYNC_INTERVAL_MINUTES`: Sync interval (default: 30 minutes)

### Modifying Configuration

1. Edit `docker-compose.yml` environment sections
2. Rebuild and restart:
   ```bash
   docker compose up --build
   ```

---

## Usage Guide

### 1. Import Transactions

Navigate to **Import** page and upload CSV file with:
- Date
- Asset (ticker symbol or ISIN)
- Type (BUY/SELL/DIVIDEND/FEE)
- Quantity
- Price
- Currency

**Supported CSV Formats:**
- Standard: `date,asset,type,quantity,price,currency`
- Directa broker format (auto-detected)
- Other broker formats (Fineco, Degiro, etc.) - will be auto-detected

### 2. Configure Portfolio Benchmark (Optional)

Go to **Settings** and configure:
- Select benchmark index (S&P 500, NASDAQ, FTSE 100, Euro Stoxx 50, etc.)
- Set start date for comparison
- Choose comparison currency

### 3. Add Crypto Portfolio (Optional)

Go to **Crypto** section to:
- Create new crypto portfolio
- Configure wallet addresses for blockchain sync
- Import crypto transactions manually
- Track holdings and performance

### 4. Configure Wallet Sync (Optional)

For Bitcoin wallet tracking:
1. Navigate to **Crypto** > Select Portfolio > **Settings**
2. Enter your Bitcoin address (P2PKH, P2SH, or Bech32 format)
3. Save configuration
4. Wallet transactions will sync automatically every 30 minutes

### 5. View Portfolio Performance

**Dashboard Page:**
- Portfolio overview with key metrics
- Total value, cost basis, profit/loss
- Today's performance
- Top gainers/losers

**Holdings Page:**
- Current positions table
- Allocation percentages
- Real-time price changes
- Sector breakdown

**Asset Detail Page:**
- Individual asset performance
- Price chart with historical data
- Full transaction history
- Average cost and position size

**Crypto Pages:**
- Crypto portfolio holdings
- Individual crypto asset details
- Transaction history
- Wallet sync status

### 6. Monitor Background Jobs

Daily scheduled tasks (Europe/Rome timezone):
- **23:00** - Update traditional asset prices from Yahoo Finance
- **23:15** - Calculate portfolio metrics (IRR, TWR, etc.)
- **23:30** - Create daily portfolio snapshot
- Every **5 minutes** - Update cryptocurrency prices
- Every **30 minutes** - Sync Bitcoin wallet transactions

View logs:
```bash
docker compose logs -f celery-worker
docker compose logs -f celery-beat
```

---

## Architecture

```
    ┌─────────────────────┐
    │ Frontend (Next.js)  │
    │ http://localhost:3000
    └──────────┬──────────┘
               │
               │ HTTP/REST
               ▼
    ┌─────────────────────┐
    │ Backend (FastAPI)   │
    │ http://localhost:8000
    └──────────┬──────────┘
               │
    ┌──────────┼─────────────────┬──────────────┐
    │          │                 │              │
    ▼          ▼                 ▼              ▼
┌─────┐   ┌─────┐           ┌────────┐   ┌──────────┐
│  DB │   │Redis│           │ Celery │   │ Celery   │
│     │   │     │           │ Worker │   │  Beat    │
└─────┘   └─────┘           └────────┘   └──────────┘
  PG15     Cache                Jobs        Scheduler
  DB       Queue
```

### Services

1. **PostgreSQL 15** - Portfolio data storage
   - User: `portfolio`, Password: `portfolio`
   - Persistent volume: `portfolio_postgres_data`

2. **Redis 7** - Cache and Celery message broker
   - Append-only file (AOF) persistence
   - Persistent volume: `portfolio_redis_data`

3. **FastAPI Backend** - REST API server
   - Port: 127.0.0.1:8000 (localhost only)
   - Health check: `/api/health`

4. **Celery Worker** - Background task processor
   - Solo pool (prevents issues with concurrent HTTP libraries)
   - Processes price updates, metric calculations, blockchain sync

5. **Celery Beat** - Task scheduler
   - RedBeat scheduler for Redis-backed persistence
   - Schedules all background jobs

6. **Next.js Frontend** - React user interface
   - Port: 127.0.0.1:3000 (localhost only)
   - Real-time data updates via React Query

---

## Data Integration

### Price Data Sources

- **Yahoo Finance** (via yfinance library)
  - Stocks, ETFs, bonds
  - Free tier (no API key required)
  - Updated daily at 23:00 CET

- **CoinGecko API**
  - 5000+ cryptocurrencies
  - Free tier: 10-50 calls/min
  - Paid tier: Higher rate limits
  - Updated every 5 minutes

- **Blockchain APIs** (Bitcoin wallet sync)
  - Blockstream API (primary)
  - Blockchain.com API (fallback)
  - BlockCypher API (secondary fallback)
  - Updated every 30 minutes

### Database Schema

- **ISIN-based**: All securities identified by 12-character ISIN
- **Transaction Deduplication**: SHA256 hash prevents duplicate imports
- **Multi-Currency**: EUR, USD, and other currencies with exchange rates
- **Performance Metrics**: Cached IRR, TWR, returns (TTL-based expiration)
- **Historical Snapshots**: Daily portfolio snapshots for charting

---

## Common Tasks

### View Service Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend
docker compose logs -f celery-worker
docker compose logs -f celery-beat
docker compose logs -f frontend
docker compose logs -f postgres
docker compose logs -f redis
```

### Restart a Service

```bash
docker compose restart backend
docker compose restart celery-worker
docker compose restart celery-beat
docker compose restart frontend
```

### Check Service Status

```bash
docker compose ps
```

### Stop All Services

```bash
docker compose down
```

### Stop and Remove All Data (WARNING)

```bash
# Delete database and cache volumes
docker compose down -v

# Restart fresh
docker compose up --build
```

### Execute Commands in Containers

```bash
# Backend shell
docker compose exec backend /bin/bash

# Database shell
docker compose exec postgres psql -U portfolio portfolio_db

# Redis CLI
docker compose exec redis redis-cli

# Frontend shell
docker compose exec frontend /bin/bash
```

---

## Database Backup & Restore

### Create Backup

```bash
mkdir -p backups

# Backup PostgreSQL database
docker compose exec -T postgres pg_dump -U portfolio portfolio_db | gzip > backups/portfolio_$(date +%Y%m%d_%H%M%S).sql.gz
```

### Restore Backup

```bash
# Stop backend services
docker compose stop backend celery-worker celery-beat

# Restore from backup
gunzip -c backups/portfolio_YYYYMMDD_HHMMSS.sql.gz | docker compose exec -T postgres psql -U portfolio -d portfolio_db

# Restart services
docker compose start backend celery-worker celery-beat
```

### Automated Daily Backup (Linux/Mac)

Add to crontab:
```bash
# Backup at 2:00 AM daily
0 2 * * * cd /path/to/TrackFolio && mkdir -p backups && docker compose exec -T postgres pg_dump -U portfolio portfolio_db | gzip > backups/portfolio_$(date +\%Y\%m\%d_\%H\%M\%S).sql.gz
```

---

## Troubleshooting

### Services Not Starting

```bash
# Check which service failed
docker compose ps

# View logs
docker compose logs backend    # or other service name

# Common issues:
# - Port 3000 or 8000 already in use
# - Database not ready (wait 15 seconds)
# - Docker daemon not running
# - Insufficient disk space
```

### Port Conflicts

If ports 3000 or 8000 are already in use:

```bash
# Find process using port
lsof -i :3000
lsof -i :8000

# Edit docker-compose.yml
frontend:
  ports:
    - "127.0.0.1:3001:3000"  # Change to 3001

backend:
  ports:
    - "127.0.0.1:8001:8000"  # Change to 8001

# Update frontend environment
NEXT_PUBLIC_API_URL: http://localhost:8001/api

# Restart
docker compose up --build
```

### Database Connection Errors

```bash
# Check PostgreSQL is healthy
docker compose exec postgres pg_isready -U portfolio

# View database logs
docker compose logs postgres

# Reset database (WARNING: deletes all data)
docker compose down -v
docker compose up -d
sleep 10
docker compose exec backend alembic upgrade head
```

### Celery Tasks Not Running

```bash
# Check worker logs
docker compose logs celery-worker | tail -50

# Check scheduler logs
docker compose logs celery-beat | tail -50

# Verify Redis
docker compose exec redis redis-cli ping

# Restart Celery services
docker compose restart celery-worker celery-beat
```

### Price Updates Failing

```bash
# Test Yahoo Finance
docker compose exec backend python -c "import yfinance; print(yfinance.Ticker('AAPL').info['currentPrice'])"

# Test CoinGecko
curl "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"

# Check rate limits
docker compose logs backend | grep -i "rate"

# Check API connectivity
docker compose exec backend python -c "import requests; print(requests.get('https://query1.finance.yahoo.com/v7/finance/quote?symbols=AAPL').status_code)"
```

### Frontend Shows Error

```bash
# Test backend connectivity
curl http://localhost:8000/api/health

# Check frontend logs
docker compose logs frontend

# Verify API URL
docker compose exec frontend printenv | grep API_URL

# Rebuild frontend
docker compose build frontend
docker compose restart frontend
```

### Wallet Sync Not Working

```bash
# Check blockchain service logs
docker compose logs backend | grep -i blockchain

# Verify Bitcoin address format (P2PKH, P2SH, or Bech32)
# Example: 1A1z7agoat3oWVoVQVe4FDvQA9vxL5b4s

# Check blockchain API connectivity
curl https://blockstream.info/api/address/1A1z7agoat3oWVoVQVe4FDvQA9vxL5b4s

# View wallet sync status in API
curl http://localhost:8000/api/blockchain/status
```

### Out of Memory

```bash
# Check Docker resource usage
docker stats

# Stop services
docker compose down

# Check available system memory
free -h  # Linux
vm_stat  # Mac

# Limit container memory in docker-compose.yml
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

## Tech Stack

### Backend
- **FastAPI** 0.100+ - Modern Python web framework
- **SQLAlchemy 2.0** - SQL ORM with async support
- **Alembic** - Database migrations
- **Celery** - Distributed task queue
- **Redis** - Cache and message broker
- **PostgreSQL** 15 - Relational database
- **Pydantic** - Data validation
- **yfinance** - Yahoo Finance price data
- **CoinGecko API** - Cryptocurrency data
- **Blockstream/Blockchain.com** - Bitcoin wallet data

### Frontend
- **Next.js 14** - React framework with App Router
- **React 18** - UI library
- **TypeScript** - Type-safe JavaScript
- **TanStack Query** - Data fetching and caching
- **Recharts** - Data visualization
- **Tailwind CSS** - Utility-first CSS framework
- **Radix UI** - Headless UI components
- **Axios** - HTTP client

### DevOps & Infrastructure
- **Docker** - Container runtime
- **Docker Compose** - Multi-container orchestration
- **GitHub Actions** - CI/CD pipeline (builds 4 images for amd64 and arm64)
- **GHCR** - Container registry

---

## Security Considerations

### Current Setup (Local/Single-User)
- ✅ Application binds to 127.0.0.1 (localhost only)
- ✅ Not accessible from internet by default
- ✅ No authentication required (designed for single-user)
- ✅ Simple database credentials (not exposed on network)
- ✅ You own and control all data

### For Internet Deployment
To expose TrackFolio to the internet, you MUST add:
1. **Reverse Proxy**: nginx, Traefik, or Caddy with SSL/TLS
2. **Authentication**: Add authentication middleware (OAuth2, etc.)
3. **Strong Credentials**: Use complex passwords for database
4. **HTTPS**: Install SSL certificate
5. **Firewall**: Restrict access to known IPs if possible
6. **Monitoring**: Log all access and changes

**Note:** TrackFolio is not multi-tenant and does not have built-in user management. Each instance is single-user only.

---

## Performance

- **Startup Time**: ~30 seconds for all services
- **Memory Usage**: ~800MB total for all services
- **Disk Usage**: ~500MB + portfolio data
- **API Response**: <100ms average
- **Price Updates**: ~1-2 minutes for 50 assets
- **Blockchain Sync**: ~30 seconds for wallet with 100+ transactions

---

## Development

For development setup and guidelines, see [CLAUDE.md](./CLAUDE.md)

For detailed API documentation, see [API.md](./API.md)

For feature documentation, see [FEATURES.md](./FEATURES.md)

---

## Support

### Troubleshooting
1. Check logs: `docker compose logs -f`
2. Review troubleshooting section above
3. Check GitHub Issues: https://github.com/AxelFooley/TrackFolio/issues

### Resources
- **API Docs**: http://localhost:8000/docs (when running)
- **Docker**: https://docs.docker.com/
- **FastAPI**: https://fastapi.tiangolo.com/
- **Next.js**: https://nextjs.org/docs

---

## License

This project is private and proprietary.

---

## Contributing

This is a private project. Contact the repository owner for contribution guidelines.

---

## Roadmap

- [ ] Mobile-responsive design improvements
- [ ] Export portfolio to PDF report
- [ ] Tax loss harvesting calculator
- [ ] Advanced multi-currency support
- [ ] Real-time price updates via WebSocket
- [ ] Asset allocation rebalancing suggestions
- [ ] Portfolio comparison with peers (anonymized)
- [ ] Performance attribution analysis
- [ ] Email notifications for price alerts
- [ ] API authentication for external integrations
