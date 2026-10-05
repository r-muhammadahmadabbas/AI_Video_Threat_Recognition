from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class Detection:
    bbox: tuple[float, float, float, float]
    confidence: float
    class_id: int
    class_name: str

    @property
    def center(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2, (y1 + y2) / 2)

    @property
    def bottom_center(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2, y2)

    @property
    def area(self) -> float:
        x1, y1, x2, y2 = self.bbox
        return (x2 - x1) * (y2 - y1)


class Detector(ABC):
    @abstractmethod
    def detect(self, frame: np.ndarray) -> list[Detection]:
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        pass

    @abstractmethod
    def get_model_version(self) -> str:
        pass


class YOLO26Detector(Detector):
    def __init__(
        self,
        model_name: str = "yolo26n",
        confidence: float = 0.25,
        iou: float = 0.45,
        device: str = "cpu",
        classes: Optional[list[int]] = None,
    ):
        from ultralytics import YOLO

        self._model_name = model_name
        self._confidence = confidence
        self._iou = iou
        self._device = device
        self._classes = classes
        self._model = YOLO(f"{model_name}.pt")
        self._model.to(device)

    def detect(self, frame: np.ndarray) -> list[Detection]:
        results = self._model(
            frame,
            conf=self._confidence,
            iou=self._iou,
            classes=self._classes,
            device=self._device,
            verbose=False,
        )

        detections: list[Detection] = []
        if not results:
            return detections

        result = results[0]
        if result.boxes is None:
            return detections

        boxes = result.boxes.xyxy.cpu().numpy()
        confs = result.boxes.conf.cpu().numpy()
        cls_ids = result.boxes.cls.cpu().numpy().astype(int)
        names = result.names

        for box, conf, cls_id in zip(boxes, confs, cls_ids):
            detections.append(
                Detection(
                    bbox=tuple(float(v) for v in box),
                    confidence=float(conf),
                    class_id=int(cls_id),
                    class_name=names.get(int(cls_id), str(cls_id)),
                )
            )

        return detections

    def get_model_name(self) -> str:
        return self._model_name

    def get_model_version(self) -> str:
        return "1.0"