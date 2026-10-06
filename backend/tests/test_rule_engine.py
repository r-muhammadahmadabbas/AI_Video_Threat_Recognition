"""Tests for the rule engine: zone resolution, observation building, incident dedup."""

from __future__ import annotations

import pytest

from tests.zone_fixtures import make_track
from workers.cv_worker.rules.base import Zone
from workers.cv_worker.rules.config import LoiterConfig, ZoneConfig, ZoneEntryConfig
from workers.cv_worker.rules.engine import RuleEngine, zone_to_pixel_polygon
from workers.cv_worker.rules.geometry import Polygon
from workers.cv_worker.rules.loitering import LoiterRule
from workers.cv_worker.rules.restricted_zone import ZoneEntryRule

WIDTH, HEIGHT = 640, 480


def pixel_zone(**overrides) -> Zone:
    """A 128..320 by 96..240 rectangle declared in pixel space for 640x480."""
    kwargs = {
        "zone_id": "zone_1",
        "name": "Restricted Area",
        "polygon": Polygon.from_bbox(128, 96, 320, 240),
        "config": ZoneConfig(
            coordinate_space="pixel",
            reference_width=WIDTH,
            reference_height=HEIGHT,
        ),
    }
    kwargs.update(overrides)
    return Zone(**kwargs)


def normalized_zone(**overrides) -> Zone:
    """The same rectangle expressed as fractions of the frame."""
    kwargs = {
        "zone_id": "zone_norm",
        "name": "Normalized",
        "polygon": Polygon.from_vertices(
            [(0.2, 0.2), (0.5, 0.2), (0.5, 0.5), (0.2, 0.5)]
        ),
        "config": ZoneConfig(),
    }
    kwargs.update(overrides)
    return Zone(**kwargs)


def entry_rule(**overrides) -> ZoneEntryRule:
    kwargs = {
        "rule_id": "rule_entry",
        "rule_name": "No entry to server room",
        "zone_id": "zone_1",
        "zone_name": "Restricted Area",
        "severity": "high",
        "config": ZoneEntryConfig(min_frames_in_zone=1, cooldown_seconds=10.0),
    }
    kwargs.update(overrides)
    return ZoneEntryRule(**kwargs)


def loiter_rule(**overrides) -> LoiterRule:
    kwargs = {
        "rule_id": "rule_loiter",
        "rule_name": "Loitering in lobby",
        "zone_id": "zone_1",
        "zone_name": "Restricted Area",
        "severity": "medium",
        "config": LoiterConfig(
            dwell_seconds=1.0,
            grace_seconds=0.0,
            cooldown_seconds=10.0,
            require_min_frames=1,
        ),
    }
    kwargs.update(overrides)
    return LoiterRule(**kwargs)


def make_engine(*zones, **kwargs) -> RuleEngine:
    engine = RuleEngine(
        camera_id="cam_1",
        frame_width=WIDTH,
        frame_height=HEIGHT,
        **kwargs,
    )
    for zone in zones:
        engine.load_zone(zone)
    return engine


# bbox (150, 80, 250, 200) -> bottom_center (200, 200), well inside.
INSIDE_TRACK_BBOX = (150.0, 80.0, 250.0, 200.0)
OUTSIDE_TRACK_BBOX = (400.0, 80.0, 500.0, 200.0)


class TestZoneResolution:
    def test_normalized_polygon_scales_to_frame_pixels(self):
        resolved = zone_to_pixel_polygon(normalized_zone(), WIDTH, HEIGHT)
        assert resolved.bbox == pytest.approx((128.0, 96.0, 320.0, 240.0))

    def test_pixel_polygon_unchanged_at_reference_size(self):
        zone = pixel_zone()
        assert zone_to_pixel_polygon(zone, WIDTH, HEIGHT) is zone.polygon

    def test_pixel_polygon_scales_from_other_reference_resolution(self):
        # Authored at 1280x720 but streamed at 640x480.
        zone = Zone(
            zone_id="zone_1",
            name="Scaled",
            polygon=Polygon.from_bbox(0, 0, 640, 360),
            config=ZoneConfig(
                coordinate_space="pixel",
                reference_width=1280,
                reference_height=720,
            ),
        )
        resolved = zone_to_pixel_polygon(zone, 640, 480)
        assert resolved.bbox == pytest.approx((0.0, 0.0, 320.0, 240.0))

    def test_load_zone_stores_resolved_polygon(self):
        engine = make_engine(normalized_zone())
        zone = engine.get_zone("zone_norm")
        assert zone is not None
        assert zone.polygon.bbox == pytest.approx((128.0, 96.0, 320.0, 240.0))


class TestRuleBinding:
    def test_bind_unknown_zone_raises(self):
        engine = make_engine(pixel_zone())
        with pytest.raises(KeyError, match="not loaded"):
            engine.bind_rule(entry_rule(zone_id="zone_missing"), "zone_missing")

    def test_bound_rule_ids_reflect_bindings(self):
        engine = make_engine(pixel_zone())
        engine.bind_rule(entry_rule(), "zone_1")
        assert engine.bound_rule_ids == ["rule_entry"]
        assert engine.zone_ids == ["zone_1"]

    def test_ring_rederived_when_zone_is_reloaded(self):
        engine = make_engine(pixel_zone())
        engine.bind_rule(entry_rule(), "zone_1")
        first = engine._bindings[0].expanded

        # Move and grow the zone; the derived ring must follow it.
        engine.load_zone(pixel_zone(polygon=Polygon.from_bbox(300, 300, 600, 450)))
        assert engine._bindings[0].expanded is not first
        assert engine._bindings[0].expanded.bbox != first.bbox


