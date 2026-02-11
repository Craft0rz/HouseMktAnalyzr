"""Generic neighbourhood data client for smaller Quebec municipalities.

Provides MAMH tax rates and StatCan crime statistics for municipalities
that lack dedicated open data portals. Crime data comes from StatCan
Table 35-10-0179-01 (police-reported incidents) via the WDS coordinate
API. Municipalities policed by the SQ or covered by a parent city's
police service won't have crime data here (handled by their dedicated
client instead).

Data sources:
- Tax rates: MAMH prévisionnelles CSV (automated download, all municipalities)
  Same pattern as sherbrooke_data.py / longueuil_data.py.
- Crime: StatCan Table 35-10-0179-01 via WDS API (automated, batch fetch)
  Covers municipal police services and régies intermunicipales.
"""

import csv
import io
import logging
from datetime import date

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MAMH — Automated residential tax rate from Données Québec.
# "Données prévisionnelles non auditées" CSV, field CPALB01726.
# Published annually ~January. One CSV covers ALL Quebec municipalities.
# ---------------------------------------------------------------------------
MAMH_CSV_URL_TEMPLATE = (
    "https://mamh.gouv.qc.ca/fichiersdonneesouvertes/"
    "Donn%C3%A9es-pr%C3%A9visionnelles-non-audit%C3%A9es-{year}"
    "-SimpleOccurrence.csv"
)
_MAMH_TAX_FIELD = "CPALB01726"  # residential general property tax rate

# ---------------------------------------------------------------------------
# Municipality registry: display name → MAMH cod_geo.
# Verified against mamh.gouv.qc.ca/repertoire-des-municipalites/
# ---------------------------------------------------------------------------
MUNICIPALITIES: dict[str, str] = {
    # --- Laurentides ---
    "Blainville": "73015",
    "Saint-Jérôme": "75017",
    "Mirabel": "74005",
    "Sainte-Thérèse": "73010",
    "Boisbriand": "73005",
    "Saint-Eustache": "72005",
    # --- Lanaudière ---
    "Terrebonne": "64008",
    "Repentigny": "60013",
    "Mascouche": "64015",
    # --- Montérégie (South Shore, outside Longueuil agglomeration) ---
    "Châteauguay": "67050",
    "Saint-Jean-sur-Richelieu": "56083",
    "La Prairie": "67015",
    "Chambly": "57005",
    "Candiac": "67020",
    "Saint-Constant": "67035",
    "Beloeil": "57040",
    "Vaudreuil-Dorion": "71083",
    "Saint-Bruno-de-Montarville": "58037",
    # --- Capitale-Nationale (outside Quebec City boroughs) ---
    "Lévis": "25213",
    "Saint-Augustin-de-Desmaures": "23072",
    # --- Estrie (outside Sherbrooke arrondissements) ---
    "Magog": "45072",
}


