"""Geographic name resolution for location scoring.

Maps Centris listing fields (city, postal_code) to the correct keys
used in each data source:
- neighbourhood_stats: Montreal borough names
- rent_data: CMHC zone names
- demographics: StatCan municipality names
"""

# French accent → ASCII translation table
_ACCENT_TABLE = str.maketrans({
    "é": "e", "è": "e", "ê": "e", "ë": "e",
    "à": "a", "â": "a", "ä": "a",
    "ô": "o",
    "ù": "u", "û": "u", "ü": "u",
    "ç": "c",
    "î": "i", "ï": "i",
    "É": "E", "È": "E", "Ê": "E", "Ë": "E",
    "À": "A", "Â": "A", "Ä": "A",
    "Ô": "O",
    "Ù": "U", "Û": "U", "Ü": "U",
    "Ç": "C",
    "Î": "I", "Ï": "I",
})


def _strip_accents(text: str) -> str:
    """Remove common French accents for fuzzy matching."""
    return text.translate(_ACCENT_TABLE)


# Merged municipalities / boroughs → parent city for CMHC zone matching.
# Used when the Centris city name won't appear in any CMHC zone name.
CITY_TO_RENT_ZONE_HINT: dict[str, str] = {
    # Montreal CMA
    "saint-hubert": "Longueuil",
    "greenfield park": "Longueuil",
    "le vieux-longueuil": "Longueuil",
    "saint-lambert": "Longueuil",
    "la prairie": "La Prairie",
    "candiac": "Candiac",
    "saint-constant": "Saint-Constant",
    # Quebec CMA — match CMHC zone names from the Quebec snapshot
    "l'ancienne-lorette": "Val-Bélair-L'Ancienne-Lorette",
    "val-belair": "Val-Bélair-L'Ancienne-Lorette",
    "cap-rouge": "Saint-Augustin-Cap-Rouge",
    "saint-augustin-de-desmaures": "Saint-Augustin-Cap-Rouge",
    "sillery": "Sainte-Foy-Sillery",
    # Sherbrooke CMA — match CMHC zone names from the Sherbrooke snapshot
    "rock-forest": "Rock-Forest-St-Elie-Deauville",
}


