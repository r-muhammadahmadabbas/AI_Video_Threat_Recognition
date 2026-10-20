"""Unified threat-detection pipeline for uploaded clips and images.

This is the upload-side adapter over the same components the live camera worker
uses: :class:`~workers.cv_worker.analyzer.FrameAnalyzer` for inference,
:class:`~workers.cv_worker.tracker.ByteTrackTracker` for identity, and the shared
:class:`~workers.cv_worker.rules.engine.RuleEngine` for events. Keeping one
inference/tracking/rule path is what makes offline accuracy measurements
transferable to production.

An upload has no administrator-authored zones, so every rule is bound to one
full-frame normalized zone. Event semantics therefore match a live camera whose
whole view is the zone, while zone entry is trivially true.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import cv2

from workers.cv_worker.analyzer import AnalyzerConfig, FrameAnalyzer
from workers.cv_worker.enrichment import apply_enrichment
from workers.cv_worker.rules.base import Zone
from workers.cv_worker.rules.config import (
    CrowdAnomalyConfig,
    LoiterConfig,
    PersonDownConfig,
    WeaponConfig,
)
from workers.cv_worker.rules.crowd import CrowdMotionRule
from workers.cv_worker.rules.engine import RuleEngine
from workers.cv_worker.rules.geometry import Polygon
from workers.cv_worker.rules.loitering import LoiterRule
from workers.cv_worker.rules.person_down import PersonDownRule
from workers.cv_worker.rules.weapon import WeaponRule
from workers.cv_worker.tracker import ByteTrackTracker

if TYPE_CHECKING:
    import numpy as np

    from workers.cv_worker.analyzer import FrameAnalysis
    from workers.cv_worker.rules.base import BehaviorRule, RuleTrigger
    from workers.cv_worker.tracker import Tracker, TrackSnapshot

#: The synthetic zone every upload rule is bound to.
UPLOAD_ZONE_ID = "upload-full-frame"

#: Fall-model confidence tuned on URFD at 5 fps: 0.40 gave 0.77 recall at
#: 0.43 precision, versus 0.25 which only traded precision for no recall gain.
FALL_CONFIDENCE = 0.40

#: Consecutive violence-model hits required before an event opens. A single
#: frame of a fast movement is not a fight; two hits in a row filter blips
#: but still catch short (5 s) clips, where a 1 Hz cadence often samples the
#: fight only once.
VIOLENCE_PERSISTENCE = 2


@dataclass
class RuleEvent:
    """An event in the shape the upload API has always returned."""

    rule: str
    severity: str
    timestamp: float
    tracker_ids: list[int]
    details: dict


def _full_frame_zone() -> Zone:
    return Zone(
        zone_id=UPLOAD_ZONE_ID,
        name="Full frame",
        polygon=Polygon.from_vertices(
            [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        ),
    )


def _upload_rules(zone_id: str) -> list[BehaviorRule]:
    """Every behavioural rule, with the same defaults live cameras use."""
    return [
        LoiterRule(
            rule_id="loitering",
            rule_name="Loitering",
            zone_id=zone_id,
            zone_name="Full frame",
            severity="low",
            config=LoiterConfig(),
        ),
        PersonDownRule(
            rule_id="person_down",
            rule_name="Person down",
            zone_id=zone_id,
            zone_name="Full frame",
            severity="high",
            config=PersonDownConfig(),
        ),
        WeaponRule(
            rule_id="weapon",
            rule_name="Weapon detected",
            zone_id=zone_id,
            zone_name="Full frame",
            severity="high",
            config=WeaponConfig(),
        ),
        CrowdMotionRule(
            rule_id="crowd_anomaly",
            rule_name="Crowd anomaly",
            zone_id=zone_id,
            zone_name="Full frame",
            severity="medium",
            config=CrowdAnomalyConfig(),
        ),
    ]


class DetectionPipeline:
    """All YOLO models, ByteTrack and all rules over one uploaded source."""

    def __init__(
        self,
        confidence: float = 0.30,
        *,
        frame_rate: float = 1.0,
        analyzer: FrameAnalyzer | None = None,
        tracker: Tracker | None = None,
    ) -> None:
        """Build a pipeline.

        ``frame_rate`` defaults to the rate at which the upload endpoint feeds
        frames (every 5th source frame, i.e. roughly 6 Hz), because ByteTrack's
        motion model must know the real spacing between updates. Person and
        fall detection run on every analyzed frame; the heavier weapon and
        pose models keep a roughly 1 Hz cadence while the light violence
        classifier runs every other analyzed frame (~3 Hz), which is what
        catches fights inside short clips.

        ``analyzer`` and ``tracker`` exist so tests can inject fakes and avoid
        loading any model weights; production callers pass only ``confidence``.
        """
        self._analyzer = analyzer or FrameAnalyzer(
            AnalyzerConfig(
                person_confidence=confidence,
                weapon_enabled=True,
                weapon_confidence=confidence,
                weapon_interval=6,
                pose_enabled=True,
                pose_interval=6,
                fall_enabled=True,
                fall_confidence=FALL_CONFIDENCE,
                violence_enabled=True,
                violence_interval=2,
            )
        )
        self._tracker = tracker or ByteTrackTracker(frame_rate=frame_rate)
        self._zone = _full_frame_zone()
        self._person_down_config = PersonDownConfig()
        self._engine: RuleEngine | None = None
        self._last_timestamp: float | None = None
        self._violence_streak = 0
        self._violence_active = False
        self.events: list[RuleEvent] = []

    def reset_session(self) -> None:
        """Clear per-video state so one pipeline instance can be reused safely."""
        self._analyzer.reset()
        self._tracker.reset()
        # The frame size of the next upload is unknown, so the zone must be
        # re-resolved for it rather than kept at the previous clip's resolution.
        self._engine = None
        self._last_timestamp = None
        self._violence_streak = 0
        self._violence_active = False
        self.events.clear()

    def process_frame(
        self, frame: np.ndarray, timestamp: float
    ) -> tuple[np.ndarray, list[dict]]:
        analysis = self._analyzer.analyze(frame)
        snapshot = self._tracker.update(analysis.persons, timestamp)
        apply_enrichment(snapshot, analysis)

        dt = (
            0.0
            if self._last_timestamp is None
            else max(0.0, timestamp - self._last_timestamp)
        )
        self._last_timestamp = timestamp

        triggers = self._engine_for(frame).process(snapshot.tracked, timestamp, dt)
        self._record_triggers(triggers)

        # Violence is a per-frame model output, not a temporal rule. Require
        # persistence across model evaluations, then emit on the rising edge
        # only; otherwise every processed frame in a fight becomes a new
        # incident. Frames where the model did not run leave the streak alone.
        if analysis.violence_checked:
            self._violence_streak = (
                self._violence_streak + 1 if analysis.violence else 0
            )
            if (
                self._violence_streak >= VIOLENCE_PERSISTENCE
                and not self._violence_active
            ):
                self._violence_active = True
                self.events.append(
                    RuleEvent(
                        rule="violence_detected",
                        severity="high",
                        timestamp=timestamp,
                        tracker_ids=[t.tracker_id for t in snapshot.tracked],
                        details={
                            "event": "violence_detected",
                            "source": "violence_model",
                            "consecutive_frames": self._violence_streak,
                        },
                    )
                )
            if self._violence_streak == 0:
                self._violence_active = False

        detections = self._detections(snapshot, analysis, timestamp)
        annotated = self._annotate(frame, snapshot, analysis)
        return annotated, detections

    def _engine_for(self, frame: np.ndarray) -> RuleEngine:
        if self._engine is None:
            height, width = frame.shape[:2]
            engine = RuleEngine(
                camera_id="upload",
                frame_width=width,
                frame_height=height,
            )
            engine.load_zone(self._zone)
            for rule in _upload_rules(UPLOAD_ZONE_ID):
                engine.bind_rule(rule, UPLOAD_ZONE_ID)
            self._engine = engine
        return self._engine

    def _record_triggers(self, triggers: list[RuleTrigger]) -> None:
        for trigger in triggers:
            self.events.append(
                RuleEvent(
                    rule=trigger.rule_id,
                    severity=trigger.severity,
                    timestamp=trigger.timestamp,
                    tracker_ids=[trigger.tracker_id],
                    details={
                        **trigger.details,
                        "rule_name": trigger.rule_name,
                        "zone_id": trigger.zone_id,
                        "zone_name": trigger.zone_name,
                    },
                )
            )

    def _detections(
        self,
        snapshot: TrackSnapshot,
        analysis: FrameAnalysis,
        timestamp: float,
    ) -> list[dict]:
        rows: list[dict] = []

        for track in snapshot.tracked:
            fall = (
                track.fall_detected
                or track.aspect_ratio
                >= self._person_down_config.aspect_ratio_threshold
            )
            rows.append(
                {
                    "timestamp": round(timestamp, 2),
                    "class_name": "person",
                    "confidence": round(track.confidence, 3),
                    "bbox": [round(v, 1) for v in track.bbox],
                    "is_threat": (
                        track.weapon_detected or fall or track.violence_detected
                    ),
                    "track_id": track.tracker_id,
                    "weapon": track.weapon_detected,
                    "weapon_conf": (
                        round(track.weapon_confidence, 3)
                        if track.weapon_detected
                        else 0
                    ),
                    "fall": fall,
                    "violence": track.violence_detected,
                }
            )

        rows.extend(
            {
                "timestamp": round(timestamp, 2),
                "class_name": weapon.class_name,
                "confidence": round(weapon.confidence, 3),
                "bbox": [round(v, 1) for v in weapon.bbox],
                "is_threat": True,
                "track_id": -1,
                "weapon": True,
                "weapon_conf": round(weapon.confidence, 3),
                "fall": False,
                "violence": False,
            }
            for weapon in analysis.weapons
        )

        return rows

    def _annotate(
        self,
        frame: np.ndarray,
        snapshot: TrackSnapshot,
        analysis: FrameAnalysis,
    ) -> np.ndarray:
        img = frame.copy()
        width = img.shape[1]

        for track in snapshot.tracked:
            x1, y1, x2, y2 = [int(v) for v in track.bbox]
            if track.weapon_detected:
                color = (0, 0, 255)
                label = f"ID:{track.tracker_id} WEAPON {track.weapon_confidence:.2f}"
            elif track.fall_detected:
                color = (0, 165, 255)
                label = f"ID:{track.tracker_id} FALLEN"
            else:
                color = (255, 255, 0)
                label = f"ID:{track.tracker_id}"
            cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
            cv2.putText(
                img,
                label,
                (x1, max(y1 - 5, 15)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                2,
            )

        for weapon in analysis.weapons:
            x1, y1, x2, y2 = [int(v) for v in weapon.bbox]
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 165, 255), 2)
            cv2.putText(
                img,
                weapon.class_name,
                (x1, max(y1 - 20, 15)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (0, 165, 255),
                1,
            )

        y_offset = 50
        if analysis.violence:
            cv2.putText(
                img,
                "! VIOLENCE DETECTED",
                (10, y_offset),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2,
            )
            y_offset += 25
        for track in snapshot.tracked:
            if track.fall_detected:
                cv2.putText(
                    img,
                    f"! PERSON DOWN (ID:{track.tracker_id})",
                    (10, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 0, 255),
                    2,
                )
                y_offset += 25

        cv2.putText(
            img,
            f"People: {len(snapshot.tracked)}",
            (max(width - 150, 10), 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
        )

        return img
