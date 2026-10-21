"""Calibration must tune on validation and never look at holdout labels."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.eval.calibrate import calibrate_threshold
from scripts.eval.scoreboard import build_scoreboard
from workers.cv_worker.rules.config import PersonDownConfig

BACKEND = Path(__file__).resolve().parents[1]
EVAL_RESULTS = BACKEND / "eval_results"


def _clip(name: str, events: list[tuple[float, float]]) -> dict:
    return {
        "clip": name,
        "duration": 10.0,
        "events": [
            {"type": "person_down", "start": start, "end": end}
            for start, end in events
        ],
    }


def _write(path: Path, clips: list[dict]) -> Path:
    path.write_text(
        "\n".join(json.dumps(clip) for clip in clips) + "\n", encoding="utf-8"
    )
    return path


def _calibrate(
    *,
    validation_gt: Path,
    validation_predictions: dict[float, Path],
    holdout_gt: Path,
    holdout_predictions: dict[float, Path],
) -> dict:
    return calibrate_threshold(
        event_type="person_down",
        validation_gt=validation_gt,
        validation_predictions=validation_predictions,
        holdout_gt=holdout_gt,
        holdout_predictions=holdout_predictions,
    )


def test_selects_on_validation_and_never_reads_losing_holdout_file(
    tmp_path: Path,
) -> None:
    validation_gt = _write(tmp_path / "val_gt.jsonl", [_clip("v1", [(0.0, 10.0)])])
    holdout_gt = _write(tmp_path / "holdout_gt.jsonl", [_clip("h1", [(5.0, 15.0)])])
    # Validation prefers 0.60 (F1 1.0 over 0.67). Holdout would prefer 0.40,
    # but its file is deliberately absent: reading it would fail the test.
    permissive_val = _write(
        tmp_path / "val_c40.jsonl", [_clip("v1", [(0.0, 10.0), (20.0, 21.0)])]
    )
    strict_val = _write(tmp_path / "val_c60.jsonl", [_clip("v1", [(0.0, 10.0)])])
    strict_holdout = _write(tmp_path / "holdout_c60.jsonl", [_clip("h1", [])])

    report = _calibrate(
        validation_gt=validation_gt,
        validation_predictions={0.4: permissive_val, 0.6: strict_val},
        holdout_gt=holdout_gt,
        holdout_predictions={0.4: tmp_path / "missing_c40.jsonl", 0.6: strict_holdout},
    )

    assert report["selected_threshold"] == 0.6
    assert report["validation"]["selected"]["f1"] == 1.0
    assert report["holdout"]["threshold"] == 0.6
    assert report["holdout"]["f1"] == 0.0


def test_tie_breaks_toward_the_higher_threshold(tmp_path: Path) -> None:
    validation_gt = _write(
        tmp_path / "val_gt.jsonl", [_clip("a", [(0.0, 5.0)])]
    )
    holdout_gt = _write(
        tmp_path / "holdout_gt.jsonl", [_clip("b", [(0.0, 5.0)])]
    )
    equal = _write(tmp_path / "equal.jsonl", [_clip("a", [(0.0, 5.0)])])
    equal_holdout = _write(
        tmp_path / "equal_holdout.jsonl", [_clip("b", [(0.0, 5.0)])]
    )

    report = _calibrate(
        validation_gt=validation_gt,
        validation_predictions={0.4: equal, 0.6: equal},
        holdout_gt=holdout_gt,
        holdout_predictions={0.4: equal_holdout, 0.6: equal_holdout},
    )

    assert report["selected_threshold"] == 0.6


def test_overlapping_validation_and_holdout_clips_are_rejected(
    tmp_path: Path,
) -> None:
    gt = _write(tmp_path / "gt.jsonl", [_clip("shared", [(0.0, 5.0)])])

    with pytest.raises(ValueError, match="overlap"):
        _calibrate(
            validation_gt=gt,
            validation_predictions={0.6: gt},
            holdout_gt=gt,
            holdout_predictions={0.6: gt},
        )


def test_empty_validation_grid_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="validation threshold"):
        _calibrate(
            validation_gt=tmp_path / "unused_gt.jsonl",
            validation_predictions={},
            holdout_gt=tmp_path / "unused_holdout.jsonl",
            holdout_predictions={},
        )


def test_committed_calibration_report_is_explicit_and_matches_defaults() -> None:
    report = json.loads(
        (EVAL_RESULTS / "person_down_calibration.json").read_text(encoding="utf-8")
    )

    assert report["status"] == "not_run"
    assert report["selected_threshold"] is None
    assert report["validation"] is None
    assert report["holdout"] is None
    assert "weights" in report["reason"]
    config = PersonDownConfig()
    assert report["current_thresholds"] == {
        field: getattr(config, field) for field in report["current_thresholds"]
    }

    notes = build_scoreboard(EVAL_RESULTS)["notes"]
    assert any("calibration status: not_run" in note for note in notes)
    assert any("calibration reason:" in note for note in notes)
