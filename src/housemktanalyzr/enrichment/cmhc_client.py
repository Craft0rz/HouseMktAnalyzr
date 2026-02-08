"""Live CMHC Rental Market Survey client.

Fetches rent data from the CMHC Housing Market Information Portal
(HMIP) internal API. No authentication required.

Data source: https://www03.cmhc-schl.gc.ca/hmip-pimh/
R package reference: https://github.com/mountainMath/cmhc
"""

import csv
import io
import logging
import re
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

# CMHC internal geography IDs (NOT Census GeoUIDs).
# Use discover_cmhc_geo_id() to find IDs for new CMAs.
CMHC_GEO_IDS = {
    "montreal": "1060",
    "toronto": "2270",
    "vancouver": "2410",
    "ottawa": "1640",
    "calgary": "0140",
    "quebec": "1400",
    "sherbrooke": "1800",
}

# Table IDs for Rental Market Survey
CMHC_TABLES = {
    # Snapshot (by zone, single year)
    "avg_rent_by_zone": "2.1.11.3",
    "vacancy_by_zone": "2.1.1.3",
    "universe_by_zone": "2.1.26.3",
    "pct_change_by_zone": "2.1.12.3",
    # Historical (time series for CMA)
    "historical_avg_rent": "2.2.11",
    "historical_vacancy": "2.2.1",
}

# Standard bedroom columns returned by CMHC
BEDROOM_TYPES = ["bachelor", "1br", "2br", "3br+", "total"]
BEDROOM_HEADER_MAP = {
    "studio": "bachelor",
    "bachelor": "bachelor",
    "1 bedroom": "1br",
    "2 bedroom": "2br",
    "3 bedroom +": "3br+",
    "3 bedroom": "3br+",
    "total": "total",
}


@dataclass
class ZoneRentData:
    """Rent data for a single CMHC zone in a given year."""
    zone: str
    year: int
    bachelor: float | None = None
    one_br: float | None = None
    two_br: float | None = None
    three_br_plus: float | None = None
    total: float | None = None

    def get_rent(self, bedrooms: int) -> float | None:
        """Get rent by bedroom count (0=bachelor, 1-3+)."""
        mapping = {0: self.bachelor, 1: self.one_br, 2: self.two_br, 3: self.three_br_plus}
        return mapping.get(min(bedrooms, 3))


@dataclass
class ZoneVacancyData:
    """Vacancy rate for a single CMHC zone in a given year."""
    zone: str
    year: int
    bachelor: float | None = None
    one_br: float | None = None
    two_br: float | None = None
    three_br_plus: float | None = None
    total: float | None = None


@dataclass
class HistoricalRent:
    """Historical rent data point for CMA-level time series."""
    year: int
    bachelor: float | None = None
    one_br: float | None = None
    two_br: float | None = None
    three_br_plus: float | None = None
    total: float | None = None


@dataclass
class CMHCSnapshot:
    """Complete CMHC snapshot for a CMA in a given year."""
    cma: str
    year: int
    rents: list[ZoneRentData] = field(default_factory=list)
    vacancies: list[ZoneVacancyData] = field(default_factory=list)


