"""Montreal Open Data client for crime, permits, and tax rates.

Queries the CKAN DataStore API at donnees.montreal.ca.
No authentication required. All data is CC-BY 4.0 licensed.

Data sources:
- Crime (SPVM): https://donnees.montreal.ca/dataset/actes-criminels
- Building Permits: https://donnees.montreal.ca/dataset/permis-construction
- Tax Rates: https://donnees.montreal.ca/dataset/taux-de-taxation-et-tarification
"""

import csv
import io
import logging
from dataclasses import dataclass, field
from datetime import date

import httpx

logger = logging.getLogger(__name__)

CKAN_BASE = "https://donnees.montreal.ca/api/3/action"

# Resource IDs for DataStore queries
RESOURCE_IDS = {
    "crime": "c6f482bf-bf0f-4960-8b2f-9982c211addd",
    "permits_stats": "6f875764-9353-43ee-9b7e-0a6abb647c7c",
    "tax_rates": "58a8021d-3232-48e4-a5da-27450435e233",
}

# PDQ (police district) → borough mapping
# Montreal island only — PDQs outside the island are excluded
PDQ_TO_BOROUGH = {
    "1": "Ville-Marie",
    "2": "Ville-Marie",
    "3": "Ville-Marie",
    "4": "Ville-Marie",
    "5": "Le Plateau-Mont-Royal",
    "7": "Outremont",
    "8": "Côte-des-Neiges-Notre-Dame-de-Grâce",
    "9": "Ahuntsic-Cartierville",
    "10": "Ahuntsic-Cartierville",
    "11": "Montréal-Nord",
    "12": "Saint-Léonard",
    "13": "Le Plateau-Mont-Royal",
    "15": "Saint-Laurent",
    "16": "Rivière-des-Prairies-Pointe-aux-Trembles",
    "17": "Rivière-des-Prairies-Pointe-aux-Trembles",
    "20": "Mercier-Hochelaga-Maisonneuve",
    "21": "Mercier-Hochelaga-Maisonneuve",
    "22": "Anjou",
    "23": "Rosemont-La Petite-Patrie",
    "24": "Verdun",
    "26": "Lachine",
    "27": "Pierrefonds-Roxboro",
    "30": "Le Sud-Ouest",
    "31": "Côte-des-Neiges-Notre-Dame-de-Grâce",
    "33": "LaSalle",
    "35": "Villeray-Saint-Michel-Parc-Extension",
    "50": "Métro (STM)",
}

# Borough name normalization for matching across datasets
BOROUGH_ALIASES = {
    "ahuntsic": "Ahuntsic-Cartierville",
    "ahuntsic-cartierville": "Ahuntsic-Cartierville",
    "anjou": "Anjou",
    "cote-des-neiges": "Côte-des-Neiges-Notre-Dame-de-Grâce",
    "cdn": "Côte-des-Neiges-Notre-Dame-de-Grâce",
    "cdn-ndg": "Côte-des-Neiges-Notre-Dame-de-Grâce",
    "notre-dame-de-grace": "Côte-des-Neiges-Notre-Dame-de-Grâce",
    "ndg": "Côte-des-Neiges-Notre-Dame-de-Grâce",
    "lachine": "Lachine",
    "lasalle": "LaSalle",
    "le-plateau-mont-royal": "Le Plateau-Mont-Royal",
    "plateau": "Le Plateau-Mont-Royal",
    "plateau-mont-royal": "Le Plateau-Mont-Royal",
    "le-sud-ouest": "Le Sud-Ouest",
    "sud-ouest": "Le Sud-Ouest",
    "mercier-hochelaga-maisonneuve": "Mercier-Hochelaga-Maisonneuve",
    "hochelaga": "Mercier-Hochelaga-Maisonneuve",
    "hochelaga-maisonneuve": "Mercier-Hochelaga-Maisonneuve",
    "montreal-nord": "Montréal-Nord",
    "outremont": "Outremont",
    "pierrefonds": "Pierrefonds-Roxboro",
    "pierrefonds-roxboro": "Pierrefonds-Roxboro",
    "riviere-des-prairies": "Rivière-des-Prairies-Pointe-aux-Trembles",
    "rdp": "Rivière-des-Prairies-Pointe-aux-Trembles",
    "rosemont": "Rosemont-La Petite-Patrie",
    "rosemont-la-petite-patrie": "Rosemont-La Petite-Patrie",
    "saint-laurent": "Saint-Laurent",
    "saint-leonard": "Saint-Léonard",
    "verdun": "Verdun",
    "ville-marie": "Ville-Marie",
    "downtown": "Ville-Marie",
    "villeray": "Villeray-Saint-Michel-Parc-Extension",
    "villeray-saint-michel-parc-extension": "Villeray-Saint-Michel-Parc-Extension",
    "parc-extension": "Villeray-Saint-Michel-Parc-Extension",
    # Demerged cities (not Montreal boroughs but still in agglomeration)
    "l'ile-bizard-sainte-genevieve": "L'Île-Bizard-Sainte-Geneviève",
    "ile-bizard": "L'Île-Bizard-Sainte-Geneviève",
}