# City/neighbourhood → neighbourhood_stats borough for non-Montreal CMAs.
# Allows resolve_borough() to match Sherbrooke/Quebec City listings to
# their arrondissement for neighbourhood stats lookup.
CITY_TO_NEIGHBOURHOOD: dict[str, str] = {
    # --- Sherbrooke arrondissements ---
    "fleurimont": "Fleurimont",
    "lennoxville": "Lennoxville",
    "rock forest": "Brompton-Rock Forest-St-Elie-Deauville",
    "rock-forest": "Brompton-Rock Forest-St-Elie-Deauville",
    "brompton": "Brompton-Rock Forest-St-Elie-Deauville",
    "deauville": "Brompton-Rock Forest-St-Elie-Deauville",
    "saint-elie-d'orford": "Brompton-Rock Forest-St-Elie-Deauville",
    "saint-elie": "Brompton-Rock Forest-St-Elie-Deauville",
    "sherbrooke": "Des Nations",  # downtown Sherbrooke = Des Nations
    # --- Quebec City arrondissements ---
    "beauport": "Beauport",
    "charlesbourg": "Charlesbourg",
    "sainte-foy": "Sainte-Foy-Sillery-Cap-Rouge",
    "sillery": "Sainte-Foy-Sillery-Cap-Rouge",
    "cap-rouge": "Sainte-Foy-Sillery-Cap-Rouge",
    "limoilou": "La Cité-Limoilou",
    "la cite-limoilou": "La Cité-Limoilou",
    "les rivieres": "Les Rivières",
    "les-rivieres": "Les Rivières",
    "la haute-saint-charles": "La Haute-Saint-Charles",
    "la-haute-saint-charles": "La Haute-Saint-Charles",
    "val-belair": "La Haute-Saint-Charles",
    "loretteville": "Les Rivières",
    "neufchatel": "Les Rivières",
    "saint-emile": "La Haute-Saint-Charles",
    "lac-saint-charles": "La Haute-Saint-Charles",
    # --- Longueuil agglomeration (city-wide stats) ---
    "longueuil": "Longueuil",
    "le vieux-longueuil": "Longueuil",
    "vieux-longueuil": "Longueuil",
    "saint-hubert": "Longueuil",
    "greenfield park": "Longueuil",
    "saint-lambert": "Longueuil",
    "brossard": "Longueuil",
    "boucherville": "Longueuil",
    # --- Laval (single municipality) ---
    "laval": "Laval",
    "chomedey": "Laval",
    "laval-des-rapides": "Laval",
    "pont-viau": "Laval",
    "vimont": "Laval",
    "auteuil": "Laval",
    "sainte-dorothee": "Laval",
    "fabreville": "Laval",
    "sainte-rose": "Laval",
    "duvernay": "Laval",
    "laval-ouest": "Laval",
    "ile-bizard": "Laval",
    # --- Gatineau (city-wide stats) ---
    "gatineau": "Gatineau",
    "hull": "Gatineau",
    "aylmer": "Gatineau",
    "buckingham": "Gatineau",
    "masson-angers": "Gatineau",
    # --- Laurentides ---
    "blainville": "Blainville",
    "saint-jerome": "Saint-Jérôme",
    "mirabel": "Mirabel",
    "sainte-therese": "Sainte-Thérèse",
    "boisbriand": "Boisbriand",
    "saint-eustache": "Saint-Eustache",
    # --- Lanaudière ---
    "terrebonne": "Terrebonne",
    "lachenaie": "Terrebonne",
    "la plaine": "Terrebonne",
    "repentigny": "Repentigny",
    "le gardeur": "Repentigny",
    "mascouche": "Mascouche",
    # --- Montérégie (South Shore, outside Longueuil agglomeration) ---
    "chateauguay": "Châteauguay",
    "saint-jean-sur-richelieu": "Saint-Jean-sur-Richelieu",
    "iberville": "Saint-Jean-sur-Richelieu",
    "saint-luc": "Saint-Jean-sur-Richelieu",
    "la prairie": "La Prairie",
    "chambly": "Chambly",
    "candiac": "Candiac",
    "saint-constant": "Saint-Constant",
    "beloeil": "Beloeil",
    "vaudreuil-dorion": "Vaudreuil-Dorion",
    "vaudreuil": "Vaudreuil-Dorion",
    "dorion": "Vaudreuil-Dorion",
    "saint-bruno-de-montarville": "Saint-Bruno-de-Montarville",
    "saint-bruno": "Saint-Bruno-de-Montarville",
    # --- Capitale-Nationale (outside Quebec City boroughs) ---
    "levis": "Lévis",
    "levy": "Lévis",
    "saint-augustin-de-desmaures": "Saint-Augustin-de-Desmaures",
    "saint-augustin": "Saint-Augustin-de-Desmaures",
    # --- Estrie (outside Sherbrooke arrondissements) ---
    "magog": "Magog",
}


