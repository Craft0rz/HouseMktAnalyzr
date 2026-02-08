"""Sherbrooke neighbourhood data client (crime/safety + permits + tax rates).

Data sources:
- Crime incidents: ArcGIS IncidentSecuritePublique FeatureServer/0
- Arrondissement boundaries: ArcGIS Arrondissement FeatureServer/0
  Portal: services3.arcgis.com/qsNXG7LzoUbR4c1C
  License: Open Data (Ville de Sherbrooke)
  Coverage: Rolling 3-year window (currently 2022-2024)
  ~11,400 incident records across 4 arrondissements
- Tax rates: sherbrooke.ca (uniform city-wide rate, hardcoded constants)
- Permits: StatCan Table 34-10-0292-01 (building permits by CMA, monthly).
  WDS vector API. CMA-level totals distributed proportionally by population.
  No per-arrondissement breakdown available.
"""

import logging
import math
from datetime import date

import httpx

logger = logging.getLogger(__name__)

CRIME_LAYER_URL = (
    "https://services3.arcgis.com/qsNXG7LzoUbR4c1C/arcgis/rest/services"
    "/IncidentSecuritePublique/FeatureServer/0"
)
ARRONDISSEMENT_LAYER_URL = (
    "https://services3.arcgis.com/qsNXG7LzoUbR4c1C/arcgis/rest/services"
    "/Arrondissement/FeatureServer/0"
)

# Crime type classification by TYPEINCIDENT code.
# 1=Accidents with injuries, 2=Fatal accidents, 3=Impaired driving,
# 4=Break & enter, 5=Mischief, 6=Threats/violence, 7=Assault, 8=Theft
VIOLENT_TYPES = {2, 6, 7}   # Fatal accident, Threats/violence, Assault
PROPERTY_TYPES = {4, 5, 8}  # Break & enter, Mischief, Theft

# Canonical short names for DB storage (strip "Arrondissement de/des" prefix).
_NOM_TO_SHORT: dict[str, str] = {
    "Arrondissement de Brompton--Rock Forest--Saint-Elie--Deauville":
        "Brompton-Rock Forest-St-Elie-Deauville",
    "Arrondissement des Nations": "Des Nations",
    "Arrondissement de Lennoxville": "Lennoxville",
    "Arrondissement de Fleurimont": "Fleurimont",
}

# 2021 Census approximate populations per arrondissement.
# Used for per-capita crime rate normalization.
# Total Sherbrooke = 172,950 (StatCan 2021).
_ARROND_POP_2021: dict[str, int] = {
    "Brompton-Rock Forest-St-Elie-Deauville": 48_500,
    "Des Nations": 57_000,
    "Lennoxville": 5_600,
    "Fleurimont": 61_850,
}

# Uniform residential tax rate (per $100 of assessed value).
# Source: sherbrooke.ca/fr/services-a-la-population/taxes-et-evaluation/
# Note: 2025 rate dropped due to new triennial assessment roll
# (property values increased ~60% on average).
_TAX_RATES: dict[int, float] = {
    2025: 0.6746,
    2024: 1.0316,
}

_TOTAL_POP = sum(_ARROND_POP_2021.values())  # 172,950

# ---------------------------------------------------------------------------
# StatCan Table 34-10-0292-01 — Building permits by CMA (monthly).
# WDS vector API: getDataFromVectorsAndLatestNPeriods
# Sherbrooke CMA = GEO member ID 28.
# scalarFactorCode: 0 = units, 3 = thousands.
# ---------------------------------------------------------------------------
STATCAN_WDS_URL = (
    "https://www150.statcan.gc.ca/t1/wds/rest"
    "/getDataFromVectorsAndLatestNPeriods"
)
# Vectors for Sherbrooke CMA residential building permits.
_STATCAN_VECTORS = {
    "total_count": 1675291698,       # coord 28.4.1.5.1 — all work types, count
    "construction_count": 1675291701, # coord 28.4.6.5.1 — new construction, count
    "transform_count": 1675291707,    # coord 28.4.12.5.1 — improvements, count
    "total_value": 1675101961,        # coord 28.4.1.1.1 — all work types, value ($000s)
}


def _point_in_polygon(x: float, y: float, rings: list) -> bool:
    """Ray-casting point-in-polygon test using outer ring only."""
    ring = rings[0]
    n = len(ring)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


