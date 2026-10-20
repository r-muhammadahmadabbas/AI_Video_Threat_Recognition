"""Tests for weapon-detector confidence floors and temporal confirmation."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from workers.cv_worker import weapon_detector


class FakeBox:
    def __init__(self, class_id, confidence, bbox):
        self.cls = np.array([class_id])
        self.conf = np.array([confidence])
        self.xyxy = np.array([bbox], dtype=float)


class FakeYOLO:
    def __init__(self, boxes):
        self._boxes = list(boxes)
        self.calls = 0
        self.last_source = None
        self.last_kwargs = {}

    def predict(self, source, **kwargs):
        self.calls += 1
        self.last_source = source
        self.last_kwargs = kwargs
        return [SimpleNamespace(boxes=self._boxes)]


def build_detector(monkeypatch, boxes, **kwargs):
    monkeypatch.setattr(weapon_detector, "YOLO", lambda _path: FakeYOLO(boxes))
    return weapon_detector.WeaponDetector(model_path="fake.pt", **kwargs)


def frame():
    return np.zeros((32, 32, 3), dtype=np.uint8)


class TestClassThresholds:
    def test_floor_rejects_detections_below_class_threshold(self, monkeypatch):
        detector = build_detector(
            monkeypatch,
            [FakeBox(3, 0.30, [11, 0, 21, 10])],
            class_thresholds={"firearm": 0.35},
        )

        assert detector.detect(frame()) == []

    def test_detection_above_floor_is_kept(self, monkeypatch):
        detector = build_detector(
            monkeypatch,
            [FakeBox(3, 0.40, [11, 0, 21, 10])],
            class_thresholds={"firearm": 0.35},
        )

        detections = detector.detect(frame())

        assert [d.class_name for d in detections] == ["firearm"]

    def test_configured_confidence_raises_the_floor(self, monkeypatch):
        detector = build_detector(
            monkeypatch,
            [FakeBox(3, 0.40, [11, 0, 21, 10])],
            confidence=0.6,
            class_thresholds={"firearm": 0.35},
        )

        assert detector.detect(frame()) == []
        assert detector.threshold_for("firearm") == 0.6

    def test_default_thresholds_apply_per_class(self, monkeypatch):
        detector = build_detector(
            monkeypatch,
            [
                FakeBox(3, 0.34, [11, 0, 21, 10]),
                FakeBox(4, 0.36, [11, 12, 21, 22]),
            ],
        )

        detections = detector.detect(frame())

        assert [d.class_name for d in detections] == ["melee_weapon"]

    def test_non_threat_classes_pass_through_for_analyzer_to_filter(
        self, monkeypatch
    ):
        detector = build_detector(
            monkeypatch,
            [FakeBox(5, 0.45, [11, 0, 21, 10])],
        )

        detections = detector.detect(frame())

        assert [d.class_name for d in detections] == ["person"]
        assert all(not d.is_threat for d in detections)

    def test_flip_pass_runs_at_lowest_effective_threshold(self, monkeypatch):
        detector = build_detector(
            monkeypatch,
            [],
            confidence=0.25,
            class_thresholds={"firearm": 0.5, "melee_weapon": 0.35},
        )

        detector.detect(frame())

        assert detector._run_confidence == 0.35