# Montreal FSA (first 3 chars of postal code) → borough mapping.
# Source: Canada Post FSA boundaries overlaid with Montreal borough boundaries.
FSA_TO_BOROUGH: dict[str, str] = {
    # Ville-Marie / Downtown
    "H2X": "Ville-Marie",
    "H2Y": "Ville-Marie",
    "H2Z": "Ville-Marie",
    "H3A": "Ville-Marie",
    "H3B": "Ville-Marie",
    "H3C": "Ville-Marie",
    "H3G": "Ville-Marie",
    "H3H": "Ville-Marie",
    # Le Plateau-Mont-Royal
    "H2J": "Le Plateau-Mont-Royal",
    "H2T": "Le Plateau-Mont-Royal",
    "H2W": "Le Plateau-Mont-Royal",
    "H2H": "Le Plateau-Mont-Royal",
    # Rosemont-La Petite-Patrie
    "H1X": "Rosemont-La Petite-Patrie",
    "H1Y": "Rosemont-La Petite-Patrie",
    "H2S": "Rosemont-La Petite-Patrie",
    "H2G": "Rosemont-La Petite-Patrie",
    # Villeray-Saint-Michel-Parc-Extension
    "H2P": "Villeray-Saint-Michel-Parc-Extension",
    "H2R": "Villeray-Saint-Michel-Parc-Extension",
    "H1Z": "Villeray-Saint-Michel-Parc-Extension",
    "H2E": "Villeray-Saint-Michel-Parc-Extension",
    # Mercier-Hochelaga-Maisonneuve
    "H1L": "Mercier-Hochelaga-Maisonneuve",
    "H1N": "Mercier-Hochelaga-Maisonneuve",
    "H1V": "Mercier-Hochelaga-Maisonneuve",
    "H1W": "Mercier-Hochelaga-Maisonneuve",
    "H1K": "Mercier-Hochelaga-Maisonneuve",
    # Ahuntsic-Cartierville
    "H2M": "Ahuntsic-Cartierville",
    "H2N": "Ahuntsic-Cartierville",
    "H2B": "Ahuntsic-Cartierville",
    "H2C": "Ahuntsic-Cartierville",
    "H3L": "Ahuntsic-Cartierville",
    "H3M": "Ahuntsic-Cartierville",
    # Côte-des-Neiges-Notre-Dame-de-Grâce
    "H3S": "Côte-des-Neiges-Notre-Dame-de-Grâce",
    "H3T": "Côte-des-Neiges-Notre-Dame-de-Grâce",
    "H3V": "Côte-des-Neiges-Notre-Dame-de-Grâce",
    "H3W": "Côte-des-Neiges-Notre-Dame-de-Grâce",
    "H4A": "Côte-des-Neiges-Notre-Dame-de-Grâce",
    "H4B": "Côte-des-Neiges-Notre-Dame-de-Grâce",
    "H4V": "Côte-des-Neiges-Notre-Dame-de-Grâce",
    # Outremont
    "H2V": "Outremont",
    # Le Sud-Ouest
    "H3J": "Le Sud-Ouest",
    "H3K": "Le Sud-Ouest",
    "H4C": "Le Sud-Ouest",
    "H4E": "Le Sud-Ouest",
    # Verdun
    "H4G": "Verdun",
    "H4H": "Verdun",
    "H3E": "Verdun",
    # LaSalle
    "H8N": "LaSalle",
    "H8P": "LaSalle",
    "H8R": "LaSalle",
    # Lachine
    "H8S": "Lachine",
    "H8T": "Lachine",
    # Saint-Laurent
    "H4L": "Saint-Laurent",
    "H4M": "Saint-Laurent",
    "H4N": "Saint-Laurent",
    "H4P": "Saint-Laurent",
    "H4R": "Saint-Laurent",
    "H4S": "Saint-Laurent",
    "H4T": "Saint-Laurent",
    # Saint-Léonard
    "H1P": "Saint-Léonard",
    "H1R": "Saint-Léonard",
    "H1S": "Saint-Léonard",
    "H1T": "Saint-Léonard",
    # Anjou
    "H1J": "Anjou",
    "H1K": "Anjou",
    # Montréal-Nord
    "H1G": "Montréal-Nord",
    "H1H": "Montréal-Nord",
    # Rivière-des-Prairies-Pointe-aux-Trembles
    "H1A": "Rivière-des-Prairies-Pointe-aux-Trembles",
    "H1B": "Rivière-des-Prairies-Pointe-aux-Trembles",
    "H1C": "Rivière-des-Prairies-Pointe-aux-Trembles",
    "H1E": "Rivière-des-Prairies-Pointe-aux-Trembles",
    # Pierrefonds-Roxboro
    "H8Y": "Pierrefonds-Roxboro",
    "H8Z": "Pierrefonds-Roxboro",
    "H9A": "Pierrefonds-Roxboro",
    "H9H": "Pierrefonds-Roxboro",
    "H9J": "Pierrefonds-Roxboro",
    "H9K": "Pierrefonds-Roxboro",
}

