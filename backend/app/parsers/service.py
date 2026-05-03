"""
Parser Service
==============
Fetches unparsed raw_reports, runs the parser, and marks them as parsed.
Event creation and deduplication happens in dedup/service.py.
This separation keeps responsibilities clean.
"""

from loguru import logger
from sqlalchemy.orm import Session

from app.models.models import RawReport
from app.parsers.parser import parse_report


def run_parser(db: Session, batch_size: int = 50) -> dict:
    """
    Parse up to batch_size unparsed raw_reports.
    Marks each as is_parsed=True. Event creation handled by dedup service.
    """
    unparsed = (
        db.query(RawReport)
        .filter(RawReport.is_parsed == False)  # noqa: E712
        .order_by(RawReport.collected_at)
        .limit(batch_size)
        .all()
    )

    if not unparsed:
        logger.info("No unparsed reports found.")
        return {"processed": 0, "created": 0, "errors": 0}

    processed = 0
    errors = 0

    for report in unparsed:
        try:
            # Validate the report can be parsed (will raise on bad input)
            parse_report(report.raw_text, report.media_json)
            report.is_parsed = True
            processed += 1
        except Exception as e:
            logger.error(f"Failed to parse report {report.id}: {e}")
            errors += 1

    db.commit()
    logger.info(f"Parser run: processed={processed} errors={errors}")
    return {"processed": processed, "created": 0, "errors": errors}
