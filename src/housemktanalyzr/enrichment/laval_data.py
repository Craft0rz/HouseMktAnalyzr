"""Laval neighbourhood data client (crime + tax + permits).

Data sources:
- Crime: SPL annual report (hardcoded, updated manually each spring)
  Source: laval.ca → Service de police
  City-wide totals only (Laval is a single-tier municipality).
- Tax rates: MAMH prévisionnelles CSV (automated download)
- Building permits: Données Québec — "Permis de construction" (Ville de Laval)
  Updated daily, covers 1991-present. CSV format, CC-BY 4.0.
  Dataset: donneesquebec.ca/recherche/dataset/permis-de-construction
"""

import csv
import io
import logging
from datetime import date

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SPL annual report crime data (city-wide totals, updated manually).
# Source: laval.ca → Service de police → Bilan annuel
# ---------------------------------------------------------------------------
SPL_CRIME_DATA: dict[int, dict] = {
    # Source: SPL Rapport d'activités 2024
    # laval.ca/organisation-municipale/salle-presse/communiques-presse/rapport-dactivites-2024-spl/
    2024: {
        "crimes_person": 5_300,    # 10-year peak, +11% vs 2023 (from report)
        "crimes_property": 7_765,  # -10% vs 2023 (confirmed from report)
        "violent": 2_900,          # homicides(7) + attempts(4) + domestic(1,359) subset
        "property": 7_765,
        "population": 438_366,     # 2021 Census
    },
    # Source: SPL Rapport d'activités 2023
    # Total criminal events: 18,688
    2023: {
        "crimes_person": 4_800,    # estimated from total events(18,688) - property - other
        "crimes_property": 8_675,  # confirmed from report
        "violent": 2_700,          # homicides(9) + attempts(16) + assaults + robbery
        "property": 8_675,
        "population": 438_366,
    },
}

# ---------------------------------------------------------------------------
# Building permits — Données Québec (Ville de Laval), CSV download.
# Updated daily, covers 1991-present.
# ---------------------------------------------------------------------------
PERMITS_CSV_URL = (
    "https://www.donneesquebec.ca/recherche/dataset/"
    "c7808c42-e401-49f0-8049-df3c809d5982/resource/"
    "d4731ee2-b1e5-4a31-bc56-4e13115e74ef/download/"
    "permis-de-construction.csv"
)

# Permit type classification by TYPE_PERMIS code.
# PN = Permis de construction - nouvelle, PR = Permis de rénovation,
# PD = Permis de démolition.  Also match via TYPE_PERMIS_DESCR for safety.
_CONSTRUCTION_CODES = {"PN"}
_TRANSFORM_CODES = {"PR"}
_DEMOLITION_CODES = {"PD"}
_CONSTRUCTION_DESCR = {"nouvelle", "construction"}
_TRANSFORM_DESCR = {"rénovation", "renovation", "transformation", "agrandissement"}
_DEMOLITION_DESCR = {"démolition", "demolition"}

# ---------------------------------------------------------------------------
# MAMH — Automated residential tax rate from Données Québec.
# Laval cod_geo = 65005. Published annually ~January.
# ---------------------------------------------------------------------------
MAMH_CSV_URL_TEMPLATE = (
    "https://mamh.gouv.qc.ca/fichiersdonneesouvertes/"
    "Donn%C3%A9es-pr%C3%A9visionnelles-non-audit%C3%A9es-{year}"
    "-SimpleOccurrence.csv"
)
_LAVAL_COD_GEO = "65005"
_MAMH_TAX_FIELD = "CPALB01726"

# Fallback residential tax rate (per $100 of assessed value).
_TAX_RATES_FALLBACK: dict[int, float] = {
    2025: 0.7290,
    2024: 0.7290,
}


