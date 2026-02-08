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


# Default expense ratios for Quebec multi-family properties.
# Sources: CMHC 2025 Rental Market Report, Quebec bank underwriting models,
# CORPIQ/TAL guidelines, SoumissionsAssurances.ca broker data.
DEFAULT_EXPENSE_RATIOS = {
    "property_tax_pct": 0.012,  # ~1.2% of value (Quebec average, fallback only)
    "insurance_pct": 0.005,  # ~0.5% of value (QC broker avg 0.45-0.59%)
    "maintenance_pct": 0.10,  # ~10% of rent (bank model: 8-15%; older stock: 10-12%)
    "vacancy_pct": 0.03,  # ~3% (CMHC avg ~2.9%, bank standard 5%)
    "management_pct": 0.05,  # 5% of rent (industry standard; 0% only if self-managed)
    "capex_reserve_pct": 0.05,  # 5% of rent for capital expenditure reserves (roof, foundation, plumbing)
    "total_expense_ratio": 0.45,  # ~45% of gross rent (bank model midpoint with management + capex)
}

# Quebec TAL (Tribunal administratif du logement) rent increase guideline.
# Updated annually; this is used for rent control warnings on multi-unit properties.
TAL_GUIDELINE_INCREASE_PCT = 3.3  # 2025 guideline ~3.3% (varies by component)

