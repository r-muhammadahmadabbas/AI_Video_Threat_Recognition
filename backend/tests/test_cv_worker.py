import os
import tempfile
import time
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

from app.config import settings
from workers.cv_worker.detector import Detection
from workers.cv_worker.main import CVWorker
from workers.cv_worker.rules.base import Zone
from workers.cv_worker.rules.config import ZoneConfig, ZoneEntryConfig
from workers.cv_worker.rules.geometry import Polygon
from workers.cv_worker.rules.restricted_zone import ZoneEntryRule
from workers.cv_worker.tracker import ByteTrackTracker


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
    _remove_video(path)


def _remove_video(path: str) -> None:
    """Best-effort delete; OpenCV may still hold the file handle on Windows."""
    import gc

    for _ in range(5):
        try:
            os.unlink(path)
            return
        except PermissionError:
            gc.collect()
            time.sleep(0.1)
        except OSError:
            return


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


def _person(x: float, y: float = 100.0, w: float = 100.0, h: float = 200.0):
    from workers.cv_worker.detector import Detection

    return Detection(
        bbox=(x, y, x + w, y + h),
        confidence=0.9,
        class_id=0,
        class_name="person",
    )


class TestCVWorkerTracking:
    @patch("workers.cv_worker.main.YOLO26Detector")
    def test_tracking_disabled_by_default_flag(self, mock_detector_cls, sample_video):
        mock_detector = MagicMock()
        mock_detector.detect.return_value = []
        mock_detector_cls.return_value = mock_detector

        worker = CVWorker(
            source_id="test_cam",
            source_path=sample_video,
            display=False,
            enable_tracking=False,
        )
        assert worker._tracker is None
        assert worker._enable_tracking is False

    @patch("workers.cv_worker.main.YOLO26Detector")
    def test_tracker_assigned_when_enabled(self, mock_detector_cls, sample_video):
        mock_detector = MagicMock()
        mock_detector.detect.return_value = []
        mock_detector_cls.return_value = mock_detector

        worker = CVWorker(
            source_id="test_cam",
            source_path=sample_video,
            display=False,
            enable_tracking=True,
        )
        worker._video_source = worker._create_source()
        worker._tracker = ByteTrackTracker(frame_rate=30.0)
        assert worker._tracker is not None

    @patch("workers.cv_worker.main.YOLO26Detector")
    def test_process_frame_populates_snapshot(self, mock_detector_cls, sample_video):
        mock_detector = MagicMock()
        mock_detector.detect.return_value = [_person(0.0)]
        mock_detector_cls.return_value = mock_detector

        worker = CVWorker(
            source_id="test_cam",
            source_path=sample_video,
            display=False,
            enable_tracking=True,
        )
        worker._video_source = worker._create_source()
        worker._detector = mock_detector
        worker._tracker = ByteTrackTracker(frame_rate=30.0)

        frame = worker._video_source.read()
        worker._process_frame(frame)

        assert worker._tracker.active_track_count == 1

    @patch("workers.cv_worker.main.YOLO26Detector")
    def test_tracker_isolated_per_worker(self, mock_detector_cls, sample_video):
        mock_detector = MagicMock()
        mock_detector.detect.return_value = [_person(0.0)]
        mock_detector_cls.return_value = mock_detector

        cam_a = CVWorker(source_id="cam_a", source_path=sample_video, display=False)
        cam_b = CVWorker(source_id="cam_b", source_path=sample_video, display=False)
        cam_a._video_source = cam_a._create_source()
        cam_b._video_source = cam_b._create_source()
        cam_a._detector = mock_detector
        cam_b._detector = mock_detector
        cam_a._tracker = ByteTrackTracker(frame_rate=30.0)
        cam_b._tracker = ByteTrackTracker(frame_rate=30.0)

        frame_a = cam_a._video_source.read()
        cam_a._process_frame(frame_a)

        assert cam_a._tracker.active_track_count == 1
        assert cam_b._tracker.active_track_count == 0

    @patch("workers.cv_worker.main.YOLO26Detector")
    def test_stop_resets_tracker(self, mock_detector_cls, sample_video):
        mock_detector = MagicMock()
        mock_detector.detect.return_value = [_person(0.0)]
        mock_detector_cls.return_value = mock_detector

        worker = CVWorker(source_id="test_cam", source_path=sample_video, display=False)
        worker._video_source = worker._create_source()
        worker._detector = mock_detector
        worker._tracker = ByteTrackTracker(frame_rate=30.0)

        worker._process_frame(worker._video_source.read())
        assert worker._tracker.active_track_count == 1

        worker.stop()
        assert worker._tracker.active_track_count == 0


