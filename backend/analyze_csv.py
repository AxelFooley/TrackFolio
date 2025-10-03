"""
Analyze CSV file and compare with database to find missing transactions.
"""
import sys
import asyncio
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.services.csv_parser import DirectaCSVParser
from app.services.deduplication import DeduplicationService
from app.database import AsyncSessionLocal
from sqlalchemy import select, text
from app.models import Transaction
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def analyze_csv_vs_db(csv_path: str):
    """Analyze CSV file and compare with database."""

    # 1. Parse CSV file
    logger.info(f"Parsing CSV file: {csv_path}")
    with open(csv_path, 'r', encoding='utf-8') as f:
        csv_content = f.read()

    csv_transactions = DirectaCSVParser.parse(csv_content)
    logger.info(f"Found {len(csv_transactions)} transactions in CSV")

    # Calculate hashes for CSV transactions
    for txn in csv_transactions:
        txn["transaction_hash"] = DeduplicationService.calculate_hash_from_dict(txn)

    # 2. Get all transactions from database
    logger.info("Fetching all transactions from database...")
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Transaction).order_by(Transaction.operation_date)
        )
        db_transactions = result.scalars().all()
        logger.info(f"Found {len(db_transactions)} transactions in database")

        # Create set of database transaction hashes
        db_hashes = {txn.transaction_hash for txn in db_transactions}

        # Create dict of database transactions by hash for detailed comparison
        db_by_hash = {txn.transaction_hash: txn for txn in db_transactions}

    # 3. Find missing transactions
    missing_transactions = []
    for csv_txn in csv_transactions:
        if csv_txn["transaction_hash"] not in db_hashes:
            missing_transactions.append(csv_txn)

    # 4. Find extra transactions in DB (not in CSV)
    csv_hashes = {txn["transaction_hash"] for txn in csv_transactions}
    extra_db_transactions = []
    for db_txn in db_transactions:
        if db_txn.transaction_hash not in csv_hashes:
            extra_db_transactions.append(db_txn)

    # 5. Print report
    print("\n" + "="*80)
    print("CSV vs DATABASE COMPARISON REPORT")
    print("="*80)

    print(f"\nTotal transactions in CSV: {len(csv_transactions)}")
    print(f"Total transactions in DB:  {len(db_transactions)}")
    print(f"\nMissing from DB: {len(missing_transactions)}")
    print(f"Extra in DB (not in CSV): {len(extra_db_transactions)}")

    # Report missing transactions
    if missing_transactions:
        print("\n" + "-"*80)
        print("MISSING TRANSACTIONS (In CSV but NOT in Database):")
        print("-"*80)

        # Group by ticker
        by_ticker = {}
        for txn in missing_transactions:
            ticker = txn["ticker"]
            if ticker not in by_ticker:
                by_ticker[ticker] = []
            by_ticker[ticker].append(txn)

        for ticker, txns in sorted(by_ticker.items()):
            print(f"\n{ticker}: {len(txns)} missing transaction(s)")
            for txn in sorted(txns, key=lambda x: x["operation_date"]):
                print(f"  {txn['operation_date']} | {txn['transaction_type'].upper():4s} | "
                      f"{txn['quantity']:>8.2f} @ {txn['price_per_share']:>8.2f} EUR | "
                      f"Total: {txn['amount_eur']:>10.2f} EUR | "
                      f"Order: {txn['order_reference']}")

    # Report extra transactions
    if extra_db_transactions:
        print("\n" + "-"*80)
        print("EXTRA TRANSACTIONS (In Database but NOT in CSV):")
        print("-"*80)
        print("NOTE: These might be from older CSV imports not included in this file")

        # Group by ticker
        by_ticker = {}
        for txn in extra_db_transactions:
            ticker = txn.ticker
            if ticker not in by_ticker:
                by_ticker[ticker] = []
            by_ticker[ticker].append(txn)

        for ticker, txns in sorted(by_ticker.items()):
            print(f"\n{ticker}: {len(txns)} extra transaction(s)")
            for txn in sorted(txns, key=lambda x: x.operation_date):
                print(f"  {txn.operation_date} | {txn.transaction_type.value.upper():4s} | "
                      f"{txn.quantity:>8.2f} @ {txn.price_per_share:>8.2f} EUR | "
                      f"Total: {txn.amount_eur:>10.2f} EUR | "
                      f"Order: {txn.order_reference}")

    # Specific check for A500 and TSLA
    print("\n" + "="*80)
    print("SPECIFIC CHECK: A500 and TSLA")
    print("="*80)

    for ticker in ["A500", "TSLA"]:
        csv_ticker_txns = [t for t in csv_transactions if t["ticker"] == ticker]
        db_ticker_txns = [t for t in db_transactions if t.ticker == ticker]
        missing_ticker_txns = [t for t in missing_transactions if t["ticker"] == ticker]

        # Calculate expected quantity
        csv_quantity = sum(
            t["quantity"] if t["transaction_type"] == "buy" else -t["quantity"]
            for t in csv_ticker_txns
        )
        db_quantity = sum(
            t.quantity if t.transaction_type.value == "buy" else -t.quantity
            for t in db_ticker_txns
        )

        print(f"\n{ticker}:")
        print(f"  CSV: {len(csv_ticker_txns)} transactions, expected quantity: {csv_quantity:.2f}")
        print(f"  DB:  {len(db_ticker_txns)} transactions, expected quantity: {db_quantity:.2f}")
        print(f"  Missing: {len(missing_ticker_txns)} transactions")

        if missing_ticker_txns:
            missing_qty = sum(
                t["quantity"] if t["transaction_type"] == "buy" else -t["quantity"]
                for t in missing_ticker_txns
            )
            print(f"  Missing quantity impact: {missing_qty:.2f} shares")

    print("\n" + "="*80)
    print()


if __name__ == "__main__":
    csv_file = "/Users/alessandro.anghelone/src/Personal/TrackFolio/Movimenti_72024_2-10-2025.csv"
    asyncio.run(analyze_csv_vs_db(csv_file))