class GenericMunicipalityClient:
    """Fetches MAMH tax rates for a batch of municipalities in one CSV download."""

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

    async def _download_mamh_csv(self, year: int) -> dict[str, float]:
        """Download the MAMH CSV and extract tax rates for all target municipalities.

        Returns {cod_geo: tax_rate} for all municipalities found in the CSV.
        """
        url = MAMH_CSV_URL_TEMPLATE.format(year=year)
        client = await self._get_client()
        try:
            resp = await client.get(url, timeout=60.0, follow_redirects=True)
            resp.raise_for_status()
        except Exception:
            logger.warning(f"MAMH CSV for {year} not available", exc_info=True)
            return {}

        # Build set of cod_geos we care about for fast lookup
        target_codes = set(MUNICIPALITIES.values())

        text = resp.text.lstrip("\ufeff")  # strip BOM
        reader = csv.DictReader(io.StringIO(text))
        results: dict[str, float] = {}
        for row in reader:
            code = row.get("cod_geo", "").strip()
            if code not in target_codes:
                continue
            raw = row.get(_MAMH_TAX_FIELD, "").strip()
            if raw:
                try:
                    results[code] = float(raw)
                except ValueError:
                    pass

        logger.info(f"MAMH: found tax rates for {len(results)}/{len(target_codes)} municipalities in {year}")
        return results

    async def get_neighbourhood_rows(self, year: int | None = None) -> list[dict]:
        """Fetch tax rates and crime stats for all registered municipalities.

        Returns list of dicts ready for upsert_neighbourhood_stats_batch().
        One row per municipality. Crime data is merged from StatCan when
        available (municipalities with their own police service or régie).
        """
        if year is None:
            year = date.today().year - 1

        # Single CSV download covers all municipalities
        rates_by_code = await self._download_mamh_csv(year)

        # Fetch StatCan crime data (batch API call for all police services)
        crime_data: dict[str, dict] = {}
        try:
            from .statcan_crime import StatCanCrimeClient

            crime_client = StatCanCrimeClient()
            try:
                crime_data = await crime_client.get_crime_data(latest_n=3)
                if crime_data:
                    logger.info(
                        f"StatCan crime: fetched data for {len(crime_data)} municipalities"
                    )
            finally:
                await crime_client.close()
        except Exception:
            logger.warning("StatCan crime data fetch failed (non-blocking)", exc_info=True)

        # Fetch CMHC housing starts (one CSV per CMA, covers all target cities)
        starts_data: dict[str, dict] = {}
        try:
            from .cmhc_starts import CMHCStartsClient

            starts_client = CMHCStartsClient()
            try:
                starts_data = await starts_client.get_starts_data()
                if starts_data:
                    logger.info(
                        f"CMHC starts: fetched data for {len(starts_data)} municipalities"
                    )
            finally:
                await starts_client.close()
        except Exception:
            logger.warning("CMHC starts fetch failed (non-blocking)", exc_info=True)

        rows: list[dict] = []
        for name, code in MUNICIPALITIES.items():
            rate = rates_by_code.get(code)
            crime = crime_data.get(name)
            starts = starts_data.get(name)

            # Skip municipality if no data at all
            if rate is None and crime is None and starts is None:
                continue

            row: dict = {
                "borough": name,
                "year": year,
                "source": "mamh_generic",
            }

            if rate is not None:
                row["tax_rate_residential"] = rate
                row["tax_rate_total"] = rate

            if crime is not None:
                row["crime_count"] = crime["crime_count"]
                row["violent_crimes"] = crime["violent_crimes"]
                row["property_crimes"] = crime["property_crimes"]
                row["crime_rate_per_1000"] = crime["crime_rate_per_1000"]
                row["crime_change_pct"] = crime["crime_change_pct"]
                row["safety_score"] = crime["safety_score"]

            if starts is not None:
                row["housing_starts"] = starts["housing_starts"]
                row["starts_single"] = starts["starts_single"]
                row["starts_semi"] = starts["starts_semi"]
                row["starts_row"] = starts["starts_row"]
                row["starts_apartment"] = starts["starts_apartment"]

            rows.append(row)

        tax_rows = [r for r in rows if "tax_rate_residential" in r]
        crime_rows = [r for r in rows if "crime_count" in r]
        starts_rows = [r for r in rows if "housing_starts" in r]
        if rows:
            logger.info(
                f"Generic municipalities: {len(rows)} rows for {year} "
                f"({len(tax_rows)} with tax, {len(crime_rows)} with crime, "
                f"{len(starts_rows)} with starts)"
            )
            if tax_rows:
                logger.info(
                    f"  Tax rates range: "
                    f"{min(r['tax_rate_residential'] for r in tax_rows):.4f}"
                    f"-{max(r['tax_rate_residential'] for r in tax_rows):.4f}/100$"
                )
        else:
            logger.warning(f"Generic municipalities: no data available for {year}")

        return rows
