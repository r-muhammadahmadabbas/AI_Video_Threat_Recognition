"""Tests for the abnormal-crowd-movement rule and config (Sprint 7A/7B/7C)."""

from __future__ import annotations

from collections import deque
from unittest.mock import MagicMock

import pytest

from workers.cv_worker.rules.base import TrackObservation
from workers.cv_worker.rules.config import CrowdAnomalyConfig
from workers.cv_worker.rules.crowd import CrowdMotionRule
from workers.cv_worker.tracker import TrackedObject


def _obs(
    tracker_id: int,
    center: tuple[float, float],
    confidence: float = 0.9,
    inside: tuple[bool, bool] = (True, True),
):
    """A track centred on ``center``; inside flags default to in-zone."""
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


def _cluster(n: int, origin: tuple[float, float], step: float) -> list[tuple[float, float]]:
    """``n`` centers in a square grid starting at ``origin``."""
    cols = int(n**0.5) + 1
    return [(origin[0] + (i % cols) * step, origin[1] + (i // cols) * step) for i in range(n)]


def _moving(
    centers: list[tuple[float, float]],
    vx: float,
    vy: float,
    frame_index: int,
) -> list[tuple[float, float]]:
    """``centers`` displaced by ``(vx, vy)`` per frame."""
    dx = vx * frame_index
    dy = vy * frame_index
    return [(x + dx, y + dy) for x, y in centers]


def make_config(**overrides) -> CrowdAnomalyConfig:
    """A config whose window separation keeps the observation current.

    ``observation_window_seconds=1.5`` at a 1 s frame cadence means the two
    most recent frames form the current window and one stale frame stays out
    of the baseline, so a burst is compared against genuinely older behaviour.
    """
    base = {
        "observation_window_seconds": 1.5,
        "baseline_window_seconds": 100.0,
        "min_baseline_snapshots": 3,
        "min_tracks": 3,
        "score_threshold": 1.0,
        "min_duration_seconds": 2.0,
        "cooldown_seconds": 100.0,
        "weight_track_count": 1.0,
        "weight_mean_speed": 1.0,
        "weight_direction_dispersion": 1.0,
        "weight_mean_pair_distance": 1.0,
        "min_confidence": 0.1,
    }
    base.update(overrides)
    return CrowdAnomalyConfig(**base)


class TestCrowdAnomalyConfig:
    """7C/7D: config is validated and rejects nonsense thresholds."""

    def test_defaults_build(self):
        cfg = CrowdAnomalyConfig()
        assert cfg.observation_window_seconds == 2.0
        assert cfg.baseline_window_seconds == 30.0
        assert cfg.min_baseline_snapshots == 3
        assert cfg.min_tracks == 3
        assert cfg.score_threshold == 1.5
        assert cfg.min_duration_seconds == 3.0
        assert cfg.cooldown_seconds == 300.0
        for weight in (
            cfg.weight_track_count,
            cfg.weight_mean_speed,
            cfg.weight_direction_dispersion,
            cfg.weight_mean_pair_distance,
        ):
            assert weight == 1.0

    def test_rejects_baseline_not_longer_than_observation(self):
        with pytest.raises(ValueError, match="baseline_window_seconds"):
            CrowdAnomalyConfig(baseline_window_seconds=1.0)
        with pytest.raises(ValueError, match="baseline_window_seconds"):
            CrowdAnomalyConfig(observation_window_seconds=5.0, baseline_window_seconds=5.0)

    def test_rejects_zero_threshold_and_window(self):
        with pytest.raises(ValueError, match="score_threshold"):
            CrowdAnomalyConfig(score_threshold=0.0)
        with pytest.raises(ValueError, match="observation_window_seconds"):
            CrowdAnomalyConfig(observation_window_seconds=0.0)

    def test_rejects_negative_weights(self):
        with pytest.raises(ValueError, match="weight_mean_speed"):
            CrowdAnomalyConfig(weight_mean_speed=-1.0)
        with pytest.raises(ValueError, match="weight_track_count"):
            CrowdAnomalyConfig(weight_track_count=-0.5)

    def test_rejects_inverted_hysteresis(self):
        with pytest.raises(ValueError, match="exit_margin"):
            CrowdAnomalyConfig(entry_margin=1.02, exit_margin=1.03)

    def test_rejects_extra_keys(self):
        with pytest.raises(ValueError, match="unknown_key"):
            CrowdAnomalyConfig(unknown_key=123)


class TestCrowdMotionRule:
    """7B: baseline warm-up, then trigger on a persistent score surge."""

    @staticmethod
    def _rule(**overrides) -> CrowdMotionRule:
        return CrowdMotionRule(
            rule_id="crowd_1",
            rule_name="Abnormal Crowd Movement",
            zone_id="zone_1",
            zone_name="Test Zone",
            severity="critical",
            config=make_config(**overrides),
        )

    def _feed(self, rule, centers: list[tuple[float, float]], timestamp: float):
        return rule.update(
            [_obs(i + 1, c) for i, c in enumerate(centers)],
            timestamp=timestamp,
            dt=1.0,
        )

    def test_warmup_requires_baseline(self):
        # Baseline can never reach the required snapshot count, so even a big
        # burst must not fire.
        rule = self._rule(min_baseline_snapshots=10)
        calm = _cluster(5, (200, 200), step=60)

        for t in range(1, 3):  # only two baseline snapshots ever exist
            assert self._feed(rule, calm, float(t)) == []

        # A burst appears, but the baseline never reached min snapshots.
        burst = _cluster(12, (300, 240), step=8)
        for t in range(3, 7):
            assert self._feed(rule, burst, float(t)) == []

    def test_triggers_after_sustained_burst(self):
        rule = self._rule()
        calm = _cluster(5, (200, 200), step=60)

        for t in range(1, 5):
            assert self._feed(rule, calm, float(t)) == []

        burst = _cluster(50, (300, 240), step=6)
        # First burst frame: score is high but duration (1 s) is under 2 s.
        assert self._feed(rule, burst, 5.0) == []
        # Second burst frame reaches min_duration -> trigger.
        triggers = self._feed(rule, burst, 6.0)
        assert len(triggers) == 1
        t = triggers[0]
        assert t.rule_id == "crowd_1"
        assert t.tracker_id == -1
        assert t.details["event"] == "crowd_anomaly"
        assert t.details["anomaly_score"] > 1.0

    def test_calm_crowd_never_triggers(self):
        rule = self._rule()
        calm = _cluster(6, (200, 200), step=40)
        for t in range(1, 12):
            assert self._feed(rule, calm, float(t)) == []

    def test_below_min_tracks_resets_persistence(self):
        # Use a tight observation window so a single sparse frame is the whole
        # current window and its track count dips below the minimum.
        rule = self._rule(
            observation_window_seconds=0.4,
            min_duration_seconds=2.0,
        )
        calm = _cluster(5, (200, 200), step=60)
        for t in range(1, 5):
            self._feed(rule, calm, float(t))

        burst = _cluster(50, (300, 240), step=6)
        assert self._feed(rule, burst, 5.0) == []  # high = 1 s

        # Crowd drops below the minimum -> high resets instead of accumulating.
        sparse = _cluster(2, (300, 240), step=6)
        assert self._feed(rule, sparse, 6.0) == []

        # A new burst starts from zero: 1 s -> no trigger, 2 s -> trigger.
        assert self._feed(rule, burst, 7.0) == []
        triggers = self._feed(rule, burst, 8.0)
        assert len(triggers) == 1

    def test_mean_speed_feature_triggers_on_sudden_motion(self):
        # Stationary crowd as baseline, then a fast-moving burst. Only the
        # speed feature is weighted, isolating the signal under test.
        rule = self._rule(
            min_duration_seconds=2.0,
            score_threshold=0.5,
            weight_track_count=0.0,
            weight_direction_dispersion=0.0,
            weight_mean_pair_distance=0.0,
            weight_mean_speed=1.0,
        )
        calm = _cluster(6, (200, 200), step=40)
        for t in range(1, 5):
            assert self._feed(rule, calm, float(t)) == []

        seen: list = []
        # 40 tracks, each streaking right at 50 px/frame in lockstep.
        for i in range(5):
            centers = _moving(_cluster(40, (150, 200), step=10), 50, 0, i)
            seen.extend(self._feed(rule, centers, float(6 + i)))
        assert seen, "expected a speed-driven trigger"
        t = seen[0]
        assert t.details["event"] == "crowd_anomaly"
        assert t.details["current_features"]["mean_speed_px_per_s"] > 1.0
        assert t.details["feature_contributions"]["mean_speed_px_per_s"] > 0.5

    def test_score_breakdown_sums_to_score(self):
        rule = self._rule()
        calm = _cluster(5, (200, 200), step=60)
        for t in range(1, 5):
            self._feed(rule, calm, float(t))
        burst = _cluster(50, (300, 240), step=6)
        self._feed(rule, burst, 5.0)
        triggers = self._feed(rule, burst, 6.0)

        t = triggers[0]
        details = t.details
        # Transparency: every feature, its baseline, and its contribution are
        # carried in the trigger so the operator can see why it fired.
        assert set(details["current_features"]) == {
            "track_count",
            "mean_speed_px_per_s",
            "direction_dispersion",
            "mean_pair_distance_px",
        }
        assert set(details["baseline_features"]) == set(details["current_features"])
        assert set(details["feature_contributions"]) == set(details["current_features"])
        assert details["score_threshold"] == 1.0
        # Contributions sum to the reported score (within rounding).
        total = sum(details["feature_contributions"].values())
        assert abs(total - details["anomaly_score"]) < 0.5

    def test_weights_off_never_triggers(self):
        # An operator can dial a feature's weight to zero (7D tuning).
        rule = self._rule(
            weight_track_count=0.0,
            weight_mean_speed=0.0,
            weight_direction_dispersion=0.0,
            weight_mean_pair_distance=0.0,
        )
        calm = _cluster(5, (200, 200), step=60)
        for t in range(1, 5):
            self._feed(rule, calm, float(t))
        burst = _cluster(50, (300, 240), step=6)
        for t in range(5, 9):
            assert self._feed(rule, burst, float(t)) == []

    def test_weight_only_mean_pair_distance(self):
        # Weight only the spacing feature: a scattered crowd that suddenly
        # packs tight must fire even with an unchanged track count.
        rule = self._rule(
            weight_track_count=0.0,
            weight_mean_speed=0.0,
            weight_direction_dispersion=0.0,
            weight_mean_pair_distance=1.0,
            score_threshold=0.5,
        )
        calm = _cluster(6, (100, 100), step=90)  # spread out, distance ~90
        for t in range(1, 5):
            self._feed(rule, calm, float(t))

        packed = _cluster(6, (300, 240), step=5)  # same count, very tight
        assert self._feed(rule, packed, 5.0) == []  # current is diluted by calm frame
        assert self._feed(rule, packed, 6.0) == []  # high = 1 s
        triggers = self._feed(rule, packed, 7.0)  # high reaches 2 s -> trigger
        assert len(triggers) == 1
        t = triggers[0]
        pair = t.details["feature_contributions"]["mean_pair_distance_px"]
        assert pair > 0.5

    def test_cooldown_gates_retrigger(self):
        rule = self._rule(cooldown_seconds=5.0)
        calm = _cluster(5, (200, 200), step=60)
        for t in range(1, 5):
            self._feed(rule, calm, float(t))

        burst = _cluster(50, (300, 240), step=6)
        self._feed(rule, burst, 5.0)
        triggers = self._feed(rule, burst, 6.0)
        assert len(triggers) == 1

        # Sustained burst stays high but cooldown (5 s) has not elapsed.
        for t in range(7, 11):
            assert self._feed(rule, burst, float(t)) == []

    def test_zone_exclusion_ignores_outside_tracks(self):
        rule = self._rule()
        calm = _cluster(5, (200, 200), step=60)
        for t in range(1, 5):
            assert self._feed(rule, calm, float(t)) == []

        # A huge crowd but all outside the zone: nothing is aggregated.
        outside = [_obs(100 + i, (500, 500), inside=(False, False)) for i in range(50)]
        for t in range(5, 8):
            assert rule.update(outside, timestamp=float(t), dt=1.0) == []
        assert rule._tracks == {}

    def test_reset_clears_all_state(self):
        rule = self._rule()
        calm = _cluster(5, (200, 200), step=60)
        for t in range(1, 5):
            self._feed(rule, calm, float(t))
        burst = _cluster(50, (300, 240), step=6)
        self._feed(rule, burst, 5.0)
        self._feed(rule, burst, 6.0)

        rule.reset()
        assert rule._tracks == {}
        assert rule._snapshots == deque()
        assert rule._high_seconds == 0.0
        assert rule._last_triggered_at is None
