"""Longueuil agglomeration neighbourhood data client (crime + tax).

Data sources:
- Crime: SPAL annual report (hardcoded, updated manually each spring)
  Source: longueuil.quebec/fr/SPAL/bilan-annuel
  The SPAL serves the entire agglomeration (~440k population).
  City-wide totals only (no per-arrondissement breakdown).
- Tax rates: MAMH prévisionnelles CSV (automated download)
  Same pattern as sherbrooke_data.py.
- Building permits: not available as open data at the municipal level.
  Montreal CMA (StatCan 34-10-0292-01) is too broad to be meaningful.
"""

import csv
import io
import logging
from datetime import date

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SPAL annual report crime data (city-wide totals, updated manually).
# Source: longueuil.quebec/fr/SPAL/bilan-annuel
# The SPAL publishes city-wide totals (no per-arrondissement breakdown).
# ---------------------------------------------------------------------------
SPAL_CRIME_DATA: dict[int, dict] = {
    # Source: SPAL Rapport des activités 2024
    # cms.longueuil.quebec/.../Rapport%20des%20activités%202024%20du%20SPAL_0.pdf
    2024: {
        "crimes_person": 3_928,    # infractions contre la personne (reported "below 4,000")
        "crimes_property": 7_635,  # -9.1% vs 2023 (from report)
        "violent": 2_200,          # homicides(4) + assaults + robbery (estimated from subtotals)
        "property": 7_635,
        "population": 443_000,     # 2021 Census, agglomération (5 cities)
    },
    # Source: SPAL Rapport des activités 2023
    2023: {
        "crimes_person": 4_190,    # confirmed from report
        "crimes_property": 8_400,  # +11.2% vs 2022 (from report)
        "violent": 2_400,          # assaults(2,292) + homicides(4) + robbery(~100)
        "property": 8_400,
        "population": 443_000,
    },
}

# ---------------------------------------------------------------------------
# MAMH — Automated residential tax rate from Données Québec.
# "Données prévisionnelles non auditées" CSV, field CPALB01726.
# Longueuil cod_geo = 58227. Published annually ~January.
# ---------------------------------------------------------------------------
MAMH_CSV_URL_TEMPLATE = (
    "https://mamh.gouv.qc.ca/fichiersdonneesouvertes/"
    "Donn%C3%A9es-pr%C3%A9visionnelles-non-audit%C3%A9es-{year}"
    "-SimpleOccurrence.csv"
)
_LONGUEUIL_COD_GEO = "58227"
_MAMH_TAX_FIELD = "CPALB01726"  # residential general property tax rate

# Fallback residential tax rate (per $100 of assessed value).
# Used if MAMH CSV is unavailable. Updated manually from longueuil.quebec.
_TAX_RATES_FALLBACK: dict[int, float] = {
    2025: 0.6992,
    2024: 0.8718,
}


class LongueuilNeighbourhoodClient:
    """Client for Longueuil agglomeration neighbourhood data."""

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
        """Fetch residential tax rate from MAMH prévisionnelles CSV.

        Returns the rate per $100 for Longueuil, or None on failure.
        Falls back to hardcoded _TAX_RATES_FALLBACK.
        """
        url = MAMH_CSV_URL_TEMPLATE.format(year=year)
        client = await self._get_client()
        try:
            resp = await client.get(url, timeout=30.0, follow_redirects=True)
            resp.raise_for_status()
        except Exception:
            logger.debug(f"MAMH CSV for {year} not available, using fallback", exc_info=True)
            return _TAX_RATES_FALLBACK.get(year)

        text = resp.text.lstrip("\ufeff")  # strip BOM
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            if row.get("cod_geo", "").strip() == _LONGUEUIL_COD_GEO:
                raw = row.get(_MAMH_TAX_FIELD, "").strip()
                if raw:
                    try:
                        rate = float(raw)
                        logger.info(f"MAMH: Longueuil {year} residential tax rate = {rate}")
                        return rate
                    except ValueError:
                        pass

        logger.info(f"MAMH: Longueuil not found in {year} CSV, using fallback")
        return _TAX_RATES_FALLBACK.get(year)

    @staticmethod
    def _compute_crime_fields(target_year: int) -> dict | None:
        """Compute crime/safety fields for Longueuil (city-wide).

        Uses hardcoded SPAL annual report data. Falls back to the most
        recent available year if target_year data isn't published yet.
        """
        crime = SPAL_CRIME_DATA.get(target_year)
        if not crime and SPAL_CRIME_DATA:
            latest = max(SPAL_CRIME_DATA.keys())
            crime = SPAL_CRIME_DATA[latest]
        if not crime:
            return None

        prev_year = max(
            (y for y in SPAL_CRIME_DATA if y < max(SPAL_CRIME_DATA)), default=None
        )
        prev_crime = SPAL_CRIME_DATA.get(prev_year) if prev_year else None
        pop = crime["population"]
        total = crime["crimes_person"] + crime["crimes_property"]
        city_rate = round((total / pop) * 1000, 1)

        # YoY change (city-wide)
        change_pct = None
        if prev_crime:
            prev_total = prev_crime["crimes_person"] + prev_crime["crimes_property"]
            if prev_total > 0:
                change_pct = round(((total - prev_total) / prev_total) * 100, 1)

        # Safety score: uniform since we only have city-wide data.
        # ratio=1 → safety = 8 - log2(1)*3 = 8.0
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
        """Compute neighbourhood stats for Longueuil.

        Returns list of dicts ready for upsert_neighbourhood_stats_batch().
        Single row for the whole agglomeration.
        """
        if year is None:
            year = date.today().year - 1

        row: dict = {
            "borough": "Longueuil",
            "year": year,
            "source": "longueuil_spal",
        }

        # Tax rate from MAMH (automated)
        tax_rate = await self._fetch_mamh_tax_rate(year)
        if tax_rate is not None:
            row["tax_rate_residential"] = tax_rate
            row["tax_rate_total"] = tax_rate

        # Crime/safety fields (from SPAL annual report)
        crime_fields = self._compute_crime_fields(year)
        if crime_fields:
            row.update(crime_fields)

        # Housing starts from CMHC (automated)
        try:
            from .cmhc_starts import CMHCStartsClient

            starts_client = CMHCStartsClient()
            try:
                starts_data = await starts_client.get_starts_data()
                starts = starts_data.get("Longueuil")
                if starts:
                    row.update(starts)
            finally:
                await starts_client.close()
        except Exception:
            logger.warning("CMHC starts fetch failed (non-blocking)", exc_info=True)

        has_data = tax_rate is not None or crime_fields is not None or "housing_starts" in row
        if has_data:
            logger.info(
                f"Longueuil: 1 row for {year}"
                + (f", tax rate {tax_rate}/100$" if tax_rate else "")
                + (f", {crime_fields['crime_count']} crimes" if crime_fields else "")
                + (f", {row['housing_starts']} starts" if "housing_starts" in row else "")
            )
            return [row]

        logger.warning(f"Longueuil: no data available for {year}")
        return []
