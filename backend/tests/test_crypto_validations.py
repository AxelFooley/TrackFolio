"""
Unit tests for Crypto Address Validation Utilities.

Tests address validation for Bitcoin, Ethereum, and EVM-compatible chains.
"""

import pytest
from app.utils.crypto_validations import (
    BitcoinAddressValidator,
    EthereumAddressValidator,
    PolygonAddressValidator,
    BSCAddressValidator,
    ArbitrumAddressValidator,
    OptimismAddressValidator,
    CryptoAddressValidator,
    ValidationError
)


class TestBitcoinAddressValidator:
    """Test cases for Bitcoin address validation."""

    @pytest.fixture
    def validator(self):
        """Create BitcoinAddressValidator instance."""
        return BitcoinAddressValidator()

    def test_valid_p2pkh_addresses(self, validator):
        """Test validation of valid P2PKH (legacy) addresses."""
        valid_addresses = [
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",  # Satoshi's address
            "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2",  # Example from Bitcoin.org
            "17VZNX1SN5NtKa8UQFxwVbBjFtDgVt4jU6",  # Random valid
        ]

        for address in valid_addresses:
            is_valid, error = validator.validate(address)
            assert is_valid, f"Address {address} should be valid"
            assert error is None

    def test_valid_p2sh_addresses(self, validator):
        """Test validation of valid P2SH (multisig) addresses."""
        valid_addresses = [
            "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy",  # Example from Bitcoin.org
            "3P14159f73E4gFr7JterCCQh9QjiTjiZrG",  # Pi address
        ]

        for address in valid_addresses:
            is_valid, error = validator.validate(address)
            assert is_valid, f"Address {address} should be valid"
            assert error is None

    def test_valid_bech32_addresses(self, validator):
        """Test validation of valid Bech32 (native segwit) addresses."""
        valid_addresses = [
            "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq",  # Example from Bitcoin.org
            "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4",  # Another example
        ]

        for address in valid_addresses:
            is_valid, error = validator.validate(address)
            assert is_valid, f"Address {address} should be valid"
            assert error is None

    def test_invalid_addresses(self, validator):
        """Test validation of invalid addresses."""
        invalid_addresses = [
            "",  # Empty
            "invalid",  # Invalid format
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfN",  # Too short
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNaX",  # Too long
            "2A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",  # Invalid prefix
            "bc1_invalid_address",  # Invalid bech32
            "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdqX",  # Too long
        ]

        for address in invalid_addresses:
            is_valid, error = validator.validate(address)
            assert not is_valid, f"Address {address} should be invalid"
            assert error is not None

    def test_network_name(self, validator):
        """Test network name retrieval."""
        assert validator.get_network() == "bitcoin"

    def test_address_case_sensitivity(self, validator):
        """Test that address validation is case-insensitive."""
        address_lower = "1a1zp1ep5qgef2dmptftl5slmv7divfna"
        address_upper = "1A1ZP1EP5QGEF2DMPTFTL5SLMV7DIVFNA"
        address_mixed = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"

        is_valid_lower, _ = validator.validate(address_lower)
        is_valid_upper, _ = validator.validate(address_upper)
        is_valid_mixed, _ = validator.validate(address_mixed)

        # All should be valid (Bitcoin addresses are case-insensitive)
        assert is_valid_lower
        assert is_valid_upper
        assert is_valid_mixed


