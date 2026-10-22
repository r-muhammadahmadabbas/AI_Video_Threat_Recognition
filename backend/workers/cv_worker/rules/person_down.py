"""Person-down (horizontal posture) detection (Sprint 5A/5B).

A subject is considered "down" when their bounding box is wider than tall
by a configurable margin, the fall model reports a confident fallen posture,
or the pose skeleton is plausibly horizontal. This is evaluated per-frame on
the track's current bbox and only for tracks that are inside the bound zone.

The rule is stateful: geometry needs ``min_frames_down`` consecutive frames on
a track that has itself persisted for ``min_track_frames`` observations, while
model and pose evidence are point observations, with a per-track cooldown to
prevent alert storms.

Fall-model hits below ``min_fall_confidence`` are not trusted on their own:
they are common on crouching, sitting and kneeling boxes. A short exponential
moving average over that weak band lets a genuinely fallen subject accumulate
evidence from several borderline frames, recovering falls whose best frame is
just under the incident threshold, while an isolated weak hit decays away and
never alerts.

A checked, upright pose vetoes geometry-only and smoothed-weak evidence for a
short window. Wide boxes are the normal signature of crouching, sitting,
bending and a shooting stance, so without the veto those hard negatives would
trip the aspect-ratio fallback. An upright pose also clears any accumulated
weak-fall evidence, so a later weak hit cannot reuse a sitting/crouching
episode. Confident fall-model and fallen-pose evidence still bypass the veto
and its track-persistence guard.
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
class FallScoreSmoother:
    """Smoothed fall-model evidence from hits below the incident threshold.

    ``confidence`` is normalized against the incident threshold before it
    updates the score, so a hit at that threshold has target ``1.0`` and a
    hit halfway through the weak band has target ``0.5``. ``positive_hits``
    counts weak hits since the evidence was last cleared, which keeps a short
    negative run from erasing the hits that preceded it.
    """

    decay: float
    score: float = 0.0
    positive_hits: int = 0

    def observe(self, confidence: float, *, incident_confidence: float) -> None:
        target = (
            min(1.0, max(0.0, confidence) / incident_confidence)
            if incident_confidence > 0.0
            else 0.0
        )
        self.score = self.decay * self.score + (1.0 - self.decay) * target
        if confidence > 0.0:
            self.positive_hits += 1

    def reset(self) -> None:
        self.score = 0.0
        self.positive_hits = 0


@dataclass
class _DownEpisode:
    """Temporal state for one track's horizontal posture."""

    weak_fall: FallScoreSmoother
    consecutive_down_frames: int = 0
    last_triggered_at: float | None = None
    last_pose_checked_at: float | None = None
    last_pose_fall_detected: bool = False


