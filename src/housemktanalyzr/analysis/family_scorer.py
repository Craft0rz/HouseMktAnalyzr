"""Family home scoring engine for owner-occupied houses.

Evaluates houses on three pillars:
- Livability (0-40): walk score, transit, safety, schools, parks
- Value (0-35): price vs assessment, price/sqft, affordability, market trend
- Space & Comfort (0-25): lot size, bedrooms, condition, property age

Also calculates cost of ownership: mortgage, taxes, energy, insurance, welcome tax.

Thresholds are calibrated for the Quebec/Montreal real estate market (2024-2026).
"""

import logging
import math
from datetime import date

from .calculator import InvestmentCalculator
from ..models.property import FamilyHomeMetrics, PropertyListing

logger = logging.getLogger(__name__)

# Shared calculator instance for mortgage calculations
_calculator = InvestmentCalculator()


# Quebec welcome tax (mutation tax) brackets — standard provincial rates.
# Montreal has additional brackets (over $1M at 2.5%, over $2M at 3.0%)
# but we use standard Quebec brackets for simplicity.
WELCOME_TAX_BRACKETS = [
    (58_900, 0.005),      # First $58,900 at 0.5%
    (294_600, 0.010),     # $58,900 to $294,600 at 1.0%
    (500_000, 0.015),     # $294,600 to $500,000 at 1.5%
    (float("inf"), 0.02), # Over $500,000 at 2.0%
]

# Energy cost per sqft per month based on construction era
ENERGY_RATES = {
    "pre_1970": 0.045,     # Poorly insulated
    "1970_1990": 0.035,
    "1990_2010": 0.028,
    "post_2010": 0.022,
    "fallback": 0.035,     # No year_built available
}

# Insurance rate: ~0.35% of property value (Quebec average for houses)
INSURANCE_RATE = 0.0035

# CMHC insurance premium (simplified): 3.5% of mortgage amount
CMHC_PREMIUM_RATE = 0.035


