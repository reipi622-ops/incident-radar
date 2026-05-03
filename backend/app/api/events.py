import math
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.models.models import Event, EventStatus, EventType
from app.schemas.schemas import EventOut, EventDetailOut, EventMapPoint, PaginatedResponse

router = APIRouter()


def _base_query(db: Session):
    return db.query(Event).options(selectinload(Event.media))


def _parse_event_type(value: Optional[str]) -> Optional[EventType]:
    if not value:
        return None
    try:
        return EventType(value)
    except ValueError:
        return None


def _parse_status(value: Optional[str]) -> Optional[EventStatus]:
    if not value:
        return None
    try:
        return EventStatus(value)
    except ValueError:
        return None


@router.get("", response_model=PaginatedResponse)
def list_events(
    event_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    min_injured: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = _base_query(db)

    et = _parse_event_type(event_type)
    if et:
        q = q.filter(Event.event_type == et)

    st = _parse_status(status)
    if st:
        q = q.filter(Event.status == st)

    if location:
        q = q.filter(Event.location_text.ilike(f"%{location}%"))
    if date_from:
        q = q.filter(Event.event_time >= date_from)
    if date_to:
        q = q.filter(Event.event_time <= date_to)
    if min_injured is not None:
        q = q.filter(Event.injured_count >= min_injured)

    total = q.count()
    items = (
        q.order_by(Event.last_seen_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return PaginatedResponse(
        items=[EventOut.model_validate(e) for e in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 1,
    )


@router.get("/map", response_model=List[EventMapPoint])
def events_map(
    event_type: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Event).filter(
        Event.latitude.isnot(None),
        Event.longitude.isnot(None),
        Event.status != EventStatus.archived,
    )

    et = _parse_event_type(event_type)
    if et:
        q = q.filter(Event.event_type == et)
    if date_from:
        q = q.filter(Event.event_time >= date_from)
    if date_to:
        q = q.filter(Event.event_time <= date_to)

    events = q.options(selectinload(Event.media)).all()
    return [
        EventMapPoint(
            id=e.id,
            canonical_title=e.canonical_title,
            event_type=e.event_type,
            event_time=e.event_time,
            location_text=e.location_text,
            latitude=e.latitude,
            longitude=e.longitude,
            injured_count=e.injured_count,
            killed_count=e.killed_count,
            has_media=bool(e.media),
        )
        for e in events
    ]


@router.get("/{event_id}", response_model=EventDetailOut)
def get_event(event_id: int, db: Session = Depends(get_db)):
    event = (
        db.query(Event)
        .options(
            selectinload(Event.media),
            selectinload(Event.reports),
            selectinload(Event.updates),
        )
        .filter(Event.id == event_id)
        .first()
    )
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return EventDetailOut.model_validate(event)
