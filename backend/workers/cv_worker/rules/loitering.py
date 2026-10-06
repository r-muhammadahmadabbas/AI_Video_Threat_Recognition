"""Loitering (Sprint 3C).

Loitering is a temporal rule: a subject must stay in a zone long enough to be
worth an operator's attention. Two behaviours make that workable in practice.

**Continuous residency.** Dwell time belongs to a single *episode* of
continuously present time. Someone who leaves and comes back has not been
loitering for the combined duration of two short visits.

**Brief-exit grace.** An exit shorter than ``grace_seconds`` merely pauses the
clock; the episode survives and accumulates on either side. An exit that
outlasts the grace window ends the episode and clears its dwell time. With
``grace_seconds`` at zero, any exit breaks continuity, so pacing in and out
never accrues dwell time at all.

Residency is accumulated from the frame cadence (``dt``) rather than wall clock
so that offline replay of a clip produces identical dwell on every run.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from workers.cv_worker.rules.base import (
    BehaviorRule,
    RuleTrigger,
    TrackObservation,
)
from workers.cv_worker.rules.config import LoiterConfig


@dataclass
class _Episode:
    """Dwell state for one track within one zone."""

    dwell_seconds: float = 0.0
    exit_seconds: float = 0.0
    consecutive_inside_frames: int = 0
    clock_started: bool = False
    triggered: bool = False
    last_triggered_at: float | None = None


@dataclass
class LoiterRule(BehaviorRule):
    """Opens one trigger when a track's residency exceeds ``dwell_seconds``."""

    rule_id: str
    rule_name: str
    zone_id: str
    zone_name: str
    severity: str
    config: LoiterConfig = field(default_factory=LoiterConfig)

    def __post_init__(self) -> None:
        self._episodes: dict[int, _Episode] = {}

    def update(
        self,
        observations: list[TrackObservation],
        timestamp: float,
        dt: float = 0.0,
    ) -> list[RuleTrigger]:
        """Advance residency for every observation and return new triggers.

        ``dt`` is the seconds elapsed since the previous frame. Use the frame
        cadence, never wall-clock time, so replay stays reproducible.
        """
        triggers: list[RuleTrigger] = []
        seen: set[int] = set()

        for observation in observations:
            tracker_id = observation.track.tracker_id
            seen.add(tracker_id)
            episode = self._episodes.setdefault(tracker_id, _Episode())

            if observation.inside_expanded:
                self._advance_inside(episode, dt)
            else:
                self._advance_outside(episode, dt)

            if not episode.clock_started or episode.triggered:
                continue
            if episode.dwell_seconds < self.config.dwell_seconds:
                continue
            if not self._cooldown_elapsed(episode, timestamp):
                continue

            episode.triggered = True
            episode.last_triggered_at = timestamp
            triggers.append(self._make_trigger(observation, timestamp))

        self._forget_absent(seen)
        return triggers

    def _advance_inside(self, episode: _Episode, dt: float) -> None:
        episode.exit_seconds = 0.0
        episode.consecutive_inside_frames += 1

        if (
            not episode.clock_started
            and episode.consecutive_inside_frames >= self.config.require_min_frames
        ):
            episode.clock_started = True

        if episode.clock_started:
            episode.dwell_seconds += dt

    def _advance_outside(self, episode: _Episode, dt: float) -> None:
        episode.consecutive_inside_frames = 0
        if not episode.clock_started:
            return

        episode.exit_seconds += dt
        if self.config.exit_is_tolerated(episode.exit_seconds):
            return

        # The exit outlasted the grace window: this episode is over.
        self._end_episode(episode)

    @staticmethod
    def _end_episode(episode: _Episode) -> None:
        """Clear episode-local state while preserving the cooldown timestamp.

        ``last_triggered_at`` deliberately survives so that repeatedly leaving
        and re-entering cannot be used to dodge a rule's cooldown, but
        ``triggered`` must go or the next episode could never alert.
        """
        episode.dwell_seconds = 0.0
        episode.exit_seconds = 0.0
        episode.clock_started = False
        episode.consecutive_inside_frames = 0
        episode.triggered = False

    def _cooldown_elapsed(self, episode: _Episode, timestamp: float) -> bool:
        if episode.last_triggered_at is None:
            return True
        return timestamp - episode.last_triggered_at >= self.config.cooldown_seconds

    def _make_trigger(
        self, observation: TrackObservation, timestamp: float
    ) -> RuleTrigger:
        track = observation.track
        episode = self._episodes[track.tracker_id]
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
                "event": "loitering",
                "residence_seconds": round(episode.dwell_seconds, 3),
                "dwell_threshold_seconds": self.config.dwell_seconds,
                "grace_seconds": self.config.grace_seconds,
                "bbox": list(track.bbox),
            },
        )

    def _forget_absent(self, seen: set[int]) -> None:
        """Drop episodes for tracks the tracker no longer reports.

        Without this ``self._episodes`` would grow without bound on a long
        running camera, and a stale ``triggered`` flag would suppress a later
        track that happened to reuse the same id.
        """
        for tracker_id in [tid for tid in self._episodes if tid not in seen]:
            del self._episodes[tracker_id]

    def reset(self) -> None:
        self._episodes.clear()

    @property
    def residence_seconds(self) -> dict[int, float]:
        return {
            tid: ep.dwell_seconds
            for tid, ep in self._episodes.items()
            if ep.clock_started
        }