class SherbrookeCrimeClient:
    """Client for Sherbrooke's ArcGIS-hosted crime data."""

    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _fetch_statcan_permits(self, year: int) -> dict[str, int | float] | None:
        """Fetch CMA-level building permit aggregates from StatCan WDS API.

        Returns dict with total_count, construction_count, transform_count,
        total_value (dollars) for the requested year, or None on failure.
        """
        client = await self._get_client()
        payload = [
            {"vectorId": vid, "latestN": 36}
            for vid in _STATCAN_VECTORS.values()
        ]
        try:
            resp = await client.post(STATCAN_WDS_URL, json=payload, timeout=30.0)
            resp.raise_for_status()
        except Exception:
            logger.warning("StatCan WDS API request failed", exc_info=True)
            return None

        data = resp.json()
        if not isinstance(data, list):
            logger.warning("StatCan WDS: unexpected response format")
            return None

        # Build vectorId → annual aggregate for target year
        vector_totals: dict[int, float] = {}
        vector_months: dict[int, int] = {}
        for item in data:
            if item.get("status") != "SUCCESS":
                continue
            obj = item["object"]
            vid = obj["vectorId"]
            for pt in obj.get("vectorDataPoint", []):
                pt_year = int(pt["refPer"][:4])
                if pt_year != year:
                    continue
                val = pt.get("value")
                if val is None:
                    continue
                scalar = pt.get("scalarFactorCode", 0)
                actual = val * (10 ** scalar) if scalar else val
                vector_totals[vid] = vector_totals.get(vid, 0) + actual
                vector_months[vid] = vector_months.get(vid, 0) + 1

        total_vid = _STATCAN_VECTORS["total_count"]
        if total_vid not in vector_totals:
            logger.info(f"StatCan: no permit data for Sherbrooke CMA in {year}")
            return None

        months = vector_months.get(total_vid, 0)
        if months < 12:
            logger.info(
                f"StatCan: Sherbrooke {year} has only {months}/12 months, "
                "extrapolating to full year"
            )
            scale = 12 / months if months > 0 else 1
            for vid in vector_totals:
                vector_totals[vid] *= scale

        result = {
            "total_count": round(vector_totals.get(_STATCAN_VECTORS["total_count"], 0)),
            "construction_count": round(vector_totals.get(_STATCAN_VECTORS["construction_count"], 0)),
            "transform_count": round(vector_totals.get(_STATCAN_VECTORS["transform_count"], 0)),
            "total_value": round(vector_totals.get(_STATCAN_VECTORS["total_value"], 0)),
        }
        logger.info(
            f"StatCan: Sherbrooke CMA {year} — "
            f"{result['total_count']} permits, "
            f"${result['total_value']:,} value "
            f"({months} months{'*' if months < 12 else ''})"
        )
        return result

    async def _fetch_arrondissements(self) -> list[dict]:
        """Fetch arrondissement boundary polygons from ArcGIS."""
        client = await self._get_client()
        resp = await client.get(
            f"{ARRONDISSEMENT_LAYER_URL}/query",
            params={
                "where": "1=1",
                "outFields": "NOM",
                "returnGeometry": "true",
                "f": "json",
            },
        )
        resp.raise_for_status()
        return resp.json().get("features", [])

    async def _fetch_crimes(self, year: int) -> list[dict]:
        """Fetch all crime records for a given year (paginated by 2000)."""
        client = await self._get_client()
        features: list[dict] = []
        offset = 0
        while True:
            resp = await client.get(
                f"{CRIME_LAYER_URL}/query",
                params={
                    "where": f"ANNEE={year}",
                    "outFields": "TYPEINCIDENT",
                    "returnGeometry": "true",
                    "resultOffset": str(offset),
                    "resultRecordCount": "2000",
                    "f": "json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            batch = data.get("features", [])
            features.extend(batch)
            if not data.get("exceededTransferLimit", False) or len(batch) == 0:
                break
            offset += len(batch)
        return features

    @staticmethod
    def _assign_to_arrondissements(
        features: list[dict],
        polygons: list[tuple[str, list]],
    ) -> dict[str, dict[str, int]]:
        """Assign crime points to arrondissements via point-in-polygon.

        Returns {short_name: {"total": N, "violent": N, "property": N}}.
        """
        stats: dict[str, dict[str, int]] = {}
        unassigned = 0

        for feat in features:
            geom = feat.get("geometry", {})
            x, y = geom.get("x", 0), geom.get("y", 0)
            if not x or not y:
                unassigned += 1
                continue

            type_code = feat.get("attributes", {}).get("TYPEINCIDENT", 0)
            assigned = False

            for short_name, rings in polygons:
                if _point_in_polygon(x, y, rings):
                    if short_name not in stats:
                        stats[short_name] = {"total": 0, "violent": 0, "property": 0}
                    stats[short_name]["total"] += 1
                    if type_code in VIOLENT_TYPES:
                        stats[short_name]["violent"] += 1
                    elif type_code in PROPERTY_TYPES:
                        stats[short_name]["property"] += 1
                    assigned = True
                    break

            if not assigned:
                unassigned += 1

        if unassigned:
            logger.debug(f"Sherbrooke: {unassigned} incidents outside arrondissement boundaries")

        return stats

    async def get_neighbourhood_rows(self, year: int | None = None) -> list[dict]:
        """Compute per-arrondissement crime stats and safety scores.

        Returns list of dicts ready for upsert_neighbourhood_stats_batch().
        """
        if year is None:
            year = date.today().year - 1

        # Fetch boundaries and crime data (current + previous year)
        arrondissements = await self._fetch_arrondissements()
        current_crimes = await self._fetch_crimes(year)
        previous_crimes = await self._fetch_crimes(year - 1)

        # Build polygon index: (short_name, rings)
        polygons: list[tuple[str, list]] = []
        for feat in arrondissements:
            nom = feat.get("attributes", {}).get("NOM", "")
            short = _NOM_TO_SHORT.get(nom, nom)
            rings = feat.get("geometry", {}).get("rings", [])
            if rings:
                polygons.append((short, rings))

        if not polygons:
            logger.warning("Sherbrooke: no arrondissement polygons fetched")
            return []

        current_stats = self._assign_to_arrondissements(current_crimes, polygons)
        previous_stats = self._assign_to_arrondissements(previous_crimes, polygons)

        # Compute per-capita rates
        rates: dict[str, float] = {}
        for name, counts in current_stats.items():
            pop = _ARROND_POP_2021.get(name, 0)
            if pop > 0:
                rates[name] = round((counts["total"] / pop) * 1000, 1)

        avg_rate = sum(rates.values()) / len(rates) if rates else 0

        # Resolve tax rate for the target year (uniform across arrondissements)
        tax_rate = _TAX_RATES.get(year) or _TAX_RATES.get(year + 1)

        # Fetch CMA-level building permits from StatCan
        permits_cma = await self._fetch_statcan_permits(year)

        # Build output rows
        rows: list[dict] = []
        for short_name, _rings in polygons:
            cur = current_stats.get(short_name, {"total": 0, "violent": 0, "property": 0})
            prev = previous_stats.get(short_name, {"total": 0, "violent": 0, "property": 0})

            rate = rates.get(short_name)
            change_pct = None
            if prev["total"] > 0:
                change_pct = round(
                    ((cur["total"] - prev["total"]) / prev["total"]) * 100, 1
                )

            # Safety score: same log-scale algorithm as Montreal.
            # 10 = safest, 1 = most dangerous. Average borough ~ 8.
            safety = None
            if rate is not None and avg_rate > 0:
                ratio = rate / avg_rate
                safety = round(max(1, min(10, 8 - math.log2(max(ratio, 0.01)) * 3)), 1)
                if change_pct is not None and change_pct < -5:
                    safety = min(10, safety + 0.5)

            row: dict = {
                "borough": short_name,
                "year": year,
                "source": "sherbrooke_arcgis",
                "crime_count": cur["total"],
                "violent_crimes": cur["violent"],
                "property_crimes": cur["property"],
                "crime_rate_per_1000": rate,
                "crime_change_pct": change_pct,
                "safety_score": safety,
            }
            if tax_rate is not None:
                row["tax_rate_residential"] = tax_rate
                row["tax_rate_total"] = tax_rate  # uniform, no additional per-$100 levies

            # Distribute CMA-level permit data proportionally by population
            if permits_cma and _TOTAL_POP:
                pop = _ARROND_POP_2021.get(short_name, 0)
                fraction = pop / _TOTAL_POP
                row["permit_count"] = round(permits_cma["total_count"] * fraction)
                row["permit_construction_count"] = round(
                    permits_cma["construction_count"] * fraction
                )
                row["permit_transform_count"] = round(
                    permits_cma["transform_count"] * fraction
                )
                row["permit_total_cost"] = round(
                    permits_cma["total_value"] * fraction
                )

            rows.append(row)

        permit_total = sum(r.get("permit_count", 0) for r in rows)
        logger.info(
            f"Sherbrooke: {len(rows)} arrondissements, "
            f"{sum(r['crime_count'] for r in rows)} incidents"
            + (f" + {permit_total} permits" if permits_cma else "")
            + f" for {year}"
            + (f", tax rate {tax_rate}/100$" if tax_rate else "")
        )
        return rows
