"""Video input: file, webcam and RTSP sources behind one interface.

Every source exposes a :class:`SourceState` so a consumer can tell *why* a read
returned no frame. That distinction matters because the two cases want opposite
handling:

* a file that ran out of frames is a normal, permanent end of stream - stop;
* a live camera that dropped out is a transient fault - reconnect and carry on.

A live source therefore never silently reports "end of stream", and one camera
failing never looks like another camera finishing its clip.
"""

from __future__ import annotations

import enum
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

import cv2

if TYPE_CHECKING:
    import numpy as np


@dataclass
class Frame:
    data: np.ndarray
    timestamp: float
    frame_number: int
    source_id: str


class SourceState(enum.StrEnum):
    """Why reads are currently succeeding or failing."""

    STREAMING = "streaming"
    END_OF_STREAM = "end_of_stream"
    RECONNECTING = "reconnecting"
    FAILED = "failed"
    CLOSED = "closed"


class VideoSource(ABC):
    """Common contract for anything that yields frames.

    Subclasses set :attr:`is_live`; everything else - state transitions and the
    reconnect budget - is shared, so a source cannot forget to report a failure.
    """

    def __init__(
        self,
        source_id: str,
        max_reconnect_attempts: int = 5,
        reconnect_delay: float = 0.0,
        max_reconnect_delay: float | None = None,
    ) -> None:
        self._source_id = source_id
        self._state = SourceState.STREAMING
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = max_reconnect_attempts
        self._reconnect_delay = reconnect_delay
        self._max_reconnect_delay = (
            reconnect_delay if max_reconnect_delay is None else max_reconnect_delay
        )
        self._cap: cv2.VideoCapture | None = None

    @property
    @abstractmethod
    def is_live(self) -> bool:
        """Live sources recover from read failures; a finished file does not."""

    @abstractmethod
    def _open_capture(self) -> cv2.VideoCapture:
        """Open the underlying capture, raising if that is impossible."""

    def _handle_read_failure(self) -> Frame | None:
        """Record why a read produced nothing.

        Live sources go to ``RECONNECTING`` rather than ``END_OF_STREAM``: a
        dropped stream is an outage to recover from, not a finished clip.
        """
        if self._state is SourceState.CLOSED:
            # Released is a deliberate terminal state; reads after release must
            # not relabel it as an ordinary end of stream.
            return None
        if not self.is_live:
            self._state = SourceState.END_OF_STREAM
        elif self._state is not SourceState.FAILED:
            self._state = SourceState.RECONNECTING
        return None

    def reconnect(self) -> bool:
        """Re-open a live capture after a drop.

        Returns ``True`` once streaming resumes. Attempts are budgeted so a
        camera that is genuinely gone moves to ``FAILED`` instead of retrying
        forever and masking the outage.
        """
        if self._state in (SourceState.CLOSED, SourceState.FAILED):
            return False
        if not self.is_live:
            return False

        if self._reconnect_attempts >= self._max_reconnect_attempts:
            self._state = SourceState.FAILED
            return False

        self._state = SourceState.RECONNECTING
        # Back off exponentially: a camera that just dropped usually comes
        # straight back, while one that is down for good must not be hammered.
        delay = min(
            self._reconnect_delay * (2**self._reconnect_attempts),
            self._max_reconnect_delay,
        )
        if delay > 0.0:
            time.sleep(delay)
        self._reconnect_attempts += 1

        try:
            capture = self._open_capture()
        except Exception:
            if self._reconnect_attempts >= self._max_reconnect_attempts:
                self._state = SourceState.FAILED
            return False

        self._attach_capture(capture)
        self._state = SourceState.STREAMING
        return True

    def _attach_capture(self, capture: cv2.VideoCapture) -> None:
        """Swap in a freshly opened capture. Overridden where state must reset."""
        self._cap = capture

    def _mark_streaming(self) -> None:
        self._state = SourceState.STREAMING
        self._reconnect_attempts = 0

    @property
    def state(self) -> SourceState:
        return self._state

    @property
    def reconnect_attempts(self) -> int:
        return self._reconnect_attempts

    @abstractmethod
    def read(self) -> Frame | None: ...

    @abstractmethod
    def is_opened(self) -> bool: ...

    @abstractmethod
    def release(self) -> None: ...

    @abstractmethod
    def get_fps(self) -> float: ...

    @abstractmethod
    def get_resolution(self) -> tuple[int, int]: ...

    def get_source_id(self) -> str:
        return self._source_id


