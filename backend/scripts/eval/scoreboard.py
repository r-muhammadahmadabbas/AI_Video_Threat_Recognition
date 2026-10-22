"""Summarize stored eval_results reports without rerunning inference or guessing."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SOURCE_DIRECTORY = "backend/eval_results"
LATENCY_REASON = (
    "existing eval report has no timing data; rerun the harness with "
    "per-frame timing to measure latency"
)
DETECTION_PRF_REASON = (
    "existing detection report records AP/mAP only; no thresholded TP/FP/FN "
    "counts are stored"
)
DETECTION_ALARM_REASON = "existing detection report has no event stream or total clip duration"
REQUIRED_FIELDS = ("precision", "recall", "f1", "false_alarms_per_10_minutes", "latency_ms")
SCORE_FIELDS = ("precision", "recall", "f1")
COUNT_FIELDS = ("true_positives", "false_positives", "false_negatives")
MISSING_COUNTS_REASON = (
    "existing eval report has no TP/FP/FN counts; its precision, recall and "
    "F1 cannot be verified"
)
REPRODUCTION_NOTES = {
    "fall_events_urfd_5fps_overlap": (
        "no matching raw prediction file is stored, and the c40/c60 prediction "
        "files do not reproduce these counts"
    ),
}
CALIBRATION_FILENAME = "person_down_calibration.json"
WEAPON_CALIBRATION_FILENAME = "weapon_calibration.json"
CALIBRATION_REPORTS = (
    ("person-down", CALIBRATION_FILENAME),
    ("weapon", WEAPON_CALIBRATION_FILENAME),
)
FALL_TRADEOFF_PREFIX = "fall_events_urfd_5fps_c"
FALL_TRADEOFF_FIELDS = (
    "true_positives",
    "false_positives",
    "false_negatives",
    "precision",
    "recall",
    "f1",
    "false_alarms_per_10_minutes",
)
STORED_TRADEOFF_REASON = (
    "the stored threshold reports cover the whole URFD benchmark; this is a "
    "stored precision/recall tradeoff, not a validation/holdout calibration, "
    "and no threshold was selected from it"
)


def _threshold_from_benchmark(name: str) -> float | None:
    """Recover the fall-model threshold encoded as ``..._c40``/``..._c60``."""
    match = re.fullmatch(rf"{re.escape(FALL_TRADEOFF_PREFIX)}(\d+)", name)
    if match is None:
        return None
    return int(match.group(1)) / 100.0


def stored_fall_threshold_tradeoff(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Collect real c40/c60 counts into a benchmark-only fall tradeoff table.

    These reports cover the whole URFD benchmark, so the table deliberately
    has no ``selected_threshold``. Using it to pick an operating point would
    tune on the evaluation set.
    """
    table = []
    for row in rows:
        threshold = _threshold_from_benchmark(row["benchmark"])
        if threshold is None or row["precision"] is None:
            continue
        table.append(
            {
                "threshold": threshold,
                "benchmark": row["benchmark"],
                "source": row["source"],
                **{field: row[field] for field in FALL_TRADEOFF_FIELDS},
            }
        )
    table.sort(key=lambda entry: entry["threshold"])
    return {
        "status": "stored_benchmark_only",
        "reason": STORED_TRADEOFF_REASON,
        "selected_threshold": None,
        "rows": table,
    }


def _missing(row: dict[str, Any], field: str, reason: str) -> None:
    row[field] = None
    row["missing"][field] = reason


def _counts(scores: dict[str, Any]) -> tuple[int, int, int] | None:
    """Return validated TP/FP/FN counts, or ``None`` when they are absent."""
    values: list[int] = []
    for field in COUNT_FIELDS:
        value = scores.get(field)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or value < 0
            or int(value) != value
        ):
            return None
        values.append(int(value))
    return values[0], values[1], values[2]


def _scores_from_counts(scores: dict[str, Any]) -> dict[str, float] | None:
    """Recompute P/R/F1 from counts so fabricated metric fields are ignored."""
    counts = _counts(scores)
    if counts is None:
        return None
    true_positives, false_positives, false_negatives = counts
    precision = (
        true_positives / (true_positives + false_positives)
        if true_positives + false_positives
        else 0.0
    )
    recall = (
        true_positives / (true_positives + false_negatives)
        if true_positives + false_negatives
        else 0.0
    )
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return {"precision": precision, "recall": recall, "f1": f1}


