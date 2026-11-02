"""Persistent person-down state for live sessions.

The person detector often drops a motionless body once it is flat on the
ground. The rule has already opened an incident by then, but with no track the
live metadata would stop drawing a box and the operator would lose the alert.

This tracker keeps the last known fallen bbox alive independently of the person
tracker. It is refreshed by person-down triggers, confident fall-model boxes,
and any later person track that still looks fallen. A clearly upright pose
clears it; otherwise it expires only after a long stale window or when the
session ends.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from workers.cv_worker.rules.base import RuleTrigger

PERSON_DOWN_RULE_ID = "person_down"
DEFAULT_STALE_SECONDS = 300.0
GEOMETRY_ASPECT_RATIO = 1.2
UPRIGHT_CLEAR_FRAMES = 3
MIN_GEOMETRY_TRACK_FRAMES = 3


@dataclass
class DownState:
    track_id: int
    bbox: tuple[float, float, float, float]
    confidence: float
    since: float
    last_seen: float
    upright_frames: int = 0


def _bbox(value) -> tuple[float, float, float, float] | None:
    if not value or len(value) < 4:
        return None
    try:
        x1, y1, x2, y2 = (float(part) for part in value[:4])
    except (TypeError, ValueError):
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    return (x1, y1, x2, y2)


def _aspect_ratio(bbox: tuple[float, float, float, float]) -> float:
    x1, y1, x2, y2 = bbox
    return max(0.0, x2 - x1) / max(1.0, y2 - y1)


def _iou(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> float:
    ax1, ay1, ax2, ay2 = first
    bx1, by1, bx2, by2 = second
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    intersection = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if intersection <= 0.0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - intersection
    return intersection / union if union > 0.0 else 0.0


def _center_distance(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> float:
    ax = (first[0] + first[2]) / 2.0
    ay = (first[1] + first[3]) / 2.0
    bx = (second[0] + second[2]) / 2.0
    by = (second[1] + second[3]) / 2.0
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


def _strong_down(track) -> bool:
    return bool(track.fall_detected or track.pose_fall_detected)


def _strong_upright(track) -> bool:
    return bool(track.pose_checked and not track.pose_fall_detected and not track.fall_detected)


def _geometry_down(track) -> bool:
    return _aspect_ratio(track.bbox) >= GEOMETRY_ASPECT_RATIO


class DownStateTracker:
    def __init__(self, stale_seconds: float = DEFAULT_STALE_SECONDS) -> None:
        self._stale_seconds = stale_seconds
        self._states: list[DownState] = []

    def update(
        self,
        *,
        timestamp: float,
        tracks,
        falls,
        triggers: list[RuleTrigger],
    ) -> list[DownState]:
        self._apply_triggers(timestamp, triggers)
        for track in tracks or []:
            self._apply_track(timestamp, track)
        self._apply_falls(timestamp, falls or [])
        self._states = [
            state for state in self._states if timestamp - state.last_seen <= self._stale_seconds
        ]
        return list(self._states)

    def reset(self) -> None:
        self._states.clear()

    def _apply_triggers(self, timestamp: float, triggers: list[RuleTrigger]) -> None:
        for trigger in triggers:
            if trigger.rule_id != PERSON_DOWN_RULE_ID:
                continue
            bbox = _bbox(trigger.details.get("bbox"))
            if bbox is None:
                continue
            self._upsert(
                track_id=trigger.tracker_id,
                bbox=bbox,
                confidence=trigger.confidence,
                timestamp=timestamp,
            )

    def _apply_track(self, timestamp: float, track) -> None:
        state = self._find(track.tracker_id, track.bbox)
        # A fall-model hit on its own is not a person-down alert. Walking
        # through a doorway often produces one. Only a rule trigger opens
        # state; later frames may keep that box alive.
        if state is None:
            return
        if _strong_down(track) or (not _strong_upright(track) and _geometry_down(track)):
            self._mark_down(timestamp, track, state)
            return

        if state is not None and _strong_upright(track):
            state.upright_frames += 1
            if state.upright_frames >= UPRIGHT_CLEAR_FRAMES:
                self._states.remove(state)

    def _mark_down(self, timestamp: float, track, state: DownState | None) -> None:
        if state is None:
            if not _strong_down(track) and track.frames_seen < MIN_GEOMETRY_TRACK_FRAMES:
                return
            self._states.append(
                DownState(
                    track_id=track.tracker_id,
                    bbox=track.bbox,
                    confidence=track.confidence,
                    since=timestamp,
                    last_seen=timestamp,
                )
            )
            return

        state.track_id = track.tracker_id
        state.bbox = track.bbox
        state.confidence = max(state.confidence, track.confidence)
        state.last_seen = timestamp
        state.upright_frames = 0

    def _apply_falls(self, timestamp: float, falls) -> None:
        for fall in falls:
            bbox = _bbox(fall.bbox)
            if bbox is None:
                continue
            state = self._find(-1, bbox)
            if state is None:
                continue
            state.bbox = bbox
            state.confidence = max(state.confidence, float(fall.confidence))
            state.last_seen = timestamp
            state.upright_frames = 0

    def _upsert(
        self,
        *,
        track_id: int,
        bbox: tuple[float, float, float, float],
        confidence: float,
        timestamp: float,
    ) -> DownState:
        state = self._find(track_id, bbox)
        if state is None:
            state = DownState(
                track_id=track_id,
                bbox=bbox,
                confidence=confidence,
                since=timestamp,
                last_seen=timestamp,
            )
            self._states.append(state)
            return state

        state.track_id = track_id
        state.bbox = bbox
        state.confidence = max(state.confidence, confidence)
        state.last_seen = timestamp
        state.upright_frames = 0
        return state

    def _find(
        self,
        track_id: int,
        bbox: tuple[float, float, float, float],
    ) -> DownState | None:
        for state in self._states:
            if state.track_id == track_id:
                return state

        best: DownState | None = None
        best_score = 0.0
        for state in self._states:
            overlap = _iou(state.bbox, bbox)
            distance = _center_distance(state.bbox, bbox)
            diagonal = max(
                state.bbox[2] - state.bbox[0],
                state.bbox[3] - state.bbox[1],
                1.0,
            )
            if overlap < 0.05 and distance > 0.6 * diagonal:
                continue
            score = overlap + (1.0 - min(1.0, distance / diagonal))
            if score > best_score:
                best = state
                best_score = score
        return best
