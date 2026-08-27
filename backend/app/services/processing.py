"""Background video processing service.

A single worker thread consumes queued videos, runs the AI pipeline, persists
detections/alerts and streams progress to connected dashboards through the
event bus.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from app.ai.pipeline import (
    AnalysisSummary,
    FrameOutcome,
    TrackedDetection,
    VideoAnalyzer,
    annotate_frame,
    probe_video,
)
from app.config import get_settings
from app.db import session_scope
from app.events import bus
from app.models import Alert, Detection, DetectionCategory, Video, VideoStatus
from app.services.alert_rules import AlertDraft, AlertEngine
from app.services.settings_service import get_runtime_settings, to_inference_config

logger = logging.getLogger(__name__)
settings = get_settings()

SNAPSHOT_CATEGORIES = {
    DetectionCategory.FACE,
    DetectionCategory.LICENSE_PLATE,
    DetectionCategory.DRONE,
    DetectionCategory.VANDALISM,
    DetectionCategory.WEAPON,
}
PROGRESS_PUBLISH_INTERVAL = 1.0


@dataclass
class JobStats:
    detections: int = 0
    alerts: int = 0


class ProcessingService:
    """Owns the processing queue and the worker thread."""

    def __init__(self) -> None:
        self._queue: queue.Queue[int] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._active_video_id: int | None = None
        self._analyzer: VideoAnalyzer | None = None
        self._analyzer_lock = threading.Lock()

    # --- lifecycle ----------------------------------------------------------
    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="video-processor", daemon=True)
        self._thread.start()
        logger.info("Video processing worker started")

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        self._queue.put(-1)
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    # --- public API ---------------------------------------------------------
    def enqueue(self, video_id: int) -> None:
        with session_scope() as db:
            video = db.get(Video, video_id)
            if video is None:
                raise ValueError(f"Video {video_id} not found")
            video.status = VideoStatus.QUEUED
            video.error_message = None
            video.progress = 0.0
        bus.publish("video_queued", {"video_id": video_id})
        self._queue.put(video_id)

    @property
    def queue_depth(self) -> int:
        return self._queue.qsize()

    @property
    def active_video_id(self) -> int | None:
        return self._active_video_id

    # --- worker -------------------------------------------------------------
    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                video_id = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if video_id < 0:
                break
            try:
                self._process(video_id)
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("Processing video %s failed", video_id)
                self._mark_failed(video_id, str(exc))
            finally:
                self._active_video_id = None
                self._queue.task_done()

    def _analyzer_for(self, config: Any) -> VideoAnalyzer:
        with self._analyzer_lock:
            if self._analyzer is None or self._analyzer.config != config:
                self._analyzer = VideoAnalyzer(config)
            return self._analyzer

    def _process(self, video_id: int) -> None:
        with session_scope() as db:
            video = db.get(Video, video_id)
            if video is None:
                logger.warning("Video %s disappeared before processing", video_id)
                return
            runtime_settings = get_runtime_settings(db)
            source = settings.uploads_dir / video.stored_name
            checkpoint = video.checkpoint
            original_name = video.original_name
            annotated_name = f"{Path(video.stored_name).stem}_annotated.mp4"
            video.status = VideoStatus.PROCESSING
            video.started_at = datetime.now(timezone.utc)
            video.progress = 0.0
            video.frames_analyzed = 0

        if not source.exists():
            raise FileNotFoundError(f"Uploaded file missing on disk: {source.name}")

        self._active_video_id = video_id
        bus.publish("video_started", {"video_id": video_id, "name": original_name})

        config = to_inference_config(runtime_settings)
        analyzer = self._analyzer_for(config)
        analyzer.warmup()
        engine = AlertEngine(runtime_settings, checkpoint)
        annotated_path = settings.processed_dir / annotated_name
        stats = JobStats()
        last_publish = 0.0
        summary: AnalysisSummary | None = None

        # Persist a poster frame so the dashboard can show the clip immediately.
        self._write_thumbnail(video_id, source)

        for item in analyzer.analyze(source, annotated_path=annotated_path):
            if isinstance(item, AnalysisSummary):
                summary = item
                break
            self._handle_frame(video_id, item, engine, stats)
            now = time.monotonic()
            if now - last_publish >= PROGRESS_PUBLISH_INTERVAL:
                last_publish = now
                self._publish_progress(video_id, item, stats)

        with session_scope() as db:
            video = db.get(Video, video_id)
            if video is None:
                return
            video.status = VideoStatus.COMPLETED
            video.progress = 100.0
            video.completed_at = datetime.now(timezone.utc)
            if summary is not None:
                video.frames_analyzed = summary.frames_analyzed
                video.processing_seconds = round(summary.elapsed_seconds, 2)
                video.annotated_name = annotated_name if summary.annotated_path else None
            payload = {
                "video_id": video_id,
                "name": video.original_name,
                "detections": stats.detections,
                "alerts": stats.alerts,
                "frames_analyzed": video.frames_analyzed,
                "processing_seconds": video.processing_seconds,
            }
        bus.publish("video_completed", payload)
        logger.info(
            "Video %s completed: %s detections, %s alerts", video_id, stats.detections, stats.alerts
        )

    # --- persistence helpers ------------------------------------------------
    def _handle_frame(
        self,
        video_id: int,
        outcome: FrameOutcome,
        engine: AlertEngine,
        stats: JobStats,
    ) -> None:
        new_detections = [item for item in outcome.detections if item.is_new]
        crowd_draft = engine.evaluate_crowd(outcome.people_in_frame, outcome.timestamp_sec)
        if not new_detections and crowd_draft is None:
            return

        events: list[tuple[str, dict[str, Any]]] = []
        with session_scope() as db:
            for item in new_detections:
                snapshot_name = self._write_snapshot(video_id, outcome, item)
                row = Detection(
                    video_id=video_id,
                    category=item.raw.category,
                    label=item.raw.label,
                    confidence=round(float(item.raw.confidence), 4),
                    frame_index=item.frame_index,
                    timestamp_sec=round(float(item.timestamp_sec), 3),
                    track_key=item.track_key,
                    x1=round(item.raw.bbox[0], 2),
                    y1=round(item.raw.bbox[1], 2),
                    x2=round(item.raw.bbox[2], 2),
                    y2=round(item.raw.bbox[3], 2),
                    plate_text=item.raw.plate_text,
                    snapshot_name=snapshot_name,
                    meta=item.raw.meta,
                )
                db.add(row)
                db.flush()
                stats.detections += 1
                events.append(
                    (
                        "detection",
                        {
                            "video_id": video_id,
                            "detection_id": row.id,
                            "category": row.category.value,
                            "label": row.label,
                            "confidence": row.confidence,
                            "timestamp_sec": row.timestamp_sec,
                            "plate_text": row.plate_text,
                            "snapshot_name": row.snapshot_name,
                        },
                    )
                )

                draft = engine.evaluate(item)
                if draft is not None:
                    alert = self._create_alert(db, video_id, draft, row.id, snapshot_name)
                    stats.alerts += 1
                    events.append(("alert", self._alert_event(alert)))

            if crowd_draft is not None:
                snapshot_name = self._write_frame_snapshot(video_id, outcome)
                alert = self._create_alert(db, video_id, crowd_draft, None, snapshot_name)
                stats.alerts += 1
                events.append(("alert", self._alert_event(alert)))

        for event_type, payload in events:
            bus.publish(event_type, payload)

    @staticmethod
    def _create_alert(
        db: Any,
        video_id: int,
        draft: AlertDraft,
        detection_id: int | None,
        snapshot_name: str | None,
    ) -> Alert:
        alert = Alert(
            video_id=video_id,
            detection_id=detection_id,
            category=draft.category,
            severity=draft.severity,
            title=draft.title,
            message=draft.message,
            timestamp_sec=round(float(draft.timestamp_sec), 3),
            snapshot_name=snapshot_name,
        )
        db.add(alert)
        db.flush()
        return alert

    @staticmethod
    def _alert_event(alert: Alert) -> dict[str, Any]:
        return {
            "video_id": alert.video_id,
            "alert_id": alert.id,
            "category": alert.category.value,
            "severity": alert.severity.value,
            "title": alert.title,
            "message": alert.message,
            "timestamp_sec": alert.timestamp_sec,
            "snapshot_name": alert.snapshot_name,
        }

    def _publish_progress(self, video_id: int, outcome: FrameOutcome, stats: JobStats) -> None:
        with session_scope() as db:
            video = db.get(Video, video_id)
            if video is not None:
                video.progress = round(outcome.progress, 2)
                video.frames_analyzed = (video.frames_analyzed or 0) + 1
        bus.publish(
            "progress",
            {
                "video_id": video_id,
                "progress": round(outcome.progress, 2),
                "timestamp_sec": round(outcome.timestamp_sec, 2),
                "detections": stats.detections,
                "alerts": stats.alerts,
                "people_in_frame": outcome.people_in_frame,
                "anomaly_score": round(outcome.anomaly_score, 2),
            },
        )

    # --- media helpers ------------------------------------------------------
    def _write_thumbnail(self, video_id: int, source: Path) -> None:
        import cv2

        try:
            meta = probe_video(source)
            capture = cv2.VideoCapture(str(source))
            capture.set(cv2.CAP_PROP_POS_FRAMES, max(0, min(10, meta.frame_count - 1)))
            ok, frame = capture.read()
            capture.release()
            if not ok or frame is None:
                return
            name = f"video_{video_id}_poster.jpg"
            cv2.imwrite(str(settings.thumbnails_dir / name), self._resize(frame, 640))
        except Exception:  # pragma: no cover - thumbnails are best effort
            logger.warning("Could not create thumbnail for video %s", video_id, exc_info=True)
            return
        with session_scope() as db:
            video = db.get(Video, video_id)
            if video is not None:
                video.thumbnail_name = name

    def _write_snapshot(
        self, video_id: int, outcome: FrameOutcome, item: TrackedDetection
    ) -> str | None:
        if item.raw.category not in SNAPSHOT_CATEGORIES:
            return None
        import cv2

        frame = outcome.frame
        height, width = frame.shape[:2]
        x1, y1, x2, y2 = (int(round(v)) for v in item.raw.bbox)
        pad_x = max(12, int((x2 - x1) * 0.25))
        pad_y = max(12, int((y2 - y1) * 0.25))
        x1, y1 = max(0, x1 - pad_x), max(0, y1 - pad_y)
        x2, y2 = min(width, x2 + pad_x), min(height, y2 + pad_y)
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return None
        name = f"det_{video_id}_{item.frame_index}_{item.track_key}.jpg"
        cv2.imwrite(str(settings.thumbnails_dir / name), self._resize(crop, 480))
        return name

    def _write_frame_snapshot(self, video_id: int, outcome: FrameOutcome) -> str | None:
        import cv2

        name = f"frame_{video_id}_{outcome.frame_index}.jpg"
        annotated = annotate_frame(outcome.frame, outcome.detections)
        cv2.imwrite(str(settings.thumbnails_dir / name), self._resize(annotated, 960))
        return name

    @staticmethod
    def _resize(image: np.ndarray, max_width: int) -> np.ndarray:
        import cv2

        height, width = image.shape[:2]
        if width <= max_width:
            return image
        scale = max_width / width
        return cv2.resize(image, (max_width, max(1, int(height * scale))))

    def _mark_failed(self, video_id: int, message: str) -> None:
        with session_scope() as db:
            video = db.get(Video, video_id)
            if video is not None:
                video.status = VideoStatus.FAILED
                video.error_message = message[:1000]
                video.completed_at = datetime.now(timezone.utc)
        bus.publish("video_failed", {"video_id": video_id, "error": message[:500]})


processing_service = ProcessingService()
