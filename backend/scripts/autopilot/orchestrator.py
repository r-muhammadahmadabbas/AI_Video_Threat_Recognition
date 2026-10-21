"""Run the continuous multi-agent autopilot and promote safe changes."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / "backend"
AUTOPILOT_DIR = REPO_ROOT / ".autopilot"
STATE_PATH = AUTOPILOT_DIR / "state.json"
PROGRESS_PATH = AUTOPILOT_DIR / "PROGRESS.md"
OUTCOME_PATH = AUTOPILOT_DIR / "outcome.json"
CANDIDATE_PATCH_PATH = AUTOPILOT_DIR / "candidate.patch"
STATE_PATHS = {".autopilot/state.json", ".autopilot/PROGRESS.md"}
PATCH_EXCLUDES = tuple(f":(exclude){path}" for path in STATE_PATHS)
RUN_ID = os.environ.get("GITHUB_RUN_ID", "local")
TODAY = datetime.now(UTC).strftime("%Y-%m-%d")
BRANCH = os.environ.get("AUTOPILOT_BRANCH") or f"autopilot/{TODAY}-{RUN_ID}"

PRIORITY = (
    "person_down",
    "fight",
    "loitering",
    "crowd_anomaly",
    "weapon",
    "zone_entry",
)
TARGET_RULES = ("all", *PRIORITY)

MODEL_CHAINS: dict[str, tuple[str, ...]] = {
    "autopilot-supervisor": (
        "opencode/minimax-m3.1-flash-free",
        "opencode/glm-5.3-flash-free",
        "opencode/deepseek-v4.1-flash-free",
    ),
    "autopilot-implementer": (
        "opencode/deepseek-v4.1-flash-free",
        "opencode/minimax-m3.1-flash-free",
        "opencode/glm-5.3-flash-free",
    ),
    "autopilot-evaluator": (
        "opencode/glm-5.3-flash-free",
        "opencode/deepseek-v4.1-flash-free",
        "opencode/minimax-m3.1-flash-free",
    ),
    "autopilot-guardian": (
        "opencode/longcat-2.5-preview-free",
        "opencode/glm-5.3-flash-free",
        "opencode/minimax-m3.1-flash-free",
    ),
}

SPRINTS: tuple[dict[str, Any], ...] = (
    {
        "id": "sprint-1",
        "name": "Benchmark and holdout baseline",
        "rule": "all",
        "tasks": (
            {
                "id": "sprint-1.1",
                "title": "Define benchmark manifest and holdout split",
                "goal": (
                    "Create or extend a benchmark manifest under backend/scripts/eval/ "
                    "that lists clips, labels, and dev/validation/holdout splits for every "
                    "rule. If clips are missing, record the expected path and missing status; "
                    "do not invent clips or metrics."
                ),
                "exit": "Manifest schema, loader, tests, and no fabricated data.",
            },
            {
                "id": "sprint-1.2",
                "title": "Record baseline metrics from existing results",
                "goal": (
                    "Read backend/eval_results/ and the offline harness, then record a "
                    "scoreboard with precision, recall, F1, false alarms per 10 minutes, and "
                    "latency where available. Use null plus a reason for missing metrics."
                ),
                "exit": "Baseline scoreboard committed with explicit missing values.",
            },
            {
                "id": "sprint-1.3",
                "title": "Add missing-data regression coverage",
                "goal": (
                    "Add tests that prove the benchmark and scoreboard do not silently turn "
                    "missing clips or labels into perfect metrics."
                ),
                "exit": "Regression tests fail on fabricated or absent metrics.",
            },
        ),
    },
    {
        "id": "sprint-2",
        "name": "Person-down accuracy",
        "rule": "person_down",
        "tasks": (
            {
                "id": "sprint-2.1",
                "title": "Strengthen person-down temporal evidence",
                "goal": (
                    "Improve person-down precision or recall using track persistence, pose "
                    "plausibility, and hard negatives such as crouching, sitting, bending, and "
                    "shooting stance. Keep the change small and test-backed."
                ),
                "exit": "Targeted tests and a measured before/after result or explicit null.",
            },
            {
                "id": "sprint-2.2",
                "title": "Calibrate person-down thresholds",
                "goal": (
                    "Calibrate only on the validation split, then report validation and holdout "
                    "metrics. Do not tune on the test or holdout labels."
                ),
                "exit": "Calibration evidence, no regression, and updated baseline.",
            },
        ),
    },
    {
        "id": "sprint-3",
        "name": "Fight false-alarm reduction",
        "rule": "fight",
        "tasks": (
            {
                "id": "sprint-3.1",
                "title": "Reduce fight false alarms on normal motion",
                "goal": (
                    "Improve fight event precision by suppressing normal fast motion, crowd "
                    "movement, hugging, and camera shake without losing true positive events."
                ),
                "exit": "Targeted tests and false-alarm evidence.",
            },
            {
                "id": "sprint-3.2",
                "title": "Improve fight temporal fusion",
                "goal": (
                    "Use temporal persistence and score smoothing to improve fight precision "
                    "or recall, then calibrate on validation data."
                ),
                "exit": "Before/after metrics and updated baseline.",
            },
        ),
    },
    {
        "id": "sprint-4",
        "name": "Fall accuracy",
        "rule": "person_down",
        "tasks": (
            {
                "id": "sprint-4.1",
                "title": "Improve fall recall without adding false alarms",
                "goal": (
                    "Improve fall event recall with event smoothing and pose evidence, while "
                    "rejecting sitting, kneeling, and crouching negatives."
                ),
                "exit": "Measured recall improvement and no precision regression.",
            },
            {
                "id": "sprint-4.2",
                "title": "Calibrate fall confidence",
                "goal": (
                    "Calibrate the fall threshold on validation data and report the fall "
                    "precision/recall tradeoff on holdout."
                ),
                "exit": "Calibration table and updated baseline.",
            },
        ),
    },
    {
        "id": "sprint-5",
        "name": "Loitering and crowd accuracy",
        "rule": "loitering",
        "tasks": (
            {
                "id": "sprint-5.1",
                "title": "Improve loitering trajectory evidence",
                "goal": (
                    "Improve loitering precision or recall using dwell time, track continuity, "
                    "and stationary-object rejection."
                ),
                "exit": "Targeted tests and event metrics.",
            },
            {
                "id": "sprint-5.2",
                "title": "Improve crowd anomaly baseline",
                "goal": (
                    "Improve crowd anomaly detection using per-zone density and motion baselines "
                    "instead of raw person count."
                ),
                "exit": "Targeted tests and event metrics.",
            },
        ),
    },
    {
        "id": "sprint-6",
        "name": "Weapon accuracy",
        "rule": "weapon",
        "tasks": (
            {
                "id": "sprint-6.1",
                "title": "Improve weapon temporal evidence",
                "goal": (
                    "Reduce weapon false positives with temporal voting, person-weapon "
                    "association, and hard negatives such as phones, tools, and holsters."
                ),
                "exit": "Targeted tests and event metrics.",
            },
            {
                "id": "sprint-6.2",
                "title": "Calibrate weapon threshold",
                "goal": (
                    "Calibrate the weapon event threshold on validation data without using the "
                    "holdout split for tuning."
                ),
                "exit": "Calibration evidence and updated baseline.",
            },
        ),
    },
    {
        "id": "sprint-7",
        "name": "Zone and live evaluation",
        "rule": "zone_entry",
        "tasks": (
            {
                "id": "sprint-7.1",
                "title": "Add live zone-entry evaluation",
                "goal": (
                    "Cover the live camera path for zone entry, including polygon geometry, "
                    "entry direction, and event matching."
                ),
                "exit": "Live-path evaluation and regression tests.",
            },
            {
                "id": "sprint-7.2",
                "title": "Close zone-entry accuracy gaps",
                "goal": (
                    "Fix the largest measured zone-entry accuracy gap without touching live "
                    "camera configuration or frontend code."
                ),
                "exit": "Measured improvement and no test regression.",
            },
        ),
    },
    {
        "id": "sprint-8",
        "name": "Regression and final report",
        "rule": "all",
        "tasks": (
            {
                "id": "sprint-8.1",
                "title": "Run the full accuracy regression",
                "goal": (
                    "Run every available benchmark, fix regressions inside the allowed surface, "
                    "and update the scoreboard with real numbers."
                ),
                "exit": "Full regression result with no unexplained regression.",
            },
            {
                "id": "sprint-8.2",
                "title": "Write the final accuracy report and next backlog",
                "goal": (
                    "Write a concise report covering what improved, what is still blocked, the "
                    "exact evidence, and the next three experiments."
                ),
                "exit": "Report committed with a prioritized backlog.",
            },
        ),
    },
)

ALLOWED_PREFIXES = (
    "backend/workers/cv_worker/",
    "backend/tests/",
    "backend/scripts/eval/",
    "backend/app/detection/",
    "backend/eval_results/",
)

FORBIDDEN_PREFIXES = (
    ".github/",
    ".opencode/",
    "frontend/",
    "backend/alembic/",
    "backend/models/",
    "backend/data/",
    "backend/media/",
)

FORBIDDEN_FILES = (
    "opencode.json",
    "AUTOPILOT.md",
    "backend/pyproject.toml",
    "backend/uv.lock",
    "backend/requirements.txt",
)

BINARY_SUFFIXES = (
    ".pt",
    ".onnx",
    ".engine",
    ".mp4",
    ".avi",
    ".mov",
    ".mkv",
    ".jpg",
    ".jpeg",
    ".png",
    ".zip",
    ".tar",
    ".gz",
)

TRANSIENT_RE = re.compile(
    r"(rate.?limit|429|too many requests|quota|usage limit|insufficient|billing|"
    r"overloaded|temporarily unavailable|capacity|model.{0,20}not found|"
    r"unauthorized|401|timed? ?out)",
    re.IGNORECASE,
)

MAX_CHANGED_FILES = 6
MAX_DIFF_LINES = 400
MAX_TASK_ATTEMPTS = 2
AGENT_TIMEOUT_SECONDS = 1800
REVIEW_TIMEOUT_SECONDS = 900

LOGGER = logging.getLogger("autopilot")


def configure_logging() -> None:
    AUTOPILOT_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(AUTOPILOT_DIR / "orchestrator.log", encoding="utf-8"),
        ],
    )


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def total_tasks() -> int:
    return sum(len(sprint["tasks"]) for sprint in SPRINTS)


def task_key(sprint_index: int, task_index: int) -> str:
    task = SPRINTS[sprint_index]["tasks"][task_index]
    return str(task["id"])


def current_task(state: dict[str, Any]) -> dict[str, Any] | None:
    sprint_index = int(state["sprint_index"])
    task_index = int(state["task_index"])
    if sprint_index >= len(SPRINTS):
        return None
    sprint = SPRINTS[sprint_index]
    if task_index >= len(sprint["tasks"]):
        return None
    task = sprint["tasks"][task_index]
    return {
        "sprint_index": sprint_index,
        "task_index": task_index,
        "sprint_id": sprint["id"],
        "sprint_name": sprint["name"],
        "rule": sprint["rule"],
        "task_id": task["id"],
        "task_title": task["title"],
        "goal": task["goal"],
        "exit": task["exit"],
    }


def initial_state() -> dict[str, Any]:
    now = utc_now()
    state: dict[str, Any] = {
        "version": 1,
        "status": "running",
        "created_at": now,
        "updated_at": now,
        "sprint_index": 0,
        "task_index": 0,
        "attempts": 0,
        "completed": [],
        "blocked": [],
        "last_result": None,
        "last_gates": None,
        "metrics": {},
        "runs": 0,
        "current": None,
    }
    state["current"] = current_task(state)
    return state


def load_state() -> dict[str, Any]:
    if not STATE_PATH.is_file():
        return initial_state()
    try:
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        LOGGER.warning("state file is unreadable; starting a fresh state")
        return initial_state()
    if not isinstance(state, dict) or state.get("version") != 1:
        LOGGER.warning("state file has an unsupported shape; starting fresh")
        return initial_state()
    defaults = initial_state()
    for key, value in defaults.items():
        state.setdefault(key, value)
    return state


def progress_text(state: dict[str, Any]) -> str:
    completed = set(state.get("completed", []))
    blocked = {item.get("task"): item.get("reason", "") for item in state.get("blocked", [])}
    current = state.get("current")
    current_id = current.get("task_id") if isinstance(current, dict) else None
    lines = [
        "# Autopilot progress",
        "",
        f"- Updated: {state.get('updated_at', 'unknown')}",
        f"- Status: {state.get('status', 'unknown')}",
        (
            f"- Progress: {len(completed)}/{total_tasks()} tasks, "
            f"{len(blocked)} blocked, {state.get('runs', 0)} runs"
        ),
    ]
    if current:
        lines.append(
            f"- Current: Sprint {current['sprint_index'] + 1}/{len(SPRINTS)} "
            f"({current['sprint_name']}) / Task {current['task_index'] + 1} "
            f"({current['task_title']})"
        )
    else:
        lines.append("- Current: none")
    last = state.get("last_result")
    if last:
        lines.append(f"- Last result: {last.get('status')}: {last.get('reason')}")
    lines.extend(["", "## Sprint board", "", "| Sprint | Task | Status |", "| --- | --- | --- |"])
    for sprint in SPRINTS:
        for task in sprint["tasks"]:
            task_id = str(task["id"])
            if task_id in completed:
                status = "done"
            elif task_id in blocked:
                status = f"blocked: {blocked[task_id]}"
            elif task_id == current_id:
                status = "current"
            else:
                status = "pending"
            lines.append(f"| {sprint['name']} | {task['title']} | {status} |")
    metrics = state.get("metrics") or {}
    if metrics:
        lines.extend(["", "## Metrics", "", "```json", json.dumps(metrics, indent=2), "```"])
    return "\n".join(lines) + "\n"


def save_state(state: dict[str, Any]) -> None:
    state["updated_at"] = utc_now()
    state["current"] = current_task(state)
    if state["sprint_index"] >= len(SPRINTS):
        state["status"] = "complete"
    write_text(STATE_PATH, json.dumps(state, indent=2) + "\n")
    write_text(PROGRESS_PATH, progress_text(state))


def advance_index(state: dict[str, Any]) -> None:
    state["task_index"] = int(state["task_index"]) + 1
    if state["task_index"] >= len(SPRINTS[state["sprint_index"]]["tasks"]):
        state["sprint_index"] = int(state["sprint_index"]) + 1
        state["task_index"] = 0
    state["attempts"] = 0
    if state["sprint_index"] >= len(SPRINTS):
        state["status"] = "complete"
    state["current"] = current_task(state)


def record_success(state: dict[str, Any], reason: str) -> None:
    task = current_task(state)
    if task is None:
        state["status"] = "complete"
        return
    if task["task_id"] not in state["completed"]:
        state["completed"].append(task["task_id"])
    state["last_result"] = {"status": "approved", "task": task["task_id"], "reason": reason}
    advance_index(state)


def record_failure(state: dict[str, Any], status: str, reason: str) -> None:
    task = current_task(state)
    if task is None:
        state["status"] = "complete"
        return
    state["attempts"] = int(state.get("attempts", 0)) + 1
    state["last_result"] = {"status": status, "task": task["task_id"], "reason": reason}
    if state["attempts"] >= MAX_TASK_ATTEMPTS:
        state["blocked"].append(
            {"task": task["task_id"], "reason": reason, "at": utc_now()}
        )
        advance_index(state)


def run_process(
    command: list[str],
    *,
    cwd: Path = REPO_ROOT,
    env: dict[str, str] | None = None,
    timeout: int | None = None,
) -> tuple[int, str, bool]:
    try:
        completed = subprocess.run(  # noqa: S603
            command,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        output = _text(exc.stdout) + _text(exc.stderr)
        return 124, output, True
    return completed.returncode, (completed.stdout or "") + (completed.stderr or ""), False


def _text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def is_transient_failure(output: str) -> bool:
    return bool(TRANSIENT_RE.search(output[-6000:]))


def redact(text: str) -> str:
    for name in ("GH_TOKEN", "GITHUB_TOKEN"):
        token = os.environ.get(name)
        if token:
            text = text.replace(token, "***")
    return text


def agent_slug(model: str) -> str:
    return model.replace("/", "_").replace(":", "_")


def agent_env() -> dict[str, str]:
    env = os.environ.copy()
    for name in (
        "GITHUB_TOKEN",
        "GH_TOKEN",
        "OPENCODE_API_KEY",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
    ):
        env.pop(name, None)
    env["NO_COLOR"] = "1"
    return env


def run_agent(agent: str, prompt: str, timeout: int) -> bool:
    for model in MODEL_CHAINS[agent]:
        LOGGER.info("%s: trying %s", agent, model)
        command = [
            "opencode",
            "run",
            "--agent",
            agent,
            "--model",
            model,
            "--auto",
            "--format",
            "json",
            "--print-logs",
            "--title",
            f"autopilot {agent}",
            prompt,
        ]
        code, output, timed_out = run_process(command, env=agent_env(), timeout=timeout)
        transcript = AUTOPILOT_DIR / f"{agent}.{agent_slug(model)}.log"
        write_text(transcript, output)
        if code == 0 and not timed_out and not is_transient_failure(output):
            LOGGER.info("%s: completed with %s", agent, model)
            return True
        LOGGER.warning(
            "%s: %s failed (code=%s timeout=%s); trying next model",
            agent,
            model,
            code,
            timed_out,
        )
    LOGGER.error("%s: all models failed", agent)
    return False


def status_entries() -> list[tuple[str, str]]:
    code, output, _ = run_process(["git", "status", "--porcelain"])
    if code != 0:
        return []
    entries: list[tuple[str, str]] = []
    for line in output.splitlines():
        if len(line) < 4:
            continue
        state = line[:2]
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", maxsplit=1)[1]
        entries.append((state, path.replace("\\", "/")))
    return entries


def changed_paths(*, include_state: bool = False) -> list[str]:
    paths = [path for _, path in status_entries()]
    if include_state:
        return paths
    return [path for path in paths if path not in STATE_PATHS]


def untracked_files() -> list[str]:
    code, output, _ = run_process(["git", "ls-files", "--others", "--exclude-standard"])
    if code != 0:
        return []
    return [line.strip().replace("\\", "/") for line in output.splitlines() if line.strip()]


def diff_text() -> str:
    _, output, _ = run_process(["git", "diff"])
    return output


def diff_line_count() -> int:
    _, output, _ = run_process(["git", "diff", "--numstat"])
    total = 0
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) < 3 or parts[2].replace("\\", "/") in STATE_PATHS:
            continue
        for value in parts[:2]:
            if value.isdigit():
                total += int(value)
    for path in untracked_files():
        if path in STATE_PATHS:
            continue
        file_path = REPO_ROOT / path
        if file_path.is_file():
            total += len(file_path.read_text(encoding="utf-8", errors="replace").splitlines())
    return total


def validate_changes(
    entries: list[tuple[str, str]],
    diff: str,
    total_lines: int,
) -> list[str]:
    entries = [(state, path) for state, path in entries if path not in STATE_PATHS]
    errors: list[str] = []
    paths = [path for _, path in entries]
    if not paths:
        return ["no changes were made"]
    if len(paths) > MAX_CHANGED_FILES:
        errors.append(f"too many changed files: {len(paths)} > {MAX_CHANGED_FILES}")
    if total_lines > MAX_DIFF_LINES:
        errors.append(f"diff too large: {total_lines} > {MAX_DIFF_LINES} lines")
    errors.extend(_path_errors(entries))
    if "deleted file mode" in diff and any(path.startswith("backend/tests/") for path in paths):
        errors.append("a test file was deleted")
    return errors


def _path_errors(entries: list[tuple[str, str]]) -> list[str]:
    errors: list[str] = []
    for state, path in entries:
        if path in FORBIDDEN_FILES:
            errors.append(f"forbidden file changed: {path}")
            continue
        if any(path.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
            errors.append(f"forbidden path changed: {path}")
            continue
        if any(path.endswith(suffix) for suffix in BINARY_SUFFIXES):
            errors.append(f"binary or media file changed: {path}")
            continue
        if not any(path.startswith(prefix) for prefix in ALLOWED_PREFIXES):
            errors.append(f"path outside the allowed accuracy surface: {path}")
        if state.startswith("D") and path.startswith("backend/tests/"):
            errors.append(f"test file deleted: {path}")
    return errors


def write_gates() -> dict[str, Any]:
    entries = [(state, path) for state, path in status_entries() if path not in STATE_PATHS]
    paths = [path for _, path in entries]
    diff = diff_text()
    line_count = diff_line_count()
    policy_errors = validate_changes(entries, diff, line_count)
    tests_code, tests_output, tests_timeout = run_process(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=BACKEND_DIR,
        timeout=AGENT_TIMEOUT_SECONDS,
    )
    python_files = [path for path in paths if path.endswith(".py")]
    if python_files:
        ruff_code, ruff_output, ruff_timeout = run_process(
            [sys.executable, "-m", "ruff", "check", *python_files],
            timeout=REVIEW_TIMEOUT_SECONDS,
        )
    else:
        ruff_code, ruff_output, ruff_timeout = 0, "no Python files changed", False
    gates = {
        "tests_ok": tests_code == 0 and not tests_timeout,
        "ruff_ok": ruff_code == 0 and not ruff_timeout,
        "policy_errors": policy_errors,
        "changed_files": paths,
        "diff_lines": line_count,
        "tests_output_tail": tests_output[-4000:],
        "ruff_output_tail": ruff_output[-4000:],
    }
    write_text(AUTOPILOT_DIR / "gates.json", json.dumps(gates, indent=2))
    return gates


def prompt_header(task: dict[str, Any], state: dict[str, Any]) -> str:
    assets = "present" if (BACKEND_DIR / "models").is_dir() else "missing"
    return f"""Autopilot for the CV threat-recognition repository.
