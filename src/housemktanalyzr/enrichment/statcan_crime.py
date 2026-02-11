"""Statistics Canada crime data client (Table 35-10-0179-01).

Fetches police-reported crime statistics for Quebec police services
using the StatCan Web Data Service (WDS) API. A single batch API call
retrieves crime data for all target municipalities.

Data source:
- Table 35-10-0179-01: Incident-based crime statistics, by detailed
  violations, police services in Quebec
- API: https://www150.statcan.gc.ca/t1/wds/rest/
- Coverage: 1998-2024, updated annually (~July)
- License: Statistics Canada Open Licence
"""

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

CUBE_ID = 35100179
METADATA_URL = "https://www150.statcan.gc.ca/t1/wds/rest/getCubeMetadata"
DATA_URL = (
    "https://www150.statcan.gc.ca/t1/wds/rest"
    "/getDataFromCubePidCoordAndLatestNPeriods"
)

# ---------------------------------------------------------------------------
# Municipality → StatCan police service name pattern.
# The GEO dimension member names look like:
#   "Lévis, Quebec, municipal [24041]"
#   "Roussillon, Quebec, municipal [24551]"
# We match by checking if the pattern appears in the member name.
#
# For régies (intermunicipal police), one entry covers multiple cities.
# We distribute régie-level stats to individual cities by population.
# ---------------------------------------------------------------------------

@dataclass
class PoliceServiceMapping:
    """Maps a StatCan police service to one or more municipalities."""
    geo_pattern: str  # substring to match in StatCan GEO member name
    municipalities: dict[str, int]  # {display_name: 2021_census_population}


# Individual municipal police services (1 service → 1 municipality)
# Plus régies (1 service → multiple municipalities)
POLICE_SERVICES: list[PoliceServiceMapping] = [
    # --- Individual municipal services ---
    # NOTE: StatCan uses "St." notation for some cities. Patterns must match
    # the memberNameEn strings in the cube metadata (case-insensitive substring).
    PoliceServiceMapping("Lévis", {"Lévis": 149_000}),
    PoliceServiceMapping("Repentigny", {"Repentigny": 86_000}),
    PoliceServiceMapping("St. J", {"Saint-Jérôme": 80_000}),  # "St. Jérôme, Quebec, municipal [24275]"
    PoliceServiceMapping("Châteauguay", {"Châteauguay": 50_000}),
    PoliceServiceMapping("Saint-Jean-sur-Richelieu", {"Saint-Jean-sur-Richelieu": 100_000}),
    PoliceServiceMapping("Mascouche", {"Mascouche": 52_000}),
    PoliceServiceMapping("Mirabel", {"Mirabel": 62_000}),
    PoliceServiceMapping("St. Eustache", {"Saint-Eustache": 46_000}),  # "St. Eustache, Quebec, municipal [24257]"
    # Terrebonne runs an intermunicipal service but is the main city
    PoliceServiceMapping("Terrebonne", {"Terrebonne": 119_000}),
    # --- Régies intermunicipales ---
    # Régie Roussillon covers La Prairie, Candiac, Saint-Constant + others
    PoliceServiceMapping("Roussillon", {
        "La Prairie": 27_000,
        "Candiac": 22_000,
        "Saint-Constant": 29_000,
    }),
    # Régie Richelieu-Saint-Laurent covers Beloeil, Chambly + others
    # Pattern "Richelieu Saint" matches "Richelieu Saint-Laurent [24268]"
    # and avoids "Saint-Jean-sur-Richelieu" and "La Vallée-du-Richelieu"
    PoliceServiceMapping("Richelieu Saint", {
        "Beloeil": 24_000,
        "Chambly": 31_000,
    }),
    # Régie Thérèse-De Blainville covers Blainville, Sainte-Thérèse, Boisbriand + others
    # Pattern "Thérèse-de" avoids matching "Ste. Thérèse" standalone entry
    PoliceServiceMapping("Thérèse-de", {
        "Blainville": 61_000,
        "Sainte-Thérèse": 27_000,
        "Boisbriand": 28_000,
    }),
    # Régie de police de Memphrémagog covers Magog + others
    PoliceServiceMapping("Memphrémagog", {"Magog": 28_000}),
    # Saint-Augustin-de-Desmaures → Quebec City police (SPVQ), already covered
    # Saint-Bruno-de-Montarville → SPAL (Longueuil), already covered
    # Vaudreuil-Dorion → SQ, harder to isolate
]

# Violation member IDs we want to fetch.
# These are discovered from cube metadata but are stable across releases.
# We'll discover them dynamically to be robust.
_TARGET_VIOLATIONS = {
    "total": "Total, all Criminal Code violations (excluding traffic)",
    "total_all": "Total, all violations",  # fallback if CC-only is null
    "violent": "Total violent Criminal Code violations",
    "property": "Total property crime violations",
}

