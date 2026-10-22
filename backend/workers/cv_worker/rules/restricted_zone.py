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
    last_seen_at: float = 0.0


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
            # Keep the track registered even below the confidence floor. A
            # briefly weak detection must not look like an absence, because
            # that would forget the presence state and duplicate the incident
            # when confidence recovers.
            seen.add(tracker_id)

            state = self._presence.get(tracker_id)
            if state is not None:
                state.last_seen_at = timestamp

            if observation.track.confidence < self.config.min_confidence:
                continue

            if state is None:
                state = _TrackPresence(last_seen_at=timestamp)
                self._presence[tracker_id] = state

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

        self._forget_absent(seen, timestamp)
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

    def _forget_absent(self, seen: set[int], timestamp: float) -> None:
        """Age state for tracks the tracker no longer reports.

        A short detection dropout keeps the presence state so reappearing
        inside the same zone is not mistaken for a second entry. Once the gap
        exceeds ``dropout_grace_seconds`` the state is dropped, which both
        bounds memory and lets a later track reuse the id for a real entry.
        With a zero grace the state is dropped immediately.
        """
        for tracker_id in [tid for tid in self._presence if tid not in seen]:
            state = self._presence[tracker_id]
            if (
                self.config.dropout_grace_seconds <= 0.0
                or timestamp - state.last_seen_at > self.config.dropout_grace_seconds
            ):
                del self._presence[tracker_id]

    def reset(self) -> None:
        self._presence.clear()

    def is_inside(self, tracker_id: int) -> bool:
        state = self._presence.get(tracker_id)
        return state is not None and state.state == PresenceState.INSIDE
