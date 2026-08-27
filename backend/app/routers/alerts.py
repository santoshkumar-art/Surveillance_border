"""Alert feed and acknowledgement endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.events import bus
from app.models import Alert, AlertSeverity, DetectionCategory, User, Video
from app.schemas import AlertAcknowledgeRequest, AlertPage, AlertRead
from app.security import get_current_user

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


def _serialize(alert: Alert) -> AlertRead:
    payload = AlertRead.model_validate(alert)
    if alert.video is not None:
        payload.video_name = alert.video.original_name
        payload.checkpoint = alert.video.checkpoint
    return payload


def _apply_filters(
    query: Select,
    video_id: int | None,
    severity: AlertSeverity | None,
    category: DetectionCategory | None,
    acknowledged: bool | None,
) -> Select:
    if video_id is not None:
        query = query.where(Alert.video_id == video_id)
    if severity is not None:
        query = query.where(Alert.severity == severity)
    if category is not None:
        query = query.where(Alert.category == category)
    if acknowledged is not None:
        query = query.where(Alert.acknowledged.is_(acknowledged))
    return query


@router.get("", response_model=AlertPage)
def list_alerts(
    video_id: int | None = None,
    severity: AlertSeverity | None = None,
    category: DetectionCategory | None = None,
    acknowledged: bool | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> AlertPage:
    limit = max(1, min(limit, 200))
    total = (
        db.scalar(
            _apply_filters(select(func.count(Alert.id)), video_id, severity, category, acknowledged)
        )
        or 0
    )
    query = _apply_filters(
        select(Alert).options(joinedload(Alert.video)), video_id, severity, category, acknowledged
    )
    rows = list(
        db.scalars(
            query.order_by(Alert.created_at.desc(), Alert.id.desc()).limit(limit).offset(offset)
        ).unique()
    )
    return AlertPage(
        total=total, limit=limit, offset=offset, items=[_serialize(row) for row in rows]
    )


@router.get("/live", response_model=list[dict])
def recent_events(_user: User = Depends(get_current_user)) -> list[dict]:
    """Replay buffer of the newest live events (used when a dashboard reconnects)."""
    return bus.recent


@router.post("/{alert_id}/acknowledge", response_model=AlertRead)
def acknowledge_alert(
    alert_id: int,
    payload: AlertAcknowledgeRequest = AlertAcknowledgeRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AlertRead:
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.acknowledged = payload.acknowledged
    alert.acknowledged_at = datetime.now(timezone.utc) if payload.acknowledged else None
    alert.acknowledged_by = current_user.username if payload.acknowledged else None
    db.commit()
    db.refresh(alert)
    bus.publish(
        "alert_acknowledged",
        {"alert_id": alert.id, "acknowledged": alert.acknowledged, "by": alert.acknowledged_by},
    )
    return _serialize(alert)


@router.post("/acknowledge-all", response_model=dict[str, int])
def acknowledge_all(
    video_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, int]:
    query = select(Alert).where(Alert.acknowledged.is_(False))
    if video_id is not None:
        query = query.where(Alert.video_id == video_id)
    rows = list(db.scalars(query))
    now = datetime.now(timezone.utc)
    for alert in rows:
        alert.acknowledged = True
        alert.acknowledged_at = now
        alert.acknowledged_by = current_user.username
    db.commit()
    if rows:
        bus.publish("alerts_acknowledged", {"count": len(rows), "by": current_user.username})
    return {"acknowledged": len(rows)}


@router.get("/{alert_id}", response_model=AlertRead)
def get_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> AlertRead:
    alert = db.scalar(select(Alert).options(joinedload(Alert.video)).where(Alert.id == alert_id))
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return _serialize(alert)


@router.get("/video/{video_id}/timeline", response_model=list[AlertRead])
def alert_timeline(
    video_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[AlertRead]:
    """Alerts of one clip ordered by playback position, for the video scrubber."""
    if db.get(Video, video_id) is None:
        raise HTTPException(status_code=404, detail="Video not found")
    rows = list(
        db.scalars(
            select(Alert)
            .options(joinedload(Alert.video))
            .where(Alert.video_id == video_id)
            .order_by(Alert.timestamp_sec.asc())
        ).unique()
    )
    return [_serialize(row) for row in rows]
