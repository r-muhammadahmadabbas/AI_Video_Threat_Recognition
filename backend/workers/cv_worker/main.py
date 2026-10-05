import signal
import sys
import time
from typing import Optional

import cv2
import numpy as np

from app.config import settings
from app.logging import get_logger
from workers.cv_worker.detector import YOLO26Detector
from workers.cv_worker.event_adapter import PersonPresenceAdapter
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
    ):
        self._source_id = source_id
        self._source_path = source_path
        self._source_type = source_type
        self._loop = loop
        self._display = display
        self._running = False
        self._video_source: Optional[VideoSource] = None
        self._detector: Optional[YOLO26Detector] = None
        self._event_adapter = PersonPresenceAdapter(
            min_confidence=settings.model.detector_confidence
        )
        self._frame_interval = 1.0 / settings.model.inference_target_fps
        self._last_inference_time = 0.0
        self._processed_frames = 0
        self._emitted_events = 0

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

            current_time = time.time()
            if current_time - self._last_inference_time < self._frame_interval:
                continue

            self._last_inference_time = current_time
            self._process_frame(frame)

    def _process_frame(self, frame: Frame) -> None:
        assert self._detector is not None

        detections = self._detector.detect(frame.data)
        self._processed_frames += 1

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

        if self._display:
            self._render(frame, detections, events)

    def _render(self, frame: Frame, detections, events) -> None:
        img = frame.data.copy()
        for d in detections:
            x1, y1, x2, y2 = [int(v) for v in d.bbox]
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            label = f"{d.class_name} {d.confidence:.2f}"
            cv2.putText(img, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        status = f"Frames: {self._processed_frames} | Events: {self._emitted_events}"
        cv2.putText(img, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        cv2.imshow(f"CV Worker - {self._source_id}", img)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            self._running = False

    def stop(self) -> None:
        self._running = False
        if self._video_source:
            self._video_source.release()
        cv2.destroyAllWindows()
        logger.info(
            "CV worker stopped",
            source_id=self._source_id,
            processed_frames=self._processed_frames,
            emitted_events=self._emitted_events,
        )


def main():
    import argparse

    parser = argparse.ArgumentParser(description="CV Worker for single video source")
    parser.add_argument("--source-id", required=True, help="Camera/source identifier")
    parser.add_argument("--source-path", required=True, help="Path to video file")
    parser.add_argument("--source-type", default="file", choices=["file", "rtsp", "webcam"])
    parser.add_argument("--loop", action="store_true", help="Loop video file")
    parser.add_argument("--display", action="store_true", help="Show debug window")
    args = parser.parse_args()

    worker = CVWorker(
        source_id=args.source_id,
        source_path=args.source_path,
        source_type=args.source_type,
        loop=args.loop,
        display=args.display,
    )
    worker.start()


if __name__ == "__main__":
    main()