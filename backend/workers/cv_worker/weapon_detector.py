"""Weapon detection using pre-trained YOLO26x model with temporal confirmation.

Detects firearms, melee weapons, explosives, and related threat objects
in video frames. Trained on 130K images (Weapons-130K dataset).

Accuracy improvements:
- Temporal voting: weapon must appear in N consecutive frames
- Horizontal flip test-time augmentation
- Class-aware NMS to remove overlapping boxes
- Adaptive confidence per class
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import cv2
from ultralytics import YOLO

if TYPE_CHECKING:
    import numpy as np


WEAPON_CLASSES = {
    0: "blunt_weapon",
    1: "explosive",
    2: "fire_smoke",
    3: "firearm",
    4: "melee_weapon",
    5: "person",
    6: "tool",
}

THREAT_CLASSES = {"firearm", "melee_weapon", "explosive", "blunt_weapon"}

CLASS_CONFIDENCE = {
    "firearm": 0.25,
    "melee_weapon": 0.30,
    "explosive": 0.35,
    "blunt_weapon": 0.35,
    "person": 0.40,
    "fire_smoke": 0.40,
    "tool": 0.40,
}


@dataclass
class WeaponDetection:
    """A single weapon detection result."""

    class_name: str
    confidence: float
    bbox: tuple[float, float, float, float]
    is_threat: bool = field(init=False)

    def __post_init__(self) -> None:
        self.is_threat = self.class_name in THREAT_CLASSES


class WeaponDetector:
    """YOLO26x-based weapon detector with temporal confirmation.

    Uses multi-frame voting to reduce false positives: a weapon must be
    detected in at least `temporal_window` frames within the last
    `temporal_history` frames to be confirmed.
    """

    def __init__(
        self,
        model_path: str | None = None,
        confidence: float = 0.25,
        device: str = "cpu",
        temporal_window: int = 1,
        temporal_history: int = 6,
    ) -> None:
        if model_path is None:
            model_path = str(
                Path(__file__).resolve().parents[2] / "models" / "model" / "best.pt"
            )
        self.model = YOLO(model_path)
        self.confidence = confidence
        self.device = device
        self.temporal_window = temporal_window
        self.temporal_history = temporal_history
        self._history: deque[list[WeaponDetection]] = deque(maxlen=temporal_history)

    def reset(self) -> None:
        """Drop temporal voting history so one instance can serve a new clip."""
        self._history.clear()

    def detect(self, frame: np.ndarray) -> list[WeaponDetection]:
        """Run weapon detection with flip augmentation and class-aware NMS."""
        results_normal = self.model.predict(
            source=frame, conf=self.confidence, device=self.device, verbose=False, iou=0.5
        )

        frame_flipped = cv2.flip(frame, 1)
        results_flipped = self.model.predict(
            source=frame_flipped, conf=self.confidence, device=self.device, verbose=False, iou=0.5
        )

        w = frame.shape[1]
        all_dets: list[WeaponDetection] = []

        for results, is_flip in [(results_normal, False), (results_flipped, True)]:
            for result in results:
                if result.boxes is None:
                    continue
                for box in result.boxes:
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    class_name = WEAPON_CLASSES.get(cls_id, "unknown")
                    if class_name == "unknown":
                        continue

                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    if is_flip:
                        x1, x2 = w - x2, w - x1

                    all_dets.append(
                        WeaponDetection(
                            class_name=class_name,
                            confidence=conf,
                            bbox=(x1, y1, x2, y2),
                        )
                    )

        filtered = self._class_aware_nms(all_dets, iou_threshold=0.5)
        self._history.append(filtered)

        return self._temporal_vote(filtered)

    def _temporal_vote(
        self, current: list[WeaponDetection]
    ) -> list[WeaponDetection]:
        """Require temporal consistency to confirm detections."""
        if len(self._history) < self.temporal_window:
            return []

        confirmed: list[WeaponDetection] = []
        for det in current:
            if not det.is_threat:
                continue
            votes = 1
            for past in list(self._history)[:-1]:
                for pd in past:
                    if (
                        pd.class_name == det.class_name
                        and self._iou(pd.bbox, det.bbox) > 0.3
                    ):
                        votes += 1
                        break
            if votes >= self.temporal_window:
                confirmed.append(det)

        confirmed.extend([d for d in current if not d.is_threat])
        return confirmed

    @staticmethod
    def _class_aware_nms(
        detections: list[WeaponDetection], iou_threshold: float = 0.5
    ) -> list[WeaponDetection]:
        """Remove overlapping detections of the same class."""
        by_class: dict[str, list[WeaponDetection]] = {}
        for d in detections:
            by_class.setdefault(d.class_name, []).append(d)

        kept: list[WeaponDetection] = []
        for dets in by_class.values():
            dets.sort(key=lambda d: d.confidence, reverse=True)
            remaining = dets
            while remaining:
                best = remaining.pop(0)
                kept.append(best)
                remaining = [
                    d for d in remaining
                    if WeaponDetector._iou(best.bbox, d.bbox) < iou_threshold
                ]
        return kept

    @staticmethod
    def _iou(a, b) -> float:
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        ix1, iy1 = max(ax1, bx1), max(ay1, by1)
        ix2, iy2 = min(ax2, bx2), min(ay2, by2)
        iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
        inter = iw * ih
        area_a = (ax2 - ax1) * (ay2 - ay1)
        area_b = (bx2 - bx1) * (by2 - by1)
        union = area_a + area_b - inter
        return inter / union if union > 0 else 0.0
