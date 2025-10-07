"""
Crypto-specific validation helpers and utilities.

This module provides centralized validation functions for cryptocurrency-related
operations in the portfolio tracker, ensuring consistency across all schemas.
"""
import re
import hashlib
from decimal import Decimal
from typing import Dict, List, Optional, Tuple


class CryptoValidationError(Exception):
    """Exception raised for crypto validation errors."""
    pass


def is_crypto_ticker(ticker: str) -> bool:
    """
    Check if a ticker represents a cryptocurrency.

    Args:
        ticker: Ticker symbol to check

    Returns:
        True if ticker appears to be a cryptocurrency
    """
    if not ticker:
        return False

    ticker = ticker.upper().strip()

    # Check for crypto patterns with separators
    if '-' in ticker or '/' in ticker:
        return True

    # Known crypto trading pair patterns
    crypto_patterns = [
        r'^[A-Z]{2,5}USD$',  # Direct pair like BTCUSD
        r'^[A-Z]{2,5}USDT$',  # Tether pairs
        r'^[A-Z]{2,5}EUR$',   # Euro pairs
        r'^[A-Z]{2,5}GBP$',   # GBP pairs
    ]

    for pattern in crypto_patterns:
        if re.match(pattern, ticker):
            return True

    # Known crypto tickers (exact match only to avoid false positives)
    known_crypto = {
        # Major cryptocurrencies
        'BTC', 'ETH', 'USDT', 'USDC', 'BNB', 'XRP', 'ADA', 'SOL', 'DOGE', 'DOT',
        'AVAX', 'MATIC', 'LINK', 'UNI', 'ATOM', 'LTC', 'SHIB', 'TRX', 'XLM',
        'FIL', 'ETC', 'VET', 'THETA', 'ICP', 'HBAR', 'EGLD', 'FTT', 'ALGO',
        'AAVE', 'CAKE', 'MANA', 'SAND', 'AXS', 'LUNA', 'CRV', 'COMP', 'MKR',

        # Additional cryptos
        'BCH', 'EOS', 'XTZ', 'NEO', 'DASH', 'ZEC', 'XMR', 'WAVES', 'KSM',
        'RUNE', 'FTM', 'CELO', 'ONE', 'HOT', 'ENJ', 'CRO', 'KAVA', 'ROSE',
        'ALICE', 'LRC', 'BAT', 'GRT', 'SNX', 'SUSHI', 'YFI', 'UMA', 'REP',

        # Stablecoins
        'BUSD', 'DAI', 'TUSD', 'USDP', 'FRAX', 'LUSD', 'MIM', 'FEI',

        # Layer 2s and scaling solutions
        'MATIC', 'ARB', 'OP', 'LRC', 'IMX', 'DYDX', 'GMX', 'GNS',

        # DeFi tokens
        'UNI', 'SUSHI', 'CRV', 'COMP', 'AAVE', 'MKR', 'YFI', 'SNX',
        'BAL', '1INCH', 'RUNE', 'KAVA', 'CAKE', 'ALPHA', 'SFP',

        # Gaming/Metaverse
        'MANA', 'SAND', 'AXS', 'ALICE', 'GALA', 'ENJ', 'RNDR', 'SAND',
        'TLM', 'PYR', 'ATLAS', 'POLIS', 'STARL', 'MBOX', 'DPET',

        # Privacy coins
        'XMR', 'ZEC', 'DASH', 'SCRT', 'FIRO', 'BEAM', 'XVG', 'NAV',

        # Exchange tokens
        'BNB', 'FTT', 'CRO', 'KCS', 'HT', 'OKB', 'LEO', 'GT', 'BGB',
        'LUNO', 'WOO', 'KRL', 'CELR', 'MEX'
    }

    return ticker in known_crypto


def normalize_crypto_ticker(ticker: str) -> str:
    """
    Normalize crypto ticker to standard format.

    Args:
        ticker: Raw ticker from exchange

    Returns:
        Normalized ticker symbol

    Raises:
        CryptoValidationError: If ticker format is invalid
    """
    if not ticker:
        raise CryptoValidationError("Ticker cannot be empty")

    ticker = ticker.upper().strip()

    # Handle various trading pair formats
    separators = ['-', '/', 'USD', 'USDT', 'EUR', 'GBP', 'BTC', 'ETH']

    for sep in separators:
        if sep in ticker:
            # Split and take the first part (base asset)
            parts = ticker.split(sep)
            ticker = parts[0]
            break

    # Validate the normalized ticker
    if len(ticker) > 20:
        raise CryptoValidationError("Crypto ticker too long (max 20 characters)")

    if not re.match(r'^[A-Z0-9]+$', ticker):
        raise CryptoValidationError("Crypto ticker contains invalid characters")

    return ticker


