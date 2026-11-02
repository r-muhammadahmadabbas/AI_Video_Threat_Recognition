"""Latest phone frame, reused as the snapshot for drawing zones."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import cv2
import numpy as np

from app.config import settings

_lock = threading.Lock()
_memory: dict[int, tuple[bytes, int, int]] = {}
_last_decode: dict[int, float] = {}


def _folder() -> Path:
    path = Path(settings.video.media_dir) / "snapshots"
    path.mkdir(parents=True, exist_ok=True)
    return path


def remember_frame(camera_id: int, jpeg: bytes) -> None:
    """Keep the newest JPEG for a phone camera.

    Decoding and disk writes happen about once a second. Frames in between
    reuse the last known size so the zone editor can refresh without stalling
    the ingest socket.
    """
    if not jpeg:
        return

    now = time.monotonic()
    with _lock:
        cached = _memory.get(camera_id)
        if cached is not None and now - _last_decode.get(camera_id, 0.0) < 1.0:
            _memory[camera_id] = (jpeg, cached[1], cached[2])
            return
        _last_decode[camera_id] = now

    image = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8).copy(), cv2.IMREAD_COLOR)
    if image is None:
        return
    height, width = image.shape[:2]

    with _lock:
        _memory[camera_id] = (jpeg, width, height)

    folder = _folder()
    (folder / f"{camera_id}.jpg").write_bytes(jpeg)
    (folder / f"{camera_id}.json").write_text(
        json.dumps({"width": width, "height": height}),
        encoding="utf-8",
    )


def latest_snapshot(camera_id: int) -> tuple[bytes, int, int] | None:
    """Return ``(jpeg, width, height)`` for the last frame, including after restart."""
    with _lock:
        cached = _memory.get(camera_id)
    if cached is not None and cached[1] > 0 and cached[2] > 0:
        return cached

    image_path = _folder() / f"{camera_id}.jpg"
    if not image_path.is_file():
        return None

    jpeg = image_path.read_bytes()
    width, height = 0, 0
    meta_path = image_path.with_suffix(".json")
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            width = int(meta.get("width") or 0)
            height = int(meta.get("height") or 0)
        except (OSError, TypeError, ValueError):
            width, height = 0, 0

    if width <= 0 or height <= 0:
        image = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8).copy(), cv2.IMREAD_COLOR)
        if image is None:
            return None
        height, width = image.shape[:2]

    with _lock:
        _memory[camera_id] = (jpeg, width, height)
    return jpeg, width, height
