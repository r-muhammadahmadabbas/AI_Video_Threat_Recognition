import os
import tempfile

import cv2
import numpy as np
import pytest

from workers.cv_worker.video_source import Frame, MP4VideoSource, WebcamVideoSource


def _create_test_video(path: str, frames: int = 10, width: int = 640, height: int = 480, fps: int = 30) -> None:
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
    os.unlink(path)


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