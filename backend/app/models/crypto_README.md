# Crypto Portfolio Database Models

This document describes the crypto portfolio database models implemented for standalone cryptocurrency tracking.

## Overview

The crypto models allow users to track cryptocurrency holdings separately from traditional investments, with independent transaction history. The implementation follows the existing codebase patterns and uses SQLAlchemy 2.0 with proper async support.

## Models

### 1. CryptoPortfolio

Represents a standalone crypto portfolio for organizing cryptocurrency holdings.

**Table:** `crypto_portfolios`

**Fields:**
- `id` (Integer, Primary Key) - Auto-incrementing unique identifier
- `name` (String(100), Required) - Portfolio name for identification
- `description` (String(500), Optional) - Optional portfolio description
- `is_active` (Boolean, Required, Default: true) - Whether the portfolio is active
 `base_currency` (SQLEnum(CryptoCurrency), Required, Default: CryptoCurrency.EUR) - Base currency for the portfolio (stored as string: EUR/USD)
- `created_at` (DateTime, Required) - When the portfolio was created
- `updated_at` (DateTime, Required) - When the portfolio was last updated

**Relationships:**
- `transactions` - One-to-many relationship with CryptoTransaction (cascade delete)

### 2. CryptoTransaction

Represents individual cryptocurrency transactions within a portfolio.

**Table:** `crypto_transactions`

**Fields:**
- `id` (Integer, Primary Key) - Auto-incrementing unique identifier
- `portfolio_id` (Integer, Required, Foreign Key) - Associated portfolio ID (CASCADE DELETE)
- `symbol` (String(20), Required, Indexed) - Crypto symbol (e.g., BTC, ETH, ADA)
- `transaction_type` (String(20), Required, Indexed) - Type of transaction (buy, sell, transfer_in, transfer_out)
- `quantity` (Numeric(20,8), Required) - Quantity of crypto asset (positive for all types)
- `price_at_execution` (Numeric(20,8), Required) - Price per unit at time of execution
 `currency` (SQLEnum(CryptoCurrency), Required) - Currency used for the transaction (stored as string: EUR/USD)
- `total_amount` (Numeric(20,2), Required) - Total value of transaction (quantity * price)
- `fee` (Numeric(20,8), Required, Default: 0) - Transaction fee in crypto asset or base currency
- `fee_currency` (String(10), Optional) - Currency of the fee (if different from main transaction)
- `timestamp` (DateTime, Required, Indexed) - When the transaction occurred
- `exchange` (String(50), Optional) - Exchange or platform where transaction occurred
- `transaction_hash` (String(100), Optional, Unique, Indexed) - Blockchain transaction hash for on-chain transactions
- `notes` (String(1000), Optional) - Additional notes about the transaction
- `created_at` (DateTime, Required) - When the record was created
- `updated_at` (DateTime, Required) - When the record was last updated

**Relationships:**
- `portfolio` - Many-to-one relationship with CryptoPortfolio

## Enums

### CryptoTransactionType
- `BUY` - "buy" - Purchase of cryptocurrency
- `SELL` - "sell" - Sale of cryptocurrency
- `TRANSFER_IN` - "transfer_in" - Incoming transfer from external wallet
- `TRANSFER_OUT` - "transfer_out" - Outgoing transfer to external wallet

### CryptoCurrency
- `EUR` - "EUR" - Euro
- `USD` - "USD" - US Dollar

## Database Indexes

**CryptoTransaction indexes for performance:**
- `ix_crypto_transactions_portfolio_id` - For filtering by portfolio
- `ix_crypto_transactions_symbol` - For filtering by crypto symbol
- `ix_crypto_transactions_timestamp` - For time-based queries
- `ix_crypto_transactions_portfolio_date` - Composite index for portfolio + time queries
- `ix_crypto_transactions_symbol_date` - Composite index for symbol + time queries
- `ix_crypto_transactions_type_date` - Composite index for transaction type + time queries
- `ix_crypto_transactions_transaction_hash` - For blockchain hash lookups (unique constraint)

## Key Design Decisions

1. **String Enums**: Used `native_enum=False` to store enum values as strings, matching the existing codebase pattern
2. **High Precision**: Used `Numeric(20,8)` for crypto quantities and prices to handle small decimal values
3. **Cascade Delete**: Portfolio deletions cascade to delete associated transactions
4. **Comprehensive Indexing**: Optimized for common query patterns
5. **Transaction Hash**: Unique constraint for blockchain transaction deduplication
6. **Fee Tracking**: Supports fees in different currencies than the main transaction
7. **Exchange Tracking**: Records which exchange/platform was used
8. **Notes Field**: Allows users to add context to transactions

## Usage Example

```python
from app.models.crypto import CryptoPortfolio, CryptoTransaction, CryptoTransactionType, CryptoCurrency
from app.database import AsyncSessionLocal
from decimal import Decimal
from datetime import datetime

# Create a crypto portfolio
async with AsyncSessionLocal() as session:
    portfolio = CryptoPortfolio(
        name="Main Crypto Portfolio",
        description="My cryptocurrency investments",
        base_currency=CryptoCurrency.EUR
    )
    session.add(portfolio)
    await session.flush()

    # Add a transaction
    transaction = CryptoTransaction(
        portfolio_id=portfolio.id,
        symbol="BTC",
        transaction_type=CryptoTransactionType.BUY,
        quantity=Decimal("0.1"),
        price_at_execution=Decimal("45000.50"),
        currency=CryptoCurrency.EUR,
        total_amount=Decimal("4500.05"),
        fee=Decimal("0.001"),
        timestamp=datetime.now(),
        exchange="Coinbase",
        notes="Initial Bitcoin purchase"
    )
    session.add(transaction)
    await session.commit()
```

## Migration

The migration file `b4c986c7b760_add_crypto_portfolio_and_transaction_.py` creates the database schema with all tables, indexes, and constraints.

## Testing

The models have been tested with:
- CRUD operations (Create, Read, Update, Delete)
- Enum handling
- Foreign key relationships
- Index performance
- Data type validation
- Unique constraints

All tests pass successfully, confirming the models work correctly with the database.