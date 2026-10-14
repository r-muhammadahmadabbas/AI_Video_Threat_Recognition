"""Weapon detection (Sprint 8A).

A :class:`WeaponRule` fires when a tracked subject carries a weapon and stays
inside a designated zone for at least the configured dwell time.  The rule
mirrors the loitering pattern: residency is accumulated from the frame cadence
``dt`` so that offline replay is reproducible.

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
        self._triggered_tracker_ids: set[int] = set()

    def update(
        self,
        observations: list[TrackObservation],
        timestamp: float,
        dt: float = 0.0,
    ) -> list[RuleTrigger]:
        triggers: list[RuleTrigger] = []
        seen: set[int] = set()

        for observation in observations:
            tracker_id = observation.track.tracker_id

            if observation.track.confidence < self.config.min_confidence:
                continue

            episode = self._episodes.setdefault(tracker_id, _Episode())

            if observation.inside_expanded:
                if not episode.clock_started:
                    episode.clock_started = True
                episode.dwell_seconds += dt

                if (
                    episode.dwell_seconds >= self.config.dwell_seconds
                    and not episode.triggered
                    and self._cooldown_elapsed(timestamp, episode.last_triggered_at)
                ):
                    episode.triggered = True
                    episode.last_triggered_at = timestamp
                    self._triggered_tracker_ids.add(tracker_id)
                    dwell_at_trigger = episode.dwell_seconds
                    triggers.append(
                        self._make_trigger(observation, timestamp, dwell_at_trigger)
                    )
            else:
                # Weapon left the zone - reset the clock.
                episode.dwell_seconds = 0.0
                episode.clock_started = False

        self._forget_absent(seen)
        return triggers

    @staticmethod
    def _cooldown_elapsed(timestamp: float, last_triggered_at: float | None = None) -> bool:
        if last_triggered_at is None:
            return True
        return timestamp - last_triggered_at >= WeaponConfig().cooldown_seconds

    def _make_trigger(
        self,
        observation: TrackObservation,
        timestamp: float,
        dwell_at_trigger: float,
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
                "event": "weapon",
                "residence_seconds": round(dwell_at_trigger, 3),
                "dwell_threshold_seconds": self.config.dwell_seconds,
                "bbox": list(track.bbox),
            },
        )

    def _forget_absent(self, seen: set[int]) -> None:
        for tid in list(self._episodes.keys()):
            if tid not in seen:
                del self._episodes[tid]
        self._triggered_tracker_ids.clear()

    def reset(self) -> None:
        self._episodes.clear()
        self._triggered_tracker_ids.clear()

    @property
    def residence_seconds(self) -> dict[int, float]:
        return {
            tid: ep.dwell_seconds
            for tid, ep in self._episodes.items()
            if ep.clock_started
        }
