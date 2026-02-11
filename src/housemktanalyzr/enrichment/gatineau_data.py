"""Gatineau neighbourhood data client (crime + tax).

Data sources:
- Crime: SPVG annual report (hardcoded, updated manually each spring)
  Source: gatineau.ca → Service de police → Bilan annuel
  City-wide totals only (no per-sector breakdown available).
- Tax rates: MAMH prévisionnelles CSV (automated download)
- Building permits: not available as machine-readable open data.
  Monthly PDF reports only at gatineau.ca.
"""

import csv
import io
import logging
from datetime import date

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SPVG annual report crime data (city-wide totals, updated manually).
# Source: gatineau.ca → Service de police → Bilan annuel / Portail criminalité
# Crime portal covers 7 categories from Jan 2022 onward (view-only map).
# ---------------------------------------------------------------------------
SPVG_CRIME_DATA: dict[int, dict] = {
    # Source: SPVG bilan 2024
    # ledroit.com/actualites/.../un-bilan-policier-marque-par-la-hausse-...
    2024: {
        "crimes_person": 3_980,    # confirmed from report
        "crimes_property": 6_424,  # confirmed from report
        "violent": 2_381,          # assault simple(1,535) + armé(541) + sexual(305)
        "property": 6_424,
        "population": 291_806,     # 2021 Census
    },
    # Source: SPVG bilan 2022 (2023 detailed breakdown not publicly available)
    # ici.radio-canada.ca/nouvelle/1983408/bilan-2022-spvg-...
    2022: {
        "crimes_person": 3_711,    # confirmed (+17% vs 2021)
        "crimes_property": 6_435,  # confirmed (+32% vs 2021)
        "violent": 2_100,          # estimated from 2024 ratio
        "property": 6_435,
        "population": 291_806,
    },
}

# ---------------------------------------------------------------------------
# MAMH — Automated residential tax rate from Données Québec.
# Gatineau cod_geo = 81017. Published annually ~January.
# ---------------------------------------------------------------------------
MAMH_CSV_URL_TEMPLATE = (
    "https://mamh.gouv.qc.ca/fichiersdonneesouvertes/"
    "Donn%C3%A9es-pr%C3%A9visionnelles-non-audit%C3%A9es-{year}"
    "-SimpleOccurrence.csv"
)
_GATINEAU_COD_GEO = "81017"
_MAMH_TAX_FIELD = "CPALB01726"

# Fallback residential tax rate (per $100 of assessed value).
_TAX_RATES_FALLBACK: dict[int, float] = {
    2025: 0.8915,
    2024: 1.0627,
}


class GatineauNeighbourhoodClient:
    """Client for Gatineau neighbourhood data."""

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

    async def _fetch_mamh_tax_rate(self, year: int) -> float | None:
        """Fetch residential tax rate from MAMH prévisionnelles CSV."""
        url = MAMH_CSV_URL_TEMPLATE.format(year=year)
        client = await self._get_client()
        try:
            resp = await client.get(url, timeout=30.0, follow_redirects=True)
            resp.raise_for_status()
        except Exception:
            logger.debug(f"MAMH CSV for {year} not available, using fallback", exc_info=True)
            return _TAX_RATES_FALLBACK.get(year)

        text = resp.text.lstrip("\ufeff")
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            if row.get("cod_geo", "").strip() == _GATINEAU_COD_GEO:
                raw = row.get(_MAMH_TAX_FIELD, "").strip()
                if raw:
                    try:
                        rate = float(raw)
                        logger.info(f"MAMH: Gatineau {year} residential tax rate = {rate}")
                        return rate
                    except ValueError:
                        pass

        logger.info(f"MAMH: Gatineau not found in {year} CSV, using fallback")
        return _TAX_RATES_FALLBACK.get(year)

    @staticmethod
    def _compute_crime_fields(target_year: int) -> dict | None:
        """Compute crime/safety fields for Gatineau (city-wide)."""
        crime = SPVG_CRIME_DATA.get(target_year)
        if not crime and SPVG_CRIME_DATA:
            latest = max(SPVG_CRIME_DATA.keys())
            crime = SPVG_CRIME_DATA[latest]
        if not crime:
            return None

        prev_year = max(
            (y for y in SPVG_CRIME_DATA if y < max(SPVG_CRIME_DATA)), default=None
        )
        prev_crime = SPVG_CRIME_DATA.get(prev_year) if prev_year else None
        pop = crime["population"]
        total = crime["crimes_person"] + crime["crimes_property"]
        city_rate = round((total / pop) * 1000, 1)

        change_pct = None
        if prev_crime:
            prev_total = prev_crime["crimes_person"] + prev_crime["crimes_property"]
            if prev_total > 0:
                change_pct = round(((total - prev_total) / prev_total) * 100, 1)

        safety = 8.0
        if change_pct is not None and change_pct < -5:
            safety = min(10, safety + 0.5)

        return {
            "crime_count": total,
            "violent_crimes": crime["violent"],
            "property_crimes": crime["property"],
            "crime_rate_per_1000": city_rate,
            "crime_change_pct": change_pct,
            "safety_score": safety,
        }

    async def get_neighbourhood_rows(self, year: int | None = None) -> list[dict]:
        """Compute neighbourhood stats for Gatineau.

        Returns list of dicts ready for upsert_neighbourhood_stats_batch().
        Single row for the whole city.
        """
        if year is None:
            year = date.today().year - 1

        row: dict = {
            "borough": "Gatineau",
            "year": year,
            "source": "gatineau_spvg",
        }

        # Tax rate from MAMH (automated)
        tax_rate = await self._fetch_mamh_tax_rate(year)
        if tax_rate is not None:
            row["tax_rate_residential"] = tax_rate
            row["tax_rate_total"] = tax_rate

        # Crime/safety fields (from SPVG annual report)
        crime_fields = self._compute_crime_fields(year)
        if crime_fields:
            row.update(crime_fields)

        # Housing starts from CMHC (automated)
        try:
            from .cmhc_starts import CMHCStartsClient

            starts_client = CMHCStartsClient()
            try:
                starts_data = await starts_client.get_starts_data()
                starts = starts_data.get("Gatineau")
                if starts:
                    row.update(starts)
            finally:
                await starts_client.close()
        except Exception:
            logger.warning("CMHC starts fetch failed (non-blocking)", exc_info=True)

        has_data = tax_rate is not None or crime_fields is not None or "housing_starts" in row
        if has_data:
            logger.info(
                f"Gatineau: 1 row for {year}"
                + (f", tax rate {tax_rate}/100$" if tax_rate else "")
                + (f", {crime_fields['crime_count']} crimes" if crime_fields else "")
                + (f", {row['housing_starts']} starts" if "housing_starts" in row else "")
            )
            return [row]

        logger.warning(f"Gatineau: no data available for {year}")
        return []
