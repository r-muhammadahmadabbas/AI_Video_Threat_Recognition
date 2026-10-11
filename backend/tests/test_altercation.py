"""Tests for the physical-altercation candidate rule and config (Sprint 6A/6B)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from workers.cv_worker.rules.altercation import AltercationRule
from workers.cv_worker.rules.base import TrackObservation
from workers.cv_worker.rules.config import AltercationConfig
from workers.cv_worker.tracker import TrackedObject


def make_config(**overrides) -> AltercationConfig:
    """A permissive config so tests exercise the rule, not the thresholds."""
    base = {
        "max_pair_distance_px": 100.0,
        "min_movement_px_per_s": 5.0,
        "min_relative_speed_px_per_s": 10.0,
        "speed_window_seconds": 1.0,
        "min_aggression_frames": 3,
        "min_confidence": 0.1,
        "cooldown_seconds": 100.0,
    }
    base.update(overrides)
    return AltercationConfig(**base)


class TestAltercationConfig:
    """6A/6C: config is validated and rejects nonsense thresholds."""

    def test_defaults_build(self):
        cfg = AltercationConfig()
        assert cfg.max_pair_distance_px == 150.0
        assert cfg.min_movement_px_per_s == 20.0
        assert cfg.min_relative_speed_px_per_s == 60.0
        assert cfg.speed_window_seconds == 1.0
        assert cfg.min_aggression_frames == 5
        assert cfg.min_confidence == 0.25
        assert cfg.cooldown_seconds == 180.0

    def test_rejects_bad_pair_distance(self):
        with pytest.raises(ValueError, match="max_pair_distance_px"):
            AltercationConfig(max_pair_distance_px=-100.0)
        with pytest.raises(ValueError, match="max_pair_distance_px"):
            AltercationConfig(max_pair_distance_px=0.0)

    def test_rejects_negative_speed_thresholds(self):
        with pytest.raises(ValueError, match="min_movement_px_per_s"):
            AltercationConfig(min_movement_px_per_s=-1.0)
        with pytest.raises(ValueError, match="min_relative_speed_px_per_s"):
            AltercationConfig(min_relative_speed_px_per_s=-5.0)

    def test_rejects_zero_or_negative_speed_window(self):
        with pytest.raises(ValueError, match="speed_window_seconds"):
            AltercationConfig(speed_window_seconds=0.0)

    def test_rejects_zero_aggression_frames(self):
        with pytest.raises(ValueError, match="min_aggression_frames"):
            AltercationConfig(min_aggression_frames=0)

    def test_rejects_negative_cooldown(self):
        with pytest.raises(ValueError, match="cooldown_seconds"):
            AltercationConfig(cooldown_seconds=-1.0)

    def test_rejects_inverted_hysteresis(self):
        with pytest.raises(ValueError, match="exit_margin"):
            AltercationConfig(entry_margin=1.02, exit_margin=1.05)

    def test_rejects_extra_keys(self):
        with pytest.raises(ValueError, match="unknown_key"):
            AltercationConfig(unknown_key=123)


class TestAltercationRule:
    """6B: triggers only for nearby pairs with persistent active motion."""

    @staticmethod
    def _obs(
        tracker_id: int,
        center: tuple[float, float],
        confidence: float = 0.9,
        inside: tuple[bool, bool] = (True, True),
    ):
        """A 20x60 bbox centred on ``center``; inside flags default to in-zone."""
        cx, cy = center
        track = MagicMock(spec=TrackedObject)
        track.tracker_id = tracker_id
        track.bbox = (cx - 10.0, cy - 60.0, cx + 10.0, cy)
        track.confidence = confidence
        track.center = (cx, cy)
        track.bottom_center = (cx, cy)
        return TrackObservation(
            track=track,
            inside_expanded=inside[0],
            inside_shrunk=inside[1],
            probe_point=(cx, cy),
        )

    @staticmethod
    def _rule(**overrides) -> AltercationRule:
        return AltercationRule(
            rule_id="fight_1",
            rule_name="Physical Altercation",
            zone_id="zone_1",
            zone_name="Test Zone",
            severity="high",
            config=make_config(**overrides),
        )

    def test_triggers_when_pair_close_and_both_move(self):
        rule = self._rule()
        # A and B converge: A right 6px/frame, B left 6px/frame, 1s between frames.
        centers_a = [(300 + 6 * i, 240) for i in range(8)]
        centers_b = [(360 - 6 * i, 240) for i in range(8)]

        # Frames up to the minimum: no trigger yet (first frame can't compute speed).
        for i in range(3):
            triggers = rule.update(
                [self._obs(1, centers_a[i]), self._obs(2, centers_b[i])],
                timestamp=float(i + 1),
            )
            assert triggers == []

        triggers = rule.update(
            [self._obs(1, centers_a[3]), self._obs(2, centers_b[3])],
            timestamp=4.0,
        )
        assert len(triggers) == 1
        t = triggers[0]
        assert t.rule_id == "fight_1"
        assert t.tracker_id == 1
        assert t.details["event"] == "physical_altercation"
        assert t.details["tracker_ids"] == [1, 2]
        assert t.details["pair_tracker_id"] == 2
        assert t.details["window_seconds"] == 1.0
        assert t.details["aggressive_frames"] == 3

    def test_pair_far_apart_never_triggers(self):
        rule = self._rule()
        centers_a = [(100 + 6 * i, 240) for i in range(8)]
        centers_b = [(500 - 6 * i, 240) for i in range(8)]  # still ~360px apart

        for i in range(8):
            triggers = rule.update(
                [self._obs(1, centers_a[i]), self._obs(2, centers_b[i])],
                timestamp=float(i + 1),
            )
            assert triggers == []

    def test_single_track_never_triggers(self):
        rule = self._rule()
        for i in range(8):
            triggers = rule.update([self._obs(1, (300 + 6 * i, 240))], timestamp=float(i + 1))
            assert triggers == []

    def test_standing_close_does_not_trigger(self):
        rule = self._rule()
        # Close but stationary -> both-move signal fails every frame.
        for i in range(8):
            triggers = rule.update(
                [self._obs(1, (300, 240)), self._obs(2, (330, 240))],
                timestamp=float(i + 1),
            )
            assert triggers == []

    def test_interrupted_proximity_resets_pair(self):
        rule = self._rule()
        centers_a = [(300 + 6 * i, 240) for i in range(8)]
        centers_b = [(360 - 6 * i, 240) for i in range(8)]

        # Build up 2 aggression frames.
        for i in range(2):
            rule.update(
                [self._obs(1, centers_a[i]), self._obs(2, centers_b[i])],
                timestamp=float(i + 1),
            )

        # One frame far apart -> state resets.
        rule.update(
            [self._obs(1, (100, 240)), self._obs(2, (500, 240))],
            timestamp=3.0,
        )

        # Re-approach needs the full window again: t=4 (no speed), t=5 and t=6
        # accumulate 1 and 2 aggression frames respectively -> no trigger yet.
        for i in range(3, 6):
            triggers = rule.update(
                [self._obs(1, centers_a[i]), self._obs(2, centers_b[i])],
                timestamp=float(i + 1),
            )
            assert triggers == []

        # t=7 -> third aggression frame -> trigger.
        triggers = rule.update(
            [self._obs(1, centers_a[6]), self._obs(2, centers_b[6])],
            timestamp=7.0,
        )
        assert len(triggers) == 1

    def test_cooldown_prevents_immediate_retrigger(self):
        rule = self._rule(cooldown_seconds=5.0)
        centers_a = [(300 + 6 * i, 240) for i in range(9)]
        centers_b = [(360 - 6 * i, 240) for i in range(9)]

        # First trigger at t=4 (third aggression frame).
        for i in range(4):
            triggers = rule.update(
                [self._obs(1, centers_a[i]), self._obs(2, centers_b[i])],
                timestamp=float(i + 1),
            )
        assert len(triggers) == 1

        # Keep moving at t=5..8: aggression persists but cooldown has not
        # elapsed (elapsed is 4s < 5s) -> no retrigger.
        for i in range(4, 8):
            triggers = rule.update(
                [self._obs(1, centers_a[i]), self._obs(2, centers_b[i])],
                timestamp=float(i + 1),
            )
            assert triggers == []

        # t=9: cooldown elapsed (5s since t=4) and aggression still >= 3.
        triggers = rule.update(
            [self._obs(1, centers_a[8]), self._obs(2, centers_b[8])],
            timestamp=9.0,
        )
        assert len(triggers) == 1

    def test_independent_pairs_trigger_separately(self):
        rule = self._rule()
        # Two converging pairs: (1,2) near x=300/360 and (3,4) near x=100/160.
        # Members 2 and 4 move left so the relative speed is high.
        centers = {
            1: [(300 + 6 * i, 200) for i in range(8)],
            2: [(360 - 6 * i, 200) for i in range(8)],
            3: [(100 + 6 * i, 200) for i in range(8)],
            4: [(160 - 6 * i, 200) for i in range(8)],
        }

        triggers = rule.update(
            [
                self._obs(1, centers[1][0]),
                self._obs(2, centers[2][0]),
                self._obs(3, centers[3][0]),
                self._obs(4, centers[4][0]),
            ],
            timestamp=1.0,
        )
        assert triggers == []

        triggers = rule.update(
            [
                self._obs(1, centers[1][1]),
                self._obs(2, centers[2][1]),
                self._obs(3, centers[3][1]),
                self._obs(4, centers[4][1]),
            ],
            timestamp=2.0,
        )
        assert triggers == []

        triggers = rule.update(
            [
                self._obs(1, centers[1][2]),
                self._obs(2, centers[2][2]),
                self._obs(3, centers[3][2]),
                self._obs(4, centers[4][2]),
            ],
            timestamp=3.0,
        )
        assert triggers == []

        triggers = rule.update(
            [
                self._obs(1, centers[1][3]),
                self._obs(2, centers[2][3]),
                self._obs(3, centers[3][3]),
                self._obs(4, centers[4][3]),
            ],
            timestamp=4.0,
        )
        assert len(triggers) == 2
        assert {t.tracker_id for t in triggers} == {1, 3}

    def test_confidence_floor_excludes_weak_tracks(self):
        rule = self._rule(min_confidence=0.5)
        centers_a = [(300 + 6 * i, 240) for i in range(8)]
        centers_b = [(360 - 6 * i, 240) for i in range(8)]

        for i in range(3):
            rule.update(
                [
                    self._obs(1, centers_a[i], confidence=0.9),
                    self._obs(2, centers_b[i], confidence=0.3),
                ],
                timestamp=float(i + 1),
            )

        # Track 2 is below the floor, so no eligible pair exists.
        triggers = rule.update(
            [
                self._obs(1, centers_a[3], confidence=0.9),
                self._obs(2, centers_b[3], confidence=0.3),
            ],
            timestamp=4.0,
        )
        assert triggers == []

    def test_zone_exclusion_drops_outsiders(self):
        rule = self._rule()

        centers_a = [(300 + 6 * i, 240) for i in range(8)]
        centers_b = [(360 - 6 * i, 240) for i in range(8)]
        for i in range(4):
            rule.update(
                [self._obs(1, centers_a[i]), self._obs(2, centers_b[i], inside=(False, False))],
                timestamp=float(i + 1),
            )

        # Track 2 never definitively in-zone -> no pair, no trigger.
        assert rule._episodes == {}

        triggers = rule.update(
            [self._obs(1, centers_a[3]), self._obs(2, centers_b[3], inside=(False, False))],
            timestamp=4.0,
        )
        assert triggers == []

    def test_rule_confidence_is_min_of_pair(self):
        rule = self._rule()
        centers_a = [(300 + 6 * i, 240) for i in range(8)]
        centers_b = [(360 - 6 * i, 240) for i in range(8)]

        for i in range(4):
            triggers = rule.update(
                [
                    self._obs(1, centers_a[i], confidence=0.9),
                    self._obs(2, centers_b[i], confidence=0.55),
                ],
                timestamp=float(i + 1),
            )
        assert len(triggers) == 1
        assert triggers[0].confidence == pytest.approx(0.55)

    def test_reset_clears_pair_state(self):
        rule = self._rule()
        centers_a = [(300 + 6 * i, 240) for i in range(8)]
        centers_b = [(360 - 6 * i, 240) for i in range(8)]

        for i in range(3):
            rule.update(
                [self._obs(1, centers_a[i]), self._obs(2, centers_b[i])],
                timestamp=float(i + 1),
            )

        rule.reset()
        assert rule._episodes == {}

        # After reset, re-approach needs the full window again; three rebuilt
        # frames reach only 2 aggression frames (first frame cannot compute speed).
        for i in range(3):
            triggers = rule.update(
                [self._obs(1, centers_a[i + 4]), self._obs(2, centers_b[i + 4])],
                timestamp=float(i + 5),
            )
            assert triggers == []

        episode = rule._episodes[(1, 2)]
        assert episode.aggressive_frames == 2
        assert len(episode.samples) == 2
