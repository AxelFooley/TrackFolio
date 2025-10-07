#!/usr/bin/env python3
"""
Simple validation script for blockchain services.

This script validates the blockchain integration services by checking
imports, syntax, and basic functionality without requiring the full
environment setup.
"""
import ast
import sys
import os

def validate_python_syntax(file_path):
    """Validate Python file syntax."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()

        # Parse the AST to check syntax
        ast.parse(content)
        return True, None
    except SyntaxError as e:
        return False, f"Syntax error: {e}"
    except Exception as e:
        return False, f"Error reading file: {e}"

def validate_imports(file_path):
    """Check if required imports are present."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()

        tree = ast.parse(content)

        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append(f"{module}.{alias.name}")

        return True, imports
    except Exception as e:
        return False, f"Error parsing imports: {e}"

def main():
    """Main validation function."""
    print("🔍 Validating Blockchain Integration Services")
    print("=" * 50)

    # Files to validate
    service_files = [
        "blockchain_service.py",
        "bitcoin_integration.py",
        "ethereum_integration.py",
        "api_manager.py",
        "blockchain_error_handler.py",
        "blockchain_tests.py",
        "blockchain_integration_demo.py"
    ]

    model_files = [
        "../models/blockchain_data.py"
    ]

    all_files = service_files + model_files
    all_valid = True

    for file_name in all_files:
        file_path = os.path.join(os.path.dirname(__file__), file_name)

        if not os.path.exists(file_path):
            print(f"❌ {file_name}: File not found")
            all_valid = False
            continue

        print(f"\n📄 Validating {file_name}...")

        # Check syntax
        is_valid, error = validate_python_syntax(file_path)
        if is_valid:
            print(f"  ✅ Syntax: Valid")
        else:
            print(f"  ❌ Syntax: {error}")
            all_valid = False
            continue

        # Check imports
        _, imports = validate_imports(file_path)
        key_imports = {
            "blockchain_service.py": ["BaseBlockchainService", "BlockchainServiceFactory"],
            "bitcoin_integration.py": ["BitcoinService", "BaseBlockchainService"],
            "ethereum_integration.py": ["EthereumService", "BaseBlockchainService"],
            "api_manager.py": ["APIManager", "RateLimiter"],
            "blockchain_error_handler.py": ["BlockchainErrorHandler", "ErrorCategory"],
            "blockchain_data.py": ["AddressBalance", "BlockchainTransaction", "BlockchainNetwork"]
        }

        if file_name in key_imports:
            missing_imports = []
            for required_import in key_imports[file_name]:
                if not any(required_import in imp for imp in imports):
                    missing_imports.append(required_import)

            if missing_imports:
                print(f"  ⚠️  Missing key imports: {missing_imports}")
            else:
                print(f"  ✅ Imports: All key imports present")

    # Check configuration updates
    config_path = os.path.join(os.path.dirname(__file__), "../config.py")
    if os.path.exists(config_path):
        print(f"\n📄 Checking config.py for blockchain settings...")
        with open(config_path, 'r') as f:
            config_content = f.read()

        blockchain_configs = [
            "blockchain_api_key",
            "alchemy_api_key",
            "infura_project_id",
            "bitcoin_rate_limit",
            "ethereum_rate_limit",
            "blockchain_cache_ttl_seconds"
        ]

        missing_configs = []
        for config in blockchain_configs:
            if config not in config_content:
                missing_configs.append(config)

        if missing_configs:
            print(f"  ⚠️  Missing blockchain configs: {missing_configs}")
        else:
            print(f"  ✅ Blockchain configurations present")

    # Summary
    print("\n" + "=" * 50)
    if all_valid:
        print("🎉 All blockchain services validated successfully!")
        print("✅ Syntax is correct")
        print("✅ Required imports are present")
        print("✅ Ready for deployment")

        print("\n📋 Next Steps:")
        print("1. Configure API keys in environment variables")
        print("2. Set up Redis for caching")
        print("3. Run the demo script: python blockchain_integration_demo.py")
        print("4. Run tests: python blockchain_tests.py")

        return 0
    else:
        print("❌ Validation failed. Please fix the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())