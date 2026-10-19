"""Run the production detection pipeline over video clips for event scoring.

Emits one JSON Lines record per clip in the same shape ``load_event_gt``
reads, so ``python -m scripts.eval.run_eval events --gt ... --pred ...``
scores rule accuracy end to end.

Rule events are points in time while the harness scores intervals. Consecutive
events of one rule are merged when the gap between them is at most two sample
periods, and every interval is extended by one sample period so a
single-frame detection still overlaps its ground-truth interval.

Examples::

    python -m scripts.eval.predict_events \
        --videos data/urfd/videos \
        --out eval_results/fall_pred.jsonl --target-fps 2
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import cv2

from scripts.eval.datasets import VIDEO_SUFFIXES
from scripts.eval.metrics import EventInterval
from scripts.eval.schema import ClipEvents, save_clip_events

if TYPE_CHECKING:
    import numpy as np

    from workers.cv_worker.pipeline import RuleEvent

DEFAULT_FPS = 25.0
GAP_TOLERANCE_PERIODS = 2.0
MIN_DURATION_PERIODS = 1.0


class EventLike(Protocol):
    rule: str
    timestamp: float


class PipelineLike(Protocol):
    events: list[RuleEvent]

    def reset_session(self) -> None: ...

    def process_frame(self, frame: np.ndarray, timestamp: float) -> tuple: ...


class CaptureLike(Protocol):
    def get(self, property_id: int) -> float: ...

    def read(self) -> tuple[bool, np.ndarray | None]: ...

    def release(self) -> None: ...


def video_files(directory: Path) -> list[Path]:
    """Every video file directly under ``directory``, in stable order."""
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in VIDEO_SUFFIXES
    )


def events_to_intervals(
    events: list[EventLike],
    *,
    gap_tolerance: float,
    min_duration: float,
) -> list[EventInterval]:
    """Merge point events of one rule into intervals for temporal scoring."""
    stamps_by_rule: dict[str, list[float]] = {}
    for event in events:
        stamps_by_rule.setdefault(event.rule, []).append(event.timestamp)

    intervals: list[EventInterval] = []
    for rule, stamps in stamps_by_rule.items():
        stamps.sort()
        start = previous = stamps[0]
        for stamp in stamps[1:]:
            if stamp - previous > gap_tolerance:
                intervals.append(
                    EventInterval(rule, start, previous + min_duration)
                )
                start = stamp
            previous = stamp
        intervals.append(EventInterval(rule, start, previous + min_duration))

    intervals.sort(key=lambda interval: (interval.event_type, interval.start))
    return intervals


def predict_clip_from_capture(
    capture: CaptureLike,
    clip_name: str,
    pipeline: PipelineLike,
    target_fps: float = 1.0,
) -> ClipEvents:
    """Sample one capture at ``target_fps`` and collect the rule events."""
    fps = capture.get(cv2.CAP_PROP_FPS)
    if not fps or math.isnan(fps) or fps <= 0:
        fps = DEFAULT_FPS

    step = max(1, round(fps / target_fps)) if target_fps > 0 else 1
    sample_period = step / fps

    pipeline.reset_session()
    index = 0
    while True:
        ok, frame = capture.read()
        if not ok or frame is None:
            break
        if index % step == 0:
            pipeline.process_frame(frame, index / fps)
        index += 1

    return ClipEvents(
        clip=clip_name,
        duration=index / fps,
        events=events_to_intervals(
            pipeline.events,
            gap_tolerance=GAP_TOLERANCE_PERIODS * sample_period,
            min_duration=MIN_DURATION_PERIODS * sample_period,
        ),
    )


def predict_clip(
    path: Path, pipeline: PipelineLike, target_fps: float = 1.0
) -> ClipEvents:
    """Open one video file and return its predicted event intervals."""
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        capture.release()
        raise ValueError(f"could not open video: {path}")
    try:
        return predict_clip_from_capture(capture, path.name, pipeline, target_fps)
    finally:
        capture.release()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--videos", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--target-fps", type=float, default=1.0)
    parser.add_argument("--confidence", type=float, default=0.30)
    return parser


def main() -> None:
    args = build_parser().parse_args()

    from workers.cv_worker.pipeline import (  # noqa: PLC0415
        DetectionPipeline,
    )

    pipeline = DetectionPipeline(
        confidence=args.confidence, frame_rate=args.target_fps
    )

    clips: dict[str, ClipEvents] = {}
    for path in video_files(args.videos):
        clip = predict_clip(path, pipeline, args.target_fps)
        clips[clip.clip] = clip
        duration = clip.duration or 0.0
        print(f"{clip.clip}: duration={duration:.1f}s events={len(clip.events)}")

    save_clip_events(args.out, clips)
    print(f"predictions: {args.out} ({len(clips)} clips)")


if __name__ == "__main__":
    main()
