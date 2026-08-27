"""Aggregated dashboard statistics and analytics."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Alert, AlertSeverity, Detection, User, Video, VideoStatus
from app.schemas import AnalyticsResponse, DashboardStats, TimeseriesPoint
from app.security import get_current_user

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _category_counts(db: Session) -> dict[str, int]:
    rows = db.execute(
        select(Detection.category, func.count(Detection.id)).group_by(Detection.category)
    ).all()
    return {category.value: count for category, count in rows}


def _severity_counts(db: Session) -> dict[str, int]:
    rows = db.execute(select(Alert.severity, func.count(Alert.id)).group_by(Alert.severity)).all()
    return {severity.value: count for severity, count in rows}


@router.get("/dashboard", response_model=DashboardStats)
def dashboard_stats(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> DashboardStats:
    status_rows = dict(
        db.execute(select(Video.status, func.count(Video.id)).group_by(Video.status)).all()
    )
    total_seconds = db.scalar(select(func.coalesce(func.sum(Video.duration_sec), 0.0))) or 0.0
    return DashboardStats(
        videos_total=sum(status_rows.values()),
        videos_processing=status_rows.get(VideoStatus.PROCESSING, 0)
        + status_rows.get(VideoStatus.QUEUED, 0),
        videos_completed=status_rows.get(VideoStatus.COMPLETED, 0),
        videos_failed=status_rows.get(VideoStatus.FAILED, 0),
        detections_total=db.scalar(select(func.count(Detection.id))) or 0,
        alerts_total=db.scalar(select(func.count(Alert.id))) or 0,
        alerts_unacknowledged=db.scalar(
            select(func.count(Alert.id)).where(Alert.acknowledged.is_(False))
        )
        or 0,
        alerts_critical=db.scalar(
            select(func.count(Alert.id)).where(Alert.severity == AlertSeverity.CRITICAL)
        )
        or 0,
        footage_hours=round(total_seconds / 3600, 2),
        detections_by_category=_category_counts(db),
        alerts_by_severity=_severity_counts(db),
    )


@router.get("", response_model=AnalyticsResponse)
def analytics(
    days: int = Query(default=14, ge=1, le=90),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> AnalyticsResponse:
    since = datetime.now(timezone.utc) - timedelta(days=days)

    detection_rows = dict(
        db.execute(
            select(func.date(Detection.created_at), func.count(Detection.id))
            .where(Detection.created_at >= since)
            .group_by(func.date(Detection.created_at))
        ).all()
    )
    alert_rows = dict(
        db.execute(
            select(func.date(Alert.created_at), func.count(Alert.id))
            .where(Alert.created_at >= since)
            .group_by(func.date(Alert.created_at))
        ).all()
    )

    series: list[TimeseriesPoint] = []
    for offset in range(days - 1, -1, -1):
        day = (datetime.now(timezone.utc) - timedelta(days=offset)).date().isoformat()
        series.append(
            TimeseriesPoint(
                bucket=day,
                detections=int(detection_rows.get(day, 0)),
                alerts=int(alert_rows.get(day, 0)),
            )
        )

    checkpoint_rows = db.execute(
        select(
            Video.checkpoint,
            func.count(func.distinct(Video.id)),
            func.count(Alert.id),
        )
        .join(Alert, Alert.video_id == Video.id, isouter=True)
        .group_by(Video.checkpoint)
        .order_by(func.count(Alert.id).desc())
        .limit(8)
    ).all()

    plate_rows = db.execute(
        select(Detection.plate_text, Detection.timestamp_sec, Detection.video_id, Detection.id)
        .where(Detection.plate_text.is_not(None))
        .order_by(Detection.id.desc())
        .limit(12)
    ).all()

    processed = db.execute(
        select(
            func.coalesce(func.sum(Video.processing_seconds), 0.0),
            func.coalesce(func.sum(Video.frames_analyzed), 0),
            func.coalesce(func.sum(Video.duration_sec), 0.0),
        ).where(Video.status == VideoStatus.COMPLETED)
    ).one()
    total_processing, total_frames, total_duration = (
        float(processed[0]),
        int(processed[1]),
        float(processed[2]),
    )

    return AnalyticsResponse(
        detections_by_category=_category_counts(db),
        alerts_by_severity=_severity_counts(db),
        detections_per_day=series,
        top_checkpoints=[
            {"checkpoint": checkpoint, "videos": videos, "alerts": alerts}
            for checkpoint, videos, alerts in checkpoint_rows
        ],
        recent_plates=[
            {
                "plate": plate,
                "timestamp_sec": round(float(timestamp), 2),
                "video_id": video_id,
                "detection_id": detection_id,
            }
            for plate, timestamp, video_id, detection_id in plate_rows
        ],
        processing_throughput={
            "frames_analyzed": float(total_frames),
            "processing_seconds": round(total_processing, 2),
            "footage_seconds": round(total_duration, 2),
            "frames_per_second": round(total_frames / total_processing, 2)
            if total_processing > 0
            else 0.0,
            "realtime_factor": round(total_duration / total_processing, 2)
            if total_processing > 0
            else 0.0,
        },
    )
