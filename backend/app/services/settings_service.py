"""Operator-editable runtime settings persisted in the database."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.ai.pipeline import InferenceConfig
from app.config import get_settings
from app.models import AppSetting

SETTINGS_KEY = "detection"

settings = get_settings()


def default_settings() -> dict[str, Any]:
    """Defaults come from the environment configuration."""
    return {
        "frame_stride": settings.frame_stride,
        "detection_confidence": settings.detection_confidence,
        "face_confidence": settings.face_confidence,
        "plate_confidence": settings.plate_confidence,
        "drone_confidence": settings.drone_confidence,
        "enable_plate_ocr": settings.enable_plate_ocr,
        "write_annotated_video": settings.write_annotated_video,
        "alert_on_face": True,
        "alert_on_vehicle": True,
        "alert_on_plate": True,
        "alert_on_drone": True,
        "alert_on_vandalism": True,
        "crowd_threshold": 4,
        "vandalism_sensitivity": 3.5,
    }


def get_runtime_settings(db: Session) -> dict[str, Any]:
    row = db.get(AppSetting, SETTINGS_KEY)
    merged = default_settings()
    if row is not None and isinstance(row.value, dict):
        merged.update(row.value)
    return merged


def update_runtime_settings(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    row = db.get(AppSetting, SETTINGS_KEY)
    merged = get_runtime_settings(db)
    merged.update(payload)
    if row is None:
        db.add(AppSetting(key=SETTINGS_KEY, value=merged))
    else:
        row.value = merged
    db.commit()
    return merged


def to_inference_config(values: dict[str, Any]) -> InferenceConfig:
    return InferenceConfig(
        frame_stride=int(values["frame_stride"]),
        detection_confidence=float(values["detection_confidence"]),
        face_confidence=float(values["face_confidence"]),
        plate_confidence=float(values["plate_confidence"]),
        drone_confidence=float(values["drone_confidence"]),
        imgsz=settings.inference_image_size,
        enable_plate_ocr=bool(values["enable_plate_ocr"]),
        write_annotated_video=bool(values["write_annotated_video"]),
        vandalism_sensitivity=float(values["vandalism_sensitivity"]),
        crowd_threshold=int(values["crowd_threshold"]),
    )
