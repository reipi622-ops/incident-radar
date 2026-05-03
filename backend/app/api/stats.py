from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.models.models import Event, RawReport, EventMedia
from app.schemas.schemas import StatsSummary

router = APIRouter()


@router.get("/summary", response_model=StatsSummary)
def stats_summary(db: Session = Depends(get_db)):
    total_events  = db.query(func.count(Event.id)).scalar() or 0
    total_reports = db.query(func.count(RawReport.id)).scalar() or 0

    events_with_location = (
        db.query(func.count(Event.id))
        .filter(Event.latitude.isnot(None))
        .scalar() or 0
    )

    events_with_media = (
        db.query(func.count(Event.id.distinct()))
        .join(EventMedia, EventMedia.event_id == Event.id)
        .scalar() or 0
    )

    # Breakdown by event_type
    type_rows = (
        db.query(Event.event_type, func.count(Event.id))
        .group_by(Event.event_type)
        .all()
    )
    events_by_type = {str(row[0].value): row[1] for row in type_rows}

    # Breakdown by status
    status_rows = (
        db.query(Event.status, func.count(Event.id))
        .group_by(Event.status)
        .all()
    )
    events_by_status = {str(row[0].value): row[1] for row in status_rows}

    return StatsSummary(
        total_events=total_events,
        total_reports=total_reports,
        events_with_location=events_with_location,
        events_with_media=events_with_media,
        events_by_type=events_by_type,
        events_by_status=events_by_status,
    )
