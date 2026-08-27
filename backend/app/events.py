"""In-process publish/subscribe bus used to stream live events to dashboards."""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import Any

logger = logging.getLogger(__name__)

MAX_QUEUE = 500
REPLAY_SIZE = 50


class EventBus:
    """Fan-out bus bridging the background worker thread and WebSocket clients."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._recent: deque[dict[str, Any]] = deque(maxlen=REPLAY_SIZE)

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Remember the API event loop so worker threads can publish safely."""
        self._loop = loop

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=MAX_QUEUE)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers.discard(queue)

    @property
    def recent(self) -> list[dict[str, Any]]:
        return list(self._recent)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        """Publish from any thread."""
        event = {"type": event_type, **payload}
        if event_type in {"detection", "alert", "video_completed", "video_failed"}:
            self._recent.append(event)
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        try:
            loop.call_soon_threadsafe(self._dispatch, event)
        except RuntimeError:  # pragma: no cover - loop shutting down
            logger.debug("Event loop unavailable, dropping %s event", event_type)

    def _dispatch(self, event: dict[str, Any]) -> None:
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("Dropping event for a slow websocket subscriber")


bus = EventBus()
