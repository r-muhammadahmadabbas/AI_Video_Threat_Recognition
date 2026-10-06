import pytest

from tests.zone_fixtures import (
    make_observation,
    make_track,
    make_zone,
    make_zone_runtime,
)
from workers.cv_worker.rules.config import ZoneEntryConfig
from workers.cv_worker.rules.restricted_zone import ZoneEntryRule


def make_rule(**overrides) -> ZoneEntryRule:
    kwargs = {
        "rule_id": "rule_1",
        "rule_name": "No entry to server room",
        "zone_id": "zone_1",
        "zone_name": "Restricted Area",
        "severity": "high",
        "config": ZoneEntryConfig(),
    }
    kwargs.update(overrides)
    return ZoneEntryRule(**kwargs)


@pytest.fixture
def zone():
    """100..300 square; see inside_track/outside_track for probe placement."""
    return make_zone()


@pytest.fixture
def runtime(zone):
    return make_zone_runtime(zone)


def inside_track(tracker_id: int = 1):
    """Well inside the 100..300 zone.

    bottom_center is (200, 250), comfortably inside even the 0.98-shrunk ring
    (101..299), so this track is *definitively* inside rather than sitting in
    the hysteresis band.
    """
    return make_track(tracker_id, bbox=(150.0, 100.0, 250.0, 250.0))


def outside_track(tracker_id: int = 1):
    """Clearly outside the expanded ring (which reaches x=306 at margin 1.02)."""
    return make_track(tracker_id, bbox=(500.0, 100.0, 600.0, 250.0))


def banded_track(tracker_id: int = 1):
    """In the hysteresis band: bottom_center (200, 305).

    Outside the 100..300 zone, inside the 1.10-expanded ring (90..310), outside
    the 0.90-shrunk ring (110..290).
    """
    return make_track(tracker_id, bbox=(150.0, 105.0, 250.0, 305.0))


def hysteresis_config(**overrides) -> ZoneEntryConfig:
    """Wide margins that put a clear band outside the zone's edge."""
    base = {"entry_margin": 1.10, "exit_margin": 0.90, "min_frames_in_zone": 1}
    base.update(overrides)
    return ZoneEntryConfig(**base)


def hysteresis_setup(zone, config: ZoneEntryConfig | None = None):
    """Rule and runtime sharing one wide-margin config."""
    cfg = config or hysteresis_config()
    return make_rule(config=cfg), make_zone_runtime(zone, cfg)


class TestBasicEntry:
    def test_no_trigger_when_outside(self, runtime):
        rule = make_rule()
        assert rule.update([make_observation(outside_track(), runtime)], 100.0) == []

    def test_trigger_after_min_frames(self, runtime):
        rule = make_rule(config=ZoneEntryConfig(min_frames_in_zone=2))
        track = inside_track()

        assert rule.update([make_observation(track, runtime)], 100.0) == []
        triggers = rule.update([make_observation(track, runtime)], 101.0)
        assert len(triggers) == 1

    def test_single_frame_config_triggers_immediately(self, runtime):
        rule = make_rule(config=ZoneEntryConfig(min_frames_in_zone=1))
        triggers = rule.update([make_observation(inside_track(), runtime)], 100.0)
        assert len(triggers) == 1

    def test_trigger_payload(self, runtime):
        rule = make_rule(config=ZoneEntryConfig(min_frames_in_zone=1))
        trigger = rule.update([make_observation(inside_track(), runtime)], 100.0)[0]

        assert trigger.rule_id == "rule_1"
        assert trigger.rule_name == "No entry to server room"
        assert trigger.zone_id == "zone_1"
        assert trigger.zone_name == "Restricted Area"
        assert trigger.severity == "high"
        assert trigger.timestamp == 100.0
        assert trigger.details["event"] == "restricted_zone_entry"
        assert trigger.details["frames_in_zone"] == 1

    def test_confidence_passed_through(self, runtime):
        rule = make_rule(config=ZoneEntryConfig(min_frames_in_zone=1))
        track = make_track(1, bbox=(150.0, 100.0, 250.0, 250.0), confidence=0.77)
        trigger = rule.update([make_observation(track, runtime)], 100.0)[0]
        assert trigger.confidence == pytest.approx(0.77)


