"""The final report must stay tied to committed evidence and a prioritized backlog."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from scripts.eval.regression import run_regression

BACKEND = Path(__file__).resolve().parents[1]
EVAL_RESULTS = BACKEND / "eval_results"
REPORT = EVAL_RESULTS / "FINAL_ACCURACY_REPORT.md"


def _format(value: Any) -> str:
    return "null" if value is None else f"{float(value):.4f}"


def _report_text() -> str:
    return REPORT.read_text(encoding="utf-8")


def test_report_quotes_current_regression_table() -> None:
    text = _report_text()
    report = run_regression(EVAL_RESULTS)
    summary = report["summary"]

    assert (
        f"{summary['reproduced']} reproduced, {summary['mismatched']} mismatched, "
        f"{summary['not_run']} not run"
    ) in text

    for row in report["benchmarks"]:
        assert f"`{row['benchmark']}`" in text
        if row["status"] == "not_run":
            continue
        scores = row["metrics"]["overall"] if row["kind"] == "events" else row["metrics"]
        per_minute = row["metrics"]["false_alarms_per_minute"]
        per_ten = per_minute * 10.0 if per_minute is not None else None
        expected = (
            f"| `{row['benchmark']}` | {row['kind']} | {scores['true_positives']} "
            f"| {scores['false_positives']} | {scores['false_negatives']} "
            f"| {_format(scores['precision'])} | {_format(scores['recall'])} "
            f"| {_format(scores['f1'])} | {_format(per_ten)} |"
        )
        assert expected in text


def test_report_quotes_stored_detection_ap_without_claiming_a_rerun() -> None:
    text = _report_text()

    for benchmark in ("coco_person_100", "coco_person_500", "weapons_val_500"):
        stored = json.loads(
            (EVAL_RESULTS / f"{benchmark}.json").read_text(encoding="utf-8")
        )
        mean_ap = stored["metrics"]["mean_ap"]
        assert f"| `{benchmark}` | {mean_ap:.4f} |" in text


def test_report_documents_blocked_assets_and_calibration() -> None:
    text = _report_text()

    assert "Accuracy measured: no" in text
    assert "`backend/models/`" in text
    assert "`backend/data/`" in text

    for filename in ("person_down_calibration.json", "weapon_calibration.json"):
        calibration = json.loads(
            (EVAL_RESULTS / filename).read_text(encoding="utf-8")
        )
        assert calibration["status"] == "not_run"
        assert calibration["selected_threshold"] is None
        assert (
            f"{calibration['rule']} threshold calibration: "
            f"`{calibration['status']}`"
        ) in text


def test_report_has_exactly_three_prioritized_experiments() -> None:
    text = _report_text()
    section = text.split("## Next three experiments", 1)
    assert len(section) == 2

    priorities = re.findall(
        r"^\d+\. \*\*(P\d+) \u2014", section[1], flags=re.MULTILINE
    )
    assert priorities == ["P0", "P1", "P2"]
