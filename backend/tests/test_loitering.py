import pytest

from tests.zone_fixtures import (
    make_observation,
    make_track,
    make_zone,
    make_zone_runtime,
)
from workers.cv_worker.rules.config import LoiterConfig
from workers.cv_worker.rules.loitering import LoiterRule


def make_rule(**overrides) -> LoiterRule:
    kwargs = {
        "rule_id": "rule_l",
        "rule_name": "Loitering in lobby",
        "zone_id": "zone_1",
        "zone_name": "Lobby",
        "severity": "low",
        "config": LoiterConfig(),
    }
    kwargs.update(overrides)
    return LoiterRule(**kwargs)


@pytest.fixture
def runtime():
    return make_zone_runtime(make_zone())


def inside_track(tid=1):
    return make_track(tid, bbox=(150.0, 100.0, 250.0, 250.0))


def outside_track(tid=1):
    return make_track(tid, bbox=(500.0, 100.0, 600.0, 250.0))


def run(rule, track, runtime, frames, dt=1.0, t0=0.0):
    """Feed `frames` observations and return every trigger produced."""
    triggers = []
    for i in range(frames):
        triggers += rule.update([make_observation(track, runtime)], t0 + i * dt, dt)
    return triggers


def residence(rule, tid=1) -> float:
    """Current dwell for a track, 0.0 when no episode is running."""
    return rule.residence_seconds.get(tid, 0.0)


class TestDwellThreshold:
    def test_no_trigger_before_threshold(self, runtime):
        rule = make_rule(config=LoiterConfig(dwell_seconds=10.0, require_min_frames=1))
        assert run(rule, inside_track(), runtime, frames=9) == []

    def test_trigger_at_threshold(self, runtime):
        rule = make_rule(config=LoiterConfig(dwell_seconds=10.0, require_min_frames=1))
        assert len(run(rule, inside_track(), runtime, frames=10)) == 1

    def test_only_triggers_once(self, runtime):
        rule = make_rule(config=LoiterConfig(dwell_seconds=5.0, require_min_frames=1))
        assert len(run(rule, inside_track(), runtime, frames=100)) == 1

    def test_zero_dwell_rejected_by_config(self):
        with pytest.raises(Exception):
            LoiterConfig(dwell_seconds=0)

    def test_outside_never_accumulates(self, runtime):
        rule = make_rule(config=LoiterConfig(dwell_seconds=5.0, require_min_frames=1))
        assert run(rule, outside_track(), runtime, frames=50) == []
        assert residence(rule) == 0.0

    def test_default_require_min_frames_delays_clock(self, runtime):
        """A single noisy frame must not start a residency clock."""
        rule = make_rule(config=LoiterConfig(dwell_seconds=100.0))  # min frames = 2
        rule.update([make_observation(inside_track(), runtime)], 0.0, 1.0)
        assert rule._episodes[1].clock_started is False
        assert residence(rule) == 0.0

        rule.update([make_observation(inside_track(), runtime)], 1.0, 1.0)
        assert rule._episodes[1].clock_started is True
        assert residence(rule) == pytest.approx(1.0)


class TestBriefExitGrace:
    def test_brief_exit_preserves_dwell(self, runtime):
        """A two-second step outside must not wipe accumulated dwell."""
        rule = make_rule(
            config=LoiterConfig(dwell_seconds=10.0, grace_seconds=5.0, require_min_frames=1)
        )
        track = inside_track()

        run(rule, track, runtime, frames=8)
        assert residence(rule) == pytest.approx(8.0)

        run(rule, outside_track(), runtime, frames=2, t0=8)
        assert residence(rule) == pytest.approx(8.0)

        run(rule, track, runtime, frames=2, t0=10)
        assert residence(rule) == pytest.approx(10.0)

    def test_exit_within_grace_does_not_prevent_trigger(self, runtime):
        rule = make_rule(
            config=LoiterConfig(dwell_seconds=10.0, grace_seconds=5.0, require_min_frames=1)
        )
        inside = inside_track()

        run(rule, inside, runtime, frames=8)
        run(rule, outside_track(), runtime, frames=2, t0=8)

        assert len(run(rule, inside, runtime, frames=2, t0=10)) == 1

    def test_long_exit_ends_episode(self, runtime):
        rule = make_rule(
            config=LoiterConfig(dwell_seconds=10.0, grace_seconds=5.0, require_min_frames=1)
        )
        run(rule, inside_track(), runtime, frames=8)
        assert residence(rule) == pytest.approx(8.0)

        run(rule, outside_track(), runtime, frames=8, t0=8)
        assert residence(rule) == 0.0

    def test_zero_grace_breaks_continuity_immediately(self, runtime):
        rule = make_rule(
            config=LoiterConfig(dwell_seconds=10.0, grace_seconds=0.0, require_min_frames=1)
        )
        run(rule, inside_track(), runtime, frames=8)
        run(rule, outside_track(), runtime, frames=3, t0=8)
        assert residence(rule) == 0.0

    def test_dwell_never_negative(self, runtime):
        rule = make_rule(
            config=LoiterConfig(dwell_seconds=10.0, grace_seconds=1.0, require_min_frames=1)
        )
        run(rule, inside_track(), runtime, frames=2)
        run(rule, outside_track(), runtime, frames=100, t0=2)
        assert residence(rule) == 0.0

    def test_outside_before_any_residence_is_harmless(self, runtime):
        rule = make_rule(config=LoiterConfig(dwell_seconds=5.0, grace_seconds=5.0))
        run(rule, outside_track(), runtime, frames=20)
        assert residence(rule) == 0.0

    def test_exit_at_grace_boundary_is_tolerated(self, runtime):
        cfg = LoiterConfig(dwell_seconds=100.0, grace_seconds=5.0, require_min_frames=1)
        rule = make_rule(config=cfg)

        run(rule, inside_track(), runtime, frames=3)
        run(rule, outside_track(), runtime, frames=5, t0=3)
        # exactly at grace: episode survives
        assert rule._episodes[1].clock_started is True
        assert residence(rule) == pytest.approx(3.0)


