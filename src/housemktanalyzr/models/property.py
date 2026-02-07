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

    # Tax and assessment
    municipal_assessment: int | None = Field(
        default=None, ge=0, description="Total municipal assessment value"
    )
    annual_taxes: int | None = Field(
        default=None, ge=0, description="Total annual property taxes"
    )

    # Listing info
    listing_date: date | None = Field(default=None, description="Date property listed")
    url: str = Field(..., description="URL to listing")

    # Raw data storage
    raw_data: dict[str, Any] | None = Field(
        default=None, description="Original API response data"
    )

    model_config = {
        "str_strip_whitespace": True,
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

    # Scoring
    score: float = Field(
        ..., ge=0, le=100, description="Investment score from 0-100"
    )
    score_breakdown: dict[str, float] = Field(
        default_factory=dict, description="Component scores breakdown"
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
