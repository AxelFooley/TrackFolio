# Portfolio Tracker Deployment Guide

This guide covers various deployment scenarios for the Portfolio Tracker application, from local development to production deployments.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Environment Variables](#environment-variables)
3. [Local Development](#local-development)
4. [Single Host Production](#single-host-production)
5. [Multi-Host Production](#multi-host-production)
6. [External Services](#external-services)
7. [SSL/TLS Configuration](#ssltls-configuration)
8. [Monitoring and Logging](#monitoring-and-logging)
9. [Backup and Recovery](#backup-and-recovery)
10. [Troubleshooting](#troubleshooting)

## Quick Start

### Local Development

```bash
# Clone and start immediately
git clone https://github.com/AxelFooley/TrackFolio.git
cd TrackFolio
docker-compose up --build

# Or use the provided script
./start.sh
```

The application will be available at:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/api/docs

### Production One-Liner

```bash
# Copy environment file and configure
cp .env.prod.example .env
# Edit .env with your actual values

# Start production services
docker-compose -f docker-compose.prod.yml up --build -d
```

## Environment Variables

### Required Variables

| Variable | Description | Example | Default |
|----------|-------------|---------|---------|
| `POSTGRES_PASSWORD` | Database password | `secure_password` | `portfolio` |
| `ALLOWED_ORIGINS` | CORS allowed origins | `["https://yourdomain.com"]` | `["http://localhost:3000"]` |

### Backend Configuration

| Variable | Description | Example | Default |
|----------|-------------|---------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://...` | Auto-generated |
| `REDIS_URL` | Redis connection string | `redis://redis:6379/0` | Auto-generated |
| `CELERY_BROKER_URL` | Celery broker URL | `redis://redis:6379/0` | Auto-generated |
| `CELERY_RESULT_BACKEND` | Celery result backend | `redis://redis:6379/0` | Auto-generated |
| `ENVIRONMENT` | Application environment | `production` | `production` |
| `LOG_LEVEL` | Logging level | `INFO` | `INFO` |
| `SECRET_KEY` | Security secret key | `random_string` | Auto-generated |

### Frontend Configuration

| Variable | Description | Example | Default |
|----------|-------------|---------|---------|
| `BACKEND_API_URL` | Runtime backend URL (server-side) | `http://backend:8000` | `http://backend:8000` |
| `NEXT_PUBLIC_API_URL` | Public API URL (client-side) | `https://api.yourdomain.com/api` | `http://localhost:8000/api` |
| `NODE_ENV` | Node.js environment | `production` | `production` |

### Optional Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `COINGECKO_API_KEY` | CoinGecko API key for higher rate limits | `your_api_key` |
| `NEXT_PUBLIC_GA_ID` | Google Analytics ID | `G-XXXXXXXXXX` |
| `NEXT_PUBLIC_SENTRY_DSN` | Sentry error tracking DSN | `https://your-dsn` |
| `CELERY_WORKER_CONCURRENCY` | Number of Celery worker processes | `4` |
| `CELERY_WORKER_PREFETCH_MULTIPLIER` | Celery prefetch multiplier | `1` |

## Local Development

### Standard Setup

```bash
# Start all services
docker-compose up --build

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f backend
docker-compose logs -f frontend
```

### Development Commands

```bash
# Restart specific service
docker-compose restart backend

# Execute commands in containers
docker-compose exec backend python -c "print('test')"
docker-compose exec postgres psql -U portfolio portfolio_db
docker-compose exec redis redis-cli

# Stop all services
docker-compose down

# Stop and remove volumes (deletes data)
docker-compose down -v
```

### Linting and Code Quality

```bash
# Frontend linting
docker-compose exec frontend npm run lint
docker-compose exec frontend npm run lint:fix

# Backend linting (if configured)
docker-compose exec backend flake8 app --max-line-length=127
docker-compose exec backend pytest
```

## Single Host Production

### Basic Production Setup

```bash
# 1. Copy and configure environment
cp .env.prod.example .env
nano .env  # Edit with your values

# 2. Start production services
docker-compose -f docker-compose.prod.yml up --build -d

# 3. Run database migrations
docker-compose -f docker-compose.prod.yml exec backend alembic upgrade head

# 4. Verify services
docker-compose -f docker-compose.prod.yml ps
docker-compose -f docker-compose.prod.yml logs
```

### Production with Nginx Reverse Proxy

```bash
# 1. Create SSL certificates
mkdir -p nginx/ssl
# Place your cert.pem and key.pem in nginx/ssl/

# 2. Update nginx configuration
nano nginx/nginx.prod.conf  # Update domain names

# 3. Create nginx docker-compose file
cat > docker-compose.nginx.yml << EOF
version: '3.8'

services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.prod.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
    depends_on:
      - frontend
      - backend
    networks:
      - portfolio-network-prod
    restart: always

networks:
  portfolio-network-prod:
    external: true
EOF

# 4. Start all services
docker-compose -f docker-compose.prod.yml -f docker-compose.nginx.yml up -d
```

## Multi-Host Production

### Separate Frontend and Backend Hosts

#### Backend Host Setup

```bash
# On backend server
# 1. Copy and configure environment
cat > .env << EOF
POSTGRES_PASSWORD=secure_password
DATABASE_URL=postgresql://portfolio:secure_password@postgres:5432/portfolio_db
REDIS_URL=redis://redis:6379/0
ALLOWED_ORIGINS=["https://yourdomain.com"]
ENVIRONMENT=production
LOG_LEVEL=INFO
EOF

# 2. Start backend services only
docker-compose -f docker-compose.prod.yml up -d postgres redis backend celery-worker celery-beat

# 3. Run migrations
docker-compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

#### Frontend Host Setup

```bash
# On frontend server
# 1. Configure environment for remote backend
cat > .env << EOF
BACKEND_API_URL=https://api.yourdomain.com
NEXT_PUBLIC_API_URL=https://api.yourdomain.com/api
NODE_ENV=production
EOF

# 2. Create frontend-only docker-compose
cat > docker-compose.frontend.yml << EOF
version: '3.8'

services:
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "127.0.0.1:3000:3000"
    environment:
      BACKEND_API_URL: \${BACKEND_API_URL}
      NEXT_PUBLIC_API_URL: \${NEXT_PUBLIC_API_URL}
      NODE_ENV: production
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
EOF

# 3. Start frontend
docker-compose -f docker-compose.frontend.yml up --build -d
```

## External Services

### External Database

```bash
# 1. Configure environment for external PostgreSQL
cat > .env << EOF
DATABASE_URL=postgresql://username:password@external-db-host:5432/dbname
REDIS_URL=redis://redis:6379/0
# ... other variables
EOF

# 2. Create production compose without database
cat > docker-compose.prod.external.yml << EOF
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    # ... redis configuration

  backend:
    build: ./backend
    environment:
      DATABASE_URL: \${DATABASE_URL}
      REDIS_URL: redis://redis:6379/0
      # ... other configuration
    depends_on:
      - redis

  # ... other services without postgres
EOF

# 3. Start services
docker-compose -f docker-compose.prod.external.yml up -d
```

### External Redis

```bash
# Configure external Redis
DATABASE_URL=postgresql://portfolio:password@postgres:5432/portfolio_db
REDIS_URL=redis://external-redis-host:6379/0
CELERY_BROKER_URL=redis://external-redis-host:6379/0
CELERY_RESULT_BACKEND=redis://external-redis-host:6379/0
```

## SSL/TLS Configuration

### Self-Signed Certificates (Testing)

```bash
# Generate self-signed certificates
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/key.pem \
  -out nginx/ssl/cert.pem \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=yourdomain.com"
```

### Let's Encrypt Certificates

```bash
# 1. Install certbot
sudo apt-get update
sudo apt-get install certbot

# 2. Generate certificates
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com

# 3. Copy certificates to nginx directory
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem nginx/ssl/cert.pem
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem nginx/ssl/key.pem
sudo chown $USER:$USER nginx/ssl/*.pem
```

### Certificate Auto-Renewal

```bash
# Add to crontab for automatic renewal
echo "0 12 * * * /usr/bin/certbot renew --quiet && docker-compose restart nginx" | sudo crontab -
```

## Monitoring and Logging

### Health Checks

```bash
# Check service health
docker-compose -f docker-compose.prod.yml ps

# Check specific service logs
docker-compose -f docker-compose.prod.yml logs -f backend
docker-compose -f docker-compose.prod.yml logs -f celery-worker

# Manual health checks
curl http://localhost:3000/api/health  # Frontend
curl http://localhost:8000/api/health  # Backend
```

### Log Management

```bash
# Configure log rotation
sudo nano /etc/docker/daemon.json

{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}

# Restart Docker daemon
sudo systemctl restart docker
```

### Monitoring Tools

```bash
# Install monitoring stack (optional)
cat > docker-compose.monitoring.yml << EOF
version: '3.8'

services:
  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana
    ports:
      - "3001:3000"
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin
    volumes:
      - grafana_data:/var/lib/grafana

volumes:
  grafana_data:
EOF

docker-compose -f docker-compose.monitoring.yml up -d
```

## Backup and Recovery

### Database Backup

```bash
# Create backup script
cat > backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/backup"
DATE=$(date +%Y%m%d_%H%M%S)
CONTAINER_NAME="portfolio-postgres-prod"

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup database
docker exec $CONTAINER_NAME pg_dump -U portfolio portfolio_db > $BACKUP_DIR/portfolio_db_$DATE.sql

# Compress backup
gzip $BACKUP_DIR/portfolio_db_$DATE.sql

# Remove old backups (keep last 7 days)
find $BACKUP_DIR -name "portfolio_db_*.sql.gz" -mtime +7 -delete

echo "Backup completed: $BACKUP_DIR/portfolio_db_$DATE.sql.gz"
EOF

chmod +x backup.sh

# Schedule daily backups
echo "0 2 * * * /path/to/backup.sh" | crontab -
```

### Database Restore

```bash
# Restore from backup
gunzip -c /backup/portfolio_db_20240101_020000.sql.gz | \
docker exec -i portfolio-postgres-prod psql -U portfolio -d portfolio_db
```

### Volume Backup

```bash
# Backup Docker volumes
docker run --rm -v portfolio_postgres_data_prod:/data -v $(pwd):/backup \
  alpine tar czf /backup/postgres_volume_$(date +%Y%m%d).tar.gz -C /data .

# Restore Docker volumes
docker run --rm -v portfolio_postgres_data_prod:/data -v $(pwd):/backup \
  alpine tar xzf /backup/postgres_volume_20240101.tar.gz -C /data
```

## Troubleshooting

### Common Issues

#### Services Not Starting

```bash
# Check service status
docker-compose -f docker-compose.prod.yml ps

# Check logs
docker-compose -f docker-compose.prod.yml logs backend
docker-compose -f docker-compose.prod.yml logs frontend

# Common causes:
# - Port conflicts
# - Database connection issues
# - Environment variable misconfiguration
```

#### Database Connection Errors

```bash
# Check database connectivity
docker-compose -f docker-compose.prod.yml exec postgres pg_isready -U portfolio

# Test connection from backend container
docker-compose -f docker-compose.prod.yml exec backend python -c "
import asyncpg
import asyncio

async def test():
    try:
        conn = await asyncpg.connect('postgresql://portfolio:password@postgres:5432/portfolio_db')
        print('Database connection successful')
        await conn.close()
    except Exception as e:
        print(f'Database connection failed: {e}')

asyncio.run(test())
"
```

#### Frontend Build Issues

```bash
# Rebuild frontend with full output
docker-compose -f docker-compose.prod.yml build --no-cache frontend

# Check build logs
docker-compose -f docker-compose.prod.yml logs frontend
```

#### Environment Variable Issues

```bash
# Check environment variables
docker-compose -f docker-compose.prod.yml exec frontend printenv | grep API_URL
docker-compose -f docker-compose.prod.yml exec backend printenv | grep DATABASE_URL
```

### Performance Issues

```bash
# Check resource usage
docker stats

# Check database performance
docker-compose -f docker-compose.prod.yml exec postgres psql -U portfolio portfolio_db -c "
SELECT query, calls, total_time, mean_time
FROM pg_stat_statements
ORDER BY total_time DESC
LIMIT 10;
"

# Check Redis memory usage
docker-compose -f docker-compose.prod.yml exec redis redis-cli info memory
```

### Security Issues

```bash
# Check for exposed ports
netstat -tlnp | grep docker

# Check SSL certificate expiration
openssl x509 -in nginx/ssl/cert.pem -noout -dates

# Review environment variables for secrets
docker-compose -f docker-compose.prod.yml config
```

## Advanced Configuration

### Resource Limits

```yaml
# In docker-compose.prod.yml
services:
  backend:
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
        reservations:
          memory: 1G
          cpus: '0.5'
```

### Auto-scaling

```bash
# Create scaling script
cat > scale.sh << 'EOF'
#!/bin/bash
SERVICE=$1
REPLICAS=$2

if [ -z "$SERVICE" ] || [ -z "$REPLICAS" ]; then
    echo "Usage: $0 <service> <replicas>"
    exit 1
fi

docker-compose -f docker-compose.prod.yml up -d --scale $SERVICE=$REPLICAS
echo "Scaled $SERVICE to $REPLICAS replicas"
EOF

chmod +x scale.sh

# Scale backend workers
./scale.sh celery-worker 4
```

### Blue-Green Deployment

```bash
# Create blue-green deployment script
cat > deploy-blue-green.sh << 'EOF'
#!/bin/bash
ENVIRONMENT=${1:-blue}

# Create new environment file
cp .env.prod.example .env.$ENVIRONMENT

# Deploy to new environment
docker-compose -f docker-compose.prod.yml -p portfolio-$ENVIRONMENT up -d

# Run health checks
sleep 30
if curl -f http://localhost:3000/api/health; then
    echo "Deployment successful"
else
    echo "Deployment failed, rolling back"
    docker-compose -f docker-compose.prod.yml -p portfolio-$ENVIRONMENT down
    exit 1
fi
EOF

chmod +x deploy-blue-green.sh
```

## Support

- **Documentation**: [API.md](./API.md), [FEATURES.md](./FEATURES.md)
- **Issues**: [GitHub Issues](https://github.com/AxelFooley/TrackFolio/issues)
- **Community**: [Discussions](https://github.com/AxelFooley/TrackFolio/discussions)

For deployment issues, please include:
- Environment variables (redacted)
- Docker compose configuration
- Complete error logs
- System information (OS, Docker version)