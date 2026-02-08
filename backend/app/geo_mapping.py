"""Geographic name resolution for location scoring.

Maps Centris listing fields (city, postal_code) to the correct keys
used in each data source:
- neighbourhood_stats: Montreal borough names
- rent_data: CMHC zone names
- demographics: StatCan municipality names
"""

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

# City name → best CMHC rent zone for CMA-level data.
# CMHC zones are specific sub-areas like "Zone 5 / Le Plateau-Mont-Royal".
# Since zone names are dynamic and we can't reliably match them, we fall back
# to the CMA-total row which is always present.
CITY_TO_RENT_ZONE_FALLBACK = "Montreal CMA Total"


def resolve_borough(city: str, postal_code: str | None = None) -> str | None:
    """Resolve a listing's city + postal_code to a Montreal borough name.

    Returns the borough name (matching neighbourhood_stats.borough) or None
    if the listing is outside Montreal island.
    """
    # Try postal code FSA first (most accurate)
    if postal_code:
        fsa = postal_code.strip().upper()[:3]
        borough = FSA_TO_BOROUGH.get(fsa)
        if borough:
            return borough

    # If city is Montreal-ish, we can't determine borough without postal code
    # Return None so the caller can try a city-wide average
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

    # Always include CMA Total as fallback
    candidates.append(CITY_TO_RENT_ZONE_FALLBACK)

    return candidates


def resolve_demographics_key(city: str) -> str:
    """Normalize city name for demographics table lookup.

    The demographics table uses StatCan municipality names. Most work
    with the existing partial-match query, but we can help by normalizing
    common variations.
    """
    normalized = city.strip().lower()

    # Common Centris city name → demographics key normalization
    aliases = {
        "montréal": "montreal",
        "montreal": "montreal",
        "mtl": "montreal",
        "laval": "laval",
        "longueuil": "longueuil",
        "brossard": "brossard",
        "saint-hubert": "longueuil",
        "greenfield park": "longueuil",
        "le vieux-longueuil": "longueuil",
    }

    return aliases.get(normalized, normalized)
