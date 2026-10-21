"""Tests for the violence-model fight rule."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from workers.cv_worker.rules.base import TrackObservation
from workers.cv_worker.rules.config import FightConfig
from workers.cv_worker.rules.fight import FightRule
from workers.cv_worker.tracker import TrackedObject


def observation(
    tracker_id: int = 1,
    *,
    violence: bool = True,
    checked: bool = True,
    fallen: bool = False,
    fall_confidence: float = 0.0,
    confidence: float = 0.9,
    inside: bool = True,
    center: tuple[float, float] = (130.0, 160.0),
) -> TrackObservation:
    bbox = (center[0] - 30.0, center[1] - 60.0, center[0] + 30.0, center[1] + 60.0)
    track = MagicMock(spec=TrackedObject)
    track.tracker_id = tracker_id
    track.bbox = bbox
    track.confidence = confidence
    track.center = center
    track.bottom_center = (center[0], bbox[3])
    track.violence_detected = violence
    track.violence_checked = checked
    track.fall_detected = fallen
    track.fall_confidence = fall_confidence
    return TrackObservation(
        track=track,
        inside_expanded=inside,
        inside_shrunk=inside,
        probe_point=(center[0], bbox[3]),
    )


def pair(
    left: tuple[float, float],
    right: tuple[float, float],
    *,
    left_overrides: dict | None = None,
    right_overrides: dict | None = None,
    **common,
) -> list[TrackObservation]:
    return [
        observation(1, center=left, **{**common, **(left_overrides or {})}),
        observation(2, center=right, **{**common, **(right_overrides or {})}),
    ]


def converging_pair(step: int = 0) -> list[TrackObservation]:
    """Two people approaching at 50 px/s each."""
    return pair((100.0 + 10.0 * step, 160.0), (220.0 - 10.0 * step, 160.0))


def make_rule(**overrides) -> FightRule:
    config = FightConfig(min_consecutive_frames=2, cooldown_seconds=10.0)
    if overrides:
        config = config.model_copy(update=overrides)
    return FightRule(
        rule_id="fight",
        rule_name="Fight detected",
        zone_id="zone_1",
        zone_name="Test zone",
        severity="high",
        config=config,
    )


class TestFightConfig:
    def test_defaults(self):
        config = FightConfig()
        assert config.min_consecutive_frames == 2
        assert config.cooldown_seconds == 60.0
        assert config.point == "bottom_center"
        assert config.entry_margin == 1.02
        assert config.exit_margin == 0.98
        assert config.fall_suppression_seconds == 3.0
        assert config.weak_fall_suppression_seconds == 1.0
        assert config.strong_fall_confidence == 0.60
        assert config.max_zone_tracks == 8
        assert config.max_pair_distance_px == 150.0
        assert config.min_movement_px_per_s == 20.0
        assert config.min_relative_speed_px_per_s == 60.0
        assert config.speed_window_seconds == 1.0

    def test_rejects_invalid_thresholds(self):
        with pytest.raises(ValueError, match="min_consecutive_frames"):
            FightConfig(min_consecutive_frames=0)
        with pytest.raises(ValueError, match="max_zone_tracks"):
            FightConfig(max_zone_tracks=1)
        with pytest.raises(ValueError, match="speed_window_seconds"):
            FightConfig(speed_window_seconds=0.0)
        with pytest.raises(ValueError, match="unknown"):
            FightConfig(unknown=1)


class TestFightRule:
    def test_single_hit_does_not_trigger(self):
        rule = make_rule()
        assert rule.update(converging_pair(0), 0.0) == []
        assert rule.update(
            pair((110.0, 160.0), (210.0, 160.0), violence=False), 0.2
        ) == []

    def test_unchecked_frames_do_not_reset_the_streak(self):
        rule = make_rule()
        rule.update(converging_pair(0), 0.0)
        unchecked = [
            observation(1, checked=False, center=(110.0, 160.0)),
            observation(2, checked=False, center=(210.0, 160.0)),
        ]
        assert rule.update(unchecked, 0.2) == []
        triggers = rule.update(converging_pair(2), 0.4)
        assert len(triggers) == 1
        assert triggers[0].details["consecutive_frames"] == 2

    def test_unchecked_frames_alone_are_silent(self):
        rule = make_rule()
        unchecked = [
            observation(1, checked=False),
            observation(2, checked=False, center=(150.0, 160.0)),
        ]
        assert rule.update(unchecked, 0.0) == []
        assert rule.update(unchecked, 0.2) == []

    def test_checked_negative_resets_the_streak(self):
        rule = make_rule()
        rule.update(converging_pair(0), 0.0)
        rule.update(pair((110.0, 160.0), (210.0, 160.0), violence=False), 0.2)
        assert rule.update(converging_pair(3), 0.4) == []

    def test_fall_evidence_suppresses_fight(self):
        rule = make_rule()
        rule.update(converging_pair(0), 0.0)
        assert rule.update(
            pair((110.0, 160.0), (210.0, 160.0), fallen=True), 0.2
        ) == []
        assert rule.update(converging_pair(2), 1.0) == []
        assert rule.update(converging_pair(3), 1.2) == []

    def test_weak_fall_hit_only_buys_a_short_veto(self):
        rule = make_rule()
        rule.update(
            pair(
                (100.0, 160.0),
                (220.0, 160.0),
                fallen=True,
                fall_confidence=0.5,
            ),
            0.0,
        )
        rule.update(pair((110.0, 160.0), (210.0, 160.0)), 1.2)
        triggers = rule.update(pair((120.0, 160.0), (200.0, 160.0)), 1.4)
        assert len(triggers) == 1

    def test_strong_fall_hit_vetoes_longer(self):
        rule = make_rule()
        rule.update(
            pair(
                (100.0, 160.0),
                (220.0, 160.0),
                fallen=True,
                fall_confidence=0.9,
            ),
            0.0,
        )
        rule.update(pair((110.0, 160.0), (210.0, 160.0)), 1.2)
        assert rule.update(pair((120.0, 160.0), (200.0, 160.0)), 1.4) == []

    def test_fight_fires_after_fall_window(self):
        rule = make_rule()
        rule.update(pair((100.0, 160.0), (220.0, 160.0), fallen=True), 0.0)
        rule.update(pair((110.0, 160.0), (210.0, 160.0)), 4.0)
        triggers = rule.update(pair((120.0, 160.0), (200.0, 160.0)), 4.2)
        assert len(triggers) == 1

    def test_two_consecutive_hits_trigger(self):
        rule = make_rule()
        assert rule.update(converging_pair(0), 0.0) == []
        triggers = rule.update(converging_pair(1), 0.2)

        assert len(triggers) == 1
        assert triggers[0].rule_id == "fight"
        assert triggers[0].details["source"] == "violence_model"
        assert triggers[0].details["consecutive_frames"] == 2
        assert triggers[0].details["interacting_tracker_ids"] == [1, 2]
        assert triggers[0].details["pair_distance_px"] == 100.0
        assert triggers[0].details["relative_speed_px_per_s"] == 100.0
        assert triggers[0].tracker_id == 1

    def test_one_trigger_per_episode(self):
        rule = make_rule()
        fired = []
        for index in range(5):
            fired.extend(rule.update(converging_pair(index), index * 0.2))
        assert len(fired) == 1

    def test_new_episode_after_clear_and_cooldown(self):
        rule = make_rule(cooldown_seconds=0.0)
        rule.update(converging_pair(0), 0.0)
        rule.update(converging_pair(1), 0.2)
        rule.update(pair((120.0, 160.0), (200.0, 160.0), violence=False), 0.4)
        rule.update(converging_pair(3), 0.6)
        assert len(rule.update(converging_pair(4), 0.8)) == 1

    def test_cooldown_blocks_quick_new_episode(self):
        rule = make_rule(cooldown_seconds=10.0)
        rule.update(converging_pair(0), 0.0)
        rule.update(converging_pair(1), 0.2)
        rule.update(pair((120.0, 160.0), (200.0, 160.0), violence=False), 0.4)
        rule.update(converging_pair(3), 0.6)
        assert rule.update(converging_pair(4), 0.8) == []

    def test_outside_zone_is_ignored(self):
        rule = make_rule()
        rule.update(
            pair((100.0, 160.0), (220.0, 160.0), left_overrides={"inside": False}),
            0.0,
        )
        assert rule.update(
            pair((110.0, 160.0), (210.0, 160.0), right_overrides={"inside": False}),
            0.2,
        ) == []

    def test_low_confidence_track_is_ignored(self):
        rule = make_rule()
        rule.update(
            pair(
                (100.0, 160.0),
                (220.0, 160.0),
                left_overrides={"confidence": 0.1},
            ),
            0.0,
        )
        assert rule.update(
            pair(
                (110.0, 160.0),
                (210.0, 160.0),
                left_overrides={"confidence": 0.1},
            ),
            0.2,
        ) == []

    def test_reset_clears_state(self):
        rule = make_rule()
        rule.update(converging_pair(0), 0.0)
        rule.reset()
        assert rule.update(converging_pair(1), 0.2) == []


def fast_single_person(index: int) -> list[TrackObservation]:
    return [observation(1, center=(100.0 + 20.0 * index, 160.0))]


def hugging_pair(_index: int) -> list[TrackObservation]:
    return pair((130.0, 160.0), (180.0, 160.0))


def camera_shake(index: int) -> list[TrackObservation]:
    shift = 15.0 * index
    return [
        observation(1, center=(100.0 + shift, 160.0)),
        observation(2, center=(180.0 + shift, 160.0)),
        observation(3, center=(260.0 + shift, 160.0)),
    ]


def crowd_movement(index: int) -> list[TrackObservation]:
    return [
        observation(tracker_id, center=(60.0 + 60.0 * tracker_id + 10.0 * index, 160.0))
        for tracker_id in range(1, 10)
    ]


class TestFightFalseAlarms:
    """Hard negatives the frame-level classifier cannot distinguish alone."""

    @pytest.mark.parametrize(
        "frames",
        [fast_single_person, hugging_pair, camera_shake, crowd_movement],
        ids=["fast-single-person", "hugging", "camera-shake", "crowd"],
    )
    def test_common_false_alarms_are_ignored(self, frames):
        rule = make_rule()
        triggers = []
        for index in range(6):
            triggers.extend(rule.update(frames(index), index * 0.2))
        assert triggers == []
