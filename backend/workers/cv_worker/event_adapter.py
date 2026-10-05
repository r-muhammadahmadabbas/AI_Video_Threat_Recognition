from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np

from workers.cv_worker.detector import Detection
from workers.cv_worker.video_source import Frame


@dataclass
class EventCandidate:
    event_type: str
    source_id: str
    timestamp: float
    confidence: float
    detections: list[Detection] = field(default_factory=list)
    frame: np.ndarray | None = field(default=None, repr=False)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "source_id": self.source_id,
            "timestamp": self.timestamp,
            "confidence": self.confidence,
            "detections": [
                {
                    "bbox": list(d.bbox),
                    "confidence": d.confidence,
                    "class_id": d.class_id,
                    "class_name": d.class_name,
                }
                for d in self.detections
            ],
            "metadata": self.metadata,
        }


class EventAdapter(ABC):
    @abstractmethod
    def process(self, frame: Frame, detections: list[Detection]) -> list[EventCandidate]:
        pass


class PersonPresenceAdapter(EventAdapter):
    def __init__(self, min_confidence: float = 0.25):
        self._min_confidence = min_confidence

    def process(self, frame: Frame, detections: list[Detection]) -> list[EventCandidate]:
        persons = [d for d in detections if d.class_name == "person" and d.confidence >= self._min_confidence]
        if not persons:
            return []

        max_conf = max(d.confidence for d in persons)
        return [
            EventCandidate(
                event_type="person_presence",
                source_id=frame.source_id,
                timestamp=frame.timestamp,
                confidence=max_conf,
                detections=persons,
                frame=frame.data.copy(),
                metadata={
                    "person_count": len(persons),
                    "frame_number": frame.frame_number,
                },
            )
        ]