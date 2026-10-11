"""Physical-altercation candidate detection (Sprint 6A/6B).

The rule scores *pairs* of tracked people inside the bound zone, not
individuals: an altercation is an interaction. For each nearby pair it keeps a
rolling window of recent geometry and requires several consecutive frames of
active motion and high relative speed before opening a trigger.

The plan is explicit that this is a candidate signal, not a verdict on what the
people are doing: the incident is labeled "potential physical altercation" and
the trigger carries the exact time window and numbers the rule used, so an
operator can review the clip with full context.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from workers.cv_worker.rules.base import (
    BehaviorRule,
    RuleTrigger,
    TrackObservation,
)
from workers.cv_worker.rules.config import AltercationConfig

if TYPE_CHECKING:
    from workers.cv_worker.tracker import TrackedObject


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


@dataclass
class _Sample:
    """One frame of a pair's geometry inside the rolling window."""

    timestamp: float
    center_a: tuple[float, float]
    center_b: tuple[float, float]
    distance: float


@dataclass
class _PairEpisode:
    """Temporal state for one nearby track pair."""

    consecutive_nearby_frames: int = 0
    aggressive_frames: int = 0
    last_triggered_at: float | None = None
    samples: deque[_Sample] = field(default_factory=deque)
    relative_speed_px_s: float = 0.0
    movement_a_px_s: float = 0.0
    movement_b_px_s: float = 0.0


