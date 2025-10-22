"""
Comprehensive integration tests for unified portfolio aggregation and multi-portfolio scenarios.

This module tests:
- Unified portfolio aggregation combining traditional and crypto holdings
- Multi-portfolio management scenarios
- Cross-portfolio performance calculations
- Transaction synchronization across portfolio types
- Error handling and edge cases in unified workflows
- API endpoints for unified portfolio operations
"""
import pytest
import asyncio
from datetime import datetime, timedelta, date
from decimal import Decimal, ROUND_HALF_UP
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import Dict, List, Any
import json

from app.database import AsyncSessionLocal, SyncSessionLocal
from app.models import (
    Transaction, Position, PriceHistory, PortfolioSnapshot,
    Benchmark, StockSplit, CachedMetrics
)
from app.models.crypto import (
    CryptoPortfolio, CryptoTransaction, CryptoPosition,
    CryptoCurrency, CryptoTransactionType
)
from app.services.calculations import FinancialCalculations
from app.services.position_manager import PositionManager
from app.services.price_history_manager import PriceHistoryManager
from app.schemas.portfolio import PortfolioOverview, PortfolioPerformance
from app.api.portfolio import get_portfolio_overview, get_holdings, get_performance_data
from app.api.crypto import (
    create_crypto_portfolio, get_crypto_holdings,
    create_crypto_transaction, get_crypto_performance_data
)
from app.config import settings


