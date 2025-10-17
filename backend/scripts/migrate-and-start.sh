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
AUTO_ROLLBACK_ON_FAILURE=${AUTO_ROLLBACK_ON_FAILURE:-"false"}  # Auto-rollback on migration failure

# Alembic command configuration (for custom alembic paths if needed)
ALEMBIC_COMMAND=${ALEMBIC_COMMAND:-"alembic"}  # Path to alembic command
ALEMBIC_DOWNGRADE_CMD=${ALEMBIC_DOWNGRADE_CMD:-"downgrade"}  # downgrade subcommand
ALEMBIC_HEADS_CMD=${ALEMBIC_HEADS_CMD:-"heads --verbose"}  # heads subcommand with options
ALEMBIC_UPGRADE_CMD=${ALEMBIC_UPGRADE_CMD:-"upgrade head"}  # upgrade subcommand with target

# Debug configuration
MIGRATION_DEBUG=${MIGRATION_DEBUG:-"false"}  # Enable verbose debug logging

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

print_debug() {
    if [[ "$MIGRATION_DEBUG" == "true" ]]; then
        echo -e "${YELLOW}[DEBUG]${NC} $1"
    fi
}

# Function to handle migration failure and optional rollback
handle_migration_failure() {
    local failure_type="$1"

    if [[ "$AUTO_ROLLBACK_ON_FAILURE" != "true" ]]; then
        print_warning "Auto-rollback is disabled (AUTO_ROLLBACK_ON_FAILURE=false)"
        print_warning "Database may be in an inconsistent state. Manual intervention required."
        print_warning "To enable auto-rollback, set AUTO_ROLLBACK_ON_FAILURE=true"
        return
    fi

    print_status "Auto-rollback enabled. Attempting to rollback to previous state..."

    # Get the revision we were trying to migrate FROM
    local target_revision="$CURRENT_REVISION"

    if [[ -z "$target_revision" ]]; then
        print_warning "No previous revision found. Cannot rollback from initial migration."
        print_warning "Database may have partial tables created. Manual cleanup required."
        return
    fi

    print_status "Rolling back to revision: $target_revision"

    # Perform the rollback
    if $ALEMBIC_COMMAND $ALEMBIC_DOWNGRADE_CMD "$target_revision"; then
        print_status "Successfully rolled back to revision: $target_revision"

        # Verify rollback
        local verify_revision=$(PGPASSFILE="$PGPASS_FILE" psql -h "$HOST" -p "$PORT" -U "$USER" -d "$DATABASE" -t -c "SELECT version_num FROM alembic_version LIMIT 1;" 2>/dev/null | xargs || echo "")

        if [[ "$verify_revision" == "$target_revision" ]]; then
            print_status "Rollback verification successful."
        else
            print_error "Rollback verification failed. Database state uncertain."
        fi
    else
        print_error "Rollback failed. Database may be in inconsistent state."
        print_error "Manual intervention required to restore database consistency."
    fi
}

