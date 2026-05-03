"""
Database Models — Incident Radar
=================================

Tables:
  sources        — registered data sources (RSS, API, mock, etc.)
  raw_reports    — immutable as-collected reports, never modified after insert
  events         — deduplicated, geocoded, processed incidents
  event_reports  — many-to-many: which reports belong to which event + dedup metadata
  event_media    — media assets linked to an event (URL + metadata only, no downloads)
  event_updates  — audit trail: every field change on an event with source attribution

Verification checklist:
  ✅ raw_reports.content_hash       — SHA-256 prevents duplicate ingestion
  ✅ raw_reports.raw_timestamp      — indexed for time-range queries
  ✅ events.parser_confidence       — 0.0–1.0 extraction quality signal
  ✅ events.geocode_confidence      — 0.0–1.0 geolocation quality signal
  ✅ events.status                  — new / updated / verified / duplicate / archived
  ✅ event_reports.relation_type    — primary / update / duplicate / related
  ✅ event_updates.source_report_id — traces which report caused each field change
  ✅ All required indexes present
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    String, Integer, Float, Boolean, Text, DateTime, ForeignKey,
    Enum as SAEnum, JSON, UniqueConstraint, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


# ── Enumerations (imported from enums.py — zero external deps) ───────────────
from app.models.enums import (  # noqa: E402
    SourceType, EventStatus, EventType, MediaType, RelationType
)


# ── sources ───────────────────────────────────────────────────────────────────

class Source(Base):
    """
    A registered data source.
    Every collector registers itself here before inserting raw_reports.
    config_json holds source-specific settings (selectors, auth, rate limits).
    """
    __tablename__ = "sources"

    id:          Mapped[int]            = mapped_column(Integer, primary_key=True)
    name:        Mapped[str]            = mapped_column(String(255), nullable=False, unique=True)
    type:        Mapped[SourceType]     = mapped_column(SAEnum(SourceType, native_enum=False), nullable=False)
    base_url:    Mapped[Optional[str]]  = mapped_column(String(2048))
    is_active:   Mapped[bool]           = mapped_column(Boolean, default=True, nullable=False)
    config_json: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at:  Mapped[datetime]       = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    raw_reports: Mapped[list["RawReport"]] = relationship(back_populates="source", lazy="select")

    def __repr__(self) -> str:
        return f"<Source id={self.id} name={self.name!r} type={self.type}>"


# ── raw_reports ───────────────────────────────────────────────────────────────

class RawReport(Base):
    """
    Immutable record of a collected report, stored exactly as received.

    content_hash: SHA-256 of raw_text — (source_id, content_hash) unique constraint
                  prevents the same content from being ingested twice.
    is_parsed:    False on insert; set to True after the parser processes this row.
    media_json:   List of {url, type, caption} objects extracted at collection time.
    """
    __tablename__ = "raw_reports"

    id:            Mapped[int]                = mapped_column(Integer, primary_key=True)
    source_id:     Mapped[int]                = mapped_column(ForeignKey("sources.id"), nullable=False)
    external_id:   Mapped[Optional[str]]      = mapped_column(String(512))
    source_url:    Mapped[Optional[str]]      = mapped_column(String(2048))
    raw_text:      Mapped[str]                = mapped_column(Text, nullable=False)
    raw_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime)
    collected_at:  Mapped[datetime]           = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    media_json:    Mapped[Optional[list]]     = mapped_column(JSON)
    language:      Mapped[Optional[str]]      = mapped_column(String(10))     # ISO 639-1: "he" | "ar" | "en"
    content_hash:  Mapped[str]                = mapped_column(String(64), nullable=False)  # SHA-256 hex
    is_parsed:     Mapped[bool]               = mapped_column(Boolean, default=False, nullable=False)
    created_at:    Mapped[datetime]           = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    source:      Mapped["Source"]             = relationship(back_populates="raw_reports")
    event_links: Mapped[list["EventReport"]]  = relationship(back_populates="raw_report")

    __table_args__ = (
        UniqueConstraint("source_id", "content_hash", name="uq_raw_report_source_hash"),
        Index("ix_raw_reports_content_hash",  "content_hash"),   # ✅ fast dedup lookup
        Index("ix_raw_reports_raw_timestamp", "raw_timestamp"),  # ✅ time-window queries
        Index("ix_raw_reports_source_id",     "source_id"),
        Index("ix_raw_reports_is_parsed",     "is_parsed"),      # ✅ worker queue filter
        Index("ix_raw_reports_collected_at",  "collected_at"),
    )

    def __repr__(self) -> str:
        return f"<RawReport id={self.id} source_id={self.source_id} parsed={self.is_parsed}>"


# ── events ────────────────────────────────────────────────────────────────────

class Event(Base):
    """
    A processed, deduplicated incident. This is what appears on the map.

    An event may be backed by 1..N raw_reports (via event_reports).
    Fields are updated as new reports arrive; changes are logged in event_updates.

    Confidence fields:
      parser_confidence  — how reliably the parser extracted structured data (0–1)
      geocode_confidence — how reliably the geocoder resolved lat/lng (0–1)

    Status lifecycle:
      new → updated → verified
          ↘ duplicate
          ↘ archived
    """
    __tablename__ = "events"

    id:                   Mapped[int]                = mapped_column(Integer, primary_key=True)
    canonical_title:      Mapped[Optional[str]]      = mapped_column(String(512))
    summary:              Mapped[Optional[str]]      = mapped_column(Text)

    # Classification
    event_type:           Mapped[EventType]          = mapped_column(
        SAEnum(EventType, native_enum=False), default=EventType.unknown, nullable=False
    )

    # Casualties
    injured_count:        Mapped[Optional[int]]      = mapped_column(Integer)
    killed_count:         Mapped[Optional[int]]      = mapped_column(Integer)
    affected_people_text: Mapped[Optional[str]]      = mapped_column(Text)

    # Timing
    event_time:           Mapped[Optional[datetime]] = mapped_column(DateTime)
    reported_time:        Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Location
    location_text:        Mapped[Optional[str]]      = mapped_column(String(512))
    latitude:             Mapped[Optional[float]]    = mapped_column(Float)
    longitude:            Mapped[Optional[float]]    = mapped_column(Float)
    geocode_confidence:   Mapped[Optional[float]]    = mapped_column(Float)  # ✅ 0.0–1.0
    geocode_query:        Mapped[Optional[str]]      = mapped_column(String(512))

    # Quality signals
    parser_confidence:    Mapped[Optional[float]]    = mapped_column(Float)  # ✅ 0.0–1.0

    # ✅ Status
    status:               Mapped[EventStatus]        = mapped_column(
        SAEnum(EventStatus, native_enum=False), default=EventStatus.new, nullable=False
    )

    # Timestamps
    first_seen_at:        Mapped[datetime]           = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at:         Mapped[datetime]           = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    created_at:           Mapped[datetime]           = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at:           Mapped[datetime]           = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    reports: Mapped[list["EventReport"]] = relationship(back_populates="event", lazy="select")
    media:   Mapped[list["EventMedia"]]  = relationship(back_populates="event", lazy="select")
    updates: Mapped[list["EventUpdate"]] = relationship(back_populates="event", lazy="select")

    __table_args__ = (
        Index("ix_events_event_time",    "event_time"),     # ✅
        Index("ix_events_location_text", "location_text"),  # ✅
        Index("ix_events_event_type",    "event_type"),
        Index("ix_events_status",        "status"),
        Index("ix_events_lat_lng",       "latitude", "longitude"),
        Index("ix_events_last_seen_at",  "last_seen_at"),
    )

    def __repr__(self) -> str:
        return f"<Event id={self.id} type={self.event_type} status={self.status}>"


# ── event_reports ─────────────────────────────────────────────────────────────

class EventReport(Base):
    """
    Many-to-many join between events and raw_reports.
    Carries full dedup metadata so every merge decision is explainable.

    relation_type:
      primary   — the report that originally created this event
      update    — a later report that triggered a field change
      duplicate — identical or near-identical content; not merged into new event
      related   — contextually linked but below the merge threshold
    """
    __tablename__ = "event_reports"

    id:            Mapped[int]             = mapped_column(Integer, primary_key=True)
    event_id:      Mapped[int]             = mapped_column(ForeignKey("events.id"), nullable=False)
    raw_report_id: Mapped[int]             = mapped_column(ForeignKey("raw_reports.id"), nullable=False)
    relation_type: Mapped[RelationType]    = mapped_column(                              # ✅
        SAEnum(RelationType, native_enum=False), default=RelationType.primary, nullable=False
    )
    dedup_score:   Mapped[Optional[float]] = mapped_column(Float)   # 0.0–1.0; None if primary
    dedup_reason:  Mapped[Optional[str]]   = mapped_column(Text)    # "text_sim=0.82, Δt=1.5h, same_location"
    created_at:    Mapped[datetime]        = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    event:      Mapped["Event"]     = relationship(back_populates="reports")
    raw_report: Mapped["RawReport"] = relationship(back_populates="event_links")

    __table_args__ = (
        Index("ix_event_reports_event_id",      "event_id"),       # ✅
        Index("ix_event_reports_raw_report_id", "raw_report_id"),  # ✅
    )

    def __repr__(self) -> str:
        return f"<EventReport event={self.event_id} report={self.raw_report_id} rel={self.relation_type}>"


# ── event_media ───────────────────────────────────────────────────────────────

class EventMedia(Base):
    """
    Media asset linked to an event.
    MVP: store URL + metadata only. No binary downloads.
    """
    __tablename__ = "event_media"

    id:            Mapped[int]           = mapped_column(Integer, primary_key=True)
    event_id:      Mapped[int]           = mapped_column(ForeignKey("events.id"), nullable=False)
    media_type:    Mapped[MediaType]     = mapped_column(SAEnum(MediaType, native_enum=False), default=MediaType.unknown, nullable=False)
    media_url:     Mapped[str]           = mapped_column(String(2048), nullable=False)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(2048))
    source_url:    Mapped[Optional[str]] = mapped_column(String(2048))
    caption:       Mapped[Optional[str]] = mapped_column(Text)
    created_at:    Mapped[datetime]      = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    event: Mapped["Event"] = relationship(back_populates="media")

    __table_args__ = (
        Index("ix_event_media_event_id", "event_id"),
    )

    def __repr__(self) -> str:
        return f"<EventMedia id={self.id} event={self.event_id} type={self.media_type}>"


# ── event_updates ─────────────────────────────────────────────────────────────

class EventUpdate(Base):
    """
    Audit trail of every field change on an Event.
    Enables reconstruction of the full history of an incident over time.
    source_report_id traces exactly which raw_report triggered each change.
    """
    __tablename__ = "event_updates"

    id:               Mapped[int]           = mapped_column(Integer, primary_key=True)
    event_id:         Mapped[int]           = mapped_column(ForeignKey("events.id"), nullable=False)
    field_name:       Mapped[str]           = mapped_column(String(100), nullable=False)
    old_value:        Mapped[Optional[str]] = mapped_column(Text)
    new_value:        Mapped[Optional[str]] = mapped_column(Text)
    source_report_id: Mapped[Optional[int]] = mapped_column(ForeignKey("raw_reports.id"))  # ✅
    created_at:       Mapped[datetime]      = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    event: Mapped["Event"] = relationship(back_populates="updates")

    __table_args__ = (
        Index("ix_event_updates_event_id", "event_id"),
    )

    def __repr__(self) -> str:
        return f"<EventUpdate event={self.event_id} field={self.field_name!r}>"