class LavalNeighbourhoodClient:
    """Client for Laval neighbourhood data."""

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
            if row.get("cod_geo", "").strip() == _LAVAL_COD_GEO:
                raw = row.get(_MAMH_TAX_FIELD, "").strip()
                if raw:
                    try:
                        rate = float(raw)
                        logger.info(f"MAMH: Laval {year} residential tax rate = {rate}")
                        return rate
                    except ValueError:
                        pass

        logger.info(f"MAMH: Laval not found in {year} CSV, using fallback")
        return _TAX_RATES_FALLBACK.get(year)

    async def _fetch_permits(self, min_year: int) -> dict[int, dict[str, int]]:
        """Download and aggregate building permits from Données Québec.

        Returns {year: {"total": N, "construction": N, "transform": N, "demolition": N}}.
        """
        client = await self._get_client()
        try:
            resp = await client.get(PERMITS_CSV_URL)
            resp.raise_for_status()
        except Exception:
            logger.warning("Laval permits CSV download failed", exc_info=True)
            return {}

        text = resp.text.lstrip("\ufeff")
        reader = csv.DictReader(io.StringIO(text))

        agg: dict[int, dict[str, int]] = {}
        for rec in reader:
            date_str = rec.get("DATE_EMISSION", "").strip()
            if len(date_str) < 4:
                continue
            try:
                year = int(date_str[:4])
            except ValueError:
                continue
            if year < min_year:
                continue

            if year not in agg:
                agg[year] = {"total": 0, "construction": 0, "transform": 0, "demolition": 0}

            agg[year]["total"] += 1

            # Classify by TYPE_PERMIS code first, then fallback to description
            code = rec.get("TYPE_PERMIS", "").strip().upper()
            descr = rec.get("TYPE_PERMIS_DESCR", "").strip().lower()
            if code in _CONSTRUCTION_CODES or any(k in descr for k in _CONSTRUCTION_DESCR):
                agg[year]["construction"] += 1
            elif code in _TRANSFORM_CODES or any(k in descr for k in _TRANSFORM_DESCR):
                agg[year]["transform"] += 1
            elif code in _DEMOLITION_CODES or any(k in descr for k in _DEMOLITION_DESCR):
                agg[year]["demolition"] += 1

        if agg:
            latest = max(agg.keys())
            logger.info(
                f"Laval permits: {agg[latest]['total']} permits in {latest} "
                f"({len(agg)} years loaded)"
            )
        return agg

    @staticmethod
    def _compute_crime_fields(target_year: int) -> dict | None:
        """Compute crime/safety fields for Laval (city-wide)."""
        crime = SPL_CRIME_DATA.get(target_year)
        if not crime and SPL_CRIME_DATA:
            latest = max(SPL_CRIME_DATA.keys())
            crime = SPL_CRIME_DATA[latest]
        if not crime:
            return None

        prev_year = max(
            (y for y in SPL_CRIME_DATA if y < max(SPL_CRIME_DATA)), default=None
        )
        prev_crime = SPL_CRIME_DATA.get(prev_year) if prev_year else None
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
        """Compute neighbourhood stats for Laval.

        Returns list of dicts ready for upsert_neighbourhood_stats_batch().
        Single row for the whole city.
        """
        if year is None:
            year = date.today().year - 1

        row: dict = {
            "borough": "Laval",
            "year": year,
            "source": "laval_open_data",
        }

        # Tax rate from MAMH (automated)
        tax_rate = await self._fetch_mamh_tax_rate(year)
        if tax_rate is not None:
            row["tax_rate_residential"] = tax_rate
            row["tax_rate_total"] = tax_rate

        # Building permits from Données Québec (automated)
        permits_by_year = await self._fetch_permits(min_year=year - 2)
        permits = permits_by_year.get(year)
        if permits:
            row["permit_count"] = permits["total"]
            row["permit_construction_count"] = permits["construction"]
            row["permit_transform_count"] = permits["transform"]
            row["permit_demolition_count"] = permits["demolition"]

            # Gentrification signal from multi-year permit trends
            gentrify = None
            years_sorted = sorted(permits_by_year.keys())
            if len(years_sorted) >= 2:
                earliest = permits_by_year[years_sorted[0]]
                latest = permits_by_year[years_sorted[-1]]
                if earliest["transform"] > 0:
                    growth = (latest["transform"] - earliest["transform"]) / earliest["transform"]
                    if growth > 0.3:
                        gentrify = "early"
                    if growth > 0.6:
                        gentrify = "mid"
                    if growth > 1.0:
                        gentrify = "mature"
            row["gentrification_signal"] = gentrify

        # Crime/safety fields (from SPL annual report)
        crime_fields = self._compute_crime_fields(year)
        if crime_fields:
            row.update(crime_fields)

        # Housing starts from CMHC (automated)
        try:
            from .cmhc_starts import CMHCStartsClient

            starts_client = CMHCStartsClient()
            try:
                starts_data = await starts_client.get_starts_data()
                starts = starts_data.get("Laval")
                if starts:
                    row.update(starts)
            finally:
                await starts_client.close()
        except Exception:
            logger.warning("CMHC starts fetch failed (non-blocking)", exc_info=True)

        has_data = tax_rate is not None or permits is not None or crime_fields is not None or "housing_starts" in row
        if has_data:
            logger.info(
                f"Laval: 1 row for {year}"
                + (f", tax rate {tax_rate}/100$" if tax_rate else "")
                + (f", {permits['total']} permits" if permits else "")
                + (f", {crime_fields['crime_count']} crimes" if crime_fields else "")
                + (f", {row['housing_starts']} starts" if "housing_starts" in row else "")
            )
            return [row]

        logger.warning(f"Laval: no data available for {year}")
        return []