Date: {TODAY}
Branch: {BRANCH}
Sprint {task["sprint_index"] + 1}/{len(SPRINTS)}: {task["sprint_name"]}
Task {task["task_index"] + 1}: {task["task_title"]}
Rule: {task["rule"]}
Goal: {task["goal"]}
Exit criteria: {task["exit"]}
Completed tasks: {len(state["completed"])}/{total_tasks()}
Blocked tasks: {len(state["blocked"])}
Model weights under backend/models: {assets}

Read AUTOPILOT.md before acting. Work only on this task. Keep the change small,
test-backed, and inside the allowed accuracy surface. Never edit dependencies,
schema or migrations, auth, frontend, model weights, datasets, CI workflows,
OpenCode config, or AUTOPILOT.md.
"""


def implementer_prompt(task: dict[str, Any], state: dict[str, Any]) -> str:
    return (
        prompt_header(task, state)
        + """
You are the implementer for this task only. Inspect the current diff first. If
a previous attempt left changes, continue them. Make the smallest correct
change that satisfies the task's exit criteria. Add or update a targeted
regression test. Run targeted tests and ruff. Do not commit or push. Write your
report to .autopilot/implementer.md.

If the task needs clips, labels, or weights that are absent, do correctness or
test work only and say explicitly that accuracy was not measured. Never invent
metrics or labels.
"""
    )


def repair_prompt(
    task: dict[str, Any],
    state: dict[str, Any],
    gates: dict[str, Any],
) -> str:
    return (
        prompt_header(task, state)
        + """
