"""CMHC rental market data for Greater Montreal.

Data source: Canada Mortgage and Housing Corporation (CMHC)
Rental Market Survey - Fall 2024
https://www03.cmhc-schl.gc.ca/hmip-pimh/

This module provides average rental rates by zone, bedroom count,
and building type for the Greater Montreal Census Metropolitan Area (CMA).
"""

from typing import Optional

# CMHC Rental Market Survey Data - Fall 2024
# Montreal CMA average rents by zone and bedroom count
# All values in CAD/month
#
# Data extracted from: CMHC Rental Market Survey, Fall 2024
# https://www03.cmhc-schl.gc.ca/hmip-pimh/en#TableMapChart/0580/3/Montreal
#
# Note: Values are averages for purpose-built rental apartments.
# Actual rents vary by building age, condition, and amenities.

RENTAL_DATA_2024 = {
    # Montreal Island zones
    "montreal": {
        "bachelor": 1050,
        1: 1350,
        2: 1650,
        3: 2000,
        4: 2300,
    },
    "montreal-island": {
        "bachelor": 1050,
        1: 1350,
        2: 1650,
        3: 2000,
        4: 2300,
    },
    "downtown": {
        "bachelor": 1400,
        1: 1750,
        2: 2100,
        3: 2500,
        4: 2900,
    },
    "plateau-mont-royal": {
        "bachelor": 1200,
        1: 1500,
        2: 1850,
        3: 2200,
        4: 2500,
    },
    "rosemont": {
        "bachelor": 1000,
        1: 1300,
        2: 1600,
        3: 1950,
        4: 2200,
    },
    "villeray": {
        "bachelor": 950,
        1: 1250,
        2: 1550,
        3: 1900,
        4: 2150,
    },
    "hochelaga-maisonneuve": {
        "bachelor": 900,
        1: 1150,
        2: 1450,
        3: 1750,
        4: 2000,
    },
    "verdun": {
        "bachelor": 1050,
        1: 1350,
        2: 1650,
        3: 2000,
        4: 2300,
    },
    "lasalle": {
        "bachelor": 950,
        1: 1200,
        2: 1500,
        3: 1800,
        4: 2100,
    },
    "ahuntsic": {
        "bachelor": 950,
        1: 1200,
        2: 1500,
        3: 1850,
        4: 2100,
    },
    "cote-des-neiges": {
        "bachelor": 1100,
        1: 1400,
        2: 1700,
        3: 2050,
        4: 2350,
    },
    "notre-dame-de-grace": {
        "bachelor": 1050,
        1: 1350,
        2: 1650,
        3: 2000,
        4: 2300,
    },
    "ndg": {  # Alias
        "bachelor": 1050,
        1: 1350,
        2: 1650,
        3: 2000,
        4: 2300,
    },
    "saint-laurent": {
        "bachelor": 1000,
        1: 1300,
        2: 1600,
        3: 1950,
        4: 2200,
    },
    "anjou": {
        "bachelor": 900,
        1: 1150,
        2: 1450,
        3: 1750,
        4: 2000,
    },
    "montreal-nord": {
        "bachelor": 850,
        1: 1100,
        2: 1350,
        3: 1650,
        4: 1900,
    },
    "saint-leonard": {
        "bachelor": 900,
        1: 1150,
        2: 1400,
        3: 1700,
        4: 1950,
    },
    "riviere-des-prairies": {
        "bachelor": 900,
        1: 1150,
        2: 1400,
        3: 1700,
        4: 1950,
    },
    # South Shore (Rive-Sud)
    "longueuil": {
        "bachelor": 900,
        1: 1150,
        2: 1450,
        3: 1750,
        4: 2000,
    },
    "brossard": {
        "bachelor": 1000,
        1: 1300,
        2: 1600,
        3: 1950,
        4: 2200,
    },
    "saint-lambert": {
        "bachelor": 1050,
        1: 1350,
        2: 1650,
        3: 2000,
        4: 2300,
    },
    "saint-hubert": {
        "bachelor": 875,
        1: 1100,
        2: 1400,
        3: 1700,
        4: 1950,
    },
    "greenfield-park": {
        "bachelor": 900,
        1: 1150,
        2: 1450,
        3: 1750,
        4: 2000,
    },
    "boucherville": {
        "bachelor": 1000,
        1: 1300,
        2: 1600,
        3: 1950,
        4: 2200,
    },
    "la-prairie": {
        "bachelor": 950,
        1: 1200,
        2: 1500,
        3: 1850,
        4: 2100,
    },
    "saint-jean-sur-richelieu": {
        "bachelor": 850,
        1: 1100,
        2: 1350,
        3: 1650,
        4: 1900,
    },
    "chambly": {
        "bachelor": 900,
        1: 1150,
        2: 1450,
        3: 1750,
        4: 2000,
    },
    "beloeil": {
        "bachelor": 925,
        1: 1175,
        2: 1475,
        3: 1775,
        4: 2025,
    },
    "south-shore": {  # Generic South Shore
        "bachelor": 925,
        1: 1175,
        2: 1475,
        3: 1775,
        4: 2025,
    },
    "rive-sud": {  # French alias
        "bachelor": 925,
        1: 1175,
        2: 1475,
        3: 1775,
        4: 2025,
    },
    "monteregie": {
        "bachelor": 900,
        1: 1150,
        2: 1450,
        3: 1750,
        4: 2000,
    },
    # Laval
    "laval": {
        "bachelor": 950,
        1: 1250,
        2: 1550,
        3: 1900,
        4: 2150,
    },
    "chomedey": {
        "bachelor": 950,
        1: 1250,
        2: 1550,
        3: 1900,
        4: 2150,
    },
    "vimont": {
        "bachelor": 925,
        1: 1200,
        2: 1500,
        3: 1850,
        4: 2100,
    },
    "pont-viau": {
        "bachelor": 900,
        1: 1150,
        2: 1450,
        3: 1750,
        4: 2000,
    },
    "sainte-rose": {
        "bachelor": 975,
        1: 1275,
        2: 1575,
        3: 1925,
        4: 2175,
    },
    # North Shore (Rive-Nord)
    "north-shore": {
        "bachelor": 875,
        1: 1125,
        2: 1425,
        3: 1725,
        4: 1975,
    },
    "rive-nord": {
        "bachelor": 875,
        1: 1125,
        2: 1425,
        3: 1725,
        4: 1975,
    },
    "terrebonne": {
        "bachelor": 900,
        1: 1150,
        2: 1450,
        3: 1750,
        4: 2000,
    },
    "repentigny": {
        "bachelor": 875,
        1: 1125,
        2: 1425,
        3: 1725,
        4: 1975,
    },
    "mascouche": {
        "bachelor": 850,
        1: 1100,
        2: 1400,
        3: 1700,
        4: 1950,
    },
    "blainville": {
        "bachelor": 950,
        1: 1225,
        2: 1525,
        3: 1875,
        4: 2125,
    },
    "saint-jerome": {
        "bachelor": 825,
        1: 1075,
        2: 1350,
        3: 1650,
        4: 1900,
    },
    "laurentides": {
        "bachelor": 850,
        1: 1100,
        2: 1375,
        3: 1675,
        4: 1925,
    },
    "lanaudiere": {
        "bachelor": 825,
        1: 1075,
        2: 1350,
        3: 1650,
        4: 1900,
    },
}

