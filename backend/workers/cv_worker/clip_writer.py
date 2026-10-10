"""Bounded evidence clip encoding (S4-4B).

Encodes a captured window of frames into a self-contained mp4. The worker
encodes at its inference cadence (never the source's raw cadence), so the
clip's duration reflects the seconds the worker actually observed - replaying
the same input file yields an identical clip.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import cv2

if TYPE_CHECKING:
    from pathlib import Path

    from workers.cv_worker.rolling_buffer import BufferedFrame

# upstream opencv stubs omit VideoWriter_fourcc even though it exists at
# runtime; mypy needs a nudge on this line
_FOURCC = cv2.VideoWriter_fourcc  # type: ignore[attr-defined]


class ClipError(Exception):
    """Raised when frames cannot be encoded into a clip."""


@dataclass(frozen=True)
class ClipResult:
    """Outcome of an encode: where the file landed and what it contains."""

    path: Path
    frame_count: int
    fps: float
    duration_seconds: float
    size_bytes: int


@dataclass
class ClipWriter:
    """Encodes frame windows into mp4 files on the local filesystem."""

    fps: float
    fourcc: str = "mp4v"

    def __post_init__(self) -> None:
        if self.fps <= 0:
            raise ValueError("fps must be positive")
        if len(self.fourcc) != 4:
            raise ValueError("fourcc must be exactly four characters")

    def cut(self, frames: list[BufferedFrame], output_path: Path) -> ClipResult:
        """Encode ``frames`` at :attr:`fps` into ``output_path``."""
        if not frames:
            raise ClipError("cannot encode an empty clip")

        height, width = frames[0].data.shape[:2]
        if width == 0 or height == 0:
            raise ClipError(f"frame has no pixels: {width}x{height}")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        writer = cv2.VideoWriter(
            str(output_path),
            _FOURCC(*self.fourcc),
            self.fps,
            (width, height),
        )
        if not writer.isOpened():
            raise ClipError(f"could not open video writer for {output_path}")

        try:
            for frame in frames:
                writer.write(frame.data)
        finally:
            writer.release()

        size_bytes = output_path.stat().st_size
        if size_bytes == 0:
            output_path.unlink()
            raise ClipError(f"encoding produced an empty file for {output_path}")

        return ClipResult(
            path=output_path,
            frame_count=len(frames),
            fps=self.fps,
            duration_seconds=len(frames) / self.fps,
            size_bytes=size_bytes,
        )