The deterministic gates failed after your first attempt. Fix only the failures
below, keep the same task and scope, and do not weaken tests. Re-run the
targeted tests and ruff. Update .autopilot/implementer.md.

Test output tail:
"""
        + gates["tests_output_tail"]
        + "\n\nRuff output tail:\n"
        + gates["ruff_output_tail"]
        + "\n\nPolicy errors:\n"
        + "\n".join(gates["policy_errors"])
    )


def evaluator_prompt(task: dict[str, Any], state: dict[str, Any]) -> str:
    return (
        prompt_header(task, state)
        + """
You are the evaluator. Do not edit production code. Run the full backend test
suite and ruff on changed Python files. Run the task's benchmark if model
weights and labelled clips are present, and compare with backend/eval_results/.
Be adversarial about weakened tests, data leakage, and unsupported accuracy
claims. Write your report to .autopilot/evaluator.md.
"""
    )


def guardian_prompt(task: dict[str, Any], state: dict[str, Any]) -> str:
    return (
        prompt_header(task, state)
        + """
You are the guardian. Review the diff, the implementer report, and the evaluator
report against AUTOPILOT.md. Reject any policy, scope, test, evidence,
holdout-leakage, or forbidden-path violation. Write .autopilot/guardian.md with
APPROVE or REJECT and specific reasons.
"""
    )


def supervisor_prompt(
    task: dict[str, Any],
    state: dict[str, Any],
    gates: dict[str, Any],
) -> str:
    return (
        prompt_header(task, state)
        + """
