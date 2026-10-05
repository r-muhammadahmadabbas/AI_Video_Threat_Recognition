import os
import tempfile
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

from workers.cv_worker.main import CVWorker
from workers.cv_worker.video_source import Frame


def _create_test_video(path: str, frames: int = 5, width: int = 320, height: int = 240) -> None:
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(path, fourcc, 30.0, (width, height))
    for _ in range(frames):
        frame = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
        writer.write(frame)
    writer.release()


@pytest.fixture
def sample_video():
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        path = f.name
    _create_test_video(path)
    yield path
    os.unlink(path)


class TestCVWorker:
    @patch("workers.cv_worker.main.YOLO26Detector")
    def test_worker_initialization(self, mock_detector_cls, sample_video):
        mock_detector = MagicMock()
        mock_detector_cls.return_value = mock_detector

        worker = CVWorker(
            source_id="test_cam",
            source_path=sample_video,
            display=False,
        )
        assert worker._source_id == "test_cam"
        assert worker._running is False
        assert worker._processed_frames == 0

    @patch("workers.cv_worker.main.YOLO26Detector")
    def test_worker_processes_frames(self, mock_detector_cls, sample_video):
        mock_detector = MagicMock()
        mock_detector.detect.return_value = []
        mock_detector_cls.return_value = mock_detector

        worker = CVWorker(
            source_id="test_cam",
            source_path=sample_video,
            display=False,
        )
        worker._video_source = worker._create_source()
        worker._detector = mock_detector

        frame = worker._video_source.read()
        assert frame is not None

        worker._process_frame(frame)
        assert worker._processed_frames == 1
        mock_detector.detect.assert_called_once()

    @patch("workers.cv_worker.main.YOLO26Detector")
    def test_worker_emits_events(self, mock_detector_cls, sample_video):
        from workers.cv_worker.detector import Detection

        mock_detector = MagicMock()
        mock_detector.detect.return_value = [
            Detection(bbox=(10, 10, 50, 100), confidence=0.9, class_id=0, class_name="person")
        ]
        mock_detector_cls.return_value = mock_detector

        worker = CVWorker(
            source_id="test_cam",
            source_path=sample_video,
            display=False,
        )
        worker._video_source = worker._create_source()
        worker._detector = mock_detector

        frame = worker._video_source.read()
        worker._process_frame(frame)

        assert worker._emitted_events == 1

    @patch("workers.cv_worker.main.YOLO26Detector")
    def test_worker_stops_cleanly(self, mock_detector_cls, sample_video):
        mock_detector = MagicMock()
        mock_detector.detect.return_value = []
        mock_detector_cls.return_value = mock_detector

        worker = CVWorker(
            source_id="test_cam",
            source_path=sample_video,
            display=False,
        )
        worker._video_source = worker._create_source()
        worker._detector = mock_detector
        worker._running = True

        worker.stop()
        assert worker._running is False