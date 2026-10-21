"""Summarize stored eval_results reports without rerunning inference or guessing."""

from __future__ import annotations

import argparse
import json
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
REPRODUCTION_NOTES = {
    "fall_events_urfd_5fps_overlap": (
        "no matching raw prediction file is stored, and the c40/c60 prediction "
        "files do not reproduce these counts"
    ),
}


def _missing(row: dict[str, Any], field: str, reason: str) -> None:
    row[field] = None
    row["missing"][field] = reason


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
        for field in ("precision", "recall", "f1"):
            value = scores.get(field)
            if value is None:
                _missing(row, field, f"existing eval report does not include {field}")
            else:
                row[field] = float(value)
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


def build_scoreboard(results_dir: Path) -> dict[str, Any]:
    rows = [_row_from_report(path, data) for path, data in load_reports(results_dir)]
    notes = [
        "metrics are transcribed from existing reports; the offline harness "
        "was not rerun because model weights are missing",
        "null means the metric was not available in the stored results; the "
        "reason is recorded in each row's missing map",
        "false alarms per 10 minutes are the stored per-minute rate scaled by 10",
    ]
    notes.extend(
        f"{row['benchmark']}: {REPRODUCTION_NOTES[row['benchmark']]}"
        for row in rows
        if row["benchmark"] in REPRODUCTION_NOTES
    )
    return {"generated_from": SOURCE_DIRECTORY, "notes": notes, "benchmarks": rows}


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
