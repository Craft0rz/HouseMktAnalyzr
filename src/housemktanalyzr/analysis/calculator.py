"""Investment metrics calculator for multi-family property analysis.

This module provides comprehensive investment analysis tools for evaluating
rental properties, including cap rate, cash-on-cash return, GRM, and more.
"""

import logging
import math
from typing import Optional

from ..enrichment.cmhc import CMHCRentalData
from ..models.property import InvestmentMetrics, PropertyListing

logger = logging.getLogger(__name__)


# Default expense ratios for Quebec multi-family properties
# These are industry-standard estimates; actual expenses vary by property
DEFAULT_EXPENSE_RATIOS = {
    "property_tax_pct": 0.012,  # ~1.2% of value (Montreal average)
    "insurance_pct": 0.004,  # ~0.4% of value
    "maintenance_pct": 0.08,  # ~8% of rent
    "vacancy_pct": 0.02,  # ~2% vacancy rate (Montreal is tight)
    "management_pct": 0.00,  # 0% if self-managed, 5-8% if hired
    "total_expense_ratio": 0.35,  # ~35% of gross rent goes to expenses
}

# Scoring weights for investment quality
SCORING_WEIGHTS = {
    "cap_rate": 0.25,  # Higher cap rate = better
    "cash_flow": 0.25,  # Positive cash flow = better
    "price_per_unit": 0.20,  # Lower price per unit = better
    "gross_yield": 0.15,  # Higher yield = better
    "grm": 0.15,  # Lower GRM = better
}


