"""Shared pytest fixtures: isolated database, storage and an authenticated client."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator

import pytest

# Environment must be configured before the application modules read settings.
_TMP_DIR = tempfile.mkdtemp(prefix="bss-tests-")
os.environ["BSS_DATA_DIR"] = os.path.join(_TMP_DIR, "data")
os.environ["BSS_MODELS_DIR"] = os.path.join(_TMP_DIR, "models")
os.environ["BSS_DATABASE_URL"] = f"sqlite:///{os.path.join(_TMP_DIR, 'test.db')}"
os.environ["BSS_SECRET_KEY"] = "test-secret"
os.environ["BSS_ADMIN_USERNAME"] = "officer"
os.environ["BSS_ADMIN_PASSWORD"] = "test-password"

from fastapi.testclient import TestClient  # noqa: E402

from app.db import engine, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services.processing import processing_service  # noqa: E402

TEST_PASSWORD = "test-password"

init_db()


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    """API client with the background worker disabled for deterministic tests."""
    processing_service.start = lambda: None  # type: ignore[method-assign]
    processing_service.stop = lambda timeout=5.0: None  # type: ignore[method-assign]
    processing_service.enqueue = lambda video_id: None  # type: ignore[method-assign]
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/login", json={"username": "officer", "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture(autouse=True)
def clean_tables() -> Iterator[None]:
    """Remove operational rows between tests, keeping the bootstrap user."""
    yield
    from app.models import Alert, Detection, Video

    with engine.begin() as connection:
        for table in (Alert.__table__, Detection.__table__, Video.__table__):
            connection.execute(table.delete())
