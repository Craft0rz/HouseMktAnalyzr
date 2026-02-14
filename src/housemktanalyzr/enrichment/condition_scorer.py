"""AI-based property condition scoring using Google Gemini.

Uses Gemini Flash Lite to analyze listing photos and assess property condition
on a 1-10 scale across multiple categories. No credit card required.

Rate limits (free tier, gemini-2.5-flash-lite):
    - 15 requests per minute (RPM)
    - 1,000 requests per day (RPD)

BATCH OPTIMIZATION: Can score 8 properties per API call by combining photos.
At 1,000 req/day * 8 props/req = 8,000 properties/day.

Env vars:
    GEMINI_API_KEY (from Google AI Studio)
    GEMINI_MODEL (default: gemini-2.5-flash-lite)
"""

import logging
import os
from dataclasses import dataclass
from typing import Optional

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Model selection: flash-lite has 1,000 RPD free tier vs flash's 20 RPD
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")

# Lazy-initialized Gemini client
_client = None


def _get_client():
    """Lazy-initialize the Gemini client."""
    global _client
    if _client is not None:
        return _client

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set")

    from google import genai

    _client = genai.Client(api_key=api_key)
    return _client


class ConditionAssessment(BaseModel):
    """Pydantic schema for Gemini structured JSON output (single property)."""

    overall: float = Field(ge=1, le=10, description="Overall condition 1-10")
    kitchen: float | None = Field(default=None, description="Kitchen condition 1-10, null if not visible")
    bathroom: float | None = Field(default=None, description="Bathroom condition 1-10, null if not visible")
    floors: float | None = Field(default=None, description="Floor/interior condition 1-10, null if not visible")
    exterior: float | None = Field(default=None, description="Exterior/facade condition 1-10, null if not visible")
    renovation_needed: bool = Field(
        description="Whether significant renovation is needed (>$20k)"
    )
    notes: str = Field(
        description="Brief summary of condition observations (2-3 sentences)"
    )


class BatchConditionAssessment(BaseModel):
    """Pydantic schema for batch scoring multiple properties."""

    properties: list[ConditionAssessment] = Field(
        description="List of condition assessments, one per property in order"
    )


@dataclass
class ConditionScoreResult:
    """Result of AI condition scoring for a property."""

    overall_score: float
    kitchen_score: float | None
    bathroom_score: float | None
    floors_score: float | None
    exterior_score: float | None
    renovation_needed: bool
    notes: str


CONDITION_PROMPT = """\
You are a real estate property condition assessor. Analyze these listing photos \
and rate the property's physical condition.

Property context: {property_type} in {city}, built {year_built}.

Rate each category from 1 (terrible/needs full renovation) to 10 (pristine/newly renovated):
- Overall: General impression of the entire property (always score this)
- Kitchen: Cabinets, countertops, appliances, flooring
- Bathroom: Fixtures, tiles, vanity, overall cleanliness
- Floors: Condition of flooring throughout (hardwood, tile, carpet)
- Exterior: Facade, roof visible condition, windows, entrance

IMPORTANT: Only score a category if you can actually see it in the photos. \
If a kitchen, bathroom, floor, or exterior is NOT visible in any photo, return null \
for that category. Do NOT guess or estimate unseen areas.

Also determine if significant renovation is needed (>$20,000 estimated), and \
provide 2-3 sentence notes about what you can actually observe.

Be calibrated: 5 = average/functional but dated. 7 = good condition with minor wear. \
9-10 = recently renovated/new."""


