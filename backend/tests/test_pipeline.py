import numpy as np
import pytest

from workers.cv_worker.analyzer import FrameAnalysis
from workers.cv_worker.detector import Detection
from workers.cv_worker.pipeline import DetectionPipeline
from workers.cv_worker.weapon_detector import WeaponDetection

FRAME = np.zeros((480, 640, 3), dtype=np.uint8)

WEAPON_BOX = (140.0, 140.0, 160.0, 160.0)


def person(bbox=(100.0, 100.0, 200.0, 300.0), confidence=0.9) -> Detection:
    return Detection(
        bbox=bbox, confidence=confidence, class_id=0, class_name="person"
    )


class FakeAnalyzer:
    def __init__(self) -> None:
        self.persons: list[Detection] = []
        self.weapons: list[WeaponDetection] = []
        self.falls: list[Detection] = []
        self.violence = False
        self.pose = None
        self.resets = 0
        self.calls = 0

    def reset(self) -> None:
        self.resets += 1

    def analyze(self, _frame) -> FrameAnalysis:
        self.calls += 1
        return FrameAnalysis(
            persons=list(self.persons),
            weapons=list(self.weapons),
            falls=list(self.falls),
            violence=self.violence,
            violence_checked=True,
            pose_keypoints=self.pose,
        )


@pytest.fixture
def analyzer() -> FakeAnalyzer:
    return FakeAnalyzer()


@pytest.fixture
def pipeline(analyzer: FakeAnalyzer) -> DetectionPipeline:
    return DetectionPipeline(analyzer=analyzer)


class TestDetectionOutput:
    def test_person_is_reported_with_track_id(self, pipeline, analyzer):
        analyzer.persons = [person()]

        _, detections = pipeline.process_frame(FRAME, 0.0)

        assert len(detections) == 1
        assert detections[0]["class_name"] == "person"
        assert detections[0]["track_id"] >= 0
        assert detections[0]["is_threat"] is False

    def test_weapon_is_reported_and_attached_to_person(self, pipeline, analyzer):
        analyzer.persons = [person()]
        analyzer.weapons = [
            WeaponDetection(class_name="firearm", confidence=0.9, bbox=WEAPON_BOX)
        ]

        _, detections = pipeline.process_frame(FRAME, 0.0)

        person_row = next(d for d in detections if d["class_name"] == "person")
        weapon_row = next(d for d in detections if d["class_name"] == "firearm")

        assert person_row["weapon"] is True
        assert person_row["weapon_conf"] == 0.9
        assert person_row["is_threat"] is True
        assert weapon_row["track_id"] == -1
        assert weapon_row["is_threat"] is True

    def test_horizontal_box_is_reported_as_fall(self, pipeline, analyzer):
        analyzer.persons = [person(bbox=(100.0, 100.0, 300.0, 200.0))]

        _, detections = pipeline.process_frame(FRAME, 0.0)

        assert detections[0]["fall"] is True


