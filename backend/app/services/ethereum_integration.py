"""
Ethereum/EVM API Integration Service.

Implements blockchain integration for Ethereum and EVM-compatible networks
(Ethereum, Polygon, BSC, Arbitrum, Optimism) using multiple API providers
with fallback support and comprehensive error handling.
"""
import asyncio
import json
import logging
import re
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any

from app.models.blockchain_data import (
    AddressBalance, AddressInfo, BlockchainTransaction, NetworkStats,
    TransactionStatus, TransactionType, AddressType, TokenInfo, GasInfo
)
from app.models.crypto_paper import BlockchainNetwork
from app.services.blockchain_service import BaseBlockchainService, BlockchainIntegrationError
from app.services.api_manager import api_manager, cache_response
from app.config import settings

logger = logging.getLogger(__name__)


class EthereumService(BaseBlockchainService):
    """Ethereum/EVM blockchain integration service."""

    # Ethereum address validation (40 hex characters, 0x prefix)
    ADDRESS_PATTERN = re.compile(r'^0x[a-fA-F0-9]{40}$')

    # Transaction hash pattern (64 hex characters, 0x prefix)
    TX_HASH_PATTERN = re.compile(r'^0x[a-fA-F0-9]{64}$')

    # Wei to ETH conversion
    WEI_TO_ETH = Decimal('1000000000000000000')

    # Common ERC-20 token addresses (for token metadata)
    COMMON_TOKENS = {
        "ethereum": {
            "0xA0b86a33E6441e7C3a3a9a4c1F2b9d8d1c8B9c9E": {"symbol": "USDC", "name": "USD Coin", "decimals": 6},
            "0xdAC17F958D2ee523a2206206994597C13D831ec7": {"symbol": "USDT", "name": "Tether", "decimals": 6},
            "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599": {"symbol": "WBTC", "name": "Wrapped Bitcoin", "decimals": 8},
        },
        "polygon": {
            "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174": {"symbol": "USDC", "name": "USD Coin", "decimals": 6},
            "0xc2132D05D31c914a87C6611C10748AEb04B58e8F": {"symbol": "USDT", "name": "Tether", "decimals": 6},
        },
        "bsc": {
            "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d": {"symbol": "USDC", "name": "USD Coin", "decimals": 18},
            "0x55d398326f99059fF775485246999027B3197955": {"symbol": "USDT", "name": "Tether", "decimals": 18},
        }
    }

    def __init__(self, network: BlockchainNetwork):
        super().__init__(network)
        self.network_name = network.value

        # Network-specific configuration
        self.network_configs = {
            BlockchainNetwork.ETHEREUM: {
                "name": "Ethereum",
                "symbol": "ETH",
                "explorer": "etherscan.io",
                "chain_id": 1
            },
            BlockchainNetwork.POLYGON: {
                "name": "Polygon",
                "symbol": "MATIC",
                "explorer": "polygonscan.com",
                "chain_id": 137
            },
            BlockchainNetwork.BSC: {
                "name": "BSC",
                "symbol": "BNB",
                "explorer": "bscscan.com",
                "chain_id": 56
            },
            BlockchainNetwork.ARBITRUM: {
                "name": "Arbitrum",
                "symbol": "ETH",
                "explorer": "arbiscan.io",
                "chain_id": 42161
            },
            BlockchainNetwork.OPTIMISM: {
                "name": "Optimism",
                "symbol": "ETH",
                "explorer": "optimistic.etherscan.io",
                "chain_id": 10
            }
        }

    async def validate_address(self, address: str) -> Tuple[bool, Optional[AddressType]]:
        """
        Validate Ethereum/EVM address format.

        Args:
            address: Ethereum/EVM address

        Returns:
            Tuple of (is_valid, address_type)
        """
        try:
            if self.ADDRESS_PATTERN.match(address):
                return True, AddressType.ETH
            else:
                return False, None
        except Exception as e:
            self.logger.error(f"Error validating {self.network_name} address {address}: {e}")
            return False, None

    @cache_response(ttl_seconds=300, key_prefix="eth_balance")
    async def get_balance(self, address: str) -> Optional[AddressBalance]:
        """
        Get ETH balance for an address.

        Args:
            address: Ethereum/EVM address

        Returns:
            Address balance or None if failed
        """
        try:
            # Validate address first
            is_valid, _ = await self.validate_address(address)
            if not is_valid:
                raise ValueError(f"Invalid {self.network_name} address: {address}")

            # Get balance via JSON-RPC
            balance_wei = await self._make_rpc_call("eth_getBalance", [address, "latest"])
            if balance_wei is None:
                return None

            # Convert from wei to ETH
            balance_eth = Decimal(int(balance_wei, 16)) / self.WEI_TO_ETH

            # Get address type
            _, address_type = await self.validate_address(address)

            return AddressBalance(
                address=address,
                network=self.network,
                balance=balance_eth,
                address_type=address_type,
                is_valid=True
            )

        except Exception as e:
            self.logger.error(f"Error getting {self.network_name} balance for {address}: {e}")
            return None

    async def get_balance_with_tokens(self, address: str) -> Optional[AddressBalance]:
        """
        Get ETH balance plus ERC-20 token balances.

        Args:
            address: Ethereum/EVM address

        Returns:
            Address balance with tokens or None if failed
        """
        try:
            # Get ETH balance first
            balance = await self.get_balance(address)
            if not balance:
                return None

            # Get token balances
            token_balances = await self.get_token_balances(address)
            balance.token_balances = token_balances

            return balance

        except Exception as e:
            self.logger.error(f"Error getting {self.network_name} balance with tokens for {address}: {e}")
            return None

    async def get_token_balances(self, address: str) -> List[Dict[str, Any]]:
        """
        Get ERC-20 token balances for an address.

        Args:
            address: Ethereum/EVM address

        Returns:
            List of token balances
        """
        try:
            # Get common tokens for this network
            common_tokens = self.COMMON_TOKENS.get(self.network_name, {})

            # Create batch requests for token balances
            requests = []
            for token_address, token_info in common_tokens.items():
                # Create balanceOf call data
                method_signature = "0x70a08231"  # balanceOf(address)
                padded_address = address[2:].zfill(64)
                call_data = method_signature + padded_address

                requests.append({
                    "endpoint": "",
                    "method": "POST",
                    "data": {
                        "jsonrpc": "2.0",
                        "method": "eth_call",
                        "params": [{
                            "to": token_address,
                            "data": call_data
                        }, "latest"],
                        "id": 1
                    }
                })

            # Execute batch requests
            responses = await api_manager.batch_request(
                network=self.network_name,
                requests=requests,
                use_cache=True
            )

            # Process responses
            token_balances = []
            for i, (token_address, token_info) in enumerate(common_tokens.items()):
                if i < len(responses) and responses[i]:
                    balance_hex = responses[i].get("result")
                    if balance_hex and balance_hex != "0x":
                        balance = int(balance_hex, 16)
                        decimals = token_info["decimals"]
                        balance_float = balance / (10 ** decimals)

                        if balance_float > 0:
                            token_balances.append({
                                "contract_address": token_address,
                                "symbol": token_info["symbol"],
                                "name": token_info["name"],
                                "decimals": decimals,
                                "balance": balance_float,
                                "balance_raw": balance
                            })

            return token_balances

        except Exception as e:
            self.logger.error(f"Error getting token balances for {address}: {e}")
            return []

    @cache_response(ttl_seconds=600, key_prefix="eth_address")
    async def get_address_info(self, address: str) -> Optional[AddressInfo]:
        """
        Get comprehensive Ethereum/EVM address information.

        Args:
            address: Ethereum/EVM address

        Returns:
            Address information or None if failed
        """
        try:
            # Get balance
            balance = await self.get_balance_with_tokens(address)
            if not balance:
                return None

            # Get transaction count
            tx_count = await self._make_rpc_call("eth_getTransactionCount", [address, "latest"])
            if tx_count is None:
                tx_count = 0
            else:
                tx_count = int(tx_count, 16)

            # Get first and last transaction (simplified)
            first_tx_hash = None
            first_tx_timestamp = None
            last_tx_hash = None
            last_tx_timestamp = None

            # For now, we'll use placeholder logic
            # In a full implementation, you'd query the transaction history
            total_transactions = tx_count
            total_received = balance.balance  # Simplified
            total_sent = Decimal("0")  # Would need to calculate from transactions

            return AddressInfo(
                address=address,
                network=self.network,
                address_type=AddressType.ETH,
                is_valid=True,
                current_balance=balance,
                total_transactions=total_transactions,
                total_received=total_received,
                total_sent=total_sent,
                first_tx_hash=first_tx_hash,
                first_tx_timestamp=first_tx_timestamp,
                last_tx_hash=last_tx_hash,
                last_tx_timestamp=last_tx_timestamp
            )

        except Exception as e:
            self.logger.error(f"Error getting {self.network_name} address info for {address}: {e}")
            return None

    async def get_transactions(
        self,
        address: str,
        limit: int = 50,
        offset: int = 0,
        from_block: Optional[int] = None,
        to_block: Optional[int] = None
    ) -> List[BlockchainTransaction]:
        """
        Get Ethereum/EVM transaction history for an address.

        Note: This is a simplified implementation. A full implementation would use
        an external service like Etherscan API or build an index of transactions.

        Args:
            address: Ethereum/EVM address
            limit: Maximum number of transactions
            offset: Number of transactions to skip
            from_block: Starting block number
            to_block: Ending block number

        Returns:
            List of Ethereum/EVM transactions
        """
        try:
            # For now, return empty list as this would require indexing or external API
            # In a full implementation, you'd use services like:
            # - Etherscan API (with API key)
            # - The Graph protocol
            # - Custom transaction indexing

            self.logger.warning(f"Transaction history not implemented for {self.network_name}")
            return []

        except Exception as e:
            self.logger.error(f"Error getting {self.network_name} transactions for {address}: {e}")
            return []

    async def get_transaction(self, tx_hash: str) -> Optional[BlockchainTransaction]:
        """
        Get Ethereum/EVM transaction details by hash.

        Args:
            tx_hash: Transaction hash

        Returns:
            Transaction details or None if not found
        """
        try:
            if not self.TX_HASH_PATTERN.match(tx_hash):
                raise ValueError(f"Invalid transaction hash: {tx_hash}")

            # Get transaction
            tx_response = await self._make_rpc_call("eth_getTransactionByHash", [tx_hash])
            if not tx_response:
                return None

            # Get transaction receipt
            receipt_response = await self._make_rpc_call("eth_getTransactionReceipt", [tx_hash])

            return await self._parse_transaction_response(tx_response, receipt_response)

        except Exception as e:
            self.logger.error(f"Error getting {self.network_name} transaction {tx_hash}: {e}")
            return None

    @cache_response(ttl_seconds=60, key_prefix="eth_network")
    async def get_network_stats(self) -> Optional[NetworkStats]:
        """
        Get Ethereum/EVM network statistics.

        Returns:
            Network statistics or None if failed
        """
        try:
            start_time = asyncio.get_event_loop().time()

            # Get latest block
            block_number = await self._make_rpc_call("eth_blockNumber", [])
            if not block_number:
                return None

            block_number_int = int(block_number, 16)

            # Get block details
            block_response = await self._make_rpc_call("eth_getBlockByNumber", ["latest", False])
            if not block_response:
                return None

            response_time = int((asyncio.get_event_loop().time() - start_time) * 1000)

            # Get provider info
            providers = api_manager.get_healthy_providers(self.network_name)
            provider_name = providers[0].name if providers else "unknown"

            return NetworkStats(
                network=self.network,
                provider=provider_name,
                latest_block_number=block_number_int,
                latest_block_hash=block_response.get("hash", ""),
                latest_block_timestamp=datetime.fromtimestamp(int(block_response.get("timestamp", "0"), 16)),
                is_healthy=True,
                response_time_ms=response_time
            )

        except Exception as e:
            self.logger.error(f"Error getting {self.network_name} network stats: {e}")
            return None

    async def _make_rpc_call(self, method: str, params: List[Any]) -> Optional[Any]:
        """
        Make JSON-RPC call to Ethereum/EVM node.

        Args:
            method: RPC method name
            params: Method parameters

        Returns:
            RPC response or None if failed
        """
        try:
            response = await api_manager.make_request(
                network=self.network_name,
                endpoint="",
                method="POST",
                data={
                    "jsonrpc": "2.0",
                    "method": method,
                    "params": params,
                    "id": 1
                }
            )

            if response:
                return response.get("result")
            return None

        except Exception as e:
            self.logger.error(f"Error making {self.network_name} RPC call {method}: {e}")
            return None

    async def _parse_balance_response(self, address: str, response: Dict) -> Optional[AddressBalance]:
        """Parse Ethereum/EVM balance response from API."""
        # This would be used if we had a REST API instead of JSON-RPC
        # For now, balance parsing is handled in get_balance method
        return None

    async def _parse_transaction_response(
        self,
        tx_response: Dict,
        receipt_response: Optional[Dict] = None
    ) -> Optional[BlockchainTransaction]:
        """Parse Ethereum/EVM transaction response from RPC."""
        try:
            tx_hash = tx_response.get("hash", "")
            from_address = tx_response.get("from", "")
            to_address = tx_response.get("to", "")
            value_hex = tx_response.get("value", "0x0")
            gas_hex = tx_response.get("gas", "0x0")
            gas_price_hex = tx_response.get("gasPrice", "0x0")
            nonce = tx_response.get("nonce", 0)

            # Convert values from hex
            value = int(value_hex, 16) / self.WEI_TO_ETH
            gas_limit = int(gas_hex, 16)
            gas_price = Decimal(int(gas_price_hex, 16)) if gas_price_hex != "0x0" else None

            # Get transaction status from receipt
            status = TransactionStatus.PENDING
            confirmations = 0
            block_hash = None
            block_number = None
            block_timestamp = None
            gas_used = None
            total_gas_cost = None

            if receipt_response:
                # Transaction was mined
                status_code = receipt_response.get("status", "0x1")
                status = TransactionStatus.CONFIRMED if status_code == "0x1" else TransactionStatus.FAILED

                block_hash = receipt_response.get("blockHash")
                block_number = receipt_response.get("blockNumber")
                if block_number:
                    block_number = int(block_number, 16)

                gas_used_hex = receipt_response.get("gasUsed", "0x0")
                gas_used = int(gas_used_hex, 16)

                if gas_price and gas_used:
                    total_gas_cost = Decimal(gas_price * gas_used) / self.WEI_TO_ETH

                # Get block timestamp
                if block_hash:
                    block_response = await self._make_rpc_call("eth_getBlockByHash", [block_hash, False])
                    if block_response:
                        block_timestamp = datetime.fromtimestamp(int(block_response.get("timestamp", "0"), 16))

            # Determine transaction type
            transaction_type = TransactionType.TRANSFER
            if to_address:
                transaction_type = TransactionType.SENT
            else:
                # Contract creation
                transaction_type = TransactionType.CONTRACT_CREATION

            # Create gas info
            gas_info = None
            if gas_limit:
                gas_info = GasInfo(
                    gas_limit=gas_limit,
                    gas_used=gas_used,
                    gas_price=gas_price,
                    total_gas_cost=total_gas_cost
                )

            return BlockchainTransaction(
                tx_hash=tx_hash,
                block_hash=block_hash,
                block_number=block_number,
                block_timestamp=block_timestamp,
                transaction_type=transaction_type,
                status=status,
                confirmations=confirmations,
                from_address=from_address,
                to_address=to_address,
                value=Decimal(str(value)),
                gas_info=gas_info,
                nonce=nonce,
                network=self.network,
                raw_data={"transaction": tx_response, "receipt": receipt_response}
            )

        except Exception as e:
            self.logger.error(f"Error parsing {self.network_name} transaction response: {e}")
            return None

    async def estimate_gas(
        self,
        from_address: str,
        to_address: Optional[str] = None,
        value: Optional[Decimal] = None,
        data: Optional[str] = None
    ) -> Optional[int]:
        """
        Estimate gas for a transaction.

        Args:
            from_address: Sender address
            to_address: Receiver address (None for contract creation)
            value: ETH value to send
            data: Transaction data

        Returns:
            Estimated gas limit or None if failed
        """
        try:
            params = {
                "from": from_address
            }

            if to_address:
                params["to"] = to_address
            if value:
                params["value"] = f"0x{int(value * self.WEI_TO_ETH):x}"
            if data:
                params["data"] = data

            gas_estimate = await self._make_rpc_call("eth_estimateGas", [params])
            if gas_estimate:
                return int(gas_estimate, 16)

            return None

        except Exception as e:
            self.logger.error(f"Error estimating gas: {e}")
            return None

    async def get_gas_price(self) -> Optional[Decimal]:
        """
        Get current gas price.

        Returns:
            Current gas price in Gwei or None if failed
        """
        try:
            gas_price_hex = await self._make_rpc_call("eth_gasPrice", [])
            if gas_price_hex:
                gas_price_wei = int(gas_price_hex, 16)
                gas_price_gwei = Decimal(gas_price_wei) / Decimal('1000000000')
                return gas_price_gwei

            return None

        except Exception as e:
            self.logger.error(f"Error getting gas price: {e}")
            return None

    async def send_raw_transaction(self, signed_tx: str) -> Optional[str]:
        """
        Send signed raw transaction.

        Args:
            signed_tx: Signed transaction hex

        Returns:
            Transaction hash or None if failed
        """
        try:
            tx_hash = await self._make_rpc_call("eth_sendRawTransaction", [signed_tx])
            return tx_hash

        except Exception as e:
            self.logger.error(f"Error sending raw transaction: {e}")
            return None

    async def get_contract_logs(
        self,
        address: str,
        from_block: Optional[int] = None,
        to_block: Optional[int] = None,
        topics: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get logs for a smart contract.

        Args:
            address: Contract address
            from_block: Starting block
            to_block: Ending block
            topics: Log topics to filter

        Returns:
            List of log entries
        """
        try:
            params = {
                "address": address
            }

            if from_block is not None:
                params["fromBlock"] = f"0x{from_block:x}"
            else:
                params["fromBlock"] = "earliest"

            if to_block is not None:
                params["toBlock"] = f"0x{to_block:x}"
            else:
                params["toBlock"] = "latest"

            if topics:
                params["topics"] = topics

            logs = await self._make_rpc_call("eth_getLogs", [params])
            return logs if logs else []

        except Exception as e:
            self.logger.error(f"Error getting contract logs: {e}")
            return []