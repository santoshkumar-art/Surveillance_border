"""Rule engine turning detections into operator alerts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.ai.pipeline import TrackedDetection
from app.models import AlertSeverity, DetectionCategory

# Minimum seconds of footage between two alerts of the same category, so a busy
# scene cannot flood the operations feed.
COOLDOWN_SECONDS: dict[DetectionCategory, float] = {
    DetectionCategory.FACE: 4.0,
    DetectionCategory.PERSON: 6.0,
    DetectionCategory.VEHICLE: 4.0,
    DetectionCategory.LICENSE_PLATE: 2.0,
    DetectionCategory.DRONE: 2.0,
    DetectionCategory.VANDALISM: 3.0,
    DetectionCategory.WEAPON: 0.0,
}


@dataclass
class AlertDraft:
    category: DetectionCategory
    severity: AlertSeverity
    title: str
    message: str
    timestamp_sec: float


class AlertEngine:
    """Stateful per-video engine (tracks cooldowns and crowd conditions)."""

    def __init__(self, config: dict[str, Any], checkpoint: str) -> None:
        self.config = config
        self.checkpoint = checkpoint
        self._last_alert_at: dict[DetectionCategory, float] = {}
        self._crowd_alerted_until = -1.0

    # --- helpers ------------------------------------------------------------
    def _allowed(self, category: DetectionCategory, timestamp: float) -> bool:
        cooldown = COOLDOWN_SECONDS.get(category, 3.0)
        last = self._last_alert_at.get(category)
        if last is not None and timestamp - last < cooldown:
            return False
        self._last_alert_at[category] = timestamp
        return True

    def _enabled(self, category: DetectionCategory) -> bool:
        flags = {
            DetectionCategory.FACE: "alert_on_face",
            DetectionCategory.VEHICLE: "alert_on_vehicle",
            DetectionCategory.LICENSE_PLATE: "alert_on_plate",
            DetectionCategory.DRONE: "alert_on_drone",
            DetectionCategory.VANDALISM: "alert_on_vandalism",
        }
        key = flags.get(category)
        return True if key is None else bool(self.config.get(key, True))

    # --- rules --------------------------------------------------------------
    def evaluate(self, detection: TrackedDetection) -> AlertDraft | None:
        raw = detection.raw
        category = raw.category
        if not self._enabled(category) or category == DetectionCategory.PERSON:
            return None

        timestamp = detection.timestamp_sec
        at = f"{timestamp:.1f}s"
        location = self.checkpoint

        if category == DetectionCategory.DRONE:
            if not self._allowed(category, timestamp):
                return None
            return AlertDraft(
                category=category,
                severity=AlertSeverity.CRITICAL,
                title=f"Aerial intrusion: {raw.label.replace('_', ' ').upper()}",
                message=(
                    f"Unmanned aerial vehicle ({raw.label}) detected over {location} at {at} "
                    f"with {raw.confidence * 100:.0f}% confidence. Activate air-space protocol."
                ),
                timestamp_sec=timestamp,
            )

        if category == DetectionCategory.WEAPON:
            if not self._allowed(category, timestamp):
                return None
            return AlertDraft(
                category=category,
                severity=AlertSeverity.CRITICAL,
                title=f"Possible weapon detected ({raw.label})",
                message=(
                    f"Object classified as '{raw.label}' carried by a subject at {location}, {at}. "
                    "Immediate verification required."
                ),
                timestamp_sec=timestamp,
            )

        if category == DetectionCategory.VANDALISM:
            if not self._allowed(category, timestamp):
                return None
            people = int(raw.meta.get("people_involved", 0))
            severity = AlertSeverity.CRITICAL if people else AlertSeverity.HIGH
            title = (
                "Vandalism / infrastructure tampering"
                if people
                else "Abnormal motion in restricted zone"
            )
            return AlertDraft(
                category=category,
                severity=severity,
                title=title,
                message=(
                    f"Anomalous activity at {location}, {at} "
                    f"(anomaly score {raw.meta.get('anomaly_score')}, "
                    f"{people} subject(s) involved). "
                    "Dispatch patrol to inspect fencing and equipment."
                ),
                timestamp_sec=timestamp,
            )

        if category == DetectionCategory.LICENSE_PLATE:
            if not self._allowed(category, timestamp):
                return None
            plate = raw.plate_text
            return AlertDraft(
                category=category,
                severity=AlertSeverity.MEDIUM,
                title=f"Number plate captured: {plate}" if plate else "Number plate captured",
                message=(
                    f"Vehicle number plate {'read as ' + plate if plate else 'localised'} "
                    f"at {location}, {at}. Cross-check against the watchlist."
                ),
                timestamp_sec=timestamp,
            )

        if category == DetectionCategory.VEHICLE:
            if not self._allowed(category, timestamp):
                return None
            return AlertDraft(
                category=category,
                severity=AlertSeverity.LOW,
                title=f"Vehicle approach: {raw.label}",
                message=(
                    f"A {raw.label} entered the monitored corridor at {location}, {at} "
                    f"({raw.confidence * 100:.0f}% confidence)."
                ),
                timestamp_sec=timestamp,
            )

        if category == DetectionCategory.FACE:
            if not self._allowed(category, timestamp):
                return None
            return AlertDraft(
                category=category,
                severity=AlertSeverity.MEDIUM,
                title="Unidentified individual detected",
                message=(
                    f"Human face captured at {location}, {at} "
                    f"({raw.confidence * 100:.0f}% confidence). Snapshot stored for identification."
                ),
                timestamp_sec=timestamp,
            )

        return None

    def evaluate_crowd(self, people_in_frame: int, timestamp: float) -> AlertDraft | None:
        """Raise a single alert while an abnormally large group is in frame."""
        threshold = int(self.config.get("crowd_threshold", 4))
        if people_in_frame < threshold or timestamp < self._crowd_alerted_until:
            return None
        self._crowd_alerted_until = timestamp + 10.0
        return AlertDraft(
            category=DetectionCategory.PERSON,
            severity=AlertSeverity.HIGH,
            title=f"Group movement: {people_in_frame} people in frame",
            message=(
                f"{people_in_frame} individuals detected simultaneously at {self.checkpoint}, "
                f"{timestamp:.1f}s (threshold {threshold}). Possible illegal mass crossing."
            ),
            timestamp_sec=timestamp,
        )
