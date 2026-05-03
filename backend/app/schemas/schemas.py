from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict

from app.models.enums import SourceType, EventStatus, EventType, MediaType, RelationType


# ── Source ──────────────────────────────────────────────────────────────────

class SourceCreate(BaseModel):
    name: str
    type: SourceType
    base_url: Optional[str] = None
    is_active: bool = True
    config_json: Optional[dict] = None


class SourceOut(SourceCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime


# ── RawReport ────────────────────────────────────────────────────────────────

class RawReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source_id: int
    external_id: Optional[str]
    source_url: Optional[str]
    raw_text: str
    raw_timestamp: Optional[datetime]
    collected_at: datetime
    media_json: Optional[list]
    language: Optional[str]
    content_hash: str
    is_parsed: bool
    created_at: datetime


# ── Event ────────────────────────────────────────────────────────────────────

class EventMediaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    media_type: MediaType
    media_url: str
    thumbnail_url: Optional[str]
    source_url: Optional[str]
    caption: Optional[str]


class EventUpdateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    field_name: str
    old_value: Optional[str]
    new_value: Optional[str]
    created_at: datetime


class EventReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    raw_report_id: int
    relation_type: RelationType
    dedup_score: Optional[float]
    dedup_reason: Optional[str]
    created_at: datetime


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    canonical_title: Optional[str]
    summary: Optional[str]
    event_type: EventType
    injured_count: Optional[int]
    killed_count: Optional[int]
    affected_people_text: Optional[str]
    event_time: Optional[datetime]
    reported_time: Optional[datetime]
    location_text: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    geocode_confidence: Optional[float]
    parser_confidence: Optional[float]
    status: EventStatus
    first_seen_at: datetime
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime
    media: List[EventMediaOut] = []


class EventDetailOut(EventOut):
    reports: List[EventReportOut] = []
    updates: List[EventUpdateOut] = []


class EventMapPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    canonical_title: Optional[str]
    event_type: EventType
    event_time: Optional[datetime]
    location_text: Optional[str]
    latitude: float
    longitude: float
    injured_count: Optional[int]
    killed_count: Optional[int]
    has_media: bool = False


# ── Stats ────────────────────────────────────────────────────────────────────

class StatsSummary(BaseModel):
    total_events: int
    total_reports: int
    events_with_location: int
    events_with_media: int
    events_by_type: dict
    events_by_status: dict


# ── Pagination ────────────────────────────────────────────────────────────────

class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    pages: int


# ── Pipeline ─────────────────────────────────────────────────────────────────

class PipelineResult(BaseModel):
    success: bool
    processed: int
    errors: int
    details: Optional[str] = None
