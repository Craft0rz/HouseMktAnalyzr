"""AI-based property condition scoring using Google Gemini.

Uses Gemini 2.5 Flash to analyze listing photos and assess property condition
on a 1-10 scale across multiple categories. No credit card required.

Rate limits (free tier):
    - 10 requests per minute (RPM)
    - 250 requests per day (RPD)

Env var: GEMINI_API_KEY (from Google AI Studio)
"""

import logging
import os
from dataclasses import dataclass
from typing import Optional

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

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
    """Pydantic schema for Gemini structured JSON output."""

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
            model="gemini-2.5-flash",
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
