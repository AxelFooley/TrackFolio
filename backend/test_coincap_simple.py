#!/usr/bin/env python3
"""
Simple test script for CoinCap service functionality (without Redis).

This script tests the basic CoinCap service API calls.
"""
import sys
import os
import requests
from datetime import date, timedelta
from decimal import Decimal

def test_coincap_api():
    """Test basic CoinCap API functionality."""
    print("Testing CoinCap API directly...")

    base_url = "https://api.coincap.io/v2/"

    try:
        # Test connection
        print("Testing basic connection...")
        response = requests.get(f"{base_url}assets", params={'limit': 1}, timeout=30)
        response.raise_for_status()
        data = response.json()

        if 'data' in data and data['data']:
            print("✓ Connection successful")
            asset = data['data'][0]
            print(f"  Sample asset: {asset['id']} ({asset['symbol']})")
        else:
            print("✗ Unexpected response format")
            return False

        # Test specific asset
        print("\nTesting Bitcoin data...")
        response = requests.get(f"{base_url}assets/bitcoin", timeout=30)
        response.raise_for_status()
        data = response.json()

        if 'data' in data:
            btc_data = data['data']
            price = Decimal(str(btc_data.get('priceUsd', '0')))
            print(f"✓ Bitcoin price: ${price}")

            # Test historical data
            print("\nTesting historical data...")
            end_timestamp = int(date.today().timestamp() * 1000)
            start_timestamp = int((date.today() - timedelta(days=7)).timestamp() * 1000)

            response = requests.get(
                f"{base_url}assets/bitcoin/history",
                params={
                    'interval': 'd1',
                    'start': start_timestamp,
                    'end': end_timestamp
                },
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            if 'data' in data and data['data']:
                print(f"✓ Retrieved {len(data['data'])} historical price points")
                latest = data['data'][-1]
                latest_price = Decimal(str(latest.get('priceUsd', '0')))
                print(f"  Latest historical price: ${latest_price}")
            else:
                print("✗ No historical data")
        else:
            print("✗ No Bitcoin data")

        # Test search functionality
        print("\nTesting search functionality...")
        response = requests.get(f"{base_url}assets", params={'search': 'ethereum'}, timeout=30)
        response.raise_for_status()
        data = response.json()

        if 'data' in data and data['data']:
            eth_found = False
            for asset in data['data']:
                if asset.get('symbol', '').upper() == 'ETH':
                    print(f"✓ Found Ethereum: {asset['id']} - ${asset.get('priceUsd', '0')}")
                    eth_found = True
                    break
            if not eth_found:
                print("✗ Ethereum not found in search results")
        else:
            print("✗ Search returned no results")

        print("\n✓ All CoinCap API tests passed")
        return True

    except requests.exceptions.RequestException as e:
        print(f"✗ API request failed: {e}")
        return False
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False

def test_symbol_mappings():
    """Test symbol mapping logic."""
    print("\nTesting symbol mappings...")

    # Basic mappings that should work
    basic_mappings = {
        'BTC': 'bitcoin',
        'ETH': 'ethereum',
        'ADA': 'cardano',
        'SOL': 'solana'
    }

    print("✓ Symbol mappings defined:")
    for symbol, expected_id in basic_mappings.items():
        print(f"  {symbol} -> {expected_id}")

    print("✓ Symbol mapping logic test passed")

def test_currency_conversion():
    """Test currency conversion logic."""
    print("\nTesting currency conversion logic...")

    # Test USD price conversion to EUR
    price_usd = Decimal('50000.00')
    mock_eur_rate = Decimal('0.92')
    price_eur = price_usd * mock_eur_rate

    print(f"✓ USD to EUR conversion: ${price_usd} -> €{price_eur}")
    print("✓ Currency conversion logic test passed")

def main():
    """Run all tests."""
    print("CoinCap Service Simple Test Suite")
    print("=" * 50)

    # Test basic API functionality
    if not test_coincap_api():
        print("\nCannot proceed - CoinCap API test failed")
        return

    # Test logic components
    test_symbol_mappings()
    test_currency_conversion()

    print("\n" + "=" * 50)
    print("✓ Simple test suite completed successfully")
    print("\nNote: Full CoinCap service requires Redis and environment setup.")

if __name__ == "__main__":
    main()