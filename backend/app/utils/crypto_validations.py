"""
Crypto Address Validation Utilities.

Provides validation functions for various blockchain addresses including
Bitcoin (P2PKH, P2SH, Bech32), Ethereum (EIP-55), and other common formats.
"""

import re
import hashlib
import logging
from typing import Tuple, Optional, Dict, Any
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

# Bitcoin address validation patterns
BITCOIN_P2PKH_PATTERN = re.compile(r'^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$')
BITCOIN_P2SH_PATTERN = re.compile(r'^3[a-km-zA-HJ-NP-Z1-9]{33}$')
BITCOIN_BECH32_PATTERN = re.compile(r'^bc1[ac-hj-np-z02-9]{8,87}$')

# Ethereum address validation pattern
ETHEREUM_PATTERN = re.compile(r'^0x[a-fA-F0-9]{40}$')

# Common cryptocurrency address patterns
CRYPTO_ADDRESS_PATTERNS = {
    'bitcoin_p2pkh': BITCOIN_P2PKH_PATTERN,
    'bitcoin_p2sh': BITCOIN_P2SH_PATTERN,
    'bitcoin_bech32': BITCOIN_BECH32_PATTERN,
    'ethereum': ETHEREUM_PATTERN,
}


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass


class AddressValidator(ABC):
    """Abstract base class for address validators."""

    @abstractmethod
    def validate(self, address: str) -> Tuple[bool, Optional[str]]:
        """
        Validate a blockchain address.

        Args:
            address: The address to validate

        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        pass

    @abstractmethod
    def get_network(self) -> str:
        """Get the network name for this validator."""
        pass


class BitcoinAddressValidator(AddressValidator):
    """Validator for Bitcoin addresses (P2PKH, P2SH, Bech32)."""

    def __init__(self):
        self.alphabet = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'

    def validate(self, address: str) -> Tuple[bool, Optional[str]]:
        """
        Validate Bitcoin address format.

        Args:
            address: Bitcoin address to validate

        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        try:
            address = address.strip()

            # Check P2PKH (legacy)
            if BITCOIN_P2PKH_PATTERN.match(address):
                return self._validate_base58(address)

            # Check P2SH (multisig)
            elif BITCOIN_P2SH_PATTERN.match(address):
                return self._validate_base58(address)

            # Check Bech32 (native segwit)
            elif BITCOIN_BECH32_PATTERN.match(address):
                return self._validate_bech32(address)

            else:
                return False, "Invalid Bitcoin address format"

        except Exception as e:
            logger.error(f"Bitcoin address validation error: {str(e)}")
            return False, f"Validation error: {str(e)}"

    def _validate_base58(self, address: str) -> Tuple[bool, Optional[str]]:
        """
        Validate Base58Check encoded Bitcoin address.

        Args:
            address: Base58Check encoded address

        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        try:
            # Decode base58
            decoded = self._base58_decode(address)

            if len(decoded) != 25:
                return False, "Invalid address length"

            # Verify checksum
            checksum = decoded[-4:]
            payload = decoded[:-4]
            calculated_checksum = hashlib.sha256(
                hashlib.sha256(payload).digest()
            ).digest()[:4]

            if checksum != calculated_checksum:
                return False, "Invalid checksum"

            return True, None

        except Exception as e:
            return False, f"Base58 validation failed: {str(e)}"

    def _validate_bech32(self, address: str) -> Tuple[bool, Optional[str]]:
        """
        Validate Bech32 encoded Bitcoin address.

        Args:
            address: Bech32 encoded address

        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        try:
            # Basic bech32 validation (simplified)
            if not address.lower().startswith('bc1'):
                return False, "Invalid Bech32 prefix"

            # Convert to lowercase for validation
            addr_lower = address.lower()

            # Check for valid characters
            if not re.match(r'^bc1[ac-hj-np-z02-9]{8,87}$', addr_lower):
                return False, "Invalid Bech32 characters"

            # Basic length check
            if len(addr_lower) < 8 or len(addr_lower) > 90:
                return False, "Invalid Bech32 length"

            return True, None

        except Exception as e:
            return False, f"Bech32 validation failed: {str(e)}"

    def _base58_decode(self, address: str) -> bytes:
        """Decode Base58Check string to bytes."""
        num = 0
        for char in address:
            if char not in self.alphabet:
                raise ValueError(f"Invalid character '{char}' in base58 string")
            num = num * 58 + self.alphabet.index(char)

        # Convert to bytes
        byte_array = []
        while num > 0:
            byte_array.insert(0, num % 256)
            num = num // 256

        return bytes(byte_array)

    def get_network(self) -> str:
        """Get the network name."""
        return "bitcoin"


