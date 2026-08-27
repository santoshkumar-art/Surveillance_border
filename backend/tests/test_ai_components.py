"""Unit tests for the AI helpers that do not require model weights."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from app.ai.detectors import BBox, RawDetection
from app.ai.pipeline import DetectionTracker, TrackedDetection, annotate_frame, probe_video
from app.ai.vandalism import VandalismDetector, iou
from app.models import DetectionCategory
from app.services.alert_rules import AlertEngine
from app.services.settings_service import default_settings, to_inference_config


def _raw(
    category: DetectionCategory, label: str, bbox: BBox, confidence: float = 0.9
) -> RawDetection:
    return RawDetection(category=category, label=label, confidence=confidence, bbox=bbox)


def _tracked(raw: RawDetection, timestamp: float = 1.0, frame_index: int = 10) -> TrackedDetection:
    return TrackedDetection(
        raw=raw,
        frame_index=frame_index,
        timestamp_sec=timestamp,
        track_key=f"{raw.category.value}-1",
        is_new=True,
    )


def test_iou_bounds() -> None:
    assert iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0
    assert iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0
    assert 0.1 < iou((0, 0, 10, 10), (5, 0, 15, 10)) < 0.5


def test_tracker_reuses_track_for_overlapping_boxes() -> None:
    tracker = DetectionTracker(iou_threshold=0.3)
    first_key, first_new = tracker.assign(
        _raw(DetectionCategory.PERSON, "person", (0, 0, 10, 20)), 0
    )
    second_key, second_new = tracker.assign(
        _raw(DetectionCategory.PERSON, "person", (1, 1, 11, 21)), 1
    )
    assert first_key == second_key
    assert first_new is True
    assert second_new is False


def test_tracker_separates_distant_boxes() -> None:
    tracker = DetectionTracker(iou_threshold=0.3)
    first_key, _ = tracker.assign(_raw(DetectionCategory.PERSON, "person", (0, 0, 10, 20)), 0)
    second_key, second_new = tracker.assign(
        _raw(DetectionCategory.PERSON, "person", (200, 200, 260, 280)), 0
    )
    assert first_key != second_key
    assert second_new is True


def test_tracker_expires_stale_tracks() -> None:
    tracker = DetectionTracker(iou_threshold=0.3, max_gap_frames=5)
    box = (0, 0, 10, 20)
    first_key, _ = tracker.assign(_raw(DetectionCategory.VEHICLE, "car", box), 0)
    later_key, later_new = tracker.assign(_raw(DetectionCategory.VEHICLE, "car", box), 100)
    assert later_key != first_key
    assert later_new is True


def test_annotate_frame_draws_without_mutating_input() -> None:
    frame = np.zeros((120, 160, 3), dtype=np.uint8)
    annotated = annotate_frame(
        frame, [_tracked(_raw(DetectionCategory.DRONE, "dji_mavic", (10, 30, 60, 80)))]
    )
    assert annotated.shape == frame.shape
    assert annotated.any(), "expected drawn overlay"
    assert not frame.any(), "input frame must not be modified"


def test_vandalism_detector_ignores_static_scene() -> None:
    detector = VandalismDetector()
    static_frame = np.full((120, 160, 3), 90, dtype=np.uint8)
    results = [detector.update(static_frame.copy(), []) for _ in range(60)]
    assert all(result is None for result in results)


def test_vandalism_detector_flags_sudden_violent_motion() -> None:
    detector = VandalismDetector(sensitivity=3.0, min_persistence=1)
    rng = np.random.default_rng(1)
    base = np.full((160, 240, 3), 80, dtype=np.uint8)
    for _ in range(40):
        detector.update(base.copy(), [])

    flagged = None
    for step in range(20):
        chaotic = base.copy()
        noise = rng.integers(0, 255, (160, 240, 3), dtype=np.uint8)
        bottom = 30 + (step + 1) * 6
        chaotic[20:bottom, 30:210] = noise[20:bottom, 30:210]
        result = detector.update(chaotic, [])
        if result is not None:
            flagged = result
            break
    assert flagged is not None
    assert flagged.category is DetectionCategory.VANDALISM
    assert flagged.confidence > 0.0


def test_probe_video_reads_metadata(tmp_path: Path) -> None:
    path = tmp_path / "probe.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 15.0, (160, 120))
    for _ in range(20):
        writer.write(np.zeros((120, 160, 3), dtype=np.uint8))
    writer.release()

    meta = probe_video(path)
    assert (meta.width, meta.height) == (160, 120)
    assert meta.fps > 0
    assert meta.duration_sec > 0


def test_probe_video_rejects_non_video(tmp_path: Path) -> None:
    path = tmp_path / "broken.mp4"
    path.write_bytes(b"definitely not a video")
    try:
        probe_video(path)
    except ValueError:
        return
    raise AssertionError("expected ValueError for unreadable video")


def test_alert_engine_rules_and_cooldown() -> None:
    engine = AlertEngine(default_settings(), "Sector 7")

    drone = engine.evaluate(_tracked(_raw(DetectionCategory.DRONE, "shahed_136", (0, 0, 20, 20))))
    assert drone is not None
    assert drone.severity.value == "critical"
    assert "Sector 7" in drone.message

    # A second drone detection inside the cooldown window is suppressed.
    assert (
        engine.evaluate(
            _tracked(_raw(DetectionCategory.DRONE, "shahed_136", (0, 0, 20, 20)), timestamp=1.2)
        )
        is None
    )

    plate = engine.evaluate(
        _tracked(_raw(DetectionCategory.LICENSE_PLATE, "License_Plate", (0, 0, 20, 20)))
    )
    assert plate is not None
    assert plate.severity.value == "medium"

    # People alone never raise an alert; crowds are handled separately.
    assert engine.evaluate(_tracked(_raw(DetectionCategory.PERSON, "person", (0, 0, 5, 5)))) is None


def test_alert_engine_respects_disabled_categories() -> None:
    values = default_settings()
    values["alert_on_vehicle"] = False
    engine = AlertEngine(values, "Gate 1")
    assert engine.evaluate(_tracked(_raw(DetectionCategory.VEHICLE, "car", (0, 0, 20, 20)))) is None


def test_settings_to_inference_config_maps_thresholds() -> None:
    values = default_settings()
    values["detection_confidence"] = 0.4
    values["drone_confidence"] = 0.7
    values["frame_stride"] = 9
    config = to_inference_config(values)
    assert config.detection_confidence == 0.4
    assert config.drone_confidence == 0.7
    assert config.frame_stride == 9
