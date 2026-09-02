"""Video analysis pipeline: runs every detector over a video file, de-duplicates
detections into tracks and optionally renders an annotated MP4."""

from __future__ import annotations

import logging
import shutil
import subprocess
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from app.ai.detectors import (
    BBox,
    DroneDetector,
    FaceDetector,
    GeneralObjectDetector,
    LicensePlateDetector,
    RawDetection,
)
from app.ai.registry import ModelRegistry
from app.ai.registry import registry as default_registry
from app.ai.vandalism import VandalismDetector, iou
from app.models import DetectionCategory

logger = logging.getLogger(__name__)

CATEGORY_COLORS: dict[DetectionCategory, tuple[int, int, int]] = {
    DetectionCategory.FACE: (255, 255, 255),
    DetectionCategory.PERSON: (0, 210, 255),
    DetectionCategory.VEHICLE: (0, 255, 140),
    DetectionCategory.LICENSE_PLATE: (255, 190, 0),
    DetectionCategory.DRONE: (0, 90, 255),
    DetectionCategory.VANDALISM: (0, 0, 255),
    DetectionCategory.WEAPON: (0, 0, 255),
}


@dataclass
class InferenceConfig:
    frame_stride: int = 5
    detection_confidence: float = 0.35
    face_confidence: float = 0.6
    plate_confidence: float = 0.3
    drone_confidence: float = 0.55
    imgsz: int = 640
    enable_plate_ocr: bool = True
    write_annotated_video: bool = True
    vandalism_sensitivity: float = 3.5
    crowd_threshold: int = 4


@dataclass
class VideoMeta:
    fps: float
    frame_count: int
    width: int
    height: int
    duration_sec: float


@dataclass
class TrackedDetection:
    raw: RawDetection
    frame_index: int
    timestamp_sec: float
    track_key: str
    is_new: bool


@dataclass
class FrameOutcome:
    frame_index: int
    timestamp_sec: float
    progress: float
    frame: np.ndarray
    detections: list[TrackedDetection]
    people_in_frame: int
    anomaly_score: float


@dataclass
class AnalysisSummary:
    frames_analyzed: int
    elapsed_seconds: float
    annotated_path: Path | None = None
    counts: dict[str, int] = field(default_factory=dict)


class _Track:
    __slots__ = ("key", "bbox", "last_frame", "hits", "best_confidence")

    def __init__(self, key: str, bbox: BBox, frame_index: int, confidence: float) -> None:
        self.key = key
        self.bbox = bbox
        self.last_frame = frame_index
        self.hits = 1
        self.best_confidence = confidence


class DetectionTracker:
    """Greedy IoU tracker that collapses the same object across frames into one event."""

    def __init__(self, iou_threshold: float = 0.35, max_gap_frames: int = 45) -> None:
        self.iou_threshold = iou_threshold
        self.max_gap_frames = max_gap_frames
        self._tracks: dict[DetectionCategory, list[_Track]] = {}
        self._counter = 0

    def assign(self, detection: RawDetection, frame_index: int) -> tuple[str, bool]:
        tracks = self._tracks.setdefault(detection.category, [])
        tracks[:] = [t for t in tracks if frame_index - t.last_frame <= self.max_gap_frames]
        best: _Track | None = None
        best_iou = 0.0
        for track in tracks:
            score = iou(track.bbox, detection.bbox)
            if score > best_iou:
                best, best_iou = track, score
        if best is not None and best_iou >= self.iou_threshold:
            best.bbox = detection.bbox
            best.last_frame = frame_index
            best.hits += 1
            best.best_confidence = max(best.best_confidence, detection.confidence)
            return best.key, False
        self._counter += 1
        key = f"{detection.category.value}-{self._counter}"
        tracks.append(_Track(key, detection.bbox, frame_index, detection.confidence))
        return key, True


def transcode_to_h264(path: Path) -> bool:
    """Re-encode an MP4 in place to H.264 so browsers can play it.

    OpenCV's bundled FFmpeg has no H.264 encoder, so renders are written with the
    MPEG-4 Part 2 (``mp4v``) fourcc, which Chrome and Safari refuse to decode. When
    the ``ffmpeg`` binary is available the file is converted with faststart for
    progressive playback; otherwise the original render is kept.
    """
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        logger.warning("ffmpeg not found; annotated render stays MPEG-4 Part 2 (%s)", path.name)
        return False

    target = path.with_name(f"{path.stem}.h264{path.suffix}")
    command = [
        ffmpeg,
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(path),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "26",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-an",
        str(target),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, timeout=900)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        logger.warning("H.264 transcode failed for %s: %s", path.name, exc)
        target.unlink(missing_ok=True)
        return False

    target.replace(path)
    return True


def probe_video(path: Path) -> VideoMeta:
    """Read container metadata without decoding the whole file."""
    import cv2

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError(f"Unable to open video file: {path.name}")
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    capture.release()
    if width <= 0 or height <= 0:
        raise ValueError(f"{path.name} does not contain a readable video stream")
    fps = fps if fps > 0 else 25.0
    duration = frame_count / fps if frame_count > 0 else 0.0
    return VideoMeta(
        fps=fps, frame_count=frame_count, width=width, height=height, duration_sec=duration
    )


