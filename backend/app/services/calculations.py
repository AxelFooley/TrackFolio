"""
Financial calculations service.

Implements IRR, TWR, and portfolio metrics as per PRD Section 5.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
import numpy_financial as npf
from scipy.optimize import newton
import logging

logger = logging.getLogger(__name__)


class FinancialCalculations:
    """Financial calculations for portfolio metrics."""

    @staticmethod
    def calculate_irr(
        cash_flows: List[Tuple[date, Decimal]],
        current_value: Decimal,
        current_date: date = None
    ) -> Optional[float]:
        """
        Calculate Internal Rate of Return (IRR) using XIRR methodology.

        From PRD Section 5.1:
        - All purchase dates & amounts as negative cash flows (amount + fees)
        - Current value as positive cash flow at today's date

        Args:
            cash_flows: List of (date, amount) tuples. Negative for investments.
            current_value: Current value of the position
            current_date: Date for current value (defaults to today)

        Returns:
            Annual IRR as decimal (e.g., 0.15 for 15%), or None if calculation fails
        """
        if not cash_flows:
            return None

        if current_date is None:
            current_date = date.today()

        try:
            # Prepare arrays for XIRR calculation
            dates = [cf[0] for cf in cash_flows] + [current_date]
            amounts = [float(cf[1]) for cf in cash_flows] + [float(current_value)]

            # Convert dates to number of days from first date
            first_date = min(dates)
            days = [(d - first_date).days for d in dates]
            years = [d / 365.25 for d in days]

            # Calculate IRR using Newton's method
            # XIRR formula: NPV = sum(amount / (1 + rate)^year) = 0

            def xnpv(rate: float, values: List[float], dates: List[float]) -> float:
                """Calculate XNPV for given rate."""
                return sum(v / (1 + rate) ** d for v, d in zip(values, dates))

            def xnpv_derivative(rate: float, values: List[float], dates: List[float]) -> float:
                """Calculate derivative of XNPV."""
                return sum(-d * v / (1 + rate) ** (d + 1) for v, d in zip(values, dates))

            # Use Newton's method to find IRR
            irr = newton(
                func=lambda r: xnpv(r, amounts, years),
                x0=0.1,  # Initial guess: 10%
                fprime=lambda r: xnpv_derivative(r, amounts, years),
                maxiter=100,
                tol=1e-6
            )

            # Sanity check: IRR between -100% and +10000%
            if irr < -0.99 or irr > 99:
                logger.warning(f"IRR calculation returned extreme value: {irr}")
                return None

            return float(irr)

        except (RuntimeError, ValueError, ZeroDivisionError) as e:
            logger.warning(f"IRR calculation failed: {str(e)}")
            return None

    @staticmethod
    def calculate_twr(
        beginning_value: Decimal,
        ending_value: Decimal,
        days: int
    ) -> Optional[float]:
        """
        Calculate Time-Weighted Return (TWR) - annualized.

        From PRD Section 5.1:
        TWR = [(Ending Value / Beginning Value)^(365/days)] - 1

        Args:
            beginning_value: Portfolio value at start
            ending_value: Portfolio value at end
            days: Number of days in period

        Returns:
            Annualized return as decimal (e.g., 0.125 for 12.5%), or None if invalid
        """
        if beginning_value <= 0 or days <= 0:
            return None

        try:
            ratio = float(ending_value) / float(beginning_value)
            if ratio <= 0:
                return None

            # Annualize the return
            twr = (ratio ** (365.25 / days)) - 1

            return float(twr)

        except (ValueError, ZeroDivisionError, OverflowError) as e:
            logger.warning(f"TWR calculation failed: {str(e)}")
            return None

    @staticmethod
    def calculate_average_cost(
        transactions: List[Dict[str, Any]]
    ) -> Decimal:
        """
        Calculate weighted average cost per share.

        From PRD Section 5.2:
        Average Cost = (Total Amount Spent + Total Fees) / Total Shares Acquired

        Args:
            transactions: List of transaction dicts with amount_eur, fees, quantity

        Returns:
            Average cost per share
        """
        total_cost = Decimal("0")
        total_shares = Decimal("0")

        for txn in transactions:
            if txn.get("transaction_type") == "buy":
                total_cost += txn["amount_eur"] + txn.get("fees", Decimal("0"))
                total_shares += txn["quantity"]
            elif txn.get("transaction_type") == "sell":
                # For sells, reduce cost basis proportionally
                if total_shares > 0:
                    avg_cost_so_far = total_cost / total_shares
                    sold_cost = avg_cost_so_far * txn["quantity"]
                    total_cost -= sold_cost
                    total_shares -= txn["quantity"]

        if total_shares <= 0:
            return Decimal("0")

        return total_cost / total_shares

    @staticmethod
    def calculate_cost_basis(
        transactions: List[Dict[str, Any]]
    ) -> Decimal:
        """
        Calculate cost basis for a position.

        From PRD Section 5.2:
        Cost Basis = Sum of (amount + fees) for all purchase transactions
        For sells: Reduce cost basis proportionally

        Args:
            transactions: List of transaction dictionaries

        Returns:
            Current cost basis
        """
        cost_basis = Decimal("0")
        total_shares = Decimal("0")

        for txn in transactions:
            if txn.get("transaction_type") == "buy":
                cost_basis += txn["amount_eur"] + txn.get("fees", Decimal("0"))
                total_shares += txn["quantity"]
            elif txn.get("transaction_type") == "sell":
                # Reduce cost basis proportionally
                if total_shares > 0:
                    avg_cost = cost_basis / total_shares
                    sold_cost = avg_cost * txn["quantity"]
                    cost_basis -= sold_cost
                    total_shares -= txn["quantity"]

        return max(cost_basis, Decimal("0"))

    @staticmethod
    def calculate_unrealized_gain_loss(
        current_value: Decimal,
        cost_basis: Decimal
    ) -> Decimal:
        """
        Calculate unrealized gain/loss.

        From PRD Section 5.2:
        Unrealized Gain/Loss = Current Value - Cost Basis

        Args:
            current_value: Current market value
            cost_basis: Cost basis

        Returns:
            Unrealized gain (positive) or loss (negative)
        """
        return current_value - cost_basis

    @staticmethod
    def calculate_return_percentage(
        current_value: Decimal,
        cost_basis: Decimal
    ) -> Optional[float]:
        """
        Calculate simple return percentage.

        Args:
            current_value: Current market value
            cost_basis: Cost basis

        Returns:
            Return as decimal (e.g., 0.15 for 15%), or None if cost_basis is 0
        """
        if cost_basis <= 0:
            return None

        return float((current_value - cost_basis) / cost_basis)

    @staticmethod
    def calculate_position_quantity(
        transactions: List[Dict[str, Any]]
    ) -> Decimal:
        """
        Calculate current position quantity from transactions.

        Args:
            transactions: List of transaction dictionaries

        Returns:
            Current quantity held
        """
        quantity = Decimal("0")

        for txn in transactions:
            if txn.get("transaction_type") == "buy":
                quantity += txn["quantity"]
            elif txn.get("transaction_type") == "sell":
                quantity -= txn["quantity"]

        return max(quantity, Decimal("0"))

    @staticmethod
    def convert_currency(
        amount: Decimal,
        from_currency: str,
        to_currency: str,
        fx_rate: Decimal
    ) -> Decimal:
        """
        Convert amount between currencies.

        From PRD Section 5.3:
        For USD positions: usd_value / eur_usd_rate

        Args:
            amount: Amount to convert
            from_currency: Source currency (EUR or USD)
            to_currency: Target currency (EUR or USD)
            fx_rate: EUR/USD exchange rate (e.g., 1.10 means 1 EUR = 1.10 USD)

        Returns:
            Converted amount
        """
        if from_currency == to_currency:
            return amount

        if from_currency == "USD" and to_currency == "EUR":
            # Convert USD to EUR: divide by rate
            return amount / fx_rate
        elif from_currency == "EUR" and to_currency == "USD":
            # Convert EUR to USD: multiply by rate
            return amount * fx_rate
        else:
            raise ValueError(f"Unsupported currency conversion: {from_currency} to {to_currency}")
