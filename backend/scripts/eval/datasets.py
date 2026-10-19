"""Adapters that turn public datasets into harness ground truth.

Supported layouts:

* COCO detection annotations (JSON) - used for the person subset.
* YOLO detection folders (``images/`` + ``labels/`` + ``classes.txt``) - used
  for weapon datasets such as Weapons-130K.
* URFD fall-feature CSV plus ``*-cam0.mp4`` clips - fall event intervals.
* RWF-2000 style ``Fight``/``NonFight`` folder trees - clip-level labels.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from PIL import Image

from scripts.eval.metrics import BoxLabel, EventInterval
from scripts.eval.schema import ClipEvents

if TYPE_CHECKING:
    from pathlib import Path

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VIDEO_SUFFIXES = {".mp4", ".avi", ".mov", ".mkv", ".webm"}


def coco_gt(
    annotation_path: Path,
    classes: tuple[str, ...] = ("person",),
    limit: int | None = None,
) -> dict[str, list[BoxLabel]]:
    """Read COCO JSON into per-image ``xyxy`` labels for the wanted classes."""
    data = json.loads(annotation_path.read_text(encoding="utf-8"))
    wanted = set(classes)
    categories = {
        category["id"]: category["name"] for category in data["categories"]
    }
    images = {image["id"]: image["file_name"] for image in data["images"]}

    gt: dict[str, list[BoxLabel]] = {name: [] for name in images.values()}
    for annotation in data["annotations"]:
        class_name = categories.get(annotation["category_id"])
        image_name = images.get(annotation["image_id"])
        if class_name not in wanted or image_name is None:
            continue
        x, y, width, height = (float(value) for value in annotation["bbox"])
        gt[image_name].append(
            BoxLabel(
                class_name=class_name,
                bbox=(x, y, x + width, y + height),
            )
        )

    if limit is not None:
        gt = dict(list(gt.items())[:limit])
    return gt


def yolo_gt(
    images_dir: Path,
    labels_dir: Path,
    classes_path: Path,
    classes: tuple[str, ...] | None = None,
    limit: int | None = None,
) -> dict[str, list[BoxLabel]]:
    """Read a YOLO-format detection folder into per-image ``xyxy`` labels.

    ``classes`` keeps only the named classes (all classes when ``None``),
    matching the ``coco_gt`` filter so threat-only subsets can be scored
    without non-production classes dragging the mean AP down.
    """
    class_names = [
        line.strip()
        for line in classes_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    wanted = set(classes) if classes is not None else None
    image_files = sorted(
        path
        for path in images_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )
    if limit is not None:
        image_files = image_files[:limit]

    gt: dict[str, list[BoxLabel]] = {}
    for image_path in image_files:
        labels_path = labels_dir / f"{image_path.stem}.txt"
        labels: list[BoxLabel] = []
        if labels_path.exists():
            with Image.open(image_path) as image:
                width, height = image.size
            for line in labels_path.read_text(encoding="utf-8").splitlines():
                parts = line.split()
                if len(parts) != 5:
                    continue
                class_id = int(parts[0])
                class_name = class_names[class_id]
                if wanted is not None and class_name not in wanted:
                    continue
                cx, cy, box_width, box_height = (float(value) for value in parts[1:])
                labels.append(
                    BoxLabel(
                        class_name=class_name,
                        bbox=(
                            (cx - box_width / 2) * width,
                            (cy - box_height / 2) * height,
                            (cx + box_width / 2) * width,
                            (cy + box_height / 2) * height,
                        ),
                    )
                )
        gt[image_path.name] = labels
    return gt


def _read_urfd_csv(csv_path: Path) -> dict[str, list[tuple[int, int]]]:
    """Parse an URFD feature CSV into ``frame, label`` samples per sequence."""
    samples_by_sequence: dict[str, list[tuple[int, int]]] = {}
    for line in csv_path.read_text(encoding="utf-8").splitlines()[1:]:
        parts = line.split(",")
        if len(parts) < 3:
            continue
        try:
            frame = int(float(parts[1]))
            label = int(float(parts[2]))
        except ValueError:
            continue
        samples_by_sequence.setdefault(parts[0].strip(), []).append((frame, label))
    return samples_by_sequence


def _urfd_clip(
    sequence: str,
    samples: list[tuple[int, int]],
    fps: float,
    *,
    events_from_labels: bool,
) -> ClipEvents:
    samples.sort()
    events: list[EventInterval] = []
    start: int | None = None
    last = 0
    for frame, label in samples:
        last = frame
        if not events_from_labels:
            continue
        if label == -1:
            if start is not None:
                events.append(
                    EventInterval("person_down", start / fps, (frame) / fps)
                )
                start = None
            continue
        if start is None:
            start = frame
    if events_from_labels and start is not None:
        events.append(EventInterval("person_down", start / fps, (last + 1) / fps))

    clip_name = f"{sequence}-cam0.mp4"
    return ClipEvents(
        clip=clip_name,
        duration=(last + 1) / fps,
        events=events,
    )


def urfd_gt(
    csv_path: Path,
    fps: float = 30.0,
    *,
    negative_csv: Path | None = None,
) -> dict[str, ClipEvents]:
    """Read URFD fall-feature CSVs into per-clip fall intervals.

    Rows are ``sequence, frame, label, ...`` where label ``-1`` means "not
    lying", ``0`` "falling" and ``1`` "lying on the ground". Each run of
    non-``-1`` rows becomes one ``person_down`` interval; clip ids match the
    published ``<sequence>-cam0.mp4`` file names.

    Sequences in ``negative_csv`` are added with no events. Pass the ADL CSV
    here: some ADLs involve lying down voluntarily, but they are not falls, so
    they belong to the benchmark as false-alarm material.
    """
    clips: dict[str, ClipEvents] = {}
    for sequence, samples in _read_urfd_csv(csv_path).items():
        clip = _urfd_clip(sequence, samples, fps, events_from_labels=True)
        clips[clip.clip] = clip

    if negative_csv is not None:
        for sequence, samples in _read_urfd_csv(negative_csv).items():
            clip = _urfd_clip(sequence, samples, fps, events_from_labels=False)
            clips.setdefault(clip.clip, clip)
    return clips


def rwf_clip_labels(videos_root: Path) -> dict[str, set[str]]:
    """Clip-level fight labels from an RWF-2000 style folder tree.

    Every video inside a ``Fight`` folder is labelled ``violence``; videos in
    ``NonFight`` folders get an empty label set. Clip ids are paths relative
    to ``videos_root`` (posix style) so duplicated file names across folders
    stay distinct, matching the clip ids ``predict_events`` writes when it is
    pointed at the same root.
    """
    positive_dirs = {"fight", "fights", "violence"}
    negative_dirs = {"nonfight", "non-fight", "non_fight", "normal"}

    labels: dict[str, set[str]] = {}
    for path in sorted(videos_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in VIDEO_SUFFIXES:
            continue
        folder = path.parent.name.lower()
        if folder in positive_dirs:
            labels[path.relative_to(videos_root).as_posix()] = {"violence"}
        elif folder in negative_dirs:
            labels[path.relative_to(videos_root).as_posix()] = set()
    return labels


def resolve_image_paths(
    gt_by_image: dict[str, list[BoxLabel]], image_root: Path
) -> dict[str, Path]:
    """Map image ids to files, failing loudly when the dataset is incomplete."""
    paths: dict[str, Path] = {}
    missing: list[str] = []
    for image_id in gt_by_image:
        path = image_root / image_id
        if path.is_file():
            paths[image_id] = path
        else:
            missing.append(image_id)

    if missing:
        preview = ", ".join(missing[:5])
        suffix = "..." if len(missing) > 5 else ""
        raise FileNotFoundError(
            f"{len(missing)} ground-truth image(s) missing under {image_root}: "
            f"{preview}{suffix}"
        )
    return paths
