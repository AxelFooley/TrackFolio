#!/usr/bin/env python3
"""
Test script for enhanced crypto validation schemas.

This script tests the crypto-specific validation functionality
to ensure all schemas work correctly with cryptocurrency data.
"""
import sys
import os
from decimal import Decimal

# Import CryptoValidationError for specific error handling
from app.schemas.crypto_validators import CryptoValidationError
from datetime import date, datetime

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.schemas.transaction import ManualTransactionCreate, TransactionCreate, TransactionResponse
from app.schemas.position import PositionResponse, PositionCreate
from app.schemas.price import RealtimePriceResponse, PriceResponse
from app.schemas.portfolio import PortfolioOverview, AssetAllocation
from app.schemas.crypto_validators import (
    validate_crypto_transaction_data, validate_crypto_ticker,
    generate_crypto_identifier, validate_crypto_isin
)
from app.models.position import AssetType


def test_crypto_transaction_schemas():
    """Test crypto transaction schemas."""
    print("Testing crypto transaction schemas...")

    # Test ManualTransactionCreate with crypto
    crypto_tx = ManualTransactionCreate(
        operation_date=date(2025, 1, 15),
        ticker="BTC",
        type="buy",
        quantity=Decimal("0.025"),
        amount=Decimal("42000.00"),
        currency="USD",
        fees=Decimal("2.50"),
        asset_type=AssetType.CRYPTO
    )
    print(f"✅ ManualTransactionCreate (crypto): {crypto_tx.ticker}, ISIN: {crypto_tx.isin}")

    # Test TransactionCreate with crypto
    crypto_tx_full = TransactionCreate(
        operation_date=date(2025, 1, 15),
        value_date=date(2025, 1, 15),
        transaction_type="buy",
        ticker="ETH",
        description="Ethereum purchase",
        quantity=Decimal("1.5"),
        price_per_share=Decimal("2500.00"),
        amount_eur=Decimal("2272.73"),
        amount_currency=Decimal("2500.00"),
        currency="USD",
        fees=Decimal("5.00"),
        asset_type=AssetType.CRYPTO
    )
    print(f"✅ TransactionCreate (crypto): {crypto_tx_full.ticker}, ISIN: {crypto_tx_full.isin}")

    # Test TransactionResponse with crypto
    crypto_tx_response = TransactionResponse(
        id=1,
        operation_date=date(2025, 1, 15),
        value_date=date(2025, 1, 15),
        transaction_type="buy",
        ticker="BTC",
        isin="XC1A2B3C4D5E",
        description="Bitcoin purchase",
        quantity=Decimal("0.025"),
        price_per_share=Decimal("42000.00"),
        amount_eur=Decimal("966.00"),
        amount_currency=Decimal("1050.00"),
        currency="USD",
        fees=Decimal("2.50"),
        order_reference="COINBASE-12345",
        transaction_hash="abc123def456",
        imported_at=datetime(2025, 1, 15, 10, 30),
        created_at=datetime(2025, 1, 15, 10, 30),
        updated_at=datetime(2025, 1, 15, 10, 30)
    )
    print(f"✅ TransactionResponse (crypto): {crypto_tx_response.ticker}, ISIN: {crypto_tx_response.isin}")

    # Test with traditional asset for comparison
    stock_tx = ManualTransactionCreate(
        operation_date=date(2025, 1, 15),
        ticker="AAPL",
        type="buy",
        quantity=Decimal("10"),
        amount=Decimal("175.50"),
        currency="USD",
        fees=Decimal("1.00")
    )
    print(f"✅ ManualTransactionCreate (stock): {stock_tx.ticker}, ISIN: {stock_tx.isin}")


def test_crypto_position_schemas():
    """Test crypto position schemas."""
    print("\nTesting crypto position schemas...")

    # Test PositionResponse with crypto
    crypto_position = PositionResponse(
        id=1,
        ticker="BTC",
        isin="XC1A2B3C4D5E",
        description="Bitcoin",
        asset_type=AssetType.CRYPTO,
        quantity=Decimal("0.025"),
        average_cost=Decimal("38640.00"),
        cost_basis=Decimal("966.00"),
        current_price=Decimal("43000.00"),
        current_value=Decimal("1075.00"),
        unrealized_gain=Decimal("109.00"),
        return_percentage=11.28,
        irr=15.5,
        today_change=Decimal("500.00"),
        today_change_percent=1.18,
        last_calculated_at=datetime(2025, 1, 15, 16, 30),
        exchange="COINBASE",
        wallet_address="1A2b3C4d5E6f7G8h9I0jK1lM2n3O4p5Q6r"
    )
    print(f"✅ PositionResponse (crypto): {crypto_position.ticker}, Exchange: {crypto_position.exchange}")

    # Test PositionCreate with crypto
    crypto_position_create = PositionCreate(
        ticker="ETH",
        isin="XC7H8I9J0K1L",
        description="Ethereum",
        asset_type=AssetType.CRYPTO,
        quantity=Decimal("1.5"),
        average_cost=Decimal("2272.73"),
        cost_basis=Decimal("3409.09"),
        exchange="BINANCE",
        wallet_address="0x742d35Cc6634C0532925a3b8D4C9db96C4b4Db45"
    )
    print(f"✅ PositionCreate (crypto): {crypto_position_create.ticker}, Exchange: {crypto_position_create.exchange}")