@dataclass
class AltercationRule(BehaviorRule):
    """Opens one trigger when a nearby pair persistently shows aggressive motion.

    Participation requires both members to be definitively inside the bound zone
    and above the confidence floor, so passers-by near a line do not contribute.
    """

    rule_id: str
    rule_name: str
    zone_id: str
    zone_name: str
    severity: str
    config: AltercationConfig = field(default_factory=AltercationConfig)

    def __post_init__(self) -> None:
        self._episodes: dict[tuple[int, int], _PairEpisode] = {}

    def update(
        self,
        observations: list[TrackObservation],
        timestamp: float,
        dt: float = 0.0,  # noqa: ARG002 - part of the BehaviorRule interface
    ) -> list[RuleTrigger]:
        """Score every pair this frame and return any new triggers."""
        eligible = [o for o in observations if self._participates(o)]
        seen_pairs: set[tuple[int, int]] = set()

        # Build each observation's center once; avoids recomputing per pair.
        centers = {o.track.tracker_id: o.track.center for o in eligible}

        triggers: list[RuleTrigger] = []

        for i, left in enumerate(eligible):
            for right in eligible[i + 1 :]:
                pair = (left.track.tracker_id, right.track.tracker_id)
                if pair[0] > pair[1]:
                    pair = (pair[1], pair[0])
                seen_pairs.add(pair)

                episode = self._episodes.setdefault(pair, _PairEpisode())
                self._advance_pair(episode, centers, left.track, right.track, timestamp)

                if (
                    episode.aggressive_frames >= self.config.min_aggression_frames
                    and self._cooldown_elapsed(episode, timestamp)
                ):
                    episode.last_triggered_at = timestamp
                    triggers.append(
                        self._make_trigger(episode, pair, left.track, right.track, timestamp)
                    )

        self._forget_absent(seen_pairs)
        return triggers

    def _participates(self, observation: TrackObservation) -> bool:
        return (
            observation.definitively_inside
            and observation.track.confidence >= self.config.min_confidence
        )

    def _advance_pair(
        self,
        episode: _PairEpisode,
        centers: dict[int, tuple[float, float]],
        left: TrackedObject,
        right: TrackedObject,
        timestamp: float,
    ) -> None:
        """Update one pair's state from the current frame's geometry."""
        center_a = centers[left.tracker_id]
        center_b = centers[right.tracker_id]
        distance = _distance(center_a, center_b)

        if distance > self.config.max_pair_distance_px:
            episode.consecutive_nearby_frames = 0
            episode.aggressive_frames = 0
            episode.samples.clear()
            return

        episode.consecutive_nearby_frames += 1
        episode.samples.append(
            _Sample(
                timestamp=timestamp,
                center_a=center_a,
                center_b=center_b,
                distance=distance,
            )
        )
        self._prune_samples(episode, timestamp)

        if not self._signals_met(episode):
            episode.aggressive_frames = 0
            return
        episode.aggressive_frames += 1

    def _prune_samples(self, episode: _PairEpisode, timestamp: float) -> None:
        """Drop samples outside the window, keeping at least one frame's worth.

        One retained sample means a single-frame approach cannot compute a
        velocity yet, which is what gives the rule its persistence requirement.
        """
        while (
            len(episode.samples) > 1
            and timestamp - episode.samples[0].timestamp > self.config.speed_window_seconds
        ):
            episode.samples.popleft()

    def _signals_met(self, episode: _PairEpisode) -> bool:
        """Whether both "active motion" signals hold over the window.

        Two signals must hold together (Sprint 6B): both members move, and the
        pair's relative centroid speed is high. People standing close to talk
        move little, so they fail the first check and never accumulate frames.
        """
        if len(episode.samples) < 2:
            return False

        prev = episode.samples[-2]
        now = episode.samples[-1]
        span = now.timestamp - prev.timestamp
        if span <= 0:
            return False

        movement_a = _distance(now.center_a, prev.center_a) / span
        movement_b = _distance(now.center_b, prev.center_b) / span
        relative_speed = abs(now.distance - prev.distance) / span

        both_move = (
            movement_a >= self.config.min_movement_px_per_s
            and movement_b >= self.config.min_movement_px_per_s
        )
        fast_close = relative_speed >= self.config.min_relative_speed_px_per_s

        episode.relative_speed_px_s = relative_speed
        episode.movement_a_px_s = movement_a
        episode.movement_b_px_s = movement_b
        return both_move and fast_close

    def _cooldown_elapsed(self, episode: _PairEpisode, timestamp: float) -> bool:
        if episode.last_triggered_at is None:
            return True
        return timestamp - episode.last_triggered_at >= self.config.cooldown_seconds

    def _make_trigger(
        self,
        episode: _PairEpisode,
        pair: tuple[int, int],
        left: TrackedObject,
        right: TrackedObject,
        timestamp: float,
    ) -> RuleTrigger:
        return RuleTrigger(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            zone_id=self.zone_id,
            zone_name=self.zone_name,
            tracker_id=pair[0],
            timestamp=timestamp,
            severity=self.severity,
            confidence=min(left.confidence, right.confidence),
            details={
                "event": "physical_altercation",
                "tracker_ids": list(pair),
                "center_distance_px": round(episode.samples[-1].distance, 2),
                "relative_speed_px_per_s": round(episode.relative_speed_px_s, 2),
                "movement_a_px_per_s": round(episode.movement_a_px_s, 2),
                "movement_b_px_per_s": round(episode.movement_b_px_s, 2),
                "window_seconds": self.config.speed_window_seconds,
                "pair_tracker_id": pair[1],
                "aggressive_frames": episode.aggressive_frames,
                "min_aggression_required": self.config.min_aggression_frames,
                "max_pair_distance_px": self.config.max_pair_distance_px,
                "bboxes": {
                    str(left.tracker_id): list(left.bbox),
                    str(right.tracker_id): list(right.bbox),
                },
                "probe_points": {
                    str(left.tracker_id): list(left.bottom_center),
                    str(right.tracker_id): list(right.bottom_center),
                },
            },
        )

    def _forget_absent(self, seen_pairs: set[tuple[int, int]]) -> None:
        """Drop pairs a member of which stopped being observed this frame."""
        for pair in [p for p in self._episodes if p not in seen_pairs]:
            del self._episodes[pair]

    def reset(self) -> None:
        self._episodes.clear()