class MP4VideoSource(VideoSource):
    def __init__(self, source_id: str, file_path: str, loop: bool = False) -> None:
        super().__init__(source_id)
        self._file_path = file_path
        self._loop = loop
        self._frame_number = 0
        self._attach_capture(self._open_capture())

    @property
    def is_live(self) -> bool:
        # A local file either has the next frame or it is finished; there is
        # nothing to reconnect to.
        return False

    def _open_capture(self) -> cv2.VideoCapture:
        capture = cv2.VideoCapture(self._file_path)
        if not capture.isOpened():
            raise RuntimeError(f"Cannot open video file: {self._file_path}")
        return capture

    def read(self) -> Frame | None:
        if self._cap is None or not self._cap.isOpened():
            return self._handle_read_failure()

        ret, frame = self._cap.read()
        if not ret:
            if self._loop:
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                self._frame_number = 0
                ret, frame = self._cap.read()
                if not ret:
                    return self._handle_read_failure()
            else:
                return self._handle_read_failure()

        self._frame_number += 1
        return Frame(
            data=frame,
            timestamp=time.time(),
            frame_number=self._frame_number,
            source_id=self._source_id,
        )

    def is_opened(self) -> bool:
        return (
            self._state is SourceState.STREAMING
            and self._cap is not None
            and self._cap.isOpened()
        )

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self._state = SourceState.CLOSED

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

    def __del__(self) -> None:
        self.release()


class _LiveSource(VideoSource):
    """Shared behaviour for capture devices and network streams."""

    def __init__(
        self,
        source_id: str,
        *,
        max_reconnect_attempts: int = 5,
        reconnect_delay: float = 0.0,
        max_reconnect_delay: float | None = None,
    ) -> None:
        super().__init__(
            source_id,
            max_reconnect_attempts=max_reconnect_attempts,
            reconnect_delay=reconnect_delay,
            max_reconnect_delay=max_reconnect_delay,
        )
        self._frame_number = 0
        self._attach_capture(self._open_capture())

    @property
    def is_live(self) -> bool:
        return True

    def _attach_capture(self, capture: cv2.VideoCapture) -> None:
        if self._cap is not None and self._cap is not capture:
            self._cap.release()
        self._cap = capture

    def read(self) -> Frame | None:
        if self._cap is None or not self._cap.isOpened():
            return self._handle_read_failure()

        ret, frame = self._cap.read()
        if not ret:
            return self._handle_read_failure()

        self._frame_number += 1
        self._mark_streaming()
        return Frame(
            data=frame,
            timestamp=time.time(),
            frame_number=self._frame_number,
            source_id=self._source_id,
        )

    def is_opened(self) -> bool:
        return (
            self._state is SourceState.STREAMING
            and self._cap is not None
            and self._cap.isOpened()
        )

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self._state = SourceState.CLOSED

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

    def __del__(self) -> None:
        self.release()


class WebcamVideoSource(_LiveSource):
    def __init__(
        self,
        source_id: str,
        device_id: int = 0,
        *,
        max_reconnect_attempts: int = 5,
        reconnect_delay: float = 0.0,
    ) -> None:
        self._device_id = device_id
        super().__init__(
            source_id,
            max_reconnect_attempts=max_reconnect_attempts,
            reconnect_delay=reconnect_delay,
        )

    def _open_capture(self) -> cv2.VideoCapture:
        capture = cv2.VideoCapture(self._device_id)
        if not capture.isOpened():
            raise RuntimeError(f"Cannot open webcam device: {self._device_id}")
        return capture


class RTSPVideoSource(_LiveSource):
    """Network stream.

    Reconnect budget and initial delay come from ``settings.video`` so an
    operator tunes recovery per deployment rather than in code.
    """

    def __init__(
        self,
        source_id: str,
        url: str,
        *,
        max_reconnect_attempts: int = 5,
        reconnect_delay: float = 0.0,
        max_reconnect_delay: float | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._url = url
        self._timeout = timeout
        super().__init__(
            source_id,
            max_reconnect_attempts=max_reconnect_attempts,
            reconnect_delay=reconnect_delay,
            max_reconnect_delay=max_reconnect_delay,
        )

    def _open_capture(self) -> cv2.VideoCapture:
        capture = cv2.VideoCapture(self._url, cv2.CAP_FFMPEG)
        capture.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, int(self._timeout * 1000))
        if not capture.isOpened():
            raise RuntimeError(f"Cannot open RTSP stream: {self._url}")
        return capture
