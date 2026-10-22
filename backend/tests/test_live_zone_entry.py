"""Live camera-path evaluation for restricted-zone entry."""

from __future__ import annotations

import numpy as np
import pytest

from scripts.eval.live_zone_entry import TrackSample, evaluate_zone_entry
from scripts.eval.metrics import EventInterval, evaluate_events
from scripts.eval.schema import load_event_gt, save_clip_events
from workers.cv_worker.detector import Detection
from workers.cv_worker.main import CVWorker
from workers.cv_worker.rules.base import Zone
from workers.cv_worker.rules.config import ZoneConfig, ZoneEntryConfig
from workers.cv_worker.rules.geometry import Polygon
from workers.cv_worker.rules.restricted_zone import ZoneEntryRule
from workers.cv_worker.tracker import ByteTrackTracker
from workers.cv_worker.video_source import Frame

WIDTH, HEIGHT = 640, 480
RULE_ID = "restricted_zone_entry"


def pixel_zone() -> Zone:
    """Rectangle at x=200..400, y=100..380 in a 640x480 frame."""
    return Zone(
        zone_id="zone_1",
        name="Restricted Area",
        polygon=Polygon.from_bbox(200, 100, 400, 380),
        config=ZoneConfig(
            coordinate_space="pixel",
            reference_width=WIDTH,
            reference_height=HEIGHT,
        ),
    )


def entry_config() -> ZoneEntryConfig:
    return ZoneEntryConfig(min_frames_in_zone=1, cooldown_seconds=0.0)


def walk(centers: list[float]) -> list[TrackSample]:
    """One person-shaped box per timestamp, with the given bottom-center x."""
    return [
        TrackSample(
            timestamp=float(index),
            tracker_id=1,
            bbox=(center - 40.0, 140.0, center + 40.0, 300.0),
        )
        for index, center in enumerate(centers)
    ]


def evaluate(samples, zone, clip="clip"):
    return evaluate_zone_entry(
        samples,
        zone,
        frame_width=WIDTH,
        frame_height=HEIGHT,
        config=entry_config(),
        clip=clip,
    )


class TestGeometry:
    def test_concave_normalized_zone_excludes_the_notch(self):
        zone = Zone(
            zone_id="lobby",
            name="L-shaped lobby",
            polygon=Polygon.from_vertices(
                [
                    (0.1, 0.1),
                    (0.6, 0.1),
                    (0.6, 0.3),
                    (0.3, 0.3),
                    (0.3, 0.7),
                    (0.1, 0.7),
                ]
            ),
            config=ZoneConfig(),
        )

        # Bottom centers at (320, 288) in the notch and (128, 240) in the arm.
        notch = [TrackSample(0.0, 1, (280.0, 100.0, 360.0, 288.0))]
        arm = [TrackSample(0.0, 1, (88.0, 100.0, 168.0, 240.0))]

        assert evaluate(notch, zone).events == []
        assert len(evaluate(arm, zone).events) == 1


class TestEntryDirection:
    def test_moving_only_outside_never_triggers(self):
        result = evaluate(walk([470.0, 490.0, 510.0, 530.0]), pixel_zone())
        assert result.events == []

    def test_crossing_inward_triggers_at_the_inside_frame(self):
        result = evaluate(walk([470.0, 450.0, 430.0, 410.0, 390.0, 370.0]), pixel_zone())

        assert [event.start for event in result.events] == [pytest.approx(4.0)]
        assert result.triggers[0].timestamp == pytest.approx(4.0)

    def test_reentry_from_outside_triggers_again(self):
        result = evaluate(
            walk(
                [
                    470.0,
                    450.0,
                    430.0,
                    410.0,
                    390.0,
                    370.0,
                    390.0,
                    410.0,
                    430.0,
                    410.0,
                    390.0,
                ]
            ),
            pixel_zone(),
        )

        assert [event.start for event in result.events] == [
            pytest.approx(4.0),
            pytest.approx(10.0),
        ]


class TestEventMatching:
    def test_live_events_match_gt_and_round_trip_through_schema(self, tmp_path):
        result = evaluate(
            walk([470.0, 450.0, 430.0, 410.0, 390.0, 370.0]),
            pixel_zone(),
            clip="entry.mp4",
        )
        path = tmp_path / "live_zone_entry.jsonl"

        save_clip_events(path, {result.clip: result.to_clip_events()})
        loaded = load_event_gt(path)["entry.mp4"]
        scored = evaluate_events(
            [EventInterval(RULE_ID, 4.0, 5.0)],
            result.events,
            iou_threshold=0.001,
            duration_seconds=result.duration,
        )

        assert loaded.duration == pytest.approx(result.duration)
        assert loaded.events == result.events
        assert scored.per_type[RULE_ID].true_positives == 1
        assert scored.per_type[RULE_ID].false_positives == 0
        assert scored.per_type[RULE_ID].false_negatives == 0


class _SequenceDetector:
    def __init__(self, bboxes):
        self._bboxes = bboxes
        self._index = 0

    def detect(self, _frame):
        bbox = self._bboxes[min(self._index, len(self._bboxes) - 1)]
        self._index += 1
        return [Detection(bbox=bbox, confidence=0.9, class_id=0, class_name="person")]


class _RecordingSink:
    def __init__(self):
        self.records = []

    def record(self, record):
        self.records.append(record)
        return len(self.records)

    def attach_evidence(self, incident_id, attachment):
        del incident_id, attachment


class TestLiveWorkerPath:
    def test_entry_becomes_one_matching_incident(self):
        sink = _RecordingSink()
        # Small steps keep ByteTrack's IoU association on one tracker id.
        bboxes = [
            (center - 40.0, 140.0, center + 40.0, 300.0)
            for center in (470.0 - 5.0 * index for index in range(17))
        ]
        rule = ZoneEntryRule(
            rule_id=RULE_ID,
            rule_name="No entry to server room",
            zone_id="zone_1",
            zone_name="Restricted Area",
            severity="high",
            config=entry_config(),
        )
        worker = CVWorker(
            source_id="test_cam",
            source_path="unused.mp4",
            display=False,
            zones=[pixel_zone()],
            rules=[rule],
            camera_id=7,
            incident_sink=sink,
        )
        worker._detector = _SequenceDetector(bboxes)
        worker._tracker = ByteTrackTracker(frame_rate=30.0)

        for index in range(len(bboxes)):
            worker._process_frame(
                Frame(
                    data=np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8),
                    timestamp=float(index),
                    frame_number=index + 1,
                    source_id="test_cam",
                )
            )

        assert worker._emitted_triggers == 1
        assert worker._recorded_incidents == 1
        record = sink.records[0]
        assert record.camera_id == 7
        assert record.event_type == RULE_ID
        assert record.metadata["zone_id"] == "zone_1"
        assert record.metadata["details"]["event"] == RULE_ID
        assert record.track_ids == (record.metadata["tracker_id"],)
