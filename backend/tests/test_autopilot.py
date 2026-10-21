from __future__ import annotations

from pathlib import Path

from scripts.autopilot import orchestrator
from scripts.autopilot.orchestrator import (
    MODEL_CHAINS,
    PATCH_EXCLUDES,
    SPRINTS,
    STATE_PATHS,
    current_task,
    initial_state,
    is_transient_failure,
    parse_decision,
    progress_text,
    record_failure,
    record_success,
    validate_changes,
    validate_decision,
)


def test_write_patch_excludes_autopilot_state(monkeypatch, tmp_path) -> None:
    calls: list[list[str]] = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        return 0, "", False

    monkeypatch.setattr(orchestrator, "run_process", fake_run)
    monkeypatch.setattr(orchestrator, "CANDIDATE_PATCH_PATH", tmp_path / "candidate.patch")
    orchestrator.write_patch()
    diff_calls = [command for command in calls if command[:2] == ["git", "diff"]]
    assert len(diff_calls) == 1
    assert set(PATCH_EXCLUDES) <= set(diff_calls[0])
    assert set(STATE_PATHS) == {".autopilot/state.json", ".autopilot/PROGRESS.md"}


def test_workflow_packages_hidden_autopilot_artifact() -> None:
    root = Path(__file__).resolve().parents[2]
    workflow = root / ".github" / "workflows" / "autopilot.yml"
    text = workflow.read_text(encoding="utf-8")
    assert text.count("name: autopilot-${{ github.run_id }}") == 2
    assert "path: .autopilot/" in text
    assert "include-hidden-files: true" in text
    assert "if-no-files-found: error" in text
    assert ".autopilot/state.json" in text
    assert ".autopilot/outcome.json" in text


def test_workflow_fails_fast_on_clean_environment() -> None:
    root = Path(__file__).resolve().parents[2]
    workflow = root / ".github" / "workflows" / "autopilot.yml"
    text = workflow.read_text(encoding="utf-8")
    assert "Validate repository prerequisites" in text
    assert "python -m pip check" in text
    assert "python -m pytest --collect-only -q" in text
    pyproject = (root / "backend" / "pyproject.toml").read_text(encoding="utf-8")
    assert "email-validator>=2.0.0" in pyproject


def test_model_chains_cover_four_roles_with_fallbacks() -> None:
    assert set(MODEL_CHAINS) == {
        "autopilot-implementer",
        "autopilot-evaluator",
        "autopilot-guardian",
        "autopilot-supervisor",
    }
    assert {chain[0] for chain in MODEL_CHAINS.values()} == {
        "opencode/deepseek-v4.1-flash-free",
        "opencode/glm-5.3-flash-free",
        "opencode/longcat-2.5-preview-free",
        "opencode/minimax-m3.1-flash-free",
    }
    assert all(len(chain) >= 2 for chain in MODEL_CHAINS.values())


def test_sprint_queue_is_ordered_and_unique() -> None:
    assert len(SPRINTS) >= 8
    task_ids = [task["id"] for sprint in SPRINTS for task in sprint["tasks"]]
    assert len(task_ids) == len(set(task_ids))
    assert all(sprint["tasks"] for sprint in SPRINTS)
    assert SPRINTS[0]["id"] == "sprint-1"
    assert SPRINTS[-1]["id"] == "sprint-8"


def test_initial_state_points_at_first_task() -> None:
    state = initial_state()
    assert state["status"] == "running"
    assert state["completed"] == []
    assert state["current"]["task_id"] == "sprint-1.1"
    assert state["current"]["task_index"] == 0


def test_success_advances_to_next_task() -> None:
    state = initial_state()
    record_success(state, "ok")
    assert state["completed"] == ["sprint-1.1"]
    assert state["current"]["task_id"] == "sprint-1.2"
    assert state["attempts"] == 0


