"""Fine-tune the fight classifier from RWF-2000.

Extracts evenly spaced frames from the 10 fps RWF-2000 clips into a YOLO
classification dataset (``Fight`` / ``NonFight``), trains ``yolo26n-cls`` on
CPU, and reports clip-level accuracy on the held-out val split.

Usage (from ``backend``)::

    python -m scripts.train_rwf_classifier
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = BACKEND_ROOT / "data" / "rwf2000"
DEFAULT_DATASET = BACKEND_ROOT / "data" / "rwf_cls"
DEFAULT_RUNS = BACKEND_ROOT / "runs" / "classify"


def extract_frames(video: str, outdir: str, count: int) -> int:
    """Save ``count`` frames, spread over the middle 80% of one clip."""
    path = Path(video)
    target = Path(outdir)
    target.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(path))
    total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if total <= 0:
        capture.release()
        return 0
    saved = 0
    for index in range(count):
        fraction = 0.1 + 0.8 * index / max(1, count - 1)
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(total * fraction))
        ok, frame = capture.read()
        if not ok:
            continue
        height, width = frame.shape[:2]
        if width > 480:
            frame = cv2.resize(frame, (480, int(height * 480 / width)))
        cv2.imwrite(
            str(target / f"{path.stem}_{index}.jpg"),
            frame,
            [cv2.IMWRITE_JPEG_QUALITY, 82],
        )
        saved += 1
    capture.release()
    return saved


def extract_split(source: Path, dataset: Path, split: str, per_clip: int) -> None:
    jobs = [
        (str(video), str(dataset / split / label), per_clip)
        for label in ("Fight", "NonFight")
        for video in sorted((source / split / label).glob("*.avi"))
    ]
    with ProcessPoolExecutor(max_workers=4) as pool:
        counts = list(pool.map(extract_frames, *zip(*jobs, strict=True)))
    print(f"{split}: {sum(counts)} frames from {len(jobs)} clips", flush=True)


def evaluate_clips(weights: Path, source: Path, frames_per_clip: int = 5) -> None:
    """Score the val split at clip level by averaging frame probabilities."""
    model = YOLO(str(weights))
    fight_index = next(
        index for index, name in model.names.items() if name.lower() == "fight"
    )
    tp = fp = fn = tn = 0
    for label in ("Fight", "NonFight"):
        for video in sorted((source / "val" / label).glob("*.avi")):
            capture = cv2.VideoCapture(str(video))
            total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
            probabilities = []
            for index in range(frames_per_clip):
                capture.set(
                    cv2.CAP_PROP_POS_FRAMES,
                    int(total * (0.1 + 0.8 * index / max(1, frames_per_clip - 1))),
                )
                ok, frame = capture.read()
                if not ok:
                    continue
                result = model.predict(
                    source=frame, imgsz=224, device="cpu", verbose=False
                )[0]
                probabilities.append(float(result.probs.data[fight_index]))
            capture.release()
            if not probabilities:
                continue
            predicted = float(np.mean(probabilities)) >= 0.5
            actual = label == "Fight"
            tp += int(predicted and actual)
            fp += int(predicted and not actual)
            fn += int(not predicted and actual)
            tn += int(not predicted and not actual)
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    accuracy = (tp + tn) / max(1, tp + tn + fp + fn)
    print(
        f"clip-level: acc={accuracy:.3f} P={precision:.3f} R={recall:.3f} "
        f"tp={tp} fp={fp} fn={fn} tn={tn}",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--frames-train", type=int, default=6)
    parser.add_argument("--frames-val", type=int, default=3)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch", type=int, default=128)
    parser.add_argument("--imgsz", type=int, default=224)
    args = parser.parse_args()

    extract_split(args.source, args.dataset, "train", args.frames_train)
    extract_split(args.source, args.dataset, "val", args.frames_val)

    model = YOLO("yolo26n-cls.pt")
    model.train(
        data=str(args.dataset),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device="cpu",
        workers=2,
        project=str(args.runs),
        name="rwf26n",
        exist_ok=True,
    )
    best = args.runs / "rwf26n" / "weights" / "best.pt"
    print(f"best weights: {best}", flush=True)
    evaluate_clips(best, args.source)


if __name__ == "__main__":
    main()
