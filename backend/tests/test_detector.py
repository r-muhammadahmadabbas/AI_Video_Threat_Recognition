import numpy as np
import pytest

from workers.cv_worker.detector import Detection, YOLO26Detector


class TestDetection:
    def test_center(self):
        d = Detection(bbox=(10, 20, 30, 40), confidence=0.9, class_id=0, class_name="person")
        assert d.center == (20, 30)

    def test_bottom_center(self):
        d = Detection(bbox=(10, 20, 30, 40), confidence=0.9, class_id=0, class_name="person")
        assert d.bottom_center == (20, 40)

    def test_area(self):
        d = Detection(bbox=(0, 0, 10, 20), confidence=0.9, class_id=0, class_name="person")
        assert d.area == 200.0


class TestYOLO26Detector:
    @pytest.fixture(scope="class")
    def detector(self):
        return YOLO26Detector(model_name="yolo26n", confidence=0.25, device="cpu")

    def test_model_name(self, detector):
        assert detector.get_model_name() == "yolo26n"

    def test_model_version(self, detector):
        assert detector.get_model_version() == "1.0"

    def test_detect_returns_list(self, detector):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        results = detector.detect(frame)
        assert isinstance(results, list)

    def test_detect_person_class_filter(self, detector):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        results = detector.detect(frame)
        for d in results:
            assert isinstance(d, Detection)
            assert 0 <= d.confidence <= 1.0
            assert len(d.bbox) == 4