"""Detection querying endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Detection, DetectionCategory, User
from app.schemas import DetectionPage, DetectionRead
from app.security import get_current_user

router = APIRouter(prefix="/api/detections", tags=["detections"])


def _apply_filters(
    query: Select,
    video_id: int | None,
    category: DetectionCategory | None,
    min_confidence: float,
    search: str | None,
) -> Select:
    if video_id is not None:
        query = query.where(Detection.video_id == video_id)
    if category is not None:
        query = query.where(Detection.category == category)
    if min_confidence > 0:
        query = query.where(Detection.confidence >= min_confidence)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(Detection.plate_text.ilike(pattern) | Detection.label.ilike(pattern))
    return query


@router.get("", response_model=DetectionPage)
def list_detections(
    video_id: int | None = None,
    category: DetectionCategory | None = None,
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0),
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> DetectionPage:
    limit = max(1, min(limit, 200))
    total = (
        db.scalar(
            _apply_filters(
                select(func.count(Detection.id)), video_id, category, min_confidence, search
            )
        )
        or 0
    )
    query = _apply_filters(select(Detection), video_id, category, min_confidence, search)
    ordering = Detection.id.asc() if order == "asc" else Detection.id.desc()
    rows = list(db.scalars(query.order_by(ordering).limit(limit).offset(offset)))
    return DetectionPage(
        total=total,
        limit=limit,
        offset=offset,
        items=[DetectionRead.model_validate(row) for row in rows],
    )


@router.get("/categories", response_model=dict[str, int])
def detection_category_counts(
    video_id: int | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict[str, int]:
    query = select(Detection.category, func.count(Detection.id)).group_by(Detection.category)
    if video_id is not None:
        query = query.where(Detection.video_id == video_id)
    return {category.value: count for category, count in db.execute(query).all()}


@router.get("/{detection_id}", response_model=DetectionRead)
def get_detection(
    detection_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> DetectionRead:
    row = db.get(Detection, detection_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Detection not found")
    return DetectionRead.model_validate(row)
