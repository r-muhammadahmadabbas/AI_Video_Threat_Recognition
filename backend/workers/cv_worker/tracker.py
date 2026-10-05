from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import warnings

import numpy as np

from workers.cv_worker.detector import Detection


class TrackState(str, Enum):
    NEW = "new"
    TRACKED = "tracked"
    LOST = "lost"
    REMOVED = "removed"


@dataclass
class TrackedObject:
    tracker_id: int
    bbox: tuple[float, float, float, float]
    confidence: float
    class_id: int
    class_name: str
    state: TrackState
    first_seen_timestamp: float
    last_seen_timestamp: float
    frames_seen: int
    missed_frames: int = 0

    @property
    def center(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    @property
    def bottom_center(self) -> tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2.0, y2)

    @property
    def dwell_seconds(self) -> float:
        return max(0.0, self.last_seen_timestamp - self.first_seen_timestamp)

    def is_inside(self, zone_bbox: tuple[float, float, float, float]) -> bool:
        zx1, zy1, zx2, zy2 = zone_bbox
        cx, cy = self.bottom_center
        return zx1 <= cx <= zx2 and zy1 <= cy <= zy2


@dataclass
class TrackSnapshot:
    """Immutable view of tracker state for one frame, used by event logic."""

    timestamp: float
    tracked: list[TrackedObject] = field(default_factory=list)
    new_track_ids: set[int] = field(default_factory=set)
    lost_track_ids: set[int] = field(default_factory=set)

    def by_id(self, tracker_id: int) -> Optional[TrackedObject]:
        for obj in self.tracked:
            if obj.tracker_id == tracker_id:
                return obj
        return None


class Tracker(ABC):
    @abstractmethod
    def update(
        self, detections: list[Detection], timestamp: float
    ) -> TrackSnapshot:
        pass

    @abstractmethod
    def reset(self) -> None:
        pass

    @property
    @abstractmethod
    def active_track_count(self) -> int:
        pass


