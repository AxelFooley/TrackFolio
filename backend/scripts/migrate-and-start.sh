#!/bin/bash
set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we should run migrations (default: true)
RUN_MIGRATIONS=${RUN_MIGRATIONS:-true}
if [[ "$RUN_MIGRATIONS" != "true" ]]; then
    print_status "Skipping database migrations (RUN_MIGRATIONS=false)"
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000
fi

print_status "Starting automated database migration process..."

# Check required dependencies
if ! command -v psql &> /dev/null; then
    print_error "psql command not found. Please ensure PostgreSQL client is installed."
    exit 1
fi

if ! command -v timeout &> /dev/null; then
    print_warning "timeout command not found. Migration timeout protection disabled."
fi

# Get database connection details from DATABASE_URL
if [[ -z "$DATABASE_URL" ]]; then
    print_error "DATABASE_URL environment variable is not set"
    exit 1
fi

# Extract connection details from DATABASE_URL
# Expected format: postgresql://user:password@host:port/database
if [[ $DATABASE_URL =~ ^postgresql://([^:]+):([^@]+)@([^:]+):([0-9]+)/(.+)$ ]]; then
    DB_USER="${BASH_REMATCH[1]}"
    DB_PASSWORD="${BASH_REMATCH[2]}"
    DB_HOST="${BASH_REMATCH[3]}"
    DB_PORT="${BASH_REMATCH[4]}"
    DB_NAME="${BASH_REMATCH[5]}"
else
    print_error "Invalid DATABASE_URL format: $DATABASE_URL"
    exit 1
fi

print_status "Database: $DB_HOST:$DB_PORT/$DB_NAME"

# Wait for database to be ready
print_status "Waiting for database to be ready..."
MAX_RETRIES=30
RETRY_INTERVAL=2

for i in $(seq 1 $MAX_RETRIES); do
    if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" > /dev/null 2>&1; then
        print_status "Database is ready!"
        break
    else
        if [[ $i -eq $MAX_RETRIES ]]; then
            print_error "Database is not ready after $MAX_RETRIES attempts"
            exit 1
        fi
        print_warning "Attempt $i/$MAX_RETRIES: Database not ready, waiting ${RETRY_INTERVAL}s..."
        sleep $RETRY_INTERVAL
    fi
done

# Check current migration status
print_status "Checking current migration status..."
cd /app

# Get current revision (will be empty if no migrations have been run)
CURRENT_REVISION=$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT version_num FROM alembic_version;" 2>/dev/null | xargs || echo "")

# Get latest revision from alembic
LATEST_REVISION=$(alembic heads --verbose | grep "Rev:" | head -1 | awk '{print $2}' || echo "")

print_status "Current revision: ${CURRENT_REVISION:-'None'}"
print_status "Latest revision: ${LATEST_REVISION:-'None'}"

# Run migrations if needed
if [[ "$CURRENT_REVISION" == "$LATEST_REVISION" ]]; then
    print_status "Database is already up to date. Skipping migrations."
else
    if [[ -n "$CURRENT_REVISION" ]]; then
        print_status "Running database migrations from $CURRENT_REVISION to $LATEST_REVISION..."
    else
        print_status "Running initial database migration..."
    fi

    # Run alembic upgrade with timeout (if available)
    MIGRATION_TIMEOUT=300  # 5 minutes
    if command -v timeout &> /dev/null; then
        timeout $MIGRATION_TIMEOUT alembic upgrade head
    else
        print_warning "timeout command not available, running without timeout protection"
        alembic upgrade head
    fi

    if [[ $? -eq 0 ]]; then
        print_status "Database migrations completed successfully!"
    else
        print_error "Database migration failed or timed out after ${MIGRATION_TIMEOUT}s"
        exit 1
    fi
fi

# Verify migration success
NEW_REVISION=$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT version_num FROM alembic_version;" 2>/dev/null | xargs || echo "")

if [[ "$NEW_REVISION" == "$LATEST_REVISION" ]]; then
    print_status "Migration verification successful. Current revision: $NEW_REVISION"
else
    print_error "Migration verification failed. Expected: $LATEST_REVISION, Got: $NEW_REVISION"
    exit 1
fi

# Start the FastAPI application
print_status "Starting FastAPI application..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000