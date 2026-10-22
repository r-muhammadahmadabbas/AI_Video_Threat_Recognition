"""Evaluate zone-entry events through the live camera rule path.

``predict_events`` uses the upload ``DetectionPipeline``, which binds every rule
to a full-frame zone. That path cannot measure polygon geometry or crossing
direction because entering the full-frame zone is trivially true. The live
worker instead builds a ``RuleEngine`` per camera and tests tracks against
administrator-authored zones.

:func:`evaluate_zone_entry` replays recorded per-frame tracks through that same
engine and returns ``ClipEvents``-compatible intervals that
``scripts.eval.run_eval events`` can score. It is model-free, so it works even
when model weights or labelled clips are absent.
"""

from __future__ import annotations

import itertools
import statistics
from dataclasses import dataclass
from typing import TYPE_CHECKING

from scripts.eval.predict_events import events_to_intervals
from scripts.eval.schema import ClipEvents
from workers.cv_worker.rules.config import ZoneEntryConfig
from workers.cv_worker.rules.engine import RuleEngine
from workers.cv_worker.rules.restricted_zone import ZoneEntryRule
from workers.cv_worker.tracker import TrackedObject, TrackState

if TYPE_CHECKING:
    from collections.abc import Iterable

    from scripts.eval.metrics import EventInterval
    from workers.cv_worker.rules.base import RuleTrigger, Zone


@dataclass(frozen=True)
class TrackSample:
    """One tracked object observed at one timestamp."""

    timestamp: float
    tracker_id: int
    bbox: tuple[float, float, float, float]
    confidence: float = 1.0


@dataclass
class ZoneEntryEvaluation:
    """Zone-entry intervals plus the live-path triggers that produced them."""

    clip: str
    duration: float
    events: list[EventInterval]
    triggers: list[RuleTrigger]

    def to_clip_events(self) -> ClipEvents:
        return ClipEvents(
            clip=self.clip, duration=self.duration, events=list(self.events)
        )


@dataclass(frozen=True)
class _TriggerPoint:
    rule: str
    timestamp: float


def _sample_period(timestamps: list[float]) -> float:
    gaps = [
        later - earlier
        for earlier, later in itertools.pairwise(timestamps)
        if later > earlier
    ]
    return statistics.median(gaps) if gaps else 1.0


def evaluate_zone_entry(
    samples: Iterable[TrackSample],
    zone: Zone,
    *,
    frame_width: int,
    frame_height: int,
    rule_id: str = "restricted_zone_entry",
    rule_name: str = "Restricted zone entry",
    severity: str = "high",
    config: ZoneEntryConfig | None = None,
    clip: str = "clip",
) -> ZoneEntryEvaluation:
    """Replay tracks through the live ``RuleEngine`` and return entry intervals."""
    ordered = sorted(samples, key=lambda sample: (sample.timestamp, sample.tracker_id))
    if not ordered:
        return ZoneEntryEvaluation(clip=clip, duration=0.0, events=[], triggers=[])

    timestamps = sorted({sample.timestamp for sample in ordered})
    sample_period = _sample_period(timestamps)
    engine = RuleEngine(
        camera_id="live-zone-entry-eval",
        frame_width=frame_width,
        frame_height=frame_height,
    )
    engine.load_zone(zone)
    engine.bind_rule(
        ZoneEntryRule(
            rule_id=rule_id,
            rule_name=rule_name,
            zone_id=zone.zone_id,
            zone_name=zone.name,
            severity=severity,
            config=config or ZoneEntryConfig(),
        ),
        zone.zone_id,
    )

    by_timestamp: dict[float, list[TrackSample]] = {}
    for sample in ordered:
        by_timestamp.setdefault(sample.timestamp, []).append(sample)

    frames_seen: dict[int, int] = {}
    first_seen: dict[int, float] = {}
    triggers: list[RuleTrigger] = []
    previous: float | None = None

    for timestamp in timestamps:
        tracks = []
        for sample in by_timestamp[timestamp]:
            frames_seen[sample.tracker_id] = frames_seen.get(sample.tracker_id, 0) + 1
            first_seen.setdefault(sample.tracker_id, sample.timestamp)
            tracks.append(
                TrackedObject(
                    tracker_id=sample.tracker_id,
                    bbox=sample.bbox,
                    confidence=sample.confidence,
                    class_id=0,
                    class_name="person",
                    state=TrackState.TRACKED,
                    first_seen_timestamp=first_seen[sample.tracker_id],
                    last_seen_timestamp=sample.timestamp,
                    frames_seen=frames_seen[sample.tracker_id],
                )
            )

        dt = 0.0 if previous is None else max(0.0, timestamp - previous)
        triggers.extend(engine.process(tracks, timestamp, dt))
        previous = timestamp

    events = events_to_intervals(
        [
            _TriggerPoint(rule=trigger.rule_id, timestamp=trigger.timestamp)
            for trigger in triggers
        ],
        gap_tolerance=2.0 * sample_period,
        min_duration=sample_period,
    )
    return ZoneEntryEvaluation(
        clip=clip,
        duration=timestamps[-1] + sample_period,
        events=events,
        triggers=triggers,
    )