def validate_crypto_ticker(ticker: str) -> str:
    """
    Validate and normalize cryptocurrency ticker.

    Args:
        ticker: Raw ticker symbol

    Returns:
        Normalized ticker symbol

    Raises:
        CryptoValidationError: If ticker format is invalid
    """
    if not ticker:
        raise CryptoValidationError("Ticker is required")

    # First normalize it
    normalized = normalize_crypto_ticker(ticker)

    # Check if it's actually a crypto ticker
    if not is_crypto_ticker(normalized):
        raise CryptoValidationError(f"'{normalized}' does not appear to be a valid cryptocurrency ticker")

    return normalized


def generate_crypto_identifier(ticker: str) -> str:
    """
    Generate ISIN-like identifier for cryptocurrency.

    Since cryptos don't have ISINs, we generate a unique identifier
    based on the ticker only for deterministic results.

    Args:
        ticker: Normalized ticker symbol

    Returns:
        12-character identifier similar to ISIN format

    Raises:
        CryptoValidationError: If ticker is invalid
    """
    if not ticker:
        raise CryptoValidationError("Ticker is required for crypto identifier generation")

    ticker = validate_crypto_ticker(ticker)

    # Create a deterministic hash of the ticker only
    content = f"CRYPTO-{ticker}"
    hash_obj = hashlib.sha256(content.encode())
    hash_hex = hash_obj.hexdigest()[:10]  # Take first 10 chars

    # Format similar to ISIN (12 characters total)
    # Start with "XC" (eXchange Crypto) country code
    identifier = f"XC{hash_hex}"

    return identifier.upper()


def validate_crypto_isin(isin: str) -> str:
    """
    Validate crypto ISIN-like identifier (XC prefixed).

    Args:
        isin: ISIN identifier

    Returns:
        Validated ISIN

    Raises:
        CryptoValidationError: If ISIN format is invalid for crypto
    """
    if not isin:
        raise CryptoValidationError("Crypto ISIN is required")

    isin = isin.upper().strip()

    # Crypto ISINs should start with "XC"
    if not isin.startswith('XC'):
        raise CryptoValidationError("Crypto ISIN must start with 'XC'")

    if len(isin) != 12:
        raise CryptoValidationError("Crypto ISIN must be 12 characters")

    if not re.match(r'^XC[A-Z0-9]{10}$', isin):
        raise CryptoValidationError("Invalid crypto ISIN format")

    return isin


def validate_crypto_quantity(quantity: Decimal) -> Decimal:
    """
    Validate cryptocurrency quantity with proper precision.

    Args:
        quantity: Transaction quantity

    Returns:
        Validated quantity

    Raises:
        CryptoValidationError: If quantity precision is invalid
    """
    if quantity <= 0:
        raise CryptoValidationError("Quantity must be greater than 0")

    # Check for excessive decimal places (more than 18)
    if quantity.as_tuple().exponent < -18:
        raise CryptoValidationError("Crypto quantity precision too high (max 18 decimal places)")

    return quantity


def validate_crypto_wallet_address(address: str, ticker: str = None) -> str:
    """
    Validate crypto wallet address format.

    Args:
        address: Wallet address to validate
        ticker: Optional ticker for format-specific validation

    Returns:
        Validated wallet address

    Raises:
        CryptoValidationError: If address format is invalid
    """
    if not address:
        raise CryptoValidationError("Wallet address is required")

    address = address.strip()

    # Basic length validation (most addresses are between 26-90 characters)
    if len(address) < 26 or len(address) > 90:
        raise CryptoValidationError("Wallet address length invalid (expected 26-90 characters)")

    # Allow alphanumeric characters and common address symbols
    if not re.match(r'^[a-zA-Z0-9]+$', address):
        raise CryptoValidationError("Wallet address contains invalid characters")

    # TODO: Add format-specific validation for different cryptos
    # For now, just basic validation

    return address


def validate_crypto_exchange(exchange: str) -> str:
    """
    Validate crypto exchange name.

    Args:
        exchange: Exchange name to validate

    Returns:
        Validated exchange name

    Raises:
        CryptoValidationError: If exchange name is invalid
    """
    if not exchange:
        raise CryptoValidationError("Exchange name is required")

    exchange = exchange.strip()
    normalized = exchange.upper()

    if len(normalized) > 50:
        raise CryptoValidationError("Exchange name too long (max 50 characters)")

    # Allow alphanumeric, spaces, and common characters
    if not re.match(r'^[A-Z0-9\s\-\.\&]+$', normalized):
        raise CryptoValidationError("Exchange name contains invalid characters")

    return normalized


def get_supported_crypto_currencies() -> List[str]:
    """
    Get list of supported crypto currencies for transactions.

    Returns:
        List of supported currency codes
    """
    return ['BTC', 'ETH', 'USDT', 'USDC', 'BNB']


