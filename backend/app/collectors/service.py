import hashlib
from datetime import datetime
from typing import List, Optional
from loguru import logger
from sqlalchemy.orm import Session

from app.collectors.base import BaseCollector, RawItem
from app.models.models import RawReport, Source, SourceType


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _get_or_create_source(db: Session, name: str, source_type: SourceType, base_url: Optional[str] = None) -> Source:
    source = db.query(Source).filter(Source.name == name).first()
    if not source:
        source = Source(name=name, type=source_type, base_url=base_url)
        db.add(source)
        db.commit()
        db.refresh(source)
        logger.info(f"Created new source: {name}")
    return source


def run_collector(collector: BaseCollector, db: Session) -> dict:
    """
    Run a collector and persist raw items to the database.
    Returns a summary dict.
    """
    source = _get_or_create_source(
        db=db,
        name=collector.source_name,
        source_type=SourceType.mock,
    )

    items: List[RawItem] = collector.collect()
    saved = 0
    skipped = 0
    errors = 0

    for item in items:
        try:
            content_hash = _hash_text(item.raw_text)

            # Skip duplicate content
            existing = (
                db.query(RawReport)
                .filter(RawReport.source_id == source.id, RawReport.content_hash == content_hash)
                .first()
            )
            if existing:
                skipped += 1
                continue

            report = RawReport(
                source_id=source.id,
                external_id=item.external_id,
                source_url=item.source_url,
                raw_text=item.raw_text,
                raw_timestamp=item.raw_timestamp,
                collected_at=datetime.utcnow(),
                media_json=item.media_items or None,
                language=item.language,
                content_hash=content_hash,
                is_parsed=False,
            )
            db.add(report)
            saved += 1

        except Exception as e:
            logger.error(f"Error saving item {item.external_id}: {e}")
            errors += 1

    db.commit()
    logger.info(f"[{collector.source_name}] Saved={saved}, Skipped={skipped}, Errors={errors}")
    return {"saved": saved, "skipped": skipped, "errors": errors}