You are the supervisor. You make the final decision for this task. Read
.autopilot/gates.json, the implementer, evaluator, and guardian reports, and the
diff.

Deterministic gate summary:
"""
        + json.dumps(gates, indent=2)
        + """

Approve only if the deterministic gates pass, the guardian approves, the
evaluator found no regression or unsupported claim, and the change satisfies the
task exit criteria. If assets were missing, approve correctness or test work
only and state that accuracy was not measured.

Write .autopilot/decision.json exactly in the requested shape. Do not commit or
push. The trusted promote step is the only process that can commit.
"""
    )


def parse_decision(raw: str) -> dict[str, Any] | None:
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def validate_decision(data: dict[str, Any] | None) -> list[str]:
    if data is None:
        return ["decision is not valid JSON"]
    errors: list[str] = []
    if data.get("decision") not in {"approve", "reject"}:
        errors.append("decision must be approve or reject")
    if data.get("target_rule") not in TARGET_RULES:
        errors.append("target_rule is missing or not a valid rule")
    confidence = data.get("confidence")
    if not isinstance(confidence, int | float) or not 0 <= float(confidence) <= 1:
        errors.append("confidence must be a number between 0 and 1")
    errors.extend(
        f"{key} must be a non-empty string"
        for key in ("summary", "commit_message", "pr_body", "risks")
        if not isinstance(data.get(key), str) or not data[key].strip()
    )
    return errors


def run_supervisor(
    task: dict[str, Any],
    state: dict[str, Any],
    gates: dict[str, Any],
) -> dict[str, Any] | None:
    decision_path = AUTOPILOT_DIR / "decision.json"
    prompt = supervisor_prompt(task, state, gates)
    for model in MODEL_CHAINS["autopilot-supervisor"]:
        decision_path.unlink(missing_ok=True)
        LOGGER.info("supervisor: trying %s", model)
        command = [
            "opencode",
            "run",
            "--agent",
            "autopilot-supervisor",
            "--model",
            model,
            "--auto",
            "--format",
            "json",
            "--print-logs",
            "--title",
            "autopilot supervisor",
            prompt,
        ]
        code, output, timed_out = run_process(
            command,
            env=agent_env(),
            timeout=REVIEW_TIMEOUT_SECONDS,
        )
        write_text(AUTOPILOT_DIR / f"autopilot-supervisor.{agent_slug(model)}.log", output)
        if code != 0 or timed_out or is_transient_failure(output):
            LOGGER.warning("supervisor: %s failed; trying next model", model)
            continue
        raw = decision_path.read_text(encoding="utf-8") if decision_path.is_file() else ""
        decision = parse_decision(raw)
        errors = validate_decision(decision)
        if not errors:
            return decision
        LOGGER.warning("supervisor: invalid decision from %s: %s", model, errors)
    return None


def reject_decision(reason: str, target_rule: str = "all") -> dict[str, Any]:
    return {
        "decision": "reject",
        "target_rule": target_rule if target_rule in TARGET_RULES else "all",
        "confidence": 0.0,
        "summary": reason,
        "commit_message": "autopilot: rejected",
        "pr_body": reason,
        "risks": "No change was promoted.",
    }


def setup_repo() -> None:
    run_process(["git", "config", "user.name", "opencode-autopilot"])
    run_process(["git", "config", "user.email", "opencode-autopilot@users.noreply.github.com"])
    code, output, _ = run_process(["git", "checkout", "-B", BRANCH])
    if code != 0:
        raise RuntimeError(f"git checkout failed: {output[-2000:]}")
    LOGGER.info("working on %s", BRANCH)


def authenticate_git() -> None:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if token and repo:
        url = f"https://x-access-token:{token}@github.com/{repo}.git"
        run_process(["git", "remote", "set-url", "origin", url])


def has_committed_changes(base: str) -> bool:
    code, output, _ = run_process(["git", "rev-list", "--count", f"{base}..HEAD"])
    return code == 0 and output.strip() not in {"", "0"}


def create_issue(title: str, body: str) -> None:
    if not (os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")):
        LOGGER.warning("no GitHub token available; skipping issue creation")
        return
    code, output, _ = run_process(
        ["gh", "issue", "create", "--title", title, "--body", body[:60000]],
        timeout=120,
    )
    if code == 0:
        LOGGER.info("issue created: %s", output.strip())
    else:
        LOGGER.error("issue creation failed: %s", redact(output[-2000:]))


def write_patch() -> None:
    run_process(["git", "add", "-N", "."])
    _, output, _ = run_process(["git", "diff", "--", ".", *PATCH_EXCLUDES])
    write_text(CANDIDATE_PATCH_PATH, output)


def write_outcome(state: dict[str, Any], kind: str, reason: str) -> None:
    task = current_task(state)
    payload = {
        "kind": kind,
        "task": task["task_id"] if task else None,
        "reason": reason,
        "at": utc_now(),
    }
    write_text(OUTCOME_PATH, json.dumps(payload, indent=2) + "\n")


def create_pull_request(title: str, body: str) -> bool:
    code, output, _ = run_process(["git", "push", "-u", "origin", BRANCH], timeout=180)
    if code != 0:
        LOGGER.error("branch push failed: %s", redact(output[-2000:]))
        return False
    code, output, _ = run_process(
        [
            "gh",
            "pr",
            "create",
            "--base",
            "main",
            "--head",
            BRANCH,
            "--title",
            title,
            "--body",
            body[:60000],
        ],
        timeout=120,
    )
    if code == 0:
        LOGGER.info("pull request created: %s", output.strip())
        merge_code, merge_output, _ = run_process(
            ["gh", "pr", "merge", "--auto", "--squash", "--delete-branch"],
            timeout=120,
        )
        if merge_code != 0:
            LOGGER.warning("auto-merge unavailable: %s", redact(merge_output[-1000:]))
        return True
    LOGGER.error("pull request failed: %s", redact(output[-2000:]))
    return False


def commit_and_promote(  # noqa: PLR0911
    title: str,
    body: str,
    *,
    stage_all: bool = True,
    paths: list[str] | None = None,
) -> bool:
    if stage_all:
        code, output, _ = run_process(["git", "add", "-A"])
    else:
        code, output, _ = run_process(["git", "add", "-f", *(paths or [])])
    if code != 0:
        LOGGER.error("git add failed: %s", redact(output[-2000:]))
        return False
    code, output, _ = run_process(["git", "commit", "-m", title], timeout=120)
    if code != 0:
        if "nothing to commit" in output.lower() or "no changes added" in output.lower():
            return True
        LOGGER.error("git commit failed: %s", redact(output[-2000:]))
        return False

    authenticate_git()
    run_process(["git", "fetch", "origin", "main"], timeout=120)
    rebase_code, rebase_output, _ = run_process(["git", "rebase", "origin/main"], timeout=120)
    if rebase_code != 0:
        run_process(["git", "rebase", "--abort"])
        create_issue(f"Autopilot rebase conflict: {TODAY}", redact(rebase_output[-6000:]))
        return False

    direct = os.environ.get("AUTOPILOT_DIRECT_PUSH", "true").lower() in {"1", "true", "yes"}
    if direct:
        code, output, _ = run_process(["git", "push", "origin", "HEAD:main"], timeout=180)
        if code == 0:
            LOGGER.info("promoted to main: %s", title)
            return True
        LOGGER.warning("main push failed; falling back to pull request: %s", redact(output[-1000:]))

    if create_pull_request(title, body):
        return True
    create_issue(f"Autopilot could not promote: {TODAY}", body)
    return False


def apply_candidate_patch() -> tuple[bool, str]:
    if not CANDIDATE_PATCH_PATH.is_file():
        return False, "candidate patch is missing"
    patch = CANDIDATE_PATCH_PATH.read_text(encoding="utf-8")
    if not patch.strip():
        return False, "candidate patch is empty"
    code, output, _ = run_process(["git", "apply", "--check", str(CANDIDATE_PATCH_PATH)])
    if code != 0:
        return False, f"git apply --check failed: {output[-2000:]}"
    code, output, _ = run_process(["git", "apply", str(CANDIDATE_PATCH_PATH)])
    if code != 0:
        return False, f"git apply failed: {output[-2000:]}"
    return True, "patch applied"


def revert_candidate_patch() -> None:
    if CANDIDATE_PATCH_PATH.is_file():
        code, output, _ = run_process(
            ["git", "apply", "-R", str(CANDIDATE_PATCH_PATH)],
            timeout=120,
        )
        if code != 0:
            LOGGER.warning("could not reverse candidate patch: %s", redact(output[-1000:]))


def commit_state_only(reason: str) -> bool:
    paths = [str(STATE_PATH.relative_to(REPO_ROOT)), str(PROGRESS_PATH.relative_to(REPO_ROOT))]
    existing = [path for path in paths if (REPO_ROOT / path).is_file()]
    if not existing:
        return True
    return commit_and_promote(
        f"autopilot: state update ({reason})",
        f"Autopilot state checkpoint: {reason}",
        stage_all=False,
        paths=existing,
    )


def run_build() -> int:  # noqa: PLR0911, PLR0912
    configure_logging()
    state = load_state()
    if state.get("status") in {"complete", "stopped"}:
        write_outcome(state, "complete", "queue is finished")
        save_state(state)
        return 0
    if os.environ.get("AUTOPILOT_STOP", "").lower() in {"1", "true", "yes"}:
        state["status"] = "stopped"
        save_state(state)
        write_outcome(state, "stopped", "AUTOPILOT_STOP is set")
        return 0
    if shutil.which("opencode") is None:
        record_failure(state, "error", "opencode CLI is not installed")
        save_state(state)
        write_outcome(state, "error", "opencode CLI is not installed")
        return 2

    task = current_task(state)
    if task is None:
        state["status"] = "complete"
        save_state(state)
        write_outcome(state, "complete", "no remaining tasks")
        return 0

    base = run_process(["git", "rev-parse", "HEAD"])[1].strip()
    LOGGER.info("task start: %s %s", task["task_id"], task["task_title"])

    if not run_agent(
        "autopilot-implementer",
        implementer_prompt(task, state),
        AGENT_TIMEOUT_SECONDS,
    ):
        record_failure(state, "blocked", "all implementer fallback models failed")
        save_state(state)
        write_outcome(state, "blocked", "all implementer fallback models failed")
        return 0
    if has_committed_changes(base):
        record_failure(state, "blocked", "a specialist committed changes")
        save_state(state)
        write_outcome(state, "blocked", "a specialist committed changes")
        return 0
    if not changed_paths():
        record_failure(state, "blocked", "the implementer made no changes")
        save_state(state)
        write_outcome(state, "blocked", "the implementer made no changes")
        return 0

    if not run_agent(
        "autopilot-evaluator",
        evaluator_prompt(task, state),
        AGENT_TIMEOUT_SECONDS,
    ):
        record_failure(state, "blocked", "all evaluator fallback models failed")
        save_state(state)
        write_outcome(state, "blocked", "all evaluator fallback models failed")
        return 0
    if has_committed_changes(base):
        record_failure(state, "blocked", "the evaluator committed changes")
        save_state(state)
        write_outcome(state, "blocked", "the evaluator committed changes")
        return 0

    gates = write_gates()
    if not (gates["tests_ok"] and gates["ruff_ok"]):
        LOGGER.info("gates failed; running one repair pass")
        run_agent(
            "autopilot-implementer",
            repair_prompt(task, state, gates),
            AGENT_TIMEOUT_SECONDS,
        )
        run_agent(
            "autopilot-evaluator",
            evaluator_prompt(task, state),
            AGENT_TIMEOUT_SECONDS,
        )
        if has_committed_changes(base):
            record_failure(state, "blocked", "a specialist committed changes")
            save_state(state)
            write_outcome(state, "blocked", "a specialist committed changes")
            return 0
        gates = write_gates()

    state["last_gates"] = {
        "tests_ok": gates["tests_ok"],
        "ruff_ok": gates["ruff_ok"],
        "policy_errors": gates["policy_errors"],
        "diff_lines": gates["diff_lines"],
    }
    if not (gates["tests_ok"] and gates["ruff_ok"] and not gates["policy_errors"]):
        reason = "deterministic gates failed"
        record_failure(state, "blocked", reason)
        save_state(state)
        write_patch()
        write_outcome(state, "blocked", reason)
        return 0

    if not run_agent(
        "autopilot-guardian",
        guardian_prompt(task, state),
        REVIEW_TIMEOUT_SECONDS,
    ):
        record_failure(state, "blocked", "all guardian fallback models failed")
        save_state(state)
        write_patch()
        write_outcome(state, "blocked", "all guardian fallback models failed")
        return 0

    decision = run_supervisor(task, state, gates)
    if decision is None:
        decision = reject_decision("Supervisor did not produce a valid decision.", task["rule"])
        write_text(AUTOPILOT_DIR / "decision.json", json.dumps(decision, indent=2) + "\n")

    approved = decision.get("decision") == "approve"
    if approved:
        record_success(state, decision.get("summary", "approved"))
        save_state(state)
        write_patch()
        write_outcome(state, "approve", decision.get("summary", "approved"))
    else:
        reason = f"supervisor rejected: {decision.get('summary', 'no reason')}"
        record_failure(state, "reject", reason)
        save_state(state)
        write_patch()
        write_outcome(state, "reject", reason)
    return 0


def run_promote() -> int:  # noqa: PLR0911
    configure_logging()
    state = load_state()
    if not OUTCOME_PATH.is_file():
        LOGGER.error("no outcome artifact found; nothing to promote")
        return 1
    outcome = json.loads(OUTCOME_PATH.read_text(encoding="utf-8"))
    kind = outcome.get("kind", "error")
    reason = str(outcome.get("reason", "unknown"))
    task = current_task(state)
    task_name = task["task_title"] if task else "none"
    LOGGER.info("promote phase: kind=%s task=%s", kind, task_name)

    setup_repo()

    if kind == "approve":
        applied, apply_reason = apply_candidate_patch()
        if not applied:
            revert_candidate_patch()
            record_failure(state, "blocked", apply_reason)
            save_state(state)
            commit_state_only("patch apply failed")
            create_issue(f"Autopilot patch apply failed: {TODAY}", apply_reason)
            return 0
        gates = write_gates()
        if not (gates["tests_ok"] and gates["ruff_ok"] and not gates["policy_errors"]):
            revert_candidate_patch()
            record_failure(state, "blocked", "promote gates failed")
            save_state(state)
            commit_state_only("promote gates failed")
            create_issue(
                f"Autopilot promote gates failed: {TODAY}",
                json.dumps(gates, indent=2)[:60000],
            )
            return 0

        decision_path = AUTOPILOT_DIR / "decision.json"
        if not decision_path.is_file():
            revert_candidate_patch()
            record_failure(state, "blocked", "decision artifact is missing")
            save_state(state)
            commit_state_only("decision missing")
            create_issue(f"Autopilot decision missing: {TODAY}", "No decision artifact.")
            return 0
        try:
            decision = json.loads(decision_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            revert_candidate_patch()
            record_failure(state, "blocked", "decision artifact is invalid JSON")
            save_state(state)
            commit_state_only("decision invalid")
            create_issue(f"Autopilot decision invalid: {TODAY}", "Decision is not valid JSON.")
            return 0
        decision_errors = validate_decision(decision)
        if decision_errors:
            revert_candidate_patch()
            record_failure(state, "blocked", "decision artifact is invalid")
            save_state(state)
            commit_state_only("decision invalid")
            create_issue(
                f"Autopilot decision invalid: {TODAY}",
                "\n".join(decision_errors),
            )
            return 0
        title = " ".join(str(decision["commit_message"]).splitlines()).strip()
        if not title.lower().startswith("autopilot:"):
            title = f"autopilot: {title}"
        body = str(decision["pr_body"]) + "\n\nRisks:\n" + str(decision["risks"])
        if commit_and_promote(title, body):
            return 0
        create_issue(f"Autopilot could not promote: {TODAY}", body)
        return 0

    if kind in {"complete", "stopped"}:
        commit_state_only(kind)
        return 0

    if kind in {"reject", "blocked", "error"}:
        commit_state_only(kind)
        create_issue(f"Autopilot {kind}: {TODAY}", reason)
        return 0

    commit_state_only(kind)
    create_issue(f"Autopilot {kind}: {TODAY}", reason)
    return 0


def run(phase: str = "build") -> int:
    if phase == "build":
        return run_build()
    if phase == "promote":
        return run_promote()
    code = run_build()
    if code != 0:
        return code
    return run_promote()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the continuous Autopilot loop.")
    parser.add_argument(
        "--phase",
        choices=("build", "promote", "all"),
        default="build",
        help="build runs agents; promote applies and pushes the candidate",
    )
    args = parser.parse_args()
    raise SystemExit(run(args.phase))


if __name__ == "__main__":
    main()