class FamilyHomeScorer:
    """Score houses for family livability using a 3-pillar model.

    Pillars:
    - Livability (0-40 pts): walkability, transit, safety, schools, parks
    - Value (0-35 pts): price vs assessment, $/sqft, monthly cost, market trend
    - Space & Comfort (0-25 pts): lot size, bedrooms, condition, age

    Total: 0-100 pts

    Example:
        scorer = FamilyHomeScorer()
        metrics = scorer.score_property(listing, safety_score=7.5)
        print(f"Family Score: {metrics.family_score}/100")
    """

    def __init__(
        self,
        down_payment_pct: float = 0.05,
        interest_rate: float = 0.05,
        amortization_years: int = 25,
    ):
        """Initialize scorer with mortgage parameters.

        Args:
            down_payment_pct: Down payment percentage (default 5% for owner-occupied/CMHC insured).
            interest_rate: Annual mortgage interest rate (default 5%).
            amortization_years: Amortization period in years (default 25).
        """
        self.down_payment_pct = down_payment_pct
        self.interest_rate = interest_rate
        self.amortization_years = amortization_years

    # =========================================================================
    # Main Scoring Method
    # =========================================================================

    def score_property(
        self,
        listing: PropertyListing,
        safety_score: float | None = None,
        school_distance_m: float | None = None,
        park_count_1km: int | None = None,
        flood_zone: bool | None = None,
        contaminated_nearby: bool | None = None,
        price_drops: list[dict] | None = None,
        days_on_market: int | None = None,
    ) -> FamilyHomeMetrics:
        """Score a house listing for family livability.

        Args:
            listing: PropertyListing to score (should be property_type=HOUSE).
            safety_score: Neighbourhood safety score (0-10) from open data.
            school_distance_m: Distance to nearest elementary school in metres.
            park_count_1km: Number of parks within 1km.
            flood_zone: Whether property is in a flood zone.
            contaminated_nearby: Whether contaminated site is nearby.
            price_drops: List of price change dicts with change_pct and recorded_at.
            days_on_market: Number of days the listing has been on market.

        Returns:
            FamilyHomeMetrics with all scores, cost breakdown, and data completeness.
        """
        breakdown = {}
        completeness: dict[str, bool] = {}

        # --- Livability Pillar (0-40) ---
        livability_score, livability_breakdown, livability_completeness = (
            self._score_livability(
                listing, safety_score, school_distance_m, park_count_1km
            )
        )
        breakdown.update(livability_breakdown)
        completeness.update(livability_completeness)

        # --- Value Pillar (0-35) ---
        value_score, value_breakdown, cost_data, value_completeness = (
            self._score_value(listing, price_drops, days_on_market)
        )
        breakdown.update(value_breakdown)
        completeness.update(value_completeness)

        # --- Space & Comfort Pillar (0-25) ---
        space_score, space_breakdown, space_completeness = self._score_space(listing)
        breakdown.update(space_breakdown)
        completeness.update(space_completeness)

        # --- Total ---
        family_score = round(livability_score + value_score + space_score, 1)

        # --- Cost of Ownership ---
        welcome_tax = self._calculate_welcome_tax(listing.price)
        down_payment = int(listing.price * self.down_payment_pct)
        cmhc_premium = int((listing.price - down_payment) * CMHC_PREMIUM_RATE)
        # Total cash needed: down payment + welcome tax + CMHC premium
        total_cash_needed = down_payment + welcome_tax + cmhc_premium

        return FamilyHomeMetrics(
            property_id=listing.id,
            purchase_price=listing.price,
            family_score=family_score,
            score_breakdown=breakdown,
            # Livability
            livability_score=round(livability_score, 1),
            walk_score_pts=livability_breakdown.get("walk_score_pts"),
            transit_score_pts=livability_breakdown.get("transit_score_pts"),
            safety_pts=livability_breakdown.get("safety_pts"),
            school_proximity_pts=livability_breakdown.get("school_proximity_pts"),
            parks_pts=livability_breakdown.get("parks_pts"),
            # Value
            value_score=round(value_score, 1),
            price_vs_assessment_pts=value_breakdown.get("price_vs_assessment_pts"),
            price_per_sqft=cost_data.get("price_per_sqft"),
            price_per_sqft_pts=value_breakdown.get("price_per_sqft_pts"),
            monthly_cost_estimate=cost_data.get("monthly_cost_estimate"),
            affordability_pts=value_breakdown.get("affordability_pts"),
            market_trajectory_pts=value_breakdown.get("market_trajectory_pts"),
            # Space & Comfort
            space_score=round(space_score, 1),
            lot_size_pts=space_breakdown.get("lot_size_pts"),
            bedroom_pts=space_breakdown.get("bedroom_pts"),
            condition_pts=space_breakdown.get("condition_pts"),
            age_pts=space_breakdown.get("age_pts"),
            # Cost of ownership
            estimated_monthly_mortgage=cost_data.get("monthly_mortgage"),
            estimated_monthly_taxes=cost_data.get("monthly_taxes"),
            estimated_annual_energy=cost_data.get("annual_energy"),
            estimated_annual_insurance=cost_data.get("annual_insurance"),
            welcome_tax=welcome_tax,
            total_cash_needed=total_cash_needed,
            # Risk flags
            flood_zone=flood_zone,
            contaminated_nearby=contaminated_nearby,
            # Raw input values for frontend tooltip display
            raw_school_distance_m=school_distance_m,
            raw_park_count_1km=park_count_1km,
            raw_safety_score=safety_score,
            raw_days_on_market=days_on_market,
            # Data completeness
            data_completeness=completeness,
        )

    # =========================================================================
    # Livability Pillar (0-40)
    # =========================================================================

    def _score_livability(
        self,
        listing: PropertyListing,
        safety_score: float | None,
        school_distance_m: float | None,
        park_count_1km: int | None,
    ) -> tuple[float, dict[str, float], dict[str, bool]]:
        """Score livability pillar (0-40 pts).

        Components:
        - Walk Score (0-8): from listing.walk_score
        - Transit Score (0-8): from listing.transit_score
        - Safety (0-8): from neighbourhood safety data
        - School Proximity (0-10): from geo enrichment
        - Parks Nearby (0-6): from geo enrichment
        """
        breakdown: dict[str, float] = {}
        completeness: dict[str, bool] = {}
        total = 0.0

        # Walk Score (0-8 pts)
        completeness["walk_score"] = listing.walk_score is not None
        if listing.walk_score is not None:
            if listing.walk_score >= 70:
                pts = 8.0
            elif listing.walk_score >= 50:
                pts = 5.0
            elif listing.walk_score >= 30:
                pts = 3.0
            else:
                pts = 0.0
            breakdown["walk_score_pts"] = pts
            total += pts

        # Transit Score (0-8 pts)
        completeness["transit_score"] = listing.transit_score is not None
        if listing.transit_score is not None:
            if listing.transit_score >= 70:
                pts = 8.0
            elif listing.transit_score >= 50:
                pts = 5.0
            elif listing.transit_score >= 30:
                pts = 3.0
            else:
                pts = 0.0
            breakdown["transit_score_pts"] = pts
            total += pts

        # Safety (0-8 pts)
        completeness["safety"] = safety_score is not None
        if safety_score is not None:
            if safety_score >= 7:
                pts = 8.0
            elif safety_score >= 5:
                pts = 5.0
            elif safety_score >= 3:
                pts = 3.0
            else:
                pts = 0.0
            breakdown["safety_pts"] = pts
            total += pts

        # School Proximity (0-10 pts) — uses Quebec geo enrichment data
        # Widened radius thresholds for Quebec (many suburban areas)
        completeness["school_proximity"] = school_distance_m is not None
        if school_distance_m is not None:
            if school_distance_m <= 800:
                pts = 10.0
            elif school_distance_m <= 1200:
                pts = 7.0
            elif school_distance_m <= 1800:
                pts = 4.0
            elif school_distance_m <= 2500:
                pts = 2.0
            else:
                pts = 0.0
            breakdown["school_proximity_pts"] = pts
            total += pts

        # Parks Nearby (0-6 pts) — uses Quebec geo enrichment data
        completeness["parks"] = park_count_1km is not None
        if park_count_1km is not None:
            if park_count_1km >= 3:
                pts = 6.0
            elif park_count_1km >= 2:
                pts = 4.0
            elif park_count_1km >= 1:
                pts = 2.0
            else:
                pts = 0.0
            breakdown["parks_pts"] = pts
            total += pts

        # Cap at 40
        total = min(40.0, total)
        return total, breakdown, completeness

    # =========================================================================
    # Value Pillar (0-35)
    # =========================================================================

    def _score_value(
        self,
        listing: PropertyListing,
        price_drops: list[dict] | None = None,
        days_on_market: int | None = None,
    ) -> tuple[float, dict[str, float], dict, dict[str, bool]]:
        """Score value pillar (0-35 pts) and compute cost data.

        Components:
        - Price vs Municipal Assessment (0-10)
        - Price per sqft (0-8)
        - Affordability / Monthly Cost (0-10)
        - Market Trajectory (0-7): price drops + days on market

        Returns:
            (score, breakdown, cost_data, completeness)
        """
        breakdown: dict[str, float] = {}
        cost_data: dict = {}
        completeness: dict[str, bool] = {}
        total = 0.0

        # --- Price vs Municipal Assessment (0-10 pts) ---
        completeness["municipal_assessment"] = (
            listing.municipal_assessment is not None
            and listing.municipal_assessment > 0
        )
        if listing.municipal_assessment and listing.municipal_assessment > 0:
            ratio = listing.price / listing.municipal_assessment
            if ratio <= 0.90:
                pts = 10.0
            elif ratio <= 1.00:
                pts = 8.0
            elif ratio <= 1.10:
                pts = 5.0
            elif ratio <= 1.25:
                pts = 2.0
            else:
                pts = 0.0
            breakdown["price_vs_assessment_pts"] = pts
            total += pts

        # --- Price per sqft (0-8 pts) ---
        # Thresholds adjusted for Quebec market (Montreal avg ~$350-450/sqft)
        completeness["sqft"] = listing.sqft is not None and listing.sqft > 0
        if listing.sqft and listing.sqft > 0:
            price_per_sqft = listing.price / listing.sqft
            cost_data["price_per_sqft"] = round(price_per_sqft, 2)

            if price_per_sqft < 300:
                pts = 8.0
            elif price_per_sqft < 400:
                pts = 6.0
            elif price_per_sqft < 500:
                pts = 4.0
            elif price_per_sqft < 600:
                pts = 2.0
            else:
                pts = 0.0
            breakdown["price_per_sqft_pts"] = pts
            total += pts

        # --- Affordability / Monthly Cost (0-10 pts) ---
        # Calculate total monthly cost = mortgage + taxes/12 + insurance/12 + energy/12
        down_payment = int(listing.price * self.down_payment_pct)
        mortgage_principal = listing.price - down_payment
        # Add CMHC insurance premium to principal
        cmhc_premium = int(mortgage_principal * CMHC_PREMIUM_RATE)
        insured_principal = mortgage_principal + cmhc_premium

        monthly_mortgage = _calculator.calculate_mortgage_payment(
            principal=insured_principal,
            annual_rate=self.interest_rate,
            amortization_years=self.amortization_years,
        )
        cost_data["monthly_mortgage"] = monthly_mortgage

        # Monthly taxes
        monthly_taxes = 0
        if listing.annual_taxes and listing.annual_taxes > 0:
            monthly_taxes = listing.annual_taxes // 12
        else:
            # Estimate: ~1.2% of property value
            monthly_taxes = int(listing.price * 0.012 / 12)
        cost_data["monthly_taxes"] = monthly_taxes

        # Annual energy estimate
        annual_energy = self._estimate_annual_energy(listing.year_built, listing.sqft)
        cost_data["annual_energy"] = annual_energy

        # Annual insurance estimate
        annual_insurance = int(listing.price * INSURANCE_RATE)
        cost_data["annual_insurance"] = annual_insurance

        # Total monthly cost
        monthly_cost = (
            monthly_mortgage
            + monthly_taxes
            + (annual_insurance // 12)
            + (annual_energy // 12)
        )
        cost_data["monthly_cost_estimate"] = monthly_cost

        # Affordability scoring — adjusted for Quebec market (2024-2026 rates)
        if monthly_cost < 3000:
            pts = 10.0
        elif monthly_cost < 3500:
            pts = 8.0
        elif monthly_cost < 4000:
            pts = 6.0
        elif monthly_cost < 4500:
            pts = 4.0
        elif monthly_cost < 5500:
            pts = 2.0
        else:
            pts = 0.0
        breakdown["affordability_pts"] = pts
        total += pts

        # --- Market Trajectory (0-7 pts) ---
        # Price drops and extended days on market signal buyer-favorable conditions
        trajectory_pts = self._score_market_trajectory(price_drops, days_on_market)
        has_market_data = price_drops is not None or days_on_market is not None
        completeness["market_trajectory"] = has_market_data
        if has_market_data:
            breakdown["market_trajectory_pts"] = trajectory_pts
        total += trajectory_pts

        # Cap at 35
        total = min(35.0, total)
        return total, breakdown, cost_data, completeness

    @staticmethod
    def _score_market_trajectory(
        price_drops: list[dict] | None,
        days_on_market: int | None,
    ) -> float:
        """Score market trajectory (0-7 pts).

        Buyer-favorable signals:
        - Price drops indicate seller motivation (0-4 pts)
        - Extended time on market suggests negotiating room (0-3 pts)
        """
        pts = 0.0

        # Price drop signals (0-4 pts)
        if price_drops:
            # Count meaningful drops (> 1% reduction)
            drops = [d for d in price_drops if d.get("change_pct", 0) < -1.0]
            total_drop_pct = sum(abs(d.get("change_pct", 0)) for d in drops)

            if total_drop_pct >= 10:
                pts += 4.0  # Major reduction (10%+)
            elif total_drop_pct >= 5:
                pts += 3.0  # Significant reduction (5-10%)
            elif total_drop_pct >= 2:
                pts += 2.0  # Moderate reduction (2-5%)
            elif drops:
                pts += 1.0  # At least one drop

        # Days on market signals (0-3 pts)
        if days_on_market is not None:
            if days_on_market >= 90:
                pts += 3.0  # Very stale — strong negotiating position
            elif days_on_market >= 60:
                pts += 2.0  # Getting stale
            elif days_on_market >= 30:
                pts += 1.0  # Some leverage

        return min(7.0, pts)

    # =========================================================================
    # Space & Comfort Pillar (0-25)
    # =========================================================================

    def _score_space(
        self, listing: PropertyListing
    ) -> tuple[float, dict[str, float], dict[str, bool]]:
        """Score space & comfort pillar (0-25 pts).

        Components:
        - Lot Size (0-8)
        - Bedrooms (0-7)
        - Condition (0-6)
        - Property Age (0-4)
        """
        breakdown: dict[str, float] = {}
        completeness: dict[str, bool] = {}
        total = 0.0

        # Lot Size (0-8 pts)
        completeness["lot_sqft"] = listing.lot_sqft is not None
        if listing.lot_sqft is not None:
            if listing.lot_sqft >= 8000:
                pts = 8.0
            elif listing.lot_sqft >= 6000:
                pts = 6.0
            elif listing.lot_sqft >= 4000:
                pts = 4.0
            elif listing.lot_sqft >= 2500:
                pts = 2.0
            else:
                pts = 0.0
            breakdown["lot_size_pts"] = pts
            total += pts

        # Bedrooms (0-7 pts)
        if listing.bedrooms >= 4:
            pts = 7.0
        elif listing.bedrooms == 3:
            pts = 5.0
        elif listing.bedrooms == 2:
            pts = 2.0
        else:
            pts = 0.0
        breakdown["bedroom_pts"] = pts
        total += pts

        # Condition (0-6 pts) from AI condition_score
        completeness["condition_score"] = listing.condition_score is not None
        if listing.condition_score is not None:
            if listing.condition_score >= 8:
                pts = 6.0
            elif listing.condition_score >= 6:
                pts = 4.0
            elif listing.condition_score >= 4:
                pts = 2.0
            else:
                pts = 0.0
            breakdown["condition_pts"] = pts
            total += pts

        # Property Age (0-4 pts)
        # Adjusted for Quebec: many heritage homes are well-maintained
        completeness["year_built"] = listing.year_built is not None
        if listing.year_built is not None:
            current_year = date.today().year
            age = current_year - listing.year_built
            if age <= 10:
                pts = 4.0
            elif age <= 25:
                pts = 3.0
            elif age <= 50:
                pts = 2.0
            elif age <= 100:
                pts = 1.0
            else:
                pts = 0.0
            breakdown["age_pts"] = pts
            total += pts

        # Cap at 25
        total = min(25.0, total)
        return total, breakdown, completeness

    # =========================================================================
    # Cost of Ownership Helpers
    # =========================================================================

    @staticmethod
    def _calculate_welcome_tax(price: int) -> int:
        """Calculate Quebec welcome tax (mutation tax).

        Standard Quebec brackets:
        - First $58,900 at 0.5%
        - $58,900 to $294,600 at 1.0%
        - $294,600 to $500,000 at 1.5%
        - Over $500,000 at 2.0%

        Args:
            price: Purchase price in CAD.

        Returns:
            Welcome tax amount in CAD.
        """
        tax = 0
        prev_threshold = 0

        for threshold, rate in WELCOME_TAX_BRACKETS:
            if price <= prev_threshold:
                break
            taxable = min(price, threshold) - prev_threshold
            if taxable > 0:
                tax += taxable * rate
            prev_threshold = threshold

        return int(math.ceil(tax))

    @staticmethod
    def _estimate_annual_energy(
        year_built: int | None, sqft: int | None
    ) -> int:
        """Estimate annual energy cost based on construction era and size.

        Args:
            year_built: Year property was built (or None).
            sqft: Living area in sqft (or None).

        Returns:
            Estimated annual energy cost in CAD.
        """
        if sqft is None or sqft <= 0:
            # Fallback: assume average 1,500 sqft house
            sqft = 1500

        if year_built is None:
            rate = ENERGY_RATES["fallback"]
        elif year_built < 1970:
            rate = ENERGY_RATES["pre_1970"]
        elif year_built < 1990:
            rate = ENERGY_RATES["1970_1990"]
        elif year_built < 2010:
            rate = ENERGY_RATES["1990_2010"]
        else:
            rate = ENERGY_RATES["post_2010"]

        monthly_cost = sqft * rate
        return int(math.ceil(monthly_cost * 12))
