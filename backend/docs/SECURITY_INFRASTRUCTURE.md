# Security Infrastructure Documentation

## Overview

This document describes the comprehensive security infrastructure implemented for crypto wallet data protection in the TrackFolio application. The security system provides AES-256-GCM encryption for sensitive wallet credentials and robust address validation for multiple blockchain networks.

## Components

### 1. Security Service (`app/services/security_service.py`)

The main security service provides encryption/decryption operations using industry-standard cryptographic algorithms.

#### Features:
- **AES-256-GCM Encryption**: Authenticated encryption with Galois/Counter Mode
- **PBKDF2 Key Derivation**: Secure key derivation from environment variables
- **Secure Random Generation**: Cryptographically secure salt and nonce generation
- **Data Masking**: Secure logging without exposing sensitive data
- **Address Hashing**: SHA-256 hashing for address validation
- **Key Rotation Support**: Preparation for future key rotation implementation

#### Key Methods:
- `encrypt(data)`: Encrypt sensitive data (string or dictionary)
- `decrypt(encrypted_data)`: Decrypt encrypted data
- `hash_address(address)`: Generate SHA-256 hash for address validation
- `mask_sensitive_data(data)`: Mask data for secure logging
- `validate_encryption_setup()`: Validate encryption configuration

### 2. Crypto Address Validation (`app/utils/crypto_validations.py`)

Comprehensive address validation support for multiple blockchain networks.

#### Supported Networks:
- **Bitcoin**: P2PKH (legacy), P2SH (multisig), Bech32 (native segwit)
- **Ethereum**: EIP-55 checksum validation
- **EVM-Compatible**: Polygon, BSC, Arbitrum, Optimism

#### Key Classes:
- `BitcoinAddressValidator`: Validates Bitcoin address formats
- `EthereumAddressValidator`: Validates Ethereum addresses with EIP-55 checksum
- `CryptoAddressValidator`: Main validator routing to network-specific validators

#### Key Methods:
- `validate_address(address, network)`: Validate address for specific network
- `get_address_info(address, network)`: Get detailed address information
- `detect_possible_networks(address)`: Detect possible networks for address format
- `sanitize_address(address)`: Normalize and clean address format

### 3. Security Configuration (`app/config.py`)

Enhanced application configuration with security settings.

#### Security Settings:
- `ENCRYPTION_KEY`: Required encryption key for wallet credentials
- `SECURITY_KEY_ROTATION_DAYS`: Key rotation interval (future feature)
- `WALLET_API_TIMEOUT`: Timeout for wallet API operations
- `MAX_WALLET_CONNECTIONS`: Maximum connections per user
- `RATE_LIMIT_WALLET_API`: Rate limiting for wallet API calls

## Security Best Practices Implemented

### 1. Encryption
- **Algorithm**: AES-256-GCM (Authenticated Encryption)
- **Key Derivation**: PBKDF2 with 100,000 iterations
- **Salt Management**: Unique salt per encryption operation
- **Nonce Generation**: Cryptographically secure random nonces
- **Authentication**: GCM provides integrity verification

### 2. Key Management
- **Environment-based**: Encryption keys stored in environment variables
- **Production vs Development**: Different key derivation strategies
- **Validation**: Built-in key strength validation
- **Rotation Support**: Framework for future key rotation

### 3. Data Protection
- **No Plaintext Storage**: Sensitive data always encrypted at rest
- **Secure Logging**: Automatic masking of sensitive data in logs
- **Memory Safety**: Proper error handling without data leakage
- **Input Validation**: Comprehensive validation of all inputs

### 4. Address Security
- **Format Validation**: Strict validation of address formats
- **Checksum Verification**: EIP-55 checksum validation for Ethereum addresses
- **Network Detection**: Automatic detection of possible networks
- **Hash Verification**: SHA-256 hashing for address validation

## Setup Instructions

### 1. Generate Encryption Key

Use the provided script to generate a secure encryption key:

```bash
cd backend/scripts
python generate_encryption_key.py
```

Or generate manually:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 2. Configure Environment

Add the encryption key to your `.env` file:

```bash
# Security Configuration
ENCRYPTION_KEY=your_generated_encryption_key_here
SECURITY_KEY_ROTATION_DAYS=90
WALLET_API_TIMEOUT=30
MAX_WALLET_CONNECTIONS=10
RATE_LIMIT_WALLET_API=60
```

