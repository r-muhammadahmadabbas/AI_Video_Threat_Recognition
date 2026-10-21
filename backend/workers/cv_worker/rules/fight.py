"""Fight detection from the violence classifier's per-frame verdict.

The classifier fires on individual frames; a fight is a sustained episode.
This rule requires ``min_consecutive_frames`` positive frames in a row, emits
one trigger when that run starts, and stays quiet until a non-positive frame
closes the episode (plus the usual cooldown).

A frame-level classifier also marks normal fast motion, coordinated crowd
movement, hugging and camera shake. The classifier verdict is therefore only a
candidate: before firing, the rule also requires a nearby pair of moving people
whose velocity vectors differ. Two people moving together (camera shake or a
drifting crowd) have almost no relative speed, and hugging has none at all.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field

from workers.cv_worker.rules.base import (
    BehaviorRule,
    RuleTrigger,
    TrackObservation,
)
from workers.cv_worker.rules.config import FightConfig

_Center = tuple[float, float]


@dataclass
class _TrackMotion:
    """Recent centers for one track, pruned to the motion window."""

    samples: deque[tuple[float, _Center]] = field(default_factory=deque)


@dataclass
class FightRule(BehaviorRule):
    """Opens one trigger per sustained run of qualifying violence-model hits."""

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
        self._last_fall_at: float | None = None
        self._last_strong_fall_at: float | None = None
        self._motion: dict[int, _TrackMotion] = {}

    def update(
        self,
        observations: list[TrackObservation],
        timestamp: float,
        dt: float = 0.0,  # noqa: ARG002 - part of the BehaviorRule interface
    ) -> list[RuleTrigger]:
        self._record_motion(observations, timestamp)

        fall_confidences = [
            observation.track.fall_confidence
            for observation in observations
            if observation.track.fall_detected
        ]
        if fall_confidences:
            self._last_fall_at = timestamp
            if any(
                confidence == 0.0
                or confidence >= self.config.strong_fall_confidence
                for confidence in fall_confidences
            ):
                self._last_strong_fall_at = timestamp
        weak_fall_recent = (
            self._last_fall_at is not None
            and timestamp - self._last_fall_at
            <= self.config.weak_fall_suppression_seconds
        )
        strong_fall_recent = (
            self._last_strong_fall_at is not None
            and timestamp - self._last_strong_fall_at
            <= self.config.fall_suppression_seconds
        )
        if weak_fall_recent or strong_fall_recent:
            # A fall also looks violent to the classifier; keep the single
            # person-down alert instead of adding a fight alert.
            self._streak = 0
            self._active = False
            return []

        checked = [
            observation
            for observation in observations
            if observation.track.violence_checked
        ]
        if not checked:
            # The model did not run on this frame. Silence is not a negative.
            return []

        eligible = [
            observation
            for observation in observations
            if observation.inside_expanded
            and observation.track.confidence >= self.config.min_confidence
        ]
        flagged = [
            observation
            for observation in checked
            if observation.inside_expanded
            and observation.track.violence_detected
            and observation.track.confidence >= self.config.min_confidence
        ]

        if len(eligible) > self.config.max_zone_tracks or not flagged:
            # A frame-level classifier marks everyone in a busy scene. Treat
            # that as crowd movement, not as a specific fight. No flagged
            # track means the episode is over.
            self._streak = 0
            self._active = False
            return []

        interaction = self._find_interaction(flagged)
        if interaction is None:
            if self._has_motion_history():
                # The model says "violence" but there is no pair of nearby
                # people moving differently. This is the normal-fast-motion,
                # hugging, camera-shake and crowd case; drop the streak so a
                # later normal movement cannot reuse stale classifier evidence.
                self._streak = 0
                self._active = False
            else:
                # First frame of a track has no velocity yet. It still counts
                # as classifier persistence, but cannot open a trigger alone.
                self._streak += 1
            return []

        self._streak += 1
        if (
            self._streak < self.config.min_consecutive_frames
            or self._active
            or (
                self._last_triggered_at is not None
                and timestamp - self._last_triggered_at
                < self.config.cooldown_seconds
            )
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
                    "interacting_tracker_ids": list(interaction["tracker_ids"]),
                    "pair_distance_px": round(interaction["distance"], 2),
                    "relative_speed_px_per_s": round(
                        interaction["relative_speed"], 2
                    ),
                    "zone_track_count": len(eligible),
                    "bbox": list(track.bbox),
                    "probe_point": list(subject.probe_point),
                },
            )
        ]

    def _record_motion(
        self, observations: list[TrackObservation], timestamp: float
    ) -> None:
        """Record every visible track's center, including unchecked frames."""
        seen: set[int] = set()
        for observation in observations:
            tracker_id = observation.track.tracker_id
            seen.add(tracker_id)
            motion = self._motion.setdefault(tracker_id, _TrackMotion())
            motion.samples.append((timestamp, observation.track.center))
            while (
                len(motion.samples) > 1
                and timestamp - motion.samples[0][0]
                > self.config.speed_window_seconds
            ):
                motion.samples.popleft()

        for tracker_id in [tid for tid in self._motion if tid not in seen]:
            del self._motion[tracker_id]

    def _has_motion_history(self) -> bool:
        return any(len(motion.samples) >= 2 for motion in self._motion.values())

    def _velocity(self, tracker_id: int) -> tuple[float, float] | None:
        motion = self._motion.get(tracker_id)
        if motion is None or len(motion.samples) < 2:
            return None
        (previous_at, previous), (current_at, current) = (motion.samples[-2], motion.samples[-1])
        span = current_at - previous_at
        if span <= 0:
            return None
        return ((current[0] - previous[0]) / span, (current[1] - previous[1]) / span)

    def _find_interaction(
        self, flagged: list[TrackObservation]
    ) -> dict[str, object] | None:
        """Return the strongest nearby moving pair, or ``None``.

        The pair must be within ``max_pair_distance_px`` and both tracks must
        have velocity. A fight is an interaction, so one isolated person is
        never enough, and a pair moving in lockstep (camera shake, crowd drift)
        has too little relative speed to qualify.
        """
        if len(flagged) < 2:
            return None

        velocities = {
            observation.track.tracker_id: self._velocity(
                observation.track.tracker_id
            )
            for observation in flagged
        }
        best: dict[str, object] | None = None

        for index, left in enumerate(flagged):
            left_id = left.track.tracker_id
            left_velocity = velocities[left_id]
            if left_velocity is None:
                continue
            left_speed = math.hypot(*left_velocity)
            if left_speed < self.config.min_movement_px_per_s:
                continue

            for right in flagged[index + 1 :]:
                right_id = right.track.tracker_id
                right_velocity = velocities[right_id]
                if right_velocity is None:
                    continue
                right_speed = math.hypot(*right_velocity)
                if right_speed < self.config.min_movement_px_per_s:
                    continue

                left_center = left.track.center
                right_center = right.track.center
                distance = math.hypot(
                    left_center[0] - right_center[0],
                    left_center[1] - right_center[1],
                )
                if distance > self.config.max_pair_distance_px:
                    continue

                relative_speed = math.hypot(
                    left_velocity[0] - right_velocity[0],
                    left_velocity[1] - right_velocity[1],
                )
                if relative_speed < self.config.min_relative_speed_px_per_s:
                    continue

                if best is None or relative_speed > float(best["relative_speed"]):
                    best = {
                        "tracker_ids": (left_id, right_id),
                        "distance": distance,
                        "relative_speed": relative_speed,
                    }

        return best

    def reset(self) -> None:
        self._streak = 0
        self._active = False
        self._last_triggered_at = None
        self._last_fall_at = None
        self._last_strong_fall_at = None
        self._motion.clear()
