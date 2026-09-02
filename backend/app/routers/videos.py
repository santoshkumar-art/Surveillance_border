"""Footage upload, listing, playback and re-processing."""

from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.responses import Response

from app.ai.pipeline import probe_video
from app.config import get_settings
from app.db import get_db
from app.deps import current_user_from_header_or_query
from app.models import Alert, AlertSeverity, Detection, User, Video, VideoStatus
from app.routers.media import ranged_file_response, safe_path
from app.schemas import VideoPage, VideoSummary
from app.security import get_current_user
from app.services.processing import processing_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/videos", tags=["videos"])
settings = get_settings()

ALLOWED_SUFFIXES = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".mpg", ".mpeg", ".m4v"}


def _summaries(db: Session, videos: list[Video]) -> list[VideoSummary]:
    ids = [video.id for video in videos]
    if not ids:
        return []
    detection_rows = db.execute(
        select(Detection.video_id, Detection.category, func.count(Detection.id))
        .where(Detection.video_id.in_(ids))
        .group_by(Detection.video_id, Detection.category)
    ).all()
    alert_rows = db.execute(
        select(Alert.video_id, Alert.severity, func.count(Alert.id))
        .where(Alert.video_id.in_(ids))
        .group_by(Alert.video_id, Alert.severity)
    ).all()

    detections: dict[int, dict[str, int]] = {}
    for video_id, category, count in detection_rows:
        detections.setdefault(video_id, {})[category.value] = count
    alerts: dict[int, dict[str, int]] = {}
    for video_id, severity, count in alert_rows:
        alerts.setdefault(video_id, {})[severity.value] = count

    summaries: list[VideoSummary] = []
    for video in videos:
        category_counts = detections.get(video.id, {})
        severity_counts = alerts.get(video.id, {})
        summary = VideoSummary.model_validate(video)
        summary.category_counts = category_counts
        summary.detection_count = sum(category_counts.values())
        summary.alert_count = sum(severity_counts.values())
        summary.critical_alert_count = severity_counts.get(AlertSeverity.CRITICAL.value, 0)
        summaries.append(summary)
    return summaries