class TestDedup:
    def test_no_retrigger_while_staying_inside(self, runtime):
        rule = make_rule(config=ZoneEntryConfig(min_frames_in_zone=1))
        track = inside_track()

        assert len(rule.update([make_observation(track, runtime)], 100.0)) == 1
        for t in (101.0, 102.0, 103.0, 104.0):
            assert rule.update([make_observation(track, runtime)], t) == []

    def test_no_frame_spam_over_long_dwell(self, runtime):
        """The core Sprint 3D guarantee: 100 frames must not mean 100 alerts."""
        rule = make_rule(config=ZoneEntryConfig(min_frames_in_zone=2))
        track = inside_track()

        total = 0
        for i in range(100):
            total += len(rule.update([make_observation(track, runtime)], 100.0 + i))

        assert total == 1

    def test_reentry_after_exit_triggers_again(self, runtime):
        rule = make_rule(
            config=ZoneEntryConfig(min_frames_in_zone=1, cooldown_seconds=0.0)
        )
        inside, outside = inside_track(), outside_track()

        assert len(rule.update([make_observation(inside, runtime)], 100.0)) == 1
        assert rule.update([make_observation(outside, runtime)], 101.0) == []
        assert len(rule.update([make_observation(inside, runtime)], 102.0)) == 1

    def test_separate_tracks_each_trigger(self, runtime):
        rule = make_rule(config=ZoneEntryConfig(min_frames_in_zone=1))
        observations = [
            make_observation(inside_track(1), runtime),
            make_observation(inside_track(2), runtime),
        ]
        triggers = rule.update(observations, 100.0)
        assert len(triggers) == 2
        assert {t.tracker_id for t in triggers} == {1, 2}

    def test_same_track_id_twice_in_one_frame_triggers_once(self, runtime):
        rule = make_rule(config=ZoneEntryConfig(min_frames_in_zone=1))
        track = inside_track()
        triggers = rule.update(
            [make_observation(track, runtime), make_observation(track, runtime)],
            100.0,
        )
        assert len(triggers) == 1


class TestCooldown:
    def test_cooldown_blocks_immediate_reentry(self, runtime):
        rule = make_rule(
            config=ZoneEntryConfig(min_frames_in_zone=1, cooldown_seconds=60.0)
        )
        inside, outside = inside_track(), outside_track()

        assert len(rule.update([make_observation(inside, runtime)], 100.0)) == 1
        rule.update([make_observation(outside, runtime)], 110.0)
        # 20s later, still within the 60s cooldown
        assert rule.update([make_observation(inside, runtime)], 120.0) == []

    def test_reentry_after_cooldown_expires(self, runtime):
        rule = make_rule(
            config=ZoneEntryConfig(min_frames_in_zone=1, cooldown_seconds=60.0)
        )
        inside, outside = inside_track(), outside_track()

        rule.update([make_observation(inside, runtime)], 100.0)
        rule.update([make_observation(outside, runtime)], 110.0)
        assert len(rule.update([make_observation(inside, runtime)], 160.0)) == 1

    def test_zero_cooldown_allows_immediate_reentry(self, runtime):
        rule = make_rule(
            config=ZoneEntryConfig(min_frames_in_zone=1, cooldown_seconds=0.0)
        )
        inside, outside = inside_track(), outside_track()

        rule.update([make_observation(inside, runtime)], 100.0)
        rule.update([make_observation(outside, runtime)], 101.0)
        assert len(rule.update([make_observation(inside, runtime)], 102.0)) == 1


