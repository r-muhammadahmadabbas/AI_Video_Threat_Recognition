"""CLI for the offline accuracy harness.

Examples::

    # Person mAP on a COCO subset
    python -m scripts.eval.run_eval detections \
        --coco-annotations data/coco/annotations/instances_val2017.json \
        --image-root data/coco/val2017 --limit 200

    # Weapon mAP on a YOLO-format folder
    python -m scripts.eval.run_eval detections \
        --yolo-images data/weapons/images/val --yolo-labels data/weapons/labels/val \
        --yolo-classes data/weapons/classes.txt --weapon

    # Rule/event P/R/F1 against labelled clips
    python -m scripts.eval.run_eval events --gt eval_results/fall_gt.jsonl \
        --pred eval_results/fall_pred.jsonl
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from scripts.eval.datasets import coco_gt, resolve_image_paths, yolo_gt
from scripts.eval.metrics import (
    DetectionEvalResult,
    EventEvalResult,
    aggregate_event_results,
    evaluate_clip_labels,
    evaluate_detections,
    evaluate_events,
)
from scripts.eval.predict import predict_images
from scripts.eval.schema import (
    load_box_gt,
    load_clip_labels,
    load_event_gt,
    save_predictions,
)


def _load_gt(args: argparse.Namespace) -> dict:
    if args.gt_jsonl is not None:
        return load_box_gt(args.gt_jsonl)
    if args.coco_annotations is not None:
        classes = (
            tuple(name.strip() for name in args.classes.split(",") if name.strip())
            if args.classes
            else ("person",)
        )
        return coco_gt(args.coco_annotations, classes=classes, limit=args.limit)
    if args.yolo_images is not None:
        if args.yolo_labels is None or args.yolo_classes is None:
            raise SystemExit(
                "--yolo-images requires --yolo-labels and --yolo-classes"
            )
        wanted = (
            tuple(name.strip() for name in args.classes.split(",") if name.strip())
            if args.classes
            else None
        )
        return yolo_gt(
            args.yolo_images,
            args.yolo_labels,
            args.yolo_classes,
            classes=wanted,
            limit=args.limit,
        )
    raise SystemExit(
        "provide ground truth via --gt-jsonl, --coco-annotations or the YOLO flags"
    )


def _build_analyzer(args: argparse.Namespace):
    from workers.cv_worker.analyzer import AnalyzerConfig, FrameAnalyzer  # noqa: PLC0415

    extra: dict = {}
    if args.weapon_model is not None:
        extra["weapon_model_path"] = str(args.weapon_model)
    config = AnalyzerConfig(
        person_model=args.model,
        person_confidence=args.confidence,
        person_iou=args.iou,
        device=args.device,
        weapon_enabled=args.weapon,
        weapon_confidence=args.weapon_confidence,
        **extra,
    )
    return FrameAnalyzer(config)


def _print_detection_result(result: DetectionEvalResult) -> None:
    for class_name, ap in result.per_class_ap.items():
        print(f"  {class_name:<20} AP@0.5 = {ap:.4f}")
    print(
        f"  mAP@0.5 = {result.mean_ap:.4f} | images={result.num_images} "
        f"gt_boxes={result.num_gt_boxes} predictions={result.num_predictions}"
    )


def _print_event_result(result: EventEvalResult) -> None:
    for event_type, scores in result.per_type.items():
        print(
            f"  {event_type:<20} P={scores.precision:.3f} "
            f"R={scores.recall:.3f} F1={scores.f1:.3f} "
            f"(TP={scores.true_positives} FP={scores.false_positives} "
            f"FN={scores.false_negatives})"
        )
    overall = result.overall
    print(
        f"  overall              P={overall.precision:.3f} "
        f"R={overall.recall:.3f} F1={overall.f1:.3f}"
    )
    if result.false_alarms_per_minute is not None:
        print(f"  false alarms: {result.false_alarms_per_minute:.2f}/min")


def _write_report(report: dict, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"  report: {output}")


def run_detections(args: argparse.Namespace) -> None:
    gt = _load_gt(args)
    paths = resolve_image_paths(gt, args.image_root)
    analyzer = _build_analyzer(args)
    predictions = predict_images(paths, analyzer)

    result = evaluate_detections(
        gt, predictions, iou_threshold=args.match_iou
    )
    _print_detection_result(result)

    if args.pred_out is not None:
        save_predictions(args.pred_out, predictions)
        print(f"  predictions: {args.pred_out}")

    _write_report(
        {
            "kind": "detections",
            "config": {
                "model": args.model,
                "confidence": args.confidence,
                "iou": args.iou,
                "device": args.device,
                "weapon": args.weapon,
                "weapon_confidence": args.weapon_confidence,
                "match_iou": args.match_iou,
                "num_images": len(paths),
            },
            "metrics": asdict(result),
        },
        args.out,
    )


def run_events(args: argparse.Namespace) -> None:
    gt_clips = load_event_gt(args.gt)
    predicted_clips = load_event_gt(args.pred)

    per_clip: list[EventEvalResult] = []
    total_duration = 0.0
    for clip_id, gt_clip in gt_clips.items():
        predicted = predicted_clips.get(clip_id)
        per_clip.append(
            evaluate_events(
                gt_clip.events,
                predicted.events if predicted is not None else [],
                iou_threshold=args.match_iou,
            )
        )
        if gt_clip.duration is not None:
            total_duration += gt_clip.duration

    # Predictions for clips absent from the GT are pure false alarms.
    for clip_id, predicted in predicted_clips.items():
        if clip_id not in gt_clips:
            per_clip.append(
                evaluate_events([], predicted.events, iou_threshold=args.match_iou)
            )

    result = aggregate_event_results(per_clip, total_duration or None)
    _print_event_result(result)
    _write_report(
        {
            "kind": "events",
            "config": {
                "match_iou": args.match_iou,
                "num_clips": len(per_clip),
                "duration_seconds": total_duration or None,
            },
            "metrics": asdict(result),
        },
        args.out,
    )


def run_clips(args: argparse.Namespace) -> None:
    gt_labels = load_clip_labels(args.gt)
    predicted_clips = load_event_gt(args.pred)
    event_types = {
        name.strip() for name in args.events.split(",") if name.strip()
    }
    predicted_labels = {
        clip_id: (
            {args.label}
            if any(event.event_type in event_types for event in clip.events)
            else set()
        )
        for clip_id, clip in predicted_clips.items()
    }

    result = evaluate_clip_labels(gt_labels, predicted_labels, args.label)
    total_duration = sum(
        clip.duration for clip in predicted_clips.values() if clip.duration
    )
    false_alarms = (
        result.false_positives / (total_duration / 60.0)
        if total_duration
        else None
    )

    print(
        f"  {args.label:<20} P={result.precision:.3f} R={result.recall:.3f} "
        f"F1={result.f1:.3f} acc={result.accuracy:.3f} "
        f"(TP={result.true_positives} FP={result.false_positives} "
        f"FN={result.false_negatives} TN={result.true_negatives})"
    )
    if false_alarms is not None:
        print(f"  false alarms: {false_alarms:.2f}/min")

    _write_report(
        {
            "kind": "clips",
            "config": {
                "label": args.label,
                "events": sorted(event_types),
                "num_clips": len(set(gt_labels) | set(predicted_labels)),
                "duration_seconds": total_duration or None,
            },
            "metrics": {
                **asdict(result),
                "false_alarms_per_minute": false_alarms,
            },
        },
        args.out,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    detections = subparsers.add_parser(
        "detections", help="measure box mAP for person/weapon detectors"
    )
    detections.add_argument("--gt-jsonl", type=Path)
    detections.add_argument("--coco-annotations", type=Path)
    detections.add_argument("--yolo-images", type=Path)
    detections.add_argument("--yolo-labels", type=Path)
    detections.add_argument("--yolo-classes", type=Path)
    detections.add_argument("--image-root", type=Path, required=True)
    detections.add_argument(
        "--classes",
        default=None,
        help=(
            "comma-separated classes to keep (COCO default: person; "
            "YOLO default: all classes)"
        ),
    )
    detections.add_argument("--limit", type=int, default=None)
    detections.add_argument("--model", default="yolo26n")
    detections.add_argument("--confidence", type=float, default=0.25)
    detections.add_argument("--iou", type=float, default=0.45)
    detections.add_argument("--device", default="cpu")
    detections.add_argument("--weapon", action="store_true")
    detections.add_argument("--weapon-model", type=Path, default=None)
    detections.add_argument("--weapon-confidence", type=float, default=0.25)
    detections.add_argument("--match-iou", type=float, default=0.5)
    detections.add_argument(
        "--out", type=Path, default=Path("eval_results/detections.json")
    )
    detections.add_argument("--pred-out", type=Path, default=None)
    detections.set_defaults(func=run_detections)

    events = subparsers.add_parser(
        "events", help="measure rule/event precision, recall and F1"
    )
    events.add_argument("--gt", type=Path, required=True)
    events.add_argument("--pred", type=Path, required=True)
    events.add_argument(
        "--match-iou",
        type=float,
        default=0.001,
        help=(
            "temporal IoU needed to match a prediction to a ground-truth "
            "interval; 0.001 means any overlap, which is what point-like "
            "rule triggers need"
        ),
    )
    events.add_argument(
        "--out", type=Path, default=Path("eval_results/events.json")
    )
    events.set_defaults(func=run_events)

    clips = subparsers.add_parser(
        "clips", help="measure clip-level label P/R/F1 (RWF-2000 style)"
    )
    clips.add_argument("--gt", type=Path, required=True)
    clips.add_argument("--pred", type=Path, required=True)
    clips.add_argument("--label", default="violence")
    clips.add_argument(
        "--events",
        default="violence_detected,altercation",
        help="predicted event types that count as the label",
    )
    clips.add_argument(
        "--out", type=Path, default=Path("eval_results/clips.json")
    )
    clips.set_defaults(func=run_clips)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
