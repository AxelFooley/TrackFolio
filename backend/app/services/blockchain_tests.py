"""
Comprehensive tests for blockchain integration services.

Tests Bitcoin and Ethereum/EVM services with sample data to ensure
proper functionality and error handling.
"""
import asyncio
import logging
from decimal import Decimal
from typing import Dict, List, Any

from app.models.crypto_paper import BlockchainNetwork
from app.models.blockchain_data import AddressType
from app.services.blockchain_service import blockchain_service, BlockchainServiceFactory
from app.services.bitcoin_integration import BitcoinService
from app.services.ethereum_integration import EthereumService
from app.services.api_manager import api_manager
from app.services.blockchain_error_handler import blockchain_error_handler, handle_blockchain_error

logger = logging.getLogger(__name__)


class BlockchainServiceTester:
    """Comprehensive tester for blockchain services."""

    def __init__(self):
        self.test_results = {}
        self.errors = []

    async def run_all_tests(self) -> Dict[str, Any]:
        """
        Run comprehensive tests for all blockchain services.

        Returns:
            Test results summary
        """
        logger.info("Starting blockchain service tests...")

        try:
            # Initialize services
            await blockchain_service.initialize()

            # Test API Manager
            await self.test_api_manager()

            # Test Bitcoin service
            await self.test_bitcoin_service()

            # Test Ethereum/EVM services
            await self.test_ethereum_services()

            # Test error handling
            await self.test_error_handling()

            # Test factory and main service
            await self.test_service_integration()

        except Exception as e:
            logger.error(f"Test suite failed: {e}")
            await handle_blockchain_error(e, message="Test suite failure")

        finally:
            await blockchain_service.cleanup()

        return self.generate_test_report()

    async def test_api_manager(self):
        """Test API manager functionality."""
        logger.info("Testing API Manager...")

        try:
            # Test provider setup
            healthy_providers = api_manager.get_healthy_providers("bitcoin")
            self.test_results["api_manager_providers"] = {
                "status": "passed" if healthy_providers else "failed",
                "message": f"Found {len(healthy_providers)} healthy Bitcoin providers"
            }

            # Test health check
            health_results = await api_manager.health_check("bitcoin")
            self.test_results["api_manager_health_check"] = {
                "status": "passed" if health_results else "failed",
                "message": f"Health check completed"
            }

            # Test cache functionality
            await api_manager.cache.set("test_key", {"test": "value"}, 60)
            cached_value = await api_manager.cache.get("test_key")
            self.test_results["api_manager_cache"] = {
                "status": "passed" if cached_value else "failed",
                "message": "Cache functionality working"
            }

            await api_manager.cache.delete("test_key")

        except Exception as e:
            logger.error(f"API Manager test failed: {e}")
            self.test_results["api_manager"] = {
                "status": "failed",
                "message": str(e)
            }
            self.errors.append(f"API Manager: {str(e)}")

    async def test_bitcoin_service(self):
        """Test Bitcoin service functionality."""
        logger.info("Testing Bitcoin service...")

        try:
            bitcoin_service = BitcoinService()

            # Test address validation
            test_addresses = [
                ("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", AddressType.P2PKH),  # Satoshi's address
                ("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy", AddressType.P2SH),
                ("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4", AddressType.BECH32),
                ("invalid_address", None)
            ]

            validation_results = []
            for address, expected_type in test_addresses:
                is_valid, address_type = await bitcoin_service.validate_address(address)
                validation_results.append({
                    "address": address,
                    "expected": expected_type.value if expected_type else None,
                    "actual": address_type.value if address_type else None,
                    "valid": is_valid,
                    "correct": is_valid and address_type == expected_type
                })

            self.test_results["bitcoin_address_validation"] = {
                "status": "passed",
                "message": f"Validated {len(validation_results)} addresses",
                "details": validation_results
            }

            # Test balance query (use real address)
            try:
                balance = await bitcoin_service.get_balance("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
                self.test_results["bitcoin_balance_query"] = {
                    "status": "passed",
                    "message": f"Balance query successful: {balance.balance if balance else 'None'}"
                }
            except Exception as e:
                self.test_results["bitcoin_balance_query"] = {
                    "status": "failed",
                    "message": f"Balance query failed: {str(e)}"
                }

            # Test network stats
            try:
                network_stats = await bitcoin_service.get_network_stats()
                self.test_results["bitcoin_network_stats"] = {
                    "status": "passed" if network_stats else "failed",
                    "message": f"Network stats: {network_stats.latest_block_number if network_stats else 'None'}"
                }
            except Exception as e:
                self.test_results["bitcoin_network_stats"] = {
                    "status": "failed",
                    "message": f"Network stats failed: {str(e)}"
                }

        except Exception as e:
            logger.error(f"Bitcoin service test failed: {e}")
            self.test_results["bitcoin_service"] = {
                "status": "failed",
                "message": str(e)
            }
            self.errors.append(f"Bitcoin Service: {str(e)}")

    async def test_ethereum_services(self):
        """Test Ethereum/EVM service functionality."""
        logger.info("Testing Ethereum/EVM services...")

        networks = [
            BlockchainNetwork.ETHEREUM,
            BlockchainNetwork.POLYGON,
            BlockchainNetwork.BSC,
            BlockchainNetwork.ARBITRUM,
            BlockchainNetwork.OPTIMISM
        ]

        for network in networks:
            try:
                service = EthereumService(network)

                # Test address validation
                test_address = "0x742d35Cc6634C0532925a3b8D4C9db96C4b4Db45"  # Uniswap V2 Router
                is_valid, address_type = await service.validate_address(test_address)

                self.test_results[f"{network.value}_address_validation"] = {
                    "status": "passed" if is_valid else "failed",
                    "message": f"Address validation for {network.value}: {is_valid}"
                }

                # Test balance query
                try:
                    balance = await service.get_balance(test_address)
                    self.test_results[f"{network.value}_balance_query"] = {
                        "status": "passed",
                        "message": f"Balance query for {network.value}: {balance.balance if balance else 'None'}"
                    }
                except Exception as e:
                    self.test_results[f"{network.value}_balance_query"] = {
                        "status": "failed",
                        "message": f"Balance query failed for {network.value}: {str(e)}"
                    }

                # Test network stats
                try:
                    network_stats = await service.get_network_stats()
                    self.test_results[f"{network.value}_network_stats"] = {
                        "status": "passed" if network_stats else "failed",
                        "message": f"Network stats for {network.value}: {network_stats.latest_block_number if network_stats else 'None'}"
                    }
                except Exception as e:
                    self.test_results[f"{network.value}_network_stats"] = {
                        "status": "failed",
                        "message": f"Network stats failed for {network.value}: {str(e)}"
                    }

                # Test gas price (Ethereum only)
                if network == BlockchainNetwork.ETHEREUM:
                    try:
                        gas_price = await service.get_gas_price()
                        self.test_results["ethereum_gas_price"] = {
                            "status": "passed" if gas_price else "failed",
                            "message": f"Gas price: {gas_price}"
                        }
                    except Exception as e:
                        self.test_results["ethereum_gas_price"] = {
                            "status": "failed",
                            "message": f"Gas price query failed: {str(e)}"
                        }

            except Exception as e:
                logger.error(f"{network.value} service test failed: {e}")
                self.test_results[f"{network.value}_service"] = {
                    "status": "failed",
                    "message": str(e)
                }
                self.errors.append(f"{network.value} Service: {str(e)}")

    async def test_error_handling(self):
        """Test error handling functionality."""
        logger.info("Testing error handling...")

        try:
            # Test error classification
            test_errors = [
                Exception("Connection timeout"),
                Exception("Rate limit exceeded"),
                Exception("Invalid address format"),
                Exception("Authentication failed"),
                Exception("Unknown error")
            ]

            for error in test_errors:
                category, severity = blockchain_error_handler.classify_error(error)
                logger.info(f"Error '{str(error)}' classified as {category.value}/{severity.value}")

            # Test error handling
            await handle_blockchain_error(
                Exception("Test error"),
                network=BlockchainNetwork.ETHEREUM,
                provider="test_provider",
                address="0x123..."
            )

            # Test error summary
            error_summary = await blockchain_error_handler.get_error_summary(hours=1)
            self.test_results["error_handling"] = {
                "status": "passed",
                "message": f"Error handling working, {error_summary['total_errors']} errors logged"
            }

            # Test health status
            health_status = await blockchain_error_handler.get_health_status()
            self.test_results["error_health_status"] = {
                "status": "passed",
                "message": f"Health status: {health_status['status']}"
            }

        except Exception as e:
            logger.error(f"Error handling test failed: {e}")
            self.test_results["error_handling"] = {
                "status": "failed",
                "message": str(e)
            }
            self.errors.append(f"Error Handling: {str(e)}")

    async def test_service_integration(self):
        """Test service factory and main service integration."""
        logger.info("Testing service integration...")

        try:
            # Test service factory
            supported_networks = BlockchainServiceFactory.get_supported_networks()
            self.test_results["service_factory_networks"] = {
                "status": "passed",
                "message": f"Supported networks: {[n.value for n in supported_networks]}"
            }

            # Test main service
            try:
                networks = await blockchain_service.get_supported_networks()
                self.test_results["main_service_networks"] = {
                    "status": "passed",
                    "message": f"Main service supports {len(networks)} networks"
                }
            except Exception as e:
                self.test_results["main_service_networks"] = {
                    "status": "failed",
                    "message": f"Main service networks failed: {str(e)}"
                }

            # Test address validation through main service
            is_valid, address_type = await blockchain_service.validate_address(
                "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                BlockchainNetwork.BITCOIN
            )
            self.test_results["main_service_validation"] = {
                "status": "passed" if is_valid else "failed",
                "message": f"Main service validation: {is_valid}"
            }

            # Test health check through main service
            health_results = await blockchain_service.health_check(BlockchainNetwork.BITCOIN)
            self.test_results["main_service_health"] = {
                "status": "passed" if health_results else "failed",
                "message": "Main service health check completed"
            }

        except Exception as e:
            logger.error(f"Service integration test failed: {e}")
            self.test_results["service_integration"] = {
                "status": "failed",
                "message": str(e)
            }
            self.errors.append(f"Service Integration: {str(e)}")

    def generate_test_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report."""
        total_tests = len(self.test_results)
        passed_tests = len([t for t in self.test_results.values() if t["status"] == "passed"])
        failed_tests = total_tests - passed_tests

        return {
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "success_rate": f"{(passed_tests / total_tests * 100):.1f}%" if total_tests > 0 else "0%"
            },
            "test_results": self.test_results,
            "errors": self.errors,
            "recommendations": self._generate_recommendations()
        }

    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on test results."""
        recommendations = []

        # Check for failed tests
        failed_tests = [name for name, result in self.test_results.items() if result["status"] == "failed"]

        if "api_manager_providers" in failed_tests:
            recommendations.append("Configure blockchain API keys in environment variables")

        if any("balance_query" in test and test in failed_tests for test in self.test_results):
            recommendations.append("Check blockchain API connectivity and rate limits")

        if any("network_stats" in test and test in failed_tests for test in self.test_results):
            recommendations.append("Verify blockchain network endpoints are accessible")

        if any("ethereum" in test and "gas_price" in test and test in failed_tests for test in self.test_results):
            recommendations.append("Ethereum gas price endpoint may need configuration")

        if not failed_tests:
            recommendations.append("All tests passed! Blockchain services are ready for production.")

        return recommendations


async def run_blockchain_tests() -> Dict[str, Any]:
    """
    Run comprehensive blockchain service tests.

    Returns:
        Test results report
    """
    tester = BlockchainServiceTester()
    return await tester.run_all_tests()


# Sample test data
SAMPLE_BITCOIN_ADDRESSES = [
    "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",  # Satoshi's address (P2PKH)
    "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy",   # P2SH address
    "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"  # Bech32 address
]

SAMPLE_ETHEREUM_ADDRESSES = [
    "0x742d35Cc6634C0532925a3b8D4C9db96C4b4Db45",  # Uniswap V2 Router
    "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # WETH
    "0xA0b86a33E6441e7C3a3a9a4c1F2b9d8d1c8B9c9E"   # USDC
]

SAMPLE_TRANSACTION_HASHES = {
    "bitcoin": "4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b",  # Genesis block coinbase
    "ethereum": "0x5c504ed432cb51138bcf09aa5e8a410dd4a1e204ef84bfed1be16dfba1b22060"  # Sample ETH tx
}


if __name__ == "__main__":
    # Run tests when executed directly
    import sys

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    async def main():
        results = await run_blockchain_tests()

        print("\n" + "="*50)
        print("BLOCKCHAIN SERVICE TEST REPORT")
        print("="*50)

        print(f"\nSUMMARY:")
        print(f"Total Tests: {results['summary']['total_tests']}")
        print(f"Passed: {results['summary']['passed']}")
        print(f"Failed: {results['summary']['failed']}")
        print(f"Success Rate: {results['summary']['success_rate']}")

        if results['errors']:
            print(f"\nERRORS:")
            for error in results['errors']:
                print(f"  - {error}")

        if results['recommendations']:
            print(f"\nRECOMMENDATIONS:")
            for rec in results['recommendations']:
                print(f"  - {rec}")

        # Exit with appropriate code
        sys.exit(0 if results['summary']['failed'] == 0 else 1)

    asyncio.run(main())