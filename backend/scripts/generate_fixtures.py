#!/usr/bin/env python3
"""Generate test video fixtures for S2-2D validation.

Creates short reproducible clips:
- single_person: one person walking across frame
- two_persons_crossing: two people crossing paths
- partial_occlusion: person briefly occluded by object
- re_entry: person leaves and re-enters zone
"""

from __future__ import annotations

import argparse
import cv2
import numpy as np
from pathlib import Path


def draw_person(frame: np.ndarray, center: tuple[int, int], color: tuple[int, int, int] = (0, 255, 0), size: int = 40) -> None:
    """Draw a simple person-like rectangle."""
    x, y = center
    w, h = size, size * 2
    cv2.rectangle(frame, (x - w // 2, y - h // 2), (x + w // 2, y + h // 2), color, -1)
    # Head
    cv2.circle(frame, (x, y - h // 2 - 10), 12, color, -1)


def draw_occluder(frame: np.ndarray, rect: tuple[int, int, int, int], color: tuple[int, int, int] = (128, 128, 128)) -> None:
    """Draw a gray occluding rectangle."""
    x1, y1, x2, y2 = rect
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, -1)


def generate_single_person(output_path: Path, frames: int = 60, width: int = 640, height: int = 480, fps: float = 30.0) -> None:
    """Single person walking left to right across the frame."""
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))

    for i in range(frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        # Person moves from left to right
        progress = i / frames
        x = int(width * 0.1 + progress * width * 0.8)
        y = height // 2
        draw_person(frame, (x, y))
        writer.write(frame)
    writer.release()


def generate_two_persons_crossing(output_path: Path, frames: int = 90, width: int = 640, height: int = 480, fps: float = 30.0) -> None:
    """Two persons crossing paths diagonally."""
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))

    for i in range(frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        progress = i / frames

        # Person 1: top-left to bottom-right
        x1 = int(width * 0.1 + progress * width * 0.8)
        y1 = int(height * 0.2 + progress * height * 0.6)
        draw_person(frame, (x1, y1), (0, 255, 0))

        # Person 2: bottom-left to top-right
        x2 = int(width * 0.1 + progress * width * 0.8)
        y2 = int(height * 0.8 - progress * height * 0.6)
        draw_person(frame, (x2, y2), (255, 0, 0))

        writer.write(frame)
    writer.release()


def generate_partial_occlusion(output_path: Path, frames: int = 90, width: int = 640, height: int = 480, fps: float = 30.0) -> None:
    """Person walking behind a vertical occluder (partial occlusion)."""
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))

    occluder_x = width // 2
    occluder_w = 60

    for i in range(frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        progress = i / frames

        # Person walks left to right, passing behind occluder
        x = int(width * 0.1 + progress * width * 0.8)
        y = height // 2

        # Draw occluder first
        draw_occluder(frame, (occluder_x - occluder_w // 2, 0, occluder_x + occluder_w // 2, height))

        # Draw person (will be partially occluded when overlapping)
        person_color = (0, 255, 0)
        # Only draw visible parts (simple: don't draw if behind occluder)
        if x < occluder_x - occluder_w // 2 or x > occluder_x + occluder_w // 2:
            draw_person(frame, (x, y), (0, 255, 0))
        else:
            # Draw left visible part
            left_part_x = occluder_x - occluder_w // 2 - 20
            if left_part_x > 0:
                draw_person(frame, (left_part_x, y), (0, 255, 0))
            # Draw right visible part
            right_part_x = occluder_x + occluder_w // 2 + 20
            if right_part_x < width:
                draw_person(frame, (right_part_x, y), (0, 255, 0))

        writer.write(frame)
    writer.release()


def generate_re_entry(output_path: Path, frames: int = 120, width: int = 640, height: int = 480, fps: float = 30.0) -> None:
    """Person enters zone, leaves, then re-enters."""
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))

    # Zone in center
    zone_x, zone_y = width // 2, height // 2
    zone_w, zone_h = 200, 150

    for i in range(frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)

        # Draw zone
        cv2.rectangle(frame,
                      (zone_x - zone_w // 2, zone_y - zone_h // 2),
                      (zone_x + zone_w // 2, zone_y + zone_h // 2),
                      (0, 0, 255), 2)

        # Movement pattern: enter, leave, wait, re-enter
        phase = i / frames
        if phase < 0.3:
            # Enter zone
            progress = phase / 0.3
            x = int(width * 0.1 + progress * (zone_x - zone_w // 2 - width * 0.1))
            y = zone_y
        elif phase < 0.5:
            # Leave zone (move right)
            progress = (phase - 0.3) / 0.2
            x = int(zone_x + zone_w // 2 + progress * (width * 0.9 - zone_x - zone_w // 2))
            y = zone_y
        elif phase < 0.7:
            # Wait outside
            x = int(width * 0.9)
            y = zone_y
        else:
            # Re-enter from right
            progress = (phase - 0.7) / 0.3
            x = int(width * 0.9 - progress * (width * 0.9 - (zone_x - zone_w // 2)))
            y = zone_y

        draw_person(frame, (x, y))
        writer.write(frame)
    writer.release()


def main():
    parser = argparse.ArgumentParser(description="Generate test video fixtures")
    parser.add_argument("--output-dir", default="tests/fixtures", help="Output directory")
    parser.add_argument("--width", type=int, default=640, help="Frame width")
    parser.add_argument("--height", type=int, default=480, help="Frame height")
    parser.add_argument("--fps", type=float, default=30.0, help="Frames per second")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    fixtures = [
        ("single_person.mp4", generate_single_person),
        ("two_persons_crossing.mp4", generate_two_persons_crossing),
        ("partial_occlusion.mp4", generate_partial_occlusion),
        ("re_entry.mp4", generate_re_entry),
    ]

    for name, generator in fixtures:
        path = out_dir / name
        print(f"Generating {name}...")
        generator(path, width=args.width, height=args.height, fps=args.fps)
        print(f"  -> {path} ({path.stat().st_size} bytes)")

    print("\nDone! Fixtures generated in:", out_dir)


if __name__ == "__main__":
    main()