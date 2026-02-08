"""Quebec City neighbourhood data client (permits + crime/safety).

Combines two data sources:
1. Building permits — weekly-updated CSV from Données Québec
   (per-arrondissement, automated download)
2. Crime/safety — SPVQ annual report city-wide totals
   (hardcoded constants, updated manually each spring when report drops)

Data sources:
- Permits: donneesquebec.ca/recherche/dataset/permis-delivres-ville-de-quebec
  License: CC-BY 4.0, Updated: Weekly, Coverage: 2020-present
- Crime: ville.quebec.qc.ca/publications/docs_ville/rapport_annuel_police_YYYY.pdf
  SPVQ publishes city-wide totals only (no per-arrondissement breakdown).
  We apply a uniform safety score to all arrondissements.
"""

import csv
import io
import logging
import math
from datetime import date

import httpx

logger = logging.getLogger(__name__)

CSV_URL = (
    "https://www.donneesquebec.ca/recherche/dataset/"
    "879abf6e-c6b2-430a-b44a-16335467c6f6/resource/"
    "9555031e-cfc5-4b78-bec9-4ab84b549f67/download/vdq-permis.csv"
)

# The 6 main arrondissements of Quebec City (as they appear in the CSV).
VALID_ARRONDISSEMENTS = {
    "La Cite-Limoilou",
    "Les Rivieres",
    "Sainte-Foy--Sillery--Cap-Rouge",
    "Charlesbourg",
    "Beauport",
    "La Haute-Saint-Charles",
}

# Canonical names for DB storage (restore accents, normalize double-dashes).
_CANONICAL_NAME: dict[str, str] = {
    "La Cite-Limoilou": "La Cité-Limoilou",
    "Les Rivieres": "Les Rivières",
    "Sainte-Foy--Sillery--Cap-Rouge": "Sainte-Foy-Sillery-Cap-Rouge",
    "Charlesbourg": "Charlesbourg",
    "Beauport": "Beauport",
    "La Haute-Saint-Charles": "La Haute-Saint-Charles",
}

# DOMAINE → permit category mapping.
CONSTRUCTION_DOMAINS = {"Construction d'un batiment principal"}
TRANSFORM_DOMAINS = {"Renovation/Agrandissement"}
DEMOLITION_DOMAINS = {"Demolition/Deplacement"}

# ---------------------------------------------------------------------------
# SPVQ annual report crime data (city-wide totals, updated manually).
# Source: ville.quebec.qc.ca/publications/docs_ville/rapport_annuel_police_YYYY.pdf
# The SPVQ does not publish per-arrondissement breakdowns.
# ---------------------------------------------------------------------------
SPVQ_CRIME_DATA: dict[int, dict] = {
    2024: {
        "crimes_person": 8_892,   # infractions contre la personne
        "crimes_property": 12_797,  # infractions contre la propriété
        # Narrow violent subset: homicides(4) + attempts(11) + assault(5005) + robbery(96)
        "violent": 5_116,
        # Property total from report
        "property": 12_797,
        "population": 594_556,
    },
    2023: {
        "crimes_person": 9_019,
        "crimes_property": 13_259,
        "violent": 5_218,  # homicides(7) + attempts(10) + assault(5096) + robbery(103) + kidnapping(2 extra from sub-total rounding)
        "property": 13_259,
        "population": 594_556,
    },
    2022: {
        "crimes_person": 8_461,
        "crimes_property": 12_316,
        "violent": 4_953,  # homicides(4) + attempts(6) + assault(4851) + robbery(92)
        "property": 12_316,
        "population": 594_556,
    },
}

# 2021 Census populations per arrondissement (Statistics Canada).
# Used to distribute city-wide crime counts proportionally.
_ARROND_POP_2021: dict[str, int] = {
    "La Cité-Limoilou": 113_635,
    "Les Rivières": 76_705,
    "Sainte-Foy-Sillery-Cap-Rouge": 107_830,
    "Charlesbourg": 84_885,
    "Beauport": 81_770,
    "La Haute-Saint-Charles": 84_634,
}
_TOTAL_ARROND_POP = sum(_ARROND_POP_2021.values())  # ~549,459

# Uniform residential tax rate (per $100 of assessed value).
# Source: ville.quebec.qc.ca/apropos/profil-financier/taux-taxation.aspx
# Note: 2025 rate dropped due to new triennial assessment roll
# (property values increased ~23.5% on average).
_TAX_RATES: dict[int, float] = {
    2025: 0.7597,
    2024: 0.9072,
}


