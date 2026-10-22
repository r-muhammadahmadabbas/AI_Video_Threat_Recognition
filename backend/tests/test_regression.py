"""Every stored event/clip report must be reproducible from real files."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from scripts.eval.regression import (
    NOT_RUN_BENCHMARKS,
    REPORT_FILENAME,
    REPRODUCIBLE_BENCHMARKS,
    render_markdown,
    run_regression,
)

EVAL_RESULTS = Path(__file__).resolve().parents[1] / "eval_results"


def _rows(report: dict) -> dict[str, dict]:
    return {row["benchmark"]: row for row in report["benchmarks"]}


def test_all_available_benchmarks_reproduce_their_stored_reports() -> None:
    report = run_regression(EVAL_RESULTS)
    rows = _rows(report)
    expected = {spec["benchmark"] for spec in (*REPRODUCIBLE_BENCHMARKS, *NOT_RUN_BENCHMARKS)}

    assert set(rows) == expected
    assert report["summary"] == {
        "reproduced": len(REPRODUCIBLE_BENCHMARKS),
        "mismatched": 0,
        "not_run": len(NOT_RUN_BENCHMARKS),
    }
    for spec in REPRODUCIBLE_BENCHMARKS:
        assert rows[spec["benchmark"]]["status"] == "reproduced"
        assert rows[spec["benchmark"]]["differences"] == []
    for spec in NOT_RUN_BENCHMARKS:
        row = rows[spec["benchmark"]]
        assert (row["status"], row["metrics"], bool(row["reason"])) == ("not_run", None, True)


def test_tampered_stored_report_is_reported_as_a_mismatch(tmp_path: Path) -> None:
    for path in EVAL_RESULTS.iterdir():
        if path.is_file():
            shutil.copy(path, tmp_path / path.name)
    report_path = tmp_path / "fall_events_urfd_5fps_c40.json"
    stored = json.loads(report_path.read_text(encoding="utf-8"))
    stored["metrics"]["overall"]["true_positives"] += 1
    report_path.write_text(json.dumps(stored), encoding="utf-8")

    report = run_regression(tmp_path)
    row = _rows(report)["fall_events_urfd_5fps_c40"]

    assert row["status"] == "mismatch"
    assert any("true_positives" in difference for difference in row["differences"])
    assert report["summary"]["mismatched"] == 1


def test_committed_regression_report_matches_current_results() -> None:
    committed = (EVAL_RESULTS / REPORT_FILENAME).read_text(encoding="utf-8")

    assert committed == render_markdown(run_regression(EVAL_RESULTS))
