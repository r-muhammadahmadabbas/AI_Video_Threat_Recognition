"""Abnormal-crowd-movement candidate detection (Sprint 7A/7B/7C).

This is a *crowd-level* rule: it scores the whole zone rather than a single
track. Each frame it aggregates transparent features over the people in the
zone and compares a short observation window against a rolling baseline of the
same zone's recent behaviour (a campus entrance at 8 AM is different from a
parking area at midnight, and a small zone is denser than a large one at the
same person count).

Raw person count is only a gating signal (``min_tracks``); it is not scored.
The density feature is people per megapixel of the bound zone footprint, so
the same number of people in a small zone is a stronger signal than in a large
one. Density, speed and direction dispersion only contribute when they rise
above the zone baseline, and pair distance only contributes when it falls
(crowding). A crowd dispersing, calming down or leaving therefore cannot raise
an alert on change alone.

The anomaly score is deliberately transparent: it is a weighted sum of each
feature's one-sided relative deviation from baseline, and every feature, its
baseline, and its contribution are carried into the trigger metadata so an
operator can see exactly why the scene was flagged.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field

from workers.cv_worker.rules.base import (
    BehaviorRule,
    RuleTrigger,
    TrackObservation,
    Zone,
)
from workers.cv_worker.rules.config import CrowdAnomalyConfig

# The zone-level "tracker id" used for crowd triggers. A crowd event belongs to
# the whole zone, not to any single subject, so it uses a stable sentinel that
# keeps the engine's dedup key consistent for one zone/rule pair.
_ZONE_TRIGGER_TRACKER_ID = -1

# Density is reported as people per megapixel of zone footprint. A typical
# 640x480 full-frame zone is 0.3 MP, so one person is already a visible
# density; it keeps the feature on roughly the same scale as a person count
# for common zones while still letting a small zone read as denser.
_DENSITY_PIXELS_PER_UNIT = 1_000_000.0

# Features that feed the anomaly score, the attribute they read, and the
# direction that counts as anomalous. A crowd alert is about a scene becoming
# denser or more agitated than this zone's own baseline; dispersal, calming
# down and people leaving are not anomalies and must not raise the score.
_SCORED_FEATURES: dict[str, tuple[str, str]] = {
    "density_per_megapixel": ("density", "increase"),
    "mean_speed_px_per_s": ("mean_speed", "increase"),
    "direction_dispersion": ("direction_dispersion", "increase"),
    "mean_pair_distance_px": ("mean_pair_distance", "decrease"),
}


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


@dataclass
class _TrackHistory:
    """Recent centers for one track, pruned to the observation window."""

    samples: deque[tuple[float, tuple[float, float]]] = field(default_factory=deque)


@dataclass
class _CrowdFeatures:
    """One frame's aggregate crowd features."""

    track_count: float
    density: float
    mean_speed: float
    direction_dispersion: float
    mean_pair_distance: float
    timestamp: float

    def as_dict(self) -> dict[str, float]:
        return {
            "track_count": round(self.track_count, 2),
            "density_per_megapixel": round(self.density, 3),
            "mean_speed_px_per_s": round(self.mean_speed, 2),
            "direction_dispersion": round(self.direction_dispersion, 2),
            "mean_pair_distance_px": round(self.mean_pair_distance, 2),
        }