def _parse_value(raw: str) -> float | None:
    """Parse a CMHC CSV value, handling suppressed data and commas."""
    raw = raw.strip()
    if not raw or raw == "**" or raw == "++":
        return None
    # Remove thousands commas and any letter quality codes
    cleaned = raw.replace(",", "").strip()
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def _parse_csv_rows(csv_text: str) -> tuple[int | None, list[str], list[list[str]]]:
    """Parse CMHC CSV response into year, headers, and data rows.

    Returns (year, bedroom_columns, data_rows) where data_rows
    are [zone_name, val1, code1, val2, code2, ...].
    """
    lines = csv_text.strip().split("\n")
    if len(lines) < 3:
        return None, [], []

    # Line 1: title (e.g. " Average Rent by Bedroom Type by Zone")
    # Line 2: period (e.g. "October 2024 Row / Apartment")
    period_line = lines[1].strip()
    year = None
    year_match = re.search(r"(\d{4})", period_line)
    if year_match:
        year = int(year_match.group(1))

    # Line 3: headers — bedroom type columns with quality code columns
    header_line = lines[2]
    reader = csv.reader(io.StringIO(header_line))
    raw_headers = next(reader, [])

    # Map headers: every other column is a quality code (skip those)
    bedroom_cols = []
    for h in raw_headers:
        h_clean = h.strip().lower()
        if h_clean in BEDROOM_HEADER_MAP:
            bedroom_cols.append(BEDROOM_HEADER_MAP[h_clean])

    # Data rows start at line 4, end before "Notes" section
    data_rows = []
    for line in lines[3:]:
        stripped = line.strip()
        if not stripped or stripped.startswith("Notes") or stripped.startswith('"Notes'):
            break
        if stripped.startswith('"The following'):
            break
        reader = csv.reader(io.StringIO(line))
        row = next(reader, [])
        if row:
            data_rows.append(row)

    return year, bedroom_cols, data_rows


def _extract_zone_values(
    row: list[str], bedroom_cols: list[str]
) -> dict[str, float | None]:
    """Extract values from a CSV row, skipping quality code columns."""
    values: dict[str, float | None] = {}
    # row[0] = zone name, then pairs of (value, quality_code)
    col_idx = 1
    for bed_type in bedroom_cols:
        if col_idx < len(row):
            values[bed_type] = _parse_value(row[col_idx])
            col_idx += 2  # skip quality code column
        else:
            values[bed_type] = None
    return values