### 3. Validate Setup

Run the security validation to ensure proper configuration:

```python
from app.services.security_service import security_service

result = security_service.validate_encryption_setup()
if result["valid"]:
    print("Security configuration is valid")
else:
    print("Security configuration errors:", result["errors"])
```

## Usage Examples

### Encrypting Wallet Credentials

```python
from app.services.security_service import security_service

# Prepare wallet credentials
credentials = {
    "api_key": "your_api_key",
    "private_key": "your_private_key",
    "seed_phrase": "your seed phrase words"
}

# Encrypt for storage
encrypted = security_service.encrypt(credentials)

# Store encrypted data in database
wallet_connection.encrypted_credentials = encrypted
```

### Decrypting Wallet Credentials

```python
from app.services.security_service import security_service

# Retrieve encrypted data from database
encrypted = wallet_connection.encrypted_credentials

# Decrypt for use
credentials = security_service.decrypt(encrypted)

# Use credentials
api_key = credentials["api_key"]
```

### Validating Addresses

```python
from app.utils.crypto_validations import address_validator

# Validate Bitcoin address
is_valid, error = address_validator.validate_address(
    "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
    "bitcoin"
)

# Get detailed information
info = address_validator.get_address_info(
    "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb9",
    "ethereum"
)
```

### Masking Sensitive Data

```python
from app.services.security_service import security_service

# Mask for logging
masked_key = security_service.mask_sensitive_data("your_private_key_here")
# Output: "your****here"

# Safe logging with masked data
logger.info(f"Processing wallet with key: {masked_key}")
```

## Security Considerations

### 1. Key Security
- **Never commit encryption keys to version control**
- **Use strong, unique keys (minimum 32 characters)**
- **Rotate keys regularly (recommended: every 90 days)**
- **Store keys securely (environment variables, secret management)**

### 2. Data Handling
- **Always encrypt sensitive data before storage**
- **Use masking for logging sensitive information**
- **Validate all inputs before processing**
- **Handle decryption errors gracefully**

### 3. Address Validation
- **Always validate addresses before storage**
- **Use the provided validation utilities**
- **Store address validation hashes for integrity**
- **Handle validation errors appropriately**

### 4. Operational Security
- **Monitor for security events in logs**
- **Regularly validate encryption configuration**
- **Test backup and restore procedures**
- **Have incident response procedures ready**

## Testing

The security infrastructure includes comprehensive test coverage:

- **Unit Tests**: Individual component testing
- **Integration Tests**: End-to-end security workflows
- **Edge Cases**: Error handling and boundary conditions
- **Performance Tests**: Large data encryption and concurrent operations

Run tests with:

```bash
cd backend
pytest tests/test_security_service.py
pytest tests/test_crypto_validations.py
pytest tests/test_security_integration.py
```

## Future Enhancements

### 1. Key Rotation
- Implement automatic key rotation
- Support for multiple key versions
- Secure re-encryption of existing data

### 2. Hardware Security Module (HSM) Integration
- Integration with cloud HSM services
- Hardware-backed key storage
- Enhanced key protection

### 3. Advanced Encryption
- Support for additional encryption algorithms
- Performance optimization for large datasets
- Compression before encryption

### 4. Audit Logging
- Comprehensive security event logging
- Tamper-evident audit trails
- Security monitoring and alerting

## Troubleshooting

### Common Issues

1. **Encryption Key Not Found**
   - Ensure ENCRYPTION_KEY is set in environment
   - Validate key format and length
   - Check for typos in variable name

2. **Decryption Failures**
   - Verify data hasn't been tampered with
   - Check encryption key consistency
   - Validate data format and integrity

3. **Address Validation Errors**
   - Verify address format for specific network
   - Check for whitespace or special characters
   - Validate network name spelling

### Error Messages

- `"ENCRYPTION_KEY environment variable is required"`: Set encryption key
- `"Invalid authentication tag"`: Data may be tampered or key mismatch
- `"Invalid Bitcoin address format"`: Check address format
- `"Invalid EIP-55 checksum"`: Check Ethereum address checksum

## Support

For security-related issues or questions:

1. Check the test files for usage examples
2. Review the security validation results
3. Consult the application logs for detailed error information
4. Follow the troubleshooting steps above

Remember: Security is everyone's responsibility. Always follow security best practices when handling sensitive data.