"""Benchmark API endpoints."""
from typing import Optional, List
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import logging
import yfinance as yf
import asyncio
import httpx

from app.database import get_db
from app.models import Benchmark, Transaction
from app.schemas.benchmark import BenchmarkCreate, BenchmarkResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/benchmark", tags=["benchmark"])


@router.get("/", response_model=Optional[BenchmarkResponse])
async def get_benchmark(db: AsyncSession = Depends(get_db)):
    """Get current active benchmark. Returns null if not configured."""
    result = await db.execute(select(Benchmark).limit(1))
    benchmark = result.scalar_one_or_none()

    return benchmark  # Returns None if not found, which is valid


@router.post("/", response_model=BenchmarkResponse)
async def set_benchmark(
    benchmark_data: BenchmarkCreate,
    db: AsyncSession = Depends(get_db)
):
    """Set or update the active benchmark (single-row table)."""
    # Delete existing benchmark
    result = await db.execute(select(Benchmark))
    existing = result.scalar_one_or_none()

    if existing:
        await db.delete(existing)

    # Create new benchmark
    benchmark = Benchmark(
        ticker=benchmark_data.ticker,
        description=benchmark_data.description or f"Benchmark: {benchmark_data.ticker}"
    )
    db.add(benchmark)
    await db.commit()
    await db.refresh(benchmark)

    # Trigger historical price fetch for benchmark
    # Find earliest transaction date or use 1 year ago as fallback
    earliest_txn_result = await db.execute(
        select(func.min(Transaction.operation_date))
    )
    earliest_date = earliest_txn_result.scalar_one_or_none()

    if earliest_date:
        start_date = earliest_date
    else:
        # Default to 1 year ago if no transactions
        start_date = date.today() - timedelta(days=365)

    end_date = date.today()

    # Trigger async task to fetch benchmark prices
    logger.info(f"Triggering price fetch for benchmark {benchmark.ticker} from {start_date} to {end_date}")

    # Use Celery task to fetch prices asynchronously
    from app.tasks.price_updates import fetch_prices_for_ticker
    fetch_prices_for_ticker.delay(
        ticker=benchmark.ticker,
        isin=None,  # Benchmarks don't have ISINs
        start_date=str(start_date),
        end_date=str(end_date)
    )

    return benchmark


@router.get("/search", response_model=List[dict])
async def search_tickers(
    q: str = Query(..., min_length=1, description="Search query for ticker symbol or company name")
):
    """
    Search for ticker symbols using Yahoo Finance with enhanced company name matching.

    Returns a list of matching tickers with their names and symbols.
    This helps users select the correct ticker for benchmarks.
    """
    try:
        search_results = []
        query_lower = q.lower().strip()

        # Common benchmark indices and ETFs with enhanced matching data
        common_benchmarks = [
            {"ticker": "^GSPC", "name": "S&P 500", "type": "INDEX", "keywords": ["s&p", "sp500", "standard", "poors"]},
            {"ticker": "^DJI", "name": "Dow Jones Industrial Average", "type": "INDEX", "keywords": ["dow", "jones", "industrial"]},
            {"ticker": "^IXIC", "name": "NASDAQ Composite", "type": "INDEX", "keywords": ["nasdaq", "composite", "tech"]},
            {"ticker": "^FTSE", "name": "FTSE 100", "type": "INDEX", "keywords": ["ftse", "uk", "british"]},
            {"ticker": "^GDAXI", "name": "DAX", "type": "INDEX", "keywords": ["dax", "germany", "german"]},
            {"ticker": "^FCHI", "name": "CAC 40", "type": "INDEX", "keywords": ["cac", "france", "french"]},
            {"ticker": "SPY", "name": "SPDR S&P 500 ETF Trust", "type": "ETF", "keywords": ["spdr", "sp500", "s&p"]},
            {"ticker": "VOO", "name": "Vanguard S&P 500 ETF", "type": "ETF", "keywords": ["vanguard", "sp500", "s&p"]},
            {"ticker": "QQQ", "name": "Invesco QQQ Trust", "type": "ETF", "keywords": ["qqq", "nasdaq", "invesco"]},
            {"ticker": "VTI", "name": "Vanguard Total Stock Market ETF", "type": "ETF", "keywords": ["vanguard", "total", "stock", "market"]},
            {"ticker": "VWCE.DE", "name": "Vanguard FTSE All-World UCITS ETF", "type": "ETF", "keywords": ["vanguard", "ftse", "all-world", "world"]},
            {"ticker": "CSPX.L", "name": "iShares Core S&P 500 UCITS ETF", "type": "ETF", "keywords": ["ishares", "sp500", "s&p", "core"]},
            {"ticker": "CSSPX.MI", "name": "iShares Core S&P 500 UCITS ETF (Milan)", "type": "ETF", "keywords": ["ishares", "sp500", "s&p", "milan"]},
            {"ticker": "EUNL.DE", "name": "iShares Core MSCI World UCITS ETF", "type": "ETF", "keywords": ["ishares", "msci", "world", "core"]},
            {"ticker": "VUSA.L", "name": "Vanguard S&P 500 UCITS ETF", "type": "ETF", "keywords": ["vanguard", "sp500", "s&p", "uk"]},
            {"ticker": "AAPL", "name": "Apple Inc.", "type": "EQUITY", "keywords": ["apple", "iphone", "mac"]},
            {"ticker": "MSFT", "name": "Microsoft Corporation", "type": "EQUITY", "keywords": ["microsoft", "windows", "office"]},
            {"ticker": "GOOGL", "name": "Alphabet Inc.", "type": "EQUITY", "keywords": ["alphabet", "google", "search"]},
            {"ticker": "AMZN", "name": "Amazon.com Inc.", "type": "EQUITY", "keywords": ["amazon", "aws", "ecommerce"]},
            {"ticker": "TSLA", "name": "Tesla Inc.", "type": "EQUITY", "keywords": ["tesla", "electric", "vehicle"]},
        ]

        # Enhanced matching function for common benchmarks
        def match_benchmark(item, query):
            """Check if benchmark item matches the query with multiple strategies."""
            query_words = query.split()

            # Exact ticker match (highest priority)
            if query.upper() == item["ticker"].upper():
                return 100

            # Exact name match
            if query_lower == item["name"].lower():
                return 90

            # Ticker starts with query
            if item["ticker"].lower().startswith(query_lower):
                return 80

            # Name contains query
            if query_lower in item["name"].lower():
                return 70

            # Check keywords
            keyword_matches = sum(1 for keyword in item.get("keywords", [])
                                if keyword in query_lower or any(keyword in word for word in query_words))
            if keyword_matches > 0:
                return 50 + (keyword_matches * 5)

            # Partial word matching
            name_words = item["name"].lower().split()
            for word in name_words:
                if word.startswith(query_lower) or query_lower.startswith(word):
                    return 30

            return 0

        # Score and filter common benchmarks
        scored_benchmarks = []
        for item in common_benchmarks:
            score = match_benchmark(item, query_lower)
            if score > 0:
                scored_benchmarks.append((item, score))

        # Sort by score (descending) and add to results
        scored_benchmarks.sort(key=lambda x: x[1], reverse=True)
        for item, score in scored_benchmarks[:10]:
            result_item = {
                "ticker": item["ticker"],
                "name": item["name"],
                "type": item["type"]
            }
            if result_item not in search_results:
                search_results.append(result_item)

        # Enhanced yfinance search strategies
        await _enhanced_yfinance_search(query_lower, search_results)

        # Ensure we have unique results and limit to 10
        unique_results = []
        seen_tickers = set()

        for result in search_results:
            if result["ticker"] not in seen_tickers:
                unique_results.append(result)
                seen_tickers.add(result["ticker"])

        return unique_results[:10]

    except Exception as e:
        logger.error(f"Error searching for tickers: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error searching for tickers: {str(e)}")


async def _enhanced_yfinance_search(query_lower: str, search_results: List[dict]):
    """
    Enhanced yfinance search using Yahoo Finance's built-in search capabilities.

    This function uses Yahoo Finance's own search to find tickers by company name
    or symbol, providing comprehensive and up-to-date results.
    """

    if len(search_results) >= 8:  # Stop if we already have good results
        return

    try:
        # Use yfinance's search functionality with async httpx
        search_url = f"https://query2.finance.yahoo.com/v1/finance/search"
        params = {
            'q': query_lower,
            'quotesCount': 10,
            'newsCount': 0,
            'listsCount': 0,
            'enableFuzzyQuery': True,
            'quotesQueryId': 'tss_match_phrase_query'
        }

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(search_url, params=params, headers=headers)

        if response.status_code == 200:
            data = await response.json()

            if 'quotes' in data and data['quotes']:
                for quote in data['quotes'][:10]:
                    if len(search_results) >= 10:
                        break

                    ticker = quote.get('symbol', '')
                    name = quote.get('longname') or quote.get('shortname') or ticker
                    quote_type = quote.get('quoteType', 'EQUITY')
                    exchange = quote.get('exchangeDisp', '')

                    if ticker and name:
                        result = {
                            "ticker": ticker,
                            "name": name,
                            "type": quote_type,
                            "exchange": exchange
                        }

                        # Avoid duplicates
                        if result not in search_results:
                            search_results.append(result)

    except Exception as e:
        logger.debug(f"Yahoo Finance search failed for '{query_lower}': {str(e)}")

        # Fallback to direct ticker lookup
        fallback_results = await _try_direct_ticker_lookup(query_lower)
        for result in fallback_results:
            if result not in search_results and len(search_results) < 10:
                search_results.append(result)


async def _try_direct_ticker_lookup(query: str) -> List[dict]:
    """Fallback: Try direct ticker lookup using yfinance."""
    results = []

    try:
        # Try the query as a ticker symbol using asyncio.to_thread to avoid blocking
        ticker_symbol = query.upper()

        # Run yfinance operations in a separate thread to avoid blocking the event loop
        ticker_info = await asyncio.to_thread(lambda: yf.Ticker(ticker_symbol).info)

        if ticker_info and ticker_info.get('symbol') and ticker_info.get('longName'):
            results.append({
                "ticker": ticker_info['symbol'],
                "name": ticker_info.get('longName') or ticker_info.get('shortName') or ticker_info['symbol'],
                "type": ticker_info.get('quoteType', 'EQUITY'),
                "exchange": ticker_info.get('exchange', '')
            })
    except Exception as e:
        logger.debug(f"Direct ticker lookup failed for {query}: {str(e)}")

    return results
