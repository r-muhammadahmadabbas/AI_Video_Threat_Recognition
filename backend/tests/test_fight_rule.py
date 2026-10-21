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
) -> TrackObservation:
    track = MagicMock(spec=TrackedObject)
    track.tracker_id = tracker_id
    track.bbox = (100.0, 100.0, 160.0, 220.0)
    track.confidence = confidence
    track.center = (130.0, 160.0)
    track.bottom_center = (130.0, 220.0)
    track.violence_detected = violence
    track.violence_checked = checked
    track.fall_detected = fallen
    track.fall_confidence = fall_confidence
    return TrackObservation(
        track=track,
        inside_expanded=inside,
        inside_shrunk=inside,
        probe_point=(130.0, 220.0),
    )


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

    def test_rejects_zero_consecutive(self):
        with pytest.raises(ValueError, match="min_consecutive_frames"):
            FightConfig(min_consecutive_frames=0)

    def test_rejects_unknown_key(self):
        with pytest.raises(ValueError, match="unknown"):
            FightConfig(unknown=1)


class TestFightRule:
    def test_single_hit_does_not_trigger(self):
        rule = make_rule()
        assert rule.update([observation(violence=True)], 0.0) == []
        assert rule.update([observation(violence=False)], 0.2) == []

    def test_unchecked_frames_do_not_reset_the_streak(self):
        rule = make_rule()
        rule.update([observation()], 0.0)
        assert rule.update([observation(checked=False)], 0.2) == []
        triggers = rule.update([observation()], 0.4)

        assert len(triggers) == 1
        assert triggers[0].details["consecutive_frames"] == 2

    def test_unchecked_frames_alone_are_silent(self):
        rule = make_rule()
        assert rule.update([observation(checked=False)], 0.0) == []
        assert rule.update([observation(checked=False)], 0.2) == []

    def test_checked_negative_resets_the_streak(self):
        rule = make_rule()
        rule.update([observation()], 0.0)
        rule.update([observation(violence=False)], 0.2)
        assert rule.update([observation()], 0.4) == []

    def test_fall_evidence_suppresses_fight(self):
        rule = make_rule()
        rule.update([observation()], 0.0)
        assert rule.update([observation(fallen=True)], 0.2) == []
        assert rule.update([observation()], 1.0) == []
        assert rule.update([observation()], 1.2) == []

    def test_weak_fall_hit_only_buys_a_short_veto(self):
        rule = make_rule()
        rule.update([observation(fallen=True, fall_confidence=0.5)], 0.0)
        rule.update([observation()], 1.2)
        triggers = rule.update([observation()], 1.4)
        assert len(triggers) == 1

    def test_strong_fall_hit_vetoes_longer(self):
        rule = make_rule()
        rule.update([observation(fallen=True, fall_confidence=0.9)], 0.0)
        rule.update([observation()], 1.2)
        assert rule.update([observation()], 1.4) == []

    def test_fight_fires_after_fall_window(self):
        rule = make_rule()
        rule.update([observation(fallen=True)], 0.0)
        rule.update([observation()], 4.0)
        triggers = rule.update([observation()], 4.2)
        assert len(triggers) == 1

    def test_two_consecutive_hits_trigger(self):
        rule = make_rule()
        assert rule.update([observation()], 0.0) == []
        triggers = rule.update([observation()], 0.2)

        assert len(triggers) == 1
        assert triggers[0].rule_id == "fight"
        assert triggers[0].details["source"] == "violence_model"
        assert triggers[0].details["consecutive_frames"] == 2
        assert triggers[0].tracker_id == 1

    def test_one_trigger_per_episode(self):
        rule = make_rule()
        fired = []
        for index in range(5):
            fired.extend(rule.update([observation()], index * 0.2))
        assert len(fired) == 1

    def test_new_episode_after_clear_and_cooldown(self):
        rule = make_rule(cooldown_seconds=0.0)
        rule.update([observation()], 0.0)
        rule.update([observation()], 0.2)
        rule.update([observation(violence=False)], 0.4)
        rule.update([observation()], 0.6)
        triggers = rule.update([observation()], 0.8)
        assert len(triggers) == 1

    def test_cooldown_blocks_quick_new_episode(self):
        rule = make_rule(cooldown_seconds=10.0)
        rule.update([observation()], 0.0)
        rule.update([observation()], 0.2)
        rule.update([observation(violence=False)], 0.4)
        rule.update([observation()], 0.6)
        assert rule.update([observation()], 0.8) == []

    def test_outside_zone_is_ignored(self):
        rule = make_rule()
        rule.update([observation(inside=False)], 0.0)
        assert rule.update([observation(inside=False)], 0.2) == []

    def test_low_confidence_track_is_ignored(self):
        rule = make_rule()
        rule.update([observation(confidence=0.1)], 0.0)
        assert rule.update([observation(confidence=0.1)], 0.2) == []

    def test_reset_clears_state(self):
        rule = make_rule()
        rule.update([observation()], 0.0)
        rule.reset()
        assert rule.update([observation()], 0.2) == []