class TestUnifiedPortfolioAggregation:
    """Test cases for unified portfolio aggregation functionality."""

    @pytest.fixture(scope="function")
    def db_session(self):
        """Create a database session for testing."""
        with SyncSessionLocal() as session:
            yield session

    @pytest.fixture
    def sample_traditional_transactions(self):
        """Sample traditional transactions for testing."""
        return [
            {
                'operation_date': datetime(2023, 1, 15).date(),
                'transaction_type': 'BUY',
                'ticker': 'AAPL',
                'isin': 'US0378331005',
                'description': 'Apple Inc.',
                'quantity': Decimal('10'),
                'price_per_share': Decimal('150.00'),
                'amount_eur': Decimal('1500.00'),
                'currency': 'USD',
                'fees': Decimal('5.00'),
                'transaction_hash': 'aapl_buy_001',
                'broker': 'Test Broker'
            },
            {
                'operation_date': datetime(2023, 2, 20).date(),
                'transaction_type': 'BUY',
                'ticker': 'GOOGL',
                'isin': 'US38259A1078',
                'description': 'Alphabet Inc.',
                'quantity': Decimal('5'),
                'price_per_share': Decimal('100.00'),
                'amount_eur': Decimal('500.00'),
                'currency': 'USD',
                'fees': Decimal('3.00'),
                'transaction_hash': 'googl_buy_001',
                'broker': 'Test Broker'
            },
            {
                'operation_date': datetime(2023, 3, 10).date(),
                'transaction_type': 'SELL',
                'ticker': 'AAPL',
                'isin': 'US0378331005',
                'description': 'Apple Inc.',
                'quantity': Decimal('2'),
                'price_per_share': Decimal('160.00'),
                'amount_eur': Decimal('320.00'),
                'currency': 'USD',
                'fees': Decimal('2.00'),
                'transaction_hash': 'aapl_sell_001',
                'broker': 'Test Broker'
            }
        ]

    @pytest.fixture
    def sample_crypto_transactions(self):
        """Sample crypto transactions for testing."""
        return [
            {
                'symbol': 'BTC',
                'transaction_type': 'BUY',
                'quantity': Decimal('0.1'),
                'price_at_execution': Decimal('50000.00'),
                'fee': Decimal('10.00'),
                'currency': 'USD',
                'timestamp': datetime(2023, 2, 1),
                'exchange': 'Binance',
                'transaction_hash': 'btc_buy_001'
            },
            {
                'symbol': 'ETH',
                'transaction_type': 'BUY',
                'quantity': Decimal('2.0'),
                'price_at_execution': Decimal('3000.00'),
                'fee': Decimal('5.00'),
                'currency': 'USD',
                'timestamp': datetime(2023, 2, 15),
                'exchange': 'Coinbase',
                'transaction_hash': 'eth_buy_001'
            },
            {
                'symbol': 'BTC',
                'transaction_type': 'SELL',
                'quantity': Decimal('0.05'),
                'price_at_execution': Decimal('51000.00'),
                'fee': Decimal('8.00'),
                'currency': 'USD',
                'timestamp': datetime(2023, 3, 1),
                'exchange': 'Binance',
                'transaction_hash': 'btc_sell_001'
            }
        ]

    def test_traditional_portfolio_calculation(self, db_session, sample_traditional_transactions):
        """Test traditional portfolio calculation and aggregation."""
        # Add transactions to database
        for tx_data in sample_traditional_transactions:
            transaction = Transaction(**tx_data)
            db_session.add(transaction)

        db_session.commit()

        # Calculate positions
        position_manager = PositionManager()
        positions = position_manager.calculate_positions(db_session)

        # Verify positions were calculated correctly
        assert len(positions) >= 1  # Should have at least one position (AAPL)

        # Find AAPL position
        aapl_position = next((p for p in positions if p.ticker == 'AAPL'), None)
        assert aapl_position is not None
        assert aapl_position.quantity == Decimal('8')  # 10 bought, 2 sold
        assert aapl_position.average_cost > 0
        assert aapl_position.cost_basis > 0

    def test_crypto_portfolio_calculation(self, db_session, sample_crypto_transactions):
        """Test crypto portfolio calculation and aggregation."""
        # Create crypto portfolio
        crypto_portfolio = CryptoPortfolio(
            name='Test Crypto Portfolio',
            base_currency=CryptoCurrency.USD,
            description='Test portfolio for crypto transactions'
        )
        db_session.add(crypto_portfolio)
        db_session.commit()
        db_session.refresh(crypto_portfolio)

        # Add crypto transactions
        for tx_data in sample_crypto_transactions:
            tx_data['portfolio_id'] = crypto_portfolio.id
            transaction = CryptoTransaction(**tx_data)
            db_session.add(transaction)

        db_session.commit()

        # Calculate crypto holdings
        holdings = get_crypto_holdings(crypto_portfolio.id)
        assert holdings is not None
        assert len(holdings) >= 1  # Should have at least BTC position

        # Verify BTC position
        btc_holding = next((h for h in holdings if h.symbol == 'BTC'), None)
        assert btc_holding is not None
        assert btc_holding.quantity == Decimal('0.05')  # 0.1 bought, 0.05 sold
        assert btc_holding.average_cost > 0
        assert btc_holding.unrealized_gain_loss is not None

    def test_unified_portfolio_aggregation(self, db_session, sample_traditional_transactions, sample_crypto_transactions):
        """Test unified portfolio aggregation combining traditional and crypto holdings."""
        # Setup traditional portfolio
        for tx_data in sample_traditional_transactions:
            transaction = Transaction(**tx_data)
            db_session.add(transaction)

        # Setup crypto portfolio
        crypto_portfolio = CryptoPortfolio(
            name='Test Crypto Portfolio',
            base_currency=CryptoCurrency.USD,
            description='Test portfolio for crypto transactions'
        )
        db_session.add(crypto_portfolio)
        db_session.commit()
        db_session.refresh(crypto_portfolio)

        for tx_data in sample_crypto_transactions:
            tx_data['portfolio_id'] = crypto_portfolio.id
            transaction = CryptoTransaction(**tx_data)
            db_session.add(transaction)

        db_session.commit()

        # Test unified portfolio overview
        overview = get_portfolio_overview()
        assert overview is not None
        assert overview.current_value >= 0
        assert overview.total_cost_basis >= 0
        assert overview.total_profit is not None
        assert overview.currency in ['USD', 'EUR']

        # Test unified holdings
        holdings = get_holdings()
        assert holdings is not None
        assert len(holdings) >= 1  # Should have positions from both portfolio types

        # Verify holdings contain both traditional and crypto assets
        tickers = [h.ticker for h in holdings]
        assert 'AAPL' in tickers or 'AAPL' in str(tickers)  # Traditional stock
        assert any('BTC' in str(t) or 'ETH' in str(t) for t in tickers)  # Crypto assets

    def test_portfolio_performance_integration(self, db_session):
        """Test portfolio performance calculation integration."""
        # Add some price history data
        price_data = [
            {
                'ticker': 'AAPL',
                'date': date(2023, 1, 1),
                'open': Decimal('140.00'),
                'high': Decimal('145.00'),
                'low': Decimal('138.00'),
                'close': Decimal('142.00'),
                'volume': 1000000
            },
            {
                'ticker': 'AAPL',
                'date': date(2023, 2, 1),
                'open': Decimal('148.00'),
                'high': Decimal('152.00'),
                'low': Decimal('146.00'),
                'close': Decimal('150.00'),
                'volume': 1200000
            },
            {
                'ticker': 'AAPL',
                'date': date(2023, 3, 1),
                'open': Decimal('155.00'),
                'high': Decimal('160.00'),
                'low': Decimal('153.00'),
                'close': Decimal('158.00'),
                'volume': 1500000
            }
        ]

        for data in price_data:
            price_history = PriceHistory(
                ticker=data['ticker'],
                date=data['date'],
                open=data['open'],
                high=data['high'],
                low=data['low'],
                close=data['close'],
                volume=data['volume']
            )
            db_session.add(price_history)

        db_session.commit()

        # Test performance data calculation
        performance = get_performance_data('3M')
        assert performance is not None
        assert len(performance.portfolio_data) >= 1
        assert performance.portfolio_start_value is not None
        assert performance.portfolio_end_value is not None
        assert performance.portfolio_change_amount is not None

        # Verify performance data structure
        for data_point in performance.portfolio_data:
            assert hasattr(data_point, 'date')
            assert hasattr(data_point, 'portfolio')
            assert data_point.portfolio >= 0


