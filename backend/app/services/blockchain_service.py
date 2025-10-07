"""
Blockchain Integration Service - Base service for multi-chain support.

Provides abstract base class and unified interface for blockchain integrations
across Bitcoin, Ethereum, and EVM-compatible networks.
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Union, Any, Tuple

from app.models.blockchain_data import (
    AddressBalance, AddressInfo, BlockchainTransaction,
    BatchBalanceRequest, BatchBalanceResponse, NetworkStats,
    TransactionStatus, TransactionType, AddressType
)
from app.models.crypto_paper import BlockchainNetwork
from app.services.api_manager import api_manager, cache_response

logger = logging.getLogger(__name__)


class BlockchainIntegrationError(Exception):
    """Base exception for blockchain integration errors."""
    pass


class AddressValidationError(BlockchainIntegrationError):
    """Exception for address validation errors."""
    pass


class NetworkNotSupportedError(BlockchainIntegrationError):
    """Exception for unsupported networks."""
    pass


class BaseBlockchainService(ABC):
    """Abstract base class for blockchain integrations."""

    def __init__(self, network: BlockchainNetwork):
        self.network = network
        self.logger = logging.getLogger(f"{__name__}.{network.value}")

    @abstractmethod
    async def validate_address(self, address: str) -> Tuple[bool, Optional[AddressType]]:
        """
        Validate address format and determine address type.

        Args:
            address: Blockchain address to validate

        Returns:
            Tuple of (is_valid, address_type)
        """
        pass

    @abstractmethod
    async def get_balance(self, address: str) -> Optional[AddressBalance]:
        """
        Get balance for a single address.

        Args:
            address: Blockchain address

        Returns:
            Address balance information or None if failed
        """
        pass

    @abstractmethod
    async def get_address_info(self, address: str) -> Optional[AddressInfo]:
        """
        Get comprehensive address information.

        Args:
            address: Blockchain address

        Returns:
            Address information or None if failed
        """
        pass

    @abstractmethod
    async def get_transactions(
        self,
        address: str,
        limit: int = 50,
        offset: int = 0,
        from_block: Optional[int] = None,
        to_block: Optional[int] = None
    ) -> List[BlockchainTransaction]:
        """
        Get transaction history for an address.

        Args:
            address: Blockchain address
            limit: Maximum number of transactions
            offset: Number of transactions to skip
            from_block: Starting block number
            to_block: Ending block number

        Returns:
            List of blockchain transactions
        """
        pass

    @abstractmethod
    async def get_transaction(self, tx_hash: str) -> Optional[BlockchainTransaction]:
        """
        Get transaction details by hash.

        Args:
            tx_hash: Transaction hash

        Returns:
            Transaction details or None if not found
        """
        pass

    async def get_batch_balances(
        self,
        addresses: List[str],
        include_tokens: bool = False
    ) -> BatchBalanceResponse:
        """
        Get balances for multiple addresses.

        Args:
            addresses: List of addresses
            include_tokens: Include token balances (for EVM chains)

        Returns:
            Batch balance response
        """
        start_time = asyncio.get_event_loop().time()

        # Validate addresses first
        valid_addresses = []
        errors = []

        for address in addresses:
            is_valid, _ = await self.validate_address(address)
            if is_valid:
                valid_addresses.append(address)
            else:
                errors.append({
                    "address": address,
                    "error": f"Invalid address format: {address}"
                })

        # Prepare batch requests
        requests = []
        for address in valid_addresses:
            requests.append({
                "endpoint": f"/address/{address}",
                "cache_ttl": getattr(settings, 'blockchain_cache_ttl_seconds', 300)
            })

        # Execute batch requests
        balance_responses = await api_manager.batch_request(
            network=self.network.value,
            requests=[{"endpoint": f"/address/{addr}"} for addr in valid_addresses],
            use_cache=True
        )

        # Process responses
        balances = []
        processed_count = 0

        for i, response in enumerate(balance_responses):
            if response and i < len(valid_addresses):
                try:
                    balance = await self._parse_balance_response(valid_addresses[i], response)
                    if balance:
                        balances.append(balance)
                        processed_count += 1
                except Exception as e:
                    self.logger.error(f"Error parsing balance for {valid_addresses[i]}: {e}")
                    errors.append({
                        "address": valid_addresses[i],
                        "error": str(e)
                    })

        response_time = int((asyncio.get_event_loop().time() - start_time) * 1000)

        return BatchBalanceResponse(
            network=self.network,
            provider=api_manager.get_healthy_providers(self.network.value)[0].name if api_manager.get_healthy_providers(self.network.value) else "unknown",
            balances=balances,
            errors=errors,
            total_addresses=len(addresses),
            successful_queries=processed_count,
            failed_queries=len(addresses) - processed_count,
            response_time_ms=response_time,
            cached_results=len([b for b in balances if self._is_cached_response(b)])
        )

    @abstractmethod
    async def get_network_stats(self) -> Optional[NetworkStats]:
        """
        Get network statistics and health information.

        Returns:
            Network statistics or None if failed
        """
        pass

    async def sync_address(
        self,
        address: str,
        last_known_tx: Optional[str] = None
    ) -> Tuple[List[BlockchainTransaction], Optional[str]]:
        """
        Sync address for new transactions.

        Args:
            address: Blockchain address
            last_known_tx: Hash of last known transaction

        Returns:
            Tuple of (new_transactions, latest_tx_hash)
        """
        try:
            # Get transactions since last known
            transactions = await self.get_transactions(address, limit=100)

            if not transactions:
                return [], last_known_tx

            # Find new transactions
            new_transactions = []
            latest_tx_hash = transactions[0].tx_hash

            if last_known_tx:
                for tx in transactions:
                    if tx.tx_hash == last_known_tx:
                        break
                    new_transactions.append(tx)
            else:
                new_transactions = transactions

            self.logger.info(f"Found {len(new_transactions)} new transactions for {address}")
            return new_transactions, latest_tx_hash

        except Exception as e:
            self.logger.error(f"Error syncing address {address}: {e}")
            raise BlockchainIntegrationError(f"Sync failed: {str(e)}")

    @abstractmethod
    async def _parse_balance_response(self, address: str, response: Dict) -> Optional[AddressBalance]:
        """Parse balance response from provider-specific format."""
        pass

    @abstractmethod
    async def _parse_transaction_response(self, response: Dict) -> Optional[BlockchainTransaction]:
        """Parse transaction response from provider-specific format."""
        pass

    def _is_cached_response(self, balance: AddressBalance) -> bool:
        """Check if balance response is from cache."""
        # Simple heuristic - if updated more than 4 minutes ago, likely cached
        return (datetime.utcnow() - balance.last_updated).total_seconds() > 240


class BlockchainServiceFactory:
    """Factory for creating blockchain service instances."""

    _services: Dict[BlockchainNetwork, BaseBlockchainService] = {}
    _initialized = False

    @classmethod
    async def initialize(cls):
        """Initialize all blockchain services."""
        if cls._initialized:
            return

        # Import service implementations here to avoid circular imports
        from .bitcoin_integration import BitcoinService
        from .ethereum_integration import EthereumService

        # Register services
        cls._services[BlockchainNetwork.BITCOIN] = BitcoinService()
        cls._services[BlockchainNetwork.ETHEREUM] = EthereumService(BlockchainNetwork.ETHEREUM)
        cls._services[BlockchainNetwork.POLYGON] = EthereumService(BlockchainNetwork.POLYGON)
        cls._services[BlockchainNetwork.BSC] = EthereumService(BlockchainNetwork.BSC)
        cls._services[BlockchainNetwork.ARBITRUM] = EthereumService(BlockchainNetwork.ARBITRUM)
        cls._services[BlockchainNetwork.OPTIMISM] = EthereumService(BlockchainNetwork.OPTIMISM)

        cls._initialized = True
        logger.info("Blockchain service factory initialized")

    @classmethod
    def get_service(cls, network: BlockchainNetwork) -> BaseBlockchainService:
        """Get blockchain service for a network."""
        if not cls._initialized:
            raise RuntimeError("BlockchainServiceFactory not initialized")

        service = cls._services.get(network)
        if not service:
            raise NetworkNotSupportedError(f"Network {network.value} not supported")

        return service

    @classmethod
    def get_supported_networks(cls) -> List[BlockchainNetwork]:
        """Get list of supported networks."""
        return list(cls._services.keys())


class BlockchainService:
    """Main blockchain service providing unified interface for all networks."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def initialize(self):
        """Initialize the service."""
        await BlockchainServiceFactory.initialize()
        await api_manager.initialize()
        self.logger.info("Blockchain service initialized")

    async def cleanup(self):
        """Cleanup resources."""
        await api_manager.cleanup()

    async def validate_address(self, address: str, network: BlockchainNetwork) -> Tuple[bool, Optional[AddressType]]:
        """
        Validate address format for any supported network.

        Args:
            address: Blockchain address
            network: Blockchain network

        Returns:
            Tuple of (is_valid, address_type)
        """
        try:
            service = BlockchainServiceFactory.get_service(network)
            return await service.validate_address(address)
        except Exception as e:
            self.logger.error(f"Error validating address {address} on {network.value}: {e}")
            return False, None

    async def get_balance(
        self,
        address: str,
        network: BlockchainNetwork,
        include_tokens: bool = False
    ) -> Optional[AddressBalance]:
        """
        Get balance for an address on any supported network.

        Args:
            address: Blockchain address
            network: Blockchain network
            include_tokens: Include token balances for EVM chains

        Returns:
            Address balance or None if failed
        """
        try:
            service = BlockchainServiceFactory.get_service(network)

            if include_tokens and hasattr(service, 'get_balance_with_tokens'):
                return await service.get_balance_with_tokens(address)
            else:
                return await service.get_balance(address)

        except Exception as e:
            self.logger.error(f"Error getting balance for {address} on {network.value}: {e}")
            return None

    async def get_address_info(
        self,
        address: str,
        network: BlockchainNetwork
    ) -> Optional[AddressInfo]:
        """
        Get comprehensive address information.

        Args:
            address: Blockchain address
            network: Blockchain network

        Returns:
            Address information or None if failed
        """
        try:
            service = BlockchainServiceFactory.get_service(network)
            return await service.get_address_info(address)
        except Exception as e:
            self.logger.error(f"Error getting address info for {address} on {network.value}: {e}")
            return None

    async def get_transactions(
        self,
        address: str,
        network: BlockchainNetwork,
        limit: int = 50,
        offset: int = 0,
        from_block: Optional[int] = None,
        to_block: Optional[int] = None
    ) -> List[BlockchainTransaction]:
        """
        Get transaction history for an address.

        Args:
            address: Blockchain address
            network: Blockchain network
            limit: Maximum number of transactions
            offset: Number of transactions to skip
            from_block: Starting block number
            to_block: Ending block number

        Returns:
            List of blockchain transactions
        """
        try:
            service = BlockchainServiceFactory.get_service(network)
            return await service.get_transactions(address, limit, offset, from_block, to_block)
        except Exception as e:
            self.logger.error(f"Error getting transactions for {address} on {network.value}: {e}")
            return []

    async def get_transaction(
        self,
        tx_hash: str,
        network: BlockchainNetwork
    ) -> Optional[BlockchainTransaction]:
        """
        Get transaction details by hash.

        Args:
            tx_hash: Transaction hash
            network: Blockchain network

        Returns:
            Transaction details or None if not found
        """
        try:
            service = BlockchainServiceFactory.get_service(network)
            return await service.get_transaction(tx_hash)
        except Exception as e:
            self.logger.error(f"Error getting transaction {tx_hash} on {network.value}: {e}")
            return None

    async def get_batch_balances(
        self,
        request: BatchBalanceRequest
    ) -> BatchBalanceResponse:
        """
        Get balances for multiple addresses.

        Args:
            request: Batch balance request

        Returns:
            Batch balance response
        """
        try:
            service = BlockchainServiceFactory.get_service(request.network)
            return await service.get_batch_balances(request.addresses, request.include_tokens)
        except Exception as e:
            self.logger.error(f"Error getting batch balances for {request.network.value}: {e}")
            return BatchBalanceResponse(
                network=request.network,
                provider="error",
                balances=[],
                errors=[{"error": str(e)}],
                total_addresses=len(request.addresses),
                successful_queries=0,
                failed_queries=len(request.addresses),
                response_time_ms=0
            )

    async def sync_address(
        self,
        address: str,
        network: BlockchainNetwork,
        last_known_tx: Optional[str] = None
    ) -> Tuple[List[BlockchainTransaction], Optional[str]]:
        """
        Sync address for new transactions.

        Args:
            address: Blockchain address
            network: Blockchain network
            last_known_tx: Hash of last known transaction

        Returns:
            Tuple of (new_transactions, latest_tx_hash)
        """
        try:
            service = BlockchainServiceFactory.get_service(network)
            return await service.sync_address(address, last_known_tx)
        except Exception as e:
            self.logger.error(f"Error syncing address {address} on {network.value}: {e}")
            return [], last_known_tx

    async def get_network_stats(self, network: BlockchainNetwork) -> Optional[NetworkStats]:
        """
        Get network statistics.

        Args:
            network: Blockchain network

        Returns:
            Network statistics or None if failed
        """
        try:
            service = BlockchainServiceFactory.get_service(network)
            return await service.get_network_stats()
        except Exception as e:
            self.logger.error(f"Error getting network stats for {network.value}: {e}")
            return None

    async def health_check(self, network: Optional[BlockchainNetwork] = None) -> Dict[str, Any]:
        """
        Perform health check on blockchain services.

        Args:
            network: Specific network to check, or None for all

        Returns:
            Health check results
        """
        if network:
            return await api_manager.health_check(network.value)
        else:
            results = {}
            for net in BlockchainServiceFactory.get_supported_networks():
                results[net.value] = await api_manager.health_check(net.value)
            return results

    async def clear_cache(self, network: Optional[BlockchainNetwork] = None) -> int:
        """
        Clear blockchain cache.

        Args:
            network: Specific network cache to clear, or None for all

        Returns:
            Number of cache entries cleared
        """
        if network:
            return await api_manager.clear_cache(network.value)
        else:
            return await api_manager.clear_cache()

    @cache_response(ttl_seconds=300, key_prefix="blockchain")
    async def get_supported_networks(self) -> List[Dict[str, str]]:
        """
        Get list of supported networks with metadata.

        Returns:
            List of supported networks
        """
        networks = []
        for network in BlockchainServiceFactory.get_supported_networks():
            networks.append({
                "network": network.value,
                "name": network.value.title(),
                "currency": self._get_native_currency(network),
                "explorer_url": self._get_explorer_url(network)
            })
        return networks

    def _get_native_currency(self, network: BlockchainNetwork) -> str:
        """Get native currency symbol for network."""
        currency_map = {
            BlockchainNetwork.BITCOIN: "BTC",
            BlockchainNetwork.ETHEREUM: "ETH",
            BlockchainNetwork.POLYGON: "MATIC",
            BlockchainNetwork.BSC: "BNB",
            BlockchainNetwork.ARBITRUM: "ETH",
            BlockchainNetwork.OPTIMISM: "ETH"
        }
        return currency_map.get(network, "UNKNOWN")

    def _get_explorer_url(self, network: BlockchainNetwork) -> str:
        """Get block explorer URL for network."""
        explorer_map = {
            BlockchainNetwork.BITCOIN: "https://blockstream.info",
            BlockchainNetwork.ETHEREUM: "https://etherscan.io",
            BlockchainNetwork.POLYGON: "https://polygonscan.com",
            BlockchainNetwork.BSC: "https://bscscan.com",
            BlockchainNetwork.ARBITRUM: "https://arbiscan.io",
            BlockchainNetwork.OPTIMISM: "https://optimistic.etherscan.io"
        }
        return explorer_map.get(network, "")


# Global blockchain service instance
blockchain_service = BlockchainService()


# Import settings for configuration
from app.config import settings