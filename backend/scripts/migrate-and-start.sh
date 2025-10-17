#!/bin/bash
set -e  # Exit on any error
set +x  # Prevent credential leakage in debug mode

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
MIGRATION_TIMEOUT=${MIGRATION_TIMEOUT:-300}  # 5 minutes default
MIGRATION_LOCK_ID=${MIGRATION_LOCK_ID:-"portfolio_migrations"}  # Deterministic lock ID

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

# Cleanup function for temporary files
cleanup() {
    if [[ -f "$PGPASS_FILE" ]]; then
        rm -f "$PGPASS_FILE"
    fi
}

# Set up cleanup trap
trap cleanup EXIT INT TERM

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

# Use Python for robust URL parsing
DB_INFO=$(python3 -c "
import os
import urllib.parse
from urllib.parse import urlparse

url = os.environ['DATABASE_URL']
parsed = urlparse(url)

# Handle different postgresql URL formats
if parsed.scheme.startswith('postgresql+asyncpg'):
    parsed = urlparse(url.replace('postgresql+asyncpg://', 'postgresql://'))

if not all([parsed.username, parsed.password, parsed.hostname, parsed.path]):
    print('ERROR: Invalid DATABASE_URL format')
    exit(1)

print(f'USER={parsed.username}')
print(f'PASSWORD={parsed.password}')
print(f'HOST={parsed.hostname}')
print(f'PORT={parsed.port or 5432}')
print(f'DATABASE={parsed.path.lstrip(\"/\")}')
" 2>/dev/null)

if [[ $? -ne 0 ]]; then
    print_error "Failed to parse DATABASE_URL. Please check the format."
    exit 1
fi

# Parse database connection info
eval "$DB_INFO"

print_status "Database: $HOST:$PORT/$DATABASE"

# Create .pgpass file for secure password handling
PGPASS_FILE=$(mktemp)
chmod 600 "$PGPASS_FILE"
echo "$HOST:$PORT:$DATABASE:$USER:$PASSWORD" > "$PGPASS_FILE"
export PGPASSFILE="$PGPASS_FILE"

# Wait for database to be ready
print_status "Waiting for database to be ready..."
MAX_RETRIES=30
RETRY_INTERVAL=2

for i in $(seq 1 $MAX_RETRIES); do
    if PGPASSFILE="$PGPASS_FILE" psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DATABASE" -c "SELECT 1;" > /dev/null 2>&1; then
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

# Get current migration status
print_status "Checking current migration status..."
cd /app

# Get current revision (will be empty if no migrations have been run)
CURRENT_REVISION=$(PGPASSFILE="$PGPASS_FILE" psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DATABASE" -t -c "SELECT version_num FROM alembic_version LIMIT 1;" 2>/dev/null | xargs || echo "")

# Get latest revision from alembic and validate there's only one head
LATEST_REVISIONS=$(alembic heads --verbose 2>/dev/null | grep "Rev:" | awk '{print $2}' || echo "")
LATEST_REVISION_COUNT=$(echo "$LATEST_REVISIONS" | wc -w)

if [[ $LATEST_REVISION_COUNT -gt 1 ]]; then
    print_error "Multiple alembic heads detected: $LATEST_REVISION_COUNT"
    print_error "This indicates a branched migration history that must be resolved manually."
    exit 1
fi

LATEST_REVISION=$(echo "$LATEST_REVISIONS" | head -1)

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

    # Acquire PostgreSQL advisory lock to prevent concurrent migrations
    print_status "Acquiring migration lock to prevent concurrent executions..."
    LOCK_ACQUIRED=$(PGPASSFILE="$PGPASS_FILE" psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DATABASE" -t -c "
        SELECT pg_try_advisory_lock(hashtext('$MIGRATION_LOCK_ID'));
    " 2>/dev/null | xargs)

    if [[ "$LOCK_ACQUIRED" != "t" ]]; then
        print_error "Could not acquire migration lock. Another instance may be running migrations."
        print_error "Please wait for the other instance to complete or use RUN_MIGRATIONS=false"
        exit 1
    fi

    print_status "Migration lock acquired. Running migrations..."

    # Run alembic upgrade with timeout and proper error handling
    MIGRATION_EXIT_CODE=0
    if command -v timeout &> /dev/null; then
        timeout $MIGRATION_TIMEOUT alembic upgrade head
        MIGRATION_EXIT_CODE=$?
    else
        print_warning "timeout command not available, running without timeout protection"
        alembic upgrade head
        MIGRATION_EXIT_CODE=$?
    fi

    # Release the lock
    PGPASSFILE="$PGPASS_FILE" psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DATABASE" -c "
        SELECT pg_advisory_unlock(hashtext('$MIGRATION_LOCK_ID'));
    " > /dev/null 2>&1

    # Handle different exit codes
    if [[ $MIGRATION_EXIT_CODE -eq 0 ]]; then
        print_status "Database migrations completed successfully!"
    elif [[ $MIGRATION_EXIT_CODE -eq 124 ]]; then
        print_error "Migration timed out after ${MIGRATION_TIMEOUT} seconds"
        exit 1
    else
        print_error "Migration failed with exit code: $MIGRATION_EXIT_CODE"
        exit 1
    fi

    # Verify migration success
    NEW_REVISION=$(PGPASSFILE="$PGPASS_FILE" psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DATABASE" -t -c "SELECT version_num FROM alembic_version LIMIT 1;" 2>/dev/null | xargs || echo "")

    if [[ "$NEW_REVISION" == "$LATEST_REVISION" ]]; then
        print_status "Migration verification successful. Current revision: $NEW_REVISION"
    else
        print_error "Migration verification failed. Expected: $LATEST_REVISION, Got: $NEW_REVISION"
        exit 1
    fi
fi

# Start the FastAPI application
print_status "Starting FastAPI application..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000