def _select_diverse_photos(photo_urls: list[str], max_photos: int) -> list[str]:
    """Select evenly-spaced photos from the full set for maximum room diversity.

    Centris listings typically order photos: exterior(s), kitchen, living room,
    bedrooms, bathrooms. Taking only the first N gives mostly exterior shots.
    Evenly sampling across the full set maximizes the chance of seeing different
    rooms (kitchen, bathroom, floors, exterior).

    Always includes the first photo (exterior) and then picks evenly-spaced
    photos from the remainder.
    """
    total = len(photo_urls)
    if total <= max_photos:
        return photo_urls

    # Always include the first photo (typically the main exterior shot)
    indices = [0]
    # Spread remaining picks evenly across the rest of the photos
    remaining = max_photos - 1
    # Sample from index 1..total-1
    step = (total - 1) / remaining
    for i in range(remaining):
        idx = int(1 + i * step)
        if idx not in indices:
            indices.append(idx)
        else:
            # Avoid duplicates by nudging forward
            indices.append(min(idx + 1, total - 1))

    return [photo_urls[i] for i in sorted(set(indices))]


async def score_property_condition(
    photo_urls: list[str],
    property_type: str = "property",
    city: str = "Montreal",
    year_built: int | None = None,
    max_photos: int = 8,
) -> Optional[ConditionScoreResult]:
    """Analyze property photos with Gemini and return condition scores.

    Args:
        photo_urls: List of photo URLs from the listing
        property_type: Type of property for context
        city: City name for context
        year_built: Year built for context, or None
        max_photos: Maximum photos to send (default 8)

    Returns:
        ConditionScoreResult or None if scoring fails
    """
    if not photo_urls:
        logger.debug("No photos available for condition scoring")
        return None

    try:
        client = _get_client()
    except RuntimeError as e:
        logger.warning(f"Gemini not configured: {e}")
        return None

    from google.genai import types

    selected_urls = _select_diverse_photos(photo_urls, max_photos)
    year_str = str(year_built) if year_built else "unknown year"

    prompt = CONDITION_PROMPT.format(
        property_type=property_type,
        city=city,
        year_built=year_str,
    )

    # Download images and build content parts
    parts = [types.Part.from_text(text=prompt)]
    async with httpx.AsyncClient(timeout=15.0) as http:
        for url in selected_urls:
            try:
                resp = await http.get(url)
                resp.raise_for_status()
                content_type = resp.headers.get("content-type", "image/jpeg")
                mime = content_type.split(";")[0].strip()
                if not mime.startswith("image/"):
                    mime = "image/jpeg"
                parts.append(types.Part.from_bytes(
                    data=resp.content,
                    mime_type=mime,
                ))
            except Exception as e:
                logger.debug(f"Skipping photo URL {url}: {e}")

    if len(parts) < 2:
        logger.warning("No valid photo parts could be created")
        return None

    try:
        response = await client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=[types.Content(role="user", parts=parts)],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ConditionAssessment,
                temperature=0.2,
            ),
        )

        assessment = ConditionAssessment.model_validate_json(response.text)

        return ConditionScoreResult(
            overall_score=assessment.overall,
            kitchen_score=assessment.kitchen,
            bathroom_score=assessment.bathroom,
            floors_score=assessment.floors,
            exterior_score=assessment.exterior,
            renovation_needed=assessment.renovation_needed,
            notes=assessment.notes,
        )

    except Exception as e:
        logger.error(f"Gemini condition scoring failed: {e}")
        return None


