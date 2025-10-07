"""
Blockchain Integration Demo Script.

Demonstrates how to use the blockchain integration services with
real-world examples and test cases.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any

from app.models.crypto_paper import BlockchainNetwork
from app.models.blockchain_data import BatchBalanceRequest
from app.services.blockchain_service import blockchain_service
from app.services.bitcoin_integration import BitcoinService
from app.services.ethereum_integration import EthereumService
from app.services.api_manager import api_manager
from app.services.blockchain_error_handler import blockchain_error_handler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class BlockchainIntegrationDemo:
    """Demonstration of blockchain integration capabilities."""

    def __init__(self):
        self.demo_results = {}

    async def run_demo(self):
        """Run comprehensive demonstration."""
        logger.info("Starting Blockchain Integration Demo...")

        try:
            # Initialize services
            await blockchain_service.initialize()

            # Demo 1: Bitcoin Address Validation and Balance
            await self.demo_bitcoin_integration()

            # Demo 2: Ethereum/EVM Multi-Chain Support
            await self.demo_ethereum_integration()

            # Demo 3: Batch Operations
            await self.demo_batch_operations()

            # Demo 4: Error Handling and Fallbacks
            await self.demo_error_handling()

            # Demo 5: Caching and Performance
            await self.demo_caching_performance()

            # Demo 6: Health Monitoring
            await self.demo_health_monitoring()

        except Exception as e:
            logger.error(f"Demo failed: {e}")
            raise

        finally:
            await blockchain_service.cleanup()

        return self.generate_demo_report()

    async def demo_bitcoin_integration(self):
        """Demonstrate Bitcoin integration capabilities."""
        logger.info("=== Bitcoin Integration Demo ===")

        try:
            bitcoin_service = BitcoinService()

            # Test address validation
            test_addresses = [
                "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",  # Satoshi's address
                "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"  # Bech32 address
            ]

            validation_results = []
            for address in test_addresses:
                is_valid, address_type = await bitcoin_service.validate_address(address)
                validation_results.append({
                    "address": address,
                    "valid": is_valid,
                    "type": address_type.value if address_type else None
                })
                logger.info(f"Address {address[:20]}...: Valid={is_valid}, Type={address_type}")

            self.demo_results["bitcoin_validation"] = validation_results

            # Test balance queries
            balance_results = []
            for address in test_addresses:
                try:
                    balance = await bitcoin_service.get_balance(address)
                    if balance:
                        logger.info(f"Balance for {address[:20]}...: {balance.balance} BTC")
                        balance_results.append({
                            "address": address,
                            "balance": str(balance.balance),
                            "utxo_count": balance.utxo_count
                        })
                except Exception as e:
                    logger.warning(f"Failed to get balance for {address[:20]}...: {e}")

            self.demo_results["bitcoin_balances"] = balance_results

            # Test network statistics
            network_stats = await bitcoin_service.get_network_stats()
            if network_stats:
                logger.info(f"Bitcoin network stats: Block {network_stats.latest_block_number}")
                self.demo_results["bitcoin_network_stats"] = {
                    "latest_block": network_stats.latest_block_number,
                    "provider": network_stats.provider,
                    "response_time_ms": network_stats.response_time_ms
                }

        except Exception as e:
            logger.error(f"Bitcoin demo failed: {e}")
            self.demo_results["bitcoin_error"] = str(e)

    async def demo_ethereum_integration(self):
        """Demonstrate Ethereum/EVM multi-chain integration."""
        logger.info("=== Ethereum/EVM Multi-Chain Demo ===")

        networks = [
            BlockchainNetwork.ETHEREUM,
            BlockchainNetwork.POLYGON,
            BlockchainNetwork.BSC
        ]

        test_address = "0x742d35Cc6634C0532925a3b8D4C9db96C4b4Db45"  # Uniswap V2 Router

        for network in networks:
            try:
                logger.info(f"Testing {network.value} network...")

                service = EthereumService(network)

                # Address validation
                is_valid, address_type = await service.validate_address(test_address)
                logger.info(f"  Address validation: {is_valid}")

                # Balance query
                balance = await service.get_balance(test_address)
                if balance:
                    logger.info(f"  Balance: {balance.balance} {service.network_configs[network]['symbol']}")
                    self.demo_results[f"{network.value}_balance"] = {
                        "balance": str(balance.balance),
                        "symbol": service.network_configs[network]['symbol']
                    }

                # Token balances (if supported)
                if hasattr(service, 'get_balance_with_tokens'):
                    token_balance = await service.get_balance_with_tokens(test_address)
                    if token_balance and token_balance.token_balances:
                        logger.info(f"  Token balances: {len(token_balance.token_balances)} tokens")
                        self.demo_results[f"{network.value}_tokens"] = [
                            {
                                "symbol": token["symbol"],
                                "balance": str(token["balance"])
                            }
                            for token in token_balance.token_balances[:5]  # First 5 tokens
                        ]

                # Network stats
                network_stats = await service.get_network_stats()
                if network_stats:
                    logger.info(f"  Network stats: Block {network_stats.latest_block_number}")
                    self.demo_results[f"{network.value}_stats"] = {
                        "latest_block": network_stats.latest_block_number,
                        "provider": network_stats.provider
                    }

                # Gas price (Ethereum only)
                if network == BlockchainNetwork.ETHEREUM:
                    gas_price = await service.get_gas_price()
                    if gas_price:
                        logger.info(f"  Gas price: {gas_price} Gwei")
                        self.demo_results["ethereum_gas_price"] = str(gas_price)

            except Exception as e:
                logger.error(f"Failed to demo {network.value}: {e}")
                self.demo_results[f"{network.value}_error"] = str(e)

    async def demo_batch_operations(self):
        """Demonstrate batch operations capabilities."""
        logger.info("=== Batch Operations Demo ===")

        try:
            # Bitcoin batch balance query
            bitcoin_addresses = [
                "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
            ]

            bitcoin_request = BatchBalanceRequest(
                addresses=bitcoin_addresses,
                network=BlockchainNetwork.BITCOIN,
                include_tokens=False
            )

            bitcoin_response = await blockchain_service.get_batch_balances(bitcoin_request)
            logger.info(f"Bitcoin batch query: {bitcoin_response.successful_queries}/{bitcoin_response.total_addresses} successful")
            self.demo_results["bitcoin_batch"] = {
                "successful": bitcoin_response.successful_queries,
                "total": bitcoin_response.total_addresses,
                "response_time_ms": bitcoin_response.response_time_ms
            }

            # Ethereum batch balance query
            ethereum_addresses = [
                "0x742d35Cc6634C0532925a3b8D4C9db96C4b4Db45",
                "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
            ]

            ethereum_request = BatchBalanceRequest(
                addresses=ethereum_addresses,
                network=BlockchainNetwork.ETHEREUM,
                include_tokens=True
            )

            ethereum_response = await blockchain_service.get_batch_balances(ethereum_request)
            logger.info(f"Ethereum batch query: {ethereum_response.successful_queries}/{ethereum_response.total_addresses} successful")
            self.demo_results["ethereum_batch"] = {
                "successful": ethereum_response.successful_queries,
                "total": ethereum_response.total_addresses,
                "response_time_ms": ethereum_response.response_time_ms
            }

        except Exception as e:
            logger.error(f"Batch operations demo failed: {e}")
            self.demo_results["batch_error"] = str(e)

    async def demo_error_handling(self):
        """Demonstrate error handling and fallback capabilities."""
        logger.info("=== Error Handling Demo ===")

        try:
            # Test with invalid address
            invalid_address = "invalid_address_format"
            is_valid, _ = await blockchain_service.validate_address(invalid_address, BlockchainNetwork.BITCOIN)
            logger.info(f"Invalid address validation: {is_valid}")
            self.demo_results["invalid_address_validation"] = is_valid

            # Test with non-existent transaction hash
            fake_tx_hash = "0x" + "0" * 64
            tx_result = await blockchain_service.get_transaction(fake_tx_hash, BlockchainNetwork.ETHEREUM)
            logger.info(f"Fake transaction query result: {tx_result is None}")
            self.demo_results["fake_transaction_query"] = tx_result is None

            # Get error summary
            error_summary = await blockchain_error_handler.get_error_summary(hours=1)
            logger.info(f"Error summary: {error_summary['total_errors']} errors in last hour")
            self.demo_results["error_summary"] = {
                "total_errors": error_summary["total_errors"],
                "categories": error_summary["errors_by_category"]
            }

            # Get health status
            health_status = await blockchain_error_handler.get_health_status()
            logger.info(f"Error handler health: {health_status['status']}")
            self.demo_results["error_handler_health"] = health_status["status"]

        except Exception as e:
            logger.error(f"Error handling demo failed: {e}")
            self.demo_results["error_handling_error"] = str(e)

    async def demo_caching_performance(self):
        """Demonstrate caching and performance features."""
        logger.info("=== Caching and Performance Demo ===")

        try:
            test_address = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"

            # First query (should hit API)
            start_time = datetime.utcnow()
            balance1 = await blockchain_service.get_balance(test_address, BlockchainNetwork.BITCOIN)
            first_query_time = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"First query time: {first_query_time:.3f}s")

            # Second query (should hit cache)
            start_time = datetime.utcnow()
            balance2 = await blockchain_service.get_balance(test_address, BlockchainNetwork.BITCOIN)
            second_query_time = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"Second query time: {second_query_time:.3f}s")

            cache_speedup = first_query_time / second_query_time if second_query_time > 0 else 0
            logger.info(f"Cache speedup: {cache_speedup:.1f}x")

            self.demo_results["caching_performance"] = {
                "first_query_time": first_query_time,
                "second_query_time": second_query_time,
                "cache_speedup": cache_speedup,
                "cache_working": second_query_time < first_query_time * 0.5  # Cache should be at least 2x faster
            }

            # Test cache clearing
            cleared_entries = await blockchain_service.clear_cache(BlockchainNetwork.BITCOIN)
            logger.info(f"Cleared {cleared_entries} cache entries")
            self.demo_results["cache_cleared"] = cleared_entries

        except Exception as e:
            logger.error(f"Caching demo failed: {e}")
            self.demo_results["caching_error"] = str(e)

    async def demo_health_monitoring(self):
        """Demonstrate health monitoring capabilities."""
        logger.info("=== Health Monitoring Demo ===")

        try:
            # Check health of all networks
            health_results = await blockchain_service.health_check()
            logger.info(f"Health check completed for {len(health_results)} networks")

            for network, result in health_results.items():
                if isinstance(result, dict) and result.get("providers"):
                    healthy_providers = sum(1 for p in result["providers"] if p["is_healthy"])
                    total_providers = len(result["providers"])
                    logger.info(f"  {network}: {healthy_providers}/{total_providers} providers healthy")
                    self.demo_results[f"{network}_health"] = {
                        "healthy_providers": healthy_providers,
                        "total_providers": total_providers
                    }

            # Get API manager health
            api_health = await api_manager.health_check("bitcoin")
            if api_health:
                logger.info(f"API Manager health: {api_health['healthy_count']}/{api_health['total_count']} providers healthy")
                self.demo_results["api_manager_health"] = {
                    "healthy": api_health["healthy_count"],
                    "total": api_health["total_count"]
                }

        except Exception as e:
            logger.error(f"Health monitoring demo failed: {e}")
            self.demo_results["health_monitoring_error"] = str(e)

    def generate_demo_report(self) -> Dict[str, Any]:
        """Generate comprehensive demo report."""
        return {
            "demo_timestamp": datetime.utcnow().isoformat(),
            "results": self.demo_results,
            "summary": self._generate_summary()
        }

    def _generate_summary(self) -> Dict[str, Any]:
        """Generate summary of demo results."""
        total_demos = len([k for k in self.demo_results.keys() if not k.endswith("_error")])
        successful_demos = len([k for k, v in self.demo_results.items()
                              if not k.endswith("_error") and v is not None])

        # Feature coverage
        features_demoed = []
        if "bitcoin_validation" in self.demo_results:
            features_demoed.append("Bitcoin Address Validation")
        if "bitcoin_balances" in self.demo_results:
            features_demoed.append("Bitcoin Balance Queries")
        if any("ethereum" in k and "balance" in k for k in self.demo_results.keys()):
            features_demoed.append("Ethereum/EVM Balance Queries")
        if "bitcoin_batch" in self.demo_results:
            features_demoed.append("Batch Operations")
        if "caching_performance" in self.demo_results:
            features_demoed.append("Caching")
        if any("health" in k for k in self.demo_results.keys()):
            features_demoed.append("Health Monitoring")

        return {
            "total_demos": total_demos,
            "successful_demos": successful_demos,
            "success_rate": f"{(successful_demos / total_demos * 100):.1f}%" if total_demos > 0 else "0%",
            "features_demoed": features_demoed,
            "error_count": len([k for k in self.demo_results.keys() if k.endswith("_error")])
        }


async def run_blockchain_demo():
    """Run the complete blockchain integration demo."""
    demo = BlockchainIntegrationDemo()
    return await demo.run_demo()


if __name__ == "__main__":
    async def main():
        print("🚀 Starting Blockchain Integration Demo...")
        print("=" * 60)

        results = await run_blockchain_demo()

        print("\n" + "=" * 60)
        print("📊 DEMO RESULTS SUMMARY")
        print("=" * 60)

        summary = results["summary"]
        print(f"Total Demos: {summary['total_demos']}")
        print(f"Successful: {summary['successful_demos']}")
        print(f"Success Rate: {summary['success_rate']}")
        print(f"Features Demoed: {', '.join(summary['features_demoed'])}")

        if summary['error_count'] > 0:
            print(f"⚠️  {summary['error_count']} errors encountered")

        print(f"\n✨ Demo completed at: {results['demo_timestamp']}")

        # Show some key results
        if "bitcoin_balances" in results["results"]:
            print(f"📈 Bitcoin balance queries: {len(results['results']['bitcoin_balances'])} successful")

        if any("ethereum" in k and "balance" in k for k in results["results"].keys()):
            eth_balances = [k for k in results["results"].keys() if "ethereum" in k and "balance" in k]
            print(f"💰 Ethereum balance queries: {len(eth_balances)} networks tested")

        if "caching_performance" in results["results"]:
            cache_perf = results["results"]["caching_performance"]
            if cache_perf.get("cache_working"):
                print(f"⚡ Caching working: {cache_perf['cache_speedup']:.1f}x speedup")

    asyncio.run(main())