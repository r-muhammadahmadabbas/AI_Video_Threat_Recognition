"""Run the shared detection pipeline over images and emit harness predictions.

The analyzer is duck-typed so the harness (and its tests) can drive either the
real :class:`workers.cv_worker.analyzer.FrameAnalyzer` or a fake.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import cv2

from scripts.eval.metrics import BoxPrediction

if TYPE_CHECKING:
    from pathlib import Path

    import numpy as np


class DetectionLike(Protocol):
    class_name: str
    confidence: float
    bbox: tuple[float, float, float, float]


class FrameAnalysisLike(Protocol):
    persons: list[DetectionLike]
    weapons: list[DetectionLike]


class ImageAnalyzer(Protocol):
    def reset(self) -> None: ...

    def analyze(self, frame: np.ndarray) -> FrameAnalysisLike: ...


def predict_images(
    paths: dict[str, Path], analyzer: ImageAnalyzer
) -> dict[str, list[BoxPrediction]]:
    """Analyze every image independently and collect box predictions.

    The analyzer is reset per image: images have no temporal relationship, so
    weapon temporal voting must not leak from one image into the next.
    """
    predictions: dict[str, list[BoxPrediction]] = {}

    for image_id, path in paths.items():
        frame = cv2.imread(str(path))
        if frame is None:
            raise ValueError(f"could not read image: {path}")

        analyzer.reset()
        analysis = analyzer.analyze(frame)
        predictions[image_id] = [
            *(
                BoxPrediction(
                    class_name=detection.class_name,
                    confidence=detection.confidence,
                    bbox=tuple(detection.bbox),
                )
                for detection in analysis.persons
            ),
            *(
                BoxPrediction(
                    class_name=detection.class_name,
                    confidence=detection.confidence,
                    bbox=tuple(detection.bbox),
                )
                for detection in analysis.weapons
            ),
        ]

    return predictions
