import argparse
import signal
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from app.config import settings
from app.evidence.storage import EvidenceStore, LocalEvidenceStore
from app.logging import get_logger
from workers.cv_worker.analyzer import AnalyzerConfig, FrameAnalyzer
from workers.cv_worker.camera_config import load_camera_runtime
from workers.cv_worker.clip_writer import ClipError, ClipWriter
from workers.cv_worker.detector import Detection, YOLO26Detector
from workers.cv_worker.enrichment import apply_enrichment
from workers.cv_worker.event_adapter import EventCandidate, PersonPresenceAdapter
from workers.cv_worker.incident_sink import (
    DatabaseIncidentSink,
    EvidenceAttachment,
    IncidentRecord,
    IncidentSink,
    LogIncidentSink,
)
from workers.cv_worker.rolling_buffer import BufferedFrame, RollingBuffer
from workers.cv_worker.rules.base import BehaviorRule, RuleTrigger, Zone
from workers.cv_worker.rules.engine import RuleEngine
from workers.cv_worker.tracker import ByteTrackTracker, Tracker, TrackSnapshot
from workers.cv_worker.video_source import (
    Frame,
    MP4VideoSource,
    RTSPVideoSource,
    SourceState,
    VideoSource,
    WebcamVideoSource,
)

logger = get_logger(__name__)

#: Keys accepted in ``settings.model.tracker_args``. Unknown keys fail fast
#: rather than being dropped, because a silently ignored typo would leave an
#: operator believing a tuned threshold was in force.
TRACKER_ARGS: frozenset[str] = frozenset(
    {
        "track_activation_threshold",
        "lost_track_buffer",
        "minimum_matching_threshold",
        "max_missed_frames",
    }
)


@dataclass
class _ActiveWindow:
    """Frames being collected for one incident's evidence clip.

    Opened when a rule triggers: it starts with the frames already in the
    rolling buffer (pre-event) and keeps receiving frames until
    ``until_frame`` so the clip shows what happened after the trigger too.
    """

    incident_id: int
    trigger: RuleTrigger
    frames: list[BufferedFrame]
    until_frame: int