class TestPacingBehaviour:
    def test_zero_grace_stops_pacing_accumulating(self, runtime):
        """In/out every second must never accrue dwell when grace is zero."""
        rule = make_rule(
            config=LoiterConfig(
                dwell_seconds=20.0, grace_seconds=0.0, require_min_frames=1
            )
        )
        inside, outside = inside_track(), outside_track()

        triggers = []
        for i in range(60):
            track = inside if i % 2 == 0 else outside
            triggers += rule.update([make_observation(track, runtime)], float(i), 1.0)

        assert residence(rule) == 0.0
        assert len(triggers) == 0

    def test_grace_tolerates_boundary_hovering(self, runtime):
        """By design a non-zero grace lets brief-exit presence accumulate.

        Dwell can reach at most the number of frames actually spent inside, so
        it can never exceed the time the subject was visible.
        """
        rule = make_rule(
            config=LoiterConfig(
                dwell_seconds=20.0, grace_seconds=5.0, require_min_frames=1
            )
        )
        inside, outside = inside_track(), outside_track()

        for i in range(60):
            track = inside if i % 2 == 0 else outside
            rule.update([make_observation(track, runtime)], float(i), 1.0)

        assert residence(rule) == pytest.approx(30.0)
        assert residence(rule) <= 30.0


class TestCooldownAndDedup:
    def test_cooldown_blocks_repeat_while_episode_lives(self, runtime):
        rule = make_rule(
            config=LoiterConfig(
                dwell_seconds=2.0, cooldown_seconds=100.0, require_min_frames=1
            )
        )
        inside, outside = inside_track(), outside_track()

        assert len(run(rule, inside, runtime, frames=2)) == 1
        run(rule, outside, runtime, frames=2, t0=2)
        assert len(run(rule, inside, runtime, frames=5, t0=4)) == 0

    def test_repeat_after_episode_breaks_and_cooldown_expires(self, runtime):
        rule = make_rule(
            config=LoiterConfig(
                dwell_seconds=2.0, grace_seconds=5.0, cooldown_seconds=10.0,
                require_min_frames=1,
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
        rule = make_rule(config=LoiterConfig(dwell_seconds=1.0, require_min_frames=1))
        assert len(run(rule, inside_track(), runtime, frames=200)) == 1

    def test_separate_tracks_independent(self, runtime):
        rule = make_rule(config=LoiterConfig(dwell_seconds=2.0, require_min_frames=1))
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
        rule = make_rule(config=LoiterConfig(dwell_seconds=3.0, require_min_frames=1))
        trigger = run(rule, inside_track(), runtime, frames=3)[0]

        assert trigger.rule_id == "rule_l"
        assert trigger.rule_name == "Loitering in lobby"
        assert trigger.zone_name == "Lobby"
        assert trigger.severity == "low"
        assert trigger.details["event"] == "loitering"
        assert trigger.details["residence_seconds"] == pytest.approx(3.0)
        assert trigger.details["dwell_threshold_seconds"] == 3.0

    def test_details_include_bbox(self, runtime):
        rule = make_rule(config=LoiterConfig(dwell_seconds=1.0, require_min_frames=1))
        trigger = run(rule, inside_track(), runtime, frames=1)[0]
        assert trigger.details["bbox"] == [150.0, 100.0, 250.0, 250.0]


class TestStateManagement:
    def test_reset_clears_state(self, runtime):
        rule = make_rule(config=LoiterConfig(dwell_seconds=100.0, require_min_frames=1))
        run(rule, inside_track(), runtime, frames=5)
        assert residence(rule) > 0

        rule.reset()
        assert residence(rule) == 0.0
        assert len(rule._episodes) == 0

    def test_absent_track_forgotten(self, runtime):
        rule = make_rule(config=LoiterConfig(dwell_seconds=100.0, require_min_frames=1))
        run(rule, inside_track(), runtime, frames=3)
        assert len(rule._episodes) == 1

        rule.update([], 10.0, 1.0)
        assert len(rule._episodes) == 0

    def test_unknown_track_reports_zero(self, runtime):
        rule = make_rule()
        assert residence(rule, tid=999) == 0.0


class TestDeterminism:
    def test_same_dt_sequence_gives_same_result(self, runtime):
        """Offline replay must accumulate identical dwell every run."""
        results = []
        for _ in range(2):
            rule = make_rule(
                config=LoiterConfig(dwell_seconds=10.0, require_min_frames=1)
            )
            triggers = run(rule, inside_track(), runtime, frames=30, dt=0.2)
            results.append((round(residence(rule), 9), len(triggers)))

        assert results[0] == results[1]
        assert results[0][0] == pytest.approx(6.0)