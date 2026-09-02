"""API level tests for auth, uploads, detections, alerts and settings."""

from __future__ import annotations

import cv2
import numpy as np
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import session_scope
from app.models import Alert, AlertSeverity, Detection, DetectionCategory, Video, VideoStatus


def _make_video(path: str, frames: int = 12, size: tuple[int, int] = (160, 120)) -> None:
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 10.0, size)
    rng = np.random.default_rng(0)
    for _ in range(frames):
        writer.write(rng.integers(0, 255, (size[1], size[0], 3), dtype=np.uint8))
    writer.release()


def _seed_video(status: VideoStatus = VideoStatus.COMPLETED) -> int:
    with session_scope() as db:
        video = Video(
            original_name="checkpoint.mp4",
            stored_name="stored.mp4",
            checkpoint="Sector 7",
            size_bytes=1024,
            duration_sec=10.0,
            fps=10.0,
            width=160,
            height=120,
            frame_count=100,
            status=status,
            progress=100.0,
            frames_analyzed=10,
            processing_seconds=2.0,
        )
        db.add(video)
        db.flush()
        db.add_all(
            [
                Detection(
                    video_id=video.id,
                    category=DetectionCategory.LICENSE_PLATE,
                    label="License_Plate",
                    confidence=0.81,
                    frame_index=5,
                    timestamp_sec=0.5,
                    track_key="plate-1",
                    x1=1.0,
                    y1=2.0,
                    x2=30.0,
                    y2=20.0,
                    plate_text="KA01AB1234",
                ),
                Detection(
                    video_id=video.id,
                    category=DetectionCategory.DRONE,
                    label="dji_mavic",
                    confidence=0.72,
                    frame_index=8,
                    timestamp_sec=0.8,
                    track_key="drone-1",
                    x1=5.0,
                    y1=5.0,
                    x2=40.0,
                    y2=25.0,
                ),
            ]
        )
        db.add(
            Alert(
                video_id=video.id,
                category=DetectionCategory.DRONE,
                severity=AlertSeverity.CRITICAL,
                title="Drone intrusion detected",
                message="Aerial intrusion at Sector 7",
                timestamp_sec=0.8,
            )
        )
        return video.id


def test_login_rejects_bad_password(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login", json={"username": "officer", "password": "wrong-password"}
    )
    assert response.status_code == 401


def test_protected_route_requires_token(client: TestClient) -> None:
    assert client.get("/api/detections").status_code in (401, 403)


def test_me_returns_profile(client: TestClient, auth: dict[str, str]) -> None:
    body = client.get("/api/auth/me", headers=auth).json()
    assert body["username"] == "officer"


def test_upload_rejects_unsupported_extension(client: TestClient, auth: dict[str, str]) -> None:
    response = client.post(
        "/api/videos",
        headers=auth,
        files={"file": ("notes.txt", b"not a video", "text/plain")},
    )
    assert response.status_code == 415
    assert "Unsupported" in response.json()["detail"]


def test_upload_accepts_video_and_creates_row(
    client: TestClient, auth: dict[str, str], tmp_path_factory: object
) -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        path = f"{directory}/clip.mp4"
        _make_video(path)
        with open(path, "rb") as handle:
            response = client.post(
                "/api/videos",
                headers=auth,
                files={"file": ("clip.mp4", handle, "video/mp4")},
                data={"checkpoint": "Gate 1", "auto_process": "false"},
            )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["checkpoint"] == "Gate 1"
    assert body["width"] == 160
    assert body["status"] == "uploaded"


def test_detection_filters_and_categories(client: TestClient, auth: dict[str, str]) -> None:
    video_id = _seed_video()
    page = client.get(f"/api/detections?video_id={video_id}", headers=auth).json()
    assert page["total"] == 2

    drones = client.get(f"/api/detections?video_id={video_id}&category=drone", headers=auth).json()
    assert [item["label"] for item in drones["items"]] == ["dji_mavic"]

    plates = client.get("/api/detections?search=KA01", headers=auth).json()
    assert plates["total"] == 1

    high_confidence = client.get("/api/detections?min_confidence=0.8", headers=auth).json()
    assert high_confidence["total"] == 1

    categories = client.get(f"/api/detections/categories?video_id={video_id}", headers=auth).json()
    assert categories == {"license_plate": 1, "drone": 1}


