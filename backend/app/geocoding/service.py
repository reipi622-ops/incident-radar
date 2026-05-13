"""
Geocoding Service — Incident Radar
====================================
Abstraction layer over geocoding providers.
MVP uses Nominatim (free, no API key needed).
Add new providers by subclassing GeocodingProvider.

Returns GeoResult with lat/lng and confidence.
Confidence is derived from result importance + address type.
Never stores a location with confidence below MIN_CONFIDENCE.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from loguru import logger
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

from app.core.config import settings


@dataclass
class GeoResult:
    latitude: float
    longitude: float
    confidence: float        # 0.0 – 1.0
    resolved_address: str    # human-readable address returned by provider
    query: str               # what we sent to the geocoder


class GeocodingProvider(ABC):
    @abstractmethod
    def geocode(self, query: str) -> Optional[GeoResult]:
        ...


# ── Nominatim provider ────────────────────────────────────────────────────────

# Address types that warrant high confidence
_HIGH_CONFIDENCE_TYPES = {"city", "town", "suburb", "neighbourhood", "road", "street"}
_MED_CONFIDENCE_TYPES  = {"county", "state_district", "state", "region"}


class NominatimProvider(GeocodingProvider):
    """
    Uses OpenStreetMap Nominatim.
    Free, no API key, but rate-limited to 1 req/sec — suitable for MVP.
    """

    def __init__(self):
        self._geolocator = Nominatim(
            user_agent=settings.NOMINATIM_USER_AGENT,
            timeout=5,
        )

    def geocode(self, query: str) -> Optional[GeoResult]:
        if not query or len(query.strip()) < 2:
            return None

        # Append ", Israel" if query looks like a Hebrew location without country
        enriched_query = query if "israel" in query.lower() else f"{query}, Israel"

        try:
            location = self._geolocator.geocode(enriched_query, language="he", addressdetails=True)
        except GeocoderTimedOut:
            logger.warning(f"Geocoder timed out for: {query!r}")
            return None
        except GeocoderServiceError as e:
            logger.error(f"Geocoder service error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected geocoder error: {e}")
            return None

        if not location:
            logger.debug(f"No geocode result for: {query!r}")
            return None

        confidence = _compute_confidence(location)

        return GeoResult(
            latitude=location.latitude,
            longitude=location.longitude,
            confidence=confidence,
            resolved_address=location.address,
            query=enriched_query,
        )


def _compute_confidence(location) -> float:
    """
    Derive a 0–1 confidence score from the Nominatim result.
    Uses `importance` (0–1) and `addresstype` as signals.
    """
    raw = getattr(location, "raw", {}) or {}
    importance = float(raw.get("importance", 0.5))
    address_type = raw.get("addresstype", raw.get("type", ""))

    if address_type in _HIGH_CONFIDENCE_TYPES:
        type_factor = 1.0
    elif address_type in _MED_CONFIDENCE_TYPES:
        type_factor = 0.7
    else:
        type_factor = 0.5

    confidence = round(importance * 0.6 + type_factor * 0.4, 3)
    return min(confidence, 1.0)



# ── Claude geocoding provider ─────────────────────────────────────────────────

class ClaudeGeocodingProvider(GeocodingProvider):
    """
    Uses Claude API to geocode locations that Nominatim can't resolve.
    Best for Arabic village names in South Lebanon / West Bank.
    """

    _PROMPT = (
        "You are a precise geocoding assistant. "
        "Return ONLY a valid JSON object — no explanation, no markdown — with the "
        "latitude and longitude of this location: \"{location}\"\n"
        "Format: {{\"lat\": 33.1197, \"lon\": 35.4333}}\n"
        "If you are not confident, still return your best estimate. "
        "Never return null values."
    )

    def geocode(self, query: str) -> Optional[GeoResult]:
        import os
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY not set — Claude geocoding disabled")
            return None
        try:
            import anthropic, json, re
            client = anthropic.Anthropic(api_key=api_key)
            message = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=64,
                messages=[{
                    "role": "user",
                    "content": self._PROMPT.format(location=query),
                }],
            )
            raw = message.content[0].text.strip()
            logger.info(f"Claude raw response for {query!r}: {raw!r}")

            # Strip markdown code fences if present
            clean = re.sub(r"^```[a-z]*\s*|\s*```$", "", raw, flags=re.DOTALL).strip()

            data = json.loads(clean)
            lat = float(data["lat"])
            lon = float(data["lon"])
            logger.info(f"Claude geocoded {query!r} → ({lat}, {lon})")
            return GeoResult(
                latitude=lat,
                longitude=lon,
                confidence=0.80,
                resolved_address=query,
                query=query,
            )
        except Exception as e:
            logger.error(f"Claude geocoding failed for {query!r}: {e}", exc_info=True)
            return None


# ── Static location lookup (high-confidence, no API call needed) ──────────────

SOUTH_LEBANON_LOCATIONS: dict[str, tuple[float, float]] = {
    "النبطية":    (33.3489, 35.4839),
    "نبطية":      (33.3489, 35.4839),
    "بنت جبيل":  (33.1197, 35.4333),
    "صور":        (33.2705, 35.2037),
    "القليعة":   (33.2833, 35.5167),
    "قليعة":     (33.2833, 35.5167),
    "مارون الراس": (33.0833, 35.4333),
    "عيتا الشعب": (33.1167, 35.4167),
    "عيترون":    (33.1333, 35.4500),
    "يارون":     (33.1000, 35.4167),
    "علما الشعب": (33.1167, 35.2167),
    "رميش":      (33.0833, 35.3833),
    "عيناتا":    (33.2000, 35.4167),
    "حاصبيا":    (33.3833, 35.6833),
    "مرجعيون":   (33.3667, 35.5833),
    "خيام":      (33.3167, 35.5833),
    "كفركلا":    (33.1167, 35.5500),
    "ميس الجبل": (33.1500, 35.5167),
    "بليدا":     (33.1667, 35.4333),
    "شقرا":      (33.2667, 35.5333),
    "تبنين":     (33.1833, 35.4167),
    "قانا":      (33.2000, 35.3000),
    "صيدا":      (33.5600, 35.3700),
    "صيدون":     (33.5600, 35.3700),
}


# ── Public geocoding service ──────────────────────────────────────────────────

_provider: GeocodingProvider = NominatimProvider()


def geocode_location(query: str) -> Optional[GeoResult]:
    """
    Geocode a location string.
    Checks the static South Lebanon lookup table before calling Nominatim.
    Returns None if confidence is below minimum threshold or geocoding fails.
    """
    if not query:
        return None

    # Static lookup — instant, no rate-limit
    query_stripped = query.strip()
    if query_stripped in SOUTH_LEBANON_LOCATIONS:
        lat, lng = SOUTH_LEBANON_LOCATIONS[query_stripped]
        logger.debug(f"Static lookup hit: {query_stripped!r} → ({lat}, {lng})")
        return GeoResult(
            latitude=lat,
            longitude=lng,
            confidence=0.95,
            resolved_address=query_stripped,
            query=query_stripped,
        )

    result = _provider.geocode(query)

    if result is None:
        return None

    if result.confidence < settings.GEOCODING_MIN_CONFIDENCE:
        logger.debug(
            f"Geocode confidence too low ({result.confidence:.2f}) for: {query!r}"
        )
        return None

    logger.debug(
        f"Geocoded {query!r} → ({result.latitude:.4f}, {result.longitude:.4f}) "
        f"conf={result.confidence:.2f}"
    )
    return result
