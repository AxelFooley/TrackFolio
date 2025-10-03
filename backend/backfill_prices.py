"""
Backfill yesterday's prices to enable movers and today_change_pct.
"""
import sys
import os
from datetime import date, timedelta

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SyncSessionLocal
from app.models import PriceHistory
import yfinance as yf


def backfill_yesterday():
    """Backfill yesterday's prices."""
    db = SyncSessionLocal()
    
    # Ticker mappings
    tickers = {
        'CSSPX': 'CSSPX.L',
        'X.PTX': 'PLTR',
        'TSLA': 'TSLA',
        '.QBTS': 'QBTS',
        'A500': 'A500.PA',
        'X.WBIT': 'BTCW.AS'  # WisdomTree Physical Bitcoin
    }
    
    yesterday = date.today() - timedelta(days=1)
    
    print(f"Backfilling prices for {yesterday}...")
    print("=" * 60)
    
    for directa_ticker, yahoo_ticker in tickers.items():
        try:
            print(f"\nFetching {directa_ticker} ({yahoo_ticker})...", end=" ")
            
            # Fetch data
            data = yf.Ticker(yahoo_ticker).history(
                start=yesterday, 
                end=yesterday + timedelta(days=1)
            )
            
            if data.empty:
                print("✗ No data")
                continue
            
            latest = data.iloc[-1]
            
            # Create or update price record
            price = PriceHistory(
                ticker=directa_ticker,
                date=yesterday,
                open=float(latest['Open']),
                high=float(latest['High']),
                low=float(latest['Low']),
                close=float(latest['Close']),
                volume=int(latest['Volume']),
                source='yahoo'
            )
            
            # Use merge to handle duplicates
            db.merge(price)
            db.commit()
            
            print(f"✓ ${latest['Close']:.2f}")
            
        except Exception as e:
            print(f"✗ Error: {e}")
            db.rollback()
    
    db.close()
    
    print("\n" + "=" * 60)
    print("Backfill complete!")


if __name__ == "__main__":
    backfill_yesterday()
