import numpy as np
import pytest

from workers.cv_worker.detector import Detection
from workers.cv_worker.event_adapter import EventCandidate, PersonPresenceAdapter
from workers.cv_worker.video_source import Frame


@pytest.fixture
def sample_frame():
    return Frame(
        data=np.zeros((480, 640, 3), dtype=np.uint8),
        timestamp=1000.0,
        frame_number=1,
        source_id="cam_1",
    )


@pytest.fixture
def person_detections():
    return [
        Detection(bbox=(100, 100, 200, 300), confidence=0.9, class_id=0, class_name="person"),
        Detection(bbox=(300, 150, 400, 350), confidence=0.8, class_id=0, class_name="person"),
    ]


class TestPersonPresenceAdapter:
    def test_no_persons_returns_empty(self, sample_frame):
        adapter = PersonPresenceAdapter()
        result = adapter.process(sample_frame, [])
        assert result == []

    def test_persons_create_event(self, sample_frame, person_detections):
        adapter = PersonPresenceAdapter()
        events = adapter.process(sample_frame, person_detections)
        assert len(events) == 1
        event = events[0]
        assert event.event_type == "person_presence"
        assert event.source_id == "cam_1"
        assert event.confidence == 0.9
        assert event.metadata["person_count"] == 2

    def test_low_confidence_filtered(self, sample_frame):
        low_conf = [Detection(bbox=(10, 10, 50, 50), confidence=0.1, class_id=0, class_name="person")]
        adapter = PersonPresenceAdapter(min_confidence=0.25)
        events = adapter.process(sample_frame, low_conf)
        assert events == []

    def test_non_person_classes_ignored(self, sample_frame):
        car = [Detection(bbox=(10, 10, 100, 100), confidence=0.95, class_id=2, class_name="car")]
        adapter = PersonPresenceAdapter()
        events = adapter.process(sample_frame, car)
        assert events == []

    def test_event_to_dict(self, sample_frame, person_detections):
        adapter = PersonPresenceAdapter()
        events = adapter.process(sample_frame, person_detections)
        d = events[0].to_dict()
        assert d["event_type"] == "person_presence"
        assert d["source_id"] == "cam_1"
        assert len(d["detections"]) == 2
        assert d["detections"][0]["class_name"] == "person"