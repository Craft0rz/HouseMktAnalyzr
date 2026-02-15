"""Property and investment data models."""

from datetime import date
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, computed_field


class PropertyType(str, Enum):
    """Types of residential properties."""

    HOUSE = "HOUSE"
    DUPLEX = "DUPLEX"
    TRIPLEX = "TRIPLEX"
    QUADPLEX = "QUADPLEX"
    MULTIPLEX = "MULTIPLEX"  # 5+ units


class PropertyListing(BaseModel):
    """Real estate listing data model.

    Represents a property listing from any source (Centris, Realtor.ca, etc.)
    with all relevant details for investment analysis.
    """

    # Identification
    id: str = Field(..., description="Unique identifier from source")
    source: str = Field(..., description="Data source (centris, realtor, etc.)")

    # Location
    address: str = Field(..., description="Street address")
    city: str = Field(..., description="City name")
    postal_code: str | None = Field(default=None, description="Postal code")

    # Pricing
    price: int = Field(..., ge=0, description="Asking price in CAD")

    # Property details
    property_type: PropertyType = Field(..., description="Type of property")
    bedrooms: int = Field(..., ge=0, description="Number of bedrooms")
    bathrooms: float = Field(..., ge=0, description="Number of bathrooms (allows half)")
    sqft: int | None = Field(default=None, ge=0, description="Living area in sqft")
    lot_sqft: int | None = Field(default=None, ge=0, description="Lot size in sqft")
    year_built: int | None = Field(
        default=None, ge=1800, le=2100, description="Year property was built"
    )

    # Multi-unit details
    units: int = Field(
        default=1, ge=1, description="Number of units (1 for house, 2 for duplex, etc.)"
    )

    # Income potential
    estimated_rent: int | None = Field(
        default=None, ge=0, description="Estimated monthly rent (per unit or total)"
    )
    gross_revenue: int | None = Field(
        default=None, ge=0, description="Annual gross revenue (for multi-family)"
    )
    total_expenses: int | None = Field(
        default=None, ge=0, description="Annual total expenses from Centris (for multi-family)"
    )
    net_income: int | None = Field(
        default=None, ge=0, description="Annual net income from Centris (for multi-family)"
    )

    # Tax and assessment
    municipal_assessment: int | None = Field(
        default=None, ge=0, description="Total municipal assessment value"
    )
    annual_taxes: int | None = Field(
        default=None, ge=0, description="Total annual property taxes"
    )

    # Walkability scores (from Walk Score API)
    walk_score: int | None = Field(default=None, ge=0, le=100, description="Walk Score (0-100)")
    transit_score: int | None = Field(default=None, ge=0, le=100, description="Transit Score (0-100)")
    bike_score: int | None = Field(default=None, ge=0, le=100, description="Bike Score (0-100)")

    # Geocoded coordinates
    latitude: float | None = Field(default=None, description="Latitude from geocoding")
    longitude: float | None = Field(default=None, description="Longitude from geocoding")

    # Property photos
    photo_urls: list[str] | None = Field(default=None, description="Gallery photo URLs")

    # AI condition assessment (from Gemini)
    condition_score: float | None = Field(
        default=None, ge=1, le=10, description="AI-assessed property condition (1-10)"
    )
    condition_details: dict[str, Any] | None = Field(
        default=None, description="Condition breakdown: kitchen, bathroom, floors, exterior, notes"
    )

    # Listing info
    listing_date: date | None = Field(default=None, description="Date property listed")
    url: str = Field(..., description="URL to listing")

    # Raw data storage
    raw_data: dict[str, Any] | None = Field(
        default=None, description="Original API response data"
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_new_construction(self) -> bool:
        """Detect new construction / pre-construction properties.

        Heuristic: year_built >= current year, OR year_built is missing together
        with municipal assessment (pre-construction projects have neither).
        """
        current_year = date.today().year
        if self.year_built is not None and self.year_built >= current_year:
            return True
        if (
            self.year_built is None
            and self.municipal_assessment is None
            and self.lot_sqft is None
        ):
            return True
        return False

    model_config = {
        "str_strip_whitespace": True,
        "validate_assignment": True,
    }


class FamilyHomeMetrics(BaseModel):
    """Family home scoring metrics for owner-occupied houses.

    Evaluates houses on livability, value, and space/comfort instead of
    investment returns. Used for property_type=HOUSE listings where families
    care about quality of life rather than rental yields.
    """

    property_id: str
    purchase_price: int

    # Overall score (0-100)
    family_score: float = Field(ge=0, le=100)
    score_breakdown: dict[str, float] = Field(default_factory=dict)

    # Livability Pillar (0-35, normalized from available data)
    livability_score: float = Field(ge=0, le=35)
    walk_score_pts: float | None = None       # 0-8 from walk_score
    transit_score_pts: float | None = None     # 0-7 from transit_score
    safety_pts: float | None = None            # 0-8 from safety_score
    school_proximity_pts: float | None = None  # 0-8 from geo enrichment
    parks_pts: float | None = None             # 0-5 from geo enrichment

    # Value Pillar (0-35, normalized from available data)
    value_score: float = Field(ge=0, le=35)
    price_vs_assessment_pts: float | None = None  # 0-10
    price_per_sqft: float | None = None
    price_per_sqft_pts: float | None = None       # 0-8
    monthly_cost_estimate: int | None = None      # mortgage + taxes + insurance + energy
    affordability_pts: float | None = None        # 0-10
    market_trajectory_pts: float | None = None    # 0-7

    # Space & Comfort Pillar (0-30, normalized from available data)
    space_score: float = Field(ge=0, le=30)
    lot_size_pts: float | None = None         # 0-8
    bedroom_pts: float | None = None          # 0-8
    condition_pts: float | None = None        # 0-8 from condition_score
    age_pts: float | None = None              # 0-4 (gentle curve, heritage-friendly)

    # Cost of ownership breakdown
    estimated_monthly_mortgage: int | None = None
    estimated_monthly_taxes: int | None = None
    estimated_annual_energy: int | None = None
    estimated_annual_insurance: int | None = None
    welcome_tax: int | None = None
    total_cash_needed: int | None = None

    # Risk flags
    flood_zone: bool | None = None            # future: CEHQ API
    contaminated_nearby: bool | None = None   # future: ESRI API

    # Raw input values (pass-through for frontend tooltip display)
    raw_school_distance_m: float | None = None
    raw_park_count_1km: int | None = None
    raw_safety_score: float | None = None
    raw_days_on_market: int | None = None

    # Data completeness — shows which scores have real data vs are missing
    data_completeness: dict[str, bool] = Field(
        default_factory=dict,
        description=(
            "Map of data field → whether real data was available. "
            "Missing fields are excluded from scoring (normalized out)."
        ),
    )

    model_config = {
        "validate_assignment": True,
    }


class InvestmentMetrics(BaseModel):
    """Investment analysis metrics for a property.

    Contains calculated metrics for evaluating the investment potential
    of a property, including yields, cap rates, and a composite score.
    """

    # Property reference
    property_id: str = Field(..., description="Reference to PropertyListing.id")

    # Financial inputs
    purchase_price: int = Field(..., ge=0, description="Purchase price in CAD")
    estimated_monthly_rent: int = Field(
        ..., ge=0, description="Total estimated monthly rent"
    )

    # Computed metrics
    gross_rental_yield: float = Field(
        ..., ge=0, description="Annual rent / price * 100"
    )
    cap_rate: float | None = Field(
        default=None, ge=0, description="NOI / price * 100"
    )
    price_per_unit: int = Field(..., ge=0, description="Price divided by unit count")
    price_per_sqft: float | None = Field(
        default=None, ge=0, description="Price per square foot"
    )
    cash_flow_monthly: float | None = Field(
        default=None, description="Monthly cash flow after expenses estimate"
    )

    # Rent estimation source
    rent_source: str = Field(
        default="cmhc_estimate",
        description="Where rent estimate came from: 'declared' (Centris gross revenue), 'cmhc_estimate' (CMHC zone average)",
    )

    # Rent vs market comparison
    cmhc_estimated_rent: int | None = Field(
        default=None, ge=0, description="CMHC average monthly rent for this zone/unit mix"
    )
    rent_vs_market_pct: float | None = Field(
        default=None, description="Actual vs CMHC rent: negative = below market (upside), positive = above"
    )

    # Scoring
    score: float = Field(
        ..., ge=0, le=100, description="Investment score 0-100 (Financial 70 + Location 30)"
    )
    score_breakdown: dict[str, float] = Field(
        default_factory=dict, description="Component scores breakdown"
    )

    # Rate sensitivity: cash flow at different interest rates
    rate_sensitivity: dict[str, float] | None = Field(
        default=None,
        description="Cash flow at base, -1.5%, +1.5% rates: {low_rate, low_cash_flow, base_rate, base_cash_flow, high_rate, high_cash_flow}",
    )

    # Comparable price-per-door from other listings in same region
    comparable_ppu: dict[str, Any] | None = Field(
        default=None,
        description="Comparable price-per-unit stats: {median, avg, count, region, property_type}",
    )

    model_config = {
        "validate_assignment": True,
    }

    @computed_field
    @property
    def annual_rent(self) -> int:
        """Calculate annual rent from monthly rent."""
        return self.estimated_monthly_rent * 12

    @computed_field
    @property
    def is_positive_cash_flow(self) -> bool:
        """Check if property has positive cash flow."""
        if self.cash_flow_monthly is None:
            return False
        return self.cash_flow_monthly > 0
