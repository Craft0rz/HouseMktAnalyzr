"""Family home scoring engine for owner-occupied houses.

Evaluates houses on three pillars:
- Livability (0-35): walk score, transit, safety, schools, parks
- Value (0-35): price vs assessment, price/sqft, affordability, market trend
- Space & Comfort (0-30): lot size, bedrooms, condition, property age

Uses linear interpolation (not hard thresholds) for smooth, fair scoring.
Missing data is handled via per-pillar normalization: scores are computed
only from available data, so missing fields don't penalize the score.

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

# Pillar weights (must sum to 100)
LIVABILITY_MAX = 35.0
VALUE_MAX = 35.0
SPACE_MAX = 30.0

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


def _lerp(value: float, breakpoints: list[tuple[float, float]]) -> float:
    """Linear interpolation between breakpoints.

    Args:
        value: Input value to map.
        breakpoints: Sorted list of (input, output) tuples defining the curve.
            Values below the first breakpoint clamp to first output.
            Values above the last breakpoint clamp to last output.

    Returns:
        Interpolated output value, rounded to 1 decimal.
    """
    if value <= breakpoints[0][0]:
        return breakpoints[0][1]
    if value >= breakpoints[-1][0]:
        return breakpoints[-1][1]

    for i in range(len(breakpoints) - 1):
        x0, y0 = breakpoints[i]
        x1, y1 = breakpoints[i + 1]
        if value <= x1:
            t = (value - x0) / (x1 - x0)
            return round(y0 + t * (y1 - y0), 1)

    return breakpoints[-1][1]


def _normalize_pillar(
    scored: list[tuple[float, float]], pillar_max: float
) -> float:
    """Normalize scored sub-components to a pillar's full range.

    Uses a weighted average of available sub-scores, scaled to the pillar max.
    Missing data fields are excluded rather than counted as zero.

    Args:
        scored: List of (actual_pts, max_pts) for sub-components that had data.
        pillar_max: Maximum score for this pillar (e.g. 35).

    Returns:
        Normalized pillar score (0 to pillar_max).
    """
    if not scored:
        return 0.0
    raw = sum(pts for pts, _ in scored)
    possible = sum(max_pts for _, max_pts in scored)
    if possible <= 0:
        return 0.0
    return round(min((raw / possible) * pillar_max, pillar_max), 1)


class FamilyHomeScorer:
    """Score houses for family livability using a 3-pillar model.

    Pillars:
    - Livability (0-35 pts): walkability, transit, safety, schools, parks
    - Value (0-35 pts): price vs assessment, $/sqft, monthly cost, market trend
    - Space & Comfort (0-30 pts): lot size, bedrooms, condition, age

    Total: 0-100 pts

    Scoring uses linear interpolation for smooth differentiation and per-pillar
    normalization so missing data doesn't unfairly penalize the score.

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

        # --- Livability Pillar (0-35) ---
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

        # --- Space & Comfort Pillar (0-30) ---
        space_score, space_breakdown, space_completeness = self._score_space(listing)
        breakdown.update(space_breakdown)
        completeness.update(space_completeness)

        # --- Total ---
        family_score = round(livability_score + value_score + space_score, 1)

        # --- Cost of Ownership ---
        welcome_tax = self._calculate_welcome_tax(listing.price)
        down_payment = int(listing.price * self.down_payment_pct)
        cmhc_premium = int((listing.price - down_payment) * CMHC_PREMIUM_RATE)
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
    # Livability Pillar (0-35)
    # =========================================================================

    def _score_livability(
        self,
        listing: PropertyListing,
        safety_score: float | None,
        school_distance_m: float | None,
        park_count_1km: int | None,
    ) -> tuple[float, dict[str, float], dict[str, bool]]:
        """Score livability pillar (0-35 pts), normalized to available data.

        Components (raw sub-score weights):
        - Walk Score (0-8): from listing.walk_score
        - Transit Score (0-7): from listing.transit_score
        - Safety (0-8): from neighbourhood safety data
        - School Proximity (0-8): from geo enrichment
        - Parks Nearby (0-5): from geo enrichment
        """
        breakdown: dict[str, float] = {}
        completeness: dict[str, bool] = {}
        scored: list[tuple[float, float]] = []  # (actual, max) pairs

        # Walk Score (0-8 pts)
        completeness["walk_score"] = listing.walk_score is not None
        if listing.walk_score is not None:
            pts = _lerp(listing.walk_score, [
                (0, 0), (20, 1.5), (40, 3.5), (60, 5.5), (80, 7.5), (100, 8.0),
            ])
            breakdown["walk_score_pts"] = pts
            scored.append((pts, 8.0))

        # Transit Score (0-7 pts)
        completeness["transit_score"] = listing.transit_score is not None
        if listing.transit_score is not None:
            pts = _lerp(listing.transit_score, [
                (0, 0), (20, 1.0), (40, 3.0), (60, 5.0), (80, 6.5), (100, 7.0),
            ])
            breakdown["transit_score_pts"] = pts
            scored.append((pts, 7.0))

        # Safety (0-8 pts)
        completeness["safety"] = safety_score is not None
        if safety_score is not None:
            pts = _lerp(safety_score, [
                (0, 0), (2, 1.0), (4, 3.0), (6, 5.0), (8, 7.0), (10, 8.0),
            ])
            breakdown["safety_pts"] = pts
            scored.append((pts, 8.0))

        # School Proximity (0-8 pts, inverted: closer = better)
        completeness["school_proximity"] = school_distance_m is not None
        if school_distance_m is not None:
            pts = _lerp(school_distance_m, [
                (0, 8.0), (500, 7.0), (1000, 5.5), (1500, 4.0),
                (2000, 2.5), (3000, 1.0), (5000, 0),
            ])
            breakdown["school_proximity_pts"] = pts
            scored.append((pts, 8.0))

        # Parks Nearby (0-5 pts)
        completeness["parks"] = park_count_1km is not None
        if park_count_1km is not None:
            pts = _lerp(float(park_count_1km), [
                (0, 0), (1, 2.0), (2, 3.5), (3, 4.5), (5, 5.0),
            ])
            breakdown["parks_pts"] = pts
            scored.append((pts, 5.0))

        total = _normalize_pillar(scored, LIVABILITY_MAX)
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
        """Score value pillar (0-35 pts), normalized to available data.

        Components (raw sub-score weights):
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
        scored: list[tuple[float, float]] = []

        # --- Price vs Municipal Assessment (0-10 pts, lower ratio = better) ---
        completeness["municipal_assessment"] = (
            listing.municipal_assessment is not None
            and listing.municipal_assessment > 0
        )
        if listing.municipal_assessment and listing.municipal_assessment > 0:
            ratio = listing.price / listing.municipal_assessment
            pts = _lerp(ratio, [
                (0.70, 10.0), (0.85, 8.5), (0.95, 6.5), (1.05, 5.0),
                (1.15, 3.0), (1.30, 1.0), (1.50, 0),
            ])
            breakdown["price_vs_assessment_pts"] = pts
            scored.append((pts, 10.0))

        # --- Price per sqft (0-8 pts, lower = better) ---
        # Thresholds calibrated for Quebec/Montreal market (2024-2026)
        completeness["sqft"] = listing.sqft is not None and listing.sqft > 0
        if listing.sqft and listing.sqft > 0:
            price_per_sqft = listing.price / listing.sqft
            cost_data["price_per_sqft"] = round(price_per_sqft, 2)

            pts = _lerp(price_per_sqft, [
                (200, 8.0), (300, 7.0), (400, 5.5), (500, 4.0),
                (650, 2.0), (800, 0.5), (1000, 0),
            ])
            breakdown["price_per_sqft_pts"] = pts
            scored.append((pts, 8.0))

        # --- Affordability / Monthly Cost (0-10 pts) ---
        down_payment = int(listing.price * self.down_payment_pct)
        mortgage_principal = listing.price - down_payment
        cmhc_premium = int(mortgage_principal * CMHC_PREMIUM_RATE)
        insured_principal = mortgage_principal + cmhc_premium

        monthly_mortgage = _calculator.calculate_mortgage_payment(
            principal=insured_principal,
            annual_rate=self.interest_rate,
            amortization_years=self.amortization_years,
        )
        cost_data["monthly_mortgage"] = monthly_mortgage

        monthly_taxes = 0
        if listing.annual_taxes and listing.annual_taxes > 0:
            monthly_taxes = listing.annual_taxes // 12
        else:
            monthly_taxes = int(listing.price * 0.012 / 12)
        cost_data["monthly_taxes"] = monthly_taxes

        annual_energy = self._estimate_annual_energy(listing.year_built, listing.sqft)
        cost_data["annual_energy"] = annual_energy

        annual_insurance = int(listing.price * INSURANCE_RATE)
        cost_data["annual_insurance"] = annual_insurance

        monthly_cost = (
            monthly_mortgage
            + monthly_taxes
            + (annual_insurance // 12)
            + (annual_energy // 12)
        )
        cost_data["monthly_cost_estimate"] = monthly_cost

        # Affordability scoring — calibrated for Quebec 2024-2026 market
        # $350K house ≈ $2,700/mo, $500K ≈ $3,800/mo, $700K ≈ $5,200/mo
        pts = _lerp(float(monthly_cost), [
            (2000, 10.0), (3000, 8.0), (4000, 6.0),
            (5000, 4.0), (6500, 2.0), (8500, 0),
        ])
        breakdown["affordability_pts"] = pts
        scored.append((pts, 10.0))  # Always has data (computed from price)

        # --- Market Trajectory (0-7 pts) ---
        trajectory_pts = self._score_market_trajectory(price_drops, days_on_market)
        has_market_data = price_drops is not None or days_on_market is not None
        completeness["market_trajectory"] = has_market_data
        if has_market_data:
            breakdown["market_trajectory_pts"] = trajectory_pts
            scored.append((trajectory_pts, 7.0))

        total = _normalize_pillar(scored, VALUE_MAX)
        return total, breakdown, cost_data, completeness

    @staticmethod
    def _score_market_trajectory(
        price_drops: list[dict] | None,
        days_on_market: int | None,
    ) -> float:
        """Score market trajectory (0-7 pts).

        Buyer-favorable signals:
        - Price drops indicate seller motivation (0-4 pts, interpolated)
        - Extended time on market suggests negotiating room (0-3 pts, interpolated)
        """
        pts = 0.0

        # Price drop signals (0-4 pts)
        if price_drops:
            drops = [d for d in price_drops if d.get("change_pct", 0) < -1.0]
            total_drop_pct = sum(abs(d.get("change_pct", 0)) for d in drops)
            pts += _lerp(total_drop_pct, [
                (0, 0), (1.5, 0.5), (3, 1.5), (5, 2.5), (8, 3.5), (12, 4.0),
            ])

        # Days on market signals (0-3 pts)
        if days_on_market is not None:
            pts += _lerp(float(days_on_market), [
                (0, 0), (14, 0), (30, 0.5), (60, 1.5), (90, 2.5), (120, 3.0),
            ])

        return round(min(7.0, pts), 1)

    # =========================================================================
    # Space & Comfort Pillar (0-30)
    # =========================================================================

    def _score_space(
        self, listing: PropertyListing
    ) -> tuple[float, dict[str, float], dict[str, bool]]:
        """Score space & comfort pillar (0-30 pts), normalized to available data.

        Components (raw sub-score weights):
        - Lot Size (0-8)
        - Bedrooms (0-8)
        - Condition (0-8)
        - Property Age (0-4): gentle curve, heritage homes not penalized
        """
        breakdown: dict[str, float] = {}
        completeness: dict[str, bool] = {}
        scored: list[tuple[float, float]] = []

        # Lot Size (0-8 pts)
        completeness["lot_sqft"] = listing.lot_sqft is not None
        if listing.lot_sqft is not None:
            pts = _lerp(float(listing.lot_sqft), [
                (0, 0), (2000, 1.0), (3500, 3.0), (5000, 5.0),
                (7000, 7.0), (10000, 8.0),
            ])
            breakdown["lot_size_pts"] = pts
            scored.append((pts, 8.0))

        # Bedrooms (0-8 pts)
        pts = _lerp(float(listing.bedrooms), [
            (0, 0), (1, 1.0), (2, 3.0), (3, 5.5), (4, 7.5), (5, 8.0),
        ])
        breakdown["bedroom_pts"] = pts
        scored.append((pts, 8.0))  # Always has data

        # Condition (0-8 pts) from AI condition_score
        completeness["condition_score"] = listing.condition_score is not None
        if listing.condition_score is not None:
            pts = _lerp(listing.condition_score, [
                (1, 0), (3, 1.5), (5, 3.5), (7, 5.5), (9, 7.5), (10, 8.0),
            ])
            breakdown["condition_pts"] = pts
            scored.append((pts, 8.0))

        # Property Age (0-4 pts) — Quebec-calibrated gentle curve
        # Heritage homes are valued, not penalized. Peak at 5-15 years (proven
        # modern), gentle decline for older homes, never drops to 0.
        completeness["year_built"] = listing.year_built is not None
        if listing.year_built is not None:
            current_year = date.today().year
            age = max(0, current_year - listing.year_built)
            pts = _lerp(float(age), [
                (0, 3.5), (10, 4.0), (25, 3.5), (50, 3.0),
                (80, 2.5), (120, 2.0), (200, 1.5),
            ])
            breakdown["age_pts"] = pts
            scored.append((pts, 4.0))

        total = _normalize_pillar(scored, SPACE_MAX)
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
        """Estimate annual energy cost based on construction era and size."""
        if sqft is None or sqft <= 0:
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
