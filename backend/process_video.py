"""Process a video file through threat detection with real weapon detection.

Usage:
    python process_video.py path/to/video.mp4

Uses YOLO26x (pre-trained on 130K weapon images) to detect firearms,
melee weapons, and explosives in each frame.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

from workers.cv_worker.weapon_detector import WeaponDetector, THREAT_CLASSES


def extract_frames(
    video_path: Path, every: int = 5
) -> list[tuple[float, np.ndarray]]:
    """Extract frames from video file."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"Error: cannot open video {video_path}", file=sys.stderr)
        sys.exit(1)

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"Video: {w}x{h} @ {fps:.2f}fps, {total} frames")

    frames: list[tuple[float, np.ndarray]] = []
    frame_idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_idx % every == 0:
            ts = frame_idx / fps
            frames.append((ts, frame))
        frame_idx += 1
    cap.release()
    print(f"Extracted {len(frames)} frames (every {every}th)")
    return frames


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Detect weapons in video using YOLO26"
    )
    parser.add_argument("video", type=str, help="Path to video file")
    parser.add_argument(
        "--every", type=int, default=5, help="Process every N frames (default 5)"
    )
    parser.add_argument(
        "--confidence", type=float, default=0.35, help="Detection confidence threshold"
    )
    args = parser.parse_args()

    video_path = Path(args.video)
    if not video_path.is_file():
        print(f"Video not found: {video_path}", file=sys.stderr)
        sys.exit(1)

    detector = WeaponDetector(confidence=args.confidence)
    frames = extract_frames(video_path, args.every)

    all_detections: list[dict] = []

    for ts, frame in frames:
        detections = detector.detect(frame)
        for d in detections:
            all_detections.append({
                "timestamp": round(ts, 2),
                "class": d.class_name,
                "confidence": round(d.confidence, 3),
                "bbox": [round(v, 1) for v in d.bbox],
                "is_threat": d.is_threat,
            })

    print("\n===== WEAPON DETECTION RESULTS =====")
    if not all_detections:
        print("No weapons detected in this video.")
        print("Tips:")
        print(" - Use video with clear weapon visibility")
        print(" - Lower --confidence (try 0.25)")
        print(" - Process more frames (lower --every, try 3)")
        return

    threats = [d for d in all_detections if d["is_threat"]]
    print(f"Total detections: {len(all_detections)}")
    print(f"Threat objects: {len(threats)}")
    print()

    for d in all_detections:
        marker = " THREAT" if d["is_threat"] else ""
        print(
            f"  t={d['timestamp']:6.1f}s  {d['class']:15s}  "
            f"conf={d['confidence']:.3f}  bbox={d['bbox']}{marker}"
        )

    if threats:
        print(f"\n{len(threats)} threat object(s) detected:")
        for d in threats:
            print(f"  t={d['timestamp']:.1f}s - {d['class']} (confidence {d['confidence']:.3f})")


if __name__ == "__main__":
    main()