@dataclass(frozen=True)
class _FrameEvidence:
    """Evidence computed for one track on one frame."""

    aspect_ratio: float
    fall_confidence: float
    model_evidence: bool
    pose_evidence: bool
    smoothed_model_evidence: bool
    geometry_evidence: bool
    pose_upright_recent: bool

    @property
    def strong(self) -> bool:
        return (
            self.model_evidence
            or self.pose_evidence
            or self.smoothed_model_evidence
        )

    @property
    def is_down(self) -> bool:
        return self.strong or (
            self.geometry_evidence and not self.pose_upright_recent
        )


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
        """Evaluate aspect ratio and fall evidence for each track in the zone."""
        triggers: list[RuleTrigger] = []
        seen: set[int] = set()

        for observation in observations:
            tracker_id = observation.track.tracker_id
            seen.add(tracker_id)

            if observation.track.confidence < self.config.min_confidence:
                continue

            episode = self._episodes.get(tracker_id)
            if episode is None:
                episode = _DownEpisode(
                    weak_fall=FallScoreSmoother(
                        self.config.fall_smoothing_decay
                    )
                )
                self._episodes[tracker_id] = episode

            if not observation.inside_expanded:
                episode.consecutive_down_frames = 0
                episode.weak_fall.reset()
                continue

            evidence = self._evidence_for(observation, episode, timestamp)
            if evidence.is_down:
                episode.consecutive_down_frames += 1
            else:
                episode.consecutive_down_frames = 0

            if not evidence.is_down:
                continue

            # Model, pose and smoothed weak-fall hits already carry temporal
            # persistence (or a confident single frame); the aspect-ratio path
            # keeps its multi-frame and track-age guards against box jitter and
            # short-lived misdetections.
            required_frames = (
                1 if evidence.strong else self.config.min_frames_down
            )
            if episode.consecutive_down_frames < required_frames:
                continue
            if (
                not evidence.strong
                and observation.track.frames_seen < self.config.min_track_frames
            ):
                continue
            if not self._cooldown_elapsed(episode, timestamp):
                continue

            episode.last_triggered_at = timestamp
            triggers.append(
                self._make_trigger(
                    observation,
                    timestamp,
                    episode.consecutive_down_frames,
                    evidence,
                )
            )
            if evidence.smoothed_model_evidence:
                episode.weak_fall.reset()

        self._forget_absent(seen)
        return triggers

    def _evidence_for(
        self,
        observation: TrackObservation,
        episode: _DownEpisode,
        timestamp: float,
    ) -> _FrameEvidence:
        bbox = observation.track.bbox
        x1, y1, x2, y2 = bbox
        width = max(0.0, x2 - x1)
        height = max(1.0, y2 - y1)
        aspect_ratio = width / height

        fall_confidence = (
            observation.track.fall_confidence
            if observation.track.fall_detected
            else 0.0
        )
        model_evidence = fall_confidence >= self.config.min_fall_confidence
        weak_fall_confidence = (
            fall_confidence
            if self.config.weak_fall_confidence
            <= fall_confidence
            < self.config.min_fall_confidence
            else 0.0
        )
        pose_evidence = bool(observation.track.pose_fall_detected)

        if observation.track.pose_checked:
            episode.last_pose_checked_at = timestamp
            episode.last_pose_fall_detected = pose_evidence
            if not pose_evidence:
                # An explicit upright skeleton invalidates weak model hits
                # from the sitting/crouching frames before it.
                episode.weak_fall.reset()

        # Pose runs less often than person detection. Remember the last verdict
        # long enough to cover that cadence, otherwise a crouch or shooting
        # stance can fill a geometry streak between pose frames.
        pose_upright_recent = (
            episode.last_pose_checked_at is not None
            and not episode.last_pose_fall_detected
            and timestamp - episode.last_pose_checked_at
            <= self.config.upright_pose_veto_seconds
        )

        if model_evidence or pose_evidence:
            episode.weak_fall.reset()
        elif weak_fall_confidence > 0.0 and not pose_upright_recent:
            episode.weak_fall.observe(
                weak_fall_confidence,
                incident_confidence=self.config.min_fall_confidence,
            )
        else:
            episode.weak_fall.observe(
                0.0,
                incident_confidence=self.config.min_fall_confidence,
            )

        return _FrameEvidence(
            aspect_ratio=aspect_ratio,
            fall_confidence=fall_confidence,
            model_evidence=model_evidence,
            pose_evidence=pose_evidence,
            smoothed_model_evidence=(
                episode.weak_fall.score
                >= self.config.min_smoothed_fall_score
            ),
            geometry_evidence=(
                aspect_ratio >= self.config.aspect_ratio_threshold
            ),
            pose_upright_recent=pose_upright_recent,
        )

    def _cooldown_elapsed(self, episode: _DownEpisode, timestamp: float) -> bool:
        if episode.last_triggered_at is None:
            return True
        return timestamp - episode.last_triggered_at >= self.config.cooldown_seconds

    def _make_trigger(
        self,
        observation: TrackObservation,
        timestamp: float,
        consecutive_down_frames: int,
        evidence: _FrameEvidence,
    ) -> RuleTrigger:
        track = observation.track
        if evidence.model_evidence:
            evidence_kind = "fall_model"
        elif evidence.pose_evidence:
            evidence_kind = "pose"
        elif evidence.smoothed_model_evidence:
            evidence_kind = "fall_model_smoothed"
        else:
            evidence_kind = "aspect_ratio"

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
                "aspect_ratio": round(evidence.aspect_ratio, 3),
                "threshold": self.config.aspect_ratio_threshold,
                "consecutive_frames_down": consecutive_down_frames,
                "min_frames_required": (
                    1 if evidence.strong else self.config.min_frames_down
                ),
                "evidence": evidence_kind,
                "fall_confidence": round(evidence.fall_confidence, 3),
                "smoothed_fall_score": round(
                    self._episodes[track.tracker_id].weak_fall.score, 3
                ),
                "weak_fall_hits": (
                    self._episodes[track.tracker_id].weak_fall.positive_hits
                ),
                "min_smoothed_fall_score": (
                    self.config.min_smoothed_fall_score
                ),
                "pose_checked": bool(track.pose_checked),
                "bbox": list(track.bbox),
                "probe_point": list(observation.probe_point),
            },
        )

    def _forget_absent(self, seen: set[int]) -> None:
        for tracker_id in [tid for tid in self._episodes if tid not in seen]:
            del self._episodes[tracker_id]

    def reset(self) -> None:
        self._episodes.clear()
