"""CMHC Housing Starts client (by census subdivision).

Fetches annual housing starts from the CMHC Housing Market Information
Portal (HMIP) for individual municipalities within Quebec CMAs. Uses
the ExportTable CSV endpoint (no authentication required).

Data source:
- CMHC Starts and Completions Survey (SCSS)
- Table 1.1.1.9: Starts by Dwelling Type, by Census Subdivision
- Portal: https://www03.cmhc-schl.gc.ca/hmip-pimh/
- Coverage: current year (updated monthly)
- License: CMHC Open Data

The CSV response contains one row per municipality within the
requested CMA, with columns: Single, Semi-Detached, Row, Apartment, All.
"""

import csv
import io
import logging
import re

import httpx

logger = logging.getLogger(__name__)

EXPORT_URL = (
    "https://www03.cmhc-schl.gc.ca/hmip-pimh/en/TableMapChart/ExportTable"
)

# Table ID for Starts by Dwelling Type, by Census Subdivision
_TABLE_STARTS_BY_CSD = "1.1.1.9"

# CMA geography IDs covering our municipalities.
# {display_name: CMHC GeographyId}
_CMAS: dict[str, str] = {
    "Montreal": "1060",
    "Quebec": "1400",
    "Sherbrooke": "1800",
    "Gatineau": "1264",
}

# Map CMHC CSV city names (stripped of type suffix) → our display names.
# CMHC uses forms like "Châteauguay (V)", "L'Épiphanie (V)".
# We strip the " (V)" / " (MÉ)" suffix and match case-insensitively.
# Only cities we care about are listed. Others are ignored.
_CITY_NAME_MAP: dict[str, str] = {
    # Montreal CMA
    "beloeil": "Beloeil",
    "blainville": "Blainville",
    "boisbriand": "Boisbriand",
    "brossard": "Longueuil",  # Longueuil agglomeration
    "boucherville": "Longueuil",  # Longueuil agglomeration
    "candiac": "Candiac",
    "chambly": "Chambly",
    "châteauguay": "Châteauguay",
    "la prairie": "La Prairie",
    "laval": "Laval",
    "longueuil": "Longueuil",
    "mascouche": "Mascouche",
    "mirabel": "Mirabel",
    "montréal": "Montréal",
    "repentigny": "Repentigny",
    "rosemère": "Rosemère",
    "saint-bruno-de-montarville": "Saint-Bruno-de-Montarville",
    "saint-constant": "Saint-Constant",
    "saint-eustache": "Saint-Eustache",
    "saint-hubert": "Longueuil",  # part of Longueuil
    "saint-jean-sur-richelieu": "Saint-Jean-sur-Richelieu",
    "saint-jérôme": "Saint-Jérôme",
    "saint-lambert": "Longueuil",  # Longueuil agglomeration
    "sainte-thérèse": "Sainte-Thérèse",
    "terrebonne": "Terrebonne",
    "vaudreuil-dorion": "Vaudreuil-Dorion",
    # Quebec CMA
    "lévis": "Lévis",
    "québec": "Québec",
    "saint-augustin-de-desmaures": "Saint-Augustin-de-Desmaures",
    # Sherbrooke CMA
    "sherbrooke": "Sherbrooke",
    "magog": "Magog",
    # Gatineau CMA
    "gatineau": "Gatineau",
}

# Regex to strip municipal type suffix: " (V)", " (MÉ)", " (CT)", " (VL)", etc.
_TYPE_SUFFIX_RE = re.compile(r"\s*\([A-ZÉ]{1,3}\)\s*$")


def _normalize_city_name(raw: str) -> str:
    """Strip the type suffix and normalize to lowercase for matching."""
    return _TYPE_SUFFIX_RE.sub("", raw).strip().lower()


def _parse_int(val: str) -> int:
    """Parse an integer that may have commas and quotes: '\"4,613\"' → 4613."""
    cleaned = val.strip().strip('"').replace(",", "")
    if not cleaned or cleaned == "-":
        return 0
    try:
        return int(cleaned)
    except ValueError:
        return 0


class CMHCStartsClient:
    """Fetches annual housing starts by municipality from CMHC HMIP."""

    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0, verify=False)
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _fetch_cma_starts(self, geo_id: str) -> list[dict]:
        """Fetch housing starts CSV for one CMA, return parsed rows.

        Returns [{"city": display_name, "single": N, "semi": N,
                  "row": N, "apartment": N, "total": N}, ...]
        """
        client = await self._get_client()
        try:
            resp = await client.post(
                EXPORT_URL,
                data={
                    "TableId": _TABLE_STARTS_BY_CSD,
                    "GeographyId": geo_id,
                    "GeographyTypeId": "3",
                    "exportType": "csv",
                    "Frequency": "Annual",
                },
                timeout=30.0,
            )
            resp.raise_for_status()
        except Exception:
            logger.warning(
                f"CMHC: starts CSV fetch failed for CMA {geo_id}", exc_info=True
            )
            return []

        text = resp.content.decode("latin1")
        lines = text.strip().split("\n")

        # Parse header: skip title rows, find column headers
        # Line 0: title, Line 1: period/filter, Line 2: column headers
        if len(lines) < 4:
            return []

        # Re-join data lines and parse with csv module to handle quoted
        # fields containing commas (e.g. "4,613").
        data_block = "\n".join(lines[3:])
        reader = csv.reader(io.StringIO(data_block))

        rows: list[dict] = []
        for parts in reader:
            if not parts or not parts[0].strip():
                continue
            first = parts[0].strip()
            if first.startswith("Notes") or first.startswith("Source"):
                break
            if len(parts) < 6:
                continue

            raw_name = parts[0]
            normalized = _normalize_city_name(raw_name)
            display_name = _CITY_NAME_MAP.get(normalized)
            if not display_name:
                continue

            total = _parse_int(parts[5])
            if total <= 0:
                continue

            rows.append({
                "city": display_name,
                "single": _parse_int(parts[1]),
                "semi": _parse_int(parts[2]),
                "row": _parse_int(parts[3]),
                "apartment": _parse_int(parts[4]),
                "total": total,
            })

        return rows

    async def get_starts_data(self) -> dict[str, dict]:
        """Fetch housing starts for all target municipalities across all CMAs.

        Returns {display_name: {
            "housing_starts": int,
            "starts_single": int,
            "starts_semi": int,
            "starts_row": int,
            "starts_apartment": int,
        }}

        For cities that appear multiple times (e.g. Longueuil agglomeration
        members), values are summed.
        """
        all_results: dict[str, dict] = {}

        for cma_name, geo_id in _CMAS.items():
            rows = await self._fetch_cma_starts(geo_id)
            logger.info(f"CMHC: {cma_name} CMA — {len(rows)} matching municipalities")

            for row in rows:
                city = row["city"]
                if city in all_results:
                    # Sum values (e.g. multiple Longueuil agglomeration members)
                    for key in ("total", "single", "semi", "row", "apartment"):
                        all_results[city][key] = (
                            all_results[city].get(key, 0) + row[key]
                        )
                else:
                    all_results[city] = {
                        "total": row["total"],
                        "single": row["single"],
                        "semi": row["semi"],
                        "row": row["row"],
                        "apartment": row["apartment"],
                    }

        # Rename keys for DB compatibility
        result: dict[str, dict] = {}
        for city, data in all_results.items():
            result[city] = {
                "housing_starts": data["total"],
                "starts_single": data["single"],
                "starts_semi": data["semi"],
                "starts_row": data["row"],
                "starts_apartment": data["apartment"],
            }

        logger.info(f"CMHC: housing starts for {len(result)} municipalities total")
        return result
