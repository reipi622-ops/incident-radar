"""
Tests for the deduplication scoring engine.
Run: pytest backend/tests/test_dedup.py -v
"""
import pytest
from datetime import datetime, timedelta
from app.dedup.engine import (
    score_text_similarity,
    score_time_proximity,
    score_location_match,
    score_location_coords,
    score_event_type,
    score_casualties,
    _haversine_km,
)
from app.models.models import EventType


# ── Text similarity ───────────────────────────────────────────────────────────

class TestTextSimilarity:
    def test_identical_texts_score_one(self):
        t = "שריפה ברחוב הרצל תל אביב, 3 פצועים"
        assert score_text_similarity(t, t) == 1.0

    def test_very_different_texts_score_low(self):
        a = "שריפה בחיפה"
        b = "רעידת אדמה בים המלח"
        assert score_text_similarity(a, b) < 0.4

    def test_similar_texts_score_high(self):
        a = "שריפה ברחוב הרצל תל אביב, 3 פצועים פונו לאיכילוב"
        b = "עדכון: שריפה ברחוב הרצל, מספר הפצועים עלה ל-5"
        score = score_text_similarity(a, b)
        assert score > 0.4  # related content, same event

    def test_empty_string_returns_zero(self):
        assert score_text_similarity("", "some text") == 0.0
        assert score_text_similarity("some text", "") == 0.0

    def test_both_empty_returns_zero(self):
        assert score_text_similarity("", "") == 0.0


# ── Time proximity ────────────────────────────────────────────────────────────

class TestTimeProximity:
    BASE = datetime(2024, 3, 15, 10, 0, 0)

    def test_same_time_score_one(self):
        assert score_time_proximity(self.BASE, self.BASE) == 1.0

    def test_one_hour_apart_high_score(self):
        score = score_time_proximity(self.BASE, self.BASE + timedelta(hours=1))
        assert score > 0.9

    def test_twelve_hours_mid_score(self):
        score = score_time_proximity(self.BASE, self.BASE + timedelta(hours=12))
        assert 0.4 < score < 0.6

    def test_beyond_window_zero(self):
        # Default window = 24h
        score = score_time_proximity(self.BASE, self.BASE + timedelta(hours=25))
        assert score == 0.0

    def test_none_time_returns_zero(self):
        assert score_time_proximity(None, self.BASE) == 0.0
        assert score_time_proximity(self.BASE, None) == 0.0


# ── Location matching ─────────────────────────────────────────────────────────

class TestLocationMatch:
    def test_identical_locations(self):
        assert score_location_match("תל אביב", "תל אביב") == 1.0

    def test_similar_locations(self):
        score = score_location_match("תל אביב רחוב הרצל", "הרצל תל אביב")
        assert score > 0.7

    def test_different_cities(self):
        score = score_location_match("חיפה", "ירושלים")
        assert score < 0.3

    def test_none_location_zero(self):
        assert score_location_match(None, "תל אביב") == 0.0
        assert score_location_match("תל אביב", None) == 0.0


class TestLocationCoords:
    def test_same_point_score_one(self):
        assert score_location_coords(32.0, 34.0, 32.0, 34.0) == 1.0

    def test_nearby_points_high_score(self):
        # ~1km apart
        score = score_location_coords(32.0853, 34.7818, 32.0950, 34.7818)
        assert score > 0.7

    def test_far_points_zero(self):
        # Tel Aviv vs Haifa (~90km)
        score = score_location_coords(32.0853, 34.7818, 32.7940, 34.9896)
        assert score == 0.0

    def test_missing_coords_zero(self):
        assert score_location_coords(None, 34.0, 32.0, 34.0) == 0.0


# ── Haversine ─────────────────────────────────────────────────────────────────

class TestHaversine:
    def test_same_point_zero(self):
        assert _haversine_km(32.0, 34.0, 32.0, 34.0) == 0.0

    def test_tel_aviv_haifa(self):
        dist = _haversine_km(32.0853, 34.7818, 32.7940, 34.9896)
        assert 85 < dist < 95  # ~90km

    def test_symmetry(self):
        a = _haversine_km(32.0, 34.0, 33.0, 35.0)
        b = _haversine_km(33.0, 35.0, 32.0, 34.0)
        assert abs(a - b) < 0.001


# ── Event type ────────────────────────────────────────────────────────────────

class TestEventTypeScore:
    def test_same_type(self):
        assert score_event_type(EventType.fire, EventType.fire) == 1.0

    def test_different_type(self):
        assert score_event_type(EventType.fire, EventType.shooting) == 0.0

    def test_unknown_returns_zero(self):
        assert score_event_type(EventType.unknown, EventType.fire) == 0.0
        assert score_event_type(EventType.fire, EventType.unknown) == 0.0


# ── Casualties ────────────────────────────────────────────────────────────────

class TestCasualtyScore:
    def test_matching_counts_full_score(self):
        assert score_casualties(3, 1, 3, 1) == 1.0

    def test_one_match_half_score(self):
        score = score_casualties(3, 1, 3, 2)  # injured match, killed mismatch
        assert score == 0.5

    def test_no_match(self):
        assert score_casualties(3, 1, 5, 2) == 0.0

    def test_none_counts_return_zero(self):
        assert score_casualties(None, None, 3, 1) == 0.0

    def test_partial_none(self):
        # Only injured known on one side
        score = score_casualties(3, None, 3, None)
        assert score == 1.0


# ── Composite score integration ───────────────────────────────────────────────

class TestCompositeLogic:
    """Test that scoring components combine correctly for realistic pairs."""

    def test_clear_duplicate_scores_high(self):
        """Near-identical reports about same event should combine to > threshold."""
        text_score = score_text_similarity(
            "שריפה ברחוב הרצל תל אביב 3 פצועים",
            "שריפה ברחוב הרצל תל אביב 3 פצועים פונו",
        )
        time_score = score_time_proximity(
            datetime(2024, 3, 15, 8, 0),
            datetime(2024, 3, 15, 8, 30),
        )
        loc_score = score_location_match("רחוב הרצל תל אביב", "הרצל תל אביב")
        type_score = score_event_type(EventType.fire, EventType.fire)

        composite = text_score * 0.4 + time_score * 0.25 + loc_score * 0.2 + type_score * 0.1
        assert composite >= 0.6  # above DEDUP_MIN_SCORE default

    def test_unrelated_events_score_low(self):
        """Different events in different cities should not be merged."""
        text_score = score_text_similarity("שריפה בחיפה", "רעידת אדמה בים המלח")
        type_score = score_event_type(EventType.fire, EventType.earthquake)

        composite = text_score * 0.4 + type_score * 0.1
        assert composite < 0.3