# Crime categories for classification
VIOLENT_CRIMES = {"Vols qualifies", "Infractions entrainant la mort"}
PROPERTY_CRIMES = {
    "Vol dans / sur vehicule a moteur",
    "Introduction",
    "Vol de vehicule a moteur",
    "Mefait",
}


def normalize_borough(name: str) -> str | None:
    """Normalize a city/borough name to the canonical borough name."""
    key = name.lower().strip().replace(" ", "-").replace("'", "'")
    if key in BOROUGH_ALIASES:
        return BOROUGH_ALIASES[key]
    # Try partial matching
    for alias, canonical in BOROUGH_ALIASES.items():
        if key in alias or alias in key:
            return canonical
    return None


@dataclass
class CrimeStats:
    """Crime statistics for a borough/year."""
    borough: str
    year: int
    total_crimes: int = 0
    violent_crimes: int = 0
    property_crimes: int = 0
    crime_rate_per_1000: float | None = None
    year_over_year_change_pct: float | None = None


@dataclass
class PermitStats:
    """Building permit statistics for a borough/year."""
    borough: str
    year: int
    total_permits: int = 0
    construction_permits: int = 0
    transform_permits: int = 0
    demolition_permits: int = 0
    total_cost: float = 0
    estimated_work_cost: float = 0


@dataclass
class TaxRate:
    """Residential property tax rate for a borough/year."""
    borough: str
    year: int
    residential_rate: float  # per $100 of assessed value
    total_tax_rate: float  # sum of all applicable rates


@dataclass
class NeighbourhoodStats:
    """Combined neighbourhood statistics."""
    borough: str
    crime: CrimeStats | None = None
    crime_previous: CrimeStats | None = None
    permits: PermitStats | None = None
    tax: TaxRate | None = None
    safety_score: float | None = None  # 0-10, higher is safer
    gentrification_signal: str | None = None  # "early", "mid", "mature", "none"


