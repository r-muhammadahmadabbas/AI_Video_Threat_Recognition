import pytest

from tests.zone_fixtures import (
    make_observation,
    make_track,
    make_zone,
    make_zone_runtime,
)
from workers.cv_worker.rules.config import WeaponConfig
from workers.cv_worker.rules.weapon import WeaponRule


@pytest.fixture
def runtime():
    return make_zone_runtime(make_zone())


def make_rule(**overrides) -> WeaponRule:
    kwargs = {
        "rule_id": "rule_w",
        "rule_name": "Weapon in area",
        "zone_id": "zone_1",
        "zone_name": "Area",
        "severity": "high",
        "config": WeaponConfig(),
    }
    kwargs.update(overrides)
    return WeaponRule(**kwargs)


def run(rule, track, runtime, *, frames, dt=1.0, t0=0.0):
    """Feed ``frames`` observations and return every trigger produced."""
    triggers = []
    for i in range(frames):
        triggers += rule.update(
            [make_observation(track, runtime)], t0 + i * dt, dt
        )
    return triggers


def residence(rule, tid=1) -> float:
    """Current dwell for a track, 0.0 when no episode is running."""
    return rule.residence_seconds.get(tid, 0.0)


def inside_track(tid=1, conf=1.0, weapon=True, weapon_conf=0.9):
    return make_track(
        tid,
        bbox=(150.0, 100.0, 250.0, 250.0),
        confidence=conf,
        weapon_detected=weapon,
        weapon_confidence=weapon_conf,
    )


def outside_track(tid=1):
    return make_track(tid, bbox=(500.0, 100.0, 600.0, 250.0), confidence=1.0)


class TestWeaponDwellThreshold:
    def test_no_trigger_before_threshold(self, runtime):
        rule = make_rule(config=WeaponConfig(dwell_seconds=10.0))
        assert run(rule, inside_track(), runtime, frames=9) == []

    def test_trigger_at_threshold(self, runtime):
        rule = make_rule(config=WeaponConfig(dwell_seconds=10.0))
        assert len(run(rule, inside_track(), runtime, frames=10)) == 1

    def test_only_triggers_once(self, runtime):
        rule = make_rule(config=WeaponConfig(dwell_seconds=5.0))
        assert len(run(rule, inside_track(), runtime, frames=100)) == 1

    def test_outside_never_accumulates(self, runtime):
        rule = make_rule(config=WeaponConfig(dwell_seconds=5.0))
        assert run(rule, outside_track(), runtime, frames=50) == []
        assert residence(rule) == 0.0


class TestWeaponPresenceGating:
    def test_unarmed_track_never_triggers(self, runtime):
        rule = make_rule(config=WeaponConfig(dwell_seconds=2.0))
        unarmed = inside_track(weapon=False)

        assert run(rule, unarmed, runtime, frames=50) == []
        assert residence(rule) == 0.0

    def test_losing_the_weapon_ends_the_episode(self, runtime):
        rule = make_rule(
            config=WeaponConfig(dwell_seconds=10.0, grace_seconds=0.0)
        )
        armed = inside_track()
        unarmed = inside_track(weapon=False)

        run(rule, armed, runtime, frames=3, dt=1.0)
        assert residence(rule) == 3.0

        run(rule, unarmed, runtime, frames=1, t0=3, dt=1.0)
        assert residence(rule) == 0.0

    def test_grace_lets_brief_weapon_loss_survive(self, runtime):
        rule = make_rule(
            config=WeaponConfig(dwell_seconds=10.0, grace_seconds=5.0)
        )
        armed = inside_track()
        unarmed = inside_track(weapon=False)

        run(rule, armed, runtime, frames=2, dt=1.0)
        run(rule, unarmed, runtime, frames=2, t0=2, dt=1.0)

        assert residence(rule) == 2.0

        assert len(run(rule, armed, runtime, frames=3, t0=4, dt=1.0)) == 0
        assert residence(rule) == 5.0


