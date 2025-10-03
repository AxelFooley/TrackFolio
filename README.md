# TrackFolio - Portfolio Tracker

A self-hosted, privacy-focused investment portfolio tracker with advanced performance analytics, TWR/IRR calculations, and comprehensive cryptocurrency support.

## Features

- **Multi-Asset Support**: Track stocks, ETFs, bonds, and cryptocurrencies in a unified portfolio
- **Advanced Performance Metrics**:
  - Time-Weighted Return (TWR) for fair performance comparison
  - Internal Rate of Return (IRR) for personal returns including cash flows
  - Sector and currency breakdown analysis
- **Automated Price Updates**: Daily market data synchronization via CoinGecko and Yahoo Finance APIs
- **Benchmark Comparison**: Compare your portfolio against market indices (S&P 500, NASDAQ, etc.)
- **Daily Snapshots**: Historical tracking of portfolio value and composition
- **CSV Import**: Easy transaction import from broker statements
- **Privacy-First**: Self-hosted, runs entirely on your local machine, no data sharing

## Prerequisites

- Docker (version 20.10 or higher)
- Docker Compose (version 2.0 or higher)
- 2GB RAM minimum
- 5GB disk space

## Quick Start

1. Clone this repository:
```bash
git clone <repository-url>
cd TrackFolio-pub
```

2. Start the application:
```bash
./start.sh
```

That's it! The script will:
- Build all Docker images
- Start all services (PostgreSQL, Redis, Backend, Frontend, Celery workers)
- Run database migrations
- Create an initial portfolio snapshot

3. Access the application:
   - **Frontend**: http://localhost:3000
   - **API Documentation**: http://localhost:8000/docs
   - **Health Check**: http://localhost:8000/api/health

## Manual Setup (Without start.sh)

If you prefer manual control:

```bash
# Build all images
docker-compose build

# Start services
docker-compose up -d

# Wait for database to be ready
sleep 10

# Run migrations
docker-compose exec backend alembic upgrade head

# Check status
docker-compose ps
```

## Configuration

All configuration is managed through docker-compose.yml environment variables. Key settings:

- **Database**: PostgreSQL 15 with persistent volume
- **Cache**: Redis 7 for Celery task queue
- **Timezone**: Europe/Rome (configurable in docker-compose.yml)
- **Ports**: Frontend on 127.0.0.1:3000, Backend on 127.0.0.1:8000 (localhost-only for security)
- **Reverse Proxy**: Not included - add your own (nginx, traefik, caddy) if desired

### External API Keys (Optional)

For higher rate limits on cryptocurrency price data:

1. Get a free API key from [CoinGecko](https://www.coingecko.com/en/api)
2. Add to docker-compose.yml under backend environment:
   ```yaml
   COINGECKO_API_KEY: your_api_key_here
   ```
3. Restart services: `docker-compose restart backend`

## Usage Guide

### 1. Import Transactions

Go to **Import** page and upload your CSV file containing:
- Date
- Asset (ticker symbol or name)
- Type (BUY/SELL/DIVIDEND/FEE)
- Quantity
- Price
- Currency

Supported CSV formats:
- Standard format: `date,asset,type,quantity,price,currency`
- Broker-specific formats (Fineco, Degiro, etc.) - will be auto-detected

### 2. Configure Benchmark (Optional)

Go to **Settings** and configure your benchmark index:
- Select index (S&P 500, NASDAQ, FTSE 100, etc.)
- Set start date
- Choose comparison currency

### 3. View Performance

- **Dashboard**: Portfolio overview with key metrics
- **Holdings**: Current positions and allocations
- **Asset Detail**: Individual asset performance and transactions
- **Charts**: Historical value, returns, sector breakdown

### 4. Monitor Background Jobs

Daily scheduled tasks (Europe/Rome timezone):
- **23:00** - Update prices from market APIs
- **23:15** - Calculate portfolio metrics (IRR, TWR)
- **23:30** - Create daily snapshot

Check Celery logs:
```bash
docker-compose logs -f celery-worker
docker-compose logs -f celery-beat
```

## Architecture

```
    ┌────────────────────┐              ┌─────────────────────┐
    │  Frontend (Next.js)│              │ Backend (FastAPI)   │
    │  Port 3000         │─────────────▶│ Port 8000           │
    │  React + TypeScript│              │ Python + SQLAlchemy │
    └────────────────────┘              └──────────┬──────────┘
                                                   │
              ┌────────────────────────────────────┼─────────────────────┐
              │                                    │                     │
    ┌─────────▼──────────┐            ┌───────────▼─────────┐  ┌───────▼────────┐
    │ PostgreSQL 15      │            │    Redis 7          │  │ Celery Workers │
    │ (Portfolio Data)   │            │ (Task Queue)        │  │ (Background Jobs)│
    └────────────────────┘            └─────────────────────┘  └────────────────┘
```

### Services

1. **postgres**: PostgreSQL database for portfolio data
2. **redis**: Redis cache and Celery message broker
3. **backend**: FastAPI REST API (port 8000)
4. **celery-worker**: Background task processor
5. **celery-beat**: Task scheduler
6. **frontend**: Next.js React application (port 3000)

**Note**: No reverse proxy is included. Add your own (nginx, traefik, caddy) if you want unified routing or SSL.

## Development Setup

To run without Docker for development:

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL=postgresql://portfolio:portfolio@localhost:5432/portfolio_db
export REDIS_URL=redis://localhost:6379/0

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install

# Set environment variables
echo "NEXT_PUBLIC_API_URL=http://localhost:8000/api" > .env.local

# Start development server
npm run dev
```

## Database Migrations

Create a new migration:
```bash
docker-compose exec backend alembic revision --autogenerate -m "description"
```

Apply migrations:
```bash
docker-compose exec backend alembic upgrade head
```

Rollback:
```bash
docker-compose exec backend alembic downgrade -1
```

## Backup and Restore

### Backup Database

```bash
# Create backup directory
mkdir -p backups

# Backup PostgreSQL database
docker-compose exec -T postgres pg_dump -U portfolio portfolio_db | gzip > backups/portfolio_$(date +%Y%m%d_%H%M%S).sql.gz
```

### Restore Database

```bash
# Stop backend services
docker-compose stop backend celery-worker celery-beat

# Restore database
gunzip -c backups/portfolio_YYYYMMDD_HHMMSS.sql.gz | docker-compose exec -T postgres psql -U portfolio -d portfolio_db

# Restart services
docker-compose start backend celery-worker celery-beat
```

### Backup Schedule

Recommended: Set up a daily cron job:
```bash
0 2 * * * cd /path/to/TrackFolio-pub && ./backup.sh
```

## Troubleshooting

### Services Not Starting

Check logs:
```bash
docker-compose logs -f
```

Check specific service:
```bash
docker-compose logs -f backend
```

### Port Conflicts

If port 3000 or 8000 is already in use, edit docker-compose.yml:
```yaml
frontend:
  ports:
    - "127.0.0.1:3001:3000"  # Change external port to 3001

backend:
  ports:
    - "127.0.0.1:8001:8000"  # Change external port to 8001
```

Then access at http://localhost:3001 and update NEXT_PUBLIC_API_URL accordingly.

### Database Connection Errors

Ensure PostgreSQL is healthy:
```bash
docker-compose exec postgres pg_isready -U portfolio
```

Reset database:
```bash
docker-compose down -v  # WARNING: Deletes all data
docker-compose up -d
docker-compose exec backend alembic upgrade head
```

### Celery Tasks Not Running

Check Celery worker:
```bash
docker-compose logs celery-worker
docker-compose logs celery-beat
```

Restart Celery:
```bash
docker-compose restart celery-worker celery-beat
```

### Frontend Shows Error

Check backend connection:
```bash
curl http://localhost:8000/api/health
```

Rebuild frontend:
```bash
docker-compose build frontend
docker-compose restart frontend
```

### Price Updates Failing

Check API connectivity:
```bash
docker-compose exec backend python -c "import yfinance; print(yfinance.Ticker('AAPL').info['currentPrice'])"
```

If CoinGecko API fails, check rate limits or add API key.

## Common Commands

```bash
# View all services
docker-compose ps

# View logs
docker-compose logs -f

# Restart a service
docker-compose restart backend

# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: deletes data)
docker-compose down -v

# Rebuild after code changes
docker-compose build
docker-compose up -d

# Execute command in backend
docker-compose exec backend python manage.py

# Access database shell
docker-compose exec postgres psql -U portfolio portfolio_db

# Access Redis CLI
docker-compose exec redis redis-cli
```

## Tech Stack

### Backend
- **FastAPI**: Modern, fast Python web framework
- **SQLAlchemy**: SQL ORM
- **Alembic**: Database migrations
- **Celery**: Distributed task queue
- **Redis**: Cache and message broker
- **PostgreSQL**: Relational database
- **yfinance**: Stock price data
- **CoinGecko API**: Cryptocurrency price data

### Frontend
- **Next.js 14**: React framework with App Router
- **TypeScript**: Type-safe JavaScript
- **TanStack Query**: Data fetching and caching
- **Recharts**: Data visualization
- **Tailwind CSS**: Utility-first CSS
- **Radix UI**: Headless UI components

### DevOps
- **Docker**: Containerization
- **Docker Compose**: Multi-container orchestration

## Security Notes

- Application binds to **127.0.0.1** (localhost only) - NOT accessible from internet
  - Frontend: 127.0.0.1:3000
  - Backend: 127.0.0.1:8000
- No authentication required (designed for single-user local deployment)
- To expose publicly:
  - Add a reverse proxy (nginx, traefik, caddy) with SSL
  - Add authentication middleware
  - Use strong database passwords
- Database password is simple because it's not internet-facing
- For production internet deployment, use strong passwords and enable HTTPS

## Performance

- **Startup Time**: ~30 seconds for all services
- **Memory Usage**: ~800MB total
- **Disk Usage**: ~500MB + portfolio data
- **API Response**: <100ms average
- **Price Updates**: ~1-2 minutes for 50 assets

## License

This project is private and proprietary.

## Contributing

This is a private project. Contact the repository owner for contribution guidelines.

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review logs: `docker-compose logs -f`
3. Open an issue on the repository

## Roadmap

- [ ] Mobile-responsive design improvements
- [ ] Export portfolio to PDF report
- [ ] Tax loss harvesting calculator
- [ ] Multi-currency support enhancements
- [ ] Real-time price updates via WebSocket
- [ ] Asset allocation rebalancing suggestions