# Two-pillar scoring: Financial (70) + Location & Quality (30) = 100
SCORING_WEIGHTS = {
    # Financial pillar (0-70)
    "cap_rate": 25,       # Higher cap rate = better
    "cash_flow": 25,      # Positive cash flow = better
    "price_per_unit": 20, # Lower price per unit = better
    # Location & Quality pillar (0-30)
    "safety": 8,          # Low crime = better
    "vacancy": 7,         # Low vacancy = high demand
    "rent_growth": 7,     # Rising rents = upside
    "affordability": 4,   # Rent-to-income sweet spot
    "condition": 4,       # AI-assessed property condition
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
        Typical range: 8-15 for multi-family in Quebec.

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
        expense_ratio: float = 0.45,
    ) -> int:
        """Estimate Net Operating Income using expense ratio.

        NOI = Annual Rent × (1 - Expense Ratio)

        Args:
            annual_rent: Total annual rent in CAD
            expense_ratio: Percentage of rent going to expenses (default 40%)

        Returns:
            Estimated NOI in CAD
        """
        return int(annual_rent * (1 - expense_ratio))

    def estimate_monthly_expenses(
        self,
        monthly_rent: int,
        property_value: int,
        expense_ratio: Optional[float] = None,
        annual_taxes: Optional[int] = None,
        total_expenses: Optional[int] = None,
    ) -> int:
        """Estimate monthly operating expenses.

        Priority:
        1. Actual total_expenses from Centris (most accurate)
        2. Detailed breakdown using actual annual_taxes + estimated rest
        3. Flat expense_ratio percentage

        Args:
            monthly_rent: Monthly rental income
            property_value: Property value for tax/insurance estimates
            expense_ratio: Optional override for expense ratio
            annual_taxes: Actual annual taxes from Centris (if available)
            total_expenses: Actual annual total expenses from Centris (if available)

        Returns:
            Estimated monthly expenses in CAD
        """
        # Priority 1: Use actual Centris total expenses (includes taxes, insurance, etc.)
        if total_expenses and total_expenses > 0:
            return total_expenses // 12

        # Priority 2: Flat ratio override
        if expense_ratio is not None:
            return int(monthly_rent * expense_ratio)

        # Priority 3: Detailed breakdown using actual taxes where available
        if annual_taxes and annual_taxes > 0:
            monthly_tax = annual_taxes // 12
        else:
            monthly_tax = int(property_value * DEFAULT_EXPENSE_RATIOS["property_tax_pct"] / 12)

        monthly_insurance = int(property_value * DEFAULT_EXPENSE_RATIOS["insurance_pct"] / 12)
        monthly_maintenance = int(monthly_rent * DEFAULT_EXPENSE_RATIOS["maintenance_pct"])
        monthly_vacancy = int(monthly_rent * DEFAULT_EXPENSE_RATIOS["vacancy_pct"])
        monthly_management = int(monthly_rent * DEFAULT_EXPENSE_RATIOS["management_pct"])
        monthly_capex = int(monthly_rent * DEFAULT_EXPENSE_RATIOS["capex_reserve_pct"])

        return (
            monthly_tax + monthly_insurance + monthly_maintenance
            + monthly_vacancy + monthly_management + monthly_capex
        )

    def estimate_monthly_cash_flow(
        self,
        monthly_rent: int,
        monthly_mortgage: int,
        monthly_expenses: Optional[int] = None,
        expense_ratio: float = 0.45,
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
        amortization_years: int = 30,
    ) -> int:
        """Calculate monthly mortgage payment.

        Uses Canadian mortgage formula with semi-annual compounding.

        Args:
            principal: Loan amount (price - down payment)
            annual_rate: Annual interest rate (e.g., 0.05 for 5%)
            amortization_years: Amortization period in years (default 30)

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

    def estimate_rent_from_listing(
        self, listing: PropertyListing
    ) -> tuple[int, str]:
        """Estimate monthly rent for a property.

        Uses this priority:
        1. Listed gross_revenue (if available) / 12
        2. CMHC data based on city, bedrooms, and units

        Args:
            listing: PropertyListing to estimate rent for

        Returns:
            Tuple of (estimated total monthly rent in CAD, source label)
            Source is "declared" for Centris gross revenue, "cmhc_estimate" for CMHC averages.
        """
        # Use listed gross revenue if available
        if listing.gross_revenue and listing.gross_revenue > 0:
            return listing.gross_revenue // 12, "declared"

        # Use estimated_rent if set
        if listing.estimated_rent and listing.estimated_rent > 0:
            return listing.estimated_rent, "declared"

        # Estimate using CMHC data
        # Assume bedrooms are distributed evenly across units
        if listing.units > 0 and listing.bedrooms > 0:
            beds_per_unit = max(1, listing.bedrooms // listing.units)
            rent_per_unit = self.cmhc.get_estimated_rent(listing.city, beds_per_unit)
            return rent_per_unit * listing.units, "cmhc_estimate"

        # Fallback: use total bedrooms
        return self.cmhc.get_estimated_rent(listing.city, listing.bedrooms), "cmhc_estimate"

    # =========================================================================
    # Full Property Analysis
    # =========================================================================

    def analyze_property(
        self,
        listing: PropertyListing,
        down_payment_pct: float = 0.20,
        interest_rate: float = 0.05,
        expense_ratio: float = 0.45,
    ) -> InvestmentMetrics:
        """Perform full investment analysis on a property.

        Calculates all investment metrics and returns a complete
        InvestmentMetrics object. Uses actual Centris data (annual_taxes)
        when available, falls back to percentage-based estimates.

        Args:
            listing: PropertyListing to analyze
            down_payment_pct: Down payment percentage (default 20%)
            interest_rate: Mortgage interest rate (default 5%)
            expense_ratio: Operating expense ratio (default 40%)

        Returns:
            InvestmentMetrics with all calculated values
        """
        price = listing.price

        # Estimate rent
        monthly_rent, rent_source = self.estimate_rent_from_listing(listing)
        annual_rent = monthly_rent * 12

        # Calculate expenses using actual Centris data when available
        monthly_expenses = self.estimate_monthly_expenses(
            monthly_rent=monthly_rent,
            property_value=price,
            annual_taxes=listing.annual_taxes,
            total_expenses=listing.total_expenses,
        )

        # Calculate NOI from detailed expenses
        noi = annual_rent - (monthly_expenses * 12)

        # Calculate mortgage
        down_payment = self.calculate_down_payment(price, down_payment_pct)
        principal = price - down_payment
        monthly_mortgage = self.calculate_mortgage_payment(principal, interest_rate)

        # Calculate cash flow
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

        # Rent vs market comparison: always compute CMHC estimate so we
        # can show how declared revenue compares to market averages.
        cmhc_estimated_rent = None
        rent_vs_market_pct = None
        if rent_source == "declared":
            if listing.units > 0 and listing.bedrooms > 0:
                beds_per_unit = max(1, listing.bedrooms // listing.units)
                cmhc_estimated_rent = (
                    self.cmhc.get_estimated_rent(listing.city, beds_per_unit)
                    * listing.units
                )
            else:
                cmhc_estimated_rent = self.cmhc.get_estimated_rent(
                    listing.city, listing.bedrooms
                )
            if cmhc_estimated_rent and cmhc_estimated_rent > 0:
                rent_vs_market_pct = round(
                    ((monthly_rent - cmhc_estimated_rent) / cmhc_estimated_rent) * 100,
                    1,
                )

        # Price per unit
        price_per_unit = price // listing.units if listing.units > 0 else price

        # Price per sqft
        price_per_sqft = None
        if listing.sqft and listing.sqft > 0:
            price_per_sqft = round(price / listing.sqft, 2)

        # Rate sensitivity: cash flow at base, -1.5%, +1.5%
        rate_sensitivity = self._compute_rate_sensitivity(
            principal=principal,
            base_rate=interest_rate,
            monthly_rent=monthly_rent,
            monthly_expenses=monthly_expenses,
        )

        # TAL rent control warning for multi-unit properties
        rent_control_risk = None
        if listing.units >= 2:
            rent_control_risk = (
                f"Quebec rent control (TAL): existing tenant rents increase "
                f"~{TAL_GUIDELINE_INCREASE_PCT}%/yr. Market rents may not apply "
                f"to occupied units."
            )

        # Calculate financial score (0-70 pillar)
        score, breakdown = self._calculate_score(
            cap_rate=cap,
            cash_flow=monthly_cash_flow,
            price_per_unit=price_per_unit,
        )

        return InvestmentMetrics(
            property_id=listing.id,
            purchase_price=price,
            estimated_monthly_rent=monthly_rent,
            rent_source=rent_source,
            cmhc_estimated_rent=cmhc_estimated_rent,
            rent_vs_market_pct=rent_vs_market_pct,
            gross_rental_yield=round(gross_yield, 2),
            cap_rate=round(cap, 2) if cap > 0 else None,
            price_per_unit=price_per_unit,
            price_per_sqft=price_per_sqft,
            cash_flow_monthly=round(monthly_cash_flow, 2),
            score=round(score, 1),
            score_breakdown=breakdown,
            rate_sensitivity=rate_sensitivity,
            rent_control_risk=rent_control_risk,
        )

    @staticmethod
    def calculate_location_score(
        safety_score: float | None = None,
        vacancy_rate: float | None = None,
        rent_cagr: float | None = None,
        rent_to_income: float | None = None,
        condition_score: float | None = None,
    ) -> tuple[float, dict[str, float]]:
        """Calculate Location & Quality score (0-30 points).

        This is the second pillar of the two-pillar scoring system.
        Combined with the Financial pillar (0-70), the total is 0-100.

        Args:
            safety_score: 0-10 score from open data crime stats
            vacancy_rate: CMHC vacancy rate percentage (lower is better)
            rent_cagr: 5-year CAGR of rents in the zone (higher = appreciating)
            rent_to_income: Rent-to-income ratio % (sweet spot 20-30%)
            condition_score: AI-assessed property condition (1-10)

        Returns:
            (total_score, breakdown_dict) where total_score is 0-30
        """
        breakdown = {}

        # Safety: 0-8 points
        if safety_score is not None:
            if safety_score >= 7:
                breakdown["neighbourhood_safety"] = 8.0
            elif safety_score >= 5:
                breakdown["neighbourhood_safety"] = 5.0
            elif safety_score >= 3:
                breakdown["neighbourhood_safety"] = 3.0
            else:
                breakdown["neighbourhood_safety"] = 0.0

        # Low vacancy = high demand: 0-7 points
        if vacancy_rate is not None:
            if vacancy_rate < 1.0:
                breakdown["neighbourhood_vacancy"] = 7.0
            elif vacancy_rate < 2.0:
                breakdown["neighbourhood_vacancy"] = 5.0
            elif vacancy_rate < 3.0:
                breakdown["neighbourhood_vacancy"] = 3.0
            else:
                breakdown["neighbourhood_vacancy"] = 0.0

        # Rent appreciation (CAGR 5yr): 0-7 points
        if rent_cagr is not None:
            if rent_cagr >= 4.0:
                breakdown["neighbourhood_rent_growth"] = 7.0
            elif rent_cagr >= 2.5:
                breakdown["neighbourhood_rent_growth"] = 5.0
            elif rent_cagr >= 1.5:
                breakdown["neighbourhood_rent_growth"] = 3.0
            else:
                breakdown["neighbourhood_rent_growth"] = 0.0

        # Rent affordability (rent-to-income ratio): 0-4 points
        if rent_to_income is not None:
            if 20 <= rent_to_income <= 28:
                breakdown["neighbourhood_affordability"] = 4.0
            elif 15 <= rent_to_income <= 32:
                breakdown["neighbourhood_affordability"] = 2.0
            else:
                breakdown["neighbourhood_affordability"] = 0.0

        # Property condition: 0-4 points
        if condition_score is not None:
            if condition_score >= 8:
                breakdown["condition"] = 4.0
            elif condition_score >= 6:
                breakdown["condition"] = 3.0
            elif condition_score >= 4:
                breakdown["condition"] = 2.0
            elif condition_score >= 2:
                breakdown["condition"] = 1.0
            else:
                breakdown["condition"] = 0.0

        total = min(30.0, sum(breakdown.values()))
        return total, breakdown

    def _compute_rate_sensitivity(
        self,
        principal: int,
        base_rate: float,
        monthly_rent: int,
        monthly_expenses: int,
    ) -> dict[str, float]:
        """Compute cash flow at base rate and +/- 1.5% for stress testing."""
        results = {}
        for label, rate in [
            ("low", max(0.01, base_rate - 0.015)),
            ("base", base_rate),
            ("high", base_rate + 0.015),
        ]:
            mortgage = self.calculate_mortgage_payment(principal, rate)
            cf = monthly_rent - monthly_expenses - mortgage
            results[f"{label}_rate"] = round(rate * 100, 2)
            results[f"{label}_cash_flow"] = round(cf, 2)
            results[f"{label}_mortgage"] = mortgage
        return results

    def _calculate_score(
        self,
        cap_rate: float,
        cash_flow: int,
        price_per_unit: int,
    ) -> tuple[float, dict[str, float]]:
        """Calculate financial investment score (0-70) with breakdown.

        This is the Financial pillar of the two-pillar scoring system.
        The Location & Quality pillar (0-30) is added separately via
        calculate_location_score().

        Scoring criteria (Quebec multi-family market):
        - Cap rate (0-25): 5%+ is good, 7%+ is excellent
        - Cash flow (0-25): Positive is good, $200+/mo is excellent
        - Price per unit (0-20): <$200k is good, <$150k is excellent
        """
        breakdown = {}

        # Cap rate score (0-25 points)
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
        if cash_flow >= 600:
            cf_score = 25
        elif cash_flow >= 400:
            cf_score = 20
        elif cash_flow >= 200:
            cf_score = 15
        elif cash_flow >= 0:
            cf_score = 10
        else:
            cf_score = max(0, 10 + cash_flow / 50)
        breakdown["cash_flow"] = round(cf_score, 1)

        # Price per unit score (0-20 points)
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

        total_score = sum(breakdown.values())
        return min(70, total_score), breakdown
