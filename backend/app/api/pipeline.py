from pathlib import Path
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.collectors.local_json import LocalJsonCollector
from app.collectors.service import run_collector
from app.parsers.service import run_parser
from app.dedup.service import run_dedup
from app.geocoding.runner import run_geocoding
from app.schemas.schemas import PipelineResult

router = APIRouter()

# Works both locally (repo root) and in Docker (/sample_data volume mount)
def _find_sample_data() -> Path:
    candidates = [
        Path("/sample_data/mock_reports.json"),
        Path(__file__).parent.parent.parent.parent / "sample_data" / "mock_reports.json",
    ]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError("mock_reports.json not found in any expected location")


@router.post("/collect/run", response_model=PipelineResult)
def collect_run(db: Session = Depends(get_db)):
    """Collect raw reports from the mock local JSON source."""
    path = _find_sample_data()
    collector = LocalJsonCollector(file_path=path, source_name="mock_seed")
    result = run_collector(collector, db)
    return PipelineResult(
        success=result["errors"] == 0,
        processed=result["saved"] + result["skipped"],
        errors=result["errors"],
        details=f"saved={result['saved']} skipped={result['skipped']}",
    )


@router.post("/parse/run", response_model=PipelineResult)
def parse_run(db: Session = Depends(get_db)):
    """Parse all unparsed raw_reports."""
    result = run_parser(db)
    return PipelineResult(
        success=result["errors"] == 0,
        processed=result["processed"],
        errors=result["errors"],
        details=f"events_created={result['created']}",
    )


@router.post("/dedup/run", response_model=PipelineResult)
def dedup_run(db: Session = Depends(get_db)):
    """Run deduplication on parsed but unlinked reports."""
    result = run_dedup(db)
    return PipelineResult(
        success=result["errors"] == 0,
        processed=result["processed"],
        errors=result["errors"],
        details=f"linked={result['linked']} created={result['created']}",
    )


@router.post("/geocode/run", response_model=PipelineResult)
def geocode_run(db: Session = Depends(get_db)):
    """Geocode events that have location_text but missing coordinates."""
    result = run_geocoding(db)
    return PipelineResult(
        success=True,
        processed=result["processed"],
        errors=0,
        details=f"resolved={result['resolved']} failed={result['failed']}",
    )


@router.post("/run-all", response_model=PipelineResult)
def run_all(db: Session = Depends(get_db)):
    """Run the full pipeline: collect → parse → dedup → geocode."""
    path = _find_sample_data()
    collector = LocalJsonCollector(file_path=path, source_name="mock_seed")
    c = run_collector(collector, db)
    p = run_parser(db)
    d = run_dedup(db)
    g = run_geocoding(db)

    total_errors = c["errors"] + p["errors"] + d["errors"]
    return PipelineResult(
        success=total_errors == 0,
        processed=c["saved"] + p["processed"] + d["processed"] + g["processed"],
        errors=total_errors,
        details=(
            f"collect:saved={c['saved']} | "
            f"parse:created={p['created']} | "
            f"dedup:linked={d['linked']},new={d['created']} | "
            f"geo:resolved={g['resolved']}"
        ),
    )

@router.post('/telegram/run', response_model=PipelineResult)
async def run_telegram(db: Session = Depends(get_db)):
    from app.collectors.telegram_collector import TelegramChannelCollector
    import asyncio
    collector = TelegramChannelCollector(db)
    result = asyncio.run(collector.collect())
    return PipelineResult(success=True, processed=result.get('saved', 0), errors=0, details=f'telegram:saved={result.get("saved", 0)}')