def test_crypto_price_schemas():
    """Test crypto price schemas."""
    print("\nTesting crypto price schemas...")

    # Test PriceResponse with crypto
    crypto_price = PriceResponse(
        ticker="BTC",
        date=date(2025, 1, 15),
        open=Decimal("42000.00"),
        high=Decimal("43500.00"),
        low=Decimal("41500.00"),
        close=Decimal("43000.00"),
        volume=1234567890,
        source="COINGECKO",
        created_at=datetime(2025, 1, 15, 18, 0),
        market_cap=Decimal("840000000000"),
        circulating_supply=Decimal("19500000")
    )
    print(f"✅ PriceResponse (crypto): {crypto_price.ticker}, Market Cap: ${crypto_price.market_cap:,.0f}")

    # Test RealtimePriceResponse with crypto
    crypto_realtime = RealtimePriceResponse(
        ticker="BTC",
        isin="XC1A2B3C4D5E",
        current_price=Decimal("43000.00"),
        previous_close=Decimal("42000.00"),
        change_amount=Decimal("1000.00"),
        change_percent=Decimal("2.38"),
        timestamp=datetime(2025, 1, 15, 14, 30),
        source="COINGECKO",
        asset_type=AssetType.CRYPTO,
        volume_24h=Decimal("25000000000"),
        market_cap=Decimal("840000000000"),
        circulating_supply=Decimal("19500000")
    )
    print(f"✅ RealtimePriceResponse (crypto): {crypto_realtime.ticker}, 24h Volume: ${crypto_realtime.volume_24h:,.0f}")


def test_crypto_portfolio_schemas():
    """Test crypto portfolio schemas."""
    print("\nTesting crypto portfolio schemas...")

    # Test PortfolioOverview with crypto breakdown
    portfolio_overview = PortfolioOverview(
        current_value=Decimal("15000.00"),
        total_cost_basis=Decimal("12000.00"),
        total_profit=Decimal("3000.00"),
        average_annual_return=15.5,
        today_gain_loss=Decimal("250.00"),
        today_gain_loss_pct=1.67,
        crypto_value=Decimal("7500.00"),
        crypto_cost_basis=Decimal("5500.00"),
        crypto_profit=Decimal("2000.00"),
        stock_value=Decimal("7500.00"),
        stock_cost_basis=Decimal("6500.00"),
        stock_profit=Decimal("1000.00"),
        crypto_percentage=50.0,
        stock_percentage=50.0,
        last_updated=date(2025, 1, 15)
    )
    print(f"✅ PortfolioOverview: Total €{portfolio_overview.current_value:,.2f}, Crypto: {portfolio_overview.crypto_percentage}%")

    # Test AssetAllocation with crypto
    crypto_allocation = AssetAllocation(
        asset_type=AssetType.CRYPTO,
        value=Decimal("7500.00"),
        cost_basis=Decimal("5500.00"),
        profit=Decimal("2000.00"),
        percentage=50.0,
        count=5
    )
    print(f"✅ AssetAllocation (crypto): {crypto_allocation.count} positions, {crypto_allocation.percentage}% of portfolio")


def test_crypto_validators():
    """Test crypto validation functions."""
    print("\nTesting crypto validators...")

    # Test crypto ticker validation
    validated_ticker = validate_crypto_ticker("btc")
    print(f"✅ validate_crypto_ticker: 'btc' -> '{validated_ticker}'")

    # Test crypto identifier generation
    crypto_isin = generate_crypto_identifier("BTC")
    print(f"✅ generate_crypto_identifier: BTC -> {crypto_isin}")

    # Test crypto ISIN validation
    validated_isin = validate_crypto_isin(crypto_isin)
    print(f"✅ validate_crypto_isin: {validated_isin} is valid")

    # Test comprehensive transaction validation
    validation_result = validate_crypto_transaction_data(
        ticker="ETH",
        quantity=Decimal("1.5"),
        currency="USD",
        exchange="BINANCE",
        wallet_address="0x742d35Cc6634C0532925a3b8D4C9db96C4b4Db45"
    )
    print(f"✅ validate_crypto_transaction_data: Valid={validation_result.is_valid}, Ticker={validation_result.ticker}")


def test_error_cases():
    """Test error cases and validation failures."""
    print("\nTesting error cases...")

    try:
        # Test invalid crypto ticker
        ManualTransactionCreate(
            operation_date=date(2025, 1, 15),
            ticker="INVALID_TICKER_1234567890",
            type="buy",
            quantity=Decimal("1"),
            amount=Decimal("100")
        )
        print("❌ Should have failed with invalid ticker")
    except CryptoValidationError as e:
        print(f"✅ Correctly caught invalid ticker error: {e}")

    try:
        # Test invalid crypto ISIN
        validate_crypto_isin("INVALID_ISIN")
        print("❌ Should have failed with invalid ISIN")
    except CryptoValidationError as e:
        print(f"✅ Correctly caught invalid ISIN error: {e}")

    try:
        # Test excessive crypto precision
        ManualTransactionCreate(
            operation_date=date(2025, 1, 15),
            ticker="BTC",
            type="buy",
            quantity=Decimal("0.000000000000000001"),  # 18+ decimal places
            amount=Decimal("42000")
        )
        print("❌ Should have failed with excessive precision")
    except CryptoValidationError as e:
        print(f"✅ Correctly caught excessive precision error: {e}")


def main():
    """Run all tests."""
    print("🧪 Testing Enhanced Crypto Schemas")
    print("=" * 50)

    try:
        test_crypto_transaction_schemas()
        test_crypto_position_schemas()
        test_crypto_price_schemas()
        test_crypto_portfolio_schemas()
        test_crypto_validators()
        test_error_cases()

        print("\n" + "=" * 50)
        print("🎉 All tests passed! Crypto schemas are working correctly.")

    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()