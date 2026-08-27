"""Frame level detectors wrapping the pretrained models in the registry."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from app.ai.registry import ModelRegistry
from app.ai.registry import registry as default_registry
from app.models import DetectionCategory

logger = logging.getLogger(__name__)

BBox = tuple[float, float, float, float]

# COCO label -> platform category
VEHICLE_LABELS = {"car", "motorcycle", "bus", "truck", "train", "bicycle"}
WEAPON_LABELS = {"knife", "baseball bat", "scissors"}
PLATE_TEXT_RE = re.compile(r"[^A-Z0-9]")


@dataclass
class RawDetection:
    category: DetectionCategory
    label: str
    confidence: float
    bbox: BBox
    plate_text: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


def _clip_bbox(bbox: BBox, width: int, height: int) -> BBox:
    x1, y1, x2, y2 = bbox
    x1 = float(max(0.0, min(x1, width - 1)))
    y1 = float(max(0.0, min(y1, height - 1)))
    x2 = float(max(0.0, min(x2, width - 1)))
    y2 = float(max(0.0, min(y2, height - 1)))
    return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))


def _yolo_detections(result: Any, names: dict[int, str]) -> list[tuple[str, float, BBox]]:
    out: list[tuple[str, float, BBox]] = []
    boxes = getattr(result, "boxes", None)
    if boxes is None or boxes.xyxy is None:
        return out
    xyxy = boxes.xyxy.cpu().numpy()
    confs = boxes.conf.cpu().numpy()
    classes = boxes.cls.cpu().numpy().astype(int)
    for (x1, y1, x2, y2), conf, cls in zip(xyxy, confs, classes, strict=False):
        label = names.get(int(cls), str(cls))
        out.append((label, float(conf), (float(x1), float(y1), float(x2), float(y2))))
    return out


class GeneralObjectDetector:
    """YOLOv8n/COCO detector used for people, vehicles and hand-carried weapons."""

    def __init__(self, registry: ModelRegistry | None = None, imgsz: int = 640) -> None:
        self.registry = registry or default_registry
        self.imgsz = imgsz

    def detect(self, frame: np.ndarray, confidence: float) -> list[RawDetection]:
        model = self.registry.yolo("general")
        result = model.predict(frame, conf=confidence, imgsz=self.imgsz, verbose=False)[0]
        height, width = frame.shape[:2]
        detections: list[RawDetection] = []
        for label, conf, bbox in _yolo_detections(result, model.names):
            if label == "person":
                category = DetectionCategory.PERSON
            elif label in VEHICLE_LABELS:
                category = DetectionCategory.VEHICLE
            elif label in WEAPON_LABELS:
                category = DetectionCategory.WEAPON
            else:
                continue
            detections.append(
                RawDetection(
                    category=category,
                    label=label,
                    confidence=conf,
                    bbox=_clip_bbox(bbox, width, height),
                )
            )
        return detections


class FaceDetector:
    """OpenCV YuNet face detector."""

    def __init__(self, registry: ModelRegistry | None = None) -> None:
        self.registry = registry or default_registry
        self._input_size: tuple[int, int] | None = None

    def detect(self, frame: np.ndarray, confidence: float) -> list[RawDetection]:
        detector = self.registry.face_detector()
        height, width = frame.shape[:2]
        if self._input_size != (width, height):
            detector.setInputSize((width, height))
            self._input_size = (width, height)
        detector.setScoreThreshold(float(confidence))
        _, faces = detector.detect(frame)
        if faces is None:
            return []
        detections: list[RawDetection] = []
        for face in faces:
            x, y, w, h = face[:4]
            score = float(face[-1])
            box = (float(x), float(y), float(x + w), float(y + h))
            detections.append(
                RawDetection(
                    category=DetectionCategory.FACE,
                    label="face",
                    confidence=score,
                    bbox=_clip_bbox(box, width, height),
                    meta={"landmarks": [float(v) for v in face[4:14]]},
                )
            )
        return detections


class LicensePlateDetector:
    """YOLOv11n plate localiser with optional EasyOCR text recognition."""

    def __init__(
        self,
        registry: ModelRegistry | None = None,
        imgsz: int = 640,
        enable_ocr: bool = True,
    ) -> None:
        self.registry = registry or default_registry
        self.imgsz = imgsz
        self.enable_ocr = enable_ocr
        self._ocr_failed = False

    def detect(self, frame: np.ndarray, confidence: float) -> list[RawDetection]:
        model = self.registry.yolo("plate")
        result = model.predict(frame, conf=confidence, imgsz=self.imgsz, verbose=False)[0]
        height, width = frame.shape[:2]
        detections: list[RawDetection] = []
        for _label, conf, bbox in _yolo_detections(result, model.names):
            clipped = _clip_bbox(bbox, width, height)
            text = self._read_plate(frame, clipped) if self.enable_ocr else None
            detections.append(
                RawDetection(
                    category=DetectionCategory.LICENSE_PLATE,
                    label="license_plate",
                    confidence=conf,
                    bbox=clipped,
                    plate_text=text,
                    meta={"ocr": bool(text)},
                )
            )
        return detections

    def _read_plate(self, frame: np.ndarray, bbox: BBox) -> str | None:
        if self._ocr_failed:
            return None
        x1, y1, x2, y2 = (int(round(v)) for v in bbox)
        if x2 - x1 < 12 or y2 - y1 < 6:
            return None
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return None
        try:
            import cv2

            reader = self.registry.ocr()
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
            results = reader.readtext(
                gray,
                allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
                detail=1,
            )
        except Exception as exc:  # pragma: no cover - OCR weights unavailable
            logger.warning("Plate OCR disabled after failure: %s", exc)
            self._ocr_failed = True
            return None
        best_text = ""
        best_score = 0.0
        for _box, text, score in results:
            cleaned = PLATE_TEXT_RE.sub("", str(text).upper())
            if len(cleaned) >= 4 and float(score) > best_score:
                best_text, best_score = cleaned, float(score)
        return best_text or None


class DroneDetector:
    """YOLOv8 model fine-tuned on UAV imagery (Shahed, MQ-9, DJI Mavic, ...)."""

    def __init__(self, registry: ModelRegistry | None = None, imgsz: int = 640) -> None:
        self.registry = registry or default_registry
        self.imgsz = imgsz

    def detect(self, frame: np.ndarray, confidence: float) -> list[RawDetection]:
        model = self.registry.yolo("drone")
        result = model.predict(frame, conf=confidence, imgsz=self.imgsz, verbose=False)[0]
        height, width = frame.shape[:2]
        return [
            RawDetection(
                category=DetectionCategory.DRONE,
                label=label,
                confidence=conf,
                bbox=_clip_bbox(bbox, width, height),
                meta={"airframe": label},
            )
            for label, conf, bbox in _yolo_detections(result, model.names)
        ]