class QuebecCityPermitsClient:
    """Client for Quebec City's open data permits + SPVQ crime stats."""

    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=120.0)
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _download_csv(self) -> list[dict]:
        """Download and parse the full permits CSV (~15 MB)."""
        client = await self._get_client()
        resp = await client.get(CSV_URL)
        resp.raise_for_status()
        reader = csv.DictReader(io.StringIO(resp.text))
        return list(reader)

    @staticmethod
    def _compute_crime_fields(
        canonical_name: str, target_year: int
    ) -> dict | None:
        """Compute crime/safety fields for an arrondissement.

        Distributes city-wide SPVQ totals proportionally to arrondissement
        population. Safety score is uniform (same city-wide rate for all).
        Falls back to the most recent available SPVQ year if target_year
        data isn't published yet.
        """
        crime = SPVQ_CRIME_DATA.get(target_year)
        if not crime and SPVQ_CRIME_DATA:
            # Fall back to most recent available year
            latest = max(SPVQ_CRIME_DATA.keys())
            crime = SPVQ_CRIME_DATA[latest]
        if not crime:
            return None

        prev_year = max(y for y in SPVQ_CRIME_DATA if y < max(SPVQ_CRIME_DATA)) if len(SPVQ_CRIME_DATA) > 1 else None
        prev_crime = SPVQ_CRIME_DATA.get(prev_year) if prev_year else None
        pop = crime["population"]
        total = crime["crimes_person"] + crime["crimes_property"]
        city_rate = round((total / pop) * 1000, 1)

        # YoY change (city-wide)
        change_pct = None
        if prev_crime:
            prev_total = prev_crime["crimes_person"] + prev_crime["crimes_property"]
            if prev_total > 0:
                change_pct = round(((total - prev_total) / prev_total) * 100, 1)

        # Safety score: uniform across arrondissements since we only have
        # city-wide data.  ratio=1 → safety = 8 - log2(1)*3 = 8.0
        safety = 8.0
        if change_pct is not None and change_pct < -5:
            safety = min(10, safety + 0.5)

        # Distribute counts proportionally to arrondissement population
        arrond_pop = _ARROND_POP_2021.get(canonical_name, 0)
        fraction = arrond_pop / _TOTAL_ARROND_POP if _TOTAL_ARROND_POP else 0

        return {
            "crime_count": round(total * fraction),
            "violent_crimes": round(crime["violent"] * fraction),
            "property_crimes": round(crime["property"] * fraction),
            "crime_rate_per_1000": city_rate,
            "crime_change_pct": change_pct,
            "safety_score": safety,
        }

    async def get_neighbourhood_rows(
        self, min_year: int | None = None
    ) -> list[dict]:
        """Aggregate permits + crime by arrondissement and year.

        Returns list of dicts ready for upsert_neighbourhood_stats_batch().
        """
        if min_year is None:
            min_year = date.today().year - 3

        records = await self._download_csv()
        logger.info(f"Quebec City permits: downloaded {len(records)} records")

        # Aggregate permits by (canonical_arrondissement, year)
        agg: dict[tuple[str, int], dict[str, int]] = {}

        for rec in records:
            arrond = rec.get("ARRONDISSEMENT", "").strip()
            if arrond not in VALID_ARRONDISSEMENTS:
                continue

            date_str = rec.get("DATE_DELIVRANCE", "").strip()
            if len(date_str) < 4:
                continue
            try:
                year = int(date_str[:4])
            except ValueError:
                continue
            if year < min_year:
                continue

            canonical = _CANONICAL_NAME.get(arrond, arrond)
            key = (canonical, year)
            if key not in agg:
                agg[key] = {
                    "total": 0, "construction": 0,
                    "transform": 0, "demolition": 0,
                }

            agg[key]["total"] += 1
            domaine = rec.get("DOMAINE", "").strip()
            if domaine in CONSTRUCTION_DOMAINS:
                agg[key]["construction"] += 1
            elif domaine in TRANSFORM_DOMAINS:
                agg[key]["transform"] += 1
            elif domaine in DEMOLITION_DOMAINS:
                agg[key]["demolition"] += 1

        # Use the most recent complete year
        target_year = date.today().year - 1
        if agg:
            available_years = sorted({y for _, y in agg.keys()}, reverse=True)
            if target_year not in {y for _, y in agg.keys()} and available_years:
                target_year = available_years[0]

        # Resolve tax rate for the target year (uniform across arrondissements)
        tax_rate = _TAX_RATES.get(target_year) or _TAX_RATES.get(target_year + 1)

        # Build output rows (permits + crime + tax for each arrondissement)
        rows: list[dict] = []
        for canonical_name in sorted(_CANONICAL_NAME.values()):
            key = (canonical_name, target_year)
            counts = agg.get(key)

            row: dict = {
                "borough": canonical_name,
                "year": target_year,
                "source": "quebec_city_open_data",
            }
            if tax_rate is not None:
                row["tax_rate_residential"] = tax_rate
                row["tax_rate_total"] = tax_rate  # uniform, no additional per-$100 levies

            # Permit fields
            if counts:
                row.update({
                    "permit_count": counts["total"],
                    "permit_construction_count": counts["construction"],
                    "permit_transform_count": counts["transform"],
                    "permit_demolition_count": counts["demolition"],
                })

                # Gentrification signal from multi-year permit trends
                gentrify = None
                years_data = sorted(
                    [(y, agg[(n, y)]) for n, y in agg if n == canonical_name],
                    key=lambda t: t[0],
                )
                if len(years_data) >= 2:
                    earliest = years_data[0][1]
                    latest = years_data[-1][1]
                    if earliest["transform"] > 0:
                        growth = (
                            (latest["transform"] - earliest["transform"])
                            / earliest["transform"]
                        )
                        if growth > 0.3:
                            gentrify = "early"
                        if growth > 0.6:
                            gentrify = "mid"
                        if growth > 1.0:
                            gentrify = "mature"
                row["gentrification_signal"] = gentrify

            # Crime/safety fields (from SPVQ annual report)
            crime_fields = self._compute_crime_fields(canonical_name, target_year)
            if crime_fields:
                row.update(crime_fields)

            # Only emit rows that have at least some data
            if counts or crime_fields:
                rows.append(row)

        permit_total = sum(r.get("permit_count", 0) for r in rows)
        crime_total = sum(r.get("crime_count", 0) for r in rows)
        logger.info(
            f"Quebec City: {len(rows)} arrondissements, "
            f"{permit_total} permits + {crime_total} est. crimes for {target_year}"
        )
        return rows
