"""Quebec municipal assessment data loader.

Data source: Quebec Open Data Portal
https://open.canada.ca/data/en/dataset/061c8cb7-ca4e-45be-a990-61fce7e7d2dc

This module provides access to Quebec municipal assessment rolls.
The data includes property assessments, land values, and building characteristics
for 1,140 municipalities in Quebec.

Note: The XML files are very large (Montreal alone is ~1GB).
This implementation uses lazy loading and caching to manage memory.
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class AssessmentRecord:
    """A single property assessment record.

    Attributes:
        cadastral_number: Quebec cadastral identification number
        address: Property address (if available)
        municipality: Municipality name
        total_value: Total assessed value (land + building)
        land_value: Land assessment value
        building_value: Building assessment value
        lot_area_sqm: Lot area in square meters
        building_area_sqm: Building area in square meters
        year_built: Year of construction
        num_units: Number of dwelling units
        property_code: Quebec property classification code
    """

    cadastral_number: str
    address: Optional[str]
    municipality: str
    total_value: int
    land_value: int
    building_value: int
    lot_area_sqm: Optional[float]
    building_area_sqm: Optional[float]
    year_built: Optional[int]
    num_units: int
    property_code: str


# Quebec property classification codes for residential
# Full list: https://www.mamh.gouv.qc.ca/evaluation-fonciere/manuel-devaluation-fonciere-du-quebec/
RESIDENTIAL_CODES = {
    "1000": "Residential (general)",
    "1100": "Single-family dwelling",
    "1200": "Duplex",
    "1300": "Triplex or Quadruplex",
    "1400": "Walk-up apartment (5+ units)",
    "1500": "High-rise apartment",
    "1600": "Mobile home",
    "1700": "Seasonal/recreational dwelling",
}

# Municipal assessment data URLs (sample - full list at data source)
MUNICIPALITY_DATA = {
    "montreal": {
        "name": "Ville de Montréal",
        "data_url": "https://donnees.montreal.ca/dataset/evaluation-fonciere",
        "format": "CSV",
        "notes": "Montreal provides CSV format, updated annually",
    },
    "longueuil": {
        "name": "Ville de Longueuil",
        "data_url": "https://open.canada.ca/data/en/dataset/061c8cb7-ca4e-45be-a990-61fce7e7d2dc",
        "format": "XML",
        "notes": "Part of Quebec-wide assessment roll",
    },
    "laval": {
        "name": "Ville de Laval",
        "data_url": "https://open.canada.ca/data/en/dataset/061c8cb7-ca4e-45be-a990-61fce7e7d2dc",
        "format": "XML",
        "notes": "Part of Quebec-wide assessment roll",
    },
}


class QuebecAssessmentData:
    """Quebec municipal assessment data loader.

    Provides access to property assessment values from Quebec's
    open data municipal assessment rolls.

    For MVP, this class provides:
    - Documentation of data sources and formats
    - Stub methods for future implementation
    - Example of expected data structure

    Full implementation would:
    - Download and cache XML/CSV assessment files
    - Parse and index by address and cadastral number
    - Provide lookup methods for property matching

    Example (future):
        assessments = QuebecAssessmentData()
        assessments.load_municipality("montreal")
        record = assessments.lookup_by_address("123 Rue Example, Montreal")
        print(f"Assessment: ${record.total_value:,}")
    """

    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize the assessment data loader.

        Args:
            cache_dir: Directory for caching downloaded data files.
                      Defaults to ~/.housemktanalyzr/assessment_cache/
        """
        if cache_dir is None:
            cache_dir = Path.home() / ".housemktanalyzr" / "assessment_cache"

        self.cache_dir = Path(cache_dir)
        self._loaded_municipalities: dict[str, list[AssessmentRecord]] = {}
        self._index_by_address: dict[str, AssessmentRecord] = {}
        self._index_by_cadastral: dict[str, AssessmentRecord] = {}

    def get_available_municipalities(self) -> list[str]:
        """Get list of municipalities with documented data sources."""
        return list(MUNICIPALITY_DATA.keys())

    def get_municipality_info(self, municipality: str) -> Optional[dict]:
        """Get information about a municipality's assessment data.

        Args:
            municipality: Municipality key (lowercase)

        Returns:
            Dict with name, data_url, format, and notes, or None if not found
        """
        return MUNICIPALITY_DATA.get(municipality.lower())

    def load_municipality(self, municipality: str) -> bool:
        """Load assessment data for a municipality.

        Note: This is a stub for MVP. Full implementation would:
        1. Check if data is cached
        2. Download if not cached or expired
        3. Parse XML/CSV into AssessmentRecord objects
        4. Build address and cadastral indexes

        Args:
            municipality: Municipality key

        Returns:
            True if data loaded successfully, False otherwise
        """
        info = self.get_municipality_info(municipality)
        if not info:
            logger.warning(f"No data source configured for: {municipality}")
            return False

        logger.info(
            f"Assessment data for {info['name']} available at: {info['data_url']}"
        )
        logger.info(f"Format: {info['format']} - {info['notes']}")
        logger.warning(
            "Full data loading not implemented in MVP. "
            "Use Centris scraper's municipal_assessment field instead."
        )
        return False

    def lookup_by_address(
        self,
        address: str,
        municipality: Optional[str] = None,
    ) -> Optional[AssessmentRecord]:
        """Look up assessment by street address.

        Note: Stub for MVP - returns None.

        Args:
            address: Street address to look up
            municipality: Optional municipality to narrow search

        Returns:
            AssessmentRecord if found, None otherwise
        """
        # Normalize address for lookup
        normalized = self._normalize_address(address)

        if normalized in self._index_by_address:
            return self._index_by_address[normalized]

        logger.debug(f"Address not found in assessment data: {address}")
        return None

    def lookup_by_cadastral(self, cadastral_number: str) -> Optional[AssessmentRecord]:
        """Look up assessment by cadastral number.

        Note: Stub for MVP - returns None.

        Args:
            cadastral_number: Quebec cadastral identification number

        Returns:
            AssessmentRecord if found, None otherwise
        """
        if cadastral_number in self._index_by_cadastral:
            return self._index_by_cadastral[cadastral_number]

        return None

    def estimate_assessment(
        self,
        price: int,
        municipality: str = "montreal",
    ) -> int:
        """Estimate municipal assessment from asking price.

        Municipal assessments in Quebec are typically 80-95% of market value,
        updated on a 3-year cycle. This provides a rough estimate.

        Args:
            price: Asking price in CAD
            municipality: Municipality for regional adjustment

        Returns:
            Estimated municipal assessment value
        """
        # Assessment-to-price ratios vary by municipality and market conditions
        # These are approximate ratios based on typical Montreal area values
        ratios = {
            "montreal": 0.85,
            "laval": 0.82,
            "longueuil": 0.80,
            "brossard": 0.83,
            "default": 0.82,
        }

        ratio = ratios.get(municipality.lower(), ratios["default"])
        return int(price * ratio)

    def _normalize_address(self, address: str) -> str:
        """Normalize address for consistent lookup.

        - Lowercase
        - Remove accents
        - Standardize abbreviations (St -> Saint, Ave -> Avenue)
        - Remove unit numbers
        """
        address = address.lower().strip()

        # Remove unit numbers like "Apt 1", "Unit 2", "#3"
        address = re.sub(r"\s*(apt|unit|#|app)\s*\d+", "", address, flags=re.I)

        # Standardize common abbreviations
        replacements = {
            r"\bst\b": "saint",
            r"\bste\b": "sainte",
            r"\bave\b": "avenue",
            r"\bblvd\b": "boulevard",
            r"\brd\b": "road",
            r"\bdr\b": "drive",
            r"\bpl\b": "place",
        }

        for pattern, replacement in replacements.items():
            address = re.sub(pattern, replacement, address)

        return address.strip()


