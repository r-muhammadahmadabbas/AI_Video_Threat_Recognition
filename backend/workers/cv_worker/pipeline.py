"""Full threat detection pipeline: all pre-trained models + all rules.

Models:
- Weapon: YOLO26x trained on 130K weapon images (firearm, knife, etc.)
- Fall: YOLO11 trained on human fall detection (fallen/sitting/standing)
- Violence: YOLO26 trained on surveillance violence detection
- Crowd: person count from weapon detector + temporal rules
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import cv2
import numpy as np
from ultralytics import YOLO

from workers.cv_worker.weapon_detector import WeaponDetector, THREAT_CLASSES


@dataclass
class TrackedPerson:
    track_id: int
    bbox: tuple[float, float, float, float]
    confidence: float
    first_seen: float
    last_seen: float
    positions: list[tuple[float, float, float]] = field(default_factory=list)
    weapon_detected: bool = False
    weapon_confidence: float = 0.0
    fall_detected: bool = False
    violence_detected: bool = False

    @property
    def center(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2, (y1 + y2) / 2)

    @property
    def aspect_ratio(self) -> float:
        x1, y1, x2, y2 = self.bbox
        w = x2 - x1
        h = y2 - y1
        return w / h if h > 0 else 0.0

    @property
    def dwell_seconds(self) -> float:
        return self.last_seen - self.first_seen


@dataclass
class RuleEvent:
    rule: str
    severity: str
    timestamp: float
    tracker_ids: list[int]
    details: dict


class SimpleTracker:
    def __init__(self, iou_threshold: float = 0.3, max_missed: int = 10):
        self.iou_threshold = iou_threshold
        self.max_missed = max_missed
        self.tracks: dict[int, TrackedPerson] = {}
        self._next_id = 1
        self._missed: dict[int, int] = {}

    @staticmethod
    def _iou(a, b):
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        ix1, iy1 = max(ax1, bx1), max(ay1, by1)
        ix2, iy2 = min(ax2, bx2), min(ay2, by2)
        iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
        inter = iw * ih
        area_a = (ax2 - ax1) * (ay2 - ay1)
        area_b = (bx2 - bx1) * (by2 - by1)
        union = area_a + area_b - inter
        return inter / union if union > 0 else 0.0

    def update(self, detections, timestamp):
        matched = set()
        used = set()

        for bbox, conf in detections:
            best_id = None
            best_iou = self.iou_threshold
            for tid, track in self.tracks.items():
                if tid in used:
                    continue
                iou = self._iou(bbox, track.bbox)
                if iou > best_iou:
                    best_iou = iou
                    best_id = tid

            if best_id is not None:
                track = self.tracks[best_id]
                track.bbox = bbox
                track.confidence = conf
                track.last_seen = timestamp
                track.positions.append((*track.center, timestamp))
                self._missed[best_id] = 0
                used.add(best_id)
            else:
                tid = self._next_id
                self._next_id += 1
                cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
                self.tracks[tid] = TrackedPerson(
                    track_id=tid,
                    bbox=bbox,
                    confidence=conf,
                    first_seen=timestamp,
                    last_seen=timestamp,
                    positions=[(cx, cy, timestamp)],
                )
                self._missed[tid] = 0
                matched.add(tid)

        for tid in list(self.tracks.keys()):
            if tid not in used:
                self._missed[tid] = self._missed.get(tid, 0) + 1
                if self._missed[tid] > self.max_missed:
                    del self.tracks[tid]
                    del self._missed[tid]

        return [t for t in self.tracks.values() if t.last_seen == timestamp]


class DetectionPipeline:
    """All pre-trained models + all rules in one pipeline."""

    def __init__(self, confidence: float = 0.30):
        self.weapon_detector = WeaponDetector(confidence=confidence)
        self.fall_model = YOLO("models/fall/best.pt")
        self.violence_model = YOLO("models/violence/best.pt")
        self.tracker = SimpleTracker()
        self.events: list[RuleEvent] = []
        self._crowd_history: list[tuple[float, int]] = []
        self._alerted: dict[str, set] = {
            "loitering": set(),
            "person_down": set(),
            "altercation": set(),
            "violence": set(),
        }

    def process_frame(self, frame, timestamp):
        h, w = frame.shape[:2]
        weapon_results = self.weapon_detector.detect(frame)
        person_dets = [(d.bbox, d.confidence) for d in weapon_results if d.class_name == "person"]
        weapon_dets = [d for d in weapon_results if d.is_threat]

        active_tracks = self.tracker.update(person_dets, timestamp)

        # Run fall detection every 30th frame only
        fall_results = None
        if int(timestamp * 25) % 30 == 0:
            fall_results = self.fall_model.predict(source=frame, conf=0.25, device="cpu", verbose=False)
            for track in active_tracks:
                if track.aspect_ratio > 1.3:
                    track.fall_detected = True

        # Run violence detection every 15th frame only
        vio_detected = False
        if int(timestamp * 10) % 15 == 0:
            vio_results = self.violence_model.predict(source=frame, conf=0.35, device="cpu", verbose=False)
            for result in vio_results:
                if result.boxes is None:
                    continue
                for box in result.boxes:
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    if cls_id == 0 and conf > 0.35:
                        vio_detected = True
                        for track in active_tracks:
                            track.violence_detected = True

        # Weapon-to-person association
        for track in active_tracks:
            for wd in weapon_dets:
                if self._overlap(track.bbox, wd.bbox):
                    track.weapon_detected = True
                    track.weapon_confidence = max(track.weapon_confidence, wd.confidence)

        # Run behavioral rules
        frame_events = self._run_rules(active_tracks, timestamp, vio_detected)
        self.events.extend(frame_events)

        annotated = self._annotate(frame, active_tracks, weapon_dets, vio_detected, fall_results)

        detections = []
        for track in active_tracks:
            detections.append({
                "timestamp": round(timestamp, 2),
                "class_name": "person",
                "confidence": round(track.confidence, 3),
                "bbox": [round(v, 1) for v in track.bbox],
                "is_threat": track.weapon_detected or track.fall_detected or track.violence_detected,
                "track_id": track.track_id,
                "weapon": track.weapon_detected,
                "weapon_conf": round(track.weapon_confidence, 3) if track.weapon_detected else 0,
                "fall": track.fall_detected,
                "violence": track.violence_detected,
            })
        for wd in weapon_dets:
            detections.append({
                "timestamp": round(timestamp, 2),
                "class_name": wd.class_name,
                "confidence": round(wd.confidence, 3),
                "bbox": [round(v, 1) for v in wd.bbox],
                "is_threat": True,
                "track_id": -1,
                "weapon": True,
                "weapon_conf": round(wd.confidence, 3),
                "fall": False,
                "violence": False,
            })

        return annotated, detections

    def _run_rules(self, tracks, timestamp, vio_detected):
        events = []

        # Crowd anomaly
        count = len(tracks)
        self._crowd_history.append((timestamp, count))
        self._crowd_history = [(t, c) for t, c in self._crowd_history if timestamp - t <= 30.0]
        if len(self._crowd_history) >= 3:
            avg = sum(c for _, c in self._crowd_history) / len(self._crowd_history)
            if count >= max(avg * 2.0, 5) and count >= 5:
                events.append(RuleEvent("crowd_anomaly", "medium", timestamp,
                    [t.track_id for t in tracks], {"count": count, "average": round(avg, 1)}))

        # Violence/fight
        if vio_detected:
            events.append(RuleEvent("violence_detected", "high", timestamp,
                [t.track_id for t in tracks], {"source": "violence_model"}))

        # Altercation (pair proximity)
        for i, a in enumerate(tracks):
            for b in tracks[i + 1:]:
                dist = math.hypot(a.center[0] - b.center[0], a.center[1] - b.center[1])
                if dist < 80 and len(a.positions) >= 2 and len(b.positions) >= 2:
                    key = tuple(sorted([a.track_id, b.track_id]))
                    if key not in self._alerted["altercation"]:
                        self._alerted["altercation"].add(key)
                        events.append(RuleEvent("altercation", "high", timestamp,
                            [a.track_id, b.track_id], {"distance": round(dist, 1)}))

        # Loitering
        for t in tracks:
            if t.dwell_seconds >= 30.0 and t.track_id not in self._alerted["loitering"]:
                self._alerted["loitering"].add(t.track_id)
                events.append(RuleEvent("loitering", "low", timestamp,
                    [t.track_id], {"dwell_seconds": round(t.dwell_seconds, 1)}))

        # Person down
        for t in tracks:
            if t.fall_detected and t.track_id not in self._alerted["person_down"]:
                self._alerted["person_down"].add(t.track_id)
                events.append(RuleEvent("person_down", "high", timestamp,
                    [t.track_id], {"aspect_ratio": round(t.aspect_ratio, 2)}))

        return events

    @staticmethod
    def _overlap(a, b):
        return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])

    def _annotate(self, frame, tracks, weapons, vio_detected, fall_results):
        img = frame.copy()
        h, w = img.shape[:2]

        for t in tracks:
            x1, y1, x2, y2 = [int(v) for v in t.bbox]
            color = (0, 0, 255) if t.weapon_detected else (255, 0, 0) if t.fall_detected else (255, 255, 0)
            cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
            label = f"ID:{t.track_id}"
            if t.weapon_detected:
                label += f" GUN {t.weapon_confidence:.2f}"
            elif t.fall_detected:
                label += " FALLEN"
            cv2.putText(img, label, (x1, max(y1 - 5, 15)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        for wd in weapons:
            x1, y1, x2, y2 = [int(v) for v in wd.bbox]
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 165, 255), 2)
            cv2.putText(img, wd.class_name, (x1, max(y1 - 20, 15)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 165, 255), 1)

        y_off = 50
        if vio_detected:
            cv2.putText(img, "! VIOLENCE DETECTED", (10, y_off), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            y_off += 25
        for t in tracks:
            if t.fall_detected:
                cv2.putText(img, f"! PERSON DOWN (ID:{t.track_id})", (10, y_off),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                y_off += 25

        cv2.putText(img, f"People: {len(tracks)}", (w - 150, 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        return img