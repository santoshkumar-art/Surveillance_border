"""Model registry: declares the real pretrained weights used by the platform,
downloads them on demand and lazily loads them into memory.

All weights are public, pretrained checkpoints:

* ``general``  - Ultralytics YOLOv8n trained on COCO (people, vehicles, bags ...).
* ``drone``    - YOLOv8 fine-tuned on a UAV/drone dataset (single ``drone`` class).
* ``plate``    - YOLOv11n fine-tuned on the Roboflow license-plate dataset.
* ``face``     - OpenCV Zoo YuNet face detector (ONNX).
* ``ocr``      - EasyOCR (CRAFT detector + english_g2 recogniser) for plate text.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_DOWNLOAD_CHUNK = 1 << 20


@dataclass(frozen=True)
class ModelSpec:
    key: str
    name: str
    task: str
    filename: str
    url: str
    source: str
    min_bytes: int = 100_000


MODEL_SPECS: dict[str, ModelSpec] = {
    "general": ModelSpec(
        key="general",
        name="YOLOv8n - COCO",
        task="People, vehicles and object detection",
        filename="yolov8n.pt",
        url="https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt",
        source="ultralytics/assets",
    ),
    "drone": ModelSpec(
        key="drone",
        name="YOLOv8n - UAV/Drone",
        task="Aerial drone intrusion detection",
        filename="drone_yolov8.pt",
        url="https://huggingface.co/Tuzelkhan/drone-yolov8/resolve/main/best.pt",
        source="huggingface: Tuzelkhan/drone-yolov8",
    ),
    "plate": ModelSpec(
        key="plate",
        name="YOLOv11n - License plate",
        task="Vehicle number plate localisation",
        filename="license_plate_yolov11n.pt",
        url=(
            "https://huggingface.co/morsetechlab/yolov11-license-plate-detection"
            "/resolve/main/license-plate-finetune-v1n.pt"
        ),
        source="huggingface: morsetechlab/yolov11-license-plate-detection",
    ),
    "face": ModelSpec(
        key="face",
        name="YuNet 2023mar",
        task="Face detection",
        filename="face_detection_yunet_2023mar.onnx",
        url=(
            "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models"
            "/face_detection_yunet/face_detection_yunet_2023mar.onnx"
        ),
        source="opencv/opencv_zoo",
        min_bytes=50_000,
    ),
}


@dataclass
class LoadState:
    loaded: bool = False
    error: str | None = None
    obj: Any = field(default=None, repr=False)


class ModelRegistry:
    """Thread-safe lazy loader for the detection models."""

    def __init__(self, models_dir: Path | None = None) -> None:
        self.models_dir = models_dir or settings.models_dir
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._states: dict[str, LoadState] = {key: LoadState() for key in MODEL_SPECS}
        self._ocr_state = LoadState()

    # --- weights ------------------------------------------------------------
    def weights_path(self, key: str) -> Path:
        return self.models_dir / MODEL_SPECS[key].filename

    def is_downloaded(self, key: str) -> bool:
        path = self.weights_path(key)
        return path.exists() and path.stat().st_size >= MODEL_SPECS[key].min_bytes

    def download(self, key: str, force: bool = False) -> Path:
        """Download the checkpoint if it is missing. Returns the local path."""
        import requests

        spec = MODEL_SPECS[key]
        target = self.weights_path(key)
        if self.is_downloaded(key) and not force:
            return target

        tmp = target.with_suffix(target.suffix + ".part")
        logger.info("Downloading %s from %s", spec.name, spec.url)
        with requests.get(spec.url, stream=True, timeout=120) as response:
            response.raise_for_status()
            with tmp.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=_DOWNLOAD_CHUNK):
                    handle.write(chunk)
        if tmp.stat().st_size < spec.min_bytes:
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"Downloaded file for {spec.key} is too small to be valid weights")
        tmp.replace(target)
        logger.info("Saved %s (%.1f MB)", target.name, target.stat().st_size / 1e6)
        return target

    def download_all(self, force: bool = False) -> dict[str, Path]:
        return {key: self.download(key, force=force) for key in MODEL_SPECS}

    # --- loading ------------------------------------------------------------
    def yolo(self, key: str) -> Any:
        """Return a loaded Ultralytics YOLO model for ``general``/``drone``/``plate``."""
        with self._lock:
            state = self._states[key]
            if state.loaded and state.obj is not None:
                return state.obj
            try:
                from ultralytics import YOLO

                path = self.download(key)
                model = YOLO(str(path))
                state.obj = model
                state.loaded = True
                state.error = None
            except Exception as exc:  # pragma: no cover - depends on network/hardware
                state.error = str(exc)
                state.loaded = False
                logger.exception("Failed to load model %s", key)
                raise
            return state.obj

    def face_detector(self, input_size: tuple[int, int] = (320, 320)) -> Any:
        """Return an OpenCV YuNet face detector."""
        with self._lock:
            state = self._states["face"]
            if state.loaded and state.obj is not None:
                return state.obj
            try:
                import cv2

                path = self.download("face")
                detector = cv2.FaceDetectorYN.create(
                    model=str(path),
                    config="",
                    input_size=input_size,
                    score_threshold=settings.face_confidence,
                    nms_threshold=0.3,
                    top_k=5000,
                )
                state.obj = detector
                state.loaded = True
                state.error = None
            except Exception as exc:  # pragma: no cover
                state.error = str(exc)
                state.loaded = False
                logger.exception("Failed to load YuNet face detector")
                raise
            return state.obj

    def ocr(self) -> Any:
        """Return an EasyOCR reader used to read license plate crops."""
        with self._lock:
            if self._ocr_state.loaded and self._ocr_state.obj is not None:
                return self._ocr_state.obj
            try:
                import easyocr

                reader = easyocr.Reader(
                    ["en"],
                    gpu=False,
                    model_storage_directory=str(self.models_dir / "easyocr"),
                    download_enabled=True,
                    verbose=False,
                )
                self._ocr_state.obj = reader
                self._ocr_state.loaded = True
                self._ocr_state.error = None
            except Exception as exc:  # pragma: no cover
                self._ocr_state.error = str(exc)
                self._ocr_state.loaded = False
                logger.exception("Failed to initialise EasyOCR")
                raise
            return self._ocr_state.obj

    # --- introspection ------------------------------------------------------
    def status(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for key, spec in MODEL_SPECS.items():
            path = self.weights_path(key)
            exists = self.is_downloaded(key)
            rows.append(
                {
                    "key": key,
                    "name": spec.name,
                    "task": spec.task,
                    "loaded": self._states[key].loaded,
                    "available": exists,
                    "weights_path": str(path) if exists else None,
                    "weights_mb": round(path.stat().st_size / 1e6, 2) if exists else None,
                    "source": spec.source,
                    "error": self._states[key].error,
                }
            )
        rows.append(
            {
                "key": "ocr",
                "name": "EasyOCR english_g2",
                "task": "Number plate text recognition",
                "loaded": self._ocr_state.loaded,
                "available": settings.enable_plate_ocr,
                "weights_path": str(self.models_dir / "easyocr"),
                "weights_mb": None,
                "source": "JaidedAI/EasyOCR",
                "error": self._ocr_state.error,
            }
        )
        return rows


registry = ModelRegistry()
