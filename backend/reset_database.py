"""
Database reset script.

WARNING: This will DELETE ALL DATA from the database!
Only use this for development/testing purposes.
"""
import sys
import os
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from alembic.config import Config
from alembic import command
import logging

from app.database import sync_engine, Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def reset_database():
    """
    Reset the database by dropping all tables and re-running migrations.

    Steps:
    1. Safety confirmation prompt
    2. Drop all tables
    3. Run Alembic migrations to recreate schema
    """
    # Safety confirmation
    print("\n" + "=" * 70)
    print("WARNING: DATABASE RESET")
    print("=" * 70)
    print("\nThis will DELETE ALL DATA from the database:")
    print("  - All transactions")
    print("  - All positions")
    print("  - All price history")
    print("  - All portfolio snapshots")
    print("  - All cached metrics")
    print("  - All benchmarks")
    print("\nThis action CANNOT be undone!")
    print("\nType 'CONFIRM' to proceed (or anything else to cancel): ", end="")

    confirmation = input().strip()

    if confirmation != "CONFIRM":
        print("\nDatabase reset cancelled.")
        return

    print("\n" + "=" * 70)
    print("Starting database reset...")
    print("=" * 70)

    try:
        # Step 1: Drop all tables
        logger.info("Dropping all tables...")
        with sync_engine.begin() as conn:
            # Get all table names
            inspector = text("""
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
            """)
            result = conn.execute(inspector)
            tables = [row[0] for row in result]

            # Drop each table
            for table in tables:
                if table != 'alembic_version':
                    logger.info(f"  Dropping table: {table}")
                    conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))

            # Drop alembic_version last
            logger.info("  Dropping table: alembic_version")
            conn.execute(text('DROP TABLE IF EXISTS alembic_version CASCADE'))

            conn.commit()

        print("\n✓ All tables dropped successfully")

        # Step 2: Run Alembic migrations
        logger.info("\nRunning Alembic migrations...")

        # Get the path to alembic.ini
        backend_dir = Path(__file__).parent
        alembic_ini_path = backend_dir / "alembic.ini"

        if not alembic_ini_path.exists():
            raise FileNotFoundError(f"alembic.ini not found at {alembic_ini_path}")

        # Create Alembic config
        alembic_cfg = Config(str(alembic_ini_path))

        # Run migrations
        logger.info("  Running migrations to 'head'...")
        command.upgrade(alembic_cfg, "head")

        print("\n✓ Database schema recreated successfully")

        # Step 3: Verify tables were created
        logger.info("\nVerifying database schema...")
        with sync_engine.begin() as conn:
            inspector = text("""
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY tablename
            """)
            result = conn.execute(inspector)
            tables = [row[0] for row in result]

        print("\nCreated tables:")
        for table in tables:
            print(f"  - {table}")

        print("\n" + "=" * 70)
        print("DATABASE RESET COMPLETE")
        print("=" * 70)
        print("\nThe database is now empty and ready for fresh data.")
        print("You can now import transactions via the API.")
        print("\n")

    except Exception as e:
        logger.error(f"Error during database reset: {str(e)}")
        print(f"\n✗ Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    reset_database()