# Cleanup function for temporary files and locks
cleanup() {
    # Release advisory lock if acquired
    if [[ -n "$LOCK_ACQUIRED" && "$LOCK_ACQUIRED" == "t" ]] && [[ -n "$DB_HOST" && -n "$DB_PORT" && -n "$DB_USER" && -n "$DB_DATABASE" && -f "$PGPASS_FILE" ]]; then
        if [[ -n "$MIGRATION_LOCK_HASH" ]]; then
            # Use pre-computed hash if available
            PGPASSFILE="$PGPASS_FILE" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_DATABASE" -c "
                SELECT pg_advisory_unlock($MIGRATION_LOCK_HASH);
            " > /dev/null 2>&1 || true
        else
            # Fallback to computing hash (should not happen with normal flow)
            PGPASSFILE="$PGPASS_FILE" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_DATABASE" -c "
                SELECT pg_advisory_unlock(hashtext('$MIGRATION_LOCK_ID'));
            " > /dev/null 2>&1 || true
        fi
    fi

    # Remove temporary .pgpass file
    if [[ -f "$PGPASS_FILE" ]]; then
        print_debug "Cleaning up temporary .pgpass file: $PGPASS_FILE"
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
print_debug "Configuration: MIGRATION_TIMEOUT=$MIGRATION_TIMEOUT, MIGRATION_LOCK_ID=$MIGRATION_LOCK_ID, AUTO_ROLLBACK_ON_FAILURE=$AUTO_ROLLBACK_ON_FAILURE"
print_debug "Configuration: MIGRATION_DEBUG=$MIGRATION_DEBUG, ALEMBIC_COMMAND=$ALEMBIC_COMMAND"

# Check required dependencies
if ! command -v psql &> /dev/null; then
    print_error "psql command not found. Please ensure PostgreSQL client is installed."
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    print_error "python3 command not found. Please ensure Python 3 is installed."
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
DB_PARSE_RESULT=$(python3 -c "
import os
import sys
from urllib.parse import urlparse

url = os.environ['DATABASE_URL']
parsed = urlparse(url)

# Handle different postgresql URL formats
if parsed.scheme.startswith('postgresql+asyncpg'):
    parsed = urlparse(url.replace('postgresql+asyncpg://', 'postgresql://'))

if not all([parsed.username, parsed.password, parsed.hostname, parsed.path]):
    print('ERROR: Invalid DATABASE_URL format', file=sys.stderr)
    exit(1)

# Output variables in a format that can be safely sourced
print(f'DB_USER=\"{parsed.username}\"')
print(f'DB_PASSWORD=\"{parsed.password}\"')
print(f'DB_HOST=\"{parsed.hostname}\"')
print(f'DB_PORT=\"{parsed.port or 5432}\"')
print(f'DB_DATABASE=\"{parsed.path.lstrip(\"/\")}\"')
" 2>/dev/null)

if [[ $? -ne 0 ]]; then
    print_error "Failed to parse DATABASE_URL. Please check the format."
    exit 1
fi

# Parse database connection info safely
eval "$DB_PARSE_RESULT"

print_debug "Parsed database connection: host=$DB_HOST, port=$DB_PORT, database=$DB_DATABASE, user=$DB_USER"
print_status "Database: $DB_HOST:$DB_PORT/$DB_DATABASE"

# Create .pgpass file for secure password handling
PGPASS_FILE=$(mktemp)
chmod 600 "$PGPASS_FILE"
echo "$DB_HOST:$DB_PORT:$DB_DATABASE:$DB_USER:$DB_PASSWORD" > "$PGPASS_FILE"
export PGPASSFILE="$PGPASS_FILE"
print_debug "Created temporary .pgpass file: $PGPASS_FILE"

# Wait for database to be ready
print_status "Waiting for database to be ready..."
MAX_RETRIES=30
RETRY_INTERVAL=2

for i in $(seq 1 $MAX_RETRIES); do
    if PGPASSFILE="$PGPASS_FILE" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_DATABASE" -c "SELECT 1;" > /dev/null 2>&1; then
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
CURRENT_REVISION=$(PGPASSFILE="$PGPASS_FILE" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_DATABASE" -t -c "SELECT version_num FROM alembic_version LIMIT 1;" 2>/dev/null | xargs || echo "")

# Get latest revision from alembic and validate there's only one head
LATEST_REVISIONS=$($ALEMBIC_COMMAND $ALEMBIC_HEADS_CMD 2>/dev/null | grep "Rev:" | awk '{print $2}' || echo "")
LATEST_REVISION_COUNT=$(echo "$LATEST_REVISIONS" | wc -w)

if [[ $LATEST_REVISION_COUNT -gt 1 ]]; then
    print_error "Multiple alembic heads detected: $LATEST_REVISION_COUNT"
    print_error "This indicates a branched migration history that must be resolved manually."
    exit 1
fi

LATEST_REVISION=$(echo "$LATEST_REVISIONS" | head -1)

print_status "Current revision: ${CURRENT_REVISION:-'None'}"
print_status "Latest revision: ${LATEST_REVISION:-'None'}"
print_debug "Alembic command executed: $ALEMBIC_COMMAND $ALEMBIC_HEADS_CMD"
print_debug "Migration check: CURRENT_REVISION=$CURRENT_REVISION, LATEST_REVISION=$LATEST_REVISION"

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
    print_debug "Attempting to acquire advisory lock with ID: $MIGRATION_LOCK_ID"

    # Pre-compute hash for advisory lock (optimization)
    MIGRATION_LOCK_HASH=$(PGPASSFILE="$PGPASS_FILE" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_DATABASE" -t -c "
        SELECT hashtext('$MIGRATION_LOCK_ID');
    " 2>/dev/null | xargs)
    print_debug "Pre-computed lock hash: $MIGRATION_LOCK_HASH"

    # Use pre-computed hash for lock acquisition
    LOCK_ACQUIRED=$(PGPASSFILE="$PGPASS_FILE" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_DATABASE" -t -c "
        SELECT pg_try_advisory_lock($MIGRATION_LOCK_HASH);
    " 2>/dev/null | xargs)
    print_debug "Lock acquisition result: $LOCK_ACQUIRED"

    if [[ "$LOCK_ACQUIRED" != "t" ]]; then
        print_error "Could not acquire migration lock. Another instance may be running migrations."
        print_error "Please wait for the other instance to complete or use RUN_MIGRATIONS=false"
        exit 1
    fi

    print_status "Migration lock acquired. Re-checking migration status to prevent race conditions..."

    # Re-check current revision after acquiring lock to prevent race conditions
    CURRENT_REVISION_AFTER_LOCK=$(PGPASSFILE="$PGPASS_FILE" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_DATABASE" -t -c "SELECT version_num FROM alembic_version LIMIT 1;" 2>/dev/null | xargs || echo "")

    if [[ "$CURRENT_REVISION_AFTER_LOCK" != "$CURRENT_REVISION" ]]; then
        print_warning "Migration revision changed while waiting for lock (${CURRENT_REVISION:-'None'} -> ${CURRENT_REVISION_AFTER_LOCK:-'None'})"
        print_status "Updating migration plan with new revision..."
        CURRENT_REVISION="$CURRENT_REVISION_AFTER_LOCK"

        # Update decision about whether to run migrations
        if [[ "$CURRENT_REVISION" == "$LATEST_REVISION" ]]; then
            print_status "Database is already up to date after re-check. Skipping migrations."
            # Release lock and start app
            if [[ -n "$MIGRATION_LOCK_HASH" ]]; then
                PGPASSFILE="$PGPASS_FILE" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_DATABASE" -c "
                    SELECT pg_advisory_unlock($MIGRATION_LOCK_HASH);
                " > /dev/null 2>&1 || true
            else
                PGPASSFILE="$PGPASS_FILE" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_DATABASE" -c "
                    SELECT pg_advisory_unlock(hashtext('$MIGRATION_LOCK_ID'));
                " > /dev/null 2>&1 || true
            fi
            LOCK_ACQUIRED="f"
        fi
    fi

    # Run alembic upgrade with timeout and proper error handling
    print_debug "Starting migration with command: $ALEMBIC_COMMAND $ALEMBIC_UPGRADE_CMD"
    MIGRATION_EXIT_CODE=0
    if command -v timeout &> /dev/null; then
        print_debug "Using timeout command with ${MIGRATION_TIMEOUT}s timeout"
        timeout $MIGRATION_TIMEOUT $ALEMBIC_COMMAND $ALEMBIC_UPGRADE_CMD
        MIGRATION_EXIT_CODE=$?
    else
        print_warning "timeout command not available, running without timeout protection"
        $ALEMBIC_COMMAND $ALEMBIC_UPGRADE_CMD
        MIGRATION_EXIT_CODE=$?
    fi
    print_debug "Migration command completed with exit code: $MIGRATION_EXIT_CODE"

    # Handle different exit codes
    if [[ $MIGRATION_EXIT_CODE -eq 0 ]]; then
        print_status "Database migrations completed successfully!"
    elif [[ $MIGRATION_EXIT_CODE -eq 124 ]]; then
        print_error "Migration timed out after ${MIGRATION_TIMEOUT} seconds"
        handle_migration_failure "timeout"
        exit 1
    else
        print_error "Migration failed with exit code: $MIGRATION_EXIT_CODE"
        handle_migration_failure "failure"
        exit 1
    fi

    # Verify migration success
    NEW_REVISION=$(PGPASSFILE="$PGPASS_FILE" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_DATABASE" -t -c "SELECT version_num FROM alembic_version LIMIT 1;" 2>/dev/null | xargs || echo "")

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