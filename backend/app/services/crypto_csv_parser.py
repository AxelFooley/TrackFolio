"""
Crypto CSV Parser for various cryptocurrency exchange formats.

Supports:
- Coinbase CSV format
- Binance CSV format
- Kraken CSV format
- Generic crypto exchange formats

Detects crypto transactions and generates appropriate ISIN-like identifiers.
"""
from io import StringIO
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import hashlib
import logging
import re

logger = logging.getLogger(__name__)


class CryptoExchangeType:
    """Supported crypto exchange types."""
    COINBASE = "coinbase"
    BINANCE = "binance"
    KRAKEN = "kraken"
    GENERIC = "generic"


class CryptoTransactionType:
    """Crypto-specific transaction types."""
    BUY = "buy"
    SELL = "sell"
    SEND = "send"
    RECEIVE = "receive"
    STAKE = "stake"
    UNSTAKE = "unstake"
    AIRDROP = "airdrop"
    FORK = "fork"
    MINT = "mint"
    BURN = "burn"


class CryptoCSVParser:
    """
    Parser for cryptocurrency exchange CSV files.

    Supports multiple exchange formats and handles:
    - Various ticker formats (BTC-USD, BTC/USD, BTC, etc.)
    - Crypto-specific transaction types
    - Gas fees and spreads
    - Missing ISINs (generates crypto-specific identifiers)
    """

    # Coinbase column mappings
    COINBASE_COLUMNS = {
        "Timestamp": "timestamp",
        "Transaction Type": "transaction_type",
        "Asset": "asset",
        "Quantity Transacted": "quantity",
        "Spot Price Currency": "spot_price_currency",
        "Spot Price at Transaction": "spot_price",
        "Subtotal": "subtotal",
        "Total (inclusive of fees and/or spread)": "total",
        "Fees and/or Spread": "fees",
        "Currency": "currency",
        "Notes": "notes",
        "Transaction ID": "transaction_id"
    }

    # Binance column mappings
    BINANCE_COLUMNS = {
        "Date": "date",
        "Pair": "pair",
        "Type": "type",
        "Side": "side",
        "Price": "price",
        "Amount": "amount",
        "Total": "total",
        "Fee": "fee",
        "Fee Coin": "fee_coin"
    }

    # Kraken column mappings
    KRAKEN_COLUMNS = {
        "txid": "txid",
        "time": "time",
        "type": "type",
        "ordertype": "ordertype",
        "pair": "pair",
        "price": "price",
        "cost": "cost",
        "fee": "fee",
        "vol": "vol"
    }

    @staticmethod
    def detect_exchange_format(df: pd.DataFrame) -> str:
        """
        Detect which crypto exchange format the CSV uses.

        Args:
            df: Pandas DataFrame of CSV data

        Returns:
            Exchange type string from CryptoExchangeType
        """
        columns = set(df.columns)

        # Check Coinbase format (must have multiple Coinbase-specific columns)
        coinbase_columns = ["Quantity Transacted", "Spot Price Currency", "Spot Price at Transaction", "Total (inclusive of fees and/or spread)"]
        coinbase_matches = sum(1 for col in coinbase_columns if col in columns)
        if coinbase_matches >= 2:  # Must match at least 2 Coinbase-specific columns
            return CryptoExchangeType.COINBASE

        # Check Binance format
        binance_columns = ["Pair", "Side", "Fee Coin"]
        binance_matches = sum(1 for col in binance_columns if col in columns)
        if binance_matches >= 2:  # Must match at least 2 Binance-specific columns
            return CryptoExchangeType.BINANCE

        # Check Kraken format
        kraken_columns = ["txid", "ordertype"]
        kraken_matches = sum(1 for col in kraken_columns if col in columns)
        if kraken_matches >= 1:  # Must match at least 1 Kraken-specific column
            return CryptoExchangeType.KRAKEN

        # Default to generic
        return CryptoExchangeType.GENERIC

    @staticmethod
    def is_crypto_transaction(ticker: str) -> bool:
        """
        Detect if a ticker represents a cryptocurrency.

        Args:
            ticker: Ticker symbol

        Returns:
            True if appears to be a cryptocurrency
        """
        if not ticker:
            return False

        ticker = ticker.upper().strip()

        # Common crypto patterns with separators
        if '-' in ticker or '/' in ticker:
            return True

        # Known crypto trading pair patterns
        crypto_patterns = [
            r'^[A-Z]{2,5}USD$',  # Direct pair like BTCUSD
            r'^[A-Z]{2,5}USDT$',  # Tether pairs
        ]

        for pattern in crypto_patterns:
            if re.match(pattern, ticker):
                return True

        # Known crypto tickers (must be exact match to avoid false positives)
        known_crypto = {
            'BTC', 'ETH', 'USDT', 'USDC', 'BNB', 'SOL', 'ADA', 'XRP', 'DOT', 'DOGE',
            'AVAX', 'MATIC', 'LINK', 'UNI', 'ATOM', 'LTC', 'SHIB', 'TRX', 'XLM',
            'FIL', 'ETC', 'VET', 'THETA', 'ICP', 'HBAR', 'EGLD', 'FTT', 'ALGO',
            'AAVE', 'CAKE', 'MANA', 'SAND', 'AXS', 'LUNA', 'CRV', 'COMP', 'MKR'
        }

        # Check if ticker is exactly a known crypto ticker
        return ticker in known_crypto

    @staticmethod
    def normalize_crypto_ticker(ticker: str) -> str:
        """
        Normalize crypto ticker to standard format.

        Args:
            ticker: Raw ticker from exchange

        Returns:
            Normalized ticker symbol
        """
        if not ticker:
            return ticker

        ticker = ticker.upper().strip()

        # Handle various trading pair formats
        separators = ['-', '/', 'USD', 'USDT', 'EUR', 'GBP']

        for sep in separators:
            if sep in ticker:
                # Split and take the first part (base asset)
                parts = ticker.split(sep)
                ticker = parts[0]
                break

        return ticker

    @staticmethod
    def generate_crypto_identifier(ticker: str, description: str = None) -> str:
        """
        Generate ISIN-like identifier for cryptocurrency.

        Since cryptos don't have ISINs, we generate a unique identifier
        based on the ticker and description.

        Args:
            ticker: Normalized ticker symbol
            description: Optional description

        Returns:
            12-character identifier similar to ISIN format
        """
        if not ticker:
            raise ValueError("Ticker is required for crypto identifier generation")

        # Create a deterministic hash of the ticker
        content = f"CRYPTO-{ticker}-{description or 'N/A'}"
        hash_obj = hashlib.sha256(content.encode())
        hash_hex = hash_obj.hexdigest()[:10]  # Take first 10 chars

        # Format similar to ISIN (12 characters total)
        # Start with "XC" (eXchange Crypto) country code
        identifier = f"XC{hash_hex}"

        return identifier.upper()

    @staticmethod
    def parse_coinbase_csv(df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Parse Coinbase CSV format.

        Args:
            df: Pandas DataFrame with Coinbase data

        Returns:
            List of parsed transaction dictionaries
        """
        transactions = []

        for idx, row in df.iterrows():
            try:
                transaction_type = str(row.get("Transaction Type", "")).strip().lower()
                asset = str(row.get("Asset", "")).strip()

                # Skip non-trading transactions for now
                if transaction_type not in ["buy", "sell"]:
                    logger.info(f"Skipping Coinbase transaction type: {transaction_type}")
                    continue

                # Parse timestamp
                timestamp_str = str(row.get("Timestamp", "")).strip()
                operation_date = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%SZ").date()

                # Parse amounts
                quantity = Decimal(str(row.get("Quantity Transacted", "0")))
                total = Decimal(str(row.get("Total (inclusive of fees and/or spread)", "0")))
                fees = Decimal(str(row.get("Fees and/or Spread", "0")))

                # Calculate price per unit
                if quantity != 0:
                    price_per_share = abs(total / quantity)
                else:
                    price_per_share = Decimal("0")

                # Generate crypto ISIN
                ticker = CryptoCSVParser.normalize_crypto_ticker(asset)
                crypto_isin = CryptoCSVParser.generate_crypto_identifier(ticker, asset)

                # Map transaction type
                txn_type = "buy" if transaction_type == "buy" else "sell"

                transaction = {
                    "operation_date": operation_date,
                    "value_date": operation_date,
                    "transaction_type": txn_type,
                    "ticker": ticker,
                    "isin": crypto_isin,
                    "description": f"{asset.title()} - {transaction_type.title()}",
                    "quantity": abs(quantity),
                    "price_per_share": price_per_share,
                    "amount_eur": abs(total),  # Coinbase shows negative for buys
                    "amount_currency": abs(total),
                    "currency": str(row.get("Currency", "USD")).strip(),
                    "fees": abs(fees),
                    "order_reference": f"COINBASE-{row.get('Transaction ID', '')}",
                }

                transactions.append(transaction)

            except Exception as e:
                logger.warning(f"Error parsing Coinbase row {idx}: {str(e)}")
                continue

        return transactions

    @staticmethod
    def parse_binance_csv(df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Parse Binance CSV format.

        Args:
            df: Pandas DataFrame with Binance data

        Returns:
            List of parsed transaction dictionaries
        """
        transactions = []

        for idx, row in df.iterrows():
            try:
                side = str(row.get("Side", "")).strip().lower()
                pair = str(row.get("Pair", "")).strip()

                # Skip non-trading transactions
                if side not in ["buy", "sell"]:
                    continue

                # Parse date
                date_str = str(row.get("Date", "")).strip()
                operation_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").date()

                # Parse amounts
                amount = Decimal(str(row.get("Amount", "0")))
                price = Decimal(str(row.get("Price", "0")))
                total = Decimal(str(row.get("Total", "0")))
                fee = Decimal(str(row.get("Fee", "0")))

                # Extract base asset from pair
                ticker = CryptoCSVParser.normalize_crypto_ticker(pair)
                crypto_isin = CryptoCSVParser.generate_crypto_identifier(ticker, pair)

                transaction = {
                    "operation_date": operation_date,
                    "value_date": operation_date,
                    "transaction_type": side,
                    "ticker": ticker,
                    "isin": crypto_isin,
                    "description": f"{pair} - {side.title()}",
                    "quantity": amount,
                    "price_per_share": price,
                    "amount_eur": total,
                    "amount_currency": total,
                    "currency": "USDT",  # Binance typically uses USDT
                    "fees": fee,
                    "order_reference": f"BINANCE-{idx}",
                }

                transactions.append(transaction)

            except Exception as e:
                logger.warning(f"Error parsing Binance row {idx}: {str(e)}")
                continue

        return transactions

    @staticmethod
    def parse_kraken_csv(df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Parse Kraken CSV format.

        Args:
            df: Pandas DataFrame with Kraken data

        Returns:
            List of parsed transaction dictionaries
        """
        transactions = []

        for idx, row in df.iterrows():
            try:
                txn_type = str(row.get("type", "")).strip().lower()
                pair = str(row.get("pair", "")).strip()

                # Skip non-trading transactions
                if txn_type not in ["buy", "sell"]:
                    continue

                # Parse timestamp
                time_str = str(row.get("time", "")).strip()
                operation_date = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S.%f").date()

                # Parse amounts
                volume = Decimal(str(row.get("vol", "0")))
                price = Decimal(str(row.get("price", "0")))
                cost = Decimal(str(row.get("cost", "0")))
                fee = Decimal(str(row.get("fee", "0")))

                # Extract base asset from pair
                ticker = CryptoCSVParser.normalize_crypto_ticker(pair)
                crypto_isin = CryptoCSVParser.generate_crypto_identifier(ticker, pair)

                transaction = {
                    "operation_date": operation_date,
                    "value_date": operation_date,
                    "transaction_type": txn_type,
                    "ticker": ticker,
                    "isin": crypto_isin,
                    "description": f"{pair} - {txn_type.title()}",
                    "quantity": volume,
                    "price_per_share": price,
                    "amount_eur": cost,
                    "amount_currency": cost,
                    "currency": "USD",  # Kraken typically uses USD
                    "fees": fee,
                    "order_reference": f"KRAKEN-{row.get('txid', '')}",
                }

                transactions.append(transaction)

            except Exception as e:
                logger.warning(f"Error parsing Kraken row {idx}: {str(e)}")
                continue

        return transactions

    @staticmethod
    def parse_generic_crypto_csv(df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Parse generic crypto exchange CSV format.

        Makes best effort to map common column names.

        Args:
            df: Pandas DataFrame with generic crypto data

        Returns:
            List of parsed transaction dictionaries
        """
        transactions = []

        # Try to map common column names
        column_mappings = {
            # Date columns
            'date': ['date', 'time', 'timestamp', 'Date', 'Time', 'Timestamp'],
            # Type columns
            'type': ['type', 'side', 'operation', 'Type', 'Side', 'Operation'],
            # Asset columns
            'asset': ['asset', 'pair', 'symbol', 'ticker', 'Asset', 'Pair', 'Symbol', 'Ticker'],
            # Quantity columns
            'quantity': ['quantity', 'amount', 'vol', 'volume', 'Quantity', 'Amount', 'Vol', 'Volume'],
            # Price columns
            'price': ['price', 'rate', 'Price', 'Rate'],
            # Total columns
            'total': ['total', 'cost', 'value', 'Total', 'Cost', 'Value'],
            # Fee columns
            'fee': ['fee', 'fees', 'Fee', 'Fees'],
        }

        # Find actual column names
        mapped_columns = {}
        for key, possible_names in column_mappings.items():
            for col in df.columns:
                if col in possible_names:
                    mapped_columns[key] = col
                    break

        for idx, row in df.iterrows():
            try:
                # Skip if essential columns are missing
                if 'type' not in mapped_columns or 'asset' not in mapped_columns:
                    continue

                # Parse transaction type
                txn_type = str(row[mapped_columns['type']]).strip().lower()
                if txn_type not in ['buy', 'sell']:
                    continue

                # Parse date
                if 'date' in mapped_columns:
                    date_val = row[mapped_columns['date']]
                    # Try different date formats
                    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"]:
                        try:
                            operation_date = datetime.strptime(str(date_val), fmt).date()
                            break
                        except ValueError:
                            continue
                    else:
                        logger.warning(f"Could not parse date: {date_val}")
                        continue
                else:
                    continue

                # Parse amounts
                quantity = Decimal(str(row.get(mapped_columns.get('quantity', '0'), "0")))
                price = Decimal(str(row.get(mapped_columns.get('price', '0'), "0")))
                total = Decimal(str(row.get(mapped_columns.get('total', '0'), "0")))
                fee = Decimal(str(row.get(mapped_columns.get('fee', '0'), "0")))

                # Skip if quantity is zero (invalid transaction)
                if quantity == 0:
                    continue

                # Extract ticker
                ticker_raw = str(row[mapped_columns['asset']])
                ticker = CryptoCSVParser.normalize_crypto_ticker(ticker_raw)
                crypto_isin = CryptoCSVParser.generate_crypto_identifier(ticker, ticker_raw)

                # Calculate price if missing
                if price == 0 and quantity > 0:
                    price = total / quantity

                transaction = {
                    "operation_date": operation_date,
                    "value_date": operation_date,
                    "transaction_type": txn_type,
                    "ticker": ticker,
                    "isin": crypto_isin,
                    "description": f"{ticker_raw} - {txn_type.title()}",
                    "quantity": quantity,
                    "price_per_share": price,
                    "amount_eur": total,
                    "amount_currency": total,
                    "currency": "USD",  # Default to USD
                    "fees": fee,
                    "order_reference": f"GENERIC-{idx}",
                }

                transactions.append(transaction)

            except Exception as e:
                logger.warning(f"Error parsing generic crypto row {idx}: {str(e)}")
                continue

        return transactions

    @staticmethod
    def parse(file_content: str) -> List[Dict[str, Any]]:
        """
        Parse crypto CSV file content and detect exchange format.

        Args:
            file_content: Raw CSV file content as string

        Returns:
            List of parsed transaction dictionaries

        Raises:
            ValueError: If CSV format is invalid or no crypto transactions found
        """
        try:
            # Parse CSV with pandas
            df = pd.read_csv(StringIO(file_content))

            if df.empty:
                raise ValueError("CSV file is empty")

            # Detect exchange format
            exchange_type = CryptoCSVParser.detect_exchange_format(df)
            logger.info(f"Detected crypto exchange format: {exchange_type}")

            # Parse based on exchange type
            if exchange_type == CryptoExchangeType.COINBASE:
                transactions = CryptoCSVParser.parse_coinbase_csv(df)
            elif exchange_type == CryptoExchangeType.BINANCE:
                transactions = CryptoCSVParser.parse_binance_csv(df)
            elif exchange_type == CryptoExchangeType.KRAKEN:
                transactions = CryptoCSVParser.parse_kraken_csv(df)
            else:
                transactions = CryptoCSVParser.parse_generic_crypto_csv(df)

            if not transactions:
                raise ValueError("No valid crypto transactions found in CSV")

            logger.info(f"Successfully parsed {len(transactions)} crypto transactions from {exchange_type}")
            return transactions

        except pd.errors.EmptyDataError:
            raise ValueError("CSV file is empty")
        except pd.errors.ParserError as e:
            raise ValueError(f"CSV parsing error: {str(e)}")
        except Exception as e:
            logger.error(f"Error parsing crypto CSV: {str(e)}")
            raise ValueError(f"Failed to parse crypto CSV: {str(e)}")