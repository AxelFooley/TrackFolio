#!/usr/bin/env python3
"""
Simple test script to verify enhanced crypto price fetching functionality.
"""
import asyncio
import sys
import os

# Add the backend directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.services.price_fetcher import PriceFetcher
from app.config import settings

async def test_crypto_price_fetching():
    """Test basic crypto price fetching functionality."""
    print("Testing Enhanced Crypto Price Fetching")
    print("=" * 50)

    # Create price fetcher instance
    fetcher = PriceFetcher()

    # Test 1: Check crypto ticker detection
    print("\n1. Testing crypto ticker detection:")
    test_tickers = ["BTC", "ETH", "AAPL", "MSFT", "SOL", "UNI", "DOGE"]
    for ticker in test_tickers:
        is_crypto = fetcher.is_crypto_ticker(ticker)
        print(f"   {ticker}: {'Crypto' if is_crypto else 'Stock'}")

    # Test 2: Test crypto price fetching
    print("\n2. Testing crypto price fetching (EUR):")
    crypto_tickers = ["BTC", "ETH"]

    for ticker in crypto_tickers:
        try:
            price_data = await fetcher.fetch_crypto_price(ticker, "EUR")
            if price_data:
                print(f"   {ticker}: {price_data['close']} EUR "
                      f"(24h change: {price_data.get('change_24h', 'N/A')}%) "
                      f"Volume: {price_data['volume']:,}")
            else:
                print(f"   {ticker}: Failed to fetch price")
        except Exception as e:
            print(f"   {ticker}: Error - {str(e)}")

    # Test 3: Test crypto price fetching (USD)
    print("\n3. Testing crypto price fetching (USD):")
    for ticker in crypto_tickers:
        try:
            price_data = await fetcher.fetch_crypto_price(ticker, "USD")
            if price_data:
                print(f"   {ticker}: {price_data['close']} USD "
                      f"(24h change: {price_data.get('change_24h', 'N/A')}%)")
            else:
                print(f"   {ticker}: Failed to fetch price")
        except Exception as e:
            print(f"   {ticker}: Error - {str(e)}")

    # Test 4: Test crypto conversion rate
    print("\n4. Testing crypto conversion rates:")
    try:
        btc_eth_rate = await fetcher.fetch_crypto_conversion_rate("BTC", "ETH", "USD")
        if btc_eth_rate:
            print(f"   BTC/ETH: 1 BTC = {btc_eth_rate:.6f} ETH")
        else:
            print("   BTC/ETH: Failed to fetch conversion rate")
    except Exception as e:
        print(f"   BTC/ETH: Error - {str(e)}")

    # Test 5: Test historical crypto prices (limited range)
    print("\n5. Testing historical crypto prices (last 7 days):")
    from datetime import date, timedelta
    end_date = date.today()
    start_date = end_date - timedelta(days=7)

    try:
        hist_prices = await fetcher.fetch_historical_prices(
            "BTC", start_date, end_date, is_crypto=True
        )
        if hist_prices:
            print(f"   BTC: Got {len(hist_prices)} price points")
            # Show first and last prices
            if len(hist_prices) >= 2:
                print(f"      Start: {hist_prices[0]['date']} - {hist_prices[0]['close']} EUR")
                print(f"      End: {hist_prices[-1]['date']} - {hist_prices[-1]['close']} EUR")
        else:
            print("   BTC: No historical data fetched")
    except Exception as e:
        print(f"   BTC: Error - {str(e)}")

    # Test 6: Test real-time price fetching
    print("\n6. Testing real-time price fetching:")
    test_assets = [("BTC", None), ("ETH", None), ("AAPL", None)]

    for ticker, isin in test_assets:
        try:
            realtime_data = fetcher.fetch_realtime_price(ticker, isin)
            if realtime_data:
                source = realtime_data.get('source', 'unknown')
                current_price = realtime_data.get('current_price')
                change_pct = realtime_data.get('change_percent', 0)

                print(f"   {ticker}: {current_price} ({source}) "
                      f"Change: {change_pct:+.2f}%")

                # Show crypto-specific data if available
                if source == 'coingecko':
                    volume_24h = realtime_data.get('volume_24h')
                    market_cap = realtime_data.get('market_cap')
                    if volume_24h:
                        print(f"      24h Volume: {volume_24h:,} EUR")
                    if market_cap:
                        print(f"      Market Cap: {market_cap:,} EUR")
            else:
                print(f"   {ticker}: Failed to fetch real-time price")
        except Exception as e:
            print(f"   {ticker}: Error - {str(e)}")

    print("\n" + "=" * 50)
    print("Test completed!")

if __name__ == "__main__":
    # Check if CoinGecko API key is configured
    if settings.coingecko_api_key:
        print(f"Using CoinGecko API key: {'*' * len(settings.coingecko_api_key)}")
    else:
        print("Warning: No CoinGecko API key configured - using free tier")

    asyncio.run(test_crypto_price_fetching())