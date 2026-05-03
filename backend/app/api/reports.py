from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.models import RawReport
from app.schemas.schemas import RawReportOut, PaginatedResponse
import math

router = APIRouter()


@router.get("", response_model=PaginatedResponse)
def list_reports(
    source_id: Optional[int] = Query(None),
    is_parsed: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = db.query(RawReport)
    if source_id is not None:
        q = q.filter(RawReport.source_id == source_id)
    if is_parsed is not None:
        q = q.filter(RawReport.is_parsed == is_parsed)

    total = q.count()
    items = q.order_by(RawReport.collected_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return PaginatedResponse(
        items=[RawReportOut.model_validate(r) for r in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size),
    )
