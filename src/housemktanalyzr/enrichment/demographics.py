"""Census demographic data from Statistics Canada SDMX API.

Fetches median household income, population, and household size
for Quebec municipalities. No authentication required.

Data source: Statistics Canada 2021 Census Profile
https://api.statcan.gc.ca/census-recensement/profile/sdmx/rest/
"""

import csv
import io
import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

# StatCan Census Profile SDMX API
STATCAN_BASE = "https://api.statcan.gc.ca/census-recensement/profile/sdmx/rest/data"

# Characteristic IDs for 2021 Census
CHARACTERISTICS = {
    "population": "1",
    "population_2016": "2",
    "pop_change_pct": "3",
    "avg_household_size": "56",
    "total_households": "228",
    "median_household_income": "229",
    "median_after_tax_income": "230",
    "avg_household_income": "238",
    "median_individual_income": "113",
}

# CSD codes → DGUID mapping for all supported CMAs.
# DGUID format: 2021A0005 + 7-digit CSD code
# Add entries for new CMAs when activating them.
CMA_CSDS = {
    # --- Montreal CMA ---
    "montreal": "2466023",
    "laval": "2465005",
    "longueuil": "2458227",
    "brossard": "2458007",
    "terrebonne": "2464008",
    "repentigny": "2460013",
    "blainville": "2473015",
    "saint-jerome": "2475017",
    "mirabel": "2474005",
    "mascouche": "2464015",
    "saint-eustache": "2472005",
    "chateauguay": "2467050",
    "vaudreuil-dorion": "2471083",
    "saint-constant": "2467035",
    "dollard-des-ormeaux": "2466142",
    "pointe-claire": "2466097",
    "saint-bruno-de-montarville": "2458037",
    "chambly": "2457005",
    "boucherville": "2458033",
    "la-prairie": "2467015",
    "sainte-therese": "2473010",
    "boisbriand": "2473010",
    "candiac": "2467025",
    "saint-lambert": "2458012",
    "beloeil": "2457030",
    "saint-jean-sur-richelieu": "2456083",
    "saint-hubert": "2458227",  # merged into Longueuil
    "greenfield-park": "2458227",  # merged into Longueuil
    "verdun": "2466023",  # borough of Montreal
    "lasalle": "2466023",
    "plateau-mont-royal": "2466023",
    "rosemont": "2466023",
    "ahuntsic": "2466023",
    "hochelaga-maisonneuve": "2466023",
    "villeray": "2466023",
    "cote-des-neiges": "2466023",
    "notre-dame-de-grace": "2466023",
    "saint-laurent": "2466023",
    "anjou": "2466023",
    "montreal-nord": "2466023",
    "saint-leonard": "2466023",
    "riviere-des-prairies": "2466023",
    "downtown": "2466023",
    "ndg": "2466023",
    # Region aliases
    "south-shore": "2458227",  # default to Longueuil
    "laurentides": "2475017",  # default to Saint-Jerome
    "lanaudiere": "2460013",  # default to Repentigny
    # --- Quebec CMA ---
    "quebec": "2423027",
    "quebec-city": "2423027",
    "levis": "2425213",
    "l-ancienne-lorette": "2423057",
    "saint-augustin-de-desmaures": "2423072",
    "beauport": "2423027",  # borough of Quebec City
    "charlesbourg": "2423027",  # borough of Quebec City
    "sainte-foy": "2423027",  # borough of Quebec City
    "shannon": "2422020",
    "boischatel": "2421045",
    "stoneham-et-tewkesbury": "2422010",
    "saint-henri": "2425080",
    "capitale-nationale": "2423027",  # default to Quebec City
    # --- Sherbrooke CMA ---
    "sherbrooke": "2443027",
    "magog": "2445072",
    "orford": "2445055",
    "ascot-corner": "2441058",
    "compton": "2441038",
    "waterville": "2441013",
    "north-hatley": "2445030",
    "fleurimont": "2443027",  # merged into Sherbrooke
    "lennoxville": "2443027",  # merged into Sherbrooke
    "estrie": "2443027",  # default to Sherbrooke
}


def _csd_to_dguid(csd_code: str) -> str:
    """Convert a 7-digit CSD code to SDMX DGUID format."""
    return f"2021A0005{csd_code}"


@dataclass
class DemographicProfile:
    """Census demographic data for a municipality."""
    municipality: str
    csd_code: str
    population: int | None = None
    population_2016: int | None = None
    pop_change_pct: float | None = None
    avg_household_size: float | None = None
    total_households: int | None = None
    median_household_income: int | None = None
    median_after_tax_income: int | None = None
    avg_household_income: int | None = None

    @property
    def rent_to_income_ratio(self) -> float | None:
        """Placeholder — set externally when rent data is available."""
        return None


