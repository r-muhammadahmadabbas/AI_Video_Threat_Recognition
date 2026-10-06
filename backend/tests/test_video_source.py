import tempfile
from pathlib import Path

import cv2
import numpy as np
import pytest

from workers.cv_worker.video_source import (
    Frame,
    MP4VideoSource,
    RTSPVideoSource,
    SourceState,
    VideoSource,
)


def _create_test_video(
    path: str,
    frames: int = 10,
    width: int = 640,
    height: int = 480,
    fps: int = 30,
) -> None:
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(path, fourcc, fps, (width, height))
    for i in range(frames):
        frame = np.full((height, width, 3), i * 20 % 255, dtype=np.uint8)
        writer.write(frame)
    writer.release()


@pytest.fixture
def sample_video():
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        path = f.name
    _create_test_video(path, frames=30)
    yield path
    Path(path).unlink(missing_ok=True)


class TestMP4VideoSource:
    def test_open_and_read(self, sample_video):
        src = MP4VideoSource("test_cam", sample_video)
        assert src.is_opened()
        assert src.get_source_id() == "test_cam"
        assert src.get_fps() == 30.0
        assert src.get_resolution() == (640, 480)

        frame = src.read()
        assert frame is not None
        assert isinstance(frame, Frame)
        assert frame.source_id == "test_cam"
        assert frame.frame_number == 1
        assert frame.data.shape == (480, 640, 3)
        src.release()

    def test_read_all_frames(self, sample_video):
        src = MP4VideoSource("test_cam", sample_video)
        count = 0
        while True:
            frame = src.read()
            if frame is None:
                break
            count += 1
        assert count == 30
        src.release()

    def test_loop_enabled(self, sample_video):
        src = MP4VideoSource("test_cam", sample_video, loop=True)
        for _ in range(35):
            frame = src.read()
            assert frame is not None
        assert src.is_opened()
        src.release()

    def test_release(self, sample_video):
        src = MP4VideoSource("test_cam", sample_video)
        src.release()
        assert not src.is_opened()

    def test_invalid_file_raises(self):
        with pytest.raises(RuntimeError, match="Cannot open video file"):
            MP4VideoSource("bad_cam", "/nonexistent/video.mp4")

    def test_frame_timestamp_increases(self, sample_video):
        src = MP4VideoSource("test_cam", sample_video)
        f1 = src.read()
        f2 = src.read()
        assert f2.timestamp >= f1.timestamp
        assert f2.frame_number == f1.frame_number + 1
        src.release()


def _drain(src: VideoSource) -> int:
    count = 0
    while src.read() is not None:
        count += 1
    return count


class _DropRTSP(RTSPVideoSource):
    """RTSP source that can be told its network has gone away.

    Used to drive the reconnect budget without needing a real camera.
    """

    def __init__(self, url: str, **kwargs) -> None:
        self._network_down = False
        super().__init__("dropcam", url=url, **kwargs)

    def _open_capture(self):
        if self._network_down:
            raise RuntimeError("connection refused")
        return super()._open_capture()


class TestSourceStates:
    def test_file_ends_in_end_of_stream(self, sample_video):
        src = MP4VideoSource("cam", sample_video)
        assert _drain(src) == 30
        assert src.state is SourceState.END_OF_STREAM

    def test_end_of_stream_is_terminal(self, sample_video):
        src = MP4VideoSource("cam", sample_video)
        _drain(src)
        assert src.read() is None
        assert src.state is SourceState.END_OF_STREAM
        src.release()

    def test_looping_file_never_reports_end_of_stream(self, sample_video):
        src = MP4VideoSource("cam", sample_video, loop=True)
        for _ in range(75):
            assert src.read() is not None
            assert src.state is SourceState.STREAMING
        src.release()

    def test_release_is_terminal(self, sample_video):
        src = MP4VideoSource("cam", sample_video)
        src.release()
        assert src.state is SourceState.CLOSED
        assert not src.is_opened()
        # Reads after release must not relabel a deliberate close.
        assert src.read() is None
        assert src.state is SourceState.CLOSED

    def test_live_source_reports_reconnecting_not_end_of_stream(
        self, sample_video
    ):
        src = RTSPVideoSource("cam", url=sample_video, reconnect_delay=0.0)
        assert src.is_live
        _drain(src)
        assert src.state is SourceState.RECONNECTING
        src.release()


class TestReconnect:
    def test_reconnect_restores_streaming(self, sample_video):
        src = RTSPVideoSource("cam", url=sample_video, reconnect_delay=0.0)
        _drain(src)
        assert src.state is SourceState.RECONNECTING

        assert src.reconnect() is True
        assert src.state is SourceState.STREAMING
        assert src.read() is not None
        src.release()

    def test_reconnect_refused_for_file_source(self, sample_video):
        src = MP4VideoSource("cam", sample_video)
        _drain(src)
        # A finished file has nothing to reconnect to; reporting success here
        # would hide a permanent end of stream behind a fake recovery.
        assert src.reconnect() is False
        assert src.state is SourceState.END_OF_STREAM
        src.release()

    def test_reconnect_budget_marks_source_failed(self, sample_video):
        src = _DropRTSP(sample_video, reconnect_delay=0.0)
        _drain(src)
        src._network_down = True

        for _ in range(10):
            src.reconnect()

        assert src.state is SourceState.FAILED
        assert src.reconnect_attempts == src._max_reconnect_attempts
        # A failed source must stay failed, not flap back to reconnecting.
        assert src.reconnect() is False
        assert src.state is SourceState.FAILED
        src.release()

    def test_reconnect_refused_after_release(self, sample_video):
        src = RTSPVideoSource("cam", url=sample_video, reconnect_delay=0.0)
        src.release()
        assert src.reconnect() is False
        assert src.state is SourceState.CLOSED
