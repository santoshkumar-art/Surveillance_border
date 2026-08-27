"""Pydantic request/response models for the public API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models import AlertSeverity, DetectionCategory, VideoStatus


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead


class LoginRequest(BaseModel):
    username: str
    password: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str
    role: str
    last_login_at: datetime | None = None


class VideoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    original_name: str
    checkpoint: str
    notes: str
    size_bytes: int
    duration_sec: float
    fps: float
    width: int
    height: int
    frame_count: int
    status: VideoStatus
    progress: float
    frames_analyzed: int
    error_message: str | None
    processing_seconds: float
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    thumbnail_name: str | None
    annotated_name: str | None


class VideoSummary(VideoRead):
    detection_count: int = 0
    alert_count: int = 0
    critical_alert_count: int = 0
    category_counts: dict[str, int] = Field(default_factory=dict)


class DetectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    video_id: int
    category: DetectionCategory
    label: str
    confidence: float
    frame_index: int
    timestamp_sec: float
    x1: float
    y1: float
    x2: float
    y2: float
    plate_text: str | None
    snapshot_name: str | None
    meta: dict[str, Any]
    created_at: datetime


class AlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    video_id: int
    detection_id: int | None
    category: DetectionCategory
    severity: AlertSeverity
    title: str
    message: str
    timestamp_sec: float
    snapshot_name: str | None
    acknowledged: bool
    acknowledged_at: datetime | None
    acknowledged_by: str | None
    created_at: datetime
    video_name: str | None = None
    checkpoint: str | None = None


class AlertAcknowledgeRequest(BaseModel):
    acknowledged: bool = True


class Paginated(BaseModel):
    total: int
    limit: int
    offset: int


class DetectionPage(Paginated):
    items: list[DetectionRead]


class AlertPage(Paginated):
    items: list[AlertRead]


class VideoPage(Paginated):
    items: list[VideoSummary]


class DashboardStats(BaseModel):
    videos_total: int
    videos_processing: int
    videos_completed: int
    videos_failed: int
    detections_total: int
    alerts_total: int
    alerts_unacknowledged: int
    alerts_critical: int
    footage_hours: float
    detections_by_category: dict[str, int]
    alerts_by_severity: dict[str, int]


class TimeseriesPoint(BaseModel):
    bucket: str
    detections: int
    alerts: int


class AnalyticsResponse(BaseModel):
    detections_by_category: dict[str, int]
    alerts_by_severity: dict[str, int]
    detections_per_day: list[TimeseriesPoint]
    top_checkpoints: list[dict[str, Any]]
    recent_plates: list[dict[str, Any]]
    processing_throughput: dict[str, float]


class ModelStatus(BaseModel):
    key: str
    name: str
    task: str
    loaded: bool
    available: bool
    weights_path: str | None
    weights_mb: float | None
    source: str
    error: str | None = None


class SystemStatus(BaseModel):
    status: str
    version: str
    uptime_seconds: float
    device: str
    torch_version: str
    opencv_version: str
    cpu_percent: float
    memory_percent: float
    disk_free_gb: float
    queue_depth: int
    active_job: int | None
    models: list[ModelStatus]
    storage: dict[str, float]


class SettingsPayload(BaseModel):
    frame_stride: int = Field(ge=1, le=120)
    detection_confidence: float = Field(ge=0.01, le=0.99)
    face_confidence: float = Field(ge=0.01, le=0.99)
    plate_confidence: float = Field(ge=0.01, le=0.99)
    drone_confidence: float = Field(ge=0.01, le=0.99)
    enable_plate_ocr: bool
    write_annotated_video: bool
    alert_on_face: bool
    alert_on_vehicle: bool
    alert_on_plate: bool
    alert_on_drone: bool
    alert_on_vandalism: bool
    crowd_threshold: int = Field(ge=2, le=100)
    vandalism_sensitivity: float = Field(ge=0.5, le=10.0)


TokenResponse.model_rebuild()