class TestHysteresis:
    def test_band_alone_never_registers_entry(self, zone):
        """Entering requires a clear crossing, not a brush of the boundary."""
        rule, runtime = hysteresis_setup(zone)
        banded = banded_track()
        observation = make_observation(banded, runtime)
        assert observation.inside_expanded is True
        assert observation.inside_shrunk is False

        for t in range(100, 110):
            assert rule.update([make_observation(banded, runtime)], float(t)) == []
        assert rule.is_inside(1) is False

    def test_stays_inside_while_in_the_band(self, zone):
        """Once clearly inside, drifting into the band must not eject the track."""
        rule, runtime = hysteresis_setup(zone)

        assert len(rule.update([make_observation(inside_track(), runtime)], 100.0)) == 1
        assert rule.is_inside(1) is True

        for t in (101.0, 102.0, 103.0, 104.0):
            assert rule.update([make_observation(banded_track(), runtime)], t) == []
            assert rule.is_inside(1) is True

    def test_band_hop_does_not_retrigger(self, zone):
        """The anti-flicker guarantee: shuttling across the edge alerts once."""
        config = hysteresis_config(cooldown_seconds=0.0)
        rule, runtime = hysteresis_setup(zone, config)

        assert len(rule.update([make_observation(inside_track(), runtime)], 100.0)) == 1

        total = 0
        for i in range(20):
            track = inside_track() if i % 2 == 0 else banded_track()
            total += len(rule.update([make_observation(track, runtime)], 101.0 + i))
        assert total == 0

    def test_definitive_exit_resets(self, zone):
        rule, runtime = hysteresis_setup(zone)

        rule.update([make_observation(inside_track(), runtime)], 100.0)
        assert rule.is_inside(1) is True

        # the band does not eject
        rule.update([make_observation(banded_track(), runtime)], 101.0)
        assert rule.is_inside(1) is True

        # moving clearly outside the expanded ring does
        rule.update([make_observation(outside_track(), runtime)], 102.0)
        assert rule.is_inside(1) is False


class TestStateManagement:
    def test_reset_clears_state(self, runtime):
        rule = make_rule(config=ZoneEntryConfig(min_frames_in_zone=1))
        track = inside_track()
        rule.update([make_observation(track, runtime)], 100.0)
        assert rule.is_inside(1) is True

        rule.reset()
        assert rule.is_inside(1) is False

    def test_state_forgotten_when_track_disappears(self, runtime):
        """Absent tracks must be dropped so memory does not grow forever."""
        rule = make_rule(config=ZoneEntryConfig(min_frames_in_zone=1))
        rule.update([make_observation(inside_track(1), runtime)], 100.0)
        assert len(rule._presence) == 1

        rule.update([], 101.0)
        assert len(rule._presence) == 0

    def test_track_id_reused_after_absence_triggers_again(self, runtime):
        rule = make_rule(
            config=ZoneEntryConfig(min_frames_in_zone=1, cooldown_seconds=0.0)
        )
        inside, outside = inside_track(1), outside_track(1)

        rule.update([make_observation(inside, runtime)], 100.0)
        rule.update([make_observation(outside, runtime)], 101.0)
        assert len(rule.update([make_observation(inside, runtime)], 102.0)) == 1

    def test_one_inside_frame_resets_consecutive_counter(self, runtime):
        rule = make_rule(config=ZoneEntryConfig(min_frames_in_zone=3))
        inside, outside = inside_track(), outside_track()

        rule.update([make_observation(inside, runtime)], 100.0)
        rule.update([make_observation(inside, runtime)], 101.0)
        rule.update([make_observation(outside, runtime)], 102.0)
        rule.update([make_observation(inside, runtime)], 103.0)
        # counter restarted, so still below 3
        assert rule.update([make_observation(inside, runtime)], 104.0) == []
        assert len(rule.update([make_observation(inside, runtime)], 105.0)) == 1


class TestProbePointChoice:
    def test_bottom_center_and_center_differ_on_straddling_track(self, runtime):
        # bbox spans y 250..350; center y=300 is on the zone edge,
        # bottom_center y=350 is below it
        track = make_track(1, bbox=(150.0, 250.0, 250.0, 350.0))
        bottom_obs = make_observation(track, runtime, point_choice="bottom_center")
        center_obs = make_observation(track, runtime, point_choice="center")

        assert bottom_obs.probe_point[1] == 350.0
        assert center_obs.probe_point[1] == 300.0