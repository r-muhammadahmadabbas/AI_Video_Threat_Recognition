"""JSON Lines records for ground truth and predictions.

One record per image or clip. Ground truth::

    {"image": "000001.jpg", "boxes": [{"class": "person", "bbox": [1, 2, 30, 60]}]}
    {"clip": "fall_01.mp4", "duration": 10.0,
     "events": [{"type": "person_down", "start": 3.0, "end": 5.5}]}

Predictions use the same shapes with a ``confidence`` per box:

    {"image": "000001.jpg",
     "predictions": [{"class": "person", "confidence": 0.9, "bbox": [1, 2, 30, 60]}]}
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from scripts.eval.metrics import BoxLabel, BoxPrediction, EventInterval

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class ClipEvents:
    """All ground-truth events for one clip."""

    clip: str
    duration: float | None
    events: list[EventInterval]


def _read_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            records.append(json.loads(stripped))
        except json.JSONDecodeError as error:
            raise ValueError(
                f"{path}:{line_number}: invalid JSON record: {error}"
            ) from error
    return records


def load_box_gt(path: Path) -> dict[str, list[BoxLabel]]:
    """Load per-image ground-truth boxes keyed by image id."""
    gt: dict[str, list[BoxLabel]] = {}
    for record in _read_jsonl(path):
        image_id = record["image"]
        gt[image_id] = [
            BoxLabel(
                class_name=box["class"],
                bbox=tuple(float(v) for v in box["bbox"]),
            )
            for box in record.get("boxes", [])
        ]
    return gt


def load_box_predictions(path: Path) -> dict[str, list[BoxPrediction]]:
    """Load per-image predictions keyed by image id."""
    predictions: dict[str, list[BoxPrediction]] = {}
    for record in _read_jsonl(path):
        image_id = record["image"]
        predictions[image_id] = [
            BoxPrediction(
                class_name=box["class"],
                confidence=float(box["confidence"]),
                bbox=tuple(float(v) for v in box["bbox"]),
            )
            for box in record.get("predictions", [])
        ]
    return predictions


def load_event_gt(path: Path) -> dict[str, ClipEvents]:
    """Load per-clip ground-truth events (also reads prediction files)."""
    clips: dict[str, ClipEvents] = {}
    for record in _read_jsonl(path):
        clip = record["clip"]
        clips[clip] = ClipEvents(
            clip=clip,
            duration=(
                float(record["duration"]) if record.get("duration") is not None else None
            ),
            events=[
                EventInterval(
                    event_type=event["type"],
                    start=float(event["start"]),
                    end=float(event["end"]),
                )
                for event in record.get("events", [])
            ],
        )
    return clips


def save_predictions(
    path: Path, predictions: dict[str, list[BoxPrediction]]
) -> None:
    """Write per-image box predictions as JSON Lines."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(
            {
                "image": image_id,
                "predictions": [
                    {
                        "class": prediction.class_name,
                        "confidence": round(prediction.confidence, 6),
                        "bbox": [round(v, 2) for v in prediction.bbox],
                    }
                    for prediction in image_predictions
                ],
            }
        )
        for image_id, image_predictions in predictions.items()
    ]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
