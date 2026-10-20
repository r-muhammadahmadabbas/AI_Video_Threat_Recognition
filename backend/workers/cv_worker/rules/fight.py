"""Fight detection from the violence classifier's per-frame verdict.

The classifier fires on individual frames; a fight is a sustained episode.
This rule requires ``min_consecutive_frames`` positive frames in a row, emits
one trigger when that run starts, and stays quiet until a non-positive frame
closes the episode (plus the usual cooldown).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from workers.cv_worker.rules.base import (
    BehaviorRule,
    RuleTrigger,
    TrackObservation,
)
from workers.cv_worker.rules.config import FightConfig


@dataclass
class FightRule(BehaviorRule):
    """Opens one trigger per sustained run of violence-model hits."""

    rule_id: str
    rule_name: str
    zone_id: str
    zone_name: str
    severity: str
    config: FightConfig = field(default_factory=FightConfig)

    def __post_init__(self) -> None:
        self._streak = 0
        self._active = False
        self._last_triggered_at: float | None = None

    def update(
        self,
        observations: list[TrackObservation],
        timestamp: float,
        dt: float = 0.0,  # noqa: ARG002 - part of the BehaviorRule interface
    ) -> list[RuleTrigger]:
        checked = [
            observation
            for observation in observations
            if observation.track.violence_checked
        ]
        if not checked:
            # The model did not run on this frame. Silence is not a negative.
            return []

        flagged = [
            observation
            for observation in checked
            if observation.inside_expanded
            and observation.track.violence_detected
            and observation.track.confidence >= self.config.min_confidence
        ]

        if not flagged:
            self._streak = 0
            self._active = False
            return []

        self._streak += 1
        if self._streak < self.config.min_consecutive_frames or self._active:
            return []
        if (
            self._last_triggered_at is not None
            and timestamp - self._last_triggered_at < self.config.cooldown_seconds
        ):
            return []

        self._active = True
        self._last_triggered_at = timestamp
        subject = max(flagged, key=lambda observation: observation.track.confidence)
        track = subject.track
        return [
            RuleTrigger(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                zone_id=self.zone_id,
                zone_name=self.zone_name,
                tracker_id=track.tracker_id,
                timestamp=timestamp,
                severity=self.severity,
                confidence=track.confidence,
                details={
                    "event": "fight",
                    "source": "violence_model",
                    "consecutive_frames": self._streak,
                    "bbox": list(track.bbox),
                    "probe_point": list(subject.probe_point),
                },
            )
        ]

    def reset(self) -> None:
        self._streak = 0
        self._active = False
        self._last_triggered_at = None