# City name → CMA key. Used to pick the correct CMHC CMA Total fallback.
# Default: "montreal" for any city not listed.
CITY_TO_CMA: dict[str, str] = {
    # --- Montreal CMA ---
    "montreal": "montreal", "laval": "montreal", "longueuil": "montreal",
    "brossard": "montreal", "terrebonne": "montreal", "repentigny": "montreal",
    "blainville": "montreal", "saint-jerome": "montreal", "mirabel": "montreal",
    "mascouche": "montreal", "saint-eustache": "montreal",
    "chateauguay": "montreal", "vaudreuil-dorion": "montreal",
    "saint-constant": "montreal", "la-prairie": "montreal",
    "chambly": "montreal", "boucherville": "montreal",
    "saint-bruno-de-montarville": "montreal",
    "saint-lambert": "montreal", "candiac": "montreal",
    "beloeil": "montreal", "saint-jean-sur-richelieu": "montreal",
    "sainte-therese": "montreal", "boisbriand": "montreal",
    "dollard-des-ormeaux": "montreal", "pointe-claire": "montreal",
    "saint-hubert": "montreal", "greenfield-park": "montreal",
    # --- Quebec CMA ---
    "quebec": "quebec", "levis": "quebec",
    "l'ancienne-lorette": "quebec", "l-ancienne-lorette": "quebec",
    "saint-augustin-de-desmaures": "quebec",
    "beauport": "quebec", "charlesbourg": "quebec",
    "sainte-foy": "quebec", "sillery": "quebec",
    "shannon": "quebec", "boischatel": "quebec",
    "stoneham-et-tewkesbury": "quebec",
    "val-belair": "quebec", "cap-rouge": "quebec",
    "saint-henri": "quebec",
    # --- Sherbrooke CMA ---
    "sherbrooke": "sherbrooke", "magog": "sherbrooke",
    "orford": "sherbrooke", "ascot-corner": "sherbrooke",
    "compton": "sherbrooke", "waterville": "sherbrooke",
    "north-hatley": "sherbrooke", "fleurimont": "sherbrooke",
    "lennoxville": "sherbrooke", "brompton": "sherbrooke",
    "rock-forest": "sherbrooke", "saint-denis-de-brompton": "sherbrooke",
}


def resolve_cma(city: str) -> str:
    """Determine which CMA a city belongs to. Defaults to 'montreal'."""
    normalized = _strip_accents(city.strip().lower())
    return CITY_TO_CMA.get(normalized, "montreal")


def resolve_borough(city: str, postal_code: str | None = None) -> str | None:
    """Resolve a listing's city + postal_code to a neighbourhood_stats borough.

    Checks Montreal FSA mapping first, then falls back to city/neighbourhood
    name matching for Sherbrooke and Quebec City arrondissements.

    Returns the borough/arrondissement name or None if unresolvable.
    """
    # Try postal code FSA first (most accurate for Montreal)
    if postal_code:
        fsa = postal_code.strip().upper()[:3]
        borough = FSA_TO_BOROUGH.get(fsa)
        if borough:
            return borough

    # Try city name → neighbourhood mapping (Sherbrooke, Quebec City)
    if city:
        normalized = _strip_accents(city.strip().lower())
        neighbourhood = CITY_TO_NEIGHBOURHOOD.get(normalized)
        if neighbourhood:
            return neighbourhood

        # Handle "City (District)" format common in Centris listings
        if "(" in normalized and ")" in normalized:
            district = normalized.split("(")[1].split(")")[0].strip()
            neighbourhood = CITY_TO_NEIGHBOURHOOD.get(district)
            if neighbourhood:
                return neighbourhood

    return None


