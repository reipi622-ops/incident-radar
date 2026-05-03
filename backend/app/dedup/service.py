"""
Dedup Service
=============
Takes parsed raw_reports that haven't been linked to events yet,
runs the dedup engine, and either:
  - Links to an existing event (relation_type = update | duplicate)
  - Creates a new event (relation_type = primary)

Also writes EventUpdate records when fields change.
"""

from datetime import datetime
from loguru import logger
from sqlalchemy.orm import Session

from app.models.models import (
    RawReport, Event, EventReport, EventMedia, EventUpdate,
    RelationType, EventStatus, MediaType,
)
from app.parsers.parser import parse_report
from app.dedup.engine import find_matching_event


def _media_type_from_str(s: str) -> MediaType:
    s = (s or "").lower()
    if "video" in s or s in ("mp4", "mov"):
        return MediaType.video
    if "image" in s or s in ("jpg", "jpeg", "png"):
        return MediaType.image
    return MediaType.unknown


def _record_field_change(
    db: Session,
    event: Event,
    field: str,
    old_val,
    new_val,
    report_id: int,
):
    if old_val != new_val and new_val is not None:
        db.add(EventUpdate(
            event_id=event.id,
            field_name=field,
            old_value=str(old_val) if old_val is not None else None,
            new_value=str(new_val),
            source_report_id=report_id,
        ))


def _update_event_fields(db: Session, event: Event, parsed, report: RawReport):
    """Apply higher values from a new report to an existing event."""
    # Prefer higher casualty counts (later reports tend to be more complete)
    if parsed.injured_count is not None:
        old = event.injured_count
        new = max(event.injured_count or 0, parsed.injured_count)
        if new != old:
            _record_field_change(db, event, "injured_count", old, new, report.id)
            event.injured_count = new

    if parsed.killed_count is not None:
        old = event.killed_count
        new = max(event.killed_count or 0, parsed.killed_count)
        if new != old:
            _record_field_change(db, event, "killed_count", old, new, report.id)
            event.killed_count = new

    # Fill in missing location
    if not event.location_text and parsed.location_text:
        _record_field_change(db, event, "location_text", None, parsed.location_text, report.id)
        event.location_text = parsed.location_text

    event.last_seen_at = datetime.utcnow()
    event.status = EventStatus.updated


def run_dedup(db: Session, batch_size: int = 50) -> dict:
    """
    Process parsed raw_reports that haven't been linked to any event yet.
    """
    # Reports that are parsed but not yet linked to any event
    linked_ids = db.query(EventReport.raw_report_id).subquery()
    unlinked = (
        db.query(RawReport)
        .filter(
            RawReport.is_parsed == True,  # noqa: E712
            ~RawReport.id.in_(linked_ids),
        )
        .order_by(RawReport.collected_at)
        .limit(batch_size)
        .all()
    )

    if not unlinked:
        logger.info("No unlinked parsed reports found.")
        return {"processed": 0, "linked": 0, "created": 0, "errors": 0}

    linked = 0
    created = 0
    errors = 0

    for report in unlinked:
        try:
            parsed = parse_report(report.raw_text, report.media_json)

            result = find_matching_event(
                db=db,
                raw_text=report.raw_text,
                event_type=parsed.event_type,
                event_time=report.raw_timestamp,
                location_text=parsed.location_text,
                latitude=None,   # geocoding happens in a separate phase
                longitude=None,
                injured_count=parsed.injured_count,
                killed_count=parsed.killed_count,
            )

            if result.matched_event_id:
                # Link to existing event
                rel = RelationType.duplicate if result.is_duplicate else RelationType.update
                event = db.get(Event, result.matched_event_id)

                db.add(EventReport(
                    event_id=result.matched_event_id,
                    raw_report_id=report.id,
                    relation_type=rel,
                    dedup_score=result.score,
                    dedup_reason=result.reason,
                ))

                if not result.is_duplicate:
                    _update_event_fields(db, event, parsed, report)

                # Attach any new media
                if report.media_json:
                    for item in report.media_json:
                        db.add(EventMedia(
                            event_id=result.matched_event_id,
                            media_type=_media_type_from_str(item.get("type", "")),
                            media_url=item.get("url", ""),
                            source_url=report.source_url,
                            caption=item.get("caption"),
                        ))
                linked += 1

            else:
                # Create a new event
                event = Event(
                    canonical_title=(parsed.summary or "")[:100],
                    summary=parsed.summary,
                    event_type=parsed.event_type,
                    injured_count=parsed.injured_count,
                    killed_count=parsed.killed_count,
                    affected_people_text=parsed.affected_people_text,
                    event_time=report.raw_timestamp,
                    reported_time=report.raw_timestamp,
                    location_text=parsed.location_text,
                    parser_confidence=parsed.confidence,
                    status=EventStatus.new,
                    first_seen_at=datetime.utcnow(),
                    last_seen_at=datetime.utcnow(),
                )
                db.add(event)
                db.flush()

                db.add(EventReport(
                    event_id=event.id,
                    raw_report_id=report.id,
                    relation_type=RelationType.primary,
                    dedup_score=None,
                    dedup_reason="no match — new event",
                ))

                if report.media_json:
                    for item in report.media_json:
                        db.add(EventMedia(
                            event_id=event.id,
                            media_type=_media_type_from_str(item.get("type", "")),
                            media_url=item.get("url", ""),
                            source_url=report.source_url,
                            caption=item.get("caption"),
                        ))
                created += 1

        except Exception as e:
            logger.error(f"Dedup error on report {report.id}: {e}")
            errors += 1

    db.commit()
    logger.info(f"Dedup run: processed={len(unlinked)} linked={linked} created={created} errors={errors}")
    return {"processed": len(unlinked), "linked": linked, "created": created, "errors": errors}