@dataclass
class CrowdMotionRule(BehaviorRule):
    """Opens a trigger when the weighted crowd anomaly score stays high.

    The rule needs a warm-up period while the baseline accumulates, and a
    minimum track count before it considers the crowd worth scoring.
    """

    rule_id: str
    rule_name: str
    zone_id: str
    zone_name: str
    severity: str
    config: CrowdAnomalyConfig = field(default_factory=CrowdAnomalyConfig)

    def __post_init__(self) -> None:
        self._tracks: dict[int, _TrackHistory] = {}
        self._snapshots: deque[_CrowdFeatures] = deque()
        self._high_seconds: float = 0.0
        self._last_triggered_at: float | None = None
        # Tests and callers that drive a rule without an engine get a unit
        # footprint; binding a zone replaces it with the real pixel area.
        self._zone_area_px2: float = _DENSITY_PIXELS_PER_UNIT

    def bind_zone(self, zone: Zone) -> None:
        """Use the resolved zone footprint to normalise crowd density.

        The engine resolves the polygon into this camera's pixel space before
        calling this, so the area is directly comparable across cameras whose
        stored zones use different coordinate conventions.
        """
        self._zone_area_px2 = max(float(zone.polygon.area), 1.0)

    def update(
        self,
        observations: list[TrackObservation],
        timestamp: float,
        dt: float = 0.0,
    ) -> list[RuleTrigger]:
        """Advance the crowd state and return a trigger if the score persists."""
        eligible = [o for o in observations if self._participates(o)]
        self._record_tracks(eligible, timestamp)

        self._snapshots.append(self._aggregate(timestamp))
        self._prune_snapshots(timestamp)

        current = self._current_window(timestamp)
        baseline = self._baseline_window(timestamp)

        if current is None or baseline is None:
            # Still warming up, or no crowd to speak of.
            self._high_seconds = 0.0
            return []

        score, contributions = self._anomaly_score(current, baseline)

        if self._below_minimum(current):
            self._high_seconds = 0.0
        elif score >= self.config.score_threshold:
            self._high_seconds += dt
        else:
            self._high_seconds = 0.0

        if self._high_seconds >= self.config.min_duration_seconds and self._cooldown_elapsed(
            timestamp
        ):
            self._last_triggered_at = timestamp
            self._high_seconds = 0.0
            return [self._make_trigger(current, baseline, score, contributions, timestamp)]

        return []

    def _participates(self, observation: TrackObservation) -> bool:
        return (
            observation.definitively_inside
            and observation.track.confidence >= self.config.min_confidence
        )

    def _record_tracks(self, observations: list[TrackObservation], timestamp: float) -> None:
        """Store each participant's current center, pruning stale history."""
        seen: set[int] = set()
        for observation in observations:
            tracker_id = observation.track.tracker_id
            seen.add(tracker_id)
            history = self._tracks.setdefault(tracker_id, _TrackHistory())
            history.samples.append((timestamp, observation.track.center))
            while (
                len(history.samples) > 1
                and timestamp - history.samples[0][0] > self.config.observation_window_seconds
            ):
                history.samples.popleft()

        for tracker_id in [tid for tid in self._tracks if tid not in seen]:
            del self._tracks[tracker_id]

    def _current_window(self, timestamp: float) -> _CrowdFeatures | None:
        """Average of frames newer than the observation window."""
        fresh = [
            f
            for f in self._snapshots
            if timestamp - f.timestamp <= self.config.observation_window_seconds
        ]
        if not fresh:
            return None
        return self._average(fresh)

    def _baseline_window(self, timestamp: float) -> _CrowdFeatures | None:
        """Average of frames between the observation and baseline windows."""
        older = [
            f
            for f in self._snapshots
            if self.config.observation_window_seconds
            < timestamp - f.timestamp
            <= self.config.baseline_window_seconds
        ]
        if len(older) < self.config.min_baseline_snapshots:
            return None
        return self._average(older)

    def _prune_snapshots(self, timestamp: float) -> None:
        """Drop snapshots older than the baseline window."""
        cutoff = timestamp - self.config.baseline_window_seconds
        while self._snapshots and self._snapshots[0].timestamp < cutoff:
            self._snapshots.popleft()

    @staticmethod
    def _average(frames: list[_CrowdFeatures]) -> _CrowdFeatures:
        n = float(len(frames))
        return _CrowdFeatures(
            track_count=sum(f.track_count for f in frames) / n,
            density=sum(f.density for f in frames) / n,
            mean_speed=sum(f.mean_speed for f in frames) / n,
            direction_dispersion=sum(f.direction_dispersion for f in frames) / n,
            mean_pair_distance=sum(f.mean_pair_distance for f in frames) / n,
            timestamp=frames[-1].timestamp,
        )

    def _aggregate(self, timestamp: float) -> _CrowdFeatures:
        """Compute this frame's crowd features from per-track history."""
        track_count = float(len(self._tracks))

        speeds: list[float] = []
        velocities: list[tuple[float, float]] = []
        for history in self._tracks.values():
            if len(history.samples) < 2:
                continue
            prev_ts, prev_center = history.samples[-2]
            now_ts, now_center = history.samples[-1]
            span = now_ts - prev_ts
            if span <= 0:
                continue
            dx = (now_center[0] - prev_center[0]) / span
            dy = (now_center[1] - prev_center[1]) / span
            speeds.append(math.hypot(dx, dy))
            norm = math.hypot(dx, dy)
            if norm > 0:
                velocities.append((dx / norm, dy / norm))

        mean_speed = sum(speeds) / len(speeds) if speeds else 0.0
        direction_dispersion = self._direction_dispersion(velocities)
        mean_pair_distance = self._mean_pair_distance()

        return _CrowdFeatures(
            track_count=track_count,
            density=track_count * _DENSITY_PIXELS_PER_UNIT / self._zone_area_px2,
            mean_speed=mean_speed,
            direction_dispersion=direction_dispersion,
            mean_pair_distance=mean_pair_distance,
            timestamp=timestamp,
        )

    @staticmethod
    def _direction_dispersion(
        velocities: list[tuple[float, float]],
    ) -> float:
        """Circular variance of track headings: 0 aligned, 1 uniform."""
        if not velocities:
            return 0.0
        sx = sum(v[0] for v in velocities)
        sy = sum(v[1] for v in velocities)
        magnitude = math.hypot(sx, sy) / len(velocities)
        return max(0.0, min(1.0, 1.0 - magnitude))

    def _mean_pair_distance(self) -> float:
        centers = [h.samples[-1][1] for h in self._tracks.values() if h.samples]
        if len(centers) < 2:
            return 0.0
        total = 0.0
        count = 0
        for i, a in enumerate(centers):
            for b in centers[i + 1 :]:
                total += _distance(a, b)
                count += 1
        return total / count if count else 0.0

    def _anomaly_score(
        self, current: _CrowdFeatures, baseline: _CrowdFeatures
    ) -> tuple[float, dict[str, float]]:
        """Weighted one-sided deviation of current features from baseline (7C).

        Each contribution is ``weight * deviation / max(baseline, 1.0)``, where
        ``deviation`` is the amount by which the current value exceeds the
        baseline for density, speed and dispersion, or falls below it for pair
        distance (crowding). A crowd dispersing, slowing down or leaving is not
        an anomaly, so it does not accumulate score just because the absolute
        change is large.

        Density replaces the old raw person count: the same number of people in
        a small zone is a stronger signal than in a large zone, while the term
        is still normalised by this zone's own rolling baseline. The returned
        contributions sum exactly to the score, keeping the breakdown honest.
        """
        weights = self._weights()
        contributions: dict[str, float] = {}
        score = 0.0
        for name, (attr, direction) in _SCORED_FEATURES.items():
            value = float(getattr(current, attr))
            base = float(getattr(baseline, attr))
            delta = value - base
            deviation = max(0.0, delta) if direction == "increase" else max(0.0, -delta)
            contribution = weights[name] * deviation / max(base, 1.0)
            contributions[name] = round(contribution, 3)
            score += contribution
        return score, contributions

    def _weights(self) -> dict[str, float]:
        return {
            # Kept under the historical name so stored camera configs remain
            # valid; this weight now scales the per-zone density feature that
            # replaced raw track count.
            "density_per_megapixel": self.config.weight_track_count,
            "mean_speed_px_per_s": self.config.weight_mean_speed,
            "direction_dispersion": self.config.weight_direction_dispersion,
            "mean_pair_distance_px": self.config.weight_mean_pair_distance,
        }

    def _total_weight(self) -> float:
        return sum(self._weights().values())

    def _below_minimum(self, current: _CrowdFeatures) -> bool:
        return current.track_count < self.config.min_tracks

    def _cooldown_elapsed(self, timestamp: float) -> bool:
        if self._last_triggered_at is None:
            return True
        return timestamp - self._last_triggered_at >= self.config.cooldown_seconds

    def _make_trigger(
        self,
        current: _CrowdFeatures,
        baseline: _CrowdFeatures,
        score: float,
        contributions: dict[str, float],
        timestamp: float,
    ) -> RuleTrigger:
        total_weight = max(self._total_weight(), 1e-6)
        return RuleTrigger(
            rule_id=self.rule_id,
            rule_name=self.rule_name,
            zone_id=self.zone_id,
            zone_name=self.zone_name,
            tracker_id=_ZONE_TRIGGER_TRACKER_ID,
            timestamp=timestamp,
            severity=self.severity,
            confidence=max(0.5, min(1.0, score / total_weight)),
            details={
                "event": "crowd_anomaly",
                "anomaly_score": round(score, 3),
                "score_threshold": self.config.score_threshold,
                "current_features": current.as_dict(),
                "baseline_features": baseline.as_dict(),
                "feature_contributions": contributions,
                "zone_area_px2": round(self._zone_area_px2, 1),
                "observation_window_seconds": self.config.observation_window_seconds,
                "baseline_window_seconds": self.config.baseline_window_seconds,
                "min_tracks": self.config.min_tracks,
                "persisted_seconds": round(self._high_seconds, 2),
            },
        )

    def reset(self) -> None:
        self._tracks.clear()
        self._snapshots.clear()
        self._high_seconds = 0.0
        self._last_triggered_at = None
