"""
Bitcoin API Integration Service.

Implements blockchain integration for Bitcoin network using multiple API providers
with fallback support and comprehensive error handling.
"""
import asyncio
import hashlib
import logging
import re
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any

from app.models.blockchain_data import (
    AddressBalance, AddressInfo, BlockchainTransaction, NetworkStats,
    TransactionStatus, TransactionType, AddressType, UTXO
)
from app.models.crypto_paper import BlockchainNetwork
from app.services.blockchain_service import BaseBlockchainService, BlockchainIntegrationError
from app.services.api_manager import api_manager, cache_response
from app.config import settings

logger = logging.getLogger(__name__)


class BitcoinService(BaseBlockchainService):
    """Bitcoin blockchain integration service."""

    # Bitcoin address validation patterns
    P2PKH_PATTERN = re.compile(r'^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$')
    P2SH_PATTERN = re.compile(r'^3[a-km-zA-HJ-NP-Z1-9]{33}$')
    BECH32_PATTERN = re.compile(r'^bc1[ac-hj-np-z02-9]{8,87}$')

    # Satoshi conversion
    SATOSHI_TO_BTC = Decimal('0.00000001')

    def __init__(self):
        super().__init__(BlockchainNetwork.BITCOIN)

    async def validate_address(self, address: str) -> Tuple[bool, Optional[AddressType]]:
        """
        Validate Bitcoin address format and determine type.

        Args:
            address: Bitcoin address

        Returns:
            Tuple of (is_valid, address_type)
        """
        try:
            # Check different address formats
            if self.BECH32_PATTERN.match(address):
                return True, AddressType.BECH32
            elif self.P2SH_PATTERN.match(address):
                return True, AddressType.P2SH
            elif self.P2PKH_PATTERN.match(address):
                return True, AddressType.P2PKH
            else:
                return False, None
        except Exception as e:
            self.logger.error(f"Error validating Bitcoin address {address}: {e}")
            return False, None

    @cache_response(ttl_seconds=300, key_prefix="bitcoin_balance")
    async def get_balance(self, address: str) -> Optional[AddressBalance]:
        """
        Get Bitcoin balance for an address.

        Args:
            address: Bitcoin address

        Returns:
            Address balance or None if failed
        """
        try:
            # Validate address first
            is_valid, address_type = await self.validate_address(address)
            if not is_valid:
                raise ValueError(f"Invalid Bitcoin address: {address}")

            # Get balance from API
            response = await api_manager.make_request(
                network="bitcoin",
                endpoint=f"/address/{address}"
            )

            if not response:
                self.logger.error(f"No response for Bitcoin address {address}")
                return None

            return await self._parse_balance_response(address, response)

        except Exception as e:
            self.logger.error(f"Error getting Bitcoin balance for {address}: {e}")
            return None

    @cache_response(ttl_seconds=600, key_prefix="bitcoin_address")
    async def get_address_info(self, address: str) -> Optional[AddressInfo]:
        """
        Get comprehensive Bitcoin address information.

        Args:
            address: Bitcoin address

        Returns:
            Address information or None if failed
        """
        try:
            # Get address details
            response = await api_manager.make_request(
                network="bitcoin",
                endpoint=f"/address/{address}"
            )

            if not response:
                return None

            # Get recent transactions
            tx_response = await api_manager.make_request(
                network="bitcoin",
                endpoint=f"/address/{address}/txs",
                params={"limit": "50"}
            )

            transactions = []
            if tx_response:
                for tx_data in tx_response:
                    transaction = await self._parse_transaction_response(tx_data)
                    if transaction:
                        transactions.append(transaction)

            return await self._parse_address_info_response(address, response, transactions)

        except Exception as e:
            self.logger.error(f"Error getting Bitcoin address info for {address}: {e}")
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
        Get Bitcoin transaction history for an address.

        Args:
            address: Bitcoin address
            limit: Maximum number of transactions
            offset: Number of transactions to skip
            from_block: Starting block height
            to_block: Ending block height

        Returns:
            List of Bitcoin transactions
        """
        try:
            params = {"limit": str(limit)}
            if offset > 0:
                params["offset"] = str(offset)

            response = await api_manager.make_request(
                network="bitcoin",
                endpoint=f"/address/{address}/txs",
                params=params
            )

            if not response:
                return []

            transactions = []
            for tx_data in response:
                transaction = await self._parse_transaction_response(tx_data)
                if transaction:
                    # Apply block filters if specified
                    if from_block and transaction.block_number and transaction.block_number < from_block:
                        continue
                    if to_block and transaction.block_number and transaction.block_number > to_block:
                        continue
                    transactions.append(transaction)

            return transactions

        except Exception as e:
            self.logger.error(f"Error getting Bitcoin transactions for {address}: {e}")
            return []

    async def get_transaction(self, tx_hash: str) -> Optional[BlockchainTransaction]:
        """
        Get Bitcoin transaction details by hash.

        Args:
            tx_hash: Bitcoin transaction hash

        Returns:
            Transaction details or None if not found
        """
        try:
            response = await api_manager.make_request(
                network="bitcoin",
                endpoint=f"/tx/{tx_hash}"
            )

            if not response:
                return None

            return await self._parse_transaction_response(response)

        except Exception as e:
            self.logger.error(f"Error getting Bitcoin transaction {tx_hash}: {e}")
            return None

    @cache_response(ttl_seconds=60, key_prefix="bitcoin_network")
    async def get_network_stats(self) -> Optional[NetworkStats]:
        """
        Get Bitcoin network statistics.

        Returns:
            Network statistics or None if failed
        """
        try:
            start_time = asyncio.get_event_loop().time()

            # Get latest block
            response = await api_manager.make_request(
                network="bitcoin",
                endpoint="/blocks",
                params={"limit": "1"}
            )

            if not response or not response:
                return None

            latest_block = response[0]
            response_time = int((asyncio.get_event_loop().time() - start_time) * 1000)

            # Get provider info
            providers = api_manager.get_healthy_providers("bitcoin")
            provider_name = providers[0].name if providers else "unknown"

            return NetworkStats(
                network=self.network,
                provider=provider_name,
                latest_block_number=latest_block.get("height", 0),
                latest_block_hash=latest_block.get("id", ""),
                latest_block_timestamp=datetime.fromtimestamp(latest_block.get("timestamp", 0)),
                is_healthy=True,
                response_time_ms=response_time
            )

        except Exception as e:
            self.logger.error(f"Error getting Bitcoin network stats: {e}")
            return None

    async def get_utxos(self, address: str) -> List[UTXO]:
        """
        Get UTXOs for a Bitcoin address.

        Args:
            address: Bitcoin address

        Returns:
            List of UTXOs
        """
        try:
            response = await api_manager.make_request(
                network="bitcoin",
                endpoint=f"/address/{address}/utxo"
            )

            if not response:
                return []

            utxos = []
            for utxo_data in response:
                utxo = UTXO(
                    txid=utxo_data.get("txid", ""),
                    vout=utxo_data.get("vout", 0),
                    value=utxo_data.get("value", 0),
                    script_pubkey=utxo_data.get("scriptpubkey", ""),
                    address=address,
                    confirmations=utxo_data.get("status", {}).get("confirmations", 0),
                    block_height=utxo_data.get("status", {}).get("block_height")
                )
                utxos.append(utxo)

            return utxos

        except Exception as e:
            self.logger.error(f"Error getting UTXOs for {address}: {e}")
            return []

    async def _parse_balance_response(self, address: str, response: Dict) -> Optional[AddressBalance]:
        """Parse Bitcoin balance response from API."""
        try:
            chain_stats = response.get("chain_stats", {})
            mempool_stats = response.get("mempool_stats", {})

            # Get confirmed balance
            confirmed_balance = chain_stats.get("funded_txo_sum", 0) - chain_stats.get("spent_txo_sum", 0)
            confirmed_balance_btc = Decimal(str(confirmed_balance)) * self.SATOSHI_TO_BTC

            # Get unconfirmed balance
            unconfirmed_balance = (mempool_stats.get("funded_txo_sum", 0) -
                                 mempool_stats.get("spent_txo_sum", 0))
            unconfirmed_balance_btc = Decimal(str(unconfirmed_balance)) * self.SATOSHI_TO_BTC

            # Get address type
            _, address_type = await self.validate_address(address)

            # Get UTXO count
            utxo_count = len(await self.get_utxos(address))

            return AddressBalance(
                address=address,
                network=self.network,
                balance=confirmed_balance_btc,
                unconfirmed_balance=unconfirmed_balance_btc,
                utxo_count=utxo_count,
                address_type=address_type,
                is_valid=True
            )

        except Exception as e:
            self.logger.error(f"Error parsing Bitcoin balance response: {e}")
            return None

    async def _parse_transaction_response(self, response: Dict) -> Optional[BlockchainTransaction]:
        """Parse Bitcoin transaction response from API."""
        try:
            tx_hash = response.get("txid", "")
            status = response.get("status", {})

            # Determine transaction status
            if status.get("confirmed", False):
                transaction_status = TransactionStatus.CONFIRMED
                confirmations = status.get("confirmations", 0)
                block_hash = status.get("block_hash", "")
                block_height = status.get("block_height", 0)
                block_time = status.get("block_time", 0)
                block_timestamp = datetime.fromtimestamp(block_time) if block_time else None
            else:
                transaction_status = TransactionStatus.PENDING
                confirmations = 0
                block_hash = None
                block_height = None
                block_timestamp = None

            # Calculate transaction value (total output to external addresses)
            total_value = 0
            fee = 0
            from_address = None
            to_addresses = []

            # Get transaction details if needed
            if "vout" not in response:
                tx_details = await api_manager.make_request(
                    network="bitcoin",
                    endpoint=f"/tx/{tx_hash}"
                )
                if tx_details:
                    response.update(tx_details)

            # Process inputs (sender address)
            vin = response.get("vin", [])
            if vin:
                # For simplicity, we'll use the first input's previous outpoint address
                # In reality, transactions can have multiple input addresses
                first_input = vin[0]
                if "prevout" in first_input:
                    from_address = first_input["prevout"].get("scriptpubkey_address")

            # Process outputs (receiver addresses and values)
            vout = response.get("vout", [])
            for output in vout:
                scriptpubkey = output.get("scriptpubkey", "")
                if scriptpubkey:
                    # Check if output is to an external address (not change)
                    scriptpubkey_address = output.get("scriptpubkey_address")
                    if scriptpubkey_address:
                        to_addresses.append(scriptpubkey_address)
                        total_value += output.get("value", 0)

            # Calculate fee (sum of inputs - sum of outputs)
            # This is simplified; in reality we'd need to get input values
            fee = response.get("fee", 0)

            # Determine transaction type
            transaction_type = TransactionType.TRANSFER
            if len(to_addresses) == 1:
                if from_address:
                    transaction_type = TransactionType.SENT
                else:
                    transaction_type = TransactionType.RECEIVED

            # Convert satoshis to BTC
            value_btc = Decimal(str(total_value)) * self.SATOSHI_TO_BTC
            fee_btc = Decimal(str(fee)) * self.SATOSHI_TO_BTC if fee else None

            return BlockchainTransaction(
                tx_hash=tx_hash,
                block_hash=block_hash,
                block_number=block_height,
                block_timestamp=block_timestamp,
                transaction_type=transaction_type,
                status=transaction_status,
                confirmations=confirmations,
                from_address=from_address,
                to_address=to_addresses[0] if to_addresses else None,
                value=value_btc,
                fee=fee_btc,
                network=self.network,
                raw_data=response
            )

        except Exception as e:
            self.logger.error(f"Error parsing Bitcoin transaction response: {e}")
            return None

    async def _parse_address_info_response(
        self,
        address: str,
        response: Dict,
        transactions: List[BlockchainTransaction]
    ) -> Optional[AddressInfo]:
        """Parse Bitcoin address info response from API."""
        try:
            chain_stats = response.get("chain_stats", {})
            mempool_stats = response.get("mempool_stats", {})

            # Calculate totals
            total_received_sat = chain_stats.get("funded_txo_sum", 0)
            total_sent_sat = chain_stats.get("spent_txo_sum", 0)
            total_received = Decimal(str(total_received_sat)) * self.SATOSHI_TO_BTC
            total_sent = Decimal(str(total_sent_sat)) * self.SATOSHI_TO_BTC

            # Get address type
            _, address_type = await self.validate_address(address)

            # Get current balance
            balance = await self.get_balance(address)
            if not balance:
                return None

            # Get first and last transaction info
            first_tx_hash = None
            first_tx_timestamp = None
            last_tx_hash = None
            last_tx_timestamp = None

            if transactions:
                # Transactions are usually returned in reverse chronological order
                last_tx = transactions[0]
                last_tx_hash = last_tx.tx_hash
                last_tx_timestamp = last_tx.block_timestamp or datetime.utcnow()

                first_tx = transactions[-1]
                first_tx_hash = first_tx.tx_hash
                first_tx_timestamp = first_tx.block_timestamp or datetime.utcnow()

            return AddressInfo(
                address=address,
                network=self.network,
                address_type=address_type,
                is_valid=True,
                current_balance=balance,
                total_transactions=len(transactions),
                total_received=total_received,
                total_sent=total_sent,
                first_tx_hash=first_tx_hash,
                first_tx_timestamp=first_tx_timestamp,
                last_tx_hash=last_tx_hash,
                last_tx_timestamp=last_tx_timestamp
            )

        except Exception as e:
            self.logger.error(f"Error parsing Bitcoin address info response: {e}")
            return None

    async def estimate_fee(self, blocks: int = 6) -> Optional[Decimal]:
        """
        Estimate Bitcoin transaction fee for target confirmation blocks.

        Args:
            blocks: Target number of blocks for confirmation

        Returns:
            Estimated fee in satoshis per byte or None if failed
        """
        try:
            response = await api_manager.make_request(
                network="bitcoin",
                endpoint="/fee-estimates"
            )

            if not response:
                return None

            fee_rate = response.get(str(blocks))
            if fee_rate:
                return Decimal(str(fee_rate))

            return None

        except Exception as e:
            self.logger.error(f"Error estimating Bitcoin fee: {e}")
            return None

    async def get_mempool_info(self) -> Optional[Dict[str, Any]]:
        """
        Get Bitcoin mempool information.

        Returns:
            Mempool statistics or None if failed
        """
        try:
            response = await api_manager.make_request(
                network="bitcoin",
                endpoint="/mempool"
            )

            return response

        except Exception as e:
            self.logger.error(f"Error getting Bitcoin mempool info: {e}")
            return None

    async def get_block(self, block_hash: str) -> Optional[Dict[str, Any]]:
        """
        Get Bitcoin block information.

        Args:
            block_hash: Block hash

        Returns:
            Block information or None if failed
        """
        try:
            response = await api_manager.make_request(
                network="bitcoin",
                endpoint=f"/block/{block_hash}"
            )

            return response

        except Exception as e:
            self.logger.error(f"Error getting Bitcoin block {block_hash}: {e}")
            return None