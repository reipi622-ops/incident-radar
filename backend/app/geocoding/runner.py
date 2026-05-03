"""
Geocoding Runner
================
Finds events that have location_text but no lat/lng,
attempts geocoding, and stores results.
"""

import time
from loguru import logger
from sqlalchemy.orm import Session

from app.models.models import Event
from app.geocoding.service import geocode_location


def run_geocoding(db: Session, batch_size: int = 30) -> dict:
    """
    Geocode events that have location_text but missing coordinates.
    Rate-limited to 1 request/sec for Nominatim compliance.
    """
    candidates = (
        db.query(Event)
        .filter(
            Event.location_text.isnot(None),
            Event.latitude.is_(None),
        )
        .order_by(Event.created_at)
        .limit(batch_size)
        .all()
    )

    if not candidates:
        logger.info("No events requiring geocoding.")
        return {"processed": 0, "resolved": 0, "failed": 0}

    resolved = 0
    failed = 0

    for event in candidates:
        result = geocode_location(event.location_text)

        if result:
            event.latitude = result.latitude
            event.longitude = result.longitude
            event.geocode_confidence = result.confidence
            event.geocode_query = result.query
            resolved += 1
        else:
            # Store the query so we don't retry the same failed query forever
            event.geocode_query = event.location_text
            failed += 1

        # Nominatim ToS: max 1 request per second
        time.sleep(1.1)

    db.commit()
    logger.info(f"Geocoding run: candidates={len(candidates)} resolved={resolved} failed={failed}")
    return {"processed": len(candidates), "resolved": resolved, "failed": failed}