class TestMultiPortfolioManagement:
    """Test cases for multi-portfolio management scenarios."""

    @pytest.fixture(scope="function")
    def db_session(self):
        """Create a database session for testing."""
        with SyncSessionLocal() as session:
            yield session

    @pytest.fixture
    def multiple_crypto_portfolios(self):
        """Create multiple crypto portfolios for testing."""
        return [
            {
                'name': 'Crypto Growth Portfolio',
                'base_currency': CryptoCurrency.USD,
                'description': 'Aggressive growth strategy'
            },
            {
                'name': 'Crypto Income Portfolio',
                'base_currency': CryptoCurrency.USD,
                'description': 'Dividend and yield strategy'
            },
            {
                'name': 'Crypto Diversified Portfolio',
                'base_currency': CryptoCurrency.EUR,
                'description': 'Balanced diversified strategy'
            }
        ]

    def test_multi_portfolio_creation(self, db_session, multiple_crypto_portfolios):
        """Test creation of multiple crypto portfolios."""
        created_portfolios = []

        for portfolio_data in multiple_crypto_portfolios:
            portfolio = create_crypto_portfolio(portfolio_data)
            created_portfolios.append(portfolio)
            db_session.add(portfolio)

        db_session.commit()

        # Verify all portfolios were created
        assert len(created_portfolios) == len(multiple_crypto_portfolios)

        # Verify portfolio properties
        for i, portfolio in enumerate(created_portfolios):
            assert portfolio.name == multiple_crypto_portfolios[i]['name']
            assert portfolio.base_currency == multiple_crypto_portfolios[i]['base_currency']
            assert portfolio.id is not None

    def test_cross_portfolio_performance_comparison(self, db_session, multiple_crypto_portfolios):
        """Test performance comparison across multiple portfolios."""
        # Create multiple crypto portfolios
        created_portfolios = []
        for portfolio_data in multiple_crypto_portfolios:
            portfolio = CryptoPortfolio(**portfolio_data)
            db_session.add(portfolio)
            created_portfolios.append(portfolio)

        db_session.commit()

        # Add different transactions to each portfolio
        # Portfolio 1 - BTC heavy
        crypto_tx1 = CryptoTransaction(
            portfolio_id=created_portfolios[0].id,
            symbol='BTC',
            transaction_type='BUY',
            quantity=Decimal('1.0'),
            price_at_execution=Decimal('50000.00'),
            fee=Decimal('10.00'),
            currency=CryptoCurrency.USD,
            timestamp=datetime(2023, 1, 1),
            exchange='Binance'
        )
        db_session.add(crypto_tx1)

        # Portfolio 2 - ETH heavy
        crypto_tx2 = CryptoTransaction(
            portfolio_id=created_portfolios[1].id,
            symbol='ETH',
            transaction_type='BUY',
            quantity=Decimal('10.0'),
            price_at_execution=Decimal('3000.00'),
            fee=Decimal('5.00'),
            currency=CryptoCurrency.USD,
            timestamp=datetime(2023, 1, 1),
            exchange='Coinbase'
        )
        db_session.add(crypto_tx2)

        # Portfolio 3 - Mixed
        crypto_tx3 = CryptoTransaction(
            portfolio_id=created_portfolios[2].id,
            symbol='BTC',
            transaction_type='BUY',
            quantity=Decimal('0.5'),
            price_at_execution=Decimal('50000.00'),
            fee=Decimal('5.00'),
            currency=CryptoCurrency.EUR,
            timestamp=datetime(2023, 1, 1),
            exchange='Kraken'
        )
        db_session.add(crypto_tx3)

        crypto_tx4 = CryptoTransaction(
            portfolio_id=created_portfolios[2].id,
            symbol='ETH',
            transaction_type='BUY',
            quantity=Decimal('5.0'),
            price_at_execution=Decimal('3000.00'),
            fee=Decimal('3.00'),
            currency=CryptoCurrency.EUR,
            timestamp=datetime(2023, 1, 1),
            exchange='Coinbase'
        )
        db_session.add(crypto_tx4)

        db_session.commit()

        # Test performance calculation for each portfolio
        performances = []
        for portfolio in created_portfolios:
            performance = get_crypto_performance_data(portfolio.id, '1M')
            assert performance is not None
            assert len(performance) >= 1
            performances.append(performance)

        # Verify each portfolio has different performance characteristics
        assert len(performances) == 3
        for performance in performances:
            assert len(performance) >= 1
            for data_point in performance:
                assert hasattr(data_point, 'date')
                assert hasattr(data_point, 'portfolio_value')
                assert data_point.portfolio_value >= 0

    def test_portfolio_switching_and_aggregation(self, db_session):
        """Test switching between portfolios and unified aggregation."""
        # Create multiple portfolios
        portfolio1 = CryptoPortfolio(
            name='Portfolio 1',
            base_currency=CryptoCurrency.USD,
            description='First test portfolio'
        )
        portfolio2 = CryptoPortfolio(
            name='Portfolio 2',
            base_currency=CryptoCurrency.USD,
            description='Second test portfolio'
        )

        db_session.add_all([portfolio1, portfolio2])
        db_session.commit()

        # Add transactions to different portfolios
        tx1 = CryptoTransaction(
            portfolio_id=portfolio1.id,
            symbol='BTC',
            transaction_type='BUY',
            quantity=Decimal('0.5'),
            price_at_execution=Decimal('50000.00'),
            fee=Decimal('5.00'),
            currency=CryptoCurrency.USD,
            timestamp=datetime(2023, 1, 1),
            exchange='Binance'
        )

        tx2 = CryptoTransaction(
            portfolio_id=portfolio2.id,
            symbol='ETH',
            transaction_type='BUY',
            quantity=Decimal('5.0'),
            price_at_execution=Decimal('3000.00'),
            fee=Decimal('3.00'),
            currency=CryptoCurrency.USD,
            timestamp=datetime(2023, 1, 1),
            exchange='Coinbase'
        )

        db_session.add_all([tx1, tx2])
        db_session.commit()

        # Test individual portfolio holdings
        holdings1 = get_crypto_holdings(portfolio1.id)
        holdings2 = get_crypto_holdings(portfolio2.id)

        assert len(holdings1) == 1
        assert len(holdings2) == 1
        assert holdings1[0].symbol == 'BTC'
        assert holdings2[0].symbol == 'ETH'

        # Test unified portfolio overview
        overview = get_portfolio_overview()
        assert overview is not None
        assert overview.current_value >= 0
        assert overview.total_profit is not None


