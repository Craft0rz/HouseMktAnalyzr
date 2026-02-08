"""Data validation and quality scoring for scraped listings.

Three-layer pipeline that runs after detail-page enrichment:
  1. apply_detail_corrections  — fix known inconsistencies (detail page wins)
  2. run_sanity_checks         — flag suspicious cross-field values
  3. compute_quality_score     — completeness score 0-100
"""

from datetime import datetime, timezone

# Expected unit counts by property type
EXPECTED_UNITS = {
    "DUPLEX": 2,
    "TRIPLEX": 3,
    "QUADPLEX": 4,
}


def apply_detail_corrections(data: dict) -> tuple[dict, list[dict]]:
    """Layer 1: Fix known data inconsistencies.

    Returns (corrected_data, list_of_corrections).
    """
    corrections: list[dict] = []

    # Fix units vs property_type mismatch
    ptype = data.get("property_type", "")
    expected = EXPECTED_UNITS.get(ptype)
    current_units = data.get("units", 1)
    if expected and current_units != expected:
        corrections.append({
            "field": "units",
            "old": current_units,
            "new": expected,
            "reason": f"{ptype} must have {expected} units",
        })
        data["units"] = expected

    # MULTIPLEX with units=1 is always wrong — but we can't guess the count,
    # so just flag it (handled by sanity checks)

    return data, corrections


def run_sanity_checks(data: dict) -> list[dict]:
    """Layer 2: Flag suspicious values without changing them."""
    flags: list[dict] = []
    units = data.get("units") or 1
    price = data.get("price") or 0
    gross_revenue = data.get("gross_revenue")
    sqft = data.get("sqft")
    bedrooms = data.get("bedrooms", 0)
    assessment = data.get("municipal_assessment")

    # Revenue per unit checks
    if gross_revenue and units:
        rev_per_unit = gross_revenue / units
        if rev_per_unit < 5000:
            flags.append({
                "rule": "revenue_per_unit_low",
                "value": round(rev_per_unit),
                "threshold": 5000,
                "severity": "warning",
            })
        elif rev_per_unit > 30000:
            flags.append({
                "rule": "revenue_per_unit_high",
                "value": round(rev_per_unit),
                "threshold": 30000,
                "severity": "warning",
            })

    # Price per unit checks
    if price and units:
        ppu = price / units
        if ppu < 50000:
            flags.append({
                "rule": "price_per_unit_low",
                "value": round(ppu),
                "threshold": 50000,
                "severity": "warning",
            })
        elif ppu > 600000:
            flags.append({
                "rule": "price_per_unit_high",
                "value": round(ppu),
                "threshold": 600000,
                "severity": "info",
            })

    # Implied cap rate check
    if gross_revenue and price:
        # Rough NOI estimate: 65% of gross (35% expense ratio)
        implied_cap = (gross_revenue * 0.65) / price * 100
        if implied_cap > 15:
            flags.append({
                "rule": "cap_rate_extreme",
                "value": round(implied_cap, 1),
                "threshold": 15,
                "severity": "warning",
            })

    # Sqft per unit checks
    if sqft and units:
        sqft_per_unit = sqft / units
        if sqft_per_unit < 300:
            flags.append({
                "rule": "sqft_per_unit_low",
                "value": round(sqft_per_unit),
                "threshold": 300,
                "severity": "warning",
            })
        elif sqft_per_unit > 3000:
            flags.append({
                "rule": "sqft_per_unit_high",
                "value": round(sqft_per_unit),
                "threshold": 3000,
                "severity": "warning",
            })

    # Bedrooms per unit check
    if bedrooms and units:
        bed_per_unit = bedrooms / units
        if bed_per_unit > 5:
            flags.append({
                "rule": "bedrooms_per_unit_high",
                "value": round(bed_per_unit, 1),
                "threshold": 5,
                "severity": "warning",
            })

    # Zero bedrooms on multi-unit
    if bedrooms == 0 and units > 1:
        flags.append({
            "rule": "zero_bedrooms_multiunit",
            "value": 0,
            "threshold": 1,
            "severity": "warning",
        })

    # Assessment vs price sanity
    if assessment and price:
        ratio = assessment / price
        if ratio > 2.0:
            flags.append({
                "rule": "assessment_above_price",
                "value": round(ratio, 2),
                "threshold": 2.0,
                "severity": "info",
            })
        elif ratio < 0.2:
            flags.append({
                "rule": "assessment_below_price",
                "value": round(ratio, 2),
                "threshold": 0.2,
                "severity": "info",
            })

    return flags


# Completeness weights (field → points)
_QUALITY_WEIGHTS: dict[str, int] = {
    "gross_revenue": 20,
    "postal_code": 10,
    "annual_taxes": 10,
    "sqft": 10,
    "photo_urls": 10,
    "condition_score": 10,
    "municipal_assessment": 5,
    "year_built": 5,
    "lot_sqft": 5,
    "walk_score": 5,
}
_UNITS_CORRECT_PTS = 5
_NO_FLAGS_PTS = 5


def compute_quality_score(data: dict, flags: list[dict]) -> int:
    """Layer 3: Compute data completeness score 0-100."""
    score = 0

    for field, pts in _QUALITY_WEIGHTS.items():
        val = data.get(field)
        if field == "photo_urls":
            if val and len(val) > 0:
                score += pts
        elif val is not None:
            score += pts

    # Correct unit count for known plex types
    ptype = data.get("property_type", "")
    expected = EXPECTED_UNITS.get(ptype)
    if expected:
        if data.get("units") == expected:
            score += _UNITS_CORRECT_PTS
    else:
        # Non-plex types (HOUSE, MULTIPLEX) — give points if units > 0
        if data.get("units", 0) > 0:
            score += _UNITS_CORRECT_PTS

    # Bonus for no sanity flags
    if not flags:
        score += _NO_FLAGS_PTS

    return min(score, 100)


def validate_listing(data: dict) -> dict:
    """Run full validation pipeline on a listing's data dict.

    Adds/updates data["_quality"] with score, flags, corrections, and timestamp.
    Returns the modified data dict.
    """
    data, corrections = apply_detail_corrections(data)
    flags = run_sanity_checks(data)
    score = compute_quality_score(data, flags)

    data["_quality"] = {
        "score": score,
        "flags": flags,
        "corrections": corrections,
        "validated_at": datetime.now(timezone.utc).isoformat(),
    }
    return data