class TestEthereumAddressValidator:
    """Test cases for Ethereum address validation."""

    @pytest.fixture
    def validator(self):
        """Create EthereumAddressValidator instance."""
        return EthereumAddressValidator()

    def test_valid_ethereum_addresses(self, validator):
        """Test validation of valid Ethereum addresses."""
        valid_addresses = [
            "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb9",  # Example with checksum
            "0x0000000000000000000000000000000000000000",  # Zero address
            "0x742d35cc6634c0532925a3b844bc9e7595f0beb9",  # All lowercase
        ]

        for address in valid_addresses:
            is_valid, error = validator.validate(address)
            assert is_valid, f"Address {address} should be valid"
            assert error is None

    def test_invalid_ethereum_addresses(self, validator):
        """Test validation of invalid Ethereum addresses."""
        invalid_addresses = [
            "",  # Empty
            "0x",  # Just prefix
            "742d35Cc6634C0532925a3b844Bc9e7595f0bEb9",  # Missing 0x
            "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",  # Too short
            "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb9X",  # Too long
            "0xG42d35Cc6634C0532925a3b844Bc9e7595f0bEb9",  # Invalid character
            "invalid",  # Invalid format
        ]

        for address in invalid_addresses:
            is_valid, error = validator.validate(address)
            assert not is_valid, f"Address {address} should be invalid"
            assert error is not None

    def test_eip55_checksum_validation(self, validator):
        """Test EIP-55 checksum validation."""
        # Valid checksum address
        checksum_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb9"
        is_valid, _ = validator.validate(checksum_address)
        assert is_valid

        # Invalid checksum (same address, wrong case)
        invalid_checksum = "0x742d35cc6634c0532925a3b844bc9e7595f0beb9"
        is_valid, _ = validator.validate(invalid_checksum)
        assert is_valid  # Still valid as lowercase

        # Wrong checksum (mixed case incorrectly)
        wrong_checksum = "0x742D35Cc6634C0532925a3b844Bc9e7595f0bEb9"
        is_valid, error = validator.validate(wrong_checksum)
        assert not is_valid
        assert "Invalid EIP-55 checksum" in error

    def test_network_name(self, validator):
        """Test network name retrieval."""
        assert validator.get_network() == "ethereum"


class TestEVMCompatibleValidators:
    """Test cases for EVM-compatible chain validators."""

    @pytest.mark.parametrize("validator_class,network_name", [
        (PolygonAddressValidator, "polygon"),
        (BSCAddressValidator, "bsc"),
        (ArbitrumAddressValidator, "arbitrum"),
        (OptimismAddressValidator, "optimism"),
    ])
    def test_evm_validator_inheritance(self, validator_class, network_name):
        """Test that EVM validators inherit from EthereumAddressValidator."""
        validator = validator_class()

        # Should inherit validation logic
        valid_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb9"
        is_valid, _ = validator.validate(valid_address)
        assert is_valid

        # Should have correct network name
        assert validator.get_network() == network_name

    def test_ethereum_vs_polygon_compatibility(self):
        """Test that Ethereum and Polygon validators are compatible."""
        eth_validator = EthereumAddressValidator()
        polygon_validator = PolygonAddressValidator()

        test_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb9"

        eth_valid, _ = eth_validator.validate(test_address)
        polygon_valid, _ = polygon_validator.validate(test_address)

        assert eth_valid == polygon_valid