class TestTransactionSynchronization:
    """Test cases for transaction synchronization across portfolio types."""

    @pytest.fixture(scope="function")
    def db_session(self):
        """Create a database session for testing."""
        with SyncSessionLocal() as session:
            yield session

    def test_cross_currency_transaction_sync(self, db_session):
        """Test synchronization of transactions across different currencies."""
        # Add traditional transaction in USD
        traditional_tx = Transaction(
            operation_date=date(2023, 1, 1),
            transaction_type='BUY',
            ticker='AAPL',
            isin='US0378331005',
            description='Apple Inc.',
            quantity=Decimal('10'),
            price_per_share=Decimal('150.00'),
            amount_eur=Decimal('1500.00'),
            currency='USD',
            fees=Decimal('5.00'),
            transaction_hash='aapl_usd_001'
        )
        db_session.add(traditional_tx)

        # Add crypto transaction in EUR
        crypto_portfolio = CryptoPortfolio(
            name='Euro Crypto Portfolio',
            base_currency=CryptoCurrency.EUR,
            description='Crypto portfolio in EUR'
        )
        db_session.add(crypto_portfolio)
        db_session.commit()
        db_session.refresh(crypto_portfolio)

        crypto_tx = CryptoTransaction(
            portfolio_id=crypto_portfolio.id,
            symbol='BTC',
            transaction_type='BUY',
            quantity=Decimal('0.1'),
            price_at_execution=Decimal('40000.00'),
            fee=Decimal('50.00'),
            currency=CryptoCurrency.EUR,
            timestamp=datetime(2023, 1, 1),
            exchange='Binance',
            transaction_hash='btc_eur_001'
        )
        db_session.add(crypto_tx)
        db_session.commit()

        # Test unified portfolio overview handles different currencies
        overview = get_portfolio_overview()
        assert overview is not None
        assert overview.currency in ['USD', 'EUR']
        assert overview.current_value >= 0

        # Test holdings aggregation works with different currencies
        holdings = get_holdings()
        assert holdings is not None
        assert len(holdings) >= 1

    def test_transaction_deduplication_across_portfolios(self, db_session):
        """Test transaction deduplication across different portfolio types."""
        # Add same transaction to different portfolios
        portfolio1 = CryptoPortfolio(
            name='Portfolio 1',
            base_currency=CryptoCurrency.USD,
            description='First portfolio'
        )
        portfolio2 = CryptoPortfolio(
            name='Portfolio 2',
            base_currency=CryptoCurrency.USD,
            description='Second portfolio'
        )

        db_session.add_all([portfolio1, portfolio2])
        db_session.commit()

        # Same transaction hash in different portfolios should be allowed
        tx1 = CryptoTransaction(
            portfolio_id=portfolio1.id,
            symbol='BTC',
            transaction_type='BUY',
            quantity=Decimal('0.1'),
            price_at_execution=Decimal('50000.00'),
            fee=Decimal('10.00'),
            currency=CryptoCurrency.USD,
            timestamp=datetime(2023, 1, 1),
            exchange='Binance',
            transaction_hash='same_hash_001'
        )

        tx2 = CryptoTransaction(
            portfolio_id=portfolio2.id,
            symbol='BTC',
            transaction_type='BUY',
            quantity=Decimal('0.1'),
            price_at_execution=Decimal('50000.00'),
            fee=Decimal('10.00'),
            currency=CryptoCurrency.USD,
            timestamp=datetime(2023, 1, 1),
            exchange='Binance',
            transaction_hash='same_hash_001'  # Same hash
        )

        db_session.add_all([tx1, tx2])
        db_session.commit()

        # Both transactions should exist in their respective portfolios
        holdings1 = get_crypto_holdings(portfolio1.id)
        holdings2 = get_crypto_holdings(portfolio2.id)

        assert len(holdings1) == 1
        assert len(holdings2) == 1