class EthereumAddressValidator(AddressValidator):
    """Validator for Ethereum addresses with EIP-55 checksum validation."""

    def validate(self, address: str) -> Tuple[bool, Optional[str]]:
        """
        Validate Ethereum address format and EIP-55 checksum.

        Args:
            address: Ethereum address to validate

        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        try:
            address = address.strip()

            # Check basic format
            if not ETHEREUM_PATTERN.match(address):
                return False, "Invalid Ethereum address format"

            # Remove 0x prefix
            addr_without_prefix = address[2:]

            # Check if it's all lowercase (no checksum)
            if addr_without_prefix.islower():
                return True, None

            # Validate EIP-55 checksum
            return self._validate_eip55_checksum(address)

        except Exception as e:
            logger.error(f"Ethereum address validation error: {str(e)}")
            return False, f"Validation error: {str(e)}"

    def _validate_eip55_checksum(self, address: str) -> Tuple[bool, Optional[str]]:
        """
        Validate EIP-55 checksum for Ethereum address.

        Args:
            address: Ethereum address with checksum

        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        try:
            # Remove 0x prefix and convert to lowercase
            addr_without_prefix = address[2:].lower()
            address_hash = hashlib.sha256(addr_without_prefix.encode()).hexdigest()

            # Apply checksum rules
            checksum_address = "0x"
            for i, char in enumerate(addr_without_prefix):
                # Get the i'th character of the hash
                hash_char = address_hash[i]
                if int(hash_char, 16) >= 8:
                    # Uppercase if the corresponding hash character is 8 or higher
                    checksum_address += char.upper()
                else:
                    checksum_address += char

            # Compare with original address
            if checksum_address == address.lower():
                return True, None
            else:
                return False, "Invalid EIP-55 checksum"

        except Exception as e:
            return False, f"EIP-55 checksum validation failed: {str(e)}"

    def get_network(self) -> str:
        """Get the network name."""
        return "ethereum"


class PolygonAddressValidator(EthereumAddressValidator):
    """Validator for Polygon addresses (same format as Ethereum)."""

    def get_network(self) -> str:
        """Get the network name."""
        return "polygon"


class BSCAddressValidator(EthereumAddressValidator):
    """Validator for BSC addresses (same format as Ethereum)."""

    def get_network(self) -> str:
        """Get the network name."""
        return "bsc"


class ArbitrumAddressValidator(EthereumAddressValidator):
    """Validator for Arbitrum addresses (same format as Ethereum)."""

    def get_network(self) -> str:
        """Get the network name."""
        return "arbitrum"


class OptimismAddressValidator(EthereumAddressValidator):
    """Validator for Optimism addresses (same format as Ethereum)."""

    def get_network(self) -> str:
        """Get the network name."""
        return "optimism"


class CryptoAddressValidator:
    """
    Main address validator that routes to specific network validators.

    Supports Bitcoin, Ethereum, and EVM-compatible chains.
    """

    def __init__(self):
        """Initialize validators for different networks."""
        self.validators = {
            'bitcoin': BitcoinAddressValidator(),
            'ethereum': EthereumAddressValidator(),
            'polygon': PolygonAddressValidator(),
            'bsc': BSCAddressValidator(),
            'arbitrum': ArbitrumAddressValidator(),
            'optimism': OptimismAddressValidator(),
        }

    def validate_address(self, address: str, network: str) -> Tuple[bool, Optional[str]]:
        """
        Validate an address for a specific network.

        Args:
            address: The address to validate
            network: The blockchain network

        Returns:
            Tuple[bool, Optional[str]]: (is_valid, error_message)
        """
        if not address or not address.strip():
            return False, "Address cannot be empty"

        network = network.lower()
        if network not in self.validators:
            return False, f"Unsupported network: {network}"

        validator = self.validators[network]
        return validator.validate(address)

    def get_address_info(self, address: str, network: str) -> Dict[str, Any]:
        """
        Get detailed information about an address.

        Args:
            address: The address to analyze
            network: The blockchain network

        Returns:
            Dict[str, Any]: Address information
        """
        is_valid, error_message = self.validate_address(address, network)

        info = {
            'address': address,
            'network': network,
            'is_valid': is_valid,
            'error_message': error_message,
            'address_type': None,
            'checksum_valid': None,
        }

        if is_valid:
            # Determine address type
            if network == 'bitcoin':
                if BITCOIN_P2PKH_PATTERN.match(address):
                    info['address_type'] = 'P2PKH (Legacy)'
                elif BITCOIN_P2SH_PATTERN.match(address):
                    info['address_type'] = 'P2SH (Multisig)'
                elif BITCOIN_BECH32_PATTERN.match(address):
                    info['address_type'] = 'Bech32 (Native Segwit)'
            elif network in ['ethereum', 'polygon', 'bsc', 'arbitrum', 'optimism']:
                info['address_type'] = 'EVM Address'
                # Check if checksum is applied
                if address != address.lower():
                    validator = self.validators[network]
                    checksum_valid, _ = validator.validate(address)
                    info['checksum_valid'] = checksum_valid

        return info

    def detect_possible_networks(self, address: str) -> Dict[str, Any]:
        """
        Detect possible networks for an address format.

        Args:
            address: The address to analyze

        Returns:
            Dict[str, Any]: Possible networks and validation results
        """
        results = {
            'address': address,
            'possible_networks': {},
            'definite_network': None,
        }

        for network, validator in self.validators.items():
            is_valid, error_message = validator.validate(address)
            if is_valid:
                results['possible_networks'][network] = {
                    'is_valid': True,
                    'error_message': None
                }
                # If only one network matches, it's the definite network
                if len(results['possible_networks']) == 1:
                    results['definite_network'] = network

        return results

    def sanitize_address(self, address: str) -> str:
        """
        Sanitize and normalize an address.

        Args:
            address: The address to sanitize

        Returns:
            str: Sanitized address
        """
        if not address:
            return ""

        # Remove whitespace and convert to consistent case
        sanitized = address.strip()

        # For Ethereum/EVM addresses, ensure 0x prefix
        if re.match(r'^[a-fA-F0-9]{40}$', sanitized):
            sanitized = f"0x{sanitized}"

        return sanitized


# Global address validator instance
address_validator = CryptoAddressValidator()