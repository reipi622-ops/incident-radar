"""
API integration tests.
Run: pytest backend/tests/test_api.py -v
"""
import hashlib
import uuid
from datetime import datetime

import pytest
from app.models.models import Source, RawReport, Event, SourceType, EventType, EventStatus


# ── Helpers ───────────────────────────────────────────────────────────────────

def _unique_name(prefix: str = "src") -> str:
    """Generate a unique name to avoid conflicts between tests."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _make_source(db, name: str = None) -> Source:
    s = Source(
        name=name or _unique_name("source"),
        type=SourceType.mock,
        base_url="http://test.local",
    )
    db.add(s)
    db.flush()
    return s


def _make_report(db, source_id: int, text: str = None) -> RawReport:
    text = text or f"שריפה בתל אביב {uuid.uuid4().hex[:6]}"
    r = RawReport(
        source_id=source_id,
        raw_text=text,
        content_hash=hashlib.sha256(text.encode()).hexdigest(),
        collected_at=datetime.utcnow(),
        language="he",
    )
    db.add(r)
    db.flush()
    return r


def _make_event(db) -> Event:
    e = Event(
        canonical_title="שריפה בתל אביב",
        event_type=EventType.fire,
        status=EventStatus.new,
        latitude=32.0853,
        longitude=34.7818,
        location_text="תל אביב",
        injured_count=3,
        first_seen_at=datetime.utcnow(),
        last_seen_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(e)
    db.flush()
    return e


# ── Health ────────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_returns_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert "status" in r.json()


# ── Sources ───────────────────────────────────────────────────────────────────

class TestSources:
    def test_list_sources_returns_list(self, client):
        r = client.get("/sources")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_source(self, client):
        name = _unique_name("walla")
        r = client.post("/sources", json={
            "name": name, "type": "rss",
            "base_url": "https://rss.walla.co.il", "is_active": True,
        })
        assert r.status_code == 201
        assert r.json()["name"] == name
        assert r.json()["id"] is not None

    def test_create_duplicate_source_returns_409(self, client):
        name = _unique_name("dup")
        client.post("/sources", json={"name": name, "type": "mock", "is_active": True})
        r = client.post("/sources", json={"name": name, "type": "mock", "is_active": True})
        assert r.status_code == 409

    def test_get_source_by_id(self, client, db):
        source = _make_source(db)
        r = client.get(f"/sources/{source.id}")
        assert r.status_code == 200
        assert r.json()["id"] == source.id

    def test_get_nonexistent_source_returns_404(self, client):
        r = client.get("/sources/99999")
        assert r.status_code == 404


# ── Raw Reports ───────────────────────────────────────────────────────────────

class TestRawReports:
    def test_list_reports_returns_paginated(self, client):
        r = client.get("/raw-reports")
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data

    def test_list_reports_pagination_respected(self, client, db):
        source = _make_source(db)
        for i in range(5):
            _make_report(db, source.id)

        r = client.get("/raw-reports?page=1&page_size=3")
        assert r.status_code == 200
        assert len(r.json()["items"]) <= 3

    def test_filter_by_source_id(self, client, db):
        source = _make_source(db)
        _make_report(db, source.id)

        r = client.get(f"/raw-reports?source_id={source.id}")
        assert r.status_code == 200
        assert r.json()["total"] >= 1


# ── Events ────────────────────────────────────────────────────────────────────

class TestEvents:
    def test_list_events_returns_paginated(self, client):
        r = client.get("/events")
        assert r.status_code == 200
        assert "items" in r.json()

    def test_get_event_by_id(self, client, db):
        event = _make_event(db)
        r = client.get(f"/events/{event.id}")
        assert r.status_code == 200
        assert r.json()["id"] == event.id
        assert r.json()["event_type"] == "fire"

    def test_get_nonexistent_event_returns_404(self, client):
        r = client.get("/events/99999")
        assert r.status_code == 404

    def test_map_endpoint_returns_list(self, client, db):
        _make_event(db)
        r = client.get("/events/map")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        if data:
            assert "latitude" in data[0]
            assert "longitude" in data[0]

    def test_filter_by_event_type(self, client, db):
        _make_event(db)
        r = client.get("/events?event_type=fire")
        assert r.status_code == 200
        for item in r.json()["items"]:
            assert item["event_type"] == "fire"

    def test_invalid_event_type_returns_empty(self, client):
        r = client.get("/events?event_type=notavalidtype")
        assert r.status_code == 200
        assert r.json()["items"] == []

    def test_pagination_fields_present(self, client):
        r = client.get("/events?page=1&page_size=5")
        assert r.status_code == 200
        data = r.json()
        assert all(k in data for k in ("items", "total", "page", "page_size", "pages"))


# ── Stats ─────────────────────────────────────────────────────────────────────

class TestStats:
    def test_summary_has_all_fields(self, client):
        r = client.get("/stats/summary")
        assert r.status_code == 200
        data = r.json()
        assert "total_events" in data
        assert "total_reports" in data
        assert "events_with_location" in data
        assert "events_with_media" in data
        assert "events_by_type" in data
        assert "events_by_status" in data

    def test_summary_counts_non_negative(self, client):
        r = client.get("/stats/summary")
        data = r.json()
        assert data["total_events"] >= 0
        assert data["total_reports"] >= 0
        assert data["events_with_location"] >= 0