def resolve_rent_zone(city: str, postal_code: str | None = None) -> list[str]:
    """Resolve a listing to a list of CMHC zone name candidates (best first).

    Returns a list of zone names to try in order. The DB query should try
    each until one matches. Always ends with CMA Total as fallback.
    """
    candidates = []

    # Try borough name if we can resolve it (CMHC zones often contain borough names)
    borough = resolve_borough(city, postal_code)
    if borough:
        candidates.append(borough)

    # Try city name — CMHC zones often contain it (e.g. "Zone 1 / Laval")
    normalized = city.strip()
    if normalized and normalized not in candidates:
        candidates.append(normalized)

    # Try hint for merged municipalities where city name ≠ CMHC zone name
    hint = CITY_TO_RENT_ZONE_HINT.get(_strip_accents(city.strip().lower()))
    if hint and hint not in candidates:
        candidates.append(hint)

    # CMA-specific fallback (e.g. "Montreal CMA Total", "Quebec CMA Total")
    from .constants import CMA_CONFIG
    cma = resolve_cma(city)
    fallback = CMA_CONFIG.get(cma, {}).get("fallback_zone", "Montreal CMA Total")
    candidates.append(fallback)

    return candidates


def resolve_demographics_key(city: str) -> str:
    """Normalize city name for demographics table lookup.

    The demographics table uses StatCan municipality names. Most work
    with the existing partial-match query, but we can help by normalizing
    common variations and stripping French accents.
    """
    normalized = city.strip().lower()
    ascii_normalized = _strip_accents(normalized)

    # Common Centris city name → demographics key normalization
    aliases = {
        # Montreal
        "montréal": "montreal",
        "montreal": "montreal",
        "mtl": "montreal",
        # Laval
        "laval": "laval",
        # South Shore — merged municipalities
        "longueuil": "longueuil",
        "brossard": "brossard",
        "saint-hubert": "longueuil",
        "greenfield park": "longueuil",
        "le vieux-longueuil": "longueuil",
        "saint-lambert": "saint-lambert",
        "saint-bruno-de-montarville": "saint-bruno-de-montarville",
        "chambly": "chambly",
        "la prairie": "la-prairie",
        "candiac": "candiac",
        "chateauguay": "chateauguay",
        "saint-constant": "saint-constant",
        # North Shore
        "terrebonne": "terrebonne",
        "mascouche": "mascouche",
        "repentigny": "repentigny",
        # Laurentides
        "saint-jerome": "saint-jerome",
        "blainville": "blainville",
        "mirabel": "mirabel",
        "sainte-therese": "sainte-therese",
        "boisbriand": "boisbriand",
        "saint-eustache": "saint-eustache",
        # Other Montreal CMA
        "vaudreuil-dorion": "vaudreuil-dorion",
        "saint-jean-sur-richelieu": "saint-jean-sur-richelieu",
        "beloeil": "beloeil",
        # Quebec CMA
        "québec": "quebec",
        "quebec": "quebec",
        "lévis": "levis",
        "levis": "levis",
        "l'ancienne-lorette": "l-ancienne-lorette",
        "saint-augustin-de-desmaures": "saint-augustin-de-desmaures",
        "beauport": "beauport",
        "charlesbourg": "charlesbourg",
        "sainte-foy": "sainte-foy",
        "sillery": "sainte-foy",
        "shannon": "shannon",
        "boischatel": "boischatel",
        "val-bélair": "quebec",
        "cap-rouge": "quebec",
        # Sherbrooke CMA
        "sherbrooke": "sherbrooke",
        "magog": "magog",
        "orford": "orford",
        "ascot corner": "ascot-corner",
        "compton": "compton",
        "waterville": "waterville",
        "north hatley": "north-hatley",
        "fleurimont": "fleurimont",
        "lennoxville": "lennoxville",
        "brompton": "sherbrooke",
        "rock forest": "sherbrooke",
        "rock-forest": "sherbrooke",
        "saint-denis-de-brompton": "sherbrooke",
    }

    # Try exact match first, then accent-stripped match
    return aliases.get(normalized) or aliases.get(ascii_normalized, normalized)
