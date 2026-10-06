import signal
import time

import cv2

from app.config import settings
from app.logging import get_logger
from workers.cv_worker.detector import YOLO26Detector
from workers.cv_worker.event_adapter import PersonPresenceAdapter
from workers.cv_worker.rules.base import BehaviorRule, Zone
from workers.cv_worker.rules.engine import RuleEngine
from workers.cv_worker.tracker import ByteTrackTracker, Tracker, TrackSnapshot
from workers.cv_worker.video_source import Frame, MP4VideoSource, VideoSource

logger = get_logger(__name__)


class CVWorker:
    def __init__(
        self,
        source_id: str,
        source_path: str,
        source_type: str = "file",
        loop: bool = False,
        display: bool = False,
        enable_tracking: bool = True,
        zones: list[Zone] | None = None,
        rules: list[BehaviorRule] | None = None,
    ):
        self._source_id = source_id
        self._source_path = source_path
        self._source_type = source_type
        self._loop = loop
        self._display = display
        self._enable_tracking = enable_tracking
        self._zones = zones or []
        self._rules = rules or []
        self._running = False
        self._video_source: VideoSource | None = None
        self._detector: YOLO26Detector | None = None
        self._tracker: Tracker | None = None
        self._rule_engine: RuleEngine | None = None
        self._last_frame_timestamp: float | None = None
        self._event_adapter = PersonPresenceAdapter(
            min_confidence=settings.model.detector_confidence
        )
        self._frame_interval = 1.0 / settings.model.inference_target_fps
        self._last_inference_time = 0.0
        self._processed_frames = 0
        self._emitted_events = 0
        self._emitted_triggers = 0

    def _create_source(self) -> VideoSource:
        if self._source_type == "file":
            return MP4VideoSource(self._source_id, self._source_path, loop=self._loop)
        raise ValueError(f"Unsupported source type: {self._source_type}")

    def start(self) -> None:
        logger.info(
            "Starting CV worker",
            source_id=self._source_id,
            source_path=self._source_path,
            target_fps=settings.model.inference_target_fps,
        )

        self._video_source = self._create_source()
        self._detector = YOLO26Detector(
            model_name=settings.model.detector_name,
            confidence=settings.model.detector_confidence,
            iou=settings.model.detector_iou,
            device=settings.model.inference_device,
            classes=[0],
        )

        if self._enable_tracking:
            # The tracker owns per-camera state, so it is created per worker
            # and seeded with this source's real frame rate.
            self._tracker = ByteTrackTracker(
                frame_rate=self._video_source.get_fps()
                or settings.model.inference_target_fps
            )

        self._running = True
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        try:
            self._run_loop()
        except Exception as e:
            logger.exception("CV worker crashed", error=str(e))
            raise
        finally:
            self.stop()

    def _signal_handler(self, signum, frame):
        logger.info("Received shutdown signal", signal=signum)
        self._running = False

    def _run_loop(self) -> None:
        while self._running:
            if not self._video_source or not self._video_source.is_opened():
                logger.error("Video source not available, stopping")
                break

            frame = self._video_source.read()
            if frame is None:
                if not self._loop:
                    logger.info("End of stream reached")
                    break
                continue

            if not self._should_process(frame):
                continue

            self._process_frame(frame)

    def _should_process(self, frame: Frame) -> bool:
        """Decide whether to run inference on this frame.

        For file sources the decision must be deterministic: processing every
        Nth frame gives reproducible results, which accuracy evaluation
        depends on. Wall-clock throttling would drop a different set of frames
        on every run. Live sources cannot be frame-indexed, so they are paced
        against real elapsed time instead.
        """
        if self._source_type != "file":
            current_time = time.time()
            if current_time - self._last_inference_time < self._frame_interval:
                return False
            self._last_inference_time = current_time
            return True

        source_fps = self._video_source.get_fps() if self._video_source else 0.0
        step = max(1, round(source_fps / settings.model.inference_target_fps))
        return frame.frame_number % step == 0

    def _process_frame(self, frame: Frame) -> None:
        assert self._detector is not None

        detections = self._detector.detect(frame.data)
        self._processed_frames += 1

        snapshot: TrackSnapshot | None = None
        if self._tracker is not None:
            snapshot = self._tracker.update(detections, frame.timestamp)
            if snapshot.new_track_ids:
                logger.info(
                    "New tracks",
                    source_id=self._source_id,
                    track_ids=sorted(snapshot.new_track_ids),
                )
            if snapshot.lost_track_ids:
                logger.info(
                    "Tracks lost",
                    source_id=self._source_id,
                    track_ids=sorted(snapshot.lost_track_ids),
                )

        events = self._event_adapter.process(frame, detections)
        self._emitted_events += len(events)

        for event in events:
            logger.info(
                "Event detected",
                event_type=event.event_type,
                source_id=event.source_id,
                confidence=event.confidence,
                person_count=event.metadata.get("person_count", 0),
            )

        if snapshot is not None:
            self._apply_rules(frame, snapshot)

        if self._display:
            self._render(frame, detections, events, snapshot)

    def _apply_rules(self, frame: Frame, snapshot: TrackSnapshot) -> None:
        """Run the zone rules over this frame's tracks.

        The engine is built lazily on the first frame because a zone's polygon
        can only be resolved into pixel space once the frame size is known.
        """
        if not self._zones and not self._rules:
            return

        height, width = frame.data.shape[:2]
        if self._rule_engine is None:
            self._rule_engine = RuleEngine(
                camera_id=self._source_id, frame_width=width, frame_height=height
            )
            for zone in self._zones:
                self._rule_engine.load_zone(zone)
            for rule in self._rules:
                self._rule_engine.bind_rule(rule, rule.zone_id)

        # Durations accumulate from frame cadence, never wall clock, so that
        # replaying a clip offline reproduces identical dwell times.
        dt = 0.0
        if self._last_frame_timestamp is not None:
            dt = max(0.0, frame.timestamp - self._last_frame_timestamp)
        self._last_frame_timestamp = frame.timestamp

        triggers = self._rule_engine.process(snapshot.tracked, frame.timestamp, dt)
        self._emitted_triggers += len(triggers)

        for trigger in triggers:
            logger.warning(
                "Threat trigger",
                source_id=self._source_id,
                rule_id=trigger.rule_id,
                rule_name=trigger.rule_name,
                zone_id=trigger.zone_id,
                severity=trigger.severity,
                tracker_id=trigger.tracker_id,
                confidence=trigger.confidence,
                details=trigger.details,
            )

    def _render(
        self, frame: Frame, detections, events, snapshot: TrackSnapshot | None = None
    ) -> None:
        img = frame.data.copy()

        for d in detections:
            x1, y1, x2, y2 = [int(v) for v in d.bbox]
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            label = f"{d.class_name} {d.confidence:.2f}"
            cv2.putText(img, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        if snapshot is not None:
            for obj in snapshot.tracked:
                x1, y1, x2, y2 = [int(v) for v in obj.bbox]
                cv2.rectangle(img, (x1, y1), (x2, y2), (255, 160, 0), 1)
                cv2.putText(
                    img,
                    f"#{obj.tracker_id}",
                    (x1, y1 - 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 160, 0),
                    1,
                )

        active = len(snapshot.tracked) if snapshot is not None else 0
        status = (
            f"Frames: {self._processed_frames} | Events: {self._emitted_events} | Tracks: {active}"
        )
        cv2.putText(img, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        cv2.imshow(f"CV Worker - {self._source_id}", img)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            self._running = False

    def stop(self) -> None:
        self._running = False
        if self._video_source:
            self._video_source.release()
        if self._tracker is not None:
            self._tracker.reset()
        if self._rule_engine is not None:
            self._rule_engine.reset()
        cv2.destroyAllWindows()
        logger.info(
            "CV worker stopped",
            source_id=self._source_id,
            processed_frames=self._processed_frames,
            emitted_events=self._emitted_events,
            emitted_triggers=self._emitted_triggers,
        )


def main():
    import argparse

    parser = argparse.ArgumentParser(description="CV Worker for single video source")
    parser.add_argument("--source-id", required=True, help="Camera/source identifier")
    parser.add_argument("--source-path", required=True, help="Path to video file")
    parser.add_argument("--source-type", default="file", choices=["file", "rtsp", "webcam"])
    parser.add_argument("--loop", action="store_true", help="Loop video file")
    parser.add_argument("--display", action="store_true", help="Show debug window")
    parser.add_argument(
        "--no-tracking",
        action="store_true",
        help="Disable ByteTrack tracking (detections only)",
    )
    args = parser.parse_args()

    worker = CVWorker(
        source_id=args.source_id,
        source_path=args.source_path,
        source_type=args.source_type,
        loop=args.loop,
        display=args.display,
        enable_tracking=not args.no_tracking,
    )
    worker.start()


if __name__ == "__main__":
    main()