def _get_video(db: Session, video_id: int) -> Video:
    video = db.get(Video, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


@router.post("", response_model=VideoSummary, status_code=status.HTTP_201_CREATED)
async def upload_video(
    file: UploadFile = File(..., description="CCTV footage file"),
    checkpoint: str = Form("Unassigned sector"),
    notes: str = Form(""),
    auto_process: bool = Form(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VideoSummary:
    """Store an uploaded clip, extract its metadata and queue it for analysis."""
    original_name = Path(file.filename or "footage.mp4").name
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported video format '{suffix}'. Allowed: {sorted(ALLOWED_SUFFIXES)}",
        )

    stored_name = f"{uuid.uuid4().hex}{suffix}"
    target = settings.uploads_dir / stored_name
    max_bytes = settings.max_upload_mb * 1024 * 1024
    written = 0
    try:
        with target.open("wb") as handle:
            while chunk := await file.read(1 << 20):
                written += len(chunk)
                if written > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds the {settings.max_upload_mb} MB limit",
                    )
                handle.write(chunk)
    except HTTPException:
        target.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    try:
        meta = probe_video(target)
    except ValueError as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{exc}. The file is not a readable video.",
        ) from exc

    video = Video(
        original_name=original_name,
        stored_name=stored_name,
        checkpoint=checkpoint.strip() or "Unassigned sector",
        notes=notes.strip(),
        size_bytes=written,
        duration_sec=round(meta.duration_sec, 2),
        fps=round(meta.fps, 2),
        width=meta.width,
        height=meta.height,
        frame_count=meta.frame_count,
        status=VideoStatus.UPLOADED,
        uploaded_by_id=current_user.id,
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    if auto_process:
        processing_service.enqueue(video.id)
        db.refresh(video)

    return _summaries(db, [video])[0]


@router.get("", response_model=VideoPage)
def list_videos(
    status_filter: VideoStatus | None = Query(default=None, alias="status"),
    search: str | None = None,
    limit: int = 25,
    offset: int = 0,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> VideoPage:
    limit = max(1, min(limit, 100))
    query = select(Video)
    count_query = select(func.count(Video.id))
    if status_filter is not None:
        query = query.where(Video.status == status_filter)
        count_query = count_query.where(Video.status == status_filter)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(Video.original_name.ilike(pattern) | Video.checkpoint.ilike(pattern))
        count_query = count_query.where(
            Video.original_name.ilike(pattern) | Video.checkpoint.ilike(pattern)
        )
    total = db.scalar(count_query) or 0
    videos = list(
        db.scalars(query.order_by(Video.created_at.desc()).limit(limit).offset(offset)).unique()
    )
    return VideoPage(total=total, limit=limit, offset=offset, items=_summaries(db, videos))


@router.get("/{video_id}", response_model=VideoSummary)
def get_video(
    video_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> VideoSummary:
    video = _get_video(db, video_id)
    return _summaries(db, [video])[0]


@router.post("/{video_id}/reprocess", response_model=VideoSummary)
def reprocess_video(
    video_id: int,
    clear_previous: bool = True,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> VideoSummary:
    """Re-run inference, e.g. after tuning thresholds in Settings."""
    video = _get_video(db, video_id)
    if video.status == VideoStatus.PROCESSING:
        raise HTTPException(status_code=409, detail="Video is already being processed")
    if clear_previous:
        for row in list(video.detections):
            db.delete(row)
        for row in list(video.alerts):
            db.delete(row)
        db.commit()
    processing_service.enqueue(video.id)
    db.refresh(video)
    return _summaries(db, [video])[0]


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_video(
    video_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Response:
    video = _get_video(db, video_id)
    if video.status == VideoStatus.PROCESSING:
        raise HTTPException(status_code=409, detail="Cannot delete a video while it is processing")
    snapshots = [row.snapshot_name for row in video.detections if row.snapshot_name] + [
        row.snapshot_name for row in video.alerts if row.snapshot_name
    ]
    for name in set(snapshots):
        (settings.thumbnails_dir / name).unlink(missing_ok=True)
    if video.thumbnail_name:
        (settings.thumbnails_dir / video.thumbnail_name).unlink(missing_ok=True)
    if video.annotated_name:
        (settings.processed_dir / video.annotated_name).unlink(missing_ok=True)
    (settings.uploads_dir / video.stored_name).unlink(missing_ok=True)
    db.delete(video)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{video_id}/stream")
def stream_video(
    video_id: int,
    request: Request,
    annotated: bool = False,
    db: Session = Depends(get_db),
    _user: User = Depends(current_user_from_header_or_query),
) -> Response:
    """Stream the original upload, or the annotated render when ``annotated=true``."""
    video = _get_video(db, video_id)
    if annotated:
        if not video.annotated_name:
            raise HTTPException(status_code=404, detail="Annotated render not available yet")
        path = safe_path(settings.processed_dir, video.annotated_name)
    else:
        path = safe_path(settings.uploads_dir, video.stored_name)
    return ranged_file_response(path, request, media_type="video/mp4")


@router.get("/{video_id}/export")
def export_video_report(
    video_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    """Machine readable case file for a clip (used by the download button)."""
    video = _get_video(db, video_id)
    detections = [
        {
            "id": row.id,
            "category": row.category.value,
            "label": row.label,
            "confidence": row.confidence,
            "timestamp_sec": row.timestamp_sec,
            "plate_text": row.plate_text,
            "bbox": [row.x1, row.y1, row.x2, row.y2],
            "meta": row.meta,
        }
        for row in sorted(video.detections, key=lambda item: item.timestamp_sec)
    ]
    alerts = [
        {
            "id": row.id,
            "severity": row.severity.value,
            "category": row.category.value,
            "title": row.title,
            "message": row.message,
            "timestamp_sec": row.timestamp_sec,
            "acknowledged": row.acknowledged,
        }
        for row in sorted(video.alerts, key=lambda item: item.timestamp_sec)
    ]
    return {
        "video": {
            "id": video.id,
            "name": video.original_name,
            "checkpoint": video.checkpoint,
            "duration_sec": video.duration_sec,
            "resolution": f"{video.width}x{video.height}",
            "status": video.status.value,
            "frames_analyzed": video.frames_analyzed,
            "processing_seconds": video.processing_seconds,
            "uploaded_at": video.created_at.isoformat(),
        },
        "detections": detections,
        "alerts": alerts,
    }


def cleanup_orphan_files() -> int:
    """Remove uploads that no longer have a database row (used on startup)."""
    removed = 0
    from app.db import session_scope

    with session_scope() as db:
        known = {name for (name,) in db.execute(select(Video.stored_name)).all()}
    for path in settings.uploads_dir.glob("*"):
        if path.is_file() and path.name not in known:
            path.unlink(missing_ok=True)
            removed += 1
    return removed


def disk_usage() -> dict[str, float]:
    """Bytes used by each storage area plus free space, in megabytes."""

    def directory_mb(directory: Path) -> float:
        return round(
            sum(item.stat().st_size for item in directory.glob("**/*") if item.is_file()) / 1e6, 2
        )

    usage = shutil.disk_usage(settings.data_dir)
    return {
        "uploads_mb": directory_mb(settings.uploads_dir),
        "processed_mb": directory_mb(settings.processed_dir),
        "snapshots_mb": directory_mb(settings.thumbnails_dir),
        "models_mb": directory_mb(settings.models_dir),
        "disk_free_gb": round(usage.free / 1e9, 2),
        "disk_total_gb": round(usage.total / 1e9, 2),
    }