class CVWorker:
    def __init__(
        self,
        source_id: str,
        source_path: str,
        source_type: str = "file",
        *,
        loop: bool = False,
        display: bool = False,
        enable_tracking: bool = True,
        zones: list[Zone] | None = None,
        rules: list[BehaviorRule] | None = None,
        camera_id: int | None = None,
        incident_sink: IncidentSink | None = None,
        evidence_store: EvidenceStore | None = None,
        enable_violence: bool = False,
        enable_weapon: bool = False,
        enable_fall: bool = False,
    ):
        self._source_id = source_id
        self._source_path = source_path
        self._source_type = source_type
        self._camera_id = camera_id
        self._incident_sink = (
            incident_sink
            if incident_sink is not None
            else (DatabaseIncidentSink() if camera_id is not None else LogIncidentSink())
        )
        # Evidence is only captured when something injects a store. The CLI
        # passes one when filing under a camera id; file replay and tests that
        # do not opt in never write media files.
        self._evidence_store = evidence_store
        self._clip_fps = settings.model.inference_target_fps
        self._clip_writer = ClipWriter(fps=self._clip_fps)
        self._rolling_buffer = RollingBuffer(capacity=settings.video.frame_buffer_size)
        self._active_windows: list[_ActiveWindow] = []
        self._loop = loop
        self._display = display
        self._enable_tracking = enable_tracking
        self._zones = zones or []
        self._rules = rules or []
        # The extra models are switched on by the camera's own active rules, so
        # an administrator adding a fight/weapon/person-down rule is enough to
        # make the worker run the model that rule depends on.
        self._enable_violence = enable_violence
        self._enable_weapon = enable_weapon
        self._enable_fall = enable_fall
        self._running = False
        self._video_source: VideoSource | None = None
        self._detector: YOLO26Detector | None = None
        self._analyzer: FrameAnalyzer | None = None
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
        self._recorded_incidents = 0
        self._failed_records = 0
        self._stored_evidence = 0
        self._failed_evidence = 0

    def _pre_event_frames(self) -> int:
        return max(0, round(settings.video.clip_pre_seconds * self._clip_fps))

    def _post_event_frames(self) -> int:
        return max(0, round(settings.video.clip_post_seconds * self._clip_fps))

    def _create_source(self) -> VideoSource:
        if self._source_type == "file":
            return MP4VideoSource(self._source_id, self._source_path, loop=self._loop)
        if self._source_type == "webcam":
            return WebcamVideoSource(
                self._source_id, device_id=int(self._source_path)
            )
        if self._source_type == "rtsp":
            video = settings.video
            return RTSPVideoSource(
                self._source_id,
                url=self._source_path,
                timeout=float(video.rtsp_timeout),
                reconnect_delay=float(video.rtsp_reconnect_delay),
                max_reconnect_delay=float(video.rtsp_max_reconnect_delay),
            )
        raise ValueError(f"Unsupported source type: {self._source_type}")

    def _build_tracker(self, frame_rate: float) -> Tracker:
        """Build the tracker from settings, rejecting unusable configuration."""
        tracker_type = settings.model.tracker_type
        if tracker_type != "bytetrack":
            raise ValueError(
                f"Unsupported tracker_type: {tracker_type!r} (only 'bytetrack' "
                "is implemented; refusing to run untracked and call it tracked)"
            )

        tracker_args = dict(settings.model.tracker_args or {})
        unknown = sorted(set(tracker_args) - TRACKER_ARGS)
        if unknown:
            raise ValueError(
                "Unknown model.tracker_args keys: "
                + ", ".join(unknown)
                + ". Supported keys: "
                + ", ".join(sorted(TRACKER_ARGS))
            )

        return ByteTrackTracker(frame_rate=frame_rate, **tracker_args)

    def _analyzer_config(self) -> AnalyzerConfig:
        """Build the analyzer config from settings plus this camera's rules.

        Extra models (weapon, pose, fall, violence) stay off unless enabled in
        settings or required by an active threat rule. The fall detector shares
        the ``pose_fall_detection_enabled`` switch: it is the same product
        feature, answered by a dedicated posture model. Weapon and violence keep
        a slower cadence than person tracking because they are far heavier.
        """
        model = settings.model
        return AnalyzerConfig(
            person_model=model.detector_name,
            person_confidence=model.detector_confidence,
            person_iou=model.detector_iou,
            device=model.inference_device,
            weapon_enabled=model.weapon_detection_enabled or self._enable_weapon,
            weapon_confidence=model.weapon_confidence,
            weapon_interval=6,
            pose_enabled=model.pose_fall_detection_enabled,
            pose_interval=30,
            fall_enabled=model.pose_fall_detection_enabled or self._enable_fall,
            violence_enabled=model.violence_detection_enabled or self._enable_violence,
            violence_interval=2,
        )

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
        self._analyzer = FrameAnalyzer(
            self._analyzer_config(), person_model=self._detector
        )

        if self._enable_tracking:
            # The tracker owns per-camera state, so it is created per worker
            # and seeded with this source's real frame rate.
            self._tracker = self._build_tracker(
                self._video_source.get_fps()
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

    def _signal_handler(self, signum: int, _frame: object) -> None:
        logger.info("Received shutdown signal", signal=signum)
        self._running = False

    def _run_loop(self) -> None:
        """Drive the source, deciding per state rather than per ``None``.

        A read returning nothing is ambiguous on its own - a finished clip and
        a dropped stream look identical - so the source's state decides what
        happens next: finished means stop, dropped means try to recover.
        """
        while self._running:
            if self._video_source is None:
                logger.error("Video source missing, stopping")
                break

            state = self._video_source.state
            if state is SourceState.CLOSED:
                break
            if state is SourceState.FAILED:
                logger.error(
                    "Video source failed permanently, stopping",
                    source_id=self._source_id,
                    state=state.value,
                    reconnect_attempts=self._video_source.reconnect_attempts,
                )
                break
            if state is SourceState.RECONNECTING:
                if self._video_source.reconnect():
                    logger.info(
                        "Video source reconnected",
                        source_id=self._source_id,
                        attempts=self._video_source.reconnect_attempts,
                    )
                else:
                    logger.error(
                        "Video source could not reconnect, stopping",
                        source_id=self._source_id,
                        attempts=self._video_source.reconnect_attempts,
                        state=self._video_source.state.value,
                    )
                    break
                continue
            if state is SourceState.END_OF_STREAM:
                logger.info("End of stream reached", source_id=self._source_id)
                break

            frame = self._video_source.read()
            if frame is None:
                # State was updated by read(); the next iteration acts on it.
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
        analysis = (
            self._analyzer.analyze(frame.data)
            if self._analyzer is not None
            else None
        )
        detections = (
            analysis.persons if analysis is not None else self._detector.detect(frame.data)
        )

        if self._evidence_store is not None:
            buffered = BufferedFrame(
                frame_number=frame.frame_number,
                timestamp=frame.timestamp,
                data=frame.data,
            )
            self._rolling_buffer.push(buffered)
            self._append_to_active_windows(buffered)
        self._close_windows(frame.frame_number)

        self._processed_frames += 1

        snapshot: TrackSnapshot | None = None
        if self._tracker is not None:
            snapshot = self._tracker.update(detections, frame.timestamp)
            if analysis is not None:
                # Attach the frame's weapon/fall/violence model evidence to the
                # tracks; the rules below consume those flags.
                apply_enrichment(snapshot, analysis)
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
            incident_id = self._persist(trigger)
            if incident_id is not None and self._evidence_store is not None:
                self._open_window(trigger, incident_id, frame)

    def _persist(self, trigger: RuleTrigger) -> int | None:
        """File a trigger as an incident, without letting persistence kill the stream.

        Losing the database must not stop detection: an unfiled threat is
        recoverable from logs, a worker that exited is not. Returns the filed
        incident's id when there is one, so evidence can be attached later.
        """
        try:
            incident_id = self._incident_sink.record(self._build_record(trigger))
        except Exception:
            self._failed_records += 1
            logger.exception(
                "Failed to record incident",
                source_id=self._source_id,
                rule_id=trigger.rule_id,
                failed_records=self._failed_records,
            )
            return None
        self._recorded_incidents += 1
        return incident_id

    def _build_record(self, trigger: RuleTrigger) -> IncidentRecord:
        return IncidentRecord.from_trigger(
            camera_id=self._camera_id,
            event_type=trigger.rule_id,
            severity=trigger.severity,
            confidence=trigger.confidence,
            timestamp=trigger.timestamp,
            track_ids=(trigger.tracker_id,),
            model_version=settings.model.detector_name,
            metadata={
                "source_id": self._source_id,
                "rule_name": trigger.rule_name,
                "zone_id": trigger.zone_id,
                "zone_name": trigger.zone_name,
                "tracker_id": trigger.tracker_id,
                "details": trigger.details,
            },
        )

    def _open_window(self, trigger: RuleTrigger, incident_id: int, frame: Frame) -> None:
        """Start collecting an evidence clip for a trigger.

        The window opens with the frames that already sat in the rolling
        buffer (the moments before the trigger) and absorbs each following
        processed frame until the post-event budget is spent. The window is
        closed and encoded once a later frame numbers past that budget.
        """
        pre = self._rolling_buffer.tail(self._pre_event_frames())
        until_frame = frame.frame_number + self._post_event_frames()
        window = _ActiveWindow(
            incident_id=incident_id,
            trigger=trigger,
            frames=list(pre),
            until_frame=until_frame,
        )
        self._active_windows.append(window)
        logger.info(
            "Evidence capture opened",
            incident_id=incident_id,
            rule_id=trigger.rule_id,
            frame_number=frame.frame_number,
            until_frame=until_frame,
            pre_frames=len(pre),
        )

    def _append_to_active_windows(self, buffered: BufferedFrame) -> None:
        """Feed post-event frames to every window still waiting for them."""
        for window in self._active_windows:
            if buffered.frame_number <= window.until_frame:
                window.frames.append(buffered)

    def _close_windows(self, frame_number: int) -> None:
        """Finalize any window whose post-event budget is spent."""
        remaining: list[_ActiveWindow] = []
        for window in self._active_windows:
            if frame_number > window.until_frame:
                self._finalize_window(window)
            else:
                remaining.append(window)
        self._active_windows = remaining

    def _finalize_window(self, window: _ActiveWindow) -> None:
        """Encode, store and attach one window as the incident's evidence.

        Any step may fail and the incident must survive: a clip that could
        not be encoded or stored is logged as failed evidence, never raised
        into the detection loop.
        """
        if self._evidence_store is None:
            self._failed_evidence += 1
            logger.error(
                "Evidence store is not configured",
                incident_id=window.incident_id,
            )
            return

        try:
            frames = window.frames or []
            if not frames:
                logger.warning(
                    "Evidence window empty, nothing to store",
                    incident_id=window.incident_id,
                )
                return

            token = f"{frames[0].frame_number}-{window.trigger.tracker_id}"
            clip_key = f"incidents/{window.incident_id}/{token}.mp4"
            thumbnail_key = f"incidents/{window.incident_id}/{token}.jpg"

            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
                tmp_path = Path(f.name)

            try:
                clip = self._clip_writer.cut(frames, tmp_path)
                clip_handle = self._evidence_store.put(
                    clip_key, clip.path, media_type="video/mp4"
                )
            finally:
                tmp_path.unlink(missing_ok=True)

            thumbnail = self._encode_thumbnail(frames[0].data)
            thumb_handle = self._evidence_store.put(
                thumbnail_key, thumbnail, media_type="image/jpeg"
            )

            attachment = EvidenceAttachment(
                key=clip_handle.key,
                incident_id=window.incident_id,
                evidence_type="clip",
                thumbnail_key=thumb_handle.key,
                duration_seconds=clip.duration_seconds,
                size_bytes=clip.size_bytes,
                metadata_json={
                    "source_id": self._source_id,
                    "rule_id": window.trigger.rule_id,
                    "rule_name": window.trigger.rule_name,
                    "zone_id": window.trigger.zone_id,
                    "zone_name": window.trigger.zone_name,
                    "tracker_id": window.trigger.tracker_id,
                    "severity": window.trigger.severity,
                    "confidence": window.trigger.confidence,
                    "start_frame": frames[0].frame_number,
                    "end_frame": frames[-1].frame_number,
                },
            )
            self._incident_sink.attach_evidence(window.incident_id, attachment)
            self._stored_evidence += 1
            logger.info(
                "Evidence stored",
                incident_id=window.incident_id,
                key=clip_handle.key,
                frames=len(frames),
                duration_seconds=clip.duration_seconds,
            )
        except Exception:
            self._failed_evidence += 1
            logger.exception(
                "Failed to store evidence",
                incident_id=window.incident_id,
                rule_id=window.trigger.rule_id,
                failed_evidence=self._failed_evidence,
            )

    def _encode_thumbnail(self, frame: np.ndarray, quality: int = 80) -> bytes:
        ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
        if not ok:
            raise ClipError("failed to encode thumbnail")
        return encoded.tobytes()

    def _render(
        self,
        frame: Frame,
        detections: list[Detection],
        _events: list[EventCandidate],
        snapshot: TrackSnapshot | None = None,
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
        # Close any windows that were still accumulating, so a shutdown does
        # not silently orphan evidence for incidents that already fired.
        try:
            for window in self._active_windows:
                self._finalize_window(window)
        finally:
            self._active_windows = []
            self._rolling_buffer.clear()
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
            recorded_incidents=self._recorded_incidents,
            failed_records=self._failed_records,
            stored_evidence=self._stored_evidence,
            failed_evidence=self._failed_evidence,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="CV Worker for single video source")
    parser.add_argument(
        "--source-id",
        default=None,
        help="Camera/source identifier (defaults to camera-<id> with --camera-id)",
    )
    parser.add_argument(
        "--source-path",
        default=None,
        help="Video file, device id or URL (defaults to the camera's stored URL)",
    )
    parser.add_argument(
        "--source-type", default=None, choices=["file", "rtsp", "webcam"]
    )
    parser.add_argument("--loop", action="store_true", help="Loop video file")
    parser.add_argument("--display", action="store_true", help="Show debug window")
    parser.add_argument(
        "--no-tracking",
        action="store_true",
        help="Disable ByteTrack tracking (detections only)",
    )
    parser.add_argument(
        "--camera-id",
        type=int,
        default=None,
        help=(
            "Database camera id. Loads the camera's source, zones and threat "
            "rules and files incidents under it."
        ),
    )
    args = parser.parse_args()

    runtime = (
        load_camera_runtime(args.camera_id)
        if args.camera_id is not None
        else None
    )
    source_id = args.source_id or (
        f"camera-{runtime.camera_id}" if runtime is not None else None
    )
    source_path = args.source_path or (
        runtime.source_url if runtime is not None else None
    )
    source_type = args.source_type or (
        runtime.source_type if runtime is not None else "file"
    )
    if source_id is None or source_path is None:
        parser.error("--source-id and --source-path are required without --camera-id")

    if runtime is not None:
        logger.info(
            "Loaded camera configuration",
            camera_id=runtime.camera_id,
            camera=runtime.name,
            zones=[zone.name for zone in runtime.zones],
            rules=[rule.rule_id for rule in runtime.rules],
            fight=runtime.fight_enabled,
            weapon=runtime.weapon_enabled,
            fall=runtime.fall_enabled,
        )

    worker = CVWorker(
        source_id=source_id,
        source_path=source_path,
        source_type=source_type,
        loop=args.loop,
        display=args.display,
        enable_tracking=not args.no_tracking,
        zones=runtime.zones if runtime is not None else None,
        rules=runtime.rules if runtime is not None else None,
        camera_id=args.camera_id,
        evidence_store=(
            LocalEvidenceStore(settings.video.evidence_dir)
            if args.camera_id is not None
            else None
        ),
        enable_violence=runtime.fight_enabled if runtime is not None else False,
        enable_weapon=runtime.weapon_enabled if runtime is not None else False,
        enable_fall=runtime.fall_enabled if runtime is not None else False,
    )
    worker.start()


if __name__ == "__main__":
    main()
