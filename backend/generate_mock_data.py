"""
Generate comprehensive mock portfolio data for testing TrackFolio application.

Creates realistic 10-year transaction history for 10 different positions
mixing ETFs and Stocks from various markets and sectors.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
from typing import List, Dict, Tuple, Optional
import yfinance as yf
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Portfolio selection - 10 diverse positions
PORTFOLIO_POSITIONS = [
    # US Tech Stocks
    {"ticker": "AAPL", "name": "Apple Inc.", "isin": "US0378331005", "sector": "Technology"},
    {"ticker": "MSFT", "name": "Microsoft Corporation", "isin": "US5949181045", "sector": "Technology"},

    # European Stocks
    {"ticker": "ASML", "name": "ASML Holding NV", "isin": "NL0010273215", "sector": "Semiconductors"},
    {"ticker": "SAP", "name": "SAP SE", "isin": "DE0007164600", "sector": "Software"},

    # US ETFs
    {"ticker": "VOO", "name": "Vanguard S&P 500 ETF", "isin": "US9229083632", "sector": "ETF - US Large Cap"},
    {"ticker": "QQQ", "name": "Invesco QQQ Trust", "isin": "US46090E1038", "sector": "ETF - Nasdaq 100"},

    # International ETFs
    {"ticker": "EFA", "name": "iShares MSCI EAFE ETF", "isin": "US4642872004", "sector": "ETF - International"},
    {"ticker": "EEM", "name": "iShares MSCI Emerging Markets", "isin": "US4642872047", "sector": "ETF - Emerging Markets"},

    # Sector ETFs
    {"ticker": "VGT", "name": "Vanguard Information Technology ETF", "isin": "US92204A7306", "sector": "ETF - Technology"},
    {"ticker": "VPU", "name": "Vanguard Utilities ETF", "isin": "US92204A7033", "sector": "ETF - Utilities"},
]

class MockDataGenerator:
    def __init__(self):
        """
        Initialize the generator's internal state.
        
        Sets up an empty list to collect transaction records and initializes the order reference counter at 1000 for generating unique order identifiers.
        """
        self.transactions = []
        self.order_ref_counter = 1000

    def get_historical_prices(self, ticker: str, start_date: datetime, end_date: datetime) -> Optional[pd.DataFrame]:
        """
        Retrieve historical price series for a given ticker over a date range.
        
        Returns a pandas DataFrame indexed by date containing the historical OHLCV and corporate-action fields produced by yfinance (typically: `Open`, `High`, `Low`, `Close`, `Volume`, `Dividends`, `Stock Splits`), or `None` if prices could not be fetched.
        """
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(start=start_date, end=end_date)
            return hist
        except Exception:
            logger.exception(f"Could not fetch prices for {ticker}")
            return None

    def generate_realistic_prices(self, base_price: float, start_date: datetime, end_date: datetime) -> List[Tuple[datetime, float]]:
        """
        Generate a daily price series between start_date and end_date that simulates realistic market movements with trend and volatility.
        
        The series models a random walk with a small annual trend and daily volatility, skips weekends, rounds prices to two decimals, and enforces a floor so prices never fall below 10% of the provided base_price.
        
        Returns:
            List[Tuple[datetime, float]]: Ordered list of (date, price) tuples for trading days only.
        """
        prices = []
        current_date = start_date
        current_price = base_price

        # Add trend and volatility
        annual_trend = random.uniform(-0.05, 0.15)  # -5% to +15% annual trend
        daily_volatility = random.uniform(0.015, 0.035)  # 1.5% to 3.5% daily volatility

        while current_date <= end_date:
            # Random walk with trend
            daily_return = np.random.normal(annual_trend/252, daily_volatility)
            current_price *= (1 + daily_return)

            # Ensure price doesn't go negative
            current_price = max(current_price, base_price * 0.1)

            prices.append((current_date, round(current_price, 2)))
            current_date += timedelta(days=1)

            # Skip weekends
            while current_date.weekday() >= 5:
                current_date += timedelta(days=1)

        return prices

    def generate_transactions(self):
        """
        Generate a 10-year sequence of transactions for all positions and store them in self.transactions.
        
        Populates the generator's transaction list with simulated buys, sells, dividends and fees for each position in PORTFOLIO_POSITIONS across the date range 2015-01-01 to 2025-01-01. Attempts to obtain a base price from live market data; if unavailable, uses a randomized fallback price.
        """
        start_date = datetime(2015, 1, 1)
        end_date = datetime(2025, 1, 1)

        # Generate base prices for each position
        base_prices = {}
        for position in PORTFOLIO_POSITIONS:
            try:
                # Try to get actual historical price
                stock = yf.Ticker(position["ticker"])
                hist = stock.history(start=start_date, end=start_date + timedelta(days=30))
                if not hist.empty:
                    base_prices[position["ticker"]] = hist['Close'].iloc[0]
                else:
                    # Fallback to realistic base price
                    base_prices[position["ticker"]] = random.uniform(50, 300)
            except Exception:
                logger.exception("Base price fetch failed for %s; using fallback", position["ticker"])
                base_prices[position["ticker"]] = random.uniform(50, 300)

        # Generate transaction schedule for each position
        for position in PORTFOLIO_POSITIONS:
            self._generate_position_transactions(
                position,
                base_prices[position["ticker"]],
                start_date,
                end_date
            )

    def _generate_position_transactions(self, position: Dict, base_price: float, start_date: datetime, end_date: datetime):
        """
        Simulate and append a time series of buy, sell, dividend and fee transactions for a single portfolio position over a date range.
        
        Simulates an investment plan for the given position between start_date and end_date and appends generated transactions to self.transactions. The simulation includes an initial purchase, periodic contributions, occasional rebalancing sells, probabilistic dividend payments, and infrequent random trades; amounts, timings, and frequencies are randomized to produce realistic variation.
        
        Parameters:
            position (Dict): Position metadata; expected keys include "ticker", "isin", and "name".
            base_price (float): Reference price used when generating the synthetic price history and transaction sizes.
            start_date (datetime): Inclusive start of the simulation period.
            end_date (datetime): Inclusive end of the simulation period.
        """
        ticker = position["ticker"]
        isin = position["isin"]
        name = position["name"]

        # Generate price history
        price_history = self.generate_realistic_prices(base_price, start_date, end_date)
        price_dict = {date: price for date, price in price_history}

        # Investment strategy parameters
        initial_investment = random.uniform(5000, 15000)  # Initial investment amount
        regular_contribution = random.uniform(500, 2000)  # Monthly contribution
        rebalance_frequency = random.choice([90, 120, 180])  # Days between rebalancing
        dividend_frequency = random.choice([90, 120, 180])  # Days between dividend payments

        # Track position
        current_shares = 0
        last_transaction_date = start_date
        last_rebalance_date = start_date
        last_dividend_date = start_date

        current_date = start_date + timedelta(days=random.randint(1, 30))  # Start sometime in first month

        while current_date <= end_date:
            # Check if it's a trading day (skip weekends)
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue

            current_price = price_dict.get(current_date, base_price)

            # Initial investment
            if current_shares == 0:
                shares_to_buy = int(initial_investment / current_price)
                if shares_to_buy > 0:
                    self._create_buy_transaction(
                        current_date, ticker, isin, name, shares_to_buy, current_price
                    )
                    current_shares += shares_to_buy
                    last_transaction_date = current_date

            # Regular contributions (monthly)
            elif (current_date - last_transaction_date).days >= random.randint(28, 35):
                if random.random() < 0.8:  # 80% chance of contribution
                    contribution_amount = regular_contribution * random.uniform(0.8, 1.2)
                    shares_to_buy = int(contribution_amount / current_price)
                    if shares_to_buy > 0:
                        self._create_buy_transaction(
                            current_date, ticker, isin, name, shares_to_buy, current_price
                        )
                        current_shares += shares_to_buy
                        last_transaction_date = current_date

            # Rebalancing (sell some shares if position grew too much)
            elif (current_date - last_rebalance_date).days >= rebalance_frequency and current_shares > 0:
                if random.random() < 0.3:  # 30% chance of rebalancing
                    shares_to_sell = int(current_shares * random.uniform(0.1, 0.3))
                    if shares_to_sell > 0:
                        self._create_sell_transaction(
                            current_date, ticker, isin, name, shares_to_sell, current_price
                        )
                        current_shares -= shares_to_sell
                        last_rebalance_date = current_date

            # Dividend payments
            elif (current_date - last_dividend_date).days >= dividend_frequency and current_shares > 0:
                if random.random() < 0.7:  # 70% chance of dividend
                    dividend_per_share = current_price * random.uniform(0.002, 0.008)  # 0.2% - 0.8% dividend
                    dividend_amount = current_shares * dividend_per_share
                    if dividend_amount > 10:  # Only if dividend is meaningful
                        self._create_dividend_transaction(
                            current_date, ticker, isin, name, dividend_amount
                        )
                        last_dividend_date = current_date

            # Random small transactions
            elif random.random() < 0.05:  # 5% chance of random transaction
                if random.random() < 0.6 and current_shares > 0:  # 60% chance of sell
                    shares_to_sell = min(int(current_shares * random.uniform(0.05, 0.2)), current_shares)
                    if shares_to_sell > 0:
                        self._create_sell_transaction(
                            current_date, ticker, isin, name, shares_to_sell, current_price
                        )
                        current_shares -= shares_to_sell
                else:  # Buy
                    shares_to_buy = int(random.uniform(200, 1000) / current_price)
                    if shares_to_buy > 0:
                        self._create_buy_transaction(
                            current_date, ticker, isin, name, shares_to_buy, current_price
                        )
                        current_shares += shares_to_buy

            current_date += timedelta(days=random.randint(1, 5))

    def _create_buy_transaction(self, date: datetime, ticker: str, isin: str, name: str,
                               quantity: int, price: float):
        """
                               Create and record a buy transaction for the given security.
                               
                               Increments the internal order reference, appends a purchase transaction entry (the purchase amount is stored as a negative value in "Importo euro"), and records a corresponding fee transaction linked to the created order.
                               
                               Parameters:
                                   date (datetime): Operation and value date for the transaction.
                                   ticker (str): Security ticker symbol.
                                   isin (str): Security ISIN identifier.
                                   name (str): Security descriptive name used in the transaction description.
                                   quantity (int): Number of shares purchased.
                                   price (float): Price per share in EUR.
                               """
        self.order_ref_counter += 1
        order_ref = f"ORD{self.order_ref_counter:06d}"

        amount_eur = quantity * price
        fee = random.uniform(5, 15)  # Trading fee

        transaction = {
            "Data operazione": date.strftime("%d-%m-%Y"),
            "Data valuta": date.strftime("%d-%m-%Y"),
            "Tipo operazione": "Acquisto",
            "Ticker": ticker,
            "Isin": isin,
            "Protocollo": f"PROT{self.order_ref_counter:06d}",
            "Descrizione": name,
            "Quantità": quantity,
            "Importo euro": -amount_eur,  # Negative for purchases
            "Importo Divisa": amount_eur,
            "Divisa": "EUR",
            "Riferimento ordine": order_ref
        }

        self.transactions.append(transaction)

        # Add corresponding fee transaction
        self._create_fee_transaction(date, order_ref, fee)

    def _create_sell_transaction(self, date: datetime, ticker: str, isin: str, name: str,
                                quantity: int, price: float):
        """
                                Record a sell transaction and its associated fee in the generator's transaction list.
                                
                                Parameters:
                                    date (datetime): Operation and value date for the sale.
                                    ticker (str): Asset ticker symbol.
                                    isin (str): Asset ISIN identifier (may be empty).
                                    name (str): Asset display name used in the description.
                                    quantity (int): Number of shares sold (positive integer).
                                    price (float): Sale price per share in EUR.
                                """
        self.order_ref_counter += 1
        order_ref = f"ORD{self.order_ref_counter:06d}"

        amount_eur = quantity * price
        fee = random.uniform(5, 15)  # Trading fee

        transaction = {
            "Data operazione": date.strftime("%d-%m-%Y"),
            "Data valuta": date.strftime("%d-%m-%Y"),
            "Tipo operazione": "Vendita",
            "Ticker": ticker,
            "Isin": isin,
            "Protocollo": f"PROT{self.order_ref_counter:06d}",
            "Descrizione": name,
            "Quantità": quantity,
            "Importo euro": amount_eur,  # Positive for sales
            "Importo Divisa": amount_eur,
            "Divisa": "EUR",
            "Riferimento ordine": order_ref
        }

        self.transactions.append(transaction)

        # Add corresponding fee transaction
        self._create_fee_transaction(date, order_ref, fee)

    def _create_dividend_transaction(self, date: datetime, ticker: str, isin: str, name: str,
                                   amount: float):
        """
                                   Record a dividend payment transaction for the specified instrument.
                                   
                                   Parameters:
                                       date (datetime): Operation and value date for the dividend.
                                       ticker (str): Instrument ticker symbol.
                                       isin (str): Instrument ISIN identifier.
                                       name (str): Instrument name used in the transaction description.
                                       amount (float): Dividend amount in EUR.
                                   
                                   Side effects:
                                       Increments the generator's internal order reference and appends a transaction entry to self.transactions.
                                   """
        self.order_ref_counter += 1
        order_ref = f"DIV{self.order_ref_counter:06d}"

        transaction = {
            "Data operazione": date.strftime("%d-%m-%Y"),
            "Data valuta": date.strftime("%d-%m-%Y"),
            "Tipo operazione": "Stacco cedola",
            "Ticker": ticker,
            "Isin": isin,
            "Protocollo": f"PROT{self.order_ref_counter:06d}",
            "Descrizione": f"Dividend {name}",
            "Quantità": 0,
            "Importo euro": amount,
            "Importo Divisa": amount,
            "Divisa": "EUR",
            "Riferimento ordine": order_ref
        }

        self.transactions.append(transaction)

    def _create_fee_transaction(self, date: datetime, order_ref: str, amount: float):
        """
        Record a commission/fee transaction and add it to the generator's transactions list.
        
        Parameters:
            date (datetime): Operation and value date for the fee.
            order_ref (str): Order reference to include in the transaction description and reference field.
            amount (float): Fee amount in EUR; recorded as a negative value in "Importo euro" and as a positive value in "Importo Divisa".
        """
        transaction = {
            "Data operazione": date.strftime("%d-%m-%Y"),
            "Data valuta": date.strftime("%d-%m-%Y"),
            "Tipo operazione": "Commissioni",
            "Ticker": "",
            "Isin": "",
            "Protocollo": "",
            "Descrizione": f"Commissioni ordine {order_ref}",
            "Quantità": 0,
            "Importo euro": -amount,  # Negative for fees
            "Importo Divisa": amount,
            "Divisa": "EUR",
            "Riferimento ordine": order_ref
        }

        self.transactions.append(transaction)

    def save_to_csv(self, filename: str):
        """
        Write the generator's accumulated transactions to a CSV file using a Directa-style layout.
        
        The transactions are sorted by the "Data operazione" field (format "%d-%m-%Y") before export. A nine-row Directa header is written first, followed by the transaction table encoded as UTF-8. After writing the file, a summary file is generated alongside the CSV.
        
        Parameters:
            filename (str): Path to the output CSV file.
        """
        # Sort transactions by date
        self.transactions.sort(key=lambda x: datetime.strptime(x["Data operazione"], "%d-%m-%Y"))

        # Create DataFrame
        df = pd.DataFrame(self.transactions)

        # Create Directa header (first 9 rows)
        now_str = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        header_rows = [
            ["Conto : 00000 Sample User"],
            [f"Data estrazione : {now_str}"],
            [""],
            ["Compravendite ordinati per Data Operazione"],
            ["Dal : 04-04-2015"],
            ["al : 01-10-2025"],
            [""],
            ["Il file include i primi 3000 movimenti"],
            [""]
        ]

        # Create header DataFrame
        header_df = pd.DataFrame(header_rows)

        # Combine header and transactions
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            # Write header
            header_df.to_csv(f, header=False, index=False)

            # Write transactions
            df.to_csv(f, index=False)

        logger.info(f"Generated {len(self.transactions)} transactions in {filename}")

        # Generate summary
        self._generate_summary(filename)

    def _generate_summary(self, filename: str):
        """
        Write a human-readable summary of the generated transactions and save it next to the CSV file.
        
        The summary aggregates totals (transactions, buys, sells, dividends, fees), counts unique positions (by ISIN), and the date range of operations, then logs these metrics and writes them to a text file named by replacing the CSV extension with `_summary.txt`.
        
        Parameters:
            filename (str): Path to the CSV file that was written; the summary file is created by replacing the `.csv` suffix with `_summary.txt`.
        """
        summary = {
            'total_transactions': len(self.transactions),
            'buys': len([t for t in self.transactions if t['Tipo operazione'] == 'Acquisto']),
            'sells': len([t for t in self.transactions if t['Tipo operazione'] == 'Vendita']),
            'dividends': len([t for t in self.transactions if t['Tipo operazione'] == 'Stacco cedola']),
            'fees': len([t for t in self.transactions if t['Tipo operazione'] == 'Commissioni']),
            'unique_positions': len(set(t['Isin'] for t in self.transactions if t['Isin'])),
            'date_range': {
                'start': min(t['Data operazione'] for t in self.transactions),
                'end': max(t['Data operazione'] for t in self.transactions)
            }
        }

        logger.info("Portfolio Summary:")
        logger.info(f"  Total Transactions: {summary['total_transactions']}")
        logger.info(f"  Buy Orders: {summary['buys']}")
        logger.info(f"  Sell Orders: {summary['sells']}")
        logger.info(f"  Dividends: {summary['dividends']}")
        logger.info(f"  Fees: {summary['fees']}")
        logger.info(f"  Unique Positions: {summary['unique_positions']}")
        logger.info(f"  Date Range: {summary['date_range']['start']} to {summary['date_range']['end']}")

        # Save summary to file
        summary_filename = filename.replace('.csv', '_summary.txt')
        with open(summary_filename, 'w', encoding='utf-8') as f:
            f.write("Portfolio Mock Data Summary\n")
            f.write("=" * 40 + "\n")
            f.write(f"Total Transactions: {summary['total_transactions']}\n")
            f.write(f"Buy Orders: {summary['buys']}\n")
            f.write(f"Sell Orders: {summary['sells']}\n")
            f.write(f"Dividends: {summary['dividends']}\n")
            f.write(f"Fees: {summary['fees']}\n")
            f.write(f"Unique Positions: {summary['unique_positions']}\n")
            f.write(f"Date Range: {summary['date_range']['start']} to {summary['date_range']['end']}\n")
            f.write("\nPositions:\n")
            for pos in PORTFOLIO_POSITIONS:
                f.write(f"  {pos['ticker']} - {pos['name']} ({pos['sector']})\n")

def main():
    """
    Generate and save a mock portfolio transactions CSV for local use.
    
    Creates a MockDataGenerator, produces a ten-year sequence of mock transactions for predefined positions, writes the result to "mock_portfolio_data.csv", and logs progress and completion.
    """
    logger.info("Generating mock portfolio data...")

    generator = MockDataGenerator()
    generator.generate_transactions()

    output_file = "mock_portfolio_data.csv"
    generator.save_to_csv(output_file)

    logger.info(f"Mock data generation complete! File saved as: {output_file}")
    logger.info("You can now import this file into TrackFolio using the web interface.")

if __name__ == "__main__":
    main()