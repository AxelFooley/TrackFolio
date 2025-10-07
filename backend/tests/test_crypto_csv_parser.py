"""
Tests for crypto CSV parser functionality.
"""
import pytest
from datetime import date
from decimal import Decimal
import os

from app.services.crypto_csv_parser import (
    CryptoCSVParser,
    CryptoExchangeType,
    CryptoTransactionType
)


class TestCryptoTickerNormalization:
    """Test crypto ticker normalization."""

    def test_normalize_crypto_ticker_basic(self):
        """Test basic ticker normalization."""
        assert CryptoCSVParser.normalize_crypto_ticker("BTC") == "BTC"
        assert CryptoCSVParser.normalize_crypto_ticker("ETH") == "ETH"
        assert CryptoCSVParser.normalize_crypto_ticker("btc") == "BTC"
        assert CryptoCSVParser.normalize_crypto_ticker("eth") == "ETH"

    def test_normalize_crypto_ticker_trading_pairs(self):
        """Test normalization of trading pair formats."""
        assert CryptoCSVParser.normalize_crypto_ticker("BTC-USD") == "BTC"
        assert CryptoCSVParser.normalize_crypto_ticker("BTC/USD") == "BTC"
        assert CryptoCSVParser.normalize_crypto_ticker("BTCUSD") == "BTC"
        assert CryptoCSVParser.normalize_crypto_ticker("BTCUSDT") == "BTC"
        assert CryptoCSVParser.normalize_crypto_ticker("ETH-EUR") == "ETH"
        assert CryptoCSVParser.normalize_crypto_ticker("SOL/USDT") == "SOL"

    def test_normalize_crypto_ticker_edge_cases(self):
        """Test edge cases in ticker normalization."""
        assert CryptoCSVParser.normalize_crypto_ticker("") == ""
        assert CryptoCSVParser.normalize_crypto_ticker(None) == None
        assert CryptoCSVParser.normalize_crypto_ticker("  BTC  ") == "BTC"

    def test_is_crypto_transaction(self):
        """Test crypto transaction detection."""
        # Basic crypto tickers
        assert CryptoCSVParser.is_crypto_transaction("BTC") == True
        assert CryptoCSVParser.is_crypto_transaction("ETH") == True
        assert CryptoCSVParser.is_crypto_transaction("SOL") == True

        # Trading pairs
        assert CryptoCSVParser.is_crypto_transaction("BTC-USD") == True
        assert CryptoCSVParser.is_crypto_transaction("BTC/USD") == True
        assert CryptoCSVParser.is_crypto_transaction("BTCUSDT") == True

        # Non-crypto
        assert CryptoCSVParser.is_crypto_transaction("AAPL") == False
        assert CryptoCSVParser.is_crypto_transaction("TSLA") == False
        assert CryptoCSVParser.is_crypto_transaction("") == False
        assert CryptoCSVParser.is_crypto_transaction(None) == False


class TestCryptoIdentifierGeneration:
    """Test crypto ISIN-like identifier generation."""

    def test_generate_crypto_identifier_basic(self):
        """Test basic identifier generation."""
        isin = CryptoCSVParser.generate_crypto_identifier("BTC", "Bitcoin")
        assert isin.startswith("XC")
        assert len(isin) == 12

    def test_generate_crypto_identifier_deterministic(self):
        """Test that same input generates same identifier."""
        isin1 = CryptoCSVParser.generate_crypto_identifier("BTC", "Bitcoin")
        isin2 = CryptoCSVParser.generate_crypto_identifier("BTC", "Bitcoin")
        assert isin1 == isin2

    def test_generate_crypto_identifier_unique_per_asset(self):
        """Test that different assets generate different identifiers."""
        btc_isin = CryptoCSVParser.generate_crypto_identifier("BTC", "Bitcoin")
        eth_isin = CryptoCSVParser.generate_crypto_identifier("ETH", "Ethereum")
        assert btc_isin != eth_isin

    def test_generate_crypto_identifier_error_handling(self):
        """Test error handling for invalid inputs."""
        with pytest.raises(ValueError):
            CryptoCSVParser.generate_crypto_identifier("", "Bitcoin")

        with pytest.raises(ValueError):
            CryptoCSVParser.generate_crypto_identifier(None, "Bitcoin")


