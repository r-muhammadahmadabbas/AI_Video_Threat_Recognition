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
        assert cfg.min_track_frames == 3
        assert cfg.upright_pose_veto_seconds == 2.0
        assert cfg.min_fall_confidence == 0.60
        assert cfg.weak_fall_confidence == 0.40
        assert cfg.fall_smoothing_decay == 0.5
        assert cfg.min_smoothed_fall_score == 0.60

    def test_rejects_negative_upright_pose_veto(self):
        with pytest.raises(ValueError, match="upright_pose_veto_seconds"):
            PersonDownConfig(upright_pose_veto_seconds=-0.1)

    def test_rejects_weak_fall_edge_above_incident_edge(self):
        with pytest.raises(ValueError, match="weak_fall_confidence"):
            PersonDownConfig(
                min_fall_confidence=0.5, weak_fall_confidence=0.6
            )

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
        *,
        confidence: float = 0.9,
        fall_detected: bool = False,
        fall_confidence: float = 0.0,
        pose_checked: bool = False,
        pose_fall_detected: bool = False,
        frames_seen: int = 10,
    ):
        track = MagicMock(spec=TrackedObject)
        track.tracker_id = tracker_id
        track.bbox = bbox
        track.confidence = confidence
        track.fall_detected = fall_detected
        track.fall_confidence = fall_confidence
        track.pose_checked = pose_checked
        track.pose_fall_detected = pose_fall_detected
        track.frames_seen = frames_seen
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

    def test_repeated_weak_fall_hits_accumulate_into_an_incident(self):
        rule = PersonDownRule(
            rule_id="pd_1",
            rule_name="Person Down",
            zone_id="zone_1",
            zone_name="Test Zone",
            severity="high",
            config=PersonDownConfig(
                aspect_ratio_threshold=1.2,
                min_fall_confidence=0.60,
                weak_fall_confidence=0.40,
                fall_smoothing_decay=0.5,
                min_smoothed_fall_score=0.60,
                cooldown_seconds=10.0,
            ),
        )
        # Upright box: only the fall model can supply evidence.
        bbox = (100.0, 100.0, 200.0, 300.0)

        assert (
            rule.update(
                [self._obs(1, bbox, fall_detected=True, fall_confidence=0.55)],
                timestamp=1.0,
            )
            == []
        )
        triggers = rule.update(
            [self._obs(1, bbox, fall_detected=True, fall_confidence=0.55)],
            timestamp=2.0,
        )

        assert len(triggers) == 1
        details = triggers[0].details
        assert details["evidence"] == "fall_model_smoothed"
        assert details["min_frames_required"] == 1
        assert details["fall_confidence"] == 0.55
        assert details["smoothed_fall_score"] == pytest.approx(0.688, abs=0.001)
        assert details["weak_fall_hits"] == 2
        assert details["min_smoothed_fall_score"] == 0.60

    @pytest.mark.parametrize(
        "hard_negative",
        ["crouching", "sitting", "kneeling"],
    )
    def test_upright_pose_rejects_repeated_weak_fall_hits(
        self, hard_negative
    ):
        rule = PersonDownRule(
            rule_id="pd_1",
            rule_name="Person Down",
            zone_id="zone_1",
            zone_name="Test Zone",
            severity="high",
            config=PersonDownConfig(
                aspect_ratio_threshold=1.2,
                min_frames_down=1,
                min_track_frames=1,
                weak_fall_confidence=0.40,
                min_fall_confidence=0.60,
                min_smoothed_fall_score=0.60,
                upright_pose_veto_seconds=5.0,
            ),
        )
        # Wide box plus a stream of weak fall hits would otherwise reach the
        # smoothed threshold; the upright skeleton keeps it a negative.
        bbox = (100.0, 100.0, 300.0, 200.0)

        for second in range(5):
            triggers = rule.update(
                [
                    self._obs(
                        1,
                        bbox,
                        fall_detected=True,
                        fall_confidence=0.55,
                        pose_checked=True,
                        pose_fall_detected=False,
                    )
                ],
                timestamp=float(second),
            )
            assert triggers == [], hard_negative

    def test_pose_evidence_is_reported_as_pose_not_fall_model(self):
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
            [
                self._obs(
                    1,
                    bbox,
                    fall_detected=True,
                    fall_confidence=0.0,
                    pose_checked=True,
                    pose_fall_detected=True,
                )
            ],
            timestamp=1.0,
        )

        assert len(triggers) == 1
        assert triggers[0].details["evidence"] == "pose"
        assert triggers[0].details["min_frames_required"] == 1
        assert triggers[0].details["pose_checked"] is True

    def test_zero_confidence_fall_flag_without_pose_is_not_evidence(self):
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

        assert triggers == []

    @pytest.mark.parametrize(
        "hard_negative",
        ["crouching", "sitting", "bending", "shooting stance"],
    )
    def test_checked_upright_pose_vetoes_wide_box_hard_negatives(
        self, hard_negative
    ):
        rule = PersonDownRule(
            rule_id="pd_1",
            rule_name="Person Down",
            zone_id="zone_1",
            zone_name="Test Zone",
            severity="high",
            config=PersonDownConfig(
                aspect_ratio_threshold=1.2,
                min_frames_down=1,
                min_track_frames=1,
                upright_pose_veto_seconds=5.0,
            ),
        )
        bbox = (100.0, 100.0, 300.0, 200.0)  # ratio 2.0

        triggers = rule.update(
            [
                self._obs(
                    1,
                    bbox,
                    pose_checked=True,
                    pose_fall_detected=False,
                )
            ],
            timestamp=1.0,
        )

        assert triggers == [], hard_negative

    def test_recent_upright_pose_keeps_vetoing_between_pose_frames(self):
        rule = PersonDownRule(
            rule_id="pd_1",
            rule_name="Person Down",
            zone_id="zone_1",
            zone_name="Test Zone",
            severity="high",
            config=PersonDownConfig(
                aspect_ratio_threshold=1.2,
                min_frames_down=2,
                min_track_frames=1,
                upright_pose_veto_seconds=2.0,
                cooldown_seconds=10.0,
            ),
        )
        bbox = (100.0, 100.0, 300.0, 200.0)  # ratio 2.0

        # Pose runs every few frames. The last upright verdict must keep
        # vetoing the wide box even on frames where pose did not run.
        assert (
            rule.update(
                [self._obs(1, bbox, pose_checked=True)], timestamp=0.0
            )
            == []
        )
        assert rule.update([self._obs(1, bbox)], timestamp=1.0) == []
        assert rule.update([self._obs(1, bbox)], timestamp=2.0) == []

        # Veto expired; geometry now needs its own two-frame persistence.
        assert rule.update([self._obs(1, bbox)], timestamp=4.0) == []
        triggers = rule.update([self._obs(1, bbox)], timestamp=5.0)

        assert len(triggers) == 1
        assert triggers[0].details["evidence"] == "aspect_ratio"

    def test_fallen_pose_clears_upright_veto_immediately(self):
        rule = PersonDownRule(
            rule_id="pd_1",
            rule_name="Person Down",
            zone_id="zone_1",
            zone_name="Test Zone",
            severity="high",
            config=PersonDownConfig(upright_pose_veto_seconds=5.0),
        )
        bbox = (100.0, 100.0, 300.0, 200.0)  # ratio 2.0

        assert (
            rule.update(
                [self._obs(1, bbox, pose_checked=True)], timestamp=1.0
            )
            == []
        )
        triggers = rule.update(
            [
                self._obs(
                    1,
                    bbox,
                    pose_checked=True,
                    pose_fall_detected=True,
                )
            ],
            timestamp=2.0,
        )

        assert len(triggers) == 1
        assert triggers[0].details["evidence"] == "pose"

    def test_confident_fall_model_overrides_upright_pose_veto(self):
        rule = PersonDownRule(
            rule_id="pd_1",
            rule_name="Person Down",
            zone_id="zone_1",
            zone_name="Test Zone",
            severity="high",
            config=PersonDownConfig(upright_pose_veto_seconds=5.0),
        )
        bbox = (100.0, 100.0, 200.0, 300.0)  # upright box

        triggers = rule.update(
            [
                self._obs(
                    1,
                    bbox,
                    fall_detected=True,
                    fall_confidence=0.9,
                    pose_checked=True,
                    pose_fall_detected=False,
                )
            ],
            timestamp=1.0,
        )

        assert len(triggers) == 1
        assert triggers[0].details["evidence"] == "fall_model"

    def test_geometry_waits_for_track_to_persist(self):
        rule = PersonDownRule(
            rule_id="pd_1",
            rule_name="Person Down",
            zone_id="zone_1",
            zone_name="Test Zone",
            severity="high",
            config=PersonDownConfig(
                aspect_ratio_threshold=1.2,
                min_frames_down=1,
                min_track_frames=3,
                cooldown_seconds=10.0,
            ),
        )
        bbox = (100.0, 100.0, 300.0, 200.0)  # ratio 2.0

        assert (
            rule.update(
                [self._obs(1, bbox, frames_seen=1)], timestamp=1.0
            )
            == []
        )
        assert (
            rule.update(
                [self._obs(1, bbox, frames_seen=2)], timestamp=2.0
            )
            == []
        )
        triggers = rule.update(
            [self._obs(1, bbox, frames_seen=3)], timestamp=3.0
        )

        assert len(triggers) == 1
        assert triggers[0].details["evidence"] == "aspect_ratio"

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
