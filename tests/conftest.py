"""Pytest fixtures and test utilities."""

import pytest

from housemktanalyzr.analysis import InvestmentCalculator, PropertyRanker
from housemktanalyzr.models.property import PropertyListing, PropertyType


@pytest.fixture
def calculator() -> InvestmentCalculator:
    """InvestmentCalculator instance."""
    return InvestmentCalculator()


@pytest.fixture
def ranker() -> PropertyRanker:
    """PropertyRanker instance."""
    return PropertyRanker()


@pytest.fixture
def sample_duplex() -> PropertyListing:
    """Sample duplex listing."""
    return PropertyListing(
        id="test-duplex-1",
        source="test",
        address="123 Test Street",
        city="Montreal",
        price=500000,
        property_type=PropertyType.DUPLEX,
        bedrooms=4,
        bathrooms=2,
        units=2,
        url="https://example.com/duplex",
        gross_revenue=36000,  # $3000/mo total rent
    )


@pytest.fixture
def sample_triplex() -> PropertyListing:
    """Sample triplex listing."""
    return PropertyListing(
        id="test-triplex-1",
        source="test",
        address="456 Main Avenue",
        city="Longueuil",
        price=650000,
        property_type=PropertyType.TRIPLEX,
        bedrooms=6,
        bathrooms=3,
        units=3,
        url="https://example.com/triplex",
        gross_revenue=48000,  # $4000/mo total rent
    )


@pytest.fixture
def sample_quadplex() -> PropertyListing:
    """Sample quadplex listing."""
    return PropertyListing(
        id="test-quadplex-1",
        source="test",
        address="789 Oak Boulevard",
        city="Brossard",
        price=800000,
        property_type=PropertyType.QUADPLEX,
        bedrooms=8,
        bathrooms=4,
        units=4,
        url="https://example.com/quadplex",
        gross_revenue=60000,  # $5000/mo total rent
    )


@pytest.fixture
def sample_listings(
    sample_duplex: PropertyListing,
    sample_triplex: PropertyListing,
    sample_quadplex: PropertyListing,
) -> list[PropertyListing]:
    """Multiple listings of various types."""
    return [sample_duplex, sample_triplex, sample_quadplex]


@pytest.fixture
def high_yield_listing() -> PropertyListing:
    """High yield property for testing filters."""
    return PropertyListing(
        id="high-yield-1",
        source="test",
        address="999 Profit Lane",
        city="Montreal",
        price=400000,
        property_type=PropertyType.TRIPLEX,
        bedrooms=6,
        bathrooms=3,
        units=3,
        url="https://example.com/highyield",
        gross_revenue=48000,  # 12% gross yield
    )


@pytest.fixture
def low_yield_listing() -> PropertyListing:
    """Low yield property for testing filters."""
    return PropertyListing(
        id="low-yield-1",
        source="test",
        address="111 Expensive Ave",
        city="Westmount",
        price=1200000,
        property_type=PropertyType.DUPLEX,
        bedrooms=4,
        bathrooms=2,
        units=2,
        url="https://example.com/lowyield",
        gross_revenue=36000,  # 3% gross yield
    )
