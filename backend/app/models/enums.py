"""
Enumerations — no external dependencies.
Imported by models.py (SQLAlchemy) and by parser/dedup directly.
"""
import enum


class SourceType(str, enum.Enum):
    rss     = "rss"
    api     = "api"
    scraper = "scraper"
    mock    = "mock"
    manual  = "manual"


class EventStatus(str, enum.Enum):
    new       = "new"
    updated   = "updated"
    verified  = "verified"
    duplicate = "duplicate"
    archived  = "archived"


class EventType(str, enum.Enum):
    fire       = "fire"
    explosion  = "explosion"
    shooting   = "shooting"
    accident   = "accident"
    flood      = "flood"
    earthquake = "earthquake"
    protest    = "protest"
    crime      = "crime"
    terror     = "terror"
    medical    = "medical"
    other      = "other"
    unknown    = "unknown"


class MediaType(str, enum.Enum):
    image    = "image"
    video    = "video"
    audio    = "audio"
    document = "document"
    unknown  = "unknown"


class RelationType(str, enum.Enum):
    primary   = "primary"
    update    = "update"
    duplicate = "duplicate"
    related   = "related"