# Statistics member: "Actual incidents" is always member 1
_STATS_ACTUAL_INCIDENTS = 1


class StatCanCrimeClient:
    """Fetches crime data from StatCan Table 35-10-0179-01 for Quebec police services."""

    def __init__(self):
        self._client: httpx.AsyncClient | None = None
        self._metadata_cache: dict | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _fetch_metadata(self) -> dict:
        """Fetch cube metadata to discover dimension member IDs.

        Returns parsed metadata with geography and violations member mappings.
        Cached for the lifetime of this client instance.
        """
        if self._metadata_cache:
            return self._metadata_cache

        client = await self._get_client()
        try:
            resp = await client.post(
                METADATA_URL,
                json=[{"productId": CUBE_ID}],
                timeout=30.0,
            )
            resp.raise_for_status()
        except Exception:
            logger.warning("StatCan: cube metadata fetch failed", exc_info=True)
            return {}

        data = resp.json()
        if not data or data[0].get("status") != "SUCCESS":
            logger.warning(f"StatCan: metadata request failed: {data}")
            return {}

        cube = data[0]["object"]
        dims = {d["dimensionNameEn"]: d for d in cube.get("dimension", [])}

        # Parse geography members
        geo_dim = dims.get("Geography", {})
        geo_members = {}
        for m in geo_dim.get("member", []):
            geo_members[m["memberId"]] = m.get("memberNameEn", "")

        # Parse violations members
        viol_dim = dims.get("Violations", {})
        viol_members = {}
        for m in viol_dim.get("member", []):
            viol_members[m["memberId"]] = m.get("memberNameEn", "")

        self._metadata_cache = {
            "geo_members": geo_members,  # {memberId: name}
            "viol_members": viol_members,
        }

        logger.info(
            f"StatCan: metadata loaded — {len(geo_members)} geographies, "
            f"{len(viol_members)} violations"
        )
        return self._metadata_cache

    def _resolve_geo_member_ids(
        self, geo_members: dict[int, str]
    ) -> dict[str, int]:
        """Match police service patterns to geography member IDs.

        Returns {geo_pattern: member_id} for all matched services.

        Resolution priority:
        1. Municipal entries only (exclude SQ/RCMP/Provincial Police)
        2. Among municipal matches, prefer the highest memberId — StatCan
           assigns higher IDs to newer/reorganized services (e.g. Lévis
           has old member 64 with no data and new member 109 with data).
        """
        _NON_MUNICIPAL = {"provincial police", "royal canadian mounted police"}
        matches: dict[str, int] = {}

        for svc in POLICE_SERVICES:
            pattern_lower = svc.geo_pattern.lower()
            municipal_matches: list[int] = []
            all_matches: list[int] = []

            for mid, name in geo_members.items():
                name_lower = name.lower()
                if pattern_lower in name_lower:
                    all_matches.append(mid)
                    if not any(excl in name_lower for excl in _NON_MUNICIPAL):
                        municipal_matches.append(mid)

            candidates = municipal_matches or all_matches
            if candidates:
                matches[svc.geo_pattern] = max(candidates)
            else:
                logger.debug(f"StatCan: no geo match for pattern '{svc.geo_pattern}'")

        return matches

    def _resolve_violation_member_ids(
        self, viol_members: dict[int, str]
    ) -> dict[str, int]:
        """Find member IDs for our target violation categories.

        Returns {"total": member_id, "violent": member_id, "property": member_id}.
        """
        matches: dict[str, int] = {}
        for key, pattern in _TARGET_VIOLATIONS.items():
            pattern_lower = pattern.lower()
            for mid, name in viol_members.items():
                if pattern_lower in name.lower():
                    matches[key] = mid
                    break
            else:
                logger.warning(f"StatCan: no violation match for '{pattern}'")
        return matches

    @staticmethod
    def _make_coord(geo_mid: int, viol_mid: int, stats_mid: int) -> str:
        """Build a 10-position WDS coordinate string.

        StatCan WDS API requires exactly 10 period-separated dimension
        member IDs, with 0 for unused dimensions.
        """
        return f"{geo_mid}.{viol_mid}.{stats_mid}.0.0.0.0.0.0.0"

    async def get_crime_data(self, latest_n: int = 3) -> dict[str, dict]:
        """Fetch crime stats for all registered police services.

        Returns {municipality_name: {
            "year": int,
            "crime_count": int,
            "violent_crimes": int,
            "property_crimes": int,
            "crime_rate_per_1000": float,
            "crime_change_pct": float | None,
            "safety_score": float,
        }}
        """
        metadata = await self._fetch_metadata()
        if not metadata:
            logger.warning("StatCan: no metadata available, skipping crime fetch")
            return {}

        geo_ids = self._resolve_geo_member_ids(metadata["geo_members"])
        viol_ids = self._resolve_violation_member_ids(metadata["viol_members"])

        if not geo_ids or not viol_ids:
            logger.warning(
                f"StatCan: insufficient member IDs — "
                f"geo={len(geo_ids)}, viol={len(viol_ids)}"
            )
            return {}

        logger.info(
            f"StatCan: matched {len(geo_ids)} police services, "
            f"{len(viol_ids)} violation categories"
        )

        # Build batch coordinate requests.
        # Map each coordinate string → (geo_pattern, violation_key) for
        # result matching (API may not preserve request ordering).
        coord_map: dict[str, tuple[str, str]] = {}  # coord → (geo_pattern, viol_key)
        coord_requests = []

        for geo_pattern, geo_mid in geo_ids.items():
            for viol_key, viol_mid in viol_ids.items():
                coord = self._make_coord(geo_mid, viol_mid, _STATS_ACTUAL_INCIDENTS)
                coord_requests.append({
                    "productId": CUBE_ID,
                    "coordinate": coord,
                    "latestN": latest_n,
                })
                coord_map[coord] = (geo_pattern, viol_key)

        # Batch fetch all data in one API call
        client = await self._get_client()
        try:
            resp = await client.post(DATA_URL, json=coord_requests, timeout=60.0)
            resp.raise_for_status()
        except Exception:
            logger.warning("StatCan: crime data fetch failed", exc_info=True)
            return {}

        results = resp.json()
        if not isinstance(results, list):
            logger.warning("StatCan: unexpected response format")
            return {}

        # Parse results into per-service yearly data.
        # Match each result to its request via the coordinate field.
        # Structure: {geo_pattern: {viol_key: {year: value}}}
        service_data: dict[str, dict[str, dict[int, int]]] = {}

        for item in results:
            if item.get("status") != "SUCCESS":
                continue

            obj = item.get("object", {})
            coord = obj.get("coordinate", "")
            mapping = coord_map.get(coord)
            if not mapping:
                continue
            geo_pattern, viol_key = mapping

            for pt in obj.get("vectorDataPoint", []):
                year = int(pt["refPer"][:4])
                val = pt.get("value")
                if val is None:
                    continue

                if geo_pattern not in service_data:
                    service_data[geo_pattern] = {}
                if viol_key not in service_data[geo_pattern]:
                    service_data[geo_pattern][viol_key] = {}
                service_data[geo_pattern][viol_key][year] = int(val)

        # Convert to per-municipality crime stats
        municipality_stats: dict[str, dict] = {}

        for svc in POLICE_SERVICES:
            data = service_data.get(svc.geo_pattern)
            if not data:
                continue

            # Find the most recent year with total crime data.
            # Prefer "CC excl traffic", fall back to "all violations" if null.
            total_by_year = data.get("total", {})
            if not total_by_year:
                total_by_year = data.get("total_all", {})
            if not total_by_year:
                continue
            latest_year = max(total_by_year.keys())

            total = total_by_year.get(latest_year, 0)
            violent = data.get("violent", {}).get(latest_year, 0)
            prop = data.get("property", {}).get(latest_year, 0)

            # YoY change
            prev_years = sorted(y for y in total_by_year if y < latest_year)
            change_pct = None
            if prev_years:
                prev_total = total_by_year[prev_years[-1]]
                if prev_total > 0:
                    change_pct = round(((total - prev_total) / prev_total) * 100, 1)

            # Total population across all municipalities served
            total_pop = sum(svc.municipalities.values())

            # Distribute to each municipality by population share
            for muni_name, muni_pop in svc.municipalities.items():
                fraction = muni_pop / total_pop if total_pop > 0 else 1

                rate = round((total * fraction / muni_pop) * 1000, 1) if muni_pop > 0 else 0

                # Safety score: log-scale, average = 8
                safety = 8.0
                if change_pct is not None and change_pct < -5:
                    safety = min(10, safety + 0.5)

                municipality_stats[muni_name] = {
                    "year": latest_year,
                    "crime_count": round(total * fraction),
                    "violent_crimes": round(violent * fraction),
                    "property_crimes": round(prop * fraction),
                    "crime_rate_per_1000": rate,
                    "crime_change_pct": change_pct,
                    "safety_score": safety,
                }

        logger.info(
            f"StatCan: crime data for {len(municipality_stats)} municipalities "
            f"from {len(service_data)} police services"
        )
        return municipality_stats