class InvestmentCalculator:
    """Calculate investment metrics for multi-family property analysis.

    Provides methods for calculating cap rate, cash-on-cash return,
    gross rent multiplier, and other key investment metrics.

    Example:
        calc = InvestmentCalculator()

        # Quick cap rate calculation
        cap = calc.cap_rate(price=500000, noi=25000)
        print(f"Cap rate: {cap:.1f}%")

        # Full property analysis
        metrics = calc.analyze_property(listing)
        print(f"Score: {metrics.score}/100")
    """

    def __init__(self, cmhc_data: Optional[CMHCRentalData] = None):
        """Initialize calculator with CMHC rental data.

        Args:
            cmhc_data: Optional CMHCRentalData instance for rent estimates.
                      Creates new instance if not provided.
        """
        self.cmhc = cmhc_data or CMHCRentalData()

    # =========================================================================
    # Core Investment Metrics
    # =========================================================================

    def gross_rental_yield(self, price: int, annual_rent: int) -> float:
        """Calculate gross rental yield percentage.

        Gross yield = (Annual Rent / Purchase Price) × 100

        Args:
            price: Purchase price in CAD
            annual_rent: Total annual rent in CAD

        Returns:
            Gross rental yield as percentage (e.g., 6.5 for 6.5%)
        """
        if price <= 0:
            return 0.0
        return (annual_rent / price) * 100

    def cap_rate(self, price: int, noi: int) -> float:
        """Calculate capitalization rate.

        Cap Rate = (NOI / Purchase Price) × 100

        The cap rate is the most common metric for comparing investment
        properties. Higher cap rate = higher return (but often higher risk).

        Args:
            price: Purchase price in CAD
            noi: Net Operating Income (annual rent minus expenses, before mortgage)

        Returns:
            Cap rate as percentage (e.g., 5.0 for 5%)
        """
        if price <= 0:
            return 0.0
        return (noi / price) * 100

    def gross_rent_multiplier(self, price: int, annual_rent: int) -> float:
        """Calculate Gross Rent Multiplier (GRM).

        GRM = Purchase Price / Annual Rent

        Lower GRM means you're paying less per dollar of rent.
        Typical range: 8-15 for multi-family in Montreal area.

        Args:
            price: Purchase price in CAD
            annual_rent: Total annual rent in CAD

        Returns:
            GRM as a multiplier (e.g., 12.5)
        """
        if annual_rent <= 0:
            return float("inf")
        return price / annual_rent

    def cash_on_cash_return(
        self,
        annual_cash_flow: int,
        total_cash_invested: int,
    ) -> float:
        """Calculate cash-on-cash return percentage.

        CoC Return = (Annual Cash Flow / Total Cash Invested) × 100

        Measures the return on the actual cash you invested (down payment
        + closing costs), not the total property value.

        Args:
            annual_cash_flow: Annual cash flow after all expenses and mortgage
            total_cash_invested: Total cash invested (down payment + closing costs)

        Returns:
            Cash-on-cash return as percentage (e.g., 8.0 for 8%)
        """
        if total_cash_invested <= 0:
            return 0.0
        return (annual_cash_flow / total_cash_invested) * 100

    def estimate_noi(
        self,
        annual_rent: int,
        expense_ratio: float = 0.35,
    ) -> int:
        """Estimate Net Operating Income using expense ratio.

        NOI = Annual Rent × (1 - Expense Ratio)

        Args:
            annual_rent: Total annual rent in CAD
            expense_ratio: Percentage of rent going to expenses (default 35%)

        Returns:
            Estimated NOI in CAD
        """
        return int(annual_rent * (1 - expense_ratio))

    def estimate_monthly_expenses(
        self,
        monthly_rent: int,
        property_value: int,
        expense_ratio: Optional[float] = None,
    ) -> int:
        """Estimate monthly operating expenses.

        Args:
            monthly_rent: Monthly rental income
            property_value: Property value for tax/insurance estimates
            expense_ratio: Optional override for expense ratio

        Returns:
            Estimated monthly expenses in CAD
        """
        if expense_ratio is not None:
            return int(monthly_rent * expense_ratio)

        # Detailed breakdown
        monthly_tax = int(property_value * DEFAULT_EXPENSE_RATIOS["property_tax_pct"] / 12)
        monthly_insurance = int(property_value * DEFAULT_EXPENSE_RATIOS["insurance_pct"] / 12)
        monthly_maintenance = int(monthly_rent * DEFAULT_EXPENSE_RATIOS["maintenance_pct"])
        monthly_vacancy = int(monthly_rent * DEFAULT_EXPENSE_RATIOS["vacancy_pct"])
        monthly_management = int(monthly_rent * DEFAULT_EXPENSE_RATIOS["management_pct"])

        return monthly_tax + monthly_insurance + monthly_maintenance + monthly_vacancy + monthly_management

    def estimate_monthly_cash_flow(
        self,
        monthly_rent: int,
        monthly_mortgage: int,
        monthly_expenses: Optional[int] = None,
        expense_ratio: float = 0.35,
    ) -> int:
        """Estimate monthly cash flow.

        Cash Flow = Rent - Expenses - Mortgage Payment

        Args:
            monthly_rent: Total monthly rent from all units
            monthly_mortgage: Monthly mortgage payment (P&I)
            monthly_expenses: Optional explicit monthly expenses
            expense_ratio: Expense ratio if monthly_expenses not provided

        Returns:
            Monthly cash flow in CAD (can be negative)
        """
        if monthly_expenses is None:
            monthly_expenses = int(monthly_rent * expense_ratio)

        return monthly_rent - monthly_expenses - monthly_mortgage

    # =========================================================================
    # Mortgage Calculations
    # =========================================================================

    def calculate_mortgage_payment(
        self,
        principal: int,
        annual_rate: float,
        amortization_years: int = 25,
    ) -> int:
        """Calculate monthly mortgage payment.

        Uses Canadian mortgage formula with semi-annual compounding.

        Args:
            principal: Loan amount (price - down payment)
            annual_rate: Annual interest rate (e.g., 0.05 for 5%)
            amortization_years: Amortization period in years (default 25)

        Returns:
            Monthly payment in CAD
        """
        if principal <= 0 or annual_rate <= 0:
            return 0

        # Canadian mortgages use semi-annual compounding
        # Convert to effective monthly rate
        semi_annual_rate = annual_rate / 2
        monthly_rate = (1 + semi_annual_rate) ** (1 / 6) - 1

        # Number of payments
        n_payments = amortization_years * 12

        # Standard amortization formula
        payment = principal * (
            monthly_rate * (1 + monthly_rate) ** n_payments
        ) / ((1 + monthly_rate) ** n_payments - 1)

        return int(math.ceil(payment))

    def calculate_down_payment(
        self,
        price: int,
        down_payment_pct: float = 0.20,
    ) -> int:
        """Calculate required down payment.

        Note: Investment properties in Canada require minimum 20% down.

        Args:
            price: Purchase price in CAD
            down_payment_pct: Down payment percentage (default 20%)

        Returns:
            Down payment amount in CAD
        """
        return int(price * down_payment_pct)

    def calculate_total_cash_needed(
        self,
        price: int,
        down_payment_pct: float = 0.20,
        closing_costs_pct: float = 0.03,
    ) -> int:
        """Calculate total cash needed to close.

        Total = Down Payment + Closing Costs

        Closing costs typically include:
        - Welcome tax (Quebec): ~1-2%
        - Notary fees: ~$1,000-2,000
        - Inspection: ~$500-1,000
        - Appraisal: ~$300-500

        Args:
            price: Purchase price in CAD
            down_payment_pct: Down payment percentage (default 20%)
            closing_costs_pct: Closing costs percentage (default 3%)

        Returns:
            Total cash needed in CAD
        """
        down_payment = self.calculate_down_payment(price, down_payment_pct)
        closing_costs = int(price * closing_costs_pct)
        return down_payment + closing_costs

    # =========================================================================
    # Rent Estimation
    # =========================================================================

    def estimate_rent_from_listing(self, listing: PropertyListing) -> int:
        """Estimate monthly rent for a property.

        Uses this priority:
        1. Listed gross_revenue (if available) / 12
        2. CMHC data based on city, bedrooms, and units

        Args:
            listing: PropertyListing to estimate rent for

        Returns:
            Estimated total monthly rent in CAD
        """
        # Use listed gross revenue if available
        if listing.gross_revenue and listing.gross_revenue > 0:
            return listing.gross_revenue // 12

        # Use estimated_rent if set
        if listing.estimated_rent and listing.estimated_rent > 0:
            return listing.estimated_rent

        # Estimate using CMHC data
        # Assume bedrooms are distributed evenly across units
        if listing.units > 0 and listing.bedrooms > 0:
            beds_per_unit = max(1, listing.bedrooms // listing.units)
            rent_per_unit = self.cmhc.get_estimated_rent(listing.city, beds_per_unit)
            return rent_per_unit * listing.units

        # Fallback: use total bedrooms
        return self.cmhc.get_estimated_rent(listing.city, listing.bedrooms)

    # =========================================================================
    # Full Property Analysis
    # =========================================================================

    def analyze_property(
        self,
        listing: PropertyListing,
        down_payment_pct: float = 0.20,
        interest_rate: float = 0.05,
        expense_ratio: float = 0.35,
    ) -> InvestmentMetrics:
        """Perform full investment analysis on a property.

        Calculates all investment metrics and returns a complete
        InvestmentMetrics object.

        Args:
            listing: PropertyListing to analyze
            down_payment_pct: Down payment percentage (default 20%)
            interest_rate: Mortgage interest rate (default 5%)
            expense_ratio: Operating expense ratio (default 35%)

        Returns:
            InvestmentMetrics with all calculated values
        """
        price = listing.price

        # Estimate rent
        monthly_rent = self.estimate_rent_from_listing(listing)
        annual_rent = monthly_rent * 12

        # Calculate NOI
        noi = self.estimate_noi(annual_rent, expense_ratio)

        # Calculate mortgage
        down_payment = self.calculate_down_payment(price, down_payment_pct)
        principal = price - down_payment
        monthly_mortgage = self.calculate_mortgage_payment(principal, interest_rate)

        # Calculate cash flow
        monthly_expenses = int(monthly_rent * expense_ratio)
        monthly_cash_flow = self.estimate_monthly_cash_flow(
            monthly_rent, monthly_mortgage, monthly_expenses
        )

        # Calculate metrics
        gross_yield = self.gross_rental_yield(price, annual_rent)
        cap = self.cap_rate(price, noi)
        grm = self.gross_rent_multiplier(price, annual_rent)

        # Cash-on-cash return
        total_cash = self.calculate_total_cash_needed(price, down_payment_pct)
        annual_cash_flow = monthly_cash_flow * 12
        coc_return = self.cash_on_cash_return(annual_cash_flow, total_cash)

        # Price per unit
        price_per_unit = price // listing.units if listing.units > 0 else price

        # Price per sqft
        price_per_sqft = None
        if listing.sqft and listing.sqft > 0:
            price_per_sqft = round(price / listing.sqft, 2)

        # Calculate score
        score, breakdown = self._calculate_score(
            cap_rate=cap,
            cash_flow=monthly_cash_flow,
            price_per_unit=price_per_unit,
            gross_yield=gross_yield,
            grm=grm,
        )

        return InvestmentMetrics(
            property_id=listing.id,
            purchase_price=price,
            estimated_monthly_rent=monthly_rent,
            gross_rental_yield=round(gross_yield, 2),
            cap_rate=round(cap, 2) if cap > 0 else None,
            price_per_unit=price_per_unit,
            price_per_sqft=price_per_sqft,
            cash_flow_monthly=round(monthly_cash_flow, 2),
            score=round(score, 1),
            score_breakdown=breakdown,
        )

    def _calculate_score(
        self,
        cap_rate: float,
        cash_flow: int,
        price_per_unit: int,
        gross_yield: float,
        grm: float,
    ) -> tuple[float, dict[str, float]]:
        """Calculate investment score (0-100) with breakdown.

        Scoring criteria (Montreal multi-family market):
        - Cap rate: 5%+ is good, 7%+ is excellent
        - Cash flow: Positive is good, $200+/unit is excellent
        - Price per unit: <$200k is good, <$150k is excellent
        - Gross yield: 6%+ is good, 8%+ is excellent
        - GRM: <12 is good, <10 is excellent
        """
        breakdown = {}

        # Cap rate score (0-25 points)
        # 4% = 10pts, 5% = 15pts, 6% = 20pts, 7%+ = 25pts
        if cap_rate >= 7:
            cap_score = 25
        elif cap_rate >= 6:
            cap_score = 20
        elif cap_rate >= 5:
            cap_score = 15
        elif cap_rate >= 4:
            cap_score = 10
        else:
            cap_score = max(0, cap_rate * 2.5)
        breakdown["cap_rate"] = round(cap_score, 1)

        # Cash flow score (0-25 points)
        # Negative = 0, break-even = 10, $200/mo = 15, $400/mo = 20, $600+ = 25
        if cash_flow >= 600:
            cf_score = 25
        elif cash_flow >= 400:
            cf_score = 20
        elif cash_flow >= 200:
            cf_score = 15
        elif cash_flow >= 0:
            cf_score = 10
        else:
            cf_score = max(0, 10 + cash_flow / 50)  # Deduct for negative
        breakdown["cash_flow"] = round(cf_score, 1)

        # Price per unit score (0-20 points)
        # <$150k = 20, <$200k = 15, <$250k = 10, <$300k = 5
        if price_per_unit < 150000:
            ppu_score = 20
        elif price_per_unit < 200000:
            ppu_score = 15
        elif price_per_unit < 250000:
            ppu_score = 10
        elif price_per_unit < 300000:
            ppu_score = 5
        else:
            ppu_score = max(0, 5 - (price_per_unit - 300000) / 100000)
        breakdown["price_per_unit"] = round(ppu_score, 1)

        # Gross yield score (0-15 points)
        # 5% = 5, 6% = 8, 7% = 10, 8%+ = 15
        if gross_yield >= 8:
            yield_score = 15
        elif gross_yield >= 7:
            yield_score = 10
        elif gross_yield >= 6:
            yield_score = 8
        elif gross_yield >= 5:
            yield_score = 5
        else:
            yield_score = max(0, gross_yield)
        breakdown["gross_yield"] = round(yield_score, 1)

        # GRM score (0-15 points)
        # <10 = 15, <12 = 10, <14 = 5, >14 = 0
        if grm < 10:
            grm_score = 15
        elif grm < 12:
            grm_score = 10
        elif grm < 14:
            grm_score = 5
        else:
            grm_score = max(0, 5 - (grm - 14))
        breakdown["grm"] = round(grm_score, 1)

        total_score = sum(breakdown.values())
        return min(100, total_score), breakdown
