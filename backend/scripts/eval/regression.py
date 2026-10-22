"""Re-run every benchmark that has enough stored files to reproduce offline.

Model weights are not in the repository, so this runner does not perform
detector inference. It re-scores event and clip benchmarks from their committed
ground truth and prediction files with the same metric code as ``run_eval``,
then reports any disagreement with the stored JSON reports. Detection
benchmarks are listed as not run with the missing asset that blocks them.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict
from pathlib import Path
from typing import Any

from scripts.eval.metrics import (
    aggregate_event_results,
    evaluate_clip_labels,
    evaluate_events,
)
from scripts.eval.schema import load_clip_labels, load_event_gt

RESULTS_DIRECTORY = "backend/eval_results"
REPORT_FILENAME = "ACCURACY_REGRESSION.md"

REPRODUCIBLE_BENCHMARKS: tuple[dict[str, Any], ...] = (
    {
        "benchmark": "fall_events_urfd_5fps_c40",
        "kind": "events",
        "gt": "fall_gt_urfd.jsonl",
        "pred": "fall_pred_urfd_5fps_c40.jsonl",
    },
    {
        "benchmark": "fall_events_urfd_5fps_c60",
        "kind": "events",
        "gt": "fall_gt_urfd.jsonl",
        "pred": "fall_pred_urfd_5fps_c60.jsonl",
    },
    {
        "benchmark": "urfd_combined_5fps_events",
        "kind": "events",
        "gt": "fall_gt_urfd.jsonl",
        "pred": "urfd_combined_5fps.jsonl",
    },
    {
        "benchmark": "rwf_val_clips_5fps",
        "kind": "clips",
        "gt": "rwf_val_labels.jsonl",
        "pred": "rwf_val_pred_5fps.jsonl",
        "label": "violence",
        "event_types": ("altercation",),
    },
    {
        "benchmark": "rwf_val_clips_violence_2fps",
        "kind": "clips",
        "gt": "rwf_val_labels.jsonl",
        "pred": "rwf_val_pred_violence_2fps.jsonl",
        "label": "violence",
        "event_types": ("violence_detected",),
    },
)

NOT_RUN_BENCHMARKS: tuple[dict[str, str], ...] = (
    {
        "benchmark": "coco_person_100",
        "kind": "detections",
        "reason": (
            "stored predictions exist, but COCO annotations/images and model "
            "weights are absent"
        ),
    },
    {
        "benchmark": "coco_person_500",
        "kind": "detections",
        "reason": (
            "stored predictions exist, but COCO annotations/images and model "
            "weights are absent"
        ),
    },
    {
        "benchmark": "fall_events_urfd_5fps_overlap",
        "kind": "events",
        "reason": (
            "no matching prediction file is stored; the c40/c60 files produce "
            "different counts"
        ),
    },
    {
        "benchmark": "weapons_val_500",
        "kind": "detections",
        "reason": (
            "stored predictions exist, but YOLO labels/images and model weights "
            "are absent"
        ),
    },
)

FLOAT_TOLERANCE = {"rel_tol": 1e-9, "abs_tol": 1e-12}


def _event_metrics(gt_path: Path, pred_path: Path, match_iou: float) -> dict[str, Any]:
    """Score an event prediction file exactly like ``run_eval events``."""
    gt, predicted = load_event_gt(gt_path), load_event_gt(pred_path)
    per_clip = [
        evaluate_events(
            clip.events,
            predicted[clip.clip].events if clip.clip in predicted else [],
            iou_threshold=match_iou,
        )
        for clip in gt.values()
    ]
    # Predictions for clips absent from the GT are pure false alarms.
    per_clip.extend(
        evaluate_events([], clip.events, iou_threshold=match_iou)
        for clip_id, clip in predicted.items()
        if clip_id not in gt
    )
    duration = sum(clip.duration for clip in gt.values() if clip.duration is not None)
    result = aggregate_event_results(per_clip, duration or None)
    return {
        "per_type": {
            name: asdict(scores) for name, scores in result.per_type.items()
        },
        "overall": asdict(result.overall),
        "false_alarms_per_minute": result.false_alarms_per_minute,
    }


def _clip_metrics(
    gt_path: Path, pred_path: Path, label: str, event_types: tuple[str, ...]
) -> dict[str, Any]:
    """Score a clip prediction file exactly like ``run_eval clips``."""
    gt_labels = load_clip_labels(gt_path)
    predicted = load_event_gt(pred_path)
    wanted = set(event_types)
    predicted_labels = {
        clip_id: (
            {label}
            if any(event.event_type in wanted for event in clip.events)
            else set()
        )
        for clip_id, clip in predicted.items()
    }
    result = evaluate_clip_labels(gt_labels, predicted_labels, label)
    duration = sum(clip.duration for clip in predicted.values() if clip.duration)
    per_minute = result.false_positives / (duration / 60.0) if duration else None
    return {**asdict(result), "false_alarms_per_minute": per_minute}


def _differences(stored: Any, rerun: Any, prefix: str = "metrics") -> list[str]:
    """Describe every numeric or structural disagreement between two reports."""
    if isinstance(stored, dict) and isinstance(rerun, dict):
        differences: list[str] = []
        for key in sorted(set(stored) | set(rerun)):
            path = f"{prefix}.{key}"
            if key not in stored:
                differences.append(f"{path}: missing from stored report")
            elif key not in rerun:
                differences.append(f"{path}: missing from rerun")
            else:
                differences.extend(_differences(stored[key], rerun[key], path))
        return differences
    numeric = (int, float)
    if all(isinstance(value, numeric) and not isinstance(value, bool) for value in (stored, rerun)):
        if math.isclose(float(stored), float(rerun), **FLOAT_TOLERANCE):
            return []
    elif stored == rerun:
        return []
    return [f"{prefix}: stored {stored!r} != rerun {rerun!r}"]


def _spec_metrics(spec: dict[str, Any], results_dir: Path) -> dict[str, Any]:
    if spec["kind"] == "events":
        return _event_metrics(
            results_dir / spec["gt"],
            results_dir / spec["pred"],
            spec.get("match_iou", 0.001),
        )
    return _clip_metrics(
        results_dir / spec["gt"],
        results_dir / spec["pred"],
        spec["label"],
        spec["event_types"],
    )


def run_regression(results_dir: Path) -> dict[str, Any]:
    """Re-run every reproducible benchmark and compare it with its stored report."""
    benchmarks: list[dict[str, Any]] = []
    for spec in REPRODUCIBLE_BENCHMARKS:
        stored = json.loads(
            (results_dir / f"{spec['benchmark']}.json").read_text(encoding="utf-8")
        )
        rerun = _spec_metrics(spec, results_dir)
        differences = _differences(stored["metrics"], rerun)
        benchmarks.append(
            {
                "benchmark": spec["benchmark"],
                "kind": spec["kind"],
                "status": "reproduced" if not differences else "mismatch",
                "metrics": rerun,
                "differences": differences,
            }
        )
    benchmarks.extend(
        {
            "benchmark": spec["benchmark"],
            "kind": spec["kind"],
            "status": "not_run",
            "metrics": None,
            "reason": spec["reason"],
        }
        for spec in NOT_RUN_BENCHMARKS
    )
    return {
        "generated_from": RESULTS_DIRECTORY,
        "summary": {
            "reproduced": sum(row["status"] == "reproduced" for row in benchmarks),
            "mismatched": sum(row["status"] == "mismatch" for row in benchmarks),
            "not_run": sum(row["status"] == "not_run" for row in benchmarks),
        },
        "benchmarks": benchmarks,
    }


def _format(value: Any) -> str:
    return "null" if value is None else f"{float(value):.4f}"


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Accuracy regression",
        "Re-ran every benchmark with committed ground truth and predictions via "
        "`python -m scripts.eval.regression`.",
        "Not-run benchmarks need model weights or raw datasets; no metric is invented.",
        "",
        f"- reproduced: {summary['reproduced']}, mismatched: "
        f"{summary['mismatched']}, not run: {summary['not_run']}",
        "",
        "| Benchmark | Kind | TP | FP | FN | Precision | Recall | F1 "
        "| False alarms / 10 min |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in report["benchmarks"]:
        if row["status"] == "not_run":
            continue
        scores = row["metrics"]["overall"] if row["kind"] == "events" else row["metrics"]
        per_minute = row["metrics"]["false_alarms_per_minute"]
        per_ten = per_minute * 10.0 if per_minute is not None else None
        lines.append(
            f"| `{row['benchmark']}` | {row['kind']} "
            f"| {scores['true_positives']} | {scores['false_positives']} "
            f"| {scores['false_negatives']} | {_format(scores['precision'])} "
            f"| {_format(scores['recall'])} | {_format(scores['f1'])} "
            f"| {_format(per_ten)} |"
        )
    mismatches = [row for row in report["benchmarks"] if row["status"] == "mismatch"]
    if mismatches:
        lines.extend(["", "## Mismatches", ""])
        for row in mismatches:
            lines.append(f"### `{row['benchmark']}`")
            lines.extend(f"- {difference}" for difference in row["differences"])
            lines.append("")
    lines.extend(
        [
            "",
            "## Not run",
            "",
            "| Benchmark | Kind | Reason |",
            "| --- | --- | --- |",
        ]
    )
    lines.extend(
        f"| `{row['benchmark']}` | {row['kind']} | {row['reason']} |"
        for row in report["benchmarks"]
        if row["status"] == "not_run"
    )
    lines.append("")
    return "\n".join(lines)


def write_regression(results_dir: Path, out_dir: Path) -> None:
    report = run_regression(results_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / REPORT_FILENAME).write_text(render_markdown(report), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, default=Path("eval_results"))
    parser.add_argument("--out-dir", type=Path, default=Path("eval_results"))
    args = parser.parse_args()
    write_regression(args.results_dir, args.out_dir)


if __name__ == "__main__":
    main()