def _row_from_report(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    kind, metrics = data["kind"], data["metrics"]
    row: dict[str, Any] = {
        "benchmark": path.stem,
        "kind": kind,
        "source": f"{SOURCE_DIRECTORY}/{path.name}",
        "precision": None,
        "recall": None,
        "f1": None,
        "false_alarms_per_10_minutes": None,
        "latency_ms": None,
        "missing": {},
    }
    if kind == "detections":
        row["mean_ap"] = metrics.get("mean_ap")
        for field in ("precision", "recall", "f1"):
            _missing(row, field, DETECTION_PRF_REASON)
        _missing(row, "false_alarms_per_10_minutes", DETECTION_ALARM_REASON)
    else:
        scores = metrics.get("overall", metrics)
        verified = _scores_from_counts(scores)
        counts = _counts(scores)
        if counts is not None:
            (
                row["true_positives"],
                row["false_positives"],
                row["false_negatives"],
            ) = counts
        for field in SCORE_FIELDS:
            if verified is None:
                _missing(row, field, MISSING_COUNTS_REASON)
            else:
                row[field] = verified[field]
        per_minute = metrics.get("false_alarms_per_minute")
        if per_minute is None:
            _missing(
                row,
                "false_alarms_per_10_minutes",
                "existing eval report has no false-alarm rate",
            )
        else:
            row["false_alarms_per_10_minutes"] = float(per_minute) * 10.0
    latency = metrics.get("latency_ms")
    if latency is None:
        _missing(row, "latency_ms", LATENCY_REASON)
    else:
        row["latency_ms"] = float(latency)
    return row


def load_reports(results_dir: Path) -> list[tuple[Path, dict[str, Any]]]:
    reports: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(results_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "kind" in data and "metrics" in data:
            reports.append((path, data))
    return reports


def _calibration_notes(results_dir: Path) -> list[str]:
    """Surface each rule's calibration status without inventing metrics."""
    notes: list[str] = []
    for label, filename in CALIBRATION_REPORTS:
        path = results_dir / filename
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        notes.append(
            f"{label} threshold calibration status: {data.get('status', 'unknown')}"
        )
        if data.get("reason"):
            notes.append(f"{label} calibration reason: {data['reason']}")
        if data.get("selected_threshold") is not None:
            notes.append(
                f"{label} threshold selected on validation: "
                f"{data['selected_threshold']}"
            )
    return notes


def build_scoreboard(results_dir: Path) -> dict[str, Any]:
    rows = [_row_from_report(path, data) for path, data in load_reports(results_dir)]
    tradeoff = stored_fall_threshold_tradeoff(rows)
    notes = [
        "metrics are transcribed from existing reports; detection AP values "
        "were not re-run because model weights and raw images/annotations are "
        "missing",
        "event and clip benchmarks were re-run from stored ground truth and "
        "predictions with `python -m scripts.eval.regression`; see "
        "`ACCURACY_REGRESSION.md` for the full result",
        "null means the metric was not available in the stored results; the "
        "reason is recorded in each row's missing map",
        "false alarms per 10 minutes are the stored per-minute rate scaled by 10",
    ]
    notes.extend(
        f"{row['benchmark']}: {REPRODUCTION_NOTES[row['benchmark']]}"
        for row in rows
        if row["benchmark"] in REPRODUCTION_NOTES
    )
    notes.extend(_calibration_notes(results_dir))
    if tradeoff["rows"]:
        notes.append(f"person-down stored threshold tradeoff: {tradeoff['reason']}")
    return {
        "generated_from": SOURCE_DIRECTORY,
        "notes": notes,
        "fall_threshold_tradeoff": tradeoff,
        "benchmarks": rows,
    }


def _format(value: Any) -> str:
    return "null" if value is None else f"{float(value):.4f}"


def _missing_groups(row: dict[str, Any]) -> list[tuple[str, list[str]]]:
    groups: dict[str, list[str]] = {}
    for field in REQUIRED_FIELDS:
        reason = row["missing"].get(field)
        if reason is not None:
            groups.setdefault(reason, []).append(field)
    return list(groups.items())


def render_markdown(scoreboard: dict[str, Any]) -> str:
    lines = [
        "# Baseline scoreboard",
        "",
        f"Generated from `{scoreboard['generated_from']}` by "
        "`python -m scripts.eval.scoreboard`.",
        "",
    ]
    lines.extend(f"- {note}" for note in scoreboard["notes"])
    tradeoff = scoreboard.get("fall_threshold_tradeoff") or {}
    if tradeoff.get("rows"):
        lines.extend(
            [
                "",
                "## Person-down stored threshold tradeoff",
                "",
                f"{tradeoff['reason']}.",
                "",
                "| Threshold | Benchmark | TP | FP | FN | Precision | Recall "
                "| F1 | False alarms / 10 min |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        lines.extend(
            (
                f"| {row['threshold']:.2f} | `{row['benchmark']}` "
                f"| {row['true_positives']} | {row['false_positives']} "
                f"| {row['false_negatives']} | {_format(row['precision'])} "
                f"| {_format(row['recall'])} | {_format(row['f1'])} "
                f"| {_format(row['false_alarms_per_10_minutes'])} |"
            )
            for row in tradeoff["rows"]
        )
    lines.extend(
        [
            "",
            "| Benchmark | Kind | Precision | Recall | F1 | False alarms / 10 min "
            "| Latency (ms) | mAP |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in scoreboard["benchmarks"]:
        mean_ap = row.get("mean_ap")
        lines.append(
            f"| `{row['benchmark']}` | {row['kind']} "
            f"| {_format(row['precision'])} | {_format(row['recall'])} "
            f"| {_format(row['f1'])} "
            f"| {_format(row['false_alarms_per_10_minutes'])} "
            f"| {_format(row['latency_ms'])} "
            f"| {_format(mean_ap) if mean_ap is not None else 'n/a'} |"
        )
    lines.extend(
        [
            "",
            "## Missing values",
            "",
            "| Benchmark | Missing fields | Reason |",
            "| --- | --- | --- |",
        ]
    )
    for row in scoreboard["benchmarks"]:
        for reason, fields in _missing_groups(row):
            lines.append(f"| `{row['benchmark']}` | {', '.join(fields)} | {reason} |")
    lines.append("")
    return "\n".join(lines)


def write_scoreboard(results_dir: Path, out_dir: Path) -> None:
    scoreboard = build_scoreboard(results_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "BASELINE_SCOREBOARD.md").write_text(render_markdown(scoreboard), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, default=Path("eval_results"))
    parser.add_argument("--out-dir", type=Path, default=Path("eval_results"))
    args = parser.parse_args()
    write_scoreboard(args.results_dir, args.out_dir)


if __name__ == "__main__":
    main()