class TestCoinbaseCSVParser:
    """Test Coinbase CSV parsing."""

    def test_parse_coinbase_csv(self):
        """Test parsing Coinbase CSV format."""
        csv_content = """Timestamp,Transaction Type,Asset,Quantity Transacted,Spot Price Currency,Spot Price at Transaction,Subtotal,Total (inclusive of fees and/or spread),Fees and/or Spread,Currency,Notes,Transaction ID
2024-01-15T10:30:00Z,Buy,BTC,0.025,USD,42150.00,1053.75,1055.50,1.75,USD,Bought Bitcoin,CB123456789
2024-01-20T14:22:00Z,Sell,ETH,0.5,USD,2680.00,1340.00,1338.25,1.75,USD,Sold Ethereum,CB987654321"""

        transactions = CryptoCSVParser.parse(csv_content)

        assert len(transactions) == 2

        # Check first transaction (BTC buy)
        btc_tx = transactions[0]
        assert btc_tx["ticker"] == "BTC"
        assert btc_tx["transaction_type"] == "buy"
        assert btc_tx["quantity"] == Decimal("0.025")
        assert btc_tx["price_per_share"] == Decimal("42220.0")  # 1055.50 / 0.025
        assert btc_tx["amount_eur"] == Decimal("1055.50")
        assert btc_tx["fees"] == Decimal("1.75")
        assert btc_tx["operation_date"] == date(2024, 1, 15)
        assert btc_tx["isin"].startswith("XC")  # Generated crypto ISIN
        assert btc_tx["order_reference"] == "COINBASE-CB123456789"

        # Check second transaction (ETH sell)
        eth_tx = transactions[1]
        assert eth_tx["ticker"] == "ETH"
        assert eth_tx["transaction_type"] == "sell"
        assert eth_tx["quantity"] == Decimal("0.5")
        assert eth_tx["operation_date"] == date(2024, 1, 20)


class TestBinanceCSVParser:
    """Test Binance CSV parsing."""

    def test_parse_binance_csv(self):
        """Test parsing Binance CSV format."""
        csv_content = """Date,Pair,Type,Side,Price,Amount,Total,Fee,Fee Coin
2024-01-15 10:30:00,BTCUSDT,MARKET,buy,42150.00,0.025,1053.75,0.0005,BNB
2024-01-20 14:22:00,ETHUSDT,LIMIT,sell,2680.00,0.5,1340.00,0.001,ETH"""

        transactions = CryptoCSVParser.parse(csv_content)

        assert len(transactions) == 2

        # Check first transaction (BTC buy)
        btc_tx = transactions[0]
        assert btc_tx["ticker"] == "BTC"
        assert btc_tx["transaction_type"] == "buy"
        assert btc_tx["quantity"] == Decimal("0.025")
        assert btc_tx["price_per_share"] == Decimal("42150.00")
        assert btc_tx["amount_eur"] == Decimal("1053.75")
        assert btc_tx["fees"] == Decimal("0.0005")
        assert btc_tx["currency"] == "USDT"
        assert btc_tx["operation_date"] == date(2024, 1, 15)


class TestKrakenCSVParser:
    """Test Kraken CSV parsing."""

    def test_parse_kraken_csv(self):
        """Test parsing Kraken CSV format."""
        csv_content = """txid,time,type,ordertype,pair,price,cost,fee,vol
KRAKEN123,2024-01-15 10:30:00.123,buy,market,XBT/USD,42150.00,1053.75,0.525,0.025
KRAKEN456,2024-01-20 14:22:00.456,sell,limit,ETH/USD,2680.00,1340.00,0.67,0.5"""

        transactions = CryptoCSVParser.parse(csv_content)

        assert len(transactions) == 2

        # Check first transaction (BTC buy - note Kraken uses XBT for Bitcoin)
        btc_tx = transactions[0]
        assert btc_tx["ticker"] == "XBT"  # Kraken uses XBT, not BTC
        assert btc_tx["transaction_type"] == "buy"
        assert btc_tx["quantity"] == Decimal("0.025")
        assert btc_tx["price_per_share"] == Decimal("42150.00")
        assert btc_tx["amount_eur"] == Decimal("1053.75")
        assert btc_tx["fees"] == Decimal("0.525")