class StatCanCensusClient:
    """Client for Statistics Canada 2021 Census Profile SDMX API."""

    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get_demographics(
        self, csd_codes: list[str] | None = None
    ) -> list[DemographicProfile]:
        """Fetch demographic profiles for municipalities.

        Args:
            csd_codes: List of 7-digit CSD codes. If None, fetches all
                       Greater Montreal municipalities.

        Returns:
            List of DemographicProfile dataclasses.
        """
        if csd_codes is None:
            # Get unique CSD codes for Greater Montreal
            csd_codes = sorted(set(CMA_CSDS.values()))

        dguids = [_csd_to_dguid(c) for c in csd_codes]
        dguid_str = "+".join(dguids)

        # Key characteristics to fetch
        chars = [
            CHARACTERISTICS["population"],
            CHARACTERISTICS["population_2016"],
            CHARACTERISTICS["pop_change_pct"],
            CHARACTERISTICS["avg_household_size"],
            CHARACTERISTICS["total_households"],
            CHARACTERISTICS["median_household_income"],
            CHARACTERISTICS["median_after_tax_income"],
            CHARACTERISTICS["avg_household_income"],
        ]
        char_str = "+".join(chars)

        url = f"{STATCAN_BASE}/STC_CP,DF_CSD/A5.{dguid_str}.1.{char_str}.1?format=csv"

        client = await self._get_client()
        resp = await client.get(url)
        resp.raise_for_status()

        return self._parse_csv(resp.text, csd_codes)

    async def get_demographics_for_city(self, city: str) -> DemographicProfile | None:
        """Get demographics for a single city/neighbourhood.

        Maps city names to CSD codes using the CMA_CSDS lookup.
        """
        normalized = city.lower().strip().replace(" ", "-")
        csd_code = CMA_CSDS.get(normalized)
        if not csd_code:
            # Try partial match
            for key, code in CMA_CSDS.items():
                if normalized in key or key in normalized:
                    csd_code = code
                    break

        if not csd_code:
            logger.warning(f"No CSD code found for city: {city}")
            return None

        results = await self.get_demographics([csd_code])
        return results[0] if results else None

    def _parse_csv(
        self, csv_text: str, csd_codes: list[str]
    ) -> list[DemographicProfile]:
        """Parse StatCan SDMX CSV response into DemographicProfile objects."""
        reader = csv.DictReader(io.StringIO(csv_text))

        # Collect data by DGUID
        data_by_dguid: dict[str, dict] = {}
        geo_names: dict[str, str] = {}

        for row in reader:
            dguid = row.get("REF_AREA", "")
            char_id = row.get("CHARACTERISTIC", "")
            value_str = row.get("OBS_VALUE", "")
            geo_name = row.get("GEO_DESC", "")

            if not dguid or not char_id:
                continue

            if dguid not in data_by_dguid:
                data_by_dguid[dguid] = {}
            if geo_name:
                geo_names[dguid] = geo_name

            try:
                value = float(value_str) if value_str else None
            except (ValueError, TypeError):
                value = None

            data_by_dguid[dguid][char_id] = value

        # Build profiles
        profiles = []
        for csd_code in csd_codes:
            dguid = _csd_to_dguid(csd_code)
            data = data_by_dguid.get(dguid, {})
            name = geo_names.get(dguid, csd_code)

            # Clean up municipality name (e.g. "Montreal, Ville" → "Montreal")
            if "," in name:
                name = name.split(",")[0].strip()

            profile = DemographicProfile(
                municipality=name,
                csd_code=csd_code,
                population=int(data[CHARACTERISTICS["population"]]) if data.get(CHARACTERISTICS["population"]) else None,
                population_2016=int(data[CHARACTERISTICS["population_2016"]]) if data.get(CHARACTERISTICS["population_2016"]) else None,
                pop_change_pct=data.get(CHARACTERISTICS["pop_change_pct"]),
                avg_household_size=data.get(CHARACTERISTICS["avg_household_size"]),
                total_households=int(data[CHARACTERISTICS["total_households"]]) if data.get(CHARACTERISTICS["total_households"]) else None,
                median_household_income=int(data[CHARACTERISTICS["median_household_income"]]) if data.get(CHARACTERISTICS["median_household_income"]) else None,
                median_after_tax_income=int(data[CHARACTERISTICS["median_after_tax_income"]]) if data.get(CHARACTERISTICS["median_after_tax_income"]) else None,
                avg_household_income=int(data[CHARACTERISTICS["avg_household_income"]]) if data.get(CHARACTERISTICS["avg_household_income"]) else None,
            )
            profiles.append(profile)

        return profiles


def get_csd_for_city(city: str) -> str | None:
    """Look up the CSD code for a city/neighbourhood name."""
    normalized = city.lower().strip().replace(" ", "-")
    code = CMA_CSDS.get(normalized)
    if code:
        return code
    # Partial match
    for key, code in CMA_CSDS.items():
        if normalized in key or key in normalized:
            return code
    return None