class TestEndToEndTriggers:
    def test_track_inside_zone_produces_one_incident(self):
        engine = make_engine(pixel_zone())
        engine.bind_rule(entry_rule(), "zone_1")

        triggers = engine.process([make_track(bbox=INSIDE_TRACK_BBOX)], timestamp=1.0)

        assert len(triggers) == 1
        trigger = triggers[0]
        assert trigger.rule_id == "rule_entry"
        assert trigger.zone_id == "zone_1"
        assert trigger.severity == "high"
        assert trigger.details["event"] == "restricted_zone_entry"
        assert trigger.details["probe_point"] == pytest.approx([200.0, 200.0])

    def test_frames_after_first_are_merged_into_the_same_incident(self):
        engine = make_engine(pixel_zone())
        engine.bind_rule(entry_rule(), "zone_1")
        tracks = [make_track(bbox=INSIDE_TRACK_BBOX)]

        per_frame = [engine.process(tracks, timestamp=t) for t in range(5)]

        assert [len(batch) for batch in per_frame] == [1, 0, 0, 0, 0]

    def test_separate_tracks_each_open_their_own_incident(self):
        engine = make_engine(pixel_zone())
        engine.bind_rule(entry_rule(), "zone_1")

        tracks = [
            make_track(tracker_id=1, bbox=INSIDE_TRACK_BBOX),
            make_track(tracker_id=2, bbox=(170.0, 80.0, 270.0, 200.0)),
        ]
        triggers = engine.process(tracks, timestamp=1.0)

        assert sorted(t.tracker_id for t in triggers) == [1, 2]

    def test_track_outside_zone_is_silent(self):
        engine = make_engine(pixel_zone())
        engine.bind_rule(entry_rule(), "zone_1")

        triggers = engine.process([make_track(bbox=OUTSIDE_TRACK_BBOX)], timestamp=1.0)
        assert triggers == []

    def test_inactive_zone_is_skipped(self):
        engine = make_engine(pixel_zone(is_active=False))
        engine.bind_rule(entry_rule(), "zone_1")

        triggers = engine.process([make_track(bbox=INSIDE_TRACK_BBOX)], timestamp=1.0)
        assert triggers == []

    def test_two_rules_on_one_zone_both_fire(self):
        engine = make_engine(pixel_zone())
        engine.bind_rule(entry_rule(), "zone_1")
        engine.bind_rule(loiter_rule(), "zone_1")
        tracks = [make_track(bbox=INSIDE_TRACK_BBOX)]

        first = engine.process(tracks, timestamp=1.0, dt=2.0)
        assert sorted(t.rule_id for t in first) == ["rule_entry", "rule_loiter"]

        # Both rules then go quiet for their own cooldown windows.
        second = engine.process(tracks, timestamp=2.0, dt=2.0)
        assert second == []

    def test_loitering_accumulates_from_dt(self):
        engine = make_engine(pixel_zone())
        engine.bind_rule(loiter_rule(), "zone_1")
        tracks = [make_track(bbox=INSIDE_TRACK_BBOX)]

        # dwell threshold is 1.0s; two frames of 0.6s each must reach it.
        assert engine.process(tracks, timestamp=0.0, dt=0.6) == []
        assert len(engine.process(tracks, timestamp=0.6, dt=0.6)) == 1

    def test_reset_allows_a_fresh_incident_immediately(self):
        engine = make_engine(pixel_zone())
        engine.bind_rule(entry_rule(), "zone_1")
        tracks = [make_track(bbox=INSIDE_TRACK_BBOX)]

        assert len(engine.process(tracks, timestamp=1.0)) == 1
        # Still inside and still cooling down.
        assert engine.process(tracks, timestamp=2.0) == []

        engine.reset()

        assert len(engine.process(tracks, timestamp=2.5)) == 1


class TestProbePointChoice:
    def test_bottom_center_is_used_by_default(self):
        engine = make_engine(pixel_zone())
        engine.bind_rule(entry_rule(), "zone_1")

        # bottom_center (225, 250) sits just below the zone's 240 edge.
        straddling = make_track(bbox=(150.0, 60.0, 300.0, 250.0))
        assert engine.process([straddling], timestamp=1.0) == []

    def test_center_point_switches_where_inside_is_judged(self):
        engine = make_engine(pixel_zone())
        engine.bind_rule(
            entry_rule(
                config=ZoneEntryConfig(
                    min_frames_in_zone=1,
                    cooldown_seconds=10.0,
                    point="center",
                )
            ),
            "zone_1",
        )

        # center (225, 155) is inside the same zone that bottom_center left.
        straddling = make_track(bbox=(150.0, 60.0, 300.0, 250.0))
        triggers = engine.process([straddling], timestamp=1.0)
        assert len(triggers) == 1
        assert triggers[0].details["probe_point"] == pytest.approx([225.0, 155.0])
