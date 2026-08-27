"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.security import CREDENTIALS_ERROR, oauth2_scheme, user_from_token


def current_user_from_header_or_query(
    header_token: str | None = Depends(oauth2_scheme),
    token: str | None = Query(default=None, description="JWT for <img>/<video> requests"),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the officer from the Authorization header or a ``token`` query param.

    Browsers cannot attach headers to ``<img>`` / ``<video>`` requests, so media
    endpoints accept the same JWT as a query parameter.
    """
    raw = header_token or token
    if not raw:
        raise CREDENTIALS_ERROR
    return user_from_token(db, raw)