class TestRuleEvents:
    def test_weapon_rule_fires_after_dwell(self, pipeline, analyzer):
        analyzer.persons = [person()]
        analyzer.weapons = [
            WeaponDetection(class_name="firearm", confidence=0.9, bbox=WEAPON_BOX)
        ]

        for second in range(6):
            pipeline.process_frame(FRAME, float(second))

        weapon_events = [e for e in pipeline.events if e.rule == "weapon"]
        assert len(weapon_events) == 1
        assert weapon_events[0].timestamp == 5.0
        assert weapon_events[0].severity == "high"
        assert weapon_events[0].tracker_ids == [1]

    def test_unarmed_person_never_emits_weapon_event(self, pipeline, analyzer):
        analyzer.persons = [person()]

        for second in range(10):
            pipeline.process_frame(FRAME, float(second))

        assert [e for e in pipeline.events if e.rule == "weapon"] == []

    def test_person_down_rule_fires_on_horizontal_box(self, pipeline, analyzer):
        analyzer.persons = [person(bbox=(100.0, 100.0, 300.0, 200.0))]

        for second in range(3):
            pipeline.process_frame(FRAME, float(second))

        down_events = [e for e in pipeline.events if e.rule == "person_down"]
        assert len(down_events) == 1
        assert down_events[0].timestamp == 2.0
        assert down_events[0].details["rule_name"] == "Person down"

    def test_wide_box_with_upright_pose_is_not_person_down(
        self, pipeline, analyzer
    ):
        # A crouch, bend or shooting stance can widen the person box. The
        # skeleton still shows a standing posture, so geometry must not raise
        # a person-down incident.
        analyzer.persons = [person(bbox=(100.0, 100.0, 400.0, 300.0))]
        pose = np.zeros((1, 17, 2), dtype=np.float32)
        pose[0][0] = (250.0, 120.0)  # nose
        pose[0][5] = (240.0, 145.0)  # shoulders
        pose[0][6] = (260.0, 145.0)
        pose[0][11] = (240.0, 200.0)  # hips
        pose[0][12] = (260.0, 200.0)
        pose[0][13] = (240.0, 255.0)  # knees
        pose[0][14] = (260.0, 255.0)
        pose[0][15] = (240.0, 290.0)  # ankles
        pose[0][16] = (260.0, 290.0)
        analyzer.pose = pose

        for second in range(5):
            pipeline.process_frame(FRAME, float(second))

        assert [e for e in pipeline.events if e.rule == "person_down"] == []

    def test_violence_is_emitted_once_per_episode(self, pipeline, analyzer):
        analyzer.persons = [person()]

        analyzer.violence = True
        for second in range(3):
            pipeline.process_frame(FRAME, float(second))

        # One missed classifier frame does not split the episode.
        analyzer.violence = False
        pipeline.process_frame(FRAME, 3.0)
        analyzer.violence = True
        pipeline.process_frame(FRAME, 4.0)
        pipeline.process_frame(FRAME, 5.0)

        # A sustained run of negatives closes it, so the next fight is new.
        analyzer.violence = False
        pipeline.process_frame(FRAME, 6.0)
        pipeline.process_frame(FRAME, 7.0)
        analyzer.violence = True
        pipeline.process_frame(FRAME, 8.0)
        pipeline.process_frame(FRAME, 9.0)

        violence_events = [
            e for e in pipeline.events if e.rule == "violence_detected"
        ]
        assert len(violence_events) == 2
        assert violence_events[0].tracker_ids == [1]
        assert violence_events[0].details["positive_hits"] == 2
        assert violence_events[0].details["smoothed_score"] == 0.75
        assert violence_events[1].timestamp == 9.0

    def test_single_negative_does_not_reset_smoothed_evidence(
        self, pipeline, analyzer
    ):
        analyzer.violence = True
        pipeline.process_frame(FRAME, 0.0)
        analyzer.violence = False
        pipeline.process_frame(FRAME, 1.0)
        analyzer.violence = True
        pipeline.process_frame(FRAME, 2.0)

        violence_events = [
            e for e in pipeline.events if e.rule == "violence_detected"
        ]
        assert len(violence_events) == 1
        assert violence_events[0].timestamp == 2.0
        assert violence_events[0].details["positive_hits"] == 2
        assert violence_events[0].details["smoothed_score"] == 0.625

    def test_single_frame_violence_hit_is_ignored(self, pipeline, analyzer):
        analyzer.violence = True
        pipeline.process_frame(FRAME, 0.0)
        analyzer.violence = False
        pipeline.process_frame(FRAME, 1.0)

        assert not [e for e in pipeline.events if e.rule == "violence_detected"]

    def test_fall_evidence_suppresses_violence(self, pipeline, analyzer):
        analyzer.persons = [person()]
        analyzer.falls = [person()]
        analyzer.violence = True
        pipeline.process_frame(FRAME, 0.0)
        pipeline.process_frame(FRAME, 1.0)

        assert not [e for e in pipeline.events if e.rule == "violence_detected"]

        analyzer.falls = []
        pipeline.process_frame(FRAME, 5.0)
        pipeline.process_frame(FRAME, 6.0)
        violence_events = [
            e for e in pipeline.events if e.rule == "violence_detected"
        ]
        assert len(violence_events) == 1


class TestSessionReset:
    def test_reset_clears_events_and_analyzer_state(self, pipeline, analyzer):
        analyzer.persons = [person()]
        analyzer.weapons = [
            WeaponDetection(class_name="firearm", confidence=0.9, bbox=WEAPON_BOX)
        ]
        for second in range(6):
            pipeline.process_frame(FRAME, float(second))
        assert pipeline.events

        pipeline.reset_session()

        assert pipeline.events == []
        assert analyzer.resets == 1
        assert pipeline._last_timestamp is None

    def test_next_clip_can_have_a_different_resolution(self, pipeline, analyzer):
        analyzer.persons = [person()]
        pipeline.process_frame(FRAME, 0.0)

        pipeline.reset_session()

        analyzer.persons = [person(bbox=(200.0, 200.0, 400.0, 600.0))]
        _, detections = pipeline.process_frame(
            np.zeros((720, 1280, 3), dtype=np.uint8), 0.0
        )

        assert len(detections) == 1
