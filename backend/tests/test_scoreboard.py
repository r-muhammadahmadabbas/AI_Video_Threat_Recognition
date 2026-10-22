"""The baseline scoreboard must transcribe stored metrics and never invent them."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.eval.scoreboard import REQUIRED_FIELDS, build_scoreboard, render_markdown

BACKEND = Path(__file__).resolve().parents[1]
EVAL_RESULTS = BACKEND / "eval_results"


def _rows(scoreboard: dict) -> dict[str, dict]:
    return {row["benchmark"]: row for row in scoreboard["benchmarks"]}


def test_scoreboard_transcribes_existing_results() -> None:
    rows = _rows(build_scoreboard(EVAL_RESULTS))
    assert set(rows) == {
        "coco_person_100",
        "coco_person_500",
        "fall_events_urfd_5fps_c40",
        "fall_events_urfd_5fps_c60",
        "fall_events_urfd_5fps_overlap",
        "rwf_val_clips_5fps",
        "rwf_val_clips_violence_2fps",
        "urfd_combined_5fps_events",
        "weapons_val_500",
    }
    fall_c40 = rows["fall_events_urfd_5fps_c40"]
    assert fall_c40["precision"] == pytest.approx(0.4339622641509434)
    assert fall_c40["recall"] == pytest.approx(0.7666666666666667)
    assert fall_c40["f1"] == pytest.approx(0.5542168674698795)
    assert fall_c40["false_alarms_per_10_minutes"] == pytest.approx(45.15427711347102)
    violence = rows["rwf_val_clips_violence_2fps"]
    assert violence["f1"] == pytest.approx(0.8096385542168675)
    assert violence["false_alarms_per_10_minutes"] == pytest.approx(14.1)
    assert rows["coco_person_100"]["mean_ap"] == pytest.approx(0.6325387648290377)
    assert rows["weapons_val_500"]["mean_ap"] == pytest.approx(0.8544660312850185)


def test_missing_metrics_stay_null_with_a_reason() -> None:
    rows = _rows(build_scoreboard(EVAL_RESULTS))
    for row in rows.values():
        assert row["latency_ms"] is None
        assert "timing data" in row["missing"]["latency_ms"]
        for field in REQUIRED_FIELDS:
            if row[field] is None:
                assert row["missing"][field]
    for benchmark in ("coco_person_100", "coco_person_500", "weapons_val_500"):
        row = rows[benchmark]
        assert row["precision"] is None
        assert row["recall"] is None
        assert row["f1"] is None
        assert row["false_alarms_per_10_minutes"] is None
        assert "AP/mAP only" in row["missing"]["precision"]


def test_absent_false_alarm_rate_is_not_zero(tmp_path: Path) -> None:
    report = {
        "kind": "events",
        "config": {},
        "metrics": {
            "overall": {
                "true_positives": 1,
                "false_positives": 0,
                "false_negatives": 0,
                "precision": 1.0,
                "recall": 1.0,
                "f1": 1.0,
            },
            "per_type": {},
        },
    }
    (tmp_path / "events.json").write_text(json.dumps(report), encoding="utf-8")
    row = _rows(build_scoreboard(tmp_path))["events"]
    assert row["false_alarms_per_10_minutes"] is None
    assert "false-alarm rate" in row["missing"]["false_alarms_per_10_minutes"]


def test_fabricated_perfect_metrics_are_recomputed_from_counts(tmp_path: Path) -> None:
    report = {
        "kind": "clips",
        "config": {},
        "metrics": {
            "true_positives": 0,
            "false_positives": 0,
            "false_negatives": 0,
            "true_negatives": 0,
            "precision": 1.0,
            "recall": 1.0,
            "f1": 1.0,
            "accuracy": 1.0,
        },
    }
    (tmp_path / "empty_labels.json").write_text(json.dumps(report), encoding="utf-8")

    row = _rows(build_scoreboard(tmp_path))["empty_labels"]

    assert row["precision"] == 0.0
    assert row["recall"] == 0.0
    assert row["f1"] == 0.0


def test_metrics_without_counts_are_missing_not_perfect(tmp_path: Path) -> None:
    report = {
        "kind": "events",
        "config": {},
        "metrics": {
            "overall": {"precision": 1.0, "recall": 1.0, "f1": 1.0},
            "false_alarms_per_minute": 0.0,
        },
    }
    (tmp_path / "fabricated.json").write_text(json.dumps(report), encoding="utf-8")

    row = _rows(build_scoreboard(tmp_path))["fabricated"]

    for field in ("precision", "recall", "f1"):
        assert row[field] is None
        assert "TP/FP/FN" in row["missing"][field]


def test_stored_fall_tradeoff_is_benchmark_only_and_uses_report_counts() -> None:
    scoreboard = build_scoreboard(EVAL_RESULTS)
    tradeoff = scoreboard["fall_threshold_tradeoff"]

    assert tradeoff["status"] == "stored_benchmark_only"
    assert tradeoff["selected_threshold"] is None
    assert [row["threshold"] for row in tradeoff["rows"]] == [0.4, 0.6]

    for row in tradeoff["rows"]:
        report = json.loads(
            (EVAL_RESULTS / f"{row['benchmark']}.json").read_text(encoding="utf-8")
        )
        scores = report["metrics"]["per_type"]["person_down"]
        for field in (
            "true_positives",
            "false_positives",
            "false_negatives",
            "precision",
            "recall",
            "f1",
        ):
            assert row[field] == scores[field]
        assert row["false_alarms_per_10_minutes"] == pytest.approx(
            report["metrics"]["false_alarms_per_minute"] * 10.0
        )

    markdown = render_markdown(scoreboard)
    assert "## Person-down stored threshold tradeoff" in markdown
    assert "not a validation/holdout calibration" in markdown
    assert "| 0.40 | `fall_events_urfd_5fps_c40` | 23 | 30 | 7 |" in markdown


def test_committed_scoreboard_matches_current_results() -> None:
    scoreboard = build_scoreboard(EVAL_RESULTS)
    committed = (EVAL_RESULTS / "BASELINE_SCOREBOARD.md").read_text(encoding="utf-8")
    assert committed == render_markdown(scoreboard)