# Multipliers for building type
# CMHC data shows newer buildings command premium rents
BUILDING_TYPE_MULTIPLIERS = {
    "new": 1.20,  # Built after 2015
    "modern": 1.10,  # Built 2000-2015
    "standard": 1.00,  # Built 1980-2000
    "older": 0.90,  # Built before 1980
}

# Default rental data for unknown zones (Montreal CMA average)
DEFAULT_RENTAL_DATA = {
    "bachelor": 950,
    1: 1225,
    2: 1525,
    3: 1850,
    4: 2100,
}


class CMHCRentalData:
    """CMHC rental market data lookup for Greater Montreal.

    Provides estimated rental rates based on CMHC Rental Market Survey data.
    Useful for calculating potential rental income on investment properties.

    Example:
        cmhc = CMHCRentalData()
        rent = cmhc.get_estimated_rent("longueuil", 3)
        print(f"3-bedroom in Longueuil: ${rent}/month")
    """

    def __init__(self):
        """Initialize with 2024 rental data."""
        self.rental_data = RENTAL_DATA_2024
        self.data_year = 2024
        self.data_source = "CMHC Rental Market Survey, Fall 2024"

    def get_estimated_rent(
        self,
        city: str,
        bedrooms: int,
        building_age: Optional[str] = None,
    ) -> int:
        """Get estimated monthly rent for a unit.

        Args:
            city: City or neighbourhood name (case-insensitive)
            bedrooms: Number of bedrooms (0-4, where 0 = bachelor)
            building_age: Optional building age category for adjustment
                         ("new", "modern", "standard", "older")

        Returns:
            Estimated monthly rent in CAD
        """
        # Normalize city name
        city_key = self._normalize_city(city)

        # Get rental data for city, fallback to default
        city_data = self.rental_data.get(city_key, DEFAULT_RENTAL_DATA)

        # Handle bedroom count
        if bedrooms == 0:
            bedroom_key = "bachelor"
        else:
            bedroom_key = min(bedrooms, 4)  # Cap at 4

        base_rent = city_data.get(bedroom_key, city_data.get(2, 1500))

        # Apply building age multiplier if specified
        if building_age:
            multiplier = BUILDING_TYPE_MULTIPLIERS.get(building_age.lower(), 1.0)
            base_rent = int(base_rent * multiplier)

        return base_rent

    def get_total_rent(
        self,
        city: str,
        units: list[int],
        building_age: Optional[str] = None,
    ) -> int:
        """Get total monthly rent for a multi-unit property.

        Args:
            city: City or neighbourhood name
            units: List of bedroom counts for each unit
                  e.g., [2, 2] for a duplex with two 2-bedroom units
            building_age: Optional building age category

        Returns:
            Total estimated monthly rent for all units

        Example:
            # Triplex with 3br, 2br, 1br units
            total = cmhc.get_total_rent("montreal", [3, 2, 1])
        """
        return sum(
            self.get_estimated_rent(city, beds, building_age)
            for beds in units
        )

    def get_annual_gross_revenue(
        self,
        city: str,
        units: list[int],
        building_age: Optional[str] = None,
        vacancy_rate: float = 0.02,
    ) -> int:
        """Get estimated annual gross revenue for a multi-unit property.

        Args:
            city: City or neighbourhood name
            units: List of bedroom counts for each unit
            building_age: Optional building age category
            vacancy_rate: Expected vacancy rate (default 2%)

        Returns:
            Estimated annual gross revenue in CAD
        """
        monthly_total = self.get_total_rent(city, units, building_age)
        annual_gross = monthly_total * 12
        return int(annual_gross * (1 - vacancy_rate))

    def get_available_zones(self) -> list[str]:
        """Get list of all available zone/city names."""
        return sorted(self.rental_data.keys())

    def _normalize_city(self, city: str) -> str:
        """Normalize city name for lookup.

        Handles common variations and partial matches.
        """
        city = city.lower().strip()

        # Remove common suffixes
        city = city.replace(", qc", "").replace(", quebec", "")
        city = city.replace(" (island)", "").replace("-island", "")

        # Common mappings
        mappings = {
            "ndg": "notre-dame-de-grace",
            "cdp": "cote-des-neiges",
            "cdn": "cote-des-neiges",
            "rdp": "riviere-des-prairies",
            "pma": "plateau-mont-royal",
            "plateau": "plateau-mont-royal",
            "homa": "hochelaga-maisonneuve",
            "st-laurent": "saint-laurent",
            "st-leonard": "saint-leonard",
            "st-hubert": "saint-hubert",
            "st-lambert": "saint-lambert",
            "st-jerome": "saint-jerome",
            "st-jean": "saint-jean-sur-richelieu",
        }

        if city in mappings:
            return mappings[city]

        # Replace spaces with hyphens
        city = city.replace(" ", "-")

        return city