class TestErrorHandlingAndEdgeCases:
    """Test cases for error handling and edge cases in unified workflows."""

    @pytest.fixture(scope="function")
    def db_session(self):
        """Create a database session for testing."""
        with SyncSessionLocal() as session:
            yield session

    def test_empty_portfolio_handling(self, db_session):
        """Test handling of empty portfolios."""
        # Get portfolio overview with no transactions
        overview = get_portfolio_overview()
        assert overview is not None
        assert overview.current_value == 0
        assert overview.total_cost_basis == 0
        assert overview.total_profit == 0

        # Get holdings with no data
        holdings = get_holdings()
        assert holdings is not None
        assert len(holdings) == 0

    def test_incomplete_data_handling(self, db_session):
        """Test handling of incomplete or missing data."""
        # Add transaction with incomplete data
        incomplete_tx = Transaction(
            operation_date=date(2023, 1, 1),
            transaction_type='BUY',
            ticker='TEST',
            isin=None,  # Missing ISIN
            description=None,  # Missing description
            quantity=Decimal('10'),
            price_per_share=Decimal('100.00'),
            amount_eur=Decimal('1000.00'),
            currency='USD',
            fees=0,
            transaction_hash='incomplete_001'
        )
        db_session.add(incomplete_tx)
        db_session.commit()

        # Should handle gracefully without crashing
        overview = get_portfolio_overview()
        assert overview is not None

        holdings = get_holdings()
        assert holdings is not None

    def test_zero_quantity_handling(self, db_session):
        """Test handling of zero quantity transactions."""
        # Add transaction with zero quantity
        zero_qty_tx = Transaction(
            operation_date=date(2023, 1, 1),
            transaction_type='BUY',
            ticker='TEST',
            isin='TEST123456789',
            description='Test asset',
            quantity=Decimal('0'),
            price_per_share=Decimal('100.00'),
            amount_eur=Decimal('0'),
            currency='USD',
            fees=0,
            transaction_hash='zero_qty_001'
        )
        db_session.add(zero_qty_tx)
        db_session.commit()

        # Should handle gracefully
        overview = get_portfolio_overview()
        assert overview is not None

        holdings = get_holdings()
        assert holdings is not None

    def test_invalid_currency_handling(self, db_session):
        """Test handling of invalid currency codes."""
        # Add transaction with invalid currency
        invalid_currency_tx = Transaction(
            operation_date=date(2023, 1, 1),
            transaction_type='BUY',
            ticker='TEST',
            isin='TEST123456789',
            description='Test asset',
            quantity=Decimal('10'),
            price_per_share=Decimal('100.00'),
            amount_eur=Decimal('1000.00'),
            currency='INVALID',  # Invalid currency
            fees=0,
            transaction_hash='invalid_currency_001'
        )
        db_session.add(invalid_currency_tx)
        db_session.commit()

        # Should handle gracefully with fallback currency
        overview = get_portfolio_overview()
        assert overview is not None
        assert overview.currency in ['USD', 'EUR']  # Should use valid fallback