class TestFrameSelection:
    """Offline replay must be deterministic so accuracy numbers are repeatable."""

    @pytest.fixture
    def long_video(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            path = f.name
        _create_test_video(path, frames=60)
        yield path
        _remove_video(path)

    def _file_worker(self, path):
        with patch("workers.cv_worker.main.YOLO26Detector"):
            worker = CVWorker(
                source_id="test_cam", source_path=path, source_type="file", display=False
            )
        worker._video_source = worker._create_source()
        return worker

    def _selected_frame_numbers(self, path):
        worker = self._file_worker(path)
        try:
            return [
                f.frame_number
                for f in _iter_all_frames(worker)
                if worker._should_process(f)
            ]
        finally:
            worker._video_source.release()

    def test_file_source_skips_frames_deterministically(self, long_video):
        source_fps = 30.0
        total_frames = 60
        step = max(1, round(source_fps / settings.model.inference_target_fps))
        assert step > 1, "fixture must be long enough to exercise frame skipping"

        first_pass = self._selected_frame_numbers(long_video)
        second_pass = self._selected_frame_numbers(long_video)

        expected = [n for n in range(1, total_frames + 1) if n % step == 0]
        assert expected, "fixture must yield a non-empty selection"
        assert first_pass == expected
        assert first_pass == second_pass
        assert all(n % step == 0 for n in first_pass)

    def test_file_source_reduces_frame_count(self, long_video):
        worker = self._file_worker(long_video)
        try:
            all_frames = list(_iter_all_frames(worker))
        finally:
            worker._video_source.release()

        selected = self._selected_frame_numbers(long_video)
        assert 0 < len(selected) < len(all_frames)

    def test_live_source_uses_wall_clock_throttle(self):
        with patch("workers.cv_worker.main.YOLO26Detector"):
            worker = CVWorker(
                source_id="cam",
                source_path="rtsp://example/stream",
                source_type="rtsp",
                display=False,
            )
        worker._video_source = MagicMock()
        worker._video_source.get_fps.return_value = 30.0

        first = MagicMock()
        first.frame_number = 1
        assert worker._should_process(first) is True

        second = MagicMock()
        second.frame_number = 2
        assert worker._should_process(second) is False


def _iter_all_frames(worker):
    while True:
        frame = worker._video_source.read()
        if frame is None:
            return
        yield frame


class TestCVWorkerRuleEngine:
    """End-to-end: detections -> tracks -> zone rules -> one incident."""

    @staticmethod
    def _zone():
        # 320x240 clip, zone occupies the middle of the frame.
        return Zone(
            zone_id="zone_1",
            name="Restricted Area",
            polygon=Polygon.from_bbox(50, 50, 250, 200),
            config=ZoneConfig(
                coordinate_space="pixel",
                reference_width=320,
                reference_height=240,
            ),
        )

    @staticmethod
    def _rule(**overrides):
        kwargs = {
            "rule_id": "rule_entry",
            "rule_name": "No entry to server room",
            "zone_id": "zone_1",
            "zone_name": "Restricted Area",
            "severity": "high",
            "config": ZoneEntryConfig(min_frames_in_zone=1, cooldown_seconds=60.0),
        }
        kwargs.update(overrides)
        return ZoneEntryRule(**kwargs)

    @staticmethod
    def _detection(bbox, confidence: float = 0.9):
        return Detection(
            bbox=bbox, confidence=confidence, class_id=0, class_name="person"
        )

    # bottom_center lands at (150, 160), inside the zone's 50..250 x 50..200.
    INSIDE = (100.0, 60.0, 200.0, 160.0)
    # bottom_center lands at (280, 160), past the zone's right edge.
    OUTSIDE = (230.0, 60.0, 330.0, 160.0)

    @pytest.fixture
    def rule_video(self):
        """Long enough that frame skipping still selects several frames.

        Frame selection steps by ``round(source_fps / inference_target_fps)``,
        so a clip shorter than that step yields no processed frames at all and
        would silently assert nothing.
        """
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            path = f.name
        _create_test_video(path, frames=60)
        yield path
        _remove_video(path)

    @staticmethod
    def _worker(sample_video, detection, zones=None, rules=None):
        mock_detector = MagicMock()
        mock_detector.detect.return_value = [detection]

        worker = CVWorker(
            source_id="test_cam",
            source_path=sample_video,
            display=False,
            zones=zones,
            rules=rules,
        )
        worker._video_source = worker._create_source()
        worker._detector = mock_detector
        worker._tracker = ByteTrackTracker(frame_rate=30.0)
        return worker

    def test_no_rules_leaves_engine_unbuilt(self, sample_video):
        worker = self._worker(sample_video, self._detection(self.INSIDE))
        worker._process_frame(worker._video_source.read())
        assert worker._rule_engine is None
        assert worker._emitted_triggers == 0

    def test_engine_built_lazily_at_frame_size(self, sample_video):
        worker = self._worker(
            sample_video,
            self._detection(self.INSIDE),
            zones=[self._zone()],
            rules=[self._rule()],
        )
        worker._process_frame(worker._video_source.read())

        assert worker._rule_engine is not None
        assert worker._rule_engine.frame_width == 320
        assert worker._rule_engine.frame_height == 240

    def test_single_incident_despite_repeated_frames(self, rule_video):
        worker = self._worker(
            rule_video,
            self._detection(self.INSIDE),
            zones=[self._zone()],
            rules=[self._rule()],
        )

        for frame in _iter_all_frames(worker):
            if worker._should_process(frame):
                worker._process_frame(frame)

        # Every processed frame saw the same subject inside the same zone, but
        # that is one incident, not one per frame.
        assert worker._emitted_triggers == 1

    def test_person_outside_zone_is_silent(self, rule_video):
        worker = self._worker(
            rule_video,
            self._detection(self.OUTSIDE),
            zones=[self._zone()],
            rules=[self._rule()],
        )
        for frame in _iter_all_frames(worker):
            if worker._should_process(frame):
                worker._process_frame(frame)

        assert worker._emitted_triggers == 0

    def test_stop_resets_rule_engine(self, sample_video):
        worker = self._worker(
            sample_video,
            self._detection(self.INSIDE),
            zones=[self._zone()],
            rules=[self._rule()],
        )
        worker._process_frame(worker._video_source.read())
        assert worker._emitted_triggers == 1

        worker.stop()
        assert worker._rule_engine.zone_ids == ["zone_1"]
        assert worker._rule_engine._last_incident == {}
