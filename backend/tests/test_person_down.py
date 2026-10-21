"""Tests for the person-down rule and config (Sprint 5A/5B)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from workers.cv_worker.rules.base import TrackObservation
from workers.cv_worker.rules.config import PersonDownConfig
from workers.cv_worker.rules.person_down import PersonDownRule
from workers.cv_worker.tracker import TrackedObject


class TestPersonDownConfig:
    """5B: config is validated and rejects nonsense."""

    def test_defaults_build(self):
        cfg = PersonDownConfig()
        assert cfg.aspect_ratio_threshold == 1.2
        assert cfg.min_confidence == 0.25
        assert cfg.cooldown_seconds == 60.0
        assert cfg.min_frames_down == 3

    def test_rejects_aspect_ratio_at_or_below_one(self):
        with pytest.raises(ValueError, match="aspect_ratio_threshold"):
            PersonDownConfig(aspect_ratio_threshold=1.0)
        with pytest.raises(ValueError, match="aspect_ratio_threshold"):
            PersonDownConfig(aspect_ratio_threshold=0.9)

    def test_rejects_negative_cooldown(self):
        with pytest.raises(ValueError, match="cooldown_seconds"):
            PersonDownConfig(cooldown_seconds=-1.0)

    def test_rejects_extra_keys(self):
        with pytest.raises(ValueError, match="unknown_key"):
            PersonDownConfig(unknown_key=123)


class TestPersonDownRule:
    """5A: rule triggers when a track is horizontally elongated."""

    @staticmethod
    def _obs(
        tracker_id: int,
        bbox: tuple[float, float, float, float],
        confidence: float = 0.9,
        fall_detected: bool = False,
        fall_confidence: float = 0.0,
    ):
        track = MagicMock(spec=TrackedObject)
        track.tracker_id = tracker_id
        track.bbox = bbox
        track.confidence = confidence
        track.fall_detected = fall_detected
        track.fall_confidence = fall_confidence
        return TrackObservation(
            track=track,
            inside_expanded=True,
            inside_shrunk=True,
            probe_point=(0.0, 0.0),
        )

    def test_triggers_when_aspect_ratio_exceeds_threshold_for_min_frames(self):
        rule = PersonDownRule(
            rule_id="pd_1",
            rule_name="Person Down",
            zone_id="zone_1",
            zone_name="Test Zone",
            severity="high",
            config=PersonDownConfig(
                aspect_ratio_threshold=1.2,
                min_frames_down=3,
                min_confidence=0.1,
                cooldown_seconds=10.0,
            ),
        )

        # Horizontal bbox: 200 wide, 100 tall -> ratio 2.0 > 1.2
        bbox = (100.0, 100.0, 300.0, 200.0)

        # Frames 1-2: below min_frames_down, no trigger
        triggers = rule.update([self._obs(1, bbox)], timestamp=1.0)
        assert triggers == []

        triggers = rule.update([self._obs(1, bbox)], timestamp=2.0)
        assert triggers == []

        # Frame 3: reaches min_frames_down=3, trigger fires
        triggers = rule.update([self._obs(1, bbox)], timestamp=3.0)
        assert len(triggers) == 1
        t = triggers[0]
        assert t.rule_id == "pd_1"
        assert t.tracker_id == 1
        assert t.details["event"] == "person_down"
        assert t.details["aspect_ratio"] == 2.0
        assert t.details["consecutive_frames_down"] == 3

    def test_no_trigger_when_ratio_below_threshold(self):
        rule = PersonDownRule(
            rule_id="pd_1",
            rule_name="Person Down",
            zone_id="zone_1",
            zone_name="Test Zone",
            severity="high",
            config=PersonDownConfig(aspect_ratio_threshold=1.5, min_frames_down=1),
        )

        # Vertical bbox: 100 wide, 200 tall -> ratio 0.5 < 1.5
        bbox = (100.0, 100.0, 200.0, 300.0)

        triggers = rule.update([self._obs(1, bbox)], timestamp=1.0)
        assert triggers == []

    def test_fall_model_evidence_triggers_immediately(self):
        rule = PersonDownRule(
            rule_id="pd_1",
            rule_name="Person Down",
            zone_id="zone_1",
            zone_name="Test Zone",
            severity="high",
            config=PersonDownConfig(aspect_ratio_threshold=1.2, min_frames_down=3),
        )

        # Upright bbox (ratio 0.5) but the fall model says the person is down.
        bbox = (100.0, 100.0, 200.0, 300.0)

        triggers = rule.update(
            [self._obs(1, bbox, fall_detected=True, fall_confidence=0.9)],
            timestamp=1.0,
        )

        assert len(triggers) == 1
        assert triggers[0].details["evidence"] == "fall_model"
        assert triggers[0].details["min_frames_required"] == 1
        assert triggers[0].details["consecutive_frames_down"] == 1

    def test_weak_fall_model_hit_is_not_an_incident(self):
        rule = PersonDownRule(
            rule_id="pd_1",
            rule_name="Person Down",
            zone_id="zone_1",
            zone_name="Test Zone",
            severity="high",
            config=PersonDownConfig(aspect_ratio_threshold=1.2),
        )
        bbox = (100.0, 100.0, 200.0, 300.0)

        triggers = rule.update(
            [self._obs(1, bbox, fall_detected=True, fall_confidence=0.5)],
            timestamp=1.0,
        )

        assert triggers == []

    def test_pose_evidence_without_model_confidence_still_triggers(self):
        rule = PersonDownRule(
            rule_id="pd_1",
            rule_name="Person Down",
            zone_id="zone_1",
            zone_name="Test Zone",
            severity="high",
            config=PersonDownConfig(aspect_ratio_threshold=1.2),
        )
        bbox = (100.0, 100.0, 200.0, 300.0)

        triggers = rule.update(
            [self._obs(1, bbox, fall_detected=True, fall_confidence=0.0)],
            timestamp=1.0,
        )

        assert len(triggers) == 1

    def test_fall_model_evidence_respects_cooldown(self):
        rule = PersonDownRule(
            rule_id="pd_1",
            rule_name="Person Down",
            zone_id="zone_1",
            zone_name="Test Zone",
            severity="high",
            config=PersonDownConfig(cooldown_seconds=10.0),
        )
        bbox = (100.0, 100.0, 200.0, 300.0)

        first = rule.update(
            [self._obs(1, bbox, fall_detected=True, fall_confidence=0.9)],
            timestamp=1.0,
        )
        second = rule.update(
            [self._obs(1, bbox, fall_detected=True, fall_confidence=0.9)],
            timestamp=5.0,
        )

        assert len(first) == 1
        assert second == []

    def test_cooldown_prevents_immediate_retrigger(self):
        rule = PersonDownRule(
            rule_id="pd_1",
            rule_name="Person Down",
            zone_id="zone_1",
            zone_name="Test Zone",
            severity="high",
            config=PersonDownConfig(
                aspect_ratio_threshold=1.2,
                min_frames_down=1,
                cooldown_seconds=10.0,
            ),
        )
        bbox = (100.0, 100.0, 300.0, 200.0)  # ratio 2.0

        # First trigger
        triggers = rule.update([self._obs(1, bbox)], timestamp=10.0)
        assert len(triggers) == 1

        # Second frame within cooldown -> no trigger
        triggers = rule.update([self._obs(1, bbox)], timestamp=15.0)
        assert triggers == []

        # After cooldown -> triggers again
        triggers = rule.update([self._obs(1, bbox)], timestamp=25.0)
        assert len(triggers) == 1

    def test_confidence_floor(self):
        rule = PersonDownRule(
            rule_id="pd_1",
            rule_name="Person Down",
            zone_id="zone_1",
            zone_name="Test Zone",
            severity="high",
            config=PersonDownConfig(min_confidence=0.5, min_frames_down=1),
        )
        bbox = (100.0, 100.0, 300.0, 200.0)

        # Below confidence floor -> ignored
        triggers = rule.update([self._obs(1, bbox, confidence=0.3)], timestamp=1.0)
        assert triggers == []

        # Above -> triggers
        triggers = rule.update([self._obs(1, bbox, confidence=0.7)], timestamp=2.0)
        assert len(triggers) == 1

    def test_different_tracks_independent(self):
        rule = PersonDownRule(
            rule_id="pd_1",
            rule_name="Person Down",
            zone_id="zone_1",
            zone_name="Test Zone",
            severity="high",
            config=PersonDownConfig(min_frames_down=2, cooldown_seconds=10.0),
        )
        bbox = (100.0, 100.0, 300.0, 200.0)

        # Track 1 fires
        rule.update([self._obs(1, bbox)], timestamp=1.0)
        triggers = rule.update([self._obs(1, bbox)], timestamp=2.0)
        assert len(triggers) == 1

        # Track 2 hasn't accumulated frames yet
        triggers = rule.update([self._obs(2, bbox)], timestamp=3.0)
        assert triggers == []

        # Track 2 fires on its own 2nd frame
        triggers = rule.update([self._obs(2, bbox)], timestamp=4.0)
        assert len(triggers) == 1

    def test_reset_clears_state(self):
        rule = PersonDownRule(
            rule_id="pd_1",
            rule_name="Person Down",
            zone_id="zone_1",
            zone_name="Test Zone",
            severity="high",
            config=PersonDownConfig(min_frames_down=1, cooldown_seconds=10.0),
        )
        bbox = (100.0, 100.0, 300.0, 200.0)

        rule.update([self._obs(1, bbox)], timestamp=1.0)
        rule.reset()

        # After reset, cooldown cleared -> triggers immediately
        triggers = rule.update([self._obs(1, bbox)], timestamp=2.0)
        assert len(triggers) == 1
