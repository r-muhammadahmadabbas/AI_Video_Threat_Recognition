"""Bounded per-camera frame window (S4-4A).

The worker keeps only the last ``capacity`` processed frames in memory so a
trigger can pull the moments before an incident without holding the stream.
The window is deterministic by frame number: clipping the same file twice
yields the same frames.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np


@dataclass(frozen=True)
class BufferedFrame:
    """One processed frame held for evidence capture."""

    frame_number: int
    timestamp: float
    data: np.ndarray


class RollingBuffer:
    """Circular store of recent frames."""

    def __init__(self, capacity: int) -> None:
        if capacity < 0:
            raise ValueError("capacity must be non-negative")
        self._capacity = capacity
        self._frames: deque[BufferedFrame] = deque()

    @property
    def capacity(self) -> int:
        return self._capacity

    def __len__(self) -> int:
        return len(self._frames)

    def push(self, frame: BufferedFrame) -> None:
        """Append a frame, evicting the oldest once the buffer is full."""
        self._frames.append(frame)
        if len(self._frames) > self._capacity:
            self._frames.popleft()

    def tail(self, n: int) -> list[BufferedFrame]:
        """The newest ``n`` frames in order, never more than held."""
        if n < 0:
            raise ValueError("n must be non-negative")
        if n == 0:
            return []
        frames = list(self._frames)
        return frames[-n:]

    def clear(self) -> None:
        self._frames.clear()
