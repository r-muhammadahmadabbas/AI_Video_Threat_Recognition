"""S4 evidence pipeline: rolling buffer, clip writer, store, range serving."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from app.evidence.router import _parse_range
from app.evidence.storage import EvidenceStoreError, LocalEvidenceStore
from workers.cv_worker.clip_writer import ClipError, ClipWriter
from workers.cv_worker.rolling_buffer import BufferedFrame, RollingBuffer


def _frame(number: int, timestamp: float, size: int = 8) -> BufferedFrame:
    data = np.full((4, size, 3), number + 1, dtype=np.uint8)
    return BufferedFrame(frame_number=number, timestamp=timestamp, data=data)


class TestRollingBuffer:
    """4A is a bounded window: capacity held, oldest dropped, tail ordered."""

    def test_pushes_and_returns_tail_in_order(self):
        buffer = RollingBuffer(capacity=5)
        for i in range(3):
            buffer.push(_frame(i, float(i)))

        assert [f.frame_number for f in buffer.tail(5)] == [0, 1, 2]

    def test_capacity_is_bounded(self):
        buffer = RollingBuffer(capacity=3)
        for i in range(10):
            buffer.push(_frame(i, float(i)))

        assert len(buffer) == 3
        assert [f.frame_number for f in buffer.tail(3)] == [7, 8, 9]

    def test_tail_never_returns_more_than_held(self):
        buffer = RollingBuffer(capacity=2)
        buffer.push(_frame(0, 0.0))

        assert [f.frame_number for f in buffer.tail(5)] == [0]

    def test_tail_zero_returns_nothing(self):
        buffer = RollingBuffer(capacity=5)
        buffer.push(_frame(0, 0.0))

        assert buffer.tail(0) == []

    def test_clear_empties_buffer(self):
        buffer = RollingBuffer(capacity=5)
        buffer.push(_frame(0, 0.0))
        buffer.clear()

        assert len(buffer) == 0

    def test_rejects_negative_capacity(self):
        with pytest.raises(ValueError):
            RollingBuffer(capacity=-1)

    def test_rejects_negative_tail(self):
        with pytest.raises(ValueError):
            RollingBuffer(capacity=5).tail(-1)


class TestClipWriter:
    """4B produces a readable, bounded mp4 whose duration matches the frames."""

    def test_cut_writes_readable_mp4(self, tmp_path):
        frames = [_frame(i, float(i), size=16) for i in range(6)]
        writer = ClipWriter(fps=10.0)
        output = tmp_path / "clip.mp4"

        result = writer.cut(frames, output)

        assert result.frame_count == 6
        assert result.fps == 10.0
        assert result.duration_seconds == pytest.approx(0.6)
        assert result.size_bytes > 0
        assert output.exists()

        cap = cv2.VideoCapture(str(output))
        assert cap.isOpened()
        count = 0
        while cap.read()[0]:
            count += 1
        cap.release()
        assert count == 6

    def test_empty_clip_is_rejected(self, tmp_path):
        with pytest.raises(ClipError):
            ClipWriter(fps=10.0).cut([], tmp_path / "empty.mp4")

    def test_requires_positive_fps(self):
        with pytest.raises(ValueError):
            ClipWriter(fps=0.0)


class TestLocalEvidenceStore:
    """4C: artifacts addressed by key, resolve() can never leave the root."""

    def test_put_bytes_and_resolve_round_trip(self, tmp_path):
        store = LocalEvidenceStore(tmp_path / "evidence")
        handle = store.put(
            "incidents/12/frame-3.jpg", b"\xff\xd8\xff", media_type="image/jpeg"
        )

        path = Path(store.resolve(handle.key))
        assert path.exists()
        assert path.read_bytes() == b"\xff\xd8\xff"
        assert Path(handle.uri) == path

    def test_put_file_copies_contents(self, tmp_path):
        store = LocalEvidenceStore(tmp_path / "evidence")
        source = tmp_path / "source.mp4"
        source.write_bytes(b"video-data")

        handle = store.put("incidents/12/clip.mp4", source, media_type="video/mp4")

        assert Path(store.resolve(handle.key)).read_bytes() == b"video-data"
        assert source.exists()

    def test_traversal_keys_are_rejected(self, tmp_path):
        store = LocalEvidenceStore(tmp_path / "evidence")

        for bad in ["../secret.txt", "../../etc/passwd", "a/../../b.txt"]:
            with pytest.raises(EvidenceStoreError):
                store.resolve(bad)
            with pytest.raises(EvidenceStoreError):
                store.put(bad, b"x", media_type="image/jpeg")

    def test_absolute_keys_are_rejected(self, tmp_path):
        store = LocalEvidenceStore(tmp_path / "evidence")

        with pytest.raises(EvidenceStoreError):
            store.resolve(str(tmp_path / "outside.mp4"))

    def test_delete_removes_and_missing_is_noop(self, tmp_path):
        store = LocalEvidenceStore(tmp_path / "evidence")
        store.put("incidents/12/a.jpg", b"x", media_type="image/jpeg")

        store.delete("incidents/12/a.jpg")
        assert not (tmp_path / "evidence" / "incidents" / "12" / "a.jpg").exists()

        store.delete("incidents/12/never-was.jpg")


class TestRangeParsing:
    """4D: browsers and players issue Range requests when seeking video."""

    def test_no_header_returns_none(self):
        assert _parse_range(None, 1000) is None

    def test_non_bytes_unit_returns_none(self):
        assert _parse_range("items=0-10", 1000) is None

    def test_open_ended_range(self):
        assert _parse_range("bytes=200-", 1000) == (200, 999)

    def test_suffix_range(self):
        assert _parse_range("bytes=-100", 1000) == (900, 999)

    def test_bounded_range(self):
        assert _parse_range("bytes=100-199", 1000) == (100, 199)

    def test_range_clamped_to_end(self):
        assert _parse_range("bytes=100-5000", 1000) == (100, 999)

    def test_start_past_end_returns_none(self):
        assert _parse_range("bytes=1000-", 1000) is None

    def test_multi_range_falls_back_to_none(self):
        assert _parse_range("bytes=0-99,200-299", 1000) is None

    def test_malformed_returns_none(self):
        assert _parse_range("bytes=abc-def", 1000) is None