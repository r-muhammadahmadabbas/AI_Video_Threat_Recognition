"""Person-down (horizontal posture) detection (Sprint 5A/5B).

A subject is considered "down" when their bounding box is wider than tall
by a configurable margin. This is evaluated per-frame on the track's
current bbox and only for tracks that are inside the bound zone.

The rule is stateful: the aspect ratio must exceed the threshold for
``min_frames_down`` consecutive frames before triggering, with a per-track
cooldown to prevent alert storms.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from workers.cv_worker.rules.base import (
    BehaviorRule,
    RuleTrigger,
    TrackObservation,
)
from workers.cv_worker.rules.config import PersonDownConfig


@dataclass
class _DownEpisode:
    """Temporal state for one track's horizontal posture."""

    consecutive_down_frames: int = 0
    last_triggered_at: float | None = None


@dataclass
class PersonDownRule(BehaviorRule):
    """Opens one trigger when a track's aspect ratio exceeds the threshold
    for enough consecutive frames."""

    rule_id: str
    rule_name: str
    zone_id: str
    zone_name: str
    severity: str
    config: PersonDownConfig = field(default_factory=PersonDownConfig)

    def __post_init__(self) -> None:
        self._episodes: dict[int, _DownEpisode] = {}

    def update(
        self,
        observations: list[TrackObservation],
        timestamp: float,
        dt: float = 0.0,  # noqa: ARG002 - part of the BehaviorRule interface
    ) -> list[RuleTrigger]:
        """Evaluate aspect ratio for each track in the zone."""
        triggers: list[RuleTrigger] = []
        seen: set[int] = set()

        for observation in observations:
            tracker_id = observation.track.tracker_id
            seen.add(tracker_id)

            if observation.track.confidence < self.config.min_confidence:
                continue

            episode = self._episodes.setdefault(tracker_id, _DownEpisode())

            if not observation.inside_expanded:
                episode.consecutive_down_frames = 0
                continue

            bbox = observation.track.bbox
            x1, y1, x2, y2 = bbox
            width = max(0.0, x2 - x1)
            height = max(1.0, y2 - y1)
            aspect_ratio = width / height

            is_down = aspect_ratio >= self.config.aspect_ratio_threshold

            if is_down:
                episode.consecutive_down_frames += 1
            else:
                episode.consecutive_down_frames = 0

            if not is_down:
                continue

            if episode.consecutive_down_frames < self.config.min_frames_down:
                continue
            if not self._cooldown_elapsed(episode, timestamp):
                continue

            episode.last_triggered_at = timestamp
            triggers.append(
                self._make_trigger(
                    observation, timestamp, aspect_ratio, episode.consecutive_down_frames
                )
            )

        self._forget_absent(seen)
        return triggers

    def _cooldown_elapsed(self, episode: _DownEpisode, timestamp: float) -> bool:
        if episode.last_triggered_at is None:
            return True
        return timestamp - episode.last_triggered_at >= self.config.cooldown_seconds

    def _make_trigger(
        self,
        observation: TrackObservation,
        timestamp: float,
        aspect_ratio: float,
        consecutive_down_frames: int,
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
                "event": "person_down",
                "aspect_ratio": round(aspect_ratio, 3),
                "threshold": self.config.aspect_ratio_threshold,
                "consecutive_frames_down": consecutive_down_frames,
                "min_frames_required": self.config.min_frames_down,
                "bbox": list(track.bbox),
                "probe_point": list(observation.probe_point),
            },
        )

    def _forget_absent(self, seen: set[int]) -> None:
        for tracker_id in [tid for tid in self._episodes if tid not in seen]:
            del self._episodes[tracker_id]

    def reset(self) -> None:
        self._episodes.clear()
