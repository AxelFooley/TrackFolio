"""
CoinCap API service wrapper for cryptocurrency price data.

This service provides access to CoinCap API for cryptocurrency prices
with proper caching, error handling, and currency conversion.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
import logging
import requests
import json
import time
from urllib.parse import urljoin
import redis
import pickle

from app.config import settings

logger = logging.getLogger(__name__)


class CoinCapService:
    """
    Service for fetching cryptocurrency data from CoinCap API.

    CoinCap API Features:
    - No API key required (free tier)
    - Base URL: https://api.coincap.io/v2/
    - Rate limits: More generous than CoinGecko
    - Response format: JSON with data object
    - Timestamps: UNIX milliseconds
    """

    # API Configuration
    BASE_URL = "https://api.coincap.io/v2/"
    REQUEST_TIMEOUT = 30  # seconds
    MAX_RETRIES = 3
    RETRY_DELAY = 1  # seconds (will be multiplied by retry attempt)

    # Cache TTL (seconds)
    CURRENT_PRICE_CACHE_TTL = 300  # 5 minutes
    HISTORICAL_PRICE_CACHE_TTL = 86400  # 24 hours
    SYMBOL_MAPPING_CACHE_TTL = 3600  # 1 hour

    # Rate limiting
    RATE_LIMIT_DELAY = 0.1  # seconds between requests

    def __init__(self):
        """Initialize CoinCap service with Redis caching."""
        self._session = requests.Session()
        self._session.timeout = self.REQUEST_TIMEOUT
        self._last_request_time = 0
        self._redis_client = None

        # Initialize Redis connection
        try:
            self._redis_client = redis.from_url(settings.redis_url, decode_responses=False)
            # Test connection
            self._redis_client.ping()
            logger.info("CoinCap service: Connected to Redis")
        except Exception as e:
            logger.warning(f"CoinCap service: Could not connect to Redis: {e}. Caching will be disabled.")
            self._redis_client = None

    def _rate_limit(self):
        """Implement simple rate limiting."""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time

        if time_since_last < self.RATE_LIMIT_DELAY:
            sleep_time = self.RATE_LIMIT_DELAY - time_since_last
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.3f} seconds")
            time.sleep(sleep_time)

        self._last_request_time = time.time()

    def _get_cache_key(self, prefix: str, *args) -> str:
        """Generate cache key for Redis."""
        return f"coincap:{prefix}:{':'.join(str(arg) for arg in args)}"

    def _cache_get(self, key: str) -> Optional[any]:
        """Get data from Redis cache."""
        if not self._redis_client:
            return None

        try:
            cached_data = self._redis_client.get(key)
            if cached_data:
                return pickle.loads(cached_data)
        except Exception as e:
            logger.warning(f"Error getting data from cache: {e}")
        return None

    def _cache_set(self, key: str, data: any, ttl: int) -> None:
        """Set data in Redis cache."""
        if not self._redis_client:
            return

        try:
            serialized_data = pickle.dumps(data)
            self._redis_client.setex(key, ttl, serialized_data)
        except Exception as e:
            logger.warning(f"Error setting data in cache: {e}")

    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Make HTTP request to CoinCap API with retry logic.

        Args:
            endpoint: API endpoint (e.g., 'assets/bitcoin')
            params: Query parameters

        Returns:
            JSON response data or None if failed
        """
        url = urljoin(self.BASE_URL, endpoint)

        for attempt in range(self.MAX_RETRIES):
            try:
                # Rate limiting
                self._rate_limit()

                logger.debug(f"CoinCap API request: {url} (attempt {attempt + 1})")

                response = self._session.get(url, params=params)
                response.raise_for_status()

                data = response.json()

                # CoinCap returns data in a 'data' field
                if 'data' in data:
                    return data

                logger.warning(f"Unexpected response format from CoinCap: {data}")
                return data

            except requests.exceptions.RequestException as e:
                wait_time = self.RETRY_DELAY * (2 ** attempt)
                logger.warning(
                    f"CoinCap API request failed (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}. "
                    f"Retrying in {wait_time} seconds..."
                )

                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(wait_time)
                else:
                    logger.error(f"CoinCap API request failed after {self.MAX_RETRIES} attempts: {e}")
                    return None

            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode CoinCap API response: {e}")
                return None

    def map_symbol_to_coincec_id(self, symbol: str) -> Optional[str]:
        """
        Map cryptocurrency symbol to CoinCap asset ID.

        Args:
            symbol: Cryptocurrency symbol (e.g., 'BTC', 'ETH')

        Returns:
            CoinCap asset ID or None if not found
        """
        # Check cache first
        cache_key = self._get_cache_key("symbol_mapping", symbol)
        cached_result = self._cache_get(cache_key)
        if cached_result:
            logger.debug(f"Cache hit for symbol mapping: {symbol} -> {cached_result}")
            return cached_result

        # Common symbol mappings
        symbol_mappings = {
            'BTC': 'bitcoin',
            'ETH': 'ethereum',
            'BNB': 'binance-coin',
            'XRP': 'ripple',
            'ADA': 'cardano',
            'SOL': 'solana',
            'DOGE': 'dogecoin',
            'DOT': 'polkadot',
            'MATIC': 'polygon',
            'SHIB': 'shiba-inu',
            'AVAX': 'avalanche-2',
            'LINK': 'chainlink',
            'UNI': 'uniswap',
            'LTC': 'litecoin',
            'ATOM': 'cosmos',
            'XLM': 'stellar',
            'BCH': 'bitcoin-cash',
            'FIL': 'filecoin',
            'TRX': 'tron',
            'ETC': 'ethereum-classic',
            'XMR': 'monero',
            'APE': 'apecoin',
            'CRO': 'crypto-com-chain',
            'MANA': 'decentraland',
            'ALGO': 'algorand',
            'VET': 'vechain',
            'SAND': 'the-sandbox',
            'FTT': 'ftx-token',
            'HOT': 'holotoken',
            'EGLD': 'elrond-erd-2',
            'AAVE': 'aave',
            'THETA': 'theta-token',
            'ENJ': 'enjincoin',
            'KCS': 'kucoin-shares',
            'MKR': 'maker',
            'COMP': 'compound-governance-token',
            'SUSHI': 'sushi',
            'ICP': 'internet-computer',
            'HBAR': 'hedera-hashgraph',
            'STX': 'blockstack',
            'RUNE': 'thorchain',
            'ZEC': 'zcash',
            'DCR': 'decred',
            'DASH': 'dash',
            'KSM': 'kusama',
            'NEAR': 'near',
            'AR': 'arweave',
            'QNT': 'quant-network',
            'BAT': 'basic-attention-token',
            'GRT': 'the-graph',
            'LRC': 'loopring',
            'LPT': 'livepeer',
            'SNX': 'synthetix-network-token',
            'YFI': 'yearn-finance',
            'CGLD': 'celo-dollar',
            'SKL': 'skale',
            'OXT': 'orchid-protocol',
            'ANKR': 'ankr',
            'SXP': 'swipe',
            'HNT': 'helium',
            'BAL': 'balancer',
            'CRV': 'curve-dao-token',
            'REN': 'republic-protocol',
            'LUNA': 'terra-luna',
            'UMA': 'uma',
            'RSR': 'reserve-rights-token',
            'FEI': 'fei-protocol',
            'MIR': 'mirror-protocol',
            'NU': 'nucypher',
            'COVER': 'cover-protocol',
            'SFI': 'saffron-finance',
            'CLV': 'clover-finance',
            'INDEX': 'index-cooperative',
            'BLT': 'bloomtoken',
            'REP': 'augur',
            'NMR': 'numeraire',
            'BNT': 'bancor',
            'MLN': 'melon',
            'GNO': 'gnosis',
            'ANT': 'aragon',
            'DGD': 'digixdao',
            'LQD': 'liquity-usd',
            'BOND': 'bondly',
            'XIO': 'xio-network',
            'HEZ': 'hermez-network',
            'TRAC': 'origintrail',
            'TORN': 'tornado-cash',
            'WNXM': 'wrapped-nxm',
            'WNCG': 'wrapped-ncg',
            'NCT': 'polyient-games-governance-token',
            'DEUS': 'deus-finance',
            'DEGO': 'dego-finance',
            'UNIT': 'universal-market-access',
            'BSW': 'biswap',
            'GPC': 'game-coin',
            'GNO': 'gnosis',
            'LGCY': 'legacy',
            'NEXO': 'nexo',
            'POLS': 'polkastarter',
            'KEEP': 'keep-network',
            'HGET': 'hedget',
            'MATH': 'math',
            'VAI': 'vai',
            'TKO': 'tokocrypto',
            'SUN': 'sun-token',
            'SUPER': 'superfarm',
            'CTK': 'certik',
            'FRAX': 'frax',
            'OPT': 'optris',
            'BIFI': 'beefy-finance',
            'XOR': 'sora',
            'TWT': 'trust-wallet-token',
            'KP3R': 'keep3rv1',
            'WSB': 'wallstreetbets',
            'AUTO': 'auto',
            'DFYN': 'dfyn-network',
            'ICE': 'icetime',
            'GAL': 'project-galaxy',
            'QI': 'benqi',
            'BETA': 'beta-finance',
            'SPO': 'spore',
            'RARI': 'rarible',
            'UFO': 'ufodao-gaming',
            'GMT': 'stepn',
            'AURORA': 'aurora-dao',
            'OOKI': 'ooki',
            'GLM': 'golem',
            'HOPR': 'hopr',
            'LCX': 'lcx',
            'MNW': 'menew',
            'PLA': 'playdapp',
            'DEAP': 'digital-entertainment-asset',
            'FORTH': 'ampleforth-governance-token',
            'OGN': 'origin-protocol',
            'BONDLY': 'bondly',
            'XED': 'exeedme',
            'RFuel': 'rio-defi',
            'DOS': 'dos-network',
            'DIA': 'dia-data',
            'STAK': 'stakewise',
            'UNFI': 'unification',
            'FARM': 'harvest-finance',
            'SEFI': 'secret-network',
            'WSM': 'wolves-of-wall-street',
            'PNT': 'pnetwork',
            'XHV': 'haven-protocol',
            'DIP': 'dipnet',
            'XMC': 'monero-original',
            'SRK': 'sparkpoint',
            'BANK': 'bankless-dao',
            'TDP': 'thedataprocess',
            'GNY': 'gny',
            'DVF': 'deversifi',
            'BOND': 'bondappetit',
            'XRT': 'robonomics-network',
            'MIR': 'mirror-protocol',
            'PSG': 'paris-saint-germain-fan-token',
            'JUV': 'juventus-fan-token',
            'ACM': 'ac-milan-fan-token',
            'ASR': 'as-roma-fan-token',
            'SANTOS': 'santos-fc-fan-token',
            'LAZIO': 's-s-lazio-fan-token',
            'NAPOLI': 'ssc-napoli-fan-token',
            'GAL': 'project-galaxy',
            'PORTO': 'fc-porto-fan-token',
            'CITY': 'manchester-city-fan-token',
            'ATM': 'atm',
            'AFA': 'argon',
            'TRU': 'truefi',
            'WOO': 'woonetwork',
            'TIDAL': 'tidal-finance',
            'CLV': 'clover-finance',
            'PERP': 'perpetual-protocol',
            'PYR': 'vulcan-forged',
            'PAR': 'parachute',
            'TOWER': 'tower-token',
            'XED': 'exeedme',
            'UOS': 'ultra',
            'MC': 'merit-circle',
            'GF': 'gaming-finance',
            'DFYN': 'dfyn-network',
            'BSW': 'biswap',
            'GFI': 'goldfinch',
            'LITH': 'lithium',
            'FODL': 'fodl-finance',
            'GENE': 'genopets',
            'DEXE': 'dexe',
            'RBN': 'ribbon-finance',
            'AURORA': 'aurora-dao',
            'TRAC': 'origintrail',
            'BONDLY': 'bondly',
            'NYAN': 'nyan-finance',
            'SUSHI': 'sushi',
            'LOOKS': 'looksrare',
            'MAGIC': 'magic',
            'TAMA': 'tamadoge',
            'LDO': 'lido-dao',
            'HFT': 'hashflow',
            'GMT': 'stepn',
            'APT': 'aptos',
            'ARB': 'arbitrum',
            'OP': 'optimism',
            'BLUR': 'blur',
            'PEPE': 'pepe',
            'FLOKI': 'floki',
            'TIA': 'celestia',
            'SEI': 'sei-network',
            'JUP': 'jupiter',
            'BONK': 'bonk',
            'PYTH': 'pyth-network',
            'JTO': 'jito',
            'WIF': 'dogwifhat',
            'RNDR': 'render-token',
            'DYDX': 'dydx',
            'AAVE': 'aave',
            'LINK': 'chainlink',
            'UNI': 'uniswap-protocol-token',
            'MATIC': 'polygon-ecosystem-token',
            'SAND': 'the-sandbox',
            'MANA': 'decentraland',
            'AXS': 'axie-infinity',
            'GALA': 'gala',
            'CHZ': 'chiliz',
            'ENJ': 'enjin-coin',
            'LRC': 'loopring',
            'KCS': 'kucoin-token',
            'HOT': 'holo',
            'CRO': 'crypto-com-chain',
            'VET': 'vechain',
            'THETA': 'theta-token',
            'FTT': 'ftx-token',
            'EGLD': 'elrond-erd-2',
            'KSM': 'kusama',
            'NEAR': 'near',
            'ICP': 'internet-computer',
            'HBAR': 'hedera-hashgraph',
            'STX': 'blockstack',
            'RUNE': 'thorchain',
            'ZEC': 'zcash',
            'DASH': 'dash',
            'KAVA': 'kava',
            'WAVES': 'waves',
            'QTUM': 'qtum',
            'XTZ': 'tezos',
            'ALGO': 'algorand',
            'EOS': 'eos',
            'BTG': 'bitcoin-gold',
            'BCH': 'bitcoin-cash',
            'BSV': 'bitcoin-sv',
            'LTC': 'litecoin',
            'XMR': 'monero',
            'ETC': 'ethereum-classic',
            'XRP': 'ripple',
            'ADA': 'cardano',
            'DOT': 'polkadot',
            'SOL': 'solana',
            'DOGE': 'dogecoin',
            'AVAX': 'avalanche-2',
            'SHIB': 'shiba-inu',
            'TRX': 'tron',
            'FIL': 'filecoin',
            'ATOM': 'cosmos',
            'LINK': 'chainlink',
            'XLM': 'stellar',
            'NEO': 'neo',
            'MIOTA': 'iota',
            'VET': 'vechain',
            'WAVES': 'waves',
            'ZIL': 'zilliqa',
            'MKR': 'maker',
            'COMP': 'compound-governance-token',
            'SUSHI': 'sushi',
            'CRV': 'curve-dao-token',
            'BAL': 'balancer',
            'SNX': 'synthetix-network-token',
            'UMA': 'uma',
            'YFI': 'yearn-finance',
            'REN': 'ren',
            'KNC': 'kyber-network-crystal',
            'ZRX': '0x',
            'BAND': 'band-protocol',
            'RLC': 'iexec-rlc',
            'LPT': 'livepeer',
            'BAT': 'basic-attention-token',
            'GRT': 'the-graph',
            'STORJ': 'storj',
            'OCEAN': 'ocean-protocol',
            'COTI': 'coti',
            'MANA': 'decentraland',
            'SAND': 'the-sandbox',
            'AXS': 'axie-infinity',
            'GALA': 'gala',
            'ENJ': 'enjin-coin',
            'CHZ': 'chiliz',
            'LRC': 'loopring',
            'HOT': 'holo',
            'CRO': 'crypto-com-chain',
            'VET': 'vechain',
            'THETA': 'theta-token',
            'FTT': 'ftx-token',
            'EGLD': 'elrond-erd-2',
            'KSM': 'kusama',
            'NEAR': 'near',
            'ICP': 'internet-computer',
            'HBAR': 'hedera-hashgraph',
            'STX': 'blockstack',
            'RUNE': 'thorchain',
            'ZEC': 'zcash',
            'DASH': 'dash',
            'KAVA': 'kava',
            'WAVES': 'waves',
            'QTUM': 'qtum',
            'XTZ': 'tezos',
            'ALGO': 'algorand',
            'EOS': 'eos',
            'BTG': 'bitcoin-gold',
            'BCH': 'bitcoin-cash',
            'BSV': 'bitcoin-sv',
            'LTC': 'litecoin',
            'XMR': 'monero',
            'ETC': 'ethereum-classic',
            'XRP': 'ripple',
            'ADA': 'cardano',
            'DOT': 'polkadot',
            'SOL': 'solana',
            'DOGE': 'dogecoin',
            'AVAX': 'avalanche-2',
            'SHIB': 'shiba-inu',
            'TRX': 'tron',
            'FIL': 'filecoin',
            'ATOM': 'cosmos',
            'XLM': 'stellar',
            'NEO': 'neo',
            'MIOTA': 'iota',
            'VET': 'vechain',
            'WAVES': 'waves',
            'ZIL': 'zilliqa',
            'MKR': 'maker',
            'COMP': 'compound-governance-token',
            'SUSHI': 'sushi',
            'CRV': 'curve-dao-token',
            'BAL': 'balancer',
            'SNX': 'synthetix-network-token',
            'UMA': 'uma',
            'YFI': 'yearn-finance',
            'REN': 'ren',
            'KNC': 'kyber-network-crystal',
            'ZRX': '0x',
            'BAND': 'band-protocol',
            'RLC': 'iexec-rlc',
            'LPT': 'livepeer',
            'BAT': 'basic-attention-token',
            'GRT': 'the-graph',
            'STORJ': 'storj',
            'OCEAN': 'ocean-protocol',
            'COTI': 'coti'
        }

        # Normalize symbol to uppercase
        symbol = symbol.upper().strip()

        # Check mapping
        if symbol in symbol_mappings:
            result = symbol_mappings[symbol]
            # Cache the result
            self._cache_set(cache_key, result, self.SYMBOL_MAPPING_CACHE_TTL)
            return result

        # If symbol already looks like a CoinCap ID, return it
        if '-' in symbol:
            logger.debug(f"Symbol {symbol} appears to be a CoinCap ID already")
            return symbol.lower()

        # Try to find the asset by searching
        logger.info(f"No direct mapping found for {symbol}, attempting search")
        result = self._search_asset_by_symbol(symbol)

        # Cache the result
        if result:
            self._cache_set(cache_key, result, self.SYMBOL_MAPPING_CACHE_TTL)

        return result

    def _search_asset_by_symbol(self, symbol: str) -> Optional[str]:
        """
        Search for asset by symbol when no direct mapping exists.

        Args:
            symbol: Cryptocurrency symbol

        Returns:
            CoinCap asset ID or None if not found
        """
        try:
            # Search for assets with this symbol
            response = self._make_request('assets', {'search': symbol})

            if response and 'data' in response:
                assets = response['data']

                # Look for exact match
                for asset in assets:
                    if asset.get('symbol', '').upper() == symbol:
                        coincapec_id = asset.get('id')
                        logger.info(f"Found CoinCap ID for {symbol}: {coincapec_id}")
                        return coincapec_id

                # If no exact match, try partial match
                for asset in assets:
                    if symbol in asset.get('symbol', '').upper():
                        coincapec_id = asset.get('id')
                        logger.info(f"Found partial match for {symbol}: {coincapec_id} ({asset.get('symbol')})")
                        return coincapec_id

            logger.warning(f"No CoinCap asset found for symbol: {symbol}")
            return None

        except Exception as e:
            logger.error(f"Error searching for CoinCap asset {symbol}: {e}")
            return None

    def get_current_price(self, symbol: str, currency: str = "eur") -> Optional[Dict[str, Decimal]]:
        """
        Get current price for a cryptocurrency.

        Args:
            symbol: Cryptocurrency symbol (e.g., 'BTC', 'ETH')
            currency: Target currency ('eur' or 'usd')

        Returns:
            Dict with price data or None if failed
        """
        # Check cache first
        cache_key = self._get_cache_key("current_price", symbol, currency)
        cached_result = self._cache_get(cache_key)
        if cached_result:
            logger.debug(f"Cache hit for current price: {symbol}")
            return cached_result

        try:
            # Map symbol to CoinCap ID
            coincapec_id = self.map_symbol_to_coincec_id(symbol)
            if not coincapec_id:
                logger.error(f"Could not map symbol {symbol} to CoinCap ID")
                return None

            # Fetch asset data
            response = self._make_request(f'assets/{coincapec_id}')

            if not response or 'data' not in response:
                logger.error(f"No data received from CoinCap for {coincapec_id}")
                return None

            asset_data = response['data']

            # Extract price (CoinCap always returns in USD)
            price_usd = Decimal(str(asset_data.get('priceUsd', '0')))

            if price_usd == 0:
                logger.warning(f"Zero price received for {symbol}")
                return None

            # Convert to target currency if needed
            if currency.lower() == 'eur':
                # Get USD to EUR conversion rate
                eur_rate = self._get_usd_to_eur_rate()
                if eur_rate is None:
                    logger.error("Could not get USD to EUR conversion rate")
                    return None

                price = price_usd * eur_rate
                currency_code = 'EUR'
            else:
                price = price_usd
                currency_code = 'USD'

            # Get additional data
            market_cap_usd = Decimal(str(asset_data.get('marketCapUsd', '0')))
            volume_24h_usd = Decimal(str(asset_data.get('volumeUsd24Hr', '0')))
            change_percent_24h = Decimal(str(asset_data.get('changePercent24Hr', '0')))

            return {
                'symbol': symbol.upper(),
                'coincapec_id': coincapec_id,
                'price': price,
                'currency': currency_code,
                'price_usd': price_usd,
                'market_cap_usd': market_cap_usd,
                'volume_24h_usd': volume_24h_usd,
                'change_percent_24h': change_percent_24h,
                'timestamp': datetime.utcnow(),
                'source': 'coincap'
            }

            # Cache the result
            self._cache_set(cache_key, result, self.CURRENT_PRICE_CACHE_TTL)
            return result

        except Exception as e:
            logger.error(f"Error fetching current price for {symbol}: {e}")
            return None

    def get_historical_prices(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        currency: str = "eur"
    ) -> List[Dict]:
        """
        Get historical price data for a cryptocurrency.

        Args:
            symbol: Cryptocurrency symbol
            start_date: Start date for historical data
            end_date: End date for historical data
            currency: Target currency ('eur' or 'usd')

        Returns:
            List of price dictionaries
        """
        # Check cache first
        cache_key = self._get_cache_key("historical_prices", symbol, start_date, end_date, currency)
        cached_result = self._cache_get(cache_key)
        if cached_result:
            logger.debug(f"Cache hit for historical prices: {symbol} ({start_date} to {end_date})")
            return cached_result

        try:
            # Map symbol to CoinCap ID
            coincapec_id = self.map_symbol_to_coincec_id(symbol)
            if not coincapec_id:
                logger.error(f"Could not map symbol {symbol} to CoinCap ID")
                return []

            # Convert dates to timestamps (CoinCap uses milliseconds)
            start_timestamp = int(datetime.combine(start_date, datetime.min.time()).timestamp() * 1000)
            end_timestamp = int(datetime.combine(end_date, datetime.max.time()).timestamp() * 1000)

            # Fetch historical data
            response = self._make_request(
                f'assets/{coincapec_id}/history',
                {
                    'interval': 'd1',  # daily data
                    'start': start_timestamp,
                    'end': end_timestamp
                }
            )

            if not response or 'data' not in response:
                logger.error(f"No historical data received from CoinCap for {coincapec_id}")
                return []

            price_data = response['data']

            # Get currency conversion rate if needed
            eur_rate = None
            if currency.lower() == 'eur':
                eur_rate = self._get_usd_to_eur_rate()
                if eur_rate is None:
                    logger.error("Could not get USD to EUR conversion rate")
                    return []

            # Process the data
            prices = []
            for item in price_data:
                try:
                    # Convert timestamp from milliseconds
                    timestamp_ms = int(item.get('time', '0'))
                    price_date = datetime.fromtimestamp(timestamp_ms / 1000).date()

                    # Extract price (CoinCap always returns in USD)
                    price_usd = Decimal(str(item.get('priceUsd', '0')))

                    if price_usd == 0:
                        continue

                    # Convert to target currency if needed
                    if currency.lower() == 'eur' and eur_rate:
                        price = price_usd * eur_rate
                        currency_code = 'EUR'
                    else:
                        price = price_usd
                        currency_code = 'USD'

                    prices.append({
                        'date': price_date,
                        'symbol': symbol.upper(),
                        'coincapec_id': coincapec_id,
                        'price': price,
                        'currency': currency_code,
                        'price_usd': price_usd,
                        'timestamp': datetime.fromtimestamp(timestamp_ms / 1000),
                        'source': 'coincap'
                    })

                except (ValueError, TypeError) as e:
                    logger.warning(f"Error processing historical price data point: {e}")
                    continue

            logger.info(f"Retrieved {len(prices)} historical price points for {symbol}")

            # Cache the result
            self._cache_set(cache_key, prices, self.HISTORICAL_PRICE_CACHE_TTL)
            return prices

        except Exception as e:
            logger.error(f"Error fetching historical prices for {symbol}: {e}")
            return []

    def get_supported_symbols(self) -> List[Dict]:
        """
        Get list of supported cryptocurrency assets from CoinCap.

        Returns:
            List of asset dictionaries with id, symbol, name, etc.
        """
        try:
            # Get top assets (limited to 1000 for performance)
            response = self._make_request('assets', {'limit': 1000})

            if not response or 'data' not in response:
                logger.error("No assets data received from CoinCap")
                return []

            assets = response['data']

            # Process assets
            supported_assets = []
            for asset in assets:
                try:
                    supported_assets.append({
                        'coincapec_id': asset.get('id'),
                        'symbol': asset.get('symbol'),
                        'name': asset.get('name'),
                        'price_usd': Decimal(str(asset.get('priceUsd', '0'))),
                        'market_cap_usd': Decimal(str(asset.get('marketCapUsd', '0'))),
                        'volume_24h_usd': Decimal(str(asset.get('volumeUsd24Hr', '0'))),
                        'change_percent_24h': Decimal(str(asset.get('changePercent24Hr', '0')))
                    })
                except (ValueError, TypeError) as e:
                    logger.warning(f"Error processing asset data: {e}")
                    continue

            logger.info(f"Retrieved {len(supported_assets)} supported assets from CoinCap")
            return supported_assets

        except Exception as e:
            logger.error(f"Error fetching supported symbols from CoinCap: {e}")
            return []

    def _get_usd_to_eur_rate(self) -> Optional[Decimal]:
        """
        Get USD to EUR conversion rate.

        In a real implementation, this could:
        1. Use a forex API
        2. Use the existing price fetcher for FX rates
        3. Cache the rate for a certain period

        For now, we'll use a reasonable approximation.

        Returns:
            USD to EUR conversion rate or None if failed
        """
        try:
            # Try to use the existing price fetcher if available
            from .price_fetcher import PriceFetcher

            price_fetcher = PriceFetcher()
            rate = price_fetcher.fetch_fx_rate("USD", "EUR")

            if rate:
                return rate

            # Fallback to a reasonable approximation
            # NOTE: In production, this should be replaced with a proper FX API
            logger.warning("Using fallback USD to EUR rate (0.92)")
            return Decimal("0.92")

        except Exception as e:
            logger.error(f"Error getting USD to EUR rate: {e}")
            return None

    def test_connection(self) -> bool:
        """
        Test connection to CoinCap API.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            response = self._make_request('assets', {'limit': 1})
            return response is not None and 'data' in response
        except Exception as e:
            logger.error(f"CoinCap API connection test failed: {e}")
            return False


# Create a singleton instance
coincap_service = CoinCapService()