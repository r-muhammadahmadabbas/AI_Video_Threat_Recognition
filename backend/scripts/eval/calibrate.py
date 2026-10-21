"""Calibrate an event threshold on validation and score the holdout once.

The harness does not assume a split: callers name the validation and holdout
ground-truth files explicitly, plus one prediction file per candidate threshold
for each split. The threshold is selected from validation F1 only; the holdout
files are read after selection and only for the winning threshold, so a lucky
holdout operating point cannot influence the choice.

Example::

    python -m scripts.eval.calibrate \
        --validation-gt eval_results/person_down_val_gt.jsonl \
        --validation-pred 0.40=eval_results/person_down_val_c40.jsonl \
        --validation-pred 0.60=eval_results/person_down_val_c60.jsonl \
        --holdout-gt eval_results/person_down_holdout_gt.jsonl \
        --holdout-pred 0.40=eval_results/person_down_holdout_c40.jsonl \
        --holdout-pred 0.60=eval_results/person_down_holdout_c60.jsonl

Generate the per-threshold prediction files with ``predict_events`` (for the
fall model, vary ``--fall-confidence``) before invoking the calibration.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.eval.metrics import (
    EventEvalResult,
    aggregate_event_results,
    evaluate_events,
)
from scripts.eval.schema import load_event_gt


def _score_split(
    gt_path: Path,
    prediction_path: Path,
    event_type: str,
    match_iou: float,
) -> dict[str, Any]:
    """Score one prediction file with the same aggregation as ``run_eval``."""
    gt_clips = load_event_gt(gt_path)
    predicted_clips = load_event_gt(prediction_path)
    per_clip: list[EventEvalResult] = []
    total_duration = 0.0

    for clip_id, gt_clip in gt_clips.items():
        predicted = predicted_clips.get(clip_id)
        per_clip.append(
            evaluate_events(
                gt_clip.events,
                predicted.events if predicted is not None else [],
                iou_threshold=match_iou,
            )
        )
        if gt_clip.duration is not None:
            total_duration += gt_clip.duration

    # Predictions for clips absent from the GT are pure false alarms.
    for clip_id, predicted in predicted_clips.items():
        if clip_id not in gt_clips:
            per_clip.append(
                evaluate_events([], predicted.events, iou_threshold=match_iou)
            )

    aggregate = aggregate_event_results(per_clip, total_duration or None)
    scores = aggregate.per_type.get(event_type)
    if scores is None:
        raise ValueError(
            f"{gt_path} and {prediction_path} contain no {event_type!r} "
            "labels or predictions; refusing to calibrate on an empty event"
        )
    false_alarms = (
        scores.false_positives / (total_duration / 600.0)
        if total_duration
        else None
    )
    return {
        "true_positives": scores.true_positives,
        "false_positives": scores.false_positives,
        "false_negatives": scores.false_negatives,
        "precision": scores.precision,
        "recall": scores.recall,
        "f1": scores.f1,
        "false_alarms_per_10_minutes": false_alarms,
    }


def _require_disjoint_splits(validation_gt: Path, holdout_gt: Path) -> None:
    overlap = set(load_event_gt(validation_gt)) & set(load_event_gt(holdout_gt))
    if overlap:
        preview = ", ".join(sorted(overlap)[:5])
        raise ValueError(
            f"validation and holdout clips overlap ({preview}); "
            "calibration would tune on holdout labels"
        )


def calibrate_threshold(
    *,
    event_type: str,
    validation_gt: Path,
    validation_predictions: dict[float, Path],
    holdout_gt: Path,
    holdout_predictions: dict[float, Path],
    match_iou: float = 0.001,
) -> dict[str, Any]:
    """Select a threshold on validation, then score holdout at that threshold."""
    if not validation_predictions:
        raise ValueError("at least one validation threshold prediction is required")
    _require_disjoint_splits(validation_gt, holdout_gt)

    validation = [
        {
            "threshold": threshold,
            **_score_split(
                validation_gt, prediction_path, event_type, match_iou
            ),
        }
        for threshold, prediction_path in sorted(validation_predictions.items())
    ]
    # Prefer F1; on a tie take the higher threshold so the operating point is
    # no more permissive than necessary.
    selected = max(validation, key=lambda row: (row["f1"], row["threshold"]))
    threshold = selected["threshold"]
    holdout_prediction = holdout_predictions.get(threshold)
    if holdout_prediction is None:
        raise ValueError(
            f"holdout predictions are missing the selected threshold {threshold}"
        )

    return {
        "rule": event_type,
        "event_type": event_type,
        "status": "calibrated",
        "selection_metric": "f1",
        "match_iou": match_iou,
        "selected_threshold": threshold,
        "validation": {"thresholds": validation, "selected": selected},
        "holdout": {
            "threshold": threshold,
            **_score_split(
                holdout_gt, holdout_prediction, event_type, match_iou
            ),
        },
        "notes": [
            "threshold selected on validation only",
            "holdout scored once at the selected threshold; it was not used for tuning",
            "false alarms per 10 minutes use total ground-truth clip duration",
        ],
    }


def _parse_predictions(values: list[str]) -> dict[float, Path]:
    predictions: dict[float, Path] = {}
    for value in values:
        threshold_text, separator, path_text = value.partition("=")
        if not separator or not path_text:
            raise ValueError(f"expected THRESHOLD=PATH, got {value!r}")
        threshold = float(threshold_text)
        if threshold in predictions:
            raise ValueError(f"duplicate threshold {threshold}")
        predictions[threshold] = Path(path_text)
    return predictions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-type", default="person_down")
    parser.add_argument("--match-iou", type=float, default=0.001)
    parser.add_argument("--validation-gt", type=Path, required=True)
    parser.add_argument(
        "--validation-pred",
        action="append",
        default=[],
        metavar="THRESHOLD=PATH",
        required=True,
    )
    parser.add_argument("--holdout-gt", type=Path, required=True)
    parser.add_argument(
        "--holdout-pred",
        action="append",
        default=[],
        metavar="THRESHOLD=PATH",
        required=True,
    )
    parser.add_argument(
        "--out", type=Path, default=Path("eval_results/person_down_calibration.json")
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    report = calibrate_threshold(
        event_type=args.event_type,
        validation_gt=args.validation_gt,
        validation_predictions=_parse_predictions(args.validation_pred),
        holdout_gt=args.holdout_gt,
        holdout_predictions=_parse_predictions(args.holdout_pred),
        match_iou=args.match_iou,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    selected = report["selected_threshold"]
    print(f"selected threshold {selected} on validation")
    print(f"holdout F1 {report['holdout']['f1']:.3f}")
    print(f"report: {args.out}")


if __name__ == "__main__":
    main()