class TestCryptoAddressValidator:
    """Test cases for the main CryptoAddressValidator."""

    @pytest.fixture
    def validator(self):
        """Create CryptoAddressValidator instance."""
        return CryptoAddressValidator()

    def test_validate_bitcoin_address(self, validator):
        """Test Bitcoin address validation through main validator."""
        address = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        is_valid, error = validator.validate_address(address, "bitcoin")

        assert is_valid
        assert error is None

    def test_validate_ethereum_address(self, validator):
        """Test Ethereum address validation through main validator."""
        address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb9"
        is_valid, error = validator.validate_address(address, "ethereum")

        assert is_valid
        assert error is None

    def test_validate_polygon_address(self, validator):
        """Test Polygon address validation through main validator."""
        address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb9"
        is_valid, error = validator.validate_address(address, "polygon")

        assert is_valid
        assert error is None

    def test_unsupported_network(self, validator):
        """Test validation with unsupported network."""
        address = "some_address"
        is_valid, error = validator.validate_address(address, "unsupported_network")

        assert not is_valid
        assert "Unsupported network" in error

    def test_empty_address(self, validator):
        """Test validation with empty address."""
        is_valid, error = validator.validate_address("", "bitcoin")

        assert not is_valid
        assert "Address cannot be empty" in error

    def test_get_address_info_bitcoin(self, validator):
        """Test address information for Bitcoin addresses."""
        # P2PKH address
        address = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        info = validator.get_address_info(address, "bitcoin")

        assert info["address"] == address
        assert info["network"] == "bitcoin"
        assert info["is_valid"] is True
        assert info["error_message"] is None
        assert info["address_type"] == "P2PKH (Legacy)"

        # P2SH address
        p2sh_address = "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy"
        info = validator.get_address_info(p2sh_address, "bitcoin")
        assert info["address_type"] == "P2SH (Multisig)"

        # Bech32 address
        bech32_address = "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq"
        info = validator.get_address_info(bech32_address, "bitcoin")
        assert info["address_type"] == "Bech32 (Native Segwit)"

    def test_get_address_info_ethereum(self, validator):
        """Test address information for Ethereum addresses."""
        # Checksum address
        address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb9"
        info = validator.get_address_info(address, "ethereum")

        assert info["address"] == address
        assert info["network"] == "ethereum"
        assert info["is_valid"] is True
        assert info["error_message"] is None
        assert info["address_type"] == "EVM Address"
        assert info["checksum_valid"] is True

        # Lowercase address
        lowercase_address = "0x742d35cc6634c0532925a3b844bc9e7595f0beb9"
        info = validator.get_address_info(lowercase_address, "ethereum")
        assert info["checksum_valid"] is None  # No checksum to validate

    def test_get_address_info_invalid(self, validator):
        """Test address information for invalid addresses."""
        address = "invalid_address"
        info = validator.get_address_info(address, "bitcoin")

        assert info["address"] == address
        assert info["network"] == "bitcoin"
        assert info["is_valid"] is False
        assert info["error_message"] is not None
        assert info["address_type"] is None

    def test_detect_possible_networks_bitcoin(self, validator):
        """Test network detection for Bitcoin address."""
        # Bitcoin P2PKH should only match Bitcoin
        address = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        results = validator.detect_possible_networks(address)

        assert "bitcoin" in results["possible_networks"]
        assert results["possible_networks"]["bitcoin"]["is_valid"] is True
        assert results["definite_network"] == "bitcoin"

    def test_detect_possible_networks_ethereum(self, validator):
        """Test network detection for Ethereum address."""
        # Ethereum address should match all EVM chains
        address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb9"
        results = validator.detect_possible_networks(address)

        expected_networks = ["ethereum", "polygon", "bsc", "arbitrum", "optimism"]
        for network in expected_networks:
            assert network in results["possible_networks"]
            assert results["possible_networks"][network]["is_valid"] is True

        # Should not have definite network (multiple matches)
        assert results["definite_network"] is None

    def test_detect_possible_networks_invalid(self, validator):
        """Test network detection for invalid address."""
        address = "invalid_address"
        results = validator.detect_possible_networks(address)

        assert len(results["possible_networks"]) == 0
        assert results["definite_network"] is None

    def test_sanitize_address(self, validator):
        """Test address sanitization."""
        # Test with whitespace
        assert validator.sanitize_address("  0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb9  ") == \
               "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb9"

        # Test Ethereum address without 0x
        assert validator.sanitize_address("742d35Cc6634C0532925a3b844Bc9e7595f0bEb9") == \
               "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb9"

        # Test empty address
        assert validator.sanitize_address("") == ""

        # Test None address
        assert validator.sanitize_address(None) == ""

        # Test Bitcoin address (should remain unchanged)
        bitcoin_address = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        assert validator.sanitize_address(bitcoin_address) == bitcoin_address

    def test_network_case_sensitivity(self, validator):
        """Test that network names are case-insensitive."""
        address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb9"

        # Test different cases
        for network in ["ethereum", "ETHEREUM", "Ethereum", "ETHereum"]:
            is_valid, _ = validator.validate_address(address, network)
            assert is_valid, f"Network {network} should be case-insensitive"