class CMHCClient:
    """Client for the CMHC Housing Market Information Portal API."""

    BASE = "https://www03.cmhc-schl.gc.ca/hmip-pimh/en/TableMapChart/ExportTable"

    def __init__(self, cma: str = "montreal"):
        self.geo_id = CMHC_GEO_IDS.get(cma, CMHC_GEO_IDS["montreal"])
        self.cma = cma
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _fetch_table(
        self, table_id: str, year: int | None = None
    ) -> str:
        """Fetch a CMHC table as CSV text."""
        client = await self._get_client()
        data = {
            "TableId": table_id,
            "GeographyId": self.geo_id,
            "GeographyTypeId": "3",
            "exportType": "csv",
            "Frequency": "Annual",
        }
        if year:
            data["ForTimePeriod.Year"] = str(year)

        resp = await client.post(
            self.BASE,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        # CMHC returns Latin-1 encoded CSV
        return resp.content.decode("latin-1")

    async def get_rents_by_zone(self, year: int | None = None) -> list[ZoneRentData]:
        """Get average rents by zone and bedroom type for a given year."""
        csv_text = await self._fetch_table(CMHC_TABLES["avg_rent_by_zone"], year)
        parsed_year, bedroom_cols, data_rows = _parse_csv_rows(csv_text)
        actual_year = year or parsed_year or 2024

        results = []
        for row in data_rows:
            zone_name = row[0].strip() if row else ""
            if not zone_name:
                # Last row is CMA total (empty zone name) — label it
                zone_name = f"{self.cma.title()} CMA Total"

            vals = _extract_zone_values(row, bedroom_cols)
            results.append(ZoneRentData(
                zone=zone_name,
                year=actual_year,
                bachelor=vals.get("bachelor"),
                one_br=vals.get("1br"),
                two_br=vals.get("2br"),
                three_br_plus=vals.get("3br+"),
                total=vals.get("total"),
            ))
        return results

    async def get_vacancy_by_zone(self, year: int | None = None) -> list[ZoneVacancyData]:
        """Get vacancy rates by zone and bedroom type."""
        csv_text = await self._fetch_table(CMHC_TABLES["vacancy_by_zone"], year)
        parsed_year, bedroom_cols, data_rows = _parse_csv_rows(csv_text)
        actual_year = year or parsed_year or 2024

        results = []
        for row in data_rows:
            zone_name = row[0].strip() if row else ""
            if not zone_name:
                zone_name = f"{self.cma.title()} CMA Total"

            vals = _extract_zone_values(row, bedroom_cols)
            results.append(ZoneVacancyData(
                zone=zone_name,
                year=actual_year,
                bachelor=vals.get("bachelor"),
                one_br=vals.get("1br"),
                two_br=vals.get("2br"),
                three_br_plus=vals.get("3br+"),
                total=vals.get("total"),
            ))
        return results

    async def get_historical_rents(self) -> list[HistoricalRent]:
        """Get historical average rents for the CMA (1990s-present)."""
        csv_text = await self._fetch_table(CMHC_TABLES["historical_avg_rent"])
        _, bedroom_cols, data_rows = _parse_csv_rows(csv_text)

        results = []
        for row in data_rows:
            # First column is like "1998 October" or "2024 October"
            label = row[0].strip() if row else ""
            year_match = re.search(r"(\d{4})", label)
            if not year_match:
                continue
            year = int(year_match.group(1))

            vals = _extract_zone_values(row, bedroom_cols)
            results.append(HistoricalRent(
                year=year,
                bachelor=vals.get("bachelor"),
                one_br=vals.get("1br"),
                two_br=vals.get("2br"),
                three_br_plus=vals.get("3br+"),
                total=vals.get("total"),
            ))
        return sorted(results, key=lambda r: r.year)

    async def get_historical_vacancy(self) -> list[dict]:
        """Get historical vacancy rates for the CMA."""
        csv_text = await self._fetch_table(CMHC_TABLES["historical_vacancy"])
        _, bedroom_cols, data_rows = _parse_csv_rows(csv_text)

        results = []
        for row in data_rows:
            label = row[0].strip() if row else ""
            year_match = re.search(r"(\d{4})", label)
            if not year_match:
                continue
            year = int(year_match.group(1))

            vals = _extract_zone_values(row, bedroom_cols)
            results.append({
                "year": year,
                "bachelor": vals.get("bachelor"),
                "one_br": vals.get("1br"),
                "two_br": vals.get("2br"),
                "three_br_plus": vals.get("3br+"),
                "total": vals.get("total"),
            })
        return sorted(results, key=lambda r: r["year"])

    async def get_snapshot(self, year: int | None = None) -> CMHCSnapshot:
        """Get complete rent + vacancy snapshot for a year."""
        rents = await self.get_rents_by_zone(year)
        vacancies = await self.get_vacancy_by_zone(year)
        actual_year = rents[0].year if rents else (year or 2024)
        return CMHCSnapshot(
            cma=self.cma,
            year=actual_year,
            rents=rents,
            vacancies=vacancies,
        )


async def discover_cmhc_geo_id(cma_name: str, id_range: range | None = None) -> str | None:
    """Probe the CMHC API to discover the GeographyId for a CMA.

    Tries candidate IDs against the avg_rent_by_zone table and checks
    the response for the CMA name. Run once per new CMA, then add the
    result to CMHC_GEO_IDS.

    Usage:
        import asyncio
        geo_id = asyncio.run(discover_cmhc_geo_id("Québec"))
    """
    if id_range is None:
        id_range = range(1, 3000)

    url = "https://www03.cmhc-schl.gc.ca/hmip-pimh/en/TableMapChart/ExportTable"
    target = cma_name.lower()

    async with httpx.AsyncClient(timeout=10.0) as client:
        for candidate in id_range:
            geo_id = f"{candidate:04d}"
            try:
                resp = await client.post(url, data={
                    "TableId": "2.1.11.3",
                    "GeographyId": geo_id,
                    "GeographyTypeId": "3",
                    "exportType": "csv",
                    "Frequency": "Annual",
                })
                if resp.status_code == 200 and target in resp.text.lower():
                    logger.info(f"Discovered CMHC geo_id for {cma_name}: {geo_id}")
                    return geo_id
            except Exception:
                continue
    return None