def get_supported_crypto_exchanges() -> List[str]:
    """
    Get list of supported crypto exchanges.

    Returns:
        List of supported exchange names
    """
    return [
        'COINBASE', 'BINANCE', 'KRAKEN', 'GEMINI', 'BITFINEX',
        'HUOBI', 'OKEX', 'BITTREX', 'POLONIEX', 'BITSTAMP',
        'COINMAMA', 'LOCALBITCOINS', 'PAXFUL', 'KUCOIN'
    ]


def validate_crypto_currency(currency: str) -> str:
    """
    Validate crypto currency code.

    Args:
        currency: Currency code to validate

    Returns:
        Validated currency code

    Raises:
        CryptoValidationError: If currency is not supported
    """
    if not currency:
        raise CryptoValidationError("Currency is required")

    currency = currency.upper().strip()

    supported = get_supported_crypto_currencies()

    if currency not in supported:
        raise CryptoValidationError(f"Currency '{currency}' not supported. Supported: {', '.join(supported)}")

    return currency


def detect_crypto_exchange_from_reference(reference: str) -> Optional[str]:
    """
    Attempt to detect crypto exchange from order reference.

    Args:
        reference: Order reference string

    Returns:
        Exchange name if detected, None otherwise
    """
    if not reference:
        return None

    reference = reference.upper().strip()

    # Check for common exchange patterns in order references
    exchange_patterns = {
        'COINBASE': r'COINBASE|CB-',
        'BINANCE': r'BN|BINANCE',
        'KRAKEN': r'KRAKEN|KR-',
        'GEMINI': r'GEMINI|GM-',
        'BITFINEX': r'BFX|BITFINEX',
        'HUOBI': r'HT|HUOBI',
        'OKEX': r'OK|OKEX',
        'BITTREX': r'BTRX|BITTREX',
        'POLONIEX': r'PLX|POLONIEX',
        'BITSTAMP': r'BTS|BITSTAMP'
    }

    for exchange, pattern in exchange_patterns.items():
        if re.search(pattern, reference):
            return exchange

    return None


def validate_crypto_price_source(source: str) -> str:
    """
    Validate crypto price data source.

    Args:
        source: Price source name

    Returns:
        Validated source name

    Raises:
        CryptoValidationError: If source is invalid
    """
    if not source:
        raise CryptoValidationError("Price source is required")

    source = source.upper().strip()

    valid_sources = {
        'COINGECKO', 'COINMARKETCAP', 'BINANCE', 'COINBASE', 'KRAKEN',
        'HUOBI', 'OKEX', 'BITFINEX', 'YAHOO', 'MANUAL'
    }

    if source not in valid_sources:
        raise CryptoValidationError(f"Invalid price source: {source}")

    return source


class CryptoValidationResult:
    """Container for crypto validation results."""

    def __init__(
        self,
        is_valid: bool,
        ticker: str = None,
        isin: str = None,
        errors: List[str] = None
    ):
        self.is_valid = is_valid
        self.ticker = ticker
        self.isin = isin
        self.errors = errors or []

    def add_error(self, error: str):
        """Add validation error."""
        self.errors.append(error)
        self.is_valid = False

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'is_valid': self.is_valid,
            'ticker': self.ticker,
            'isin': self.isin,
            'errors': self.errors
        }


def validate_crypto_transaction_data(
    ticker: str,
    quantity: Decimal,
    currency: str = None,
    isin: str = None,
    exchange: str = None,
    wallet_address: str = None
) -> CryptoValidationResult:
    """
    Comprehensive validation for crypto transaction data.

    Args:
        ticker: Crypto ticker symbol
        quantity: Transaction quantity
        currency: Transaction currency (optional)
        isin: Crypto ISIN (optional)
        exchange: Exchange name (optional)
        wallet_address: Wallet address (optional)

    Returns:
        CryptoValidationResult with validation status and details
    """
    result = CryptoValidationResult(is_valid=True)

    try:
        # Validate and normalize ticker
        validated_ticker = validate_crypto_ticker(ticker)
        result.ticker = validated_ticker
    except CryptoValidationError as e:
        result.add_error(str(e))

    try:
        # Validate quantity
        validate_crypto_quantity(quantity)
    except CryptoValidationError as e:
        result.add_error(str(e))

    # Validate currency if provided
    if currency:
        try:
            validate_crypto_currency(currency)
        except CryptoValidationError as e:
            result.add_error(str(e))

    # Validate or generate ISIN
    if isin:
        try:
            validate_crypto_isin(isin)
            result.isin = isin
        except CryptoValidationError as e:
            result.add_error(str(e))
    else:
        # Generate ISIN if ticker is valid
        if result.ticker:
            result.isin = generate_crypto_identifier(result.ticker)

    # Validate exchange if provided
    if exchange:
        try:
            validate_crypto_exchange(exchange)
        except CryptoValidationError as e:
            result.add_error(str(e))

    # Validate wallet address if provided
    if wallet_address:
        try:
            validate_crypto_wallet_address(wallet_address, ticker)
        except CryptoValidationError as e:
            result.add_error(str(e))

    return result