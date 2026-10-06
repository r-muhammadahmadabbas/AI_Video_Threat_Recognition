"""Restricted zone entry (Sprint 3B).

Entry and exit are deliberately asymmetric so a subject standing on a zone
boundary does not alternate between inside and outside on successive frames:

* to become ``inside`` the probe point must be within the *expanded* ring;
* to become ``outside`` it must be outside the *shrunk* ring.

Anything between the two rings is the hysteresis band, where the previous state
is retained.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field

from workers.cv_worker.rules.base import (
    BehaviorRule,
    RuleTrigger,
    TrackObservation,
)
from workers.cv_worker.rules.config import ZoneEntryConfig


class PresenceState(enum.StrEnum):
    INSIDE = "inside"
    OUTSIDE = "outside"


@dataclass
class _TrackPresence:
    state: PresenceState = PresenceState.OUTSIDE
    consecutive_inside_frames: int = 0
    triggered: bool = False
    last_triggered_at: float | None = None


@dataclass
class ZoneEntryRule(BehaviorRule):
    """Opens one trigger when a track enters a restricted zone.

    The cooldown is enforced per track, so two different subjects breaching the
    same zone at once still each get their own incident, while one subject
    lingering inside does not re-alert on every frame.
    """

    rule_id: str
    rule_name: str
    zone_id: str
    zone_name: str
    severity: str
    config: ZoneEntryConfig = field(default_factory=ZoneEntryConfig)

    def __post_init__(self) -> None:
        self._presence: dict[int, _TrackPresence] = {}

    def update(
        self,
        observations: list[TrackObservation],
        timestamp: float,
        dt: float = 0.0,  # noqa: ARG002 - part of the BehaviorRule interface
    ) -> list[RuleTrigger]:
        """Open at most one trigger per track per cooldown window.

        ``dt`` is accepted for interface symmetry with duration-driven rules;
        entry is a discrete crossing, so nothing here integrates time.
        """
        triggers: list[RuleTrigger] = []
        seen: set[int] = set()

        for observation in observations:
            tracker_id = observation.track.tracker_id
            # Register presence even when below the confidence floor, so a
            # briefly low-confidence frame forgets state and causes a
            # duplicate incident when confidence recovers.
            seen.add(tracker_id)

            if observation.track.confidence < self.config.min_confidence:
                continue

            state = self._presence.setdefault(tracker_id, _TrackPresence())

            was_inside = state.state == PresenceState.INSIDE
            now_inside = self._next_state(observation, was_inside)

            if now_inside:
                state.consecutive_inside_frames += 1
            else:
                state.consecutive_inside_frames = 0
                state.triggered = False

            if was_inside and not now_inside:
                state.state = PresenceState.OUTSIDE
                continue

            if not now_inside:
                state.state = PresenceState.OUTSIDE
                continue

            state.state = PresenceState.INSIDE

            if state.triggered:
                continue
            if state.consecutive_inside_frames < self.config.min_frames_in_zone:
                continue
            if not self._cooldown_elapsed(state, timestamp):
                continue

            state.triggered = True
            state.last_triggered_at = timestamp
            triggers.append(self._make_trigger(observation, timestamp))

        self._forget_absent(seen)
        return triggers

    def _next_state(self, observation: TrackObservation, was_inside: bool) -> bool:
        """Resolve hysteresis for one frame.

        The two rings are paired so that a subject must be *clearly* inside to
        register an entry, and must be *clearly* outside to register an exit.
        A subject sitting anywhere in the band between the rings therefore keeps
        whatever state it already had, which is what stops boundary flicker.
        """
        if was_inside:
            return observation.inside_expanded
        return observation.inside_shrunk

    def _cooldown_elapsed(self, state: _TrackPresence, timestamp: float) -> bool:
        if state.last_triggered_at is None:
            return True
        return timestamp - state.last_triggered_at >= self.config.cooldown_seconds

    def _make_trigger(
        self, observation: TrackObservation, timestamp: float
    ) -> RuleTrigger:
        track = observation.track
        return RuleTrigger(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            zone_id=self.zone_id,
            zone_name=self.zone_name,
            tracker_id=track.tracker_id,
            timestamp=timestamp,
            severity=self.severity,
            confidence=track.confidence,
            details={
                "event": "restricted_zone_entry",
                "frames_in_zone": self._presence[track.tracker_id].consecutive_inside_frames,
                "bbox": list(track.bbox),
                "probe_point": list(observation.probe_point),
            },
        )

    def _forget_absent(self, seen: set[int]) -> None:
        """Drop state for tracks the tracker no longer reports.

        Without this, ``self._presence`` would grow without bound on a long
        running camera and ``triggered`` flags would suppress a re-entry of the
        same track id forever.
        """
        for tracker_id in [tid for tid in self._presence if tid not in seen]:
            del self._presence[tracker_id]

    def reset(self) -> None:
        self._presence.clear()

    def is_inside(self, tracker_id: int) -> bool:
        state = self._presence.get(tracker_id)
        return state is not None and state.state == PresenceState.INSIDE
