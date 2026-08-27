"""Range-capable media serving for footage, annotated renders and snapshots."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, StreamingResponse
from starlette.responses import Response

from app.config import get_settings
from app.deps import current_user_from_header_or_query
from app.models import User

router = APIRouter(prefix="/api/media", tags=["media"])
settings = get_settings()

RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")
CHUNK_SIZE = 1 << 20
SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def safe_path(directory: Path, name: str) -> Path:
    if not SAFE_NAME_RE.match(name):
        raise HTTPException(status_code=400, detail="Invalid file name")
    candidate = (directory / name).resolve()
    if directory.resolve() not in candidate.parents:
        raise HTTPException(status_code=400, detail="Invalid file path")
    if not candidate.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return candidate


def _iter_file(path: Path, start: int, end: int) -> Iterator[bytes]:
    remaining = end - start + 1
    with path.open("rb") as handle:
        handle.seek(start)
        while remaining > 0:
            chunk = handle.read(min(CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def ranged_file_response(path: Path, request: Request, media_type: str) -> Response:
    """Serve a file honouring HTTP Range requests so the player can seek."""
    file_size = path.stat().st_size
    range_header = request.headers.get("range")
    if not range_header:
        return FileResponse(
            path,
            media_type=media_type,
            headers={"Accept-Ranges": "bytes", "Cache-Control": "private, max-age=60"},
        )
    match = RANGE_RE.fullmatch(range_header.strip())
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            detail="Malformed Range header",
        )
    raw_start, raw_end = match.groups()
    start = int(raw_start) if raw_start else 0
    end = int(raw_end) if raw_end else file_size - 1
    end = min(end, file_size - 1)
    if start > end:
        raise HTTPException(
            status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
            detail="Requested range not satisfiable",
        )
    return StreamingResponse(
        _iter_file(path, start, end),
        status_code=status.HTTP_206_PARTIAL_CONTENT,
        media_type=media_type,
        headers={
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(end - start + 1),
            "Accept-Ranges": "bytes",
        },
    )


@router.get("/snapshots/{name}")
def get_snapshot(
    name: str,
    _user: User = Depends(current_user_from_header_or_query),
) -> Response:
    path = safe_path(settings.thumbnails_dir, name)
    return FileResponse(
        path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"}
    )