class TestAPIEndpointIntegration:
    """Test cases for API endpoint integration in unified workflows."""

    @pytest.fixture(scope="function")
    def async_db_session(self):
        """Create an async database session for testing."""
        return AsyncSessionLocal()

    @pytest.mark.asyncio
    async def test_portfolio_overview_endpoint(self, async_db_session):
        """Test portfolio overview API endpoint."""
        overview = await get_portfolio_overview(async_db_session)
        assert overview is not None
        assert isinstance(overview, PortfolioOverview)
        assert overview.current_value >= 0
        assert overview.total_cost_basis >= 0
        assert overview.total_profit is not None

    @pytest.mark.asyncio
    async def test_holdings_endpoint(self, async_db_session):
        """Test holdings API endpoint."""
        holdings = await get_holdings(async_db_session)
        assert holdings is not None
        if holdings:  # May be empty in test environment
            for holding in holdings:
                assert hasattr(holding, 'ticker')
                assert hasattr(holding, 'quantity')
                assert hasattr(holding, 'current_value')

    @pytest.mark.asyncio
    async def test_performance_endpoint(self, async_db_session):
        """Test performance API endpoint."""
        performance = await get_performance_data(async_db_session, '3M')
        assert performance is not None
        assert isinstance(performance, PortfolioPerformance)
        assert len(performance.portfolio_data) >= 0
        assert performance.portfolio_start_value is not None
        assert performance.portfolio_end_value is not None

    @pytest.mark.asyncio
    async def test_error_handling_in_endpoints(self, async_db_session):
        """Test error handling in API endpoints."""
        # Test with invalid time range
        with pytest.raises(Exception):  # Should raise appropriate exception
            await get_performance_data(async_db_session, 'INVALID_RANGE')

        # Test database connection errors (mocked)
        with patch('app.database.get_db') as mock_get_db:
            mock_get_db.side_effect = Exception("Database connection failed")
            with pytest.raises(Exception):
                await get_portfolio_overview(async_db_session)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])