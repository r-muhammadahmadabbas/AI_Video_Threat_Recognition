"""Shared helpers for building rule-engine fixtures in tests."""

from __future__ import annotations

from workers.cv_worker.detector import Detection
from workers.cv_worker.rules.base import TrackObservation, Zone, ZoneRuntime
from workers.cv_worker.rules.config import ZoneConfig, ZoneEntryConfig
from workers.cv_worker.rules.geometry import Polygon
from workers.cv_worker.tracker import TrackState, TrackedObject


def make_track(
    tracker_id: int = 1,
    bbox: tuple[float, float, float, float] = (100.0, 100.0, 200.0, 300.0),
    confidence: float = 0.9,
    class_name: str = "person",
    class_id: int = 0,
) -> TrackedObject:
    return TrackedObject(
        tracker_id=tracker_id,
        bbox=bbox,
        confidence=confidence,
        class_id=class_id,
        class_name=class_name,
        state=TrackState.TRACKED,
        first_seen_timestamp=0.0,
        last_seen_timestamp=0.0,
        frames_seen=1,
    )


def make_zone(
    zone_id: str = "zone_1",
    name: str = "Restricted Area",
    vertices: list[tuple[float, float]] | None = None,
    is_active: bool = True,
) -> Zone:
    if vertices is None:
        vertices = [(100.0, 100.0), (300.0, 100.0), (300.0, 300.0), (100.0, 300.0)]
    return Zone(
        zone_id=zone_id,
        name=name,
        polygon=Polygon.from_vertices(vertices),
        is_active=is_active,
        config=ZoneConfig(),
    )


def make_zone_runtime(
    zone: Zone,
    entry_margin: float = 1.02,
    exit_margin: float = 0.98,
) -> ZoneRuntime:
    return ZoneRuntime(
        zone=zone,
        expanded=zone.polygon.scaled_about_centroid(entry_margin),
        shrunk=zone.polygon.scaled_about_centroid(exit_margin),
    )


def make_observation(
    track: TrackedObject,
    runtime: ZoneRuntime,
    point_choice: str = "bottom_center",
) -> TrackObservation:
    from workers.cv_worker.rules.base import probe_point_for

    probe = probe_point_for(track, point_choice)
    return TrackObservation(
        track=track,
        inside_expanded=runtime.expanded.contains(probe),
        inside_shrunk=runtime.shrunk.contains(probe),
        probe_point=probe,
    )


def entry_config(**overrides) -> ZoneEntryConfig:
    return ZoneEntryConfig(**overrides)


def detection_to_track_bbox(x: float, y: float, w: float = 100.0, h: float = 200.0):
    return Detection(
        bbox=(x, y, x + w, y + h), confidence=0.9, class_id=0, class_name="person"
    )