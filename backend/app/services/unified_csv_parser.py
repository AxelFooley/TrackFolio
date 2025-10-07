"""
Unified CSV Parser that detects and handles both stock broker (Directa) and crypto exchange formats.

This is the main entry point for CSV parsing that automatically detects the format
and routes to the appropriate parser.
"""
import pandas as pd
import logging
from typing import List, Dict, Any

from app.services.csv_parser import DirectaCSVParser
from app.services.crypto_csv_parser import CryptoCSVParser

logger = logging.getLogger(__name__)


class UnifiedCSVParser:
    """
    Unified CSV parser that automatically detects format and routes to appropriate parser.

    Handles:
    - Directa broker CSV format (stocks/ETFs with ISINs)
    - Crypto exchange CSV formats (Coinbase, Binance, Kraken, etc.)
    - Mixed CSV files (rare but possible)
    """

    @staticmethod
    def detect_csv_format(file_content: str) -> str:
        """
        Detect the CSV format type.

        Args:
            file_content: Raw CSV file content

        Returns:
            Format type: 'directa', 'crypto', or 'unknown'
        """
        try:
            # Split into lines for analysis
            lines = file_content.splitlines()

            if len(lines) < 2:
                return 'unknown'

            # Check for Directa format (first 9 rows are metadata)
            if len(lines) >= 10:
                first_10_lines = lines[:10]

                # Directa specific patterns in first lines
                directa_patterns = [
                    "Conto :",
                    "Data estrazione :",
                    "Compravendite ordinati per Data Operazione",
                    "Dal :",
                    "al :"
                ]

                directa_count = sum(
                    1 for line in first_10_lines
                    for pattern in directa_patterns
                    if pattern in line
                )

                if directa_count >= 3:  # If we match multiple Directa patterns
                    return 'directa'

            # For non-Directa formats, check column headers
            # Look for crypto-specific column names in first row (for crypto) or line 9 (for Directa)
            data_start_line = 9 if len(lines) > 9 and 'Conto :' in lines[0] else 0

            if data_start_line < len(lines):
                # Try to parse header row
                header_line = lines[data_start_line]
                columns = [col.strip() for col in header_line.split(',')]

                # Enhanced crypto column detection
                crypto_column_patterns = [
                    'Asset', 'Quantity Transacted', 'Pair', 'Side', 'Transaction Type',
                    'Spot Price', 'Fee Coin', 'txid', 'ordertype', 'Timestamp'
                ]

                crypto_matches = sum(
                    1 for column in columns
                    for pattern in crypto_column_patterns
                    if pattern.lower() in column.lower()
                )

                # Lower threshold for crypto detection - more sensitive
                if crypto_matches >= 1:
                    return 'crypto'

            # Additional check: look for crypto tickers in the data
            sample_lines = lines[data_start_line + 1:data_start_line + 6]  # Sample 5 data rows

            crypto_ticker_patterns = ['BTC', 'ETH', 'SOL', 'ADA', 'DOT', 'AVAX', 'USDT', 'USDC']
            crypto_ticker_count = 0

            for line in sample_lines:
                # Check for crypto ticker patterns
                found_crypto = False
                for ticker in crypto_ticker_patterns:
                    # Look for trading pair formats
                    if f"{ticker}-" in line or f"{ticker}/" in line or f"{ticker}USD" in line or f"{ticker}USDT" in line:
                        crypto_ticker_count += 1
                        found_crypto = True
                        break
                    # Also check for standalone crypto tickers
                    elif f",{ticker}," in line or f",{ticker} " in line:
                        crypto_ticker_count += 1
                        found_crypto = True
                        break

                if not found_crypto:
                    # Check for standalone tickers at start of line
                    for ticker in crypto_ticker_patterns:
                        if line.startswith(f"{ticker},") or line.startswith(f"{ticker} "):
                            crypto_ticker_count += 1
                            break

            if crypto_ticker_count >= 1:  # Lower threshold
                return 'crypto'

            return 'unknown'

        except Exception as e:
            logger.warning(f"Error detecting CSV format: {str(e)}")
            return 'unknown'

    @staticmethod
    def parse(file_content: str) -> List[Dict[str, Any]]:
        """
        Parse CSV file content with automatic format detection.

        Args:
            file_content: Raw CSV file content as string

        Returns:
            List of parsed transaction dictionaries

        Raises:
            ValueError: If CSV format cannot be detected or parsing fails
        """
        try:
            # Detect format
            format_type = UnifiedCSVParser.detect_csv_format(file_content)
            logger.info(f"Detected CSV format: {format_type}")

            # Route to appropriate parser
            if format_type == 'directa':
                return DirectaCSVParser.parse(file_content)
            elif format_type == 'crypto':
                return CryptoCSVParser.parse(file_content)
            else:
                # Try both parsers and see which works
                try:
                    # Try Directa first
                    return DirectaCSVParser.parse(file_content)
                except ValueError as directa_error:
                    logger.debug(f"Directa parser failed: {str(directa_error)}")

                    try:
                        # Try crypto parser
                        return CryptoCSVParser.parse(file_content)
                    except ValueError as crypto_error:
                        logger.debug(f"Crypto parser failed: {str(crypto_error)}")

                        raise ValueError(
                            f"Unable to determine CSV format. "
                            f"Directa parser error: {str(directa_error)}. "
                            f"Crypto parser error: {str(crypto_error)}. "
                            f"Please ensure your CSV file is in a supported format."
                        )

        except Exception as e:
            logger.error(f"Error parsing CSV with unified parser: {str(e)}")
            raise ValueError(f"Failed to parse CSV: {str(e)}")

    @staticmethod
    def get_format_description(format_type: str) -> str:
        """
        Get human-readable description of detected format.

        Args:
            format_type: Format type string

        Returns:
            Description string
        """
        descriptions = {
            'directa': 'Directa broker format (Italian stock broker)',
            'crypto': 'Cryptocurrency exchange format (Coinbase, Binance, Kraken, etc.)',
            'unknown': 'Unknown or unsupported format'
        }
        return descriptions.get(format_type, 'Unknown format')