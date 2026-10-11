#!/usr/bin/env python3
"""S2-2A: Experiment script for detector parameter tuning.

This script runs the CV worker on a test video with varying detector parameters
(confidence threshold, IoU, etc.) and logs precision/recall metrics for each
configuration. Results are written as JSON lines for later analysis.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class ExperimentConfig:
    detector_name: str
    confidence: float
    iou: float
    inference_fps: float


@dataclass
class ExperimentResult:
    config: ExperimentConfig
    video: str
    frames_processed: int
    detections_total: int
    tracks_created: int
    triggers_emitted: int
    duration_seconds: float
    error: Optional[str] = None


def run_experiment(
    video_path: Path,
    config: ExperimentConfig,
    camera_id: Optional[int] = None,
    timeout_seconds: int = 300,
) -> ExperimentResult:
    """Run the CV worker with given config and capture metrics."""
    start_time = time.time()

    cmd = [
        sys.executable,
        "-m", "workers.cv_worker.main",
        "--source-id", "exp_cam",
        "--source-path", str(video_path),
        "--source-type", "file",
        "--loop",
        "--no-tracking",  # Disable tracking for pure detection experiments
    ]

    # Set environment variables for detector config
    env = {
        **{k: v for k, v in {
            "MODEL_DETECTOR_NAME": config.detector_name,
            "MODEL_DETECTOR_CONFIDENCE": str(config.confidence),
            "MODEL_DETECTOR_IOU": str(config.iou),
            "MODEL_INFERENCE_TARGET_FPS": str(config.inference_fps),
        }.items() if v is not None},
    }

    if camera_id is not None:
        cmd.extend(["--camera-id", str(camera_id)])

    try:
        result = subprocess.run(
            cmd,
            env={**dict(__import__('os').environ), **env},
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        duration = time.time() - start_time

        # Parse metrics from stdout (last log line)
        frames = 0
        detections = 0
        tracks = 0
        triggers = 0
        for line in result.stdout.splitlines():
            if "CV worker stopped" in line:
                # Parse: "CV worker stopped ... processed_frames=X emitted_events=Y emitted_triggers=Z"
                parts = line.split()
                for p in parts:
                    if p.startswith("processed_frames="):
                        frames = int(p.split("=")[1])
                    elif p.startswith("emitted_events="):
                        detections = int(p.split("=")[1])
                    elif p.startswith("emitted_triggers="):
                        triggers = int(p.split("=")[1])

        return ExperimentResult(
            config=config,
            video=str(video_path),
            frames_processed=frames,
            detections_total=detections,
            tracks_created=tracks,
            triggers_emitted=triggers,
            duration_seconds=duration,
            error=result.stderr if result.returncode != 0 else None,
        )
    except subprocess.TimeoutExpired:
        return ExperimentResult(
            config=config,
            video=str(video_path),
            frames_processed=0,
            detections_total=0,
            tracks_created=0,
            triggers_emitted=0,
            duration_seconds=timeout_seconds,
            error="Timeout",
        )
    except Exception as e:
        return ExperimentResult(
            config=config,
            video=str(video_path),
            frames_processed=0,
            detections_total=0,
            tracks_created=0,
            triggers_emitted=0,
            duration_seconds=time.time() - start_time,
            error=str(e),
        )


def main():
    parser = argparse.ArgumentParser(description="Run detector parameter sweep experiments")
    parser.add_argument("--video", required=True, help="Path to test video")
    parser.add_argument("--output", default="experiment_results.jsonl", help="Output JSONL file")
    parser.add_argument("--detector", default="yolo26n", help="Detector model name")
    parser.add_argument("--confidences", nargs="+", type=float, default=[0.15, 0.25, 0.35, 0.5])
    parser.add_argument("--ious", nargs="+", type=float, default=[0.3, 0.45, 0.6])
    parser.add_argument("--inference-fps", type=float, default=5.0)
    parser.add_argument("--camera-id", type=int, help="Camera ID for DB persistence")
    parser.add_argument("--max-runs", type=int, default=50, help="Max experiment combinations")
    args = parser.parse_args()

    video_path = Path(args.video)
    if not video_path.exists():
        print(f"Error: Video not found: {video_path}")
        sys.exit(1)

    # Generate parameter combinations
    configs = []
    for conf in args.confidences:
        for iou in args.ious:
            configs.append(ExperimentConfig(
                detector_name=args.detector,
                confidence=conf,
                iou=iou,
                inference_fps=args.inference_fps,
            ))

    if len(configs) > args.max_runs:
        configs = configs[:args.max_runs]

    print(f"Running {len(configs)} experiments on {video_path}")
    print(f"Output: {args.output}")

    results = []
    for i, config in enumerate(configs, 1):
        print(f"\n[{i}/{len(configs)}] conf={config.confidence}, iou={config.iou}")
        result = run_experiment(video_path, config, camera_id=args.camera_id)
        results.append(result)
        print(f"  frames={result.frames_processed}, detections={result.detections_total}, "
              f"triggers={result.triggers_emitted}, duration={result.duration_seconds:.1f}s")
        if result.error:
            print(f"  ERROR: {result.error}")

        # Write incrementally
        with open(args.output, "a") as f:
            f.write(json.dumps(asdict(result)) + "\n")

    print(f"\nDone! Results written to {args.output}")

    # Summary
    successful = [r for r in results if r.error is None]
    print(f"\nSuccessful: {len(successful)}/{len(results)}")
    if successful:
        best = max(successful, key=lambda r: r.detections_total / max(r.frames_processed, 1))
        print(f"Best detection rate: conf={best.config.confidence}, iou={best.config.iou} "
              f"({best.detections_total}/{best.frames_processed})")


if __name__ == "__main__":
    main()