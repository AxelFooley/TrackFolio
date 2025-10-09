#!/usr/bin/env python3
"""
Test script for CoinCap service functionality.

This script tests the CoinCap service implementation to ensure
it works correctly with the existing codebase patterns.
"""
import sys
import os
from datetime import date, timedelta

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from services.coincap import coincap_service
from config import settings

def test_connection():
    """Test basic connection to CoinCap API."""
    print("Testing CoinCap API connection...")

    try:
        result = coincap_service.test_connection()
        if result:
            print("✓ Connection successful")
            return True
        else:
            print("✗ Connection failed")
            return False
    except Exception as e:
        print(f"✗ Connection error: {e}")
        return False

def test_symbol_mapping():
    """Test symbol mapping functionality."""
    print("\nTesting symbol mapping...")

    test_symbols = ['BTC', 'ETH', 'ADA', 'UNKNOWN_SYMBOL']

    for symbol in test_symbols:
        try:
            result = coincap_service.map_symbol_to_coincec_id(symbol)
            if result:
                print(f"✓ {symbol} -> {result}")
            else:
                print(f"✗ {symbol} -> Not found")
        except Exception as e:
            print(f"✗ {symbol} -> Error: {e}")

def test_current_price():
    """Test current price fetching."""
    print("\nTesting current price fetching...")

    test_cases = [
        ('BTC', 'usd'),
        ('ETH', 'eur'),
        ('ADA', 'usd')
    ]

    for symbol, currency in test_cases:
        try:
            result = coincap_service.get_current_price(symbol, currency)
            if result:
                print(f"✓ {symbol}/{currency}: {result['price']} {result['currency']}")
            else:
                print(f"✗ {symbol}/{currency}: No data")
        except Exception as e:
            print(f"✗ {symbol}/{currency}: Error: {e}")

def test_historical_prices():
    """Test historical price fetching."""
    print("\nTesting historical price fetching...")

    end_date = date.today()
    start_date = end_date - timedelta(days=7)

    test_symbols = ['BTC', 'ETH']

    for symbol in test_symbols:
        try:
            result = coincap_service.get_historical_prices(symbol, start_date, end_date, 'usd')
            if result:
                print(f"✓ {symbol}: {len(result)} price points")
                if result:
                    latest = result[-1]
                    print(f"   Latest: {latest['date']} - ${latest['price']}")
            else:
                print(f"✗ {symbol}: No data")
        except Exception as e:
            print(f"✗ {symbol}: Error: {e}")

def test_supported_symbols():
    """Test getting supported symbols."""
    print("\nTesting supported symbols...")

    try:
        result = coincap_service.get_supported_symbols()
        if result:
            print(f"✓ Retrieved {len(result)} supported assets")
            # Show first 5
            for asset in result[:5]:
                print(f"   {asset['symbol']}: {asset['name']} (${asset['price_usd']})")
        else:
            print("✗ No supported symbols retrieved")
    except Exception as e:
        print(f"✗ Error: {e}")

def test_caching():
    """Test caching functionality."""
    print("\nTesting caching...")

    symbol = 'BTC'
    currency = 'usd'

    # First call (should hit API)
    print("First call (API)...")
    try:
        result1 = coincap_service.get_current_price(symbol, currency)
        if result1:
            print(f"✓ Price: {result1['price']}")
        else:
            print("✗ No data")
            return
    except Exception as e:
        print(f"✗ Error: {e}")
        return

    # Second call (should hit cache)
    print("Second call (cache)...")
    try:
        result2 = coincap_service.get_current_price(symbol, currency)
        if result2:
            print(f"✓ Price: {result2['price']}")
            if result1['price'] == result2['price']:
                print("✓ Cache working correctly")
            else:
                print("✗ Cache mismatch")
        else:
            print("✗ No data from cache")
    except Exception as e:
        print(f"✗ Error: {e}")

def main():
    """Run all tests."""
    print("CoinCap Service Test Suite")
    print("=" * 50)

    # Test connection first
    if not test_connection():
        print("\nCannot proceed with tests - API connection failed")
        return

    # Run other tests
    test_symbol_mapping()
    test_current_price()
    test_historical_prices()
    test_supported_symbols()
    test_caching()

    print("\n" + "=" * 50)
    print("Test suite completed")

if __name__ == "__main__":
    main()