def test_alert_acknowledgement_flow(client: TestClient, auth: dict[str, str]) -> None:
    _seed_video()
    alerts = client.get("/api/alerts?acknowledged=false", headers=auth).json()
    assert alerts["total"] == 1
    alert_id = alerts["items"][0]["id"]
    assert alerts["items"][0]["severity"] == "critical"
    assert alerts["items"][0]["checkpoint"] == "Sector 7"

    acknowledged = client.post(f"/api/alerts/{alert_id}/acknowledge", headers=auth).json()
    assert acknowledged["acknowledged"] is True
    assert acknowledged["acknowledged_by"] == "officer"
    assert client.get("/api/alerts?acknowledged=false", headers=auth).json()["total"] == 0

    assert client.post("/api/alerts/999999/acknowledge", headers=auth).status_code == 404


def test_acknowledge_all(client: TestClient, auth: dict[str, str]) -> None:
    _seed_video()
    _seed_video()
    result = client.post("/api/alerts/acknowledge-all", headers=auth).json()
    assert result["acknowledged"] == 2


def test_dashboard_and_analytics(client: TestClient, auth: dict[str, str]) -> None:
    _seed_video()
    stats = client.get("/api/analytics/dashboard", headers=auth).json()
    assert stats["videos_completed"] == 1
    assert stats["detections_total"] == 2
    assert stats["alerts_critical"] == 1
    assert stats["detections_by_category"]["drone"] == 1

    analytics = client.get("/api/analytics?days=3", headers=auth).json()
    assert len(analytics["detections_per_day"]) == 3
    assert analytics["recent_plates"][0]["plate"] == "KA01AB1234"
    assert analytics["processing_throughput"]["frames_analyzed"] == 10.0


def test_settings_round_trip(client: TestClient, auth: dict[str, str]) -> None:
    current = client.get("/api/settings", headers=auth).json()
    updated = dict(current)
    updated["detection_confidence"] = 0.61
    updated["alert_on_face"] = not current["alert_on_face"]
    response = client.put("/api/settings", headers=auth, json=updated)
    assert response.status_code == 200
    assert response.json()["detection_confidence"] == 0.61
    assert client.get("/api/settings", headers=auth).json()["detection_confidence"] == 0.61

    client.put("/api/settings", headers=auth, json=current)


def test_settings_validation_rejects_out_of_range(client: TestClient, auth: dict[str, str]) -> None:
    payload = client.get("/api/settings", headers=auth).json()
    payload["detection_confidence"] = 5.0
    assert client.put("/api/settings", headers=auth, json=payload).status_code == 422


def test_system_status_reports_models(client: TestClient, auth: dict[str, str]) -> None:
    body = client.get("/api/system/status", headers=auth).json()
    assert body["status"] == "operational"
    assert {model["key"] for model in body["models"]} >= {"general", "drone", "plate", "face"}


def test_video_delete_removes_children(client: TestClient, auth: dict[str, str]) -> None:
    video_id = _seed_video()
    assert client.delete(f"/api/videos/{video_id}", headers=auth).status_code == 204
    with session_scope() as db:
        assert db.scalar(select(Video).where(Video.id == video_id)) is None
        assert db.scalars(select(Detection)).first() is None
        assert db.scalars(select(Alert)).first() is None


def test_video_list_filters_by_status_query(client: TestClient, auth: dict[str, str]) -> None:
    completed_id = _seed_video(VideoStatus.COMPLETED)
    failed_id = _seed_video(VideoStatus.FAILED)

    completed = client.get("/api/videos", headers=auth, params={"status": "completed"}).json()
    assert [item["id"] for item in completed["items"]] == [completed_id]

    failed = client.get("/api/videos", headers=auth, params={"status": "failed"}).json()
    assert [item["id"] for item in failed["items"]] == [failed_id]

    assert client.get("/api/videos", headers=auth).json()["total"] == 2


def test_health_endpoint_is_public(client: TestClient) -> None:
    assert client.get("/api/health").json()["status"] == "ok"
