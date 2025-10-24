"""
CSV Parser for Directa broker CSV files.

CRITICAL: Skips first 9 rows as per PRD Section 3 - Data Sources.
"""
from io import StringIO
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any
import pandas as pd
import logging

from app.services.ticker_normalizer import TickerNormalizer

logger = logging.getLogger(__name__)


class DirectaCSVParser:
    """
    Parser for Directa broker CSV format.

    CSV Structure (from PRD):
    Row 0: "Conto : 72024 Anghelone Alessandro" (header, skip)
    Row 1: "Data estrazione : 1-10-2025 10:52:29" (metadata, skip)
    Row 2: Empty (skip)
    Row 3: "Compravendite ordinati per Data Operazione" (skip)
    Row 4: "Dal : 04-04-2025" (date range, skip)
    Row 5: "al : 01-10-2025" (date range, skip)
    Row 6: Empty (skip)
    Row 7: "Il file include i primi 3000 movimenti" (skip)
    Row 8: Empty (skip)
    Row 9: ACTUAL HEADER ROW - "Data operazione,Data valuta,Tipo operazione..."
    Row 10+: Transaction data
    """

    # Expected column names (Italian from Directa)
    EXPECTED_COLUMNS = [
        "Data operazione",
        "Data valuta",
        "Tipo operazione",
        "Ticker",
        "Isin",
        "Protocollo",
        "Descrizione",
        "Quantità",
        "Importo euro",
        "Importo Divisa",
        "Divisa",
        "Riferimento ordine"
    ]

    @staticmethod
    def parse(file_content: str) -> List[Dict[str, Any]]:
        """
        Parse Directa CSV file content.

        Two-pass parsing:
        1. Parse buy/sell transactions
        2. Parse "Commissioni" rows and match fees to transactions by order reference

        Args:
            file_content: Raw CSV file content as string

        Returns:
            List of parsed transaction dictionaries with fees

        Raises:
            ValueError: If CSV format is invalid
        """
        try:
            # Skip first 9 rows as per PRD
            lines = file_content.splitlines()

            if len(lines) < 10:
                raise ValueError("CSV file too short. Expected at least 10 rows.")

            # Get data starting from row 9 (0-indexed)
            data_lines = lines[9:]
            csv_data = '\n'.join(data_lines)

            # Parse with pandas (Detect delimiter automatically)
            df = pd.read_csv(
                StringIO(csv_data),
                delimiter=',',  # Change to comma for comma-separated format
                skipinitialspace=True
            )

            # Validate columns
            DirectaCSVParser._validate_columns(df)

            # PASS 1: Parse buy/sell transactions
            transactions = []  # List of transaction dicts
            for idx, row in df.iterrows():
                tipo_operazione = str(row["Tipo operazione"]).strip()

                if tipo_operazione in ["Acquisto", "Vendita"]:
                    try:
                        transaction = DirectaCSVParser._parse_row(row)
                        transactions.append(transaction)
                    except Exception as e:
                        logger.warning(f"Skipping buy/sell row {idx + 10}: {str(e)}")
                        continue

            # PASS 2: Parse "Commissioni" rows and match fees to transactions
            # Build index of transactions by order_reference for fee matching
            # Note: Multiple transactions can share the same order_reference (partial fills)
            transaction_index = {}  # Dict[order_reference, List[transaction_dict]]
            for transaction in transactions:
                order_ref = transaction["order_reference"]
                if order_ref not in transaction_index:
                    transaction_index[order_ref] = []
                transaction_index[order_ref].append(transaction)

            fees_matched = 0
            fees_unmatched = 0

            for idx, row in df.iterrows():
                tipo_operazione = str(row["Tipo operazione"]).strip()

                if tipo_operazione == "Commissioni":
                    try:
                        # Extract order reference and fee amount
                        order_reference = str(row["Riferimento ordine"]).strip()
                        if not order_reference or order_reference == "nan":
                            logger.warning(f"Commissioni row {idx + 10} missing order reference, skipping")
                            fees_unmatched += 1
                            continue

                        # Parse fee amount (negative in CSV, store as positive)
                        fee_amount = DirectaCSVParser._parse_decimal(row["Importo euro"])
                        fee_amount = abs(fee_amount)

                        # Match to transaction(s)
                        if order_reference in transaction_index:
                            # For partial fills, split fee equally among all fills
                            txns = transaction_index[order_reference]
                            fee_per_txn = fee_amount / len(txns)

                            for txn in txns:
                                # Add fee to existing fee (in case multiple fee rows for same order)
                                txn["fees"] = txn.get("fees", Decimal("0")) + fee_per_txn

                            fees_matched += 1
                        else:
                            logger.warning(
                                f"Commissioni row {idx + 10} has order reference {order_reference} "
                                f"but no matching transaction found"
                            )
                            fees_unmatched += 1

                    except Exception as e:
                        logger.warning(f"Error parsing Commissioni row {idx + 10}: {str(e)}")
                        fees_unmatched += 1
                        continue

            if not transactions:
                raise ValueError("No valid transactions found in CSV")

            transaction_list = transactions
            logger.info(
                f"Successfully parsed {len(transaction_list)} transactions, "
                f"matched {fees_matched} fees, {fees_unmatched} fees unmatched"
            )
            return transaction_list

        except pd.errors.EmptyDataError:
            raise ValueError("CSV file is empty")
        except pd.errors.ParserError as e:
            raise ValueError(f"CSV parsing error: {str(e)}")
        except Exception as e:
            logger.error(f"Error parsing CSV: {str(e)}")
            raise ValueError(f"Failed to parse CSV: {str(e)}")

    @staticmethod
    def _validate_columns(df: pd.DataFrame) -> None:
        """Validate that required columns exist."""
        missing_columns = set(DirectaCSVParser.EXPECTED_COLUMNS) - set(df.columns)
        if missing_columns:
            raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")

    @staticmethod
    def _parse_row(row: pd.Series) -> Dict[str, Any]:
        """
        Parse a single CSV row into a transaction dictionary.

        Args:
            row: Pandas Series representing a CSV row

        Returns:
            Dictionary with parsed transaction data

        Raises:
            ValueError: If row data is invalid
        """
        # Parse dates (DD-MM-YYYY format)
        operation_date = DirectaCSVParser._parse_date(row["Data operazione"])
        value_date = DirectaCSVParser._parse_date(row["Data valuta"])

        # Parse transaction type
        tipo_operazione = str(row["Tipo operazione"]).strip()
        if tipo_operazione not in ["Acquisto", "Vendita"]:
            raise ValueError(f"Invalid transaction type: {tipo_operazione}")

        transaction_type = "buy" if tipo_operazione == "Acquisto" else "sell"

        # Parse ticker and normalize
        ticker_raw = str(row["Ticker"]).strip()
        if not ticker_raw or ticker_raw == "nan":
            raise ValueError("Ticker is required")

        ticker = TickerNormalizer.normalize(ticker_raw)

        # Validate ISIN (now required)
        isin = str(row["Isin"]).strip() if pd.notna(row["Isin"]) else None
        if not isin or isin == "nan":
            raise ValueError(f"ISIN is required for ticker {ticker}. Cannot import without ISIN.")

        if len(isin) != 12:
            raise ValueError(f"Invalid ISIN format: {isin}. Must be 12 characters.")

        description = str(row["Descrizione"]).strip()

        # Parse numeric fields
        quantity = DirectaCSVParser._parse_decimal(row["Quantità"])
        if quantity <= 0:
            raise ValueError("Quantity must be greater than 0")

        amount_eur = DirectaCSVParser._parse_decimal(row["Importo euro"])
        amount_currency = DirectaCSVParser._parse_decimal(row["Importo Divisa"])

        # Parse currency
        currency = str(row["Divisa"]).strip() if pd.notna(row["Divisa"]) else "EUR"

        # Calculate price per share
        # Amount is negative for purchases, positive for sales in Directa CSV
        price_per_share = abs(amount_eur / quantity)

        # Parse order reference (for deduplication)
        order_reference = str(row["Riferimento ordine"]).strip()
        if not order_reference or order_reference == "nan":
            raise ValueError("Order reference is required for deduplication")

        return {
            "operation_date": operation_date,
            "value_date": value_date,
            "transaction_type": transaction_type,
            "ticker": ticker,
            "isin": isin,
            "description": description,
            "quantity": quantity,
            "price_per_share": price_per_share,
            "amount_eur": abs(amount_eur),  # Store as positive
            "amount_currency": abs(amount_currency) if amount_currency != 0 else 0,
            "currency": currency,
            "fees": Decimal("0"),  # Default to 0, manually added later
            "order_reference": order_reference,
        }

    @staticmethod
    def _parse_date(date_str: str) -> datetime.date:
        """
        Parse date from DD-MM-YYYY format.

        Args:
            date_str: Date string in DD-MM-YYYY format

        Returns:
            datetime.date object

        Raises:
            ValueError: If date format is invalid
        """
        try:
            return datetime.strptime(date_str.strip(), "%d-%m-%Y").date()
        except (ValueError, AttributeError) as e:
            raise ValueError(f"Invalid date format '{date_str}'. Expected DD-MM-YYYY")

    @staticmethod
    def _parse_decimal(value: Any) -> Decimal:
        """
        Parse decimal value from string or number.

        Args:
            value: Value to parse

        Returns:
            Decimal value

        Raises:
            ValueError: If value cannot be converted to Decimal
        """
        try:
            if pd.isna(value):
                return Decimal("0")

            # Handle string values with potential formatting
            if isinstance(value, str):
                # Remove spaces and replace comma with dot
                value = value.strip().replace(" ", "").replace(",", ".")

            return Decimal(str(value))
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid numeric value: {value}")
