"""Bounded evidence clip encoding (S4-4B).

Encodes a captured window of frames into a self-contained mp4. The worker
encodes at its inference cadence (never the source's raw cadence), so the
clip's duration reflects the seconds the worker actually observed - replaying
the same input file yields an identical clip.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import cv2

from app.logging import get_logger

try:
    import imageio_ffmpeg
except ImportError:  # pragma: no cover - optional dependency
    imageio_ffmpeg = None  # type: ignore[assignment]

if TYPE_CHECKING:
    from workers.cv_worker.rolling_buffer import BufferedFrame

logger = get_logger(__name__)

# upstream opencv stubs omit VideoWriter_fourcc even though it exists at
# runtime; mypy needs a nudge on this line
_FOURCC = cv2.VideoWriter_fourcc  # type: ignore[attr-defined]


def _find_ffmpeg() -> str | None:
    """A usable ffmpeg binary, preferring the one bundled with imageio."""
    if imageio_ffmpeg is not None:
        try:
            bundled = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:  # optional dependency, PATH fallback
            bundled = None
        if bundled and Path(bundled).is_file():
            return bundled
    return shutil.which("ffmpeg")


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
    #: Browsers cannot play OpenCV's MPEG-4 Part 2 output (``mp4v``). After
    #: writing, re-encode to H.264 so the clip plays inline. Best effort: when
    #: ffmpeg is unavailable the original file is kept.
    transcode_h264: bool = True

    def __post_init__(self) -> None:
        if self.fps <= 0:
            raise ValueError("fps must be positive")
        if len(self.fourcc) != 4:
            raise ValueError("fourcc must be exactly four characters")

    def _transcode_to_h264(self, output_path: Path) -> bool:
        ffmpeg = _find_ffmpeg()
        if ffmpeg is None:
            logger.warning(
                "ffmpeg not found; evidence clip stays mp4v and may not play in browsers"
            )
            return False

        temp_path = output_path.with_name(
            f"{output_path.stem}.h264{output_path.suffix}"
        )
        command = [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(output_path),
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(temp_path),
        ]
        try:
            subprocess.run(  # noqa: S603 - fixed argv, discovered binary
                command,
                check=True,
                capture_output=True,
                timeout=120,
            )
        except (OSError, subprocess.SubprocessError):
            temp_path.unlink(missing_ok=True)
            logger.warning("H.264 transcode failed; keeping mp4v clip")
            return False

        if not temp_path.is_file() or temp_path.stat().st_size == 0:
            temp_path.unlink(missing_ok=True)
            logger.warning("H.264 transcode produced no output; keeping mp4v clip")
            return False

        temp_path.replace(output_path)
        return True

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

        if self.transcode_h264:
            self._transcode_to_h264(output_path)

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