class MontrealOpenDataClient:
    """Client for Montreal's CKAN DataStore API."""

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

    async def _datastore_sql(self, sql: str) -> list[dict]:
        """Execute a SQL query against the CKAN DataStore."""
        client = await self._get_client()
        resp = await client.get(
            f"{CKAN_BASE}/datastore_search_sql",
            params={"sql": sql},
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise RuntimeError(f"CKAN API error: {data.get('error', 'Unknown')}")
        return data["result"]["records"]

    async def _datastore_search(
        self, resource_id: str, limit: int = 1000, offset: int = 0,
        filters: dict | None = None,
    ) -> list[dict]:
        """Query the DataStore with optional filters."""
        client = await self._get_client()
        params: dict = {
            "resource_id": resource_id,
            "limit": limit,
            "offset": offset,
        }
        if filters:
            import json
            params["filters"] = json.dumps(filters)
        resp = await client.get(f"{CKAN_BASE}/datastore_search", params=params)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            raise RuntimeError(f"CKAN API error: {data.get('error', 'Unknown')}")
        return data["result"]["records"]

    # --- Crime Statistics ---

    async def get_crime_stats(
        self, year: int | None = None
    ) -> list[CrimeStats]:
        """Get crime stats aggregated by borough for a given year.

        Uses SQL aggregation on the CKAN DataStore to avoid
        downloading the entire 340K+ record dataset.
        """
        if year is None:
            year = date.today().year - 1  # most recent complete year

        sql = f"""
            SELECT "PDQ", "CATEGORIE", COUNT(*) as cnt
            FROM "{RESOURCE_IDS['crime']}"
            WHERE "DATE" >= '{year}-01-01' AND "DATE" < '{year + 1}-01-01'
            GROUP BY "PDQ", "CATEGORIE"
        """

        records = await self._datastore_sql(sql)

        # Aggregate by borough
        borough_data: dict[str, CrimeStats] = {}
        for rec in records:
            pdq = str(rec.get("PDQ", "")).strip()
            borough = PDQ_TO_BOROUGH.get(pdq)
            if not borough or borough == "Métro (STM)":
                continue

            category = rec.get("CATEGORIE", "")
            count = int(rec.get("cnt", 0))

            if borough not in borough_data:
                borough_data[borough] = CrimeStats(borough=borough, year=year)

            stats = borough_data[borough]
            stats.total_crimes += count
            if category in VIOLENT_CRIMES:
                stats.violent_crimes += count
            elif category in PROPERTY_CRIMES:
                stats.property_crimes += count

        return sorted(borough_data.values(), key=lambda s: s.borough)

    async def get_crime_stats_two_years(
        self, year: int | None = None
    ) -> tuple[list[CrimeStats], list[CrimeStats]]:
        """Get crime stats for current and previous year for trend analysis."""
        if year is None:
            year = date.today().year - 1
        current = await self.get_crime_stats(year)
        previous = await self.get_crime_stats(year - 1)
        return current, previous

    # --- Building Permits ---

    async def get_permit_stats(
        self, min_year: int | None = None
    ) -> list[PermitStats]:
        """Get building permit statistics aggregated by borough and year.

        Uses the pre-aggregated statistics resource (much smaller than
        the full 547K+ permits dataset).
        """
        if min_year is None:
            min_year = date.today().year - 3

        sql = f"""
            SELECT "annee", "arrondissement", "code_type_base_demande",
                   "nombre_permis_emis", "cout_permis_emis", "cout_travaux_estimes"
            FROM "{RESOURCE_IDS['permits_stats']}"
            WHERE "annee" >= {min_year}
            ORDER BY "annee", "arrondissement"
        """

        records = await self._datastore_sql(sql)

        # Aggregate by borough + year
        key_map: dict[tuple[str, int], PermitStats] = {}
        for rec in records:
            borough = str(rec.get("arrondissement", "")).strip()
            if not borough:
                continue
            year = int(rec.get("annee", 0))
            if not year:
                continue

            permit_type = str(rec.get("code_type_base_demande", "")).strip()
            count = int(float(rec.get("nombre_permis_emis", 0) or 0))
            cost = float(rec.get("cout_permis_emis", 0) or 0)
            work_cost = float(rec.get("cout_travaux_estimes", 0) or 0)

            key = (borough, year)
            if key not in key_map:
                key_map[key] = PermitStats(borough=borough, year=year)

            stats = key_map[key]
            stats.total_permits += count
            stats.total_cost += cost
            stats.estimated_work_cost += work_cost

            if permit_type == "CO":
                stats.construction_permits += count
            elif permit_type == "TR":
                stats.transform_permits += count
            elif permit_type == "DE":
                stats.demolition_permits += count

        return sorted(key_map.values(), key=lambda s: (s.borough, s.year))

    # --- Tax Rates ---

    async def get_tax_rates(
        self, year: int | None = None
    ) -> list[TaxRate]:
        """Get residential property tax rates by borough.

        Returns the general residential tax rate (taxe fonciere)
        for each borough in the given year.
        """
        if year is None:
            year = date.today().year

        sql = f"""
            SELECT "Annee", "Arrondissement", "Categorie", "Taux",
                   "Categorie d'immeubles"
            FROM "{RESOURCE_IDS['tax_rates']}"
            WHERE "Annee" = {year}
            ORDER BY "Arrondissement"
        """

        records = await self._datastore_sql(sql)

        # Sum up all rates per borough for residential properties
        borough_rates: dict[str, dict] = {}
        for rec in records:
            borough = str(rec.get("Arrondissement", "")).strip()
            if not borough:
                continue

            prop_category = str(rec.get("Categorie d'immeubles", "")).strip().lower()
            rate = float(rec.get("Taux", 0) or 0)

            # Only include residential rates (not commercial/industrial)
            if "non residentiel" in prop_category or "non-residentiel" in prop_category:
                continue
            if "industriel" in prop_category or "terrain vague" in prop_category:
                continue

            if borough not in borough_rates:
                borough_rates[borough] = {
                    "residential_rate": 0,
                    "total_rate": 0,
                }

            # The general property tax is the main "residential_rate"
            category = str(rec.get("Categorie", "")).strip().lower()
            if "fonciere generale" in category or "foncière générale" in category:
                borough_rates[borough]["residential_rate"] = rate

            borough_rates[borough]["total_rate"] += rate

        results = []
        for borough, data in sorted(borough_rates.items()):
            results.append(TaxRate(
                borough=borough,
                year=year,
                residential_rate=round(data["residential_rate"], 4),
                total_tax_rate=round(data["total_rate"], 4),
            ))
        return results

    # --- Combined Neighbourhood Analysis ---

    async def get_neighbourhood_stats(
        self, borough: str | None = None
    ) -> list[NeighbourhoodStats]:
        """Get combined stats for all boroughs or a specific one.

        Fetches crime (2 years), permits (3 years), and tax rates,
        then computes safety scores and gentrification signals.
        """
        current_year = date.today().year - 1  # most recent complete year

        crime_current, crime_previous = await self.get_crime_stats_two_years(current_year)
        permits = await self.get_permit_stats(current_year - 2)
        taxes = await self.get_tax_rates()

        # Index by borough
        crime_cur_map = {s.borough: s for s in crime_current}
        crime_prev_map = {s.borough: s for s in crime_previous}
        permits_map: dict[str, list[PermitStats]] = {}
        for p in permits:
            permits_map.setdefault(p.borough, []).append(p)
        tax_map = {t.borough: t for t in taxes}

        # Compute YoY crime change
        for borough_name, stats in crime_cur_map.items():
            prev = crime_prev_map.get(borough_name)
            if prev and prev.total_crimes > 0:
                stats.year_over_year_change_pct = round(
                    ((stats.total_crimes - prev.total_crimes) / prev.total_crimes) * 100, 1
                )

        # Build combined stats
        all_boroughs = set(crime_cur_map.keys()) | set(tax_map.keys())
        if borough:
            canonical = normalize_borough(borough)
            if canonical:
                all_boroughs = {canonical} & all_boroughs
                if not all_boroughs:
                    # Try matching directly
                    for b in set(crime_cur_map.keys()) | set(tax_map.keys()):
                        if borough.lower() in b.lower() or b.lower() in borough.lower():
                            all_boroughs = {b}
                            break

        results = []
        # City-wide crime total for relative scoring
        total_city_crimes = sum(s.total_crimes for s in crime_current)
        num_boroughs = len(crime_current) or 1
        avg_crimes = total_city_crimes / num_boroughs

        for b in sorted(all_boroughs):
            crime = crime_cur_map.get(b)
            crime_prev = crime_prev_map.get(b)

            # Get most recent year's permits for this borough
            borough_permits = permits_map.get(b, [])
            # Try fuzzy match on borough name for permits
            if not borough_permits:
                for pk, pv in permits_map.items():
                    if b.lower() in pk.lower() or pk.lower() in b.lower():
                        borough_permits = pv
                        break
            latest_permits = max(borough_permits, key=lambda p: p.year) if borough_permits else None

            tax = tax_map.get(b)
            # Try fuzzy match on tax borough
            if not tax:
                for tk, tv in tax_map.items():
                    if b.lower() in tk.lower() or tk.lower() in b.lower():
                        tax = tv
                        break

            # Safety score: 10 = safest, 0 = most dangerous
            safety = None
            if crime and avg_crimes > 0:
                ratio = crime.total_crimes / avg_crimes
                # Score: if ratio < 0.5 → ~9, if ratio ~1 → ~5, if ratio > 2 → ~1
                safety = round(max(0, min(10, 10 - (ratio * 5))), 1)
                # Boost if crime is declining
                if crime.year_over_year_change_pct is not None and crime.year_over_year_change_pct < -5:
                    safety = min(10, safety + 0.5)

            # Gentrification signal from permit activity
            gentrify = "none"
            if borough_permits and len(borough_permits) >= 2:
                sorted_permits = sorted(borough_permits, key=lambda p: p.year)
                latest = sorted_permits[-1]
                earliest = sorted_permits[0]
                if earliest.transform_permits > 0:
                    transform_growth = (
                        (latest.transform_permits - earliest.transform_permits)
                        / earliest.transform_permits
                    )
                    if transform_growth > 0.3:
                        gentrify = "early"
                    if transform_growth > 0.6:
                        gentrify = "mid"
                    if transform_growth > 1.0 and latest.total_cost > 50_000_000:
                        gentrify = "mature"

            results.append(NeighbourhoodStats(
                borough=b,
                crime=crime,
                crime_previous=crime_prev,
                permits=latest_permits,
                tax=tax,
                safety_score=safety,
                gentrification_signal=gentrify,
            ))

        return results