def test_failure_retries_then_blocks_and_advances() -> None:
    state = initial_state()
    record_failure(state, "blocked", "first failure")
    assert state["attempts"] == 1
    assert current_task(state)["task_id"] == "sprint-1.1"
    record_failure(state, "blocked", "second failure")
    assert state["attempts"] == 0
    assert state["blocked"][0]["task"] == "sprint-1.1"
    assert current_task(state)["task_id"] == "sprint-1.2"


def test_progress_text_contains_sprint_and_current_task() -> None:
    text = progress_text(initial_state())
    assert "# Autopilot progress" in text
    assert "sprint-1.1" not in text
    assert "Benchmark and holdout baseline" in text
    assert "current" in text


def test_transient_failure_detects_limits_and_timeouts() -> None:
    assert is_transient_failure("429 Too Many Requests")
    assert is_transient_failure("provider quota exceeded")
    assert is_transient_failure("model overloaded, try again")
    assert is_transient_failure("request timed out")
    assert not is_transient_failure("assertion failed in test_person_down")


def test_validate_changes_accepts_small_rule_change() -> None:
    entries = [
        (" M", "backend/workers/cv_worker/rules/person_down.py"),
        ("??", "backend/tests/test_person_down.py"),
    ]
    assert validate_changes(entries, "", 20) == []


def test_validate_changes_ignores_autopilot_state_files() -> None:
    entries = [
        (" M", ".autopilot/state.json"),
        (" M", ".autopilot/PROGRESS.md"),
        (" M", "backend/workers/cv_worker/rules/person_down.py"),
    ]
    assert validate_changes(entries, "", 5) == []


def test_validate_changes_rejects_forbidden_file() -> None:
    entries = [(" M", "backend/pyproject.toml")]
    errors = validate_changes(entries, "", 2)
    assert any("forbidden file" in error for error in errors)


def test_validate_changes_rejects_unrelated_path() -> None:
    entries = [(" M", "frontend/src/app/page.tsx")]
    errors = validate_changes(entries, "", 2)
    assert any("forbidden path" in error for error in errors)


def test_validate_changes_rejects_deleted_test() -> None:
    entries = [("D ", "backend/tests/test_person_down.py")]
    errors = validate_changes(entries, "", 2)
    assert any("test file deleted" in error for error in errors)


def test_validate_changes_rejects_oversized_diff() -> None:
    entries = [(" M", "backend/workers/cv_worker/rules/person_down.py")]
    errors = validate_changes(entries, "", 401)
    assert any("diff too large" in error for error in errors)


def test_validate_decision_accepts_valid_payload() -> None:
    decision = {
        "decision": "approve",
        "target_rule": "person_down",
        "confidence": 0.8,
        "summary": "tighten pose plausibility",
        "commit_message": "autopilot: person_down: tighten pose plausibility",
        "pr_body": "tests and eval evidence",
        "risks": "limited clips",
    }
    assert validate_decision(decision) == []


def test_validate_decision_accepts_all_rule_for_benchmark_tasks() -> None:
    decision = {
        "decision": "approve",
        "target_rule": "all",
        "confidence": 0.8,
        "summary": "benchmark manifest",
        "commit_message": "autopilot: benchmark manifest",
        "pr_body": "tests",
        "risks": "clips missing",
    }
    assert validate_decision(decision) == []


def test_validate_decision_rejects_bad_rule_and_confidence() -> None:
    decision = {
        "decision": "approve",
        "target_rule": "unknown",
        "confidence": 2,
        "summary": "",
        "commit_message": "",
        "pr_body": "",
        "risks": "",
    }
    errors = validate_decision(decision)
    assert any("target_rule" in error for error in errors)
    assert any("confidence" in error for error in errors)
    assert any("summary" in error for error in errors)


def test_parse_decision_handles_invalid_json() -> None:
    assert parse_decision("{not json") is None
    assert parse_decision("[]") is None
    assert parse_decision('{"decision": "reject"}') == {"decision": "reject"}


def test_parse_decision_extracts_fenced_json() -> None:
    raw = 'Here is the decision:\n```json\n{"decision": "approve"}\n```\n'
    assert parse_decision(raw) == {"decision": "approve"}
