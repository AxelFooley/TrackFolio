#!/usr/bin/env python3
"""
Encryption Key Generation Script

Generate secure encryption keys for wallet credential encryption.
This script should be run once to generate a strong encryption key
that will be used to encrypt sensitive wallet data.
"""

import secrets
import sys
import argparse
from pathlib import Path


def generate_encryption_key(length: int = 32) -> str:
    """
    Generate a cryptographically secure encryption key.

    Args:
        length: Length of the key in bytes

    Returns:
        str: URL-safe base64-encoded encryption key
    """
    return secrets.token_urlsafe(length)


def validate_key_strength(key: str) -> bool:
    """
    Validate the strength of an encryption key.

    Args:
        key: The encryption key to validate

    Returns:
        bool: True if key meets minimum requirements
    """
    if len(key) < 32:
        return False

    # Check for variety of characters
    has_lower = any(c.islower() for c in key)
    has_upper = any(c.isupper() for c in key)
    has_digit = any(c.isdigit() for c in key)
    has_special = any(c in '-_~' for c in key)

    # Require at least 3 of the 4 character types
    variety_score = sum([has_lower, has_upper, has_digit, has_special])
    return variety_score >= 3


def main():
    """Main function to generate and display encryption key."""
    parser = argparse.ArgumentParser(
        description="Generate secure encryption key for wallet credential encryption"
    )
    parser.add_argument(
        "--length",
        type=int,
        default=32,
        help="Length of key in bytes (default: 32)"
    )
    parser.add_argument(
        "--validate",
        type=str,
        help="Validate an existing encryption key"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Write key to specified file"
    )
    parser.add_argument(
        "--env-format",
        action="store_true",
        help="Output in .env format (ENCRYPTION_KEY=...)"
    )

    args = parser.parse_args()

    if args.validate:
        key = args.validate
        if validate_key_strength(key):
            print(f"✅ Key validation passed: Key meets security requirements")
            print(f"   Key length: {len(key)} characters")
        else:
            print(f"❌ Key validation failed: Key does not meet security requirements")
            print(f"   Key length: {len(key)} characters (minimum: 32)")
            print("   Please generate a new key using this script")
            sys.exit(1)
        return

    # Generate new encryption key
    key = generate_encryption_key(args.length)

    # Validate the generated key
    if not validate_key_strength(key):
        print("⚠️  Warning: Generated key may not be strong enough")
        print("   Consider generating a new key with increased length")

    # Prepare output
    if args.env_format:
        output = f"ENCRYPTION_KEY={key}"
    else:
        output = key

    # Display the key
    print("🔐 Generated Encryption Key:")
    print(f"   {output}")
    print()
    print("📋 Security Information:")
    print(f"   Length: {len(key)} characters")
    print(f"   Algorithm: AES-256-GCM with PBKDF2 key derivation")
    print()
    print("⚠️  IMPORTANT SECURITY NOTICE:")
    print("   1. Store this key securely and never commit it to version control")
    print("   2. Add this key to your .env file:")
    print(f"      ENCRYPTION_KEY={key}")
    print("   3. Rotate this key periodically (recommended: every 90 days)")
    print("   4. If you lose this key, encrypted wallet data will be unrecoverable")

    # Write to file if requested
    if args.output:
        try:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'w') as f:
                if args.env_format:
                    f.write(f"# Encryption key for wallet credential encryption\n")
                    f.write(f"# Generated on {secrets.token_hex(8)}\n")
                    f.write(f"{output}\n")
                else:
                    f.write(output)

            print()
            print(f"✅ Key written to: {output_path}")
            print("   Ensure this file has appropriate permissions (600)")

        except Exception as e:
            print(f"❌ Error writing to file: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()