from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import time

import cv2
import numpy as np


@dataclass
class Frame:
    data: np.ndarray
    timestamp: float
    frame_number: int
    source_id: str


class VideoSource(ABC):
    @abstractmethod
    def read(self) -> Optional[Frame]:
        pass

    @abstractmethod
    def is_opened(self) -> bool:
        pass

    @abstractmethod
    def release(self) -> None:
        pass

    @abstractmethod
    def get_fps(self) -> float:
        pass

    @abstractmethod
    def get_resolution(self) -> tuple[int, int]:
        pass

    @abstractmethod
    def get_source_id(self) -> str:
        pass


class MP4VideoSource(VideoSource):
    def __init__(self, source_id: str, file_path: str, loop: bool = False):
        self._source_id = source_id
        self._file_path = file_path
        self._loop = loop
        self._cap: Optional[cv2.VideoCapture] = None
        self._frame_number = 0
        self._open()

    def _open(self) -> None:
        self._cap = cv2.VideoCapture(self._file_path)
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open video file: {self._file_path}")

    def read(self) -> Optional[Frame]:
        if self._cap is None or not self._cap.isOpened():
            return None

        ret, frame = self._cap.read()
        if not ret:
            if self._loop:
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                self._frame_number = 0
                ret, frame = self._cap.read()
                if not ret:
                    return None
            else:
                return None

        self._frame_number += 1
        timestamp = time.time()
        return Frame(
            data=frame,
            timestamp=timestamp,
            frame_number=self._frame_number,
            source_id=self._source_id,
        )

    def is_opened(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def get_fps(self) -> float:
        if self._cap is None:
            return 0.0
        return self._cap.get(cv2.CAP_PROP_FPS)

    def get_resolution(self) -> tuple[int, int]:
        if self._cap is None:
            return (0, 0)
        w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return (w, h)

    def get_source_id(self) -> str:
        return self._source_id

    def __del__(self):
        self.release()


class WebcamVideoSource(VideoSource):
    def __init__(self, source_id: str, device_id: int = 0):
        self._source_id = source_id
        self._device_id = device_id
        self._cap: Optional[cv2.VideoCapture] = None
        self._frame_number = 0
        self._open()

    def _open(self) -> None:
        self._cap = cv2.VideoCapture(self._device_id)
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open webcam device: {self._device_id}")

    def read(self) -> Optional[Frame]:
        if self._cap is None or not self._cap.isOpened():
            return None

        ret, frame = self._cap.read()
        if not ret:
            return None

        self._frame_number += 1
        return Frame(
            data=frame,
            timestamp=time.time(),
            frame_number=self._frame_number,
            source_id=self._source_id,
        )

    def is_opened(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def get_fps(self) -> float:
        if self._cap is None:
            return 0.0
        return self._cap.get(cv2.CAP_PROP_FPS)

    def get_resolution(self) -> tuple[int, int]:
        if self._cap is None:
            return (0, 0)
        w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return (w, h)

    def get_source_id(self) -> str:
        return self._source_id

    def __del__(self):
        self.release()