async def score_properties_batch(
    properties: list[dict],
    max_photos_per_property: int = 5,
    batch_size: int = 8,
) -> list[Optional[ConditionScoreResult]]:
    """Score multiple properties in a single API call for efficiency.

    Args:
        properties: List of property dicts with keys:
            - photo_urls: list[str]
            - property_type: str
            - city: str
            - year_built: int | None
        max_photos_per_property: Max photos to include per property (default 5)
        batch_size: Number of properties to score per API call (default 8)

    Returns:
        List of ConditionScoreResult or None for each property (maintains order)

    Example:
        properties = [
            {"photo_urls": [...], "property_type": "HOUSE", "city": "Montreal", "year_built": 1990},
            {"photo_urls": [...], "property_type": "DUPLEX", "city": "Laval", "year_built": 2005},
        ]
        results = await score_properties_batch(properties, batch_size=8)
    """
    if not properties or len(properties) > batch_size:
        logger.warning(f"Batch size {len(properties)} exceeds max {batch_size}")
        return [None] * len(properties)

    try:
        client = _get_client()
    except RuntimeError as e:
        logger.warning(f"Gemini not configured: {e}")
        return [None] * len(properties)

    from google.genai import types

    # Build prompt with property sections
    prompt_parts = [
        f"You are analyzing {len(properties)} different properties. "
        "For each property below, assess its condition independently.\n\n"
    ]

    property_metadata = []
    all_parts = []
    photo_count = 0

    async with httpx.AsyncClient(timeout=15.0) as http:
        for idx, prop in enumerate(properties):
            photo_urls = prop.get("photo_urls", [])
            if not photo_urls:
                logger.debug(f"Property {idx} has no photos, skipping")
                continue

            property_type = prop.get("property_type", "property")
            city = prop.get("city", "Montreal")
            year_built = prop.get("year_built")
            year_str = str(year_built) if year_built else "unknown year"

            # Select diverse photos for this property
            selected_urls = _select_diverse_photos(photo_urls, max_photos_per_property)

            # Add property header
            prompt_parts.append(
                f"PROPERTY {idx + 1}: {property_type} in {city}, built {year_str}\n"
                f"Photos for Property {idx + 1}:\n"
            )

            # Download and add photos
            prop_photo_count = 0
            for url in selected_urls:
                try:
                    resp = await http.get(url)
                    resp.raise_for_status()
                    content_type = resp.headers.get("content-type", "image/jpeg")
                    mime = content_type.split(";")[0].strip()
                    if not mime.startswith("image/"):
                        mime = "image/jpeg"

                    all_parts.append(
                        types.Part.from_bytes(
                            data=resp.content,
                            mime_type=mime,
                        )
                    )
                    prop_photo_count += 1
                    photo_count += 1
                except Exception as e:
                    logger.debug(f"Skipping photo for property {idx}: {e}")

            prompt_parts.append(f"({prop_photo_count} photos above)\n\n")
            property_metadata.append({"index": idx, "photo_count": prop_photo_count})

    if photo_count == 0:
        logger.warning("No valid photos could be loaded for any property")
        return [None] * len(properties)

    # Build final prompt
    full_prompt = "".join(prompt_parts) + f"""
Rate each property's condition from 1 (terrible/needs full renovation) to 10 (pristine/newly renovated):
- Overall: General impression (always score this)
- Kitchen: Cabinets, countertops, appliances (null if not visible)
- Bathroom: Fixtures, tiles, vanity (null if not visible)
- Floors: Flooring condition (null if not visible)
- Exterior: Facade, roof, windows (null if not visible)

IMPORTANT: Only score categories you can SEE in each property's photos. Return null if not visible.

Return a JSON array with {len(properties)} assessments in the SAME ORDER as the properties above.

Be calibrated: 5 = average/functional but dated, 7 = good with minor wear, 9-10 = recently renovated.
"""

    # Combine text prompt + images
    parts = [types.Part.from_text(text=full_prompt)] + all_parts

    try:
        response = await client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=[types.Content(role="user", parts=parts)],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=BatchConditionAssessment,
                temperature=0.2,
            ),
        )

        batch_result = BatchConditionAssessment.model_validate_json(response.text)

        # Convert to ConditionScoreResult objects
        results = []
        for assessment in batch_result.properties:
            results.append(
                ConditionScoreResult(
                    overall_score=assessment.overall,
                    kitchen_score=assessment.kitchen,
                    bathroom_score=assessment.bathroom,
                    floors_score=assessment.floors,
                    exterior_score=assessment.exterior,
                    renovation_needed=assessment.renovation_needed,
                    notes=assessment.notes,
                )
            )

        # Pad with None if we got fewer results than expected
        while len(results) < len(properties):
            results.append(None)

        logger.info(f"Batch scored {len(results)} properties with {photo_count} total photos")
        return results

    except Exception as e:
        logger.error(f"Batch condition scoring failed: {e}")
        return [None] * len(properties)
