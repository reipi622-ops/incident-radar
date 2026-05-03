"""
Deduplication Engine — Incident Radar
=======================================
Heuristic scoring engine. No ML in MVP — fully explainable rule-based logic.

Score components (max 1.0):
  text_similarity   0.40  — fuzzy match between report texts
  time_proximity    0.25  — how close in time the events are
  location_match    0.20  — same location string or coordinates
  type_match        0.10  — same event type
  casualty_match    0.05  — same injured/killed counts

If total score >= DEDUP_MIN_SCORE, the incoming report is linked to the
existing event as `update` or `duplicate`. Otherwise a new event is created.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from loguru import logger
from thefuzz import fuzz
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import EventType, EventStatus
from app.models.models import Event


# ── Score weights ─────────────────────────────────────────────────────────────

W_TEXT     = 0.40
W_TIME     = 0.25
W_LOCATION = 0.20
W_TYPE     = 0.10
W_CASUALTY = 0.05


@dataclass
class DedupResult:
    matched_event_id: Optional[int]
    score: float
    reason: str
    is_duplicate: bool   # True = exact copy; False = update


# ── Scoring functions (pure, testable) ───────────────────────────────────────

def score_text_similarity(text_a: str, text_b: str) -> float:
    """0.0–1.0: how similar are the two texts."""
    if not text_a or not text_b:
        return 0.0
    ratio = fuzz.token_set_ratio(text_a, text_b) / 100.0
    return round(ratio, 3)


def score_time_proximity(time_a: Optional[datetime], time_b: Optional[datetime]) -> float:
    """0.0–1.0: decreasing score as time gap grows."""
    if not time_a or not time_b:
        return 0.0
    delta_hours = abs((time_a - time_b).total_seconds()) / 3600.0
    window = settings.DEDUP_TIME_WINDOW_HOURS
    if delta_hours > window:
        return 0.0
    # Linear decay: full score at 0h, zero at window
    return round(1.0 - (delta_hours / window), 3)


def score_location_match(loc_a: Optional[str], loc_b: Optional[str]) -> float:
    """0.0–1.0: fuzzy match on location text."""
    if not loc_a or not loc_b:
        return 0.0
    ratio = fuzz.token_set_ratio(loc_a, loc_b) / 100.0
    return round(ratio, 3)


def score_location_coords(
    lat_a: Optional[float], lng_a: Optional[float],
    lat_b: Optional[float], lng_b: Optional[float],
) -> float:
    """0.0–1.0 based on distance between coordinates."""
    if None in (lat_a, lng_a, lat_b, lng_b):
        return 0.0
    dist_km = _haversine_km(lat_a, lng_a, lat_b, lng_b)
    if dist_km > settings.DEDUP_LOCATION_RADIUS_KM:
        return 0.0
    return round(1.0 - (dist_km / settings.DEDUP_LOCATION_RADIUS_KM), 3)


def score_event_type(type_a: EventType, type_b: EventType) -> float:
    if type_a == EventType.unknown or type_b == EventType.unknown:
        return 0.0
    return 1.0 if type_a == type_b else 0.0


def score_casualties(
    injured_a: Optional[int], killed_a: Optional[int],
    injured_b: Optional[int], killed_b: Optional[int],
) -> float:
    """1.0 if both counts match, 0.5 if one matches, 0.0 otherwise."""
    if injured_a is None and killed_a is None:
        return 0.0
    matches = 0
    total = 0
    for a, b in ((injured_a, injured_b), (killed_a, killed_b)):
        if a is not None and b is not None:
            total += 1
            if a == b:
                matches += 1
    return round(matches / total, 3) if total else 0.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


# ── Main dedup function ───────────────────────────────────────────────────────

def find_matching_event(
    db: Session,
    raw_text: str,
    event_type: EventType,
    event_time: Optional[datetime],
    location_text: Optional[str],
    latitude: Optional[float],
    longitude: Optional[float],
    injured_count: Optional[int],
    killed_count: Optional[int],
) -> DedupResult:
    """
    Search recent events for a match.
    Returns DedupResult with the best match (or None if no match above threshold).
    """
    time_window = settings.DEDUP_TIME_WINDOW_HOURS
    cutoff = None
    if event_time:
        cutoff = event_time - timedelta(hours=time_window)

    # Limit candidate pool: same type within time window
    query = db.query(Event).filter(Event.status.notin_([EventStatus.duplicate, EventStatus.archived]))
    if event_type != EventType.unknown:
        query = query.filter(Event.event_type == event_type)
    if cutoff:
        query = query.filter(Event.last_seen_at >= cutoff)

    candidates = query.order_by(Event.last_seen_at.desc()).limit(50).all()

    best_score = 0.0
    best_event: Optional[Event] = None
    best_reason = ""

    for candidate in candidates:
        components: dict[str, float] = {}

        # Text similarity (most important signal)
        summary = candidate.summary or ""
        ts = score_text_similarity(raw_text[:500], summary[:500])
        components["text"] = ts * W_TEXT

        # Time proximity
        tp = score_time_proximity(event_time, candidate.last_seen_at)
        components["time"] = tp * W_TIME

        # Location (prefer coords if available, fall back to text)
        if latitude and longitude and candidate.latitude and candidate.longitude:
            lp = score_location_coords(latitude, longitude, candidate.latitude, candidate.longitude)
        else:
            lp = score_location_match(location_text, candidate.location_text)
        components["location"] = lp * W_LOCATION

        # Type match
        components["type"] = score_event_type(event_type, candidate.event_type) * W_TYPE

        # Casualties
        cp = score_casualties(injured_count, killed_count, candidate.injured_count, candidate.killed_count)
        components["casualties"] = cp * W_CASUALTY

        total = round(sum(components.values()), 3)

        if total > best_score:
            best_score = total
            best_event = candidate
            best_reason = (
                f"text_sim={ts:.2f}, time_prox={tp:.2f}, "
                f"loc_sim={lp:.2f}, type={components['type'] / W_TYPE:.0f}, "
                f"casualties={cp:.2f} → total={total:.3f}"
            )

    threshold = settings.DEDUP_MIN_SCORE

    if best_event and best_score >= threshold:
        is_dup = best_score >= 0.90
        logger.debug(f"Dedup match: event_id={best_event.id} score={best_score:.3f} dup={is_dup}")
        return DedupResult(
            matched_event_id=best_event.id,
            score=best_score,
            reason=best_reason,
            is_duplicate=is_dup,
        )

    return DedupResult(matched_event_id=None, score=best_score, reason="no match above threshold", is_duplicate=False)
