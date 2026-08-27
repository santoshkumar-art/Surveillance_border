"""System health, model status and runtime settings."""

from __future__ import annotations

import platform
import time

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.ai.registry import registry
from app.config import get_settings
from app.db import get_db
from app.models import User
from app.routers.videos import disk_usage
from app.schemas import ModelStatus, SettingsPayload, SystemStatus
from app.security import get_current_user
from app.services.processing import processing_service
from app.services.settings_service import get_runtime_settings, update_runtime_settings

router = APIRouter(prefix="/api", tags=["system"])
settings = get_settings()

VERSION = "1.0.0"
_STARTED_AT = time.time()


@router.get("/system/status", response_model=SystemStatus)
def system_status(_user: User = Depends(get_current_user)) -> SystemStatus:
    import cv2
    import psutil
    import torch

    storage = disk_usage()
    return SystemStatus(
        status="operational",
        version=VERSION,
        uptime_seconds=round(time.time() - _STARTED_AT, 1),
        device="cuda" if torch.cuda.is_available() else f"cpu ({platform.machine()})",
        torch_version=torch.__version__,
        opencv_version=cv2.__version__,
        cpu_percent=psutil.cpu_percent(interval=0.1),
        memory_percent=psutil.virtual_memory().percent,
        disk_free_gb=storage["disk_free_gb"],
        queue_depth=processing_service.queue_depth or 0,
        active_job=processing_service.active_video_id,
        models=[ModelStatus(**row) for row in registry.status()],
        storage=storage,
    )


@router.post("/system/models/download", response_model=dict[str, str])
def download_models(
    background_tasks: BackgroundTasks,
    force: bool = False,
    _user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Fetch any missing weights in the background."""
    background_tasks.add_task(registry.download_all, force)
    return {"status": "started"}


@router.get("/settings", response_model=SettingsPayload)
def read_settings(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> SettingsPayload:
    return SettingsPayload(**get_runtime_settings(db))


@router.put("/settings", response_model=SettingsPayload)
def write_settings(
    payload: SettingsPayload,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> SettingsPayload:
    merged = update_runtime_settings(db, payload.model_dump())
    return SettingsPayload(**merged)
