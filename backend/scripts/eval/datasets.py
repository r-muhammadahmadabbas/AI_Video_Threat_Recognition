"""Adapters that turn public datasets into harness ground truth.

Supported layouts:

* COCO detection annotations (JSON) - used for the person subset.
* YOLO detection folders (``images/`` + ``labels/`` + ``classes.txt``) - used
  for weapon datasets such as Weapons-130K.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from PIL import Image

from scripts.eval.metrics import BoxLabel

if TYPE_CHECKING:
    from pathlib import Path

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


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
