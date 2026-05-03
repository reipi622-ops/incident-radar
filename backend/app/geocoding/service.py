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


# ── Public geocoding service ──────────────────────────────────────────────────

_provider: GeocodingProvider = NominatimProvider()


def geocode_location(query: str) -> Optional[GeoResult]:
    """
    Geocode a location string.
    Returns None if confidence is below minimum threshold or geocoding fails.
    """
    if not query:
        return None

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
