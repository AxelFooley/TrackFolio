#!/usr/bin/env python3
"""
Simple schema syntax validation script.

This script checks that all schema files have valid Python syntax
and can be imported without syntax errors.
"""
import sys
import os
import ast
from pathlib import Path

# Compute script directory for absolute paths
script_dir = Path(__file__).resolve().parent

def validate_file_syntax(filepath):
    """Validate Python syntax of a file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Parse the AST to check for syntax errors
        ast.parse(content)
        return True, None
    except SyntaxError as e:
        return False, f"Syntax error: {e}"
    except Exception as e:
        return False, f"Error reading file: {e}"

def main():
    """Validate all schema files."""
    print("🔍 Validating Schema Syntax")
    print("=" * 40)

    # List of schema files to validate
    schema_files = [
        script_dir / "app" / "schemas" / "transaction.py",
        script_dir / "app" / "schemas" / "position.py",
        script_dir / "app" / "schemas" / "price.py",
        script_dir / "app" / "schemas" / "portfolio.py",
        script_dir / "app" / "schemas" / "crypto_validators.py",
        script_dir / "app" / "schemas" / "benchmark.py",
        script_dir / "app" / "schemas" / "__init__.py"
    ]

    all_valid = True

    for schema_file in schema_files:
        print(f"Checking {schema_file}...", end=" ")

        if not schema_file.exists():
            print("❌ File not found")
            all_valid = False
            continue

        is_valid, error = validate_file_syntax(str(schema_file))

        if is_valid:
            print("✅ Valid")
        else:
            print(f"❌ {error}")
            all_valid = False

    print("\n" + "=" * 40)

    if all_valid:
        print("🎉 All schema files have valid syntax!")
        print("\n📋 Enhanced schemas include:")
        print("  • Transaction schemas with crypto validation")
        print("  • Position schemas with crypto support")
        print("  • Price schemas for crypto assets")
        print("  • Portfolio schemas with crypto allocation")
        print("  • Dedicated crypto validation helpers")
        print("  • Comprehensive examples for all schemas")
    else:
        print("❌ Some schema files have syntax errors!")
        sys.exit(1)

if __name__ == "__main__":
    main()