#!/bin/bash

# Portfolio Tracker - One-Command Deployment Script
# This script builds and starts all services, runs migrations, and creates initial data

set -e  # Exit on error

echo "======================================"
echo "Portfolio Tracker - Starting Deployment"
echo "======================================"
echo ""

# Stop any existing containers
echo "[1/7] Stopping existing containers..."
docker-compose down 2>/dev/null || true
echo "✓ Stopped"
echo ""

# Build Docker images
echo "[2/7] Building Docker images..."
docker-compose build
echo "✓ Built"
echo ""

# Start services
echo "[3/7] Starting services..."
docker-compose up -d
echo "✓ Started"
echo ""

# Wait for PostgreSQL to be ready
echo "[4/7] Waiting for database to be ready..."
for i in {1..30}; do
    if docker-compose exec -T postgres pg_isready -U portfolio >/dev/null 2>&1; then
        echo "✓ Database ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "✗ Database failed to start after 30 seconds"
        exit 1
    fi
    echo "   Waiting... ($i/30)"
    sleep 1
done
echo ""

# Run database migrations
echo "[5/7] Running database migrations..."
docker-compose exec -T backend alembic upgrade head
echo "✓ Migrations applied"
echo ""

# Create initial daily snapshot
echo "[6/7] Creating initial portfolio snapshot..."
docker-compose exec -T backend python -c "
from app.tasks.snapshots import create_daily_snapshot
try:
    create_daily_snapshot()
    print('✓ Initial snapshot created')
except Exception as e:
    print(f'Note: Could not create initial snapshot (this is normal if portfolio is empty): {e}')
" || echo "   (Skipped - portfolio may be empty)"
echo ""

# Display service status
echo "[7/7] Checking service status..."
echo ""
docker-compose ps
echo ""

# Display success message
echo "======================================"
echo "✓ Portfolio Tracker is ready!"
echo "======================================"
echo ""
echo "Access the application:"
echo "  - Frontend:  http://localhost:3000"
echo "  - API Docs:  http://localhost:8000/docs"
echo "  - Health:    http://localhost:8000/api/health"
echo ""
echo "Useful commands:"
echo "  - View logs:        docker-compose logs -f"
echo "  - Stop services:    docker-compose down"
echo "  - Restart:          docker-compose restart"
echo "  - View status:      docker-compose ps"
echo ""
echo "Background jobs schedule (Europe/Rome timezone):"
echo "  - 23:00 - Update prices from market APIs"
echo "  - 23:15 - Calculate portfolio metrics (IRR, returns)"
echo "  - 23:30 - Create daily portfolio snapshot"
echo ""
echo "Next steps:"
echo "  1. Open http://localhost:3000 in your browser"
echo "  2. Import your transaction CSV file"
echo "  3. Configure your benchmark (optional)"
echo "  4. View your portfolio performance"
echo ""
echo "Note: Add your own reverse proxy (nginx, traefik, etc.) if desired"
echo ""
