"""Weapon detection using pre-trained YOLO26x model.

Detects firearms, melee weapons, explosives, and related threat objects
in video frames. Trained on 130K images (Weapons-130K dataset).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import numpy as np
from ultralytics import YOLO


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
    """YOLO26x-based weapon detector.

    Loads a pre-trained model and runs inference on frames to detect
    weapons and threat-related objects.
    """

    def __init__(
        self,
        model_path: str | None = None,
        confidence: float = 0.35,
        device: str = "cpu",
    ) -> None:
        if model_path is None:
            model_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "models", "model", "best.pt"
            )
        self.model = YOLO(model_path)
        self.confidence = confidence
        self.device = device

    def detect(self, frame: np.ndarray) -> list[WeaponDetection]:
        """Run weapon detection on a single frame.

        Returns a list of WeaponDetection objects for all threat objects
        found above the confidence threshold.
        """
        results = self.model.predict(
            source=frame,
            conf=self.confidence,
            device=self.device,
            verbose=False,
        )

        detections: list[WeaponDetection] = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                class_name = WEAPON_CLASSES.get(cls_id, "unknown")
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                detections.append(
                    WeaponDetection(
                        class_name=class_name,
                        confidence=conf,
                        bbox=(x1, y1, x2, y2),
                    )
                )

        return detections

    def detect_batch(
        self, frames: list[np.ndarray]
    ) -> list[list[WeaponDetection]]:
        """Run weapon detection on a batch of frames."""
        return [self.detect(frame) for frame in frames]