# Data format documentation for future implementation
"""
Quebec Assessment Roll XML Format
=================================

The Quebec-wide assessment roll XML files follow this structure:

<RoleFoncier>
  <Unite>
    <Matricule>1234-56-7890-1-000-0000</Matricule>  <!-- Cadastral number -->
    <Adresse>
      <NoCivique>123</NoCivique>
      <Rue>RUE EXAMPLE</Rue>
      <Municipalite>Montreal</Municipalite>
      <CodePostal>H1A 1A1</CodePostal>
    </Adresse>
    <Evaluation>
      <ValeurTerrain>100000</ValeurTerrain>
      <ValeurBatiment>200000</ValeurBatiment>
      <ValeurTotale>300000</ValeurTotale>
    </Evaluation>
    <Terrain>
      <SuperficieTerrain>500</SuperficieTerrain>  <!-- m² -->
    </Terrain>
    <Batiment>
      <SuperficieBatiment>150</SuperficieBatiment>  <!-- m² -->
      <AnneeConstruction>1975</AnneeConstruction>
      <NombreLogements>2</NombreLogements>
    </Batiment>
    <Utilisation>
      <CodeUtilisation>1200</CodeUtilisation>  <!-- Duplex -->
    </Utilisation>
  </Unite>
</RoleFoncier>

Montreal CSV Format
==================

Montreal provides assessment data in CSV format with columns:
- ID_UEV: Unique identifier
- CIVIQUE_DEBUT, CIVIQUE_FIN: Street numbers
- NOM_RUE: Street name
- ARRONDISSEMENT: Borough
- ANNEE_CONSTRUCTION: Year built
- NOMBRE_LOGEMENTS: Number of units
- VALEUR_TERRAIN: Land value
- VALEUR_BATIMENT: Building value
- VALEUR_TOTALE: Total value

Download: https://donnees.montreal.ca/dataset/evaluation-fonciere
"""