class TestWeaponCooldownAndDedup:
    def test_cooldown_blocks_repeat_while_episode_lives(self, runtime):
        rule = make_rule(
            config=WeaponConfig(dwell_seconds=2.0, cooldown_seconds=100.0)
        )
        inside, outside = inside_track(), outside_track()

        assert len(run(rule, inside, runtime, frames=2)) == 1
        run(rule, outside, runtime, frames=2, t0=2)
        assert len(run(rule, inside, runtime, frames=5, t0=4)) == 0

    def test_repeat_after_episode_breaks_and_cooldown_expires(self, runtime):
        rule = make_rule(
            config=WeaponConfig(
                dwell_seconds=2.0, grace_seconds=5.0, cooldown_seconds=10.0
            )
        )
        inside, outside = inside_track(), outside_track()

        assert len(run(rule, inside, runtime, frames=2)) == 1

        # 6s outside exceeds the 5s grace, ending the episode entirely
        run(rule, outside, runtime, frames=6, t0=2)
        assert residence(rule) == 0.0

        # re-enter well after the 10s cooldown: a fresh episode alerts again
        assert len(run(rule, inside, runtime, frames=5, t0=30)) == 1

    def test_no_frame_spam_over_long_loiter(self, runtime):
        rule = make_rule(config=WeaponConfig(dwell_seconds=1.0))
        assert len(run(rule, inside_track(), runtime, frames=200)) == 1

    def test_separate_tracks_independent(self, runtime):
        rule = make_rule(config=WeaponConfig(dwell_seconds=2.0))
        a, b = inside_track(1), inside_track(2)

        triggers = []
        for i in range(3):
            observations = [
                make_observation(a, runtime),
                make_observation(b, runtime),
            ]
            triggers += rule.update(observations, float(i), 1.0)

        assert {t.tracker_id for t in triggers} == {1, 2}


class TestTriggerPayload:
    def test_payload_fields(self, runtime):
        rule = make_rule(config=WeaponConfig(dwell_seconds=3.0))
        trigger = run(rule, inside_track(), runtime, frames=3)[0]

        assert trigger.rule_id == "rule_w"
        assert trigger.rule_name == "Weapon in area"
        assert trigger.zone_name == "Area"
        assert trigger.severity == "high"
        assert trigger.details["event"] == "weapon"
        assert trigger.details["residence_seconds"] == pytest.approx(3.0)
        assert trigger.details["dwell_threshold_seconds"] == 3.0
        assert trigger.details["weapon_confidence"] == 0.9

    def test_details_include_bbox(self, runtime):
        rule = make_rule(config=WeaponConfig(dwell_seconds=1.0))
        trigger = run(rule, inside_track(), runtime, frames=1)[0]
        assert trigger.details["bbox"] == [150.0, 100.0, 250.0, 250.0]


class TestStateManagement:
    def test_reset_clears_state(self, runtime):
        rule = make_rule(config=WeaponConfig(dwell_seconds=100.0))
        run(rule, inside_track(), runtime, frames=5)
        assert residence(rule) > 0

        rule.reset()
        assert residence(rule) == 0.0
        assert len(rule._episodes) == 0

    def test_absent_track_forgotten(self, runtime):
        rule = make_rule(config=WeaponConfig(dwell_seconds=100.0))
        run(rule, inside_track(), runtime, frames=3)
        assert len(rule._episodes) == 1

        rule.update([], 10.0, 1.0)
        assert len(rule._episodes) == 0

    def test_unknown_track_reports_zero(self):
        rule = make_rule()
        assert residence(rule, tid=999) == 0.0


class TestDeterminism:
    def test_same_dt_sequence_gives_same_result(self, runtime):
        """Offline replay must accumulate identical dwell every run."""
        results = []
        for _ in range(2):
            rule = make_rule(
                config=WeaponConfig(dwell_seconds=10.0)
            )
            triggers = run(rule, inside_track(), runtime, frames=30, dt=0.2)
            results.append((round(residence(rule), 9), len(triggers)))

        assert results[0] == results[1]
        assert results[0][0] == pytest.approx(6.0)


class TestConfidenceFiltering:
    def test_below_threshold_track_accumulates_no_dwell(self, runtime):
        rule = make_rule(
            config=WeaponConfig(dwell_seconds=2.0, min_confidence=0.6)
        )
        faint = make_track(
            bbox=(150.0, 100.0, 250.0, 250.0),
            confidence=0.4,
            weapon_detected=True,
            weapon_confidence=0.9,
        )

        run(rule, faint, runtime, frames=5, dt=1.0)

        assert residence(rule) == 0.0

    def test_confidence_dip_does_not_reset_a_residency_clock(self, runtime):
        rule = make_rule(
            config=WeaponConfig(
                dwell_seconds=10.0, min_confidence=0.6
            )
        )
        confident = make_track(
            bbox=(150.0, 100.0, 250.0, 250.0),
            confidence=0.9,
            weapon_detected=True,
            weapon_confidence=0.9,
        )
        faint = make_track(
            bbox=(150.0, 100.0, 250.0, 250.0),
            confidence=0.2,
            weapon_detected=True,
            weapon_confidence=0.9,
        )

        run(rule, confident, runtime, frames=3, dt=1.0)
        dwell_before = residence(rule)

        run(rule, faint, runtime, frames=2, dt=1.0)

        # The episode survived the dip rather than being forgotten and restarted.
        assert residence(rule) == dwell_before
        run(rule, confident, runtime, frames=3, dt=1.0)
        assert residence(rule) == pytest.approx(dwell_before + 3.0)