class TestGenericCryptoCSVParser:
    """Test generic crypto CSV parsing."""

    def test_parse_generic_csv(self):
        """Test parsing generic crypto CSV format."""
        csv_content = """Date,Asset,Type,Quantity,Price,Total,Fee,Currency
2024-01-15,BTC-USD,Buy,0.025,42150.00,1053.75,1.75,USD
2024-01-20,ETH/USD,Sell,0.5,2680.00,1340.00,1.75,USD"""

        transactions = CryptoCSVParser.parse(csv_content)

        assert len(transactions) == 2

        # Check first transaction
        btc_tx = transactions[0]
        assert btc_tx["ticker"] == "BTC"  # Normalized from BTC-USD
        assert btc_tx["transaction_type"] == "buy"
        assert btc_tx["quantity"] == Decimal("0.025")
        assert btc_tx["price_per_share"] == Decimal("42150.00")


class TestExchangeDetection:
    """Test exchange format detection."""

    def test_detect_coinbase_format(self):
        """Test Coinbase format detection."""
        csv_content = """Timestamp,Transaction Type,Asset,Quantity Transacted,Spot Price Currency
2024-01-15T10:30:00Z,Buy,BTC,0.025,USD"""

        import pandas as pd
        from io import StringIO
        df = pd.read_csv(StringIO(csv_content))

        detected = CryptoCSVParser.detect_exchange_format(df)
        assert detected == CryptoExchangeType.COINBASE

    def test_detect_binance_format(self):
        """Test Binance format detection."""
        csv_content = """Date,Pair,Type,Side,Price,Amount
2024-01-15 10:30:00,BTCUSDT,MARKET,buy,42150.00,0.025"""

        import pandas as pd
        from io import StringIO
        df = pd.read_csv(StringIO(csv_content))

        detected = CryptoCSVParser.detect_exchange_format(df)
        assert detected == CryptoExchangeType.BINANCE

    def test_detect_kraken_format(self):
        """Test Kraken format detection."""
        csv_content = """txid,time,type,ordertype,pair,price
KRAKEN123,2024-01-15 10:30:00.123,buy,market,XBT/USD,42150.00"""

        import pandas as pd
        from io import StringIO
        df = pd.read_csv(StringIO(csv_content))

        detected = CryptoCSVParser.detect_exchange_format(df)
        assert detected == CryptoExchangeType.KRAKEN


class TestErrorHandling:
    """Test error handling in crypto CSV parser."""

    def test_empty_csv(self):
        """Test handling of empty CSV."""
        with pytest.raises(ValueError, match="CSV file is empty"):
            CryptoCSVParser.parse("")

    def test_invalid_csv_format(self):
        """Test handling of invalid CSV format."""
        csv_content = """Invalid,CSV,Format
No,proper,headers"""

        with pytest.raises(ValueError):
            CryptoCSVParser.parse(csv_content)

    def test_invalid_date_format(self):
        """Test handling of invalid date formats."""
        csv_content = """Date,Asset,Type,Quantity,Price,Total,Fee,Currency
invalid-date,BTC,Buy,0.025,42150.00,1053.75,1.75,USD"""

        # Should not crash, but will raise error for CSV with no valid transactions
        with pytest.raises(ValueError, match="No valid crypto transactions found"):
            CryptoCSVParser.parse(csv_content)


def test_parse_sample_files():
    """Test parsing actual sample CSV files."""
    sample_dir = os.path.join(os.path.dirname(__file__), "sample_crypto_csv")

    # Test Coinbase sample
    coinbase_file = os.path.join(sample_dir, "coinbase_sample.csv")
    if os.path.exists(coinbase_file):
        with open(coinbase_file, 'r') as f:
            content = f.read()
            transactions = CryptoCSVParser.parse(content)
            assert len(transactions) == 4

            # Check that all have crypto ISINs
            for tx in transactions:
                assert tx["isin"].startswith("XC")
                assert tx["ticker"] in ["BTC", "ETH", "SOL", "ADA"]

    # Test Binance sample
    binance_file = os.path.join(sample_dir, "binance_sample.csv")
    if os.path.exists(binance_file):
        with open(binance_file, 'r') as f:
            content = f.read()
            transactions = CryptoCSVParser.parse(content)
            assert len(transactions) == 4

    # Test Kraken sample
    kraken_file = os.path.join(sample_dir, "kraken_sample.csv")
    if os.path.exists(kraken_file):
        with open(kraken_file, 'r') as f:
            content = f.read()
            transactions = CryptoCSVParser.parse(content)
            assert len(transactions) == 4

    # Test generic sample
    generic_file = os.path.join(sample_dir, "generic_crypto_sample.csv")
    if os.path.exists(generic_file):
        with open(generic_file, 'r') as f:
            content = f.read()
            transactions = CryptoCSVParser.parse(content)
            assert len(transactions) == 4