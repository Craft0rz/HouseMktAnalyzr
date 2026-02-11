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

    # MULTIPLEX with units=1 is always wrong — try to extract from raw_data,
    # otherwise set minimum of 5 (definition of multiplex)
    if ptype == "MULTIPLEX" and current_units <= 1:
        raw = data.get("raw_data") or {}
        raw_units = raw.get("number_of_units") or raw.get("nombre_d'unités") or raw.get("nombre_de_logements")
        if raw_units:
            import re
            m = re.search(r"(\d+)", str(raw_units))
            if m:
                extracted = int(m.group(1))
                if extracted >= 5:
                    corrections.append({
                        "field": "units",
                        "old": current_units,
                        "new": extracted,
                        "reason": f"MULTIPLEX units extracted from raw_data: {extracted}",
                    })
                    data["units"] = extracted
                    current_units = extracted
        # If still wrong after raw_data check, set floor of 5
        if data.get("units", 1) <= 1:
            corrections.append({
                "field": "units",
                "old": current_units,
                "new": 5,
                "reason": "MULTIPLEX must have >=5 units, defaulting to 5",
            })
            data["units"] = 5

    # Validate inferred financial fields: if a field was inferred by the scraper,
    # cross-check it against sanity bounds
    raw_data = data.get("raw_data") or {}
    inferred = raw_data.get("finance_inferred_fields") or []
    units = data.get("units") or 1
    for field in inferred:
        val = data.get(field)
        if val is not None and units > 0:
            per_unit = val / units
            # Gross revenue per unit: $3k-$40k/yr is plausible for Quebec
            if field == "gross_revenue" and (per_unit < 3000 or per_unit > 40000):
                corrections.append({
                    "field": field,
                    "old": val,
                    "new": None,
                    "reason": f"Inferred {field} per unit ${per_unit:.0f} outside plausible range",
                })
                data[field] = None

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

    # Enriched but still missing sqft — flag for price-per-sqft gap
    raw_data = data.get("raw_data") or {}
    if not sqft and raw_data.get("enriched") or raw_data.get("detail_enriched_at"):
        flags.append({
            "rule": "sqft_missing_after_enrichment",
            "value": None,
            "threshold": None,
            "severity": "warning",
        })

    # Flag inferred financial fields so downstream consumers know
    inferred_fields = raw_data.get("finance_inferred_fields") or []
    if inferred_fields:
        flags.append({
            "rule": "financial_values_inferred",
            "value": inferred_fields,
            "threshold": None,
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

    units = data.get("units", 1) or 1

    for field, pts in _QUALITY_WEIGHTS.items():
        val = data.get(field)
        if field == "photo_urls":
            if val and len(val) > 0:
                score += pts
        elif field == "gross_revenue":
            if val is not None:
                score += pts
            elif units <= 1:
                # Single-family: rental revenue not expected, don't penalize
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

    # Extra penalty: sqft missing after enrichment blocks price-per-sqft analysis
    sqft_missing_flag = any(f.get("rule") == "sqft_missing_after_enrichment" for f in flags)
    if sqft_missing_flag:
        score = max(score - 5, 0)

    # Bonus for no warning-level sanity flags (info flags don't penalize)
    warning_flags = [f for f in flags if f.get("severity") == "warning"]
    if not warning_flags:
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
