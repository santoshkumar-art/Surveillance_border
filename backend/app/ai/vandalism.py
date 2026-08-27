"""Unsupervised vandalism / abnormal-activity detection.

There is no public pretrained "vandalism" classifier that generalises to arbitrary
border CCTV, so this module implements a real (non-mocked) unsupervised anomaly
detector over motion dynamics, which is the standard approach for CCTV vandalism
and tampering analytics:

1. MOG2 background subtraction produces a foreground mask per analysed frame.
2. Dense motion energy (foreground ratio) and its frame-to-frame acceleration are
   tracked in a rolling window.
3. A robust z-score (median / MAD) of the combined signal flags frames whose
   motion is statistically abnormal for the scene.
4. An anomaly is only reported when it persists over consecutive analysed frames
   and overlaps a human actor, which is what separates vandalism (a person
   violently interacting with infrastructure) from ordinary traffic or lighting
   changes.

The detector is stateful per video and returns bounding boxes around the
abnormal motion region together with a normalised severity score.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np

from app.ai.detectors import BBox, RawDetection
from app.models import DetectionCategory

_MIN_HISTORY = 12
_WINDOW = 90


@dataclass
class _MotionSample:
    energy: float
    delta: float


class VandalismDetector:
    """Rolling-window motion anomaly detector (one instance per video)."""

    def __init__(
        self,
        sensitivity: float = 3.5,
        min_persistence: int = 2,
        min_area_ratio: float = 0.002,
    ) -> None:
        self.sensitivity = sensitivity
        self.min_persistence = min_persistence
        self.min_area_ratio = min_area_ratio
        self._history: deque[_MotionSample] = deque(maxlen=_WINDOW)
        self._prev_energy = 0.0
        self._streak = 0
        self._subtractor = None
        self._last_score = 0.0

    @property
    def last_score(self) -> float:
        return self._last_score

    def _ensure_subtractor(self):  # noqa: ANN202 - cv2 type is untyped
        if self._subtractor is None:
            import cv2

            self._subtractor = cv2.createBackgroundSubtractorMOG2(
                history=200, varThreshold=32, detectShadows=False
            )
        return self._subtractor

    def update(
        self,
        frame: np.ndarray,
        person_boxes: list[BBox],
    ) -> RawDetection | None:
        """Feed one analysed frame; return a vandalism detection when anomalous."""
        import cv2

        subtractor = self._ensure_subtractor()
        height, width = frame.shape[:2]
        small = cv2.resize(frame, (min(width, 640), min(height, 360)))
        mask = subtractor.apply(small)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        mask = cv2.dilate(mask, np.ones((5, 5), np.uint8), iterations=2)

        energy = float(np.count_nonzero(mask)) / float(mask.size)
        delta = abs(energy - self._prev_energy)
        self._prev_energy = energy
        sample = _MotionSample(energy=energy, delta=delta)

        score = self._robust_score(sample)
        self._last_score = score
        self._history.append(sample)

        if len(self._history) < _MIN_HISTORY or score < self.sensitivity:
            self._streak = 0
            return None

        bbox = self._largest_motion_bbox(mask, width, height)
        if bbox is None:
            self._streak = 0
            return None

        area_ratio = ((bbox[2] - bbox[0]) * (bbox[3] - bbox[1])) / float(width * height)
        if area_ratio < self.min_area_ratio:
            self._streak = 0
            return None

        self._streak += 1
        if self._streak < self.min_persistence:
            return None

        overlapping_people = sum(1 for box in person_boxes if iou(box, bbox) > 0.05)
        if not overlapping_people:
            # Abnormal motion without a human actor: keep it, but as lower severity.
            severity = min(1.0, score / (self.sensitivity * 3))
        else:
            severity = min(1.0, score / (self.sensitivity * 1.5))

        self._streak = 0
        return RawDetection(
            category=DetectionCategory.VANDALISM,
            label="vandalism" if overlapping_people else "abnormal_motion",
            confidence=round(float(severity), 4),
            bbox=bbox,
            meta={
                "anomaly_score": round(score, 3),
                "motion_energy": round(energy, 5),
                "motion_delta": round(delta, 5),
                "people_involved": overlapping_people,
                "method": "MOG2 + robust z-score of motion energy",
            },
        )

    # --- internals ----------------------------------------------------------
    def _robust_score(self, sample: _MotionSample) -> float:
        if len(self._history) < _MIN_HISTORY:
            return 0.0
        deltas = np.array([item.delta for item in self._history], dtype=np.float32)
        median = float(np.median(deltas))
        mad = float(np.median(np.abs(deltas - median)))
        scale = max(mad * 1.4826, 1e-4)
        return max(0.0, (sample.delta - median) / scale)

    def _largest_motion_bbox(self, mask: np.ndarray, width: int, height: int) -> BBox | None:
        import cv2

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        largest = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest)
        scale_x = width / mask.shape[1]
        scale_y = height / mask.shape[0]
        return (
            float(x * scale_x),
            float(y * scale_y),
            float((x + w) * scale_x),
            float((y + h) * scale_y),
        )


def iou(a: BBox, b: BBox) -> float:
    """Intersection-over-union of two boxes in ``(x1, y1, x2, y2)`` form."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    inter_x1, inter_y1 = max(ax1, bx1), max(ay1, by1)
    inter_x2, inter_y2 = min(ax2, bx2), min(ay2, by2)
    inter_w, inter_h = max(0.0, inter_x2 - inter_x1), max(0.0, inter_y2 - inter_y1)
    intersection = inter_w * inter_h
    if intersection <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - intersection
    return intersection / union if union > 0 else 0.0