class ByteTrackTracker(Tracker):
    """Camera-local multi-object tracker built on supervision ByteTrack.

    One instance must be owned by exactly one video source: ByteTrack holds
    per-source Kalman state and track IDs, so sharing an instance across
    cameras would mix identities.
    """

    def __init__(
        self,
        frame_rate: float = 30.0,
        track_activation_threshold: float = 0.25,
        lost_track_buffer: int = 30,
        minimum_matching_threshold: float = 0.8,
        max_missed_frames: int = 15,
    ):
        self._frame_rate = frame_rate
        self._activation_threshold = track_activation_threshold
        self._lost_track_buffer = lost_track_buffer
        self._matching_threshold = minimum_matching_threshold
        self._max_missed_frames = max_missed_frames
        self._max_ids_created = 0

        self._tracks: dict[int, TrackedObject] = {}
        self._total_ids_created = 0
        self._reset_backend()

    def _reset_backend(self) -> None:
        # supervision deprecated ByteTrack at the top-level sv.ByteTrack alias
        # in 0.28.0; the implementation now lives in this module path.
        from supervision.tracker.byte_tracker.core import ByteTrack

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            self._backend = ByteTrack(
                track_activation_threshold=self._activation_threshold,
                lost_track_buffer=self._lost_track_buffer,
                minimum_matching_threshold=self._matching_threshold,
                frame_rate=self._frame_rate,
            )

    def update(self, detections: list[Detection], timestamp: float) -> TrackSnapshot:
        if not detections:
            return self._handle_empty_frame(timestamp)

        sv_detections = self._to_supervision(detections)
        class_names = {d.class_id: d.class_name for d in detections}
        tracked_sv = self._backend.update_with_detections(sv_detections)

        tracked: list[TrackedObject] = []
        for row in self._iter_rows(tracked_sv):
            obj = self._upsert(row, timestamp, class_names)
            tracked.append(obj)

        new_ids = self._mark_new(tracked)
        lost_ids = self._mark_lost(tracked, timestamp)
        self._retire(lost_ids)

        return TrackSnapshot(
            timestamp=timestamp, tracked=tracked, new_track_ids=new_ids, lost_track_ids=lost_ids
        )

    def _to_supervision(self, detections: list[Detection]):
        import supervision as sv

        return sv.Detections(
            xyxy=np.array([d.bbox for d in detections], dtype=np.float64),
            confidence=np.array([d.confidence for d in detections], dtype=np.float64),
            class_id=np.array([d.class_id for d in detections], dtype=int),
        )

    def _iter_rows(self, tracked_sv):
        xyxy = tracked_sv.xyxy
        confidences = (
            tracked_sv.confidence
            if tracked_sv.confidence is not None
            else np.zeros(len(tracked_sv))
        )
        class_ids = (
            tracked_sv.class_id
            if tracked_sv.class_id is not None
            else np.zeros(len(tracked_sv), dtype=int)
        )
        track_ids = tracked_sv.tracker_id

        for i, tracker_id in enumerate(track_ids):
            yield {
                "tracker_id": int(tracker_id),
                "bbox": tuple(float(v) for v in xyxy[i]),
                "confidence": float(confidences[i]),
                "class_id": int(class_ids[i]),
            }

    def _upsert(
        self, row: dict, timestamp: float, class_names: dict[int, str]
    ) -> TrackedObject:
        tracker_id = row["tracker_id"]
        existing = self._tracks.get(tracker_id)

        if existing is None:
            self._total_ids_created += 1
            obj = TrackedObject(
                tracker_id=tracker_id,
                bbox=row["bbox"],
                confidence=row["confidence"],
                class_id=row["class_id"],
                class_name=class_names.get(row["class_id"], str(row["class_id"])),
                state=TrackState.NEW,
                first_seen_timestamp=timestamp,
                last_seen_timestamp=timestamp,
                frames_seen=1,
            )
            self._tracks[tracker_id] = obj
            return obj

        existing.bbox = row["bbox"]
        existing.confidence = row["confidence"]
        existing.last_seen_timestamp = timestamp
        existing.frames_seen += 1
        existing.missed_frames = 0
        if existing.state in (TrackState.NEW, TrackState.LOST):
            existing.state = TrackState.TRACKED
        return existing

    def _mark_new(self, tracked: list[TrackedObject]) -> set[int]:
        return {obj.tracker_id for obj in tracked if obj.state == TrackState.NEW}

    def _mark_lost(
        self, tracked: list[TrackedObject], timestamp: float
    ) -> set[int]:
        seen = {obj.tracker_id for obj in tracked}
        lost: set[int] = set()

        for tracker_id, obj in self._tracks.items():
            if tracker_id in seen or obj.state == TrackState.REMOVED:
                continue
            obj.missed_frames += 1
            obj.state = TrackState.LOST
            lost.add(tracker_id)

        return lost

    def _retire(self, lost_ids: set[int]) -> None:
        for tracker_id in lost_ids:
            obj = self._tracks.get(tracker_id)
            if obj and obj.missed_frames > self._max_missed_frames:
                obj.state = TrackState.REMOVED
                del self._tracks[tracker_id]

    def _handle_empty_frame(self, timestamp: float) -> TrackSnapshot:
        lost_ids = self._mark_lost([], timestamp)
        self._retire(lost_ids)
        return TrackSnapshot(
            timestamp=timestamp, tracked=[], new_track_ids=set(), lost_track_ids=lost_ids
        )

    @property
    def active_track_count(self) -> int:
        return sum(
            1 for o in self._tracks.values() if o.state != TrackState.REMOVED
        )

    @property
    def total_ids_created(self) -> int:
        return self._total_ids_created

    def reset(self) -> None:
        self._tracks.clear()
        self._total_ids_created = 0
        self._reset_backend()