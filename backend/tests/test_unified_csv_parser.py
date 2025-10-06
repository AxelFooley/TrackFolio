"""
Tests for unified CSV parser functionality.
"""
import pytest
import os
from datetime import date

from app.services.unified_csv_parser import UnifiedCSVParser


class TestUnifiedCSVFormatDetection:
    """Test CSV format detection in unified parser."""

    def test_detect_directa_format(self):
        """Test detection of Directa broker format."""
        # Sample Directa CSV header (first 10 lines)
        csv_content = """Conto : 72024 Anghelone Alessandro
Data estrazione : 1-10-2025 10:52:29

Compravendite ordinati per Data Operazione
Dal : 04-04-2025
al : 01-10-2025


Data operazione,Data valuta,Tipo operazione,Ticker,Isin,Protocollo,Descrizione,Quantità,Importo euro,Importo Divisa,Divisa,Riferimento ordine
05-04-2025,08-04-2025,Acquisto,1TSLA,US88160R1014,12345,Tesla Inc,10,850.00,850.00,USD,ORD123"""

        format_type = UnifiedCSVParser.detect_csv_format(csv_content)
        assert format_type == 'directa'

    def test_detect_crypto_format_coinbase(self):
        """Test detection of Coinbase crypto format."""
        csv_content = """Timestamp,Transaction Type,Asset,Quantity Transacted,Spot Price Currency,Spot Price at Transaction,Subtotal,Total (inclusive of fees and/or spread),Fees and/or Spread,Currency,Notes,Transaction ID
2024-01-15T10:30:00Z,Buy,BTC,0.025,USD,42150.00,1053.75,1055.50,1.75,USD,Bought Bitcoin,CB123456789"""

        format_type = UnifiedCSVParser.detect_csv_format(csv_content)
        assert format_type == 'crypto'

    def test_detect_crypto_format_binance(self):
        """Test detection of Binance crypto format."""
        csv_content = """Date,Pair,Type,Side,Price,Amount,Total,Fee,Fee Coin
2024-01-15 10:30:00,BTCUSDT,MARKET,buy,42150.00,0.025,1053.75,0.0005,BNB"""

        format_type = UnifiedCSVParser.detect_csv_format(csv_content)
        assert format_type == 'crypto'

    def test_detect_crypto_by_ticker_patterns(self):
        """Test crypto detection by ticker patterns in data."""
        csv_content = """Date,Asset,Type,Quantity,Price,Total
2024-01-15,BTC-USD,Buy,0.025,42150.00,1053.75
2024-01-20,ETH/USD,Sell,0.5,2680.00,1340.00"""

        format_type = UnifiedCSVParser.detect_csv_format(csv_content)
        assert format_type == 'crypto'

    def test_detect_unknown_format(self):
        """Test detection of unknown/unsupported format."""
        csv_content = """Some,Random,CSV,Format
No,patterns,match
Unknown,data"""

        format_type = UnifiedCSVParser.detect_csv_format(csv_content)
        assert format_type == 'unknown'

    def test_detect_empty_csv(self):
        """Test detection with empty CSV."""
        format_type = UnifiedCSVParser.detect_csv_format("")
        assert format_type == 'unknown'

    def test_detect_short_csv(self):
        """Test detection with very short CSV."""
        csv_content = """Header,Only,No,Data"""
        format_type = UnifiedCSVParser.detect_csv_format(csv_content)
        assert format_type == 'unknown'


class TestUnifiedCSVParsing:
    """Test end-to-end CSV parsing with format detection."""

    def test_parse_directa_csv(self):
        """Test parsing Directa CSV through unified parser."""
        # Full Directa CSV structure
        csv_content = """Conto : 72024 Anghelone Alessandro
Data estrazione : 1-10-2025 10:52:29

Compravendite ordinati per Data Operazione
Dal : 04-04-2025
al : 01-10-2025


Data operazione,Data valuta,Tipo operazione,Ticker,Isin,Protocollo,Descrizione,Quantità,Importo euro,Importo Divisa,Divisa,Riferimento ordine
05-04-2025,08-04-2025,Acquisto,TSLA,US88160R1014,12345,Tesla Inc,10,850.00,850.00,USD,ORD123
06-04-2025,09-04-2025,Acquisto,AAPL,US0378331005,12346,Apple Inc,5,850.00,850.00,USD,ORD124
07-04-2025,10-04-2025,Commissioni,,,,,,,,1.50,,EUR,ORD123"""

        transactions = UnifiedCSVParser.parse(csv_content)
        assert len(transactions) == 2

        # Check first transaction
        tsla_tx = transactions[0]
        assert tsla_tx["ticker"] == "TSLA"
        assert tsla_tx["isin"] == "US88160R1014"
        assert tsla_tx["transaction_type"] == "buy"
        assert tsla_tx["quantity"] == 10

    def test_parse_crypto_csv_coinbase(self):
        """Test parsing Coinbase CSV through unified parser."""
        csv_content = """Timestamp,Transaction Type,Asset,Quantity Transacted,Spot Price Currency,Spot Price at Transaction,Subtotal,Total (inclusive of fees and/or spread),Fees and/or Spread,Currency,Notes,Transaction ID
2024-01-15T10:30:00Z,Buy,BTC,0.025,USD,42150.00,1053.75,1055.50,1.75,USD,Bought Bitcoin,CB123456789
2024-01-20T14:22:00Z,Sell,ETH,0.5,USD,2680.00,1340.00,1338.25,1.75,USD,Sold Ethereum,CB987654321"""

        transactions = UnifiedCSVParser.parse(csv_content)
        assert len(transactions) == 2

        # Check first transaction
        btc_tx = transactions[0]
        assert btc_tx["ticker"] == "BTC"
        assert btc_tx["transaction_type"] == "buy"
        assert btc_tx["isin"].startswith("XC")  # Crypto ISIN
        assert float(btc_tx["quantity"]) == 0.025

    def test_parse_crypto_csv_binance(self):
        """Test parsing Binance CSV through unified parser."""
        csv_content = """Date,Pair,Type,Side,Price,Amount,Total,Fee,Fee Coin
2024-01-15 10:30:00,BTCUSDT,MARKET,buy,42150.00,0.025,1053.75,0.0005,BNB
2024-01-20 14:22:00,ETHUSDT,LIMIT,sell,2680.00,0.5,1340.00,0.001,ETH"""

        transactions = UnifiedCSVParser.parse(csv_content)
        assert len(transactions) == 2

        # Check first transaction
        btc_tx = transactions[0]
        assert btc_tx["ticker"] == "BTC"
        assert btc_tx["transaction_type"] == "buy"
        assert btc_tx["isin"].startswith("XC")  # Crypto ISIN

    def test_parse_crypto_csv_generic(self):
        """Test parsing generic crypto CSV through unified parser."""
        csv_content = """Date,Asset,Type,Quantity,Price,Total,Fee,Currency
2024-01-15,BTC-USD,Buy,0.025,42150.00,1053.75,1.75,USD
2024-01-20,ETH/USD,Sell,0.5,2680.00,1340.00,1.75,USD"""

        transactions = UnifiedCSVParser.parse(csv_content)
        assert len(transactions) == 2

        # Check first transaction
        btc_tx = transactions[0]
        assert btc_tx["ticker"] == "BTC"  # Normalized from BTC-USD
        assert btc_tx["transaction_type"] == "buy"
        assert btc_tx["isin"].startswith("XC")

    def test_parse_with_fallback_parsing(self):
        """Test parsing with fallback when initial detection is uncertain."""
        # This CSV doesn't clearly match any format, but should still work
        csv_content = """Date,Ticker,Type,Quantity,Price,Total
2024-01-15,TSLA,Buy,10,170.00,1700.00
2024-01-20,AAPL,Sell,5,150.00,750.00"""

        # Should try both parsers and succeed with Directa parser
        transactions = UnifiedCSVParser.parse(csv_content)
        assert len(transactions) == 2


class TestFormatDescription:
    """Test format description functionality."""

    def test_get_format_descriptions(self):
        """Test getting human-readable format descriptions."""
        assert "Directa" in UnifiedCSVParser.get_format_description('directa')
        assert "cryptocurrency" in UnifiedCSVParser.get_format_description('crypto').lower()
        assert "Unknown" in UnifiedCSVParser.get_format_description('unknown')
        assert "Unknown" in UnifiedCSVParser.get_format_description('invalid')


class TestErrorHandling:
    """Test error handling in unified CSV parser."""

    def test_parse_invalid_csv_both_parsers_fail(self):
        """Test parsing when both Directa and crypto parsers fail."""
        csv_content = """Completely,Invalid,CSV,Format
No,proper,structure
Missing,required,columns"""

        with pytest.raises(ValueError, match="Unable to determine CSV format"):
            UnifiedCSVParser.parse(csv_content)

    def test_parse_empty_csv(self):
        """Test parsing empty CSV."""
        with pytest.raises(ValueError, match=r"(CSV file is empty|Failed to parse CSV)"):
            UnifiedCSVParser.parse("")

    def test_detect_format_with_exception_handling(self):
        """Test format detection with malformed input."""
        # This should not crash, even with malformed input
        format_type = UnifiedCSVParser.detect_csv_format("invalid,csv\nwith,no,clear,patterns")
        assert format_type in ['unknown', 'crypto', 'directa']


def test_parse_sample_files():
    """Test parsing actual sample CSV files through unified parser."""
    sample_dir = os.path.join(os.path.dirname(__file__), "sample_crypto_csv")

    # Test all crypto sample files
    sample_files = [
        "coinbase_sample.csv",
        "binance_sample.csv",
        "kraken_sample.csv",
        "generic_crypto_sample.csv"
    ]

    for filename in sample_files:
        file_path = os.path.join(sample_dir, filename)
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                content = f.read()

                # Detect format first
                format_type = UnifiedCSVParser.detect_csv_format(content)
                assert format_type == 'crypto', f"File {filename} should be detected as crypto format"

                # Parse through unified parser
                transactions = UnifiedCSVParser.parse(content)
                assert len(transactions) > 0, f"File {filename} should parse successfully"

                # Verify crypto transactions
                for tx in transactions:
                    assert tx["isin"].startswith("XC"), f"Transaction should have crypto ISIN"
                    # Normalize tickers (e.g., XBT -> BTC for Kraken)
                    ticker = tx["ticker"]
                    if ticker == "XBT":
                        ticker = "BTC"
                    assert ticker in ["BTC", "ETH", "SOL", "ADA"], f"Unexpected ticker: {ticker}"