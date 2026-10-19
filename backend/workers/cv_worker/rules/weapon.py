"""Weapon detection (Sprint 8A).

A :class:`WeaponRule` fires when a tracked subject carries a weapon and stays
inside a designated zone for at least the configured dwell time.  A track only
counts while ``track.weapon_detected`` is set by the enrichment stage, so a
person standing in the zone without an associated weapon never alerts; losing
the weapon is treated exactly like leaving the zone, including the optional
grace window for brief detection dropouts.

The rule mirrors the loitering pattern: residency is accumulated from the frame
cadence ``dt`` so that offline replay is reproducible, a brief exit within
``grace_seconds`` merely pauses the clock, and ``cooldown_seconds`` caps how
often the same track can alert.

.. seealso :ref:`loitering-page`
    For dwell-time mechanics see :mod:`~workers.cv_worker.rules.loitering`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from workers.cv_worker.rules.base import (
    BehaviorRule,
    RuleTrigger,
    TrackObservation,
)
from workers.cv_worker.rules.config import WeaponConfig


@dataclass
class _Episode:
    """Dwell state for one track within one zone."""

    dwell_seconds: float = 0.0
    exit_seconds: float = 0.0
    clock_started: bool = False
    triggered: bool = False
    last_triggered_at: float | None = None


@dataclass
class WeaponRule(BehaviorRule):
    """Fires one trigger when a weapon-bearing track exceeds ``dwell_seconds``."""

    rule_id: str
    rule_name: str
    zone_id: str
    zone_name: str
    severity: str
    config: WeaponConfig = field(default_factory=WeaponConfig)

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
            # Register presence even when below the confidence floor, so a
            # briefly low-confidence frame does not forget the episode and
            # restart the residency clock when confidence recovers.
            seen.add(tracker_id)

            if observation.track.confidence < self.config.min_confidence:
                continue

            episode = self._episodes.setdefault(tracker_id, _Episode())

            if observation.inside_expanded and observation.track.weapon_detected:
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
        episode.clock_started = True
        episode.dwell_seconds += dt

    def _advance_outside(self, episode: _Episode, dt: float) -> None:
        if not episode.clock_started:
            return

        episode.exit_seconds += dt
        if episode.exit_seconds <= self.config.grace_seconds:
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
                "event": "weapon",
                "residence_seconds": round(episode.dwell_seconds, 3),
                "dwell_threshold_seconds": self.config.dwell_seconds,
                "grace_seconds": self.config.grace_seconds,
                "weapon_confidence": round(track.weapon_confidence, 3),
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
