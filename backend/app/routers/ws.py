"""WebSocket endpoint streaming live detections, alerts and progress."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from app.db import SessionLocal
from app.events import bus
from app.security import user_from_token

logger = logging.getLogger(__name__)
router = APIRouter(tags=["realtime"])

HEARTBEAT_SECONDS = 20.0


@router.websocket("/api/ws")
async def realtime_feed(websocket: WebSocket, token: str = Query(default="")) -> None:
    db = SessionLocal()
    try:
        user = user_from_token(db, token)
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    finally:
        db.close()

    await websocket.accept()
    queue = bus.subscribe()
    await websocket.send_json({"type": "connected", "user": user.username})
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "heartbeat"})
                continue
            await websocket.send_json(event)
    except WebSocketDisconnect:
        logger.debug("WebSocket client disconnected: %s", user.username)
    except Exception:  # pragma: no cover - network errors
        logger.debug("WebSocket stream ended unexpectedly", exc_info=True)
    finally:
        bus.unsubscribe(queue)
