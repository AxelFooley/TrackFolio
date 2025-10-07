"""
Security Service - Provides encryption/decryption operations for sensitive data.

Implements AES-256-GCM encryption with PBKDF2 key derivation for secure
handling of crypto wallet credentials and sensitive data.
"""

import os
import json
import hashlib
import secrets
import logging
from base64 import b64encode, b64decode
from typing import Any, Dict, Optional, Tuple, Union

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidTag

from app.config import settings

logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """Custom exception for security-related errors."""
    pass


class SecurityService:
    """
    Provides encryption/decryption services for sensitive wallet data.

    Uses AES-256-GCM with PBKDF2 key derivation for secure encryption
    of wallet credentials and other sensitive information.
    """

    # Constants for encryption
    ALGORITHM = "AES-256-GCM"
    KEY_SIZE = 32  # 256 bits
    SALT_SIZE = 16  # 128 bits
    NONCE_SIZE = 12  # 96 bits for GCM
    PBKDF2_ITERATIONS = 100000

    def __init__(self):
        """Initialize the security service."""
        self._encryption_key: Optional[bytes] = None

    @property
    def encryption_key(self) -> bytes:
        """
        Get or derive the encryption key from environment settings.

        Returns:
            bytes: 32-byte encryption key

        Raises:
            SecurityError: If encryption key is not properly configured
        """
        if self._encryption_key is None:
            self._encryption_key = self._derive_encryption_key()
        return self._encryption_key

    def _derive_encryption_key(self) -> bytes:
        """
        Derive encryption key from environment variable using PBKDF2.

        Returns:
            bytes: 32-byte derived key

        Raises:
            SecurityError: If ENCRYPTION_KEY is not set or invalid
        """
        encryption_key_base = getattr(settings, 'encryption_key', None)

        if not encryption_key_base:
            raise SecurityError(
                "ENCRYPTION_KEY environment variable is required for wallet security"
            )

        # In production, use a fixed salt for key derivation from environment
        # In development, we can use a different approach
        if settings.environment == "production":
            # Use a deterministic salt for production to maintain key consistency
            # across restarts while still providing good security
            salt = hashlib.sha256(encryption_key_base.encode()).digest()[:self.SALT_SIZE]
        else:
            # In development, use a simple approach but warn about security
            salt = b"development_salt_123"
            logger.warning(
                "Using development encryption key. "
                "This is NOT secure for production use!"
            )

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.KEY_SIZE,
            salt=salt,
            iterations=self.PBKDF2_ITERATIONS,
        )

        return kdf.derive(encryption_key_base.encode())

    def encrypt(self, data: Union[str, Dict[str, Any]]) -> str:
        """
        Encrypt sensitive data using AES-256-GCM.

        Args:
            data: String or dictionary to encrypt

        Returns:
            str: Base64-encoded encrypted data with salt and nonce

        Raises:
            SecurityError: If encryption fails
        """
        try:
            # Convert data to JSON string if it's a dictionary
            if isinstance(data, dict):
                data_str = json.dumps(data, separators=(',', ':'), sort_keys=True)
            else:
                data_str = str(data)

            # Convert to bytes
            data_bytes = data_str.encode('utf-8')

            # Generate random salt and nonce
            salt = os.urandom(self.SALT_SIZE)
            nonce = os.urandom(self.NONCE_SIZE)

            # Derive key using the salt
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=self.KEY_SIZE,
                salt=salt,
                iterations=self.PBKDF2_ITERATIONS,
            )
            key = kdf.derive(self.encryption_key)

            # Encrypt the data
            aesgcm = AESGCM(key)
            encrypted_data = aesgcm.encrypt(nonce, data_bytes, None)

            # Combine salt + nonce + encrypted data and encode as base64
            combined = salt + nonce + encrypted_data
            encrypted_b64 = b64encode(combined).decode('utf-8')

            logger.debug(f"Data encrypted successfully, length: {len(data_bytes)}")
            return encrypted_b64

        except Exception as e:
            logger.error(f"Encryption failed: {str(e)}")
            raise SecurityError(f"Failed to encrypt sensitive data: {str(e)}")

    def decrypt(self, encrypted_data: str) -> Union[str, Dict[str, Any]]:
        """
        Decrypt sensitive data using AES-256-GCM.

        Args:
            encrypted_data: Base64-encoded encrypted data with salt and nonce

        Returns:
            Union[str, Dict[str, Any]]: Decrypted data as string or parsed JSON

        Raises:
            SecurityError: If decryption fails or data is tampered
        """
        try:
            # Decode base64
            combined = b64decode(encrypted_data.encode('utf-8'))

            # Extract salt, nonce, and encrypted data
            salt = combined[:self.SALT_SIZE]
            nonce = combined[self.SALT_SIZE:self.SALT_SIZE + self.NONCE_SIZE]
            ciphertext = combined[self.SALT_SIZE + self.NONCE_SIZE:]

            # Derive key using the salt
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=self.KEY_SIZE,
                salt=salt,
                iterations=self.PBKDF2_ITERATIONS,
            )
            key = kdf.derive(self.encryption_key)

            # Decrypt the data
            aesgcm = AESGCM(key)
            decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)

            # Convert to string
            decrypted_str = decrypted_bytes.decode('utf-8')

            # Try to parse as JSON, fallback to string
            try:
                return json.loads(decrypted_str)
            except json.JSONDecodeError:
                return decrypted_str

        except InvalidTag:
            logger.error("Decryption failed: Invalid authentication tag (data may be tampered)")
            raise SecurityError("Failed to decrypt data: Invalid authentication tag")
        except Exception as e:
            logger.error(f"Decryption failed: {str(e)}")
            raise SecurityError(f"Failed to decrypt sensitive data: {str(e)}")

    def hash_address(self, address: str) -> str:
        """
        Hash a blockchain address for validation purposes.

        Args:
            address: Blockchain address to hash

        Returns:
            str: SHA-256 hash of the address
        """
        return hashlib.sha256(address.strip().lower().encode('utf-8')).hexdigest()

    def generate_secure_token(self, length: int = 32) -> str:
        """
        Generate a cryptographically secure random token.

        Args:
            length: Length of the token in bytes

        Returns:
            str: Hex-encoded secure token
        """
        return secrets.token_hex(length)

    def mask_sensitive_data(self, data: str, visible_chars: int = 4) -> str:
        """
        Mask sensitive data for logging purposes.

        Args:
            data: Sensitive data to mask
            visible_chars: Number of characters to keep visible at start and end

        Returns:
            str: Masked data (e.g., "a***b" for "abcdef")
        """
        if not data or len(data) <= visible_chars * 2:
            return "*" * len(data)

        start = data[:visible_chars]
        end = data[-visible_chars:] if len(data) > visible_chars else ""
        middle = "*" * (len(data) - visible_chars * 2)

        return f"{start}{middle}{end}"

    def validate_encryption_setup(self) -> Dict[str, Any]:
        """
        Validate that encryption is properly configured.

        Returns:
            Dict[str, Any]: Validation results
        """
        results = {
            "valid": False,
            "encryption_configured": False,
            "test_encryption_passed": False,
            "environment": settings.environment,
            "errors": []
        }

        try:
            # Check if encryption key is configured
            encryption_key = getattr(settings, 'encryption_key', None)
            if not encryption_key:
                results["errors"].append("ENCRYPTION_KEY environment variable not set")
            else:
                results["encryption_configured"] = True

            # Test encryption/decryption
            test_data = "test_encryption_validation"
            try:
                encrypted = self.encrypt(test_data)
                decrypted = self.decrypt(encrypted)

                if decrypted == test_data:
                    results["test_encryption_passed"] = True
                else:
                    results["errors"].append("Test encryption/decryption failed: data mismatch")
            except Exception as e:
                results["errors"].append(f"Test encryption failed: {str(e)}")

            # Overall validation
            results["valid"] = (
                results["encryption_configured"] and
                results["test_encryption_passed"]
            )

            if results["valid"]:
                logger.info("Security service validation passed")
            else:
                logger.error(f"Security service validation failed: {results['errors']}")

        except Exception as e:
            results["errors"].append(f"Validation error: {str(e)}")
            logger.error(f"Security validation error: {str(e)}")

        return results

    def prepare_for_key_rotation(self) -> Dict[str, Any]:
        """
        Prepare data for future key rotation operations.

        Returns:
            Dict[str, Any]: Key rotation preparation status
        """
        return {
            "current_key_version": 1,
            "supported_versions": [1],
            "rotation_ready": True,
            "note": "Key rotation functionality will be implemented in future versions"
        }


# Global security service instance
security_service = SecurityService()