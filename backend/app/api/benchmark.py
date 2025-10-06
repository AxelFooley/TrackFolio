"""Benchmark API endpoints."""
from typing import Optional, List
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import logging
import yfinance as yf

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
    Enhanced yfinance search with multiple strategies for finding tickers.

    This function implements several search strategies:
    1. Direct ticker lookup
    2. Company name search
    3. Partial matching
    4. Common variations and expansions
    """

    search_strategies = [
        # Strategy 1: Exact ticker match (try uppercase)
        lambda: _try_ticker_lookup(query_lower.upper()),

        # Strategy 2: Common company name variations
        lambda: _try_company_name_variations(query_lower),

        # Strategy 3: Partial ticker matches for common patterns
        lambda: _try_partial_matches(query_lower),

        # Strategy 4: Try removing common suffixes/prefixes
        lambda: _try_cleaned_query(query_lower),
    ]

    for strategy_func in search_strategies:
        if len(search_results) >= 8:  # Stop if we already have good results
            break

        try:
            new_results = strategy_func()
            for result in new_results:
                if result not in search_results and len(search_results) < 10:
                    search_results.append(result)
        except Exception as e:
            logger.debug(f"Search strategy failed: {str(e)}")
            continue


def _try_ticker_lookup(ticker_symbol: str) -> List[dict]:
    """Try direct ticker lookup using yfinance."""
    results = []

    try:
        ticker_obj = yf.Ticker(ticker_symbol)
        info = ticker_obj.info

        if info and info.get('symbol') and info.get('longName'):
            results.append({
                "ticker": info['symbol'],
                "name": info.get('longName') or info.get('shortName') or info['symbol'],
                "type": info.get('quoteType', 'EQUITY')
            })
    except Exception as e:
        logger.debug(f"Direct ticker lookup failed for {ticker_symbol}: {str(e)}")

    return results


def _try_company_name_variations(query: str) -> List[dict]:
    """Try various company name variations and common mappings."""
    results = []

    # Common company name mappings
    company_mappings = {
        "apple": "AAPL",
        "microsoft": "MSFT",
        "google": "GOOGL",
        "alphabet": "GOOGL",
        "amazon": "AMZN",
        "tesla": "TSLA",
        "facebook": "META",
        "meta": "META",
        "netflix": "NFLX",
        "nvidia": "NVDA",
        "berkshire": "BRK-B",
        "warren": "BRK-B",
        "jpmorgan": "JPM",
        "jp morgan": "JPM",
        "bank of america": "BAC",
        "wells fargo": "WFC",
        "goldman": "GS",
        "morgan stanley": "MS",
        "johnson": "JNJ",
        "jnj": "JNJ",
        "procter": "PG",
        "pg": "PG",
        "verizon": "VZ",
        "at&t": "T",
        "coca": "KO",
        "pepsi": "PEP",
        "mcdonald": "MCD",
        "starbucks": "SBUX",
        "nike": "NKE",
        "disney": "DIS",
        "boeing": "BA",
        "caterpillar": "CAT",
        "chevron": "CVX",
        "exxon": "XOM",
        "pfizer": "PFE",
        "merck": "MRK",
        "home depot": "HD",
        "lowe": "LOW",
        "target": "TGT",
        "walmart": "WMT",
        "costco": "COST",
    }

    # Check for exact matches in mappings
    for company_name, ticker in company_mappings.items():
        if query in company_name or company_name in query:
            ticker_result = _try_ticker_lookup(ticker)
            results.extend(ticker_result)

    # Try common expansions
    expansions = {
        "vanguard": ["VOO", "VTI", "VWCE.DE", "VUSA.L"],
        "ishares": ["EUNL.DE", "CSPX.L", "CSSPX.MI"],
        "spdr": ["SPY", "GLD"],
        "invesco": ["QQQ"],
        "s&p": ["SPY", "VOO", "^GSPC", "CSPX.L"],
        "sp500": ["SPY", "VOO", "^GSPC", "CSPX.L"],
        "nasdaq": ["QQQ", "^IXIC"],
        "dow": ["^DJI", "DIA"],
        "ftse": ["^FTSE", "VUKE.L"],
        "dax": ["^GDAXI", "EWG"],
        "cac": ["^FCHI", "EWQ"],
    }

    for expansion_term, tickers in expansions.items():
        if expansion_term in query or query in expansion_term:
            for ticker in tickers[:3]:  # Limit to avoid too many results
                ticker_result = _try_ticker_lookup(ticker)
                results.extend(ticker_result)

    return results


def _try_partial_matches(query: str) -> List[dict]:
    """Try partial matches for common ticker patterns."""
    results = []

    # Common patterns
    if len(query) >= 2:
        # Try common single-letter prefixes
        common_prefixes = ["A", "B", "C", "M", "S", "T"]
        for prefix in common_prefixes:
            if query.startswith(prefix.lower()):
                test_tickers = [f"{prefix}{query[1:].upper()}", f"{prefix}{query[1:].upper()}A"]
                for ticker in test_tickers:
                    ticker_result = _try_ticker_lookup(ticker)
                    if ticker_result:
                        results.extend(ticker_result)
                        break  # Only take first successful match per prefix

    return results


def _try_cleaned_query(query: str) -> List[dict]:
    """Try cleaned versions of the query."""
    results = []

    # Remove common suffixes and try again
    cleaned_query = query
    suffixes_to_remove = ["corporation", "corp", "inc", "llc", "ltd", "limited", "company", "co", "group", "holdings", "plc"]

    for suffix in suffixes_to_remove:
        if cleaned_query.endswith(suffix):
            cleaned_query = cleaned_query[:-len(suffix)].strip()
            break

    if cleaned_query != query and len(cleaned_query) >= 2:
        # Try the cleaned query with existing strategies
        results.extend(_try_company_name_variations(cleaned_query))
        results.extend(_try_ticker_lookup(cleaned_query.upper()))

    return results