def annotate_frame(frame: np.ndarray, detections: list[TrackedDetection]) -> np.ndarray:
    """Draw labelled boxes for every detection on a copy of the frame."""
    import cv2

    canvas = frame.copy()
    for item in detections:
        raw = item.raw
        color = CATEGORY_COLORS.get(raw.category, (255, 255, 255))
        x1, y1, x2, y2 = (int(round(v)) for v in raw.bbox)
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)
        text = raw.plate_text or raw.label
        caption = f"{text} {raw.confidence * 100:.0f}%"
        (tw, th), _ = cv2.getTextSize(caption, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(canvas, (x1, max(0, y1 - th - 8)), (x1 + tw + 8, y1), color, -1)
        cv2.putText(
            canvas,
            caption,
            (x1 + 4, max(10, y1 - 5)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 0),
            1,
            cv2.LINE_AA,
        )
    return canvas


class VideoAnalyzer:
    """Runs the full detector ensemble over a video file."""

    def __init__(
        self,
        config: InferenceConfig | None = None,
        registry: ModelRegistry | None = None,
    ) -> None:
        self.config = config or InferenceConfig()
        self.registry = registry or default_registry
        self.general = GeneralObjectDetector(self.registry, imgsz=self.config.imgsz)
        self.faces = FaceDetector(self.registry)
        self.plates = LicensePlateDetector(
            self.registry, imgsz=self.config.imgsz, enable_ocr=self.config.enable_plate_ocr
        )
        self.drones = DroneDetector(self.registry, imgsz=self.config.imgsz)

    def warmup(self) -> None:
        """Load every model so the first frame is not penalised."""
        self.registry.yolo("general")
        self.registry.yolo("plate")
        self.registry.yolo("drone")
        self.registry.face_detector()

    def analyze(
        self,
        video_path: Path,
        annotated_path: Path | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> Iterator[FrameOutcome | AnalysisSummary]:
        """Yield a :class:`FrameOutcome` per analysed frame, then an :class:`AnalysisSummary`."""
        import cv2

        meta = probe_video(video_path)
        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            raise ValueError(f"Unable to open video file: {video_path.name}")

        writer = None
        write_annotated = bool(annotated_path) and self.config.write_annotated_video
        if write_annotated and annotated_path is not None:
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            out_fps = max(1.0, meta.fps / self.config.frame_stride)
            writer = cv2.VideoWriter(
                str(annotated_path), fourcc, out_fps, (meta.width, meta.height)
            )
            if not writer.isOpened():
                logger.warning("Could not open annotated video writer for %s", annotated_path)
                writer = None

        tracker = DetectionTracker(max_gap_frames=max(15, self.config.frame_stride * 6))
        vandalism = VandalismDetector(sensitivity=self.config.vandalism_sensitivity)
        counts: dict[str, int] = {}
        frames_analyzed = 0
        frame_index = -1
        started = time.perf_counter()

        try:
            while True:
                grabbed = capture.grab()
                if not grabbed:
                    break
                frame_index += 1
                if frame_index % self.config.frame_stride:
                    continue
                ok, frame = capture.retrieve()
                if not ok or frame is None:
                    continue
                if should_cancel is not None and should_cancel():
                    break

                raw_detections = self._detect_frame(frame)
                person_boxes = [
                    d.bbox for d in raw_detections if d.category == DetectionCategory.PERSON
                ]
                anomaly = vandalism.update(frame, person_boxes)
                if anomaly is not None:
                    raw_detections.append(anomaly)

                tracked: list[TrackedDetection] = []
                for raw in raw_detections:
                    track_key, is_new = tracker.assign(raw, frame_index)
                    if is_new:
                        counts[raw.category.value] = counts.get(raw.category.value, 0) + 1
                    tracked.append(
                        TrackedDetection(
                            raw=raw,
                            frame_index=frame_index,
                            timestamp_sec=frame_index / meta.fps,
                            track_key=track_key,
                            is_new=is_new,
                        )
                    )

                frames_analyzed += 1
                if writer is not None:
                    writer.write(annotate_frame(frame, tracked))

                progress = (
                    min(100.0, (frame_index + 1) / meta.frame_count * 100.0)
                    if meta.frame_count > 0
                    else 0.0
                )
                yield FrameOutcome(
                    frame_index=frame_index,
                    timestamp_sec=frame_index / meta.fps,
                    progress=progress,
                    frame=frame,
                    detections=tracked,
                    people_in_frame=len(person_boxes),
                    anomaly_score=vandalism.last_score,
                )
        finally:
            capture.release()
            if writer is not None:
                writer.release()
                if annotated_path is not None:
                    transcode_to_h264(annotated_path)

        yield AnalysisSummary(
            frames_analyzed=frames_analyzed,
            elapsed_seconds=time.perf_counter() - started,
            annotated_path=annotated_path if writer is not None else None,
            counts=counts,
        )

    def _detect_frame(self, frame: np.ndarray) -> list[RawDetection]:
        detections: list[RawDetection] = []
        detections.extend(self.general.detect(frame, self.config.detection_confidence))
        detections.extend(self.faces.detect(frame, self.config.face_confidence))
        detections.extend(self.plates.detect(frame, self.config.plate_confidence))
        detections.extend(self.drones.detect(frame, self.config.drone_confidence))
        return detections
