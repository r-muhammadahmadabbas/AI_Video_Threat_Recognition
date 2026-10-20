"""Unified frame inference used by every detection path.

Both the live-camera worker and the upload ``/detect`` pipeline run their
models through :class:`FrameAnalyzer`. One place decides which models run, how
often each of them runs, and how their raw outputs are shaped. Accuracy work
(threshold sweeps, evaluation harnesses) then measures a single code path
instead of two divergent ones.

Model cadence is counted in *frames visited by the analyzer*, never wall-clock
time, so replaying the same clip produces identical model calls every run -
the same determinism rule the tracker and rules already follow.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import numpy as np
from ultralytics import YOLO

from workers.cv_worker.detector import Detection, YOLO26Detector
from workers.cv_worker.weapon_detector import WeaponDetection, WeaponDetector

#: ``models/`` sits at the backend root, independent of the process cwd.
BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODELS_DIR = BACKEND_ROOT / "models"


class PersonModel(Protocol):
    """Anything that turns a frame into person detections."""

    def detect(self, frame: np.ndarray) -> list[Detection]: ...


class WeaponModel(Protocol):
    """Anything that turns a frame into weapon detections with temporal state."""

    def detect(self, frame: np.ndarray) -> list[WeaponDetection]: ...

    def reset(self) -> None: ...


#: Pose runner: frame -> ``(N, 17, 2)`` keypoints, or ``None`` when undetected.
PoseRunner = Callable[[np.ndarray], "np.ndarray | None"]
#: Violence runner: frame -> whether the frame shows violence.
ViolenceRunner = Callable[[np.ndarray], bool]
#: Fall runner: frame -> detections of people in a fallen posture.
FallRunner = Callable[[np.ndarray], list[Detection]]


@dataclass(frozen=True)
class AnalyzerConfig:
    """Which models run for one camera or one uploaded clip.

    ``*_interval`` values are frame cadences: weapon detection defaults to
    every analyzed frame, pose to every 30th, violence to every 15th, because
    those models are far heavier than the person detector.
    """

    person_model: str = "yolo26n"
    person_confidence: float = 0.25
    person_iou: float = 0.45
    person_classes: tuple[int, ...] | None = (0,)
    device: str = "cpu"

    weapon_enabled: bool = False
    weapon_model_path: str = str(DEFAULT_MODELS_DIR / "model" / "best.pt")
    weapon_confidence: float = 0.25
    weapon_interval: int = 1

    pose_enabled: bool = False
    pose_model_path: str = str(DEFAULT_MODELS_DIR / "pose" / "yolo26s-pose.pt")
    pose_confidence: float = 0.25
    pose_interval: int = 30

    fall_enabled: bool = False
    fall_model_path: str = str(DEFAULT_MODELS_DIR / "fall" / "best.pt")
    fall_confidence: float = 0.40
    fall_class_ids: tuple[int, ...] = (0,)
    fall_interval: int = 1

    violence_enabled: bool = False
    violence_model_path: str = str(DEFAULT_MODELS_DIR / "violence" / "best.pt")
    violence_confidence: float = 0.35
    violence_class_ids: tuple[int, ...] = (0,)
    violence_positive_labels: tuple[str, ...] = (
        "violence",
        "violent",
        "fight",
        "fighting",
    )
    violence_interval: int = 15


@dataclass
class FrameAnalysis:
    """Raw per-frame model outputs, before tracking or rules see them."""

    persons: list[Detection] = field(default_factory=list)
    weapons: list[WeaponDetection] = field(default_factory=list)
    falls: list[Detection] = field(default_factory=list)
    violence: bool = False
    pose_keypoints: np.ndarray | None = None


class FrameAnalyzer:
    """Runs the configured model suite over frames of one source.

    One instance belongs to exactly one source: the weapon model carries
    temporal voting state and the cadence counters are per-stream.
    """

    def __init__(
        self,
        config: AnalyzerConfig | None = None,
        *,
        person_model: PersonModel | None = None,
        weapon_model: WeaponModel | None = None,
        pose_runner: PoseRunner | None = None,
        fall_runner: FallRunner | None = None,
        violence_runner: ViolenceRunner | None = None,
    ) -> None:
        """Build an analyzer.

        The ``*_model``/``*_runner`` arguments exist so tests (and the
        evaluation harness) can drive the analyzer with fakes; production
        callers pass only a config and get the real models.
        """
        self._config = config or AnalyzerConfig()
        self._frame_index = 0

        self._person_model: PersonModel = person_model or YOLO26Detector(
            model_name=self._config.person_model,
            confidence=self._config.person_confidence,
            iou=self._config.person_iou,
            device=self._config.device,
            classes=(
                list(self._config.person_classes)
                if self._config.person_classes is not None
                else None
            ),
        )

        if weapon_model is not None:
            self._weapon_model: WeaponModel | None = weapon_model
        elif self._config.weapon_enabled:
            self._weapon_model = WeaponDetector(
                model_path=self._config.weapon_model_path,
                confidence=self._config.weapon_confidence,
                device=self._config.device,
            )
        else:
            self._weapon_model = None

        self._pose_runner = pose_runner or (
            _build_pose_runner(
                self._config.pose_model_path,
                self._config.pose_confidence,
                self._config.device,
            )
            if self._config.pose_enabled
            else None
        )
        self._fall_runner = fall_runner or (
            _build_fall_runner(
                self._config.fall_model_path,
                self._config.fall_confidence,
                self._config.fall_class_ids,
                self._config.device,
            )
            if self._config.fall_enabled
            else None
        )
        self._violence_runner = violence_runner or (
            _build_violence_runner(
                self._config.violence_model_path,
                self._config.violence_confidence,
                self._config.violence_class_ids,
                self._config.violence_positive_labels,
                self._config.device,
            )
            if self._config.violence_enabled
            else None
        )

    def analyze(self, frame: np.ndarray) -> FrameAnalysis:
        """Run every due model for this frame and collect their outputs."""
        index = self._frame_index
        analysis = FrameAnalysis(persons=self._person_model.detect(frame))

        if self._weapon_model is not None and self._due(index, self._config.weapon_interval):
            analysis.weapons = [
                detection
                for detection in self._weapon_model.detect(frame)
                if detection.is_threat
            ]

        if self._pose_runner is not None and self._due(index, self._config.pose_interval):
            analysis.pose_keypoints = self._pose_runner(frame)

        if self._fall_runner is not None and self._due(index, self._config.fall_interval):
            analysis.falls = self._fall_runner(frame)

        if self._violence_runner is not None and self._due(
            index, self._config.violence_interval
        ):
            analysis.violence = self._violence_runner(frame)

        self._frame_index += 1
        return analysis

    def reset(self) -> None:
        """Clear per-source temporal state so the analyzer can be reused."""
        self._frame_index = 0
        if self._weapon_model is not None:
            self._weapon_model.reset()

    @staticmethod
    def _due(index: int, interval: int) -> bool:
        return interval <= 1 or index % interval == 0


def _build_pose_runner(model_path: str, confidence: float, device: str) -> PoseRunner:
    """Load a pose model once and return the per-frame runner over it."""
    model = YOLO(model_path)

    def run(frame: np.ndarray) -> np.ndarray | None:
        results = model.predict(
            source=frame, conf=confidence, device=device, verbose=False
        )
        if not results:
            return None
        keypoints = getattr(results[0], "keypoints", None)
        if keypoints is None or keypoints.xy is None:
            return None
        return keypoints.xy.cpu().numpy()

    return run


def _build_fall_runner(
    model_path: str,
    confidence: float,
    class_ids: tuple[int, ...],
    device: str,
) -> FallRunner:
    """Load a fallen-posture detector once and return the per-frame runner."""
    model = YOLO(model_path)
    wanted = set(class_ids)

    def run(frame: np.ndarray) -> list[Detection]:
        results = model.predict(
            source=frame, conf=confidence, device=device, verbose=False
        )
        detections: list[Detection] = []
        for result in results:
            if result.boxes is None:
                continue
            boxes = result.boxes.xyxy.cpu().numpy()
            scores = result.boxes.conf.cpu().numpy()
            classes = result.boxes.cls.cpu().numpy().astype(int)
            names = result.names
            for box, score, class_id in zip(
                boxes, scores, classes, strict=True
            ):
                if int(class_id) not in wanted:
                    continue
                detections.append(
                    Detection(
                        bbox=tuple(float(value) for value in box),
                        confidence=float(score),
                        class_id=int(class_id),
                        class_name=names.get(int(class_id), str(class_id)),
                    )
                )
        return detections

    return run


def _build_violence_runner(
    model_path: str,
    confidence: float,
    class_ids: tuple[int, ...],
    positive_labels: tuple[str, ...],
    device: str,
) -> ViolenceRunner:
    """Load a violence model and return the per-frame runner.

    Supports both a frame classifier (``probs`` output) and the legacy
    single-class detector (``boxes`` output), so a replacement classifier can
    be dropped in without touching the pipeline.
    """
    model = YOLO(model_path)
    threat_ids = set(class_ids)
    positives = {label.lower() for label in positive_labels}

    def run(frame: np.ndarray) -> bool:
        results = model.predict(
            source=frame, conf=confidence, device=device, verbose=False
        )
        for result in results:
            probabilities = getattr(result, "probs", None)
            if probabilities is not None:
                top = int(probabilities.top1)
                label = str(result.names.get(top, top)).lower()
                return (
                    float(probabilities.top1conf) > confidence
                    and label in positives
                )
            if result.boxes is None:
                continue
            for box in result.boxes:
                if (
                    int(box.cls[0]) in threat_ids
                    and float(box.conf[0]) > confidence
                ):
                    return True
        return False

    return run
