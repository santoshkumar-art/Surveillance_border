"""FastAPI application entry point."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import get_settings
from app.db import init_db, session_scope
from app.events import bus
from app.models import User, Video, VideoStatus
from app.routers import alerts, analytics, auth, detections, media, system, videos, ws
from app.security import hash_password
from app.services.processing import processing_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s :: %(message)s",
)
logger = logging.getLogger("app")
settings = get_settings()


def bootstrap_admin() -> None:
    """Create the initial officer account if the user table is empty."""
    with session_scope() as db:
        if db.scalar(select(User).limit(1)) is not None:
            return
        db.add(
            User(
                username=settings.admin_username,
                full_name=settings.admin_full_name,
                role="commander",
                password_hash=hash_password(settings.admin_password),
            )
        )
    logger.info("Created bootstrap officer account '%s'", settings.admin_username)


def requeue_interrupted_jobs() -> None:
    """Videos left mid-processing by a restart are queued again."""
    with session_scope() as db:
        stale = list(
            db.scalars(
                select(Video).where(Video.status.in_([VideoStatus.PROCESSING, VideoStatus.QUEUED]))
            ).unique()
        )
        ids = [video.id for video in stale]
        for video in stale:
            video.status = VideoStatus.UPLOADED
    for video_id in ids:
        processing_service.enqueue(video_id)
    if ids:
        logger.info("Re-queued %s interrupted job(s)", len(ids))


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings.ensure_directories()
    init_db()
    bootstrap_admin()
    bus.bind_loop(asyncio.get_running_loop())
    processing_service.start()
    requeue_interrupted_jobs()
    logger.info("Border Security Surveillance backend ready")
    try:
        yield
    finally:
        processing_service.stop()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Border Security Surveillance System",
        description=(
            "AI-powered analysis of border CCTV footage: people & faces, vehicles & "
            "number plates, drones and vandalism, with real-time operator alerts."
        ),
        version=system.VERSION,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for module in (auth, videos, detections, alerts, analytics, system, media, ws):
        app.include_router(module.router)

    @app.get("/api/health", tags=["system"])
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "version": system.VERSION,
            "queue_depth": processing_service.queue_depth or 0,
            "active_job": processing_service.active_video_id,
            "websocket_clients": bus.subscriber_count,
        }

    return app


app = create_app()
