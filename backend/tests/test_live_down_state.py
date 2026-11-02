from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from app.live.down_state import DownStateTracker
from app.live.manager import LiveSession
from workers.cv_worker.rules.base import RuleTrigger

BBOX = (10.0, 10.0, 110.0, 60.0)


def trigger(
    *,
    track_id: int = 7,
    bbox: tuple[float, float, float, float] = BBOX,
    confidence: float = 0.8,
    timestamp: float = 10.0,
) -> RuleTrigger:
    return RuleTrigger(
        rule_id="person_down",
        rule_name="Person Down",
        zone_id="live",
        zone_name="Live",
        tracker_id=track_id,
        timestamp=timestamp,
        severity="high",
        confidence=confidence,
        details={"bbox": list(bbox)},
    )


def track(
    *,
    track_id: int = 7,
    bbox: tuple[float, float, float, float] = BBOX,
    confidence: float = 0.8,
    frames_seen: int = 10,
    fall_detected: bool = True,
    fall_confidence: float = 0.8,
    pose_checked: bool = False,
    pose_fall_detected: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        tracker_id=track_id,
        bbox=bbox,
        confidence=confidence,
        frames_seen=frames_seen,
        fall_detected=fall_detected,
        fall_confidence=fall_confidence,
        pose_checked=pose_checked,
        pose_fall_detected=pose_fall_detected,
    )


def fall(
    *,
    bbox: tuple[float, float, float, float],
    confidence: float = 0.9,
) -> SimpleNamespace:
    return SimpleNamespace(bbox=bbox, confidence=confidence)


def test_trigger_state_survives_frames_without_a_person_track() -> None:
    tracker = DownStateTracker()
    tracker.update(
        timestamp=10.0,
        tracks=[],
        falls=[],
        triggers=[trigger()],
    )

    states = tracker.update(timestamp=12.0, tracks=[], falls=[], triggers=[])

    assert len(states) == 1
    assert states[0].track_id == 7
    assert states[0].bbox == BBOX
    assert states[0].since == 10.0


def test_fall_box_refreshes_state_when_person_track_is_gone() -> None:
    tracker = DownStateTracker()
    tracker.update(timestamp=10.0, tracks=[], falls=[], triggers=[trigger()])
    new_bbox = (20.0, 20.0, 140.0, 70.0)

    states = tracker.update(
        timestamp=11.0,
        tracks=[],
        falls=[fall(bbox=new_bbox)],
        triggers=[],
    )

    assert len(states) == 1
    assert states[0].bbox == new_bbox
    assert states[0].last_seen == 11.0


def test_new_track_id_matches_existing_state_by_overlap() -> None:
    tracker = DownStateTracker()
    tracker.update(timestamp=10.0, tracks=[], falls=[], triggers=[trigger()])

    states = tracker.update(
        timestamp=11.0,
        tracks=[track(track_id=9, bbox=(12.0, 10.0, 112.0, 60.0))],
        falls=[],
        triggers=[],
    )

    assert len(states) == 1
    assert states[0].track_id == 9


def test_clear_upright_pose_removes_state() -> None:
    tracker = DownStateTracker()
    tracker.update(timestamp=10.0, tracks=[], falls=[], triggers=[trigger()])

    upright = track(
        bbox=(10.0, 10.0, 60.0, 160.0),
        fall_detected=False,
        fall_confidence=0.0,
        pose_checked=True,
        pose_fall_detected=False,
    )
    states = []
    for timestamp in (11.0, 12.0, 13.0):
        states = tracker.update(
            timestamp=timestamp,
            tracks=[upright],
            falls=[],
            triggers=[],
        )

    assert states == []


def test_stale_state_expires() -> None:
    tracker = DownStateTracker(stale_seconds=5.0)
    tracker.update(timestamp=10.0, tracks=[], falls=[], triggers=[trigger()])

    states = tracker.update(timestamp=16.0, tracks=[], falls=[], triggers=[])

    assert states == []


def test_geometry_only_state_requires_multiple_track_frames() -> None:
    tracker = DownStateTracker()
    horizontal = track(
        frames_seen=1,
        fall_detected=False,
        fall_confidence=0.0,
    )

    states = tracker.update(
        timestamp=10.0,
        tracks=[horizontal],
        falls=[],
        triggers=[],
    )

    assert states == []


def test_live_payload_keeps_synthetic_box_and_event_after_track_is_lost() -> None:
    captured: list[dict] = []

    class ImmediateLoop:
        def call_soon_threadsafe(self, callback, *args) -> None:
            callback(*args)

    session = LiveSession.__new__(LiveSession)
    session._down_state = DownStateTracker()
    session._loop = ImmediateLoop()
    session._set_metadata = captured.append
    frame = SimpleNamespace(
        data=np.zeros((480, 640, 3), dtype=np.uint8),
        timestamp=10.0,
    )
    analysis = SimpleNamespace(weapons=[], falls=[])

    session._on_processed(frame, None, [], analysis, [trigger()])
    session._on_processed(
        SimpleNamespace(data=frame.data, timestamp=11.0),
        None,
        [],
        analysis,
        [],
    )

    payload = captured[-1]
    assert payload["detections"][0]["track_id"] == 7
    assert payload["detections"][0]["fall"] is True
    assert payload["events"][0]["rule"] == "person_down"
    assert payload["events"][0]["details"]["persistent"] is True
