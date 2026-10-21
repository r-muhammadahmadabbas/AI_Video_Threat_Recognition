"""Show Autopilot progress for the local CLI and GitHub Actions summary."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from scripts.autopilot.orchestrator import (  # noqa: E402
    SPRINTS,
    STATE_PATH,
    load_state,
    progress_text,
    total_tasks,
)


def should_continue() -> bool:
    if os.environ.get("AUTOPILOT_STOP", "").lower() in {"1", "true", "yes"}:
        return False
    if not STATE_PATH.is_file():
        return False
    state = load_state()
    return state.get("status") not in {"complete", "stopped"}


def render(state: dict) -> str:
    completed = len(state.get("completed", []))
    blocked = len(state.get("blocked", []))
    current = state.get("current")
    lines = [
        "Autopilot progress",
        f"Status: {state.get('status', 'unknown')}",
        f"Tasks: {completed}/{total_tasks()} done, {blocked} blocked, {state.get('runs', 0)} runs",
    ]
    if current:
        lines.append(
            f"Current: Sprint {current['sprint_index'] + 1}/{len(SPRINTS)} "
            f"- {current['sprint_name']} / Task {current['task_index'] + 1} - "
            f"{current['task_title']}"
        )
    else:
        lines.append("Current: none")
    last = state.get("last_result")
    if last:
        lines.append(f"Last: {last.get('status')} - {last.get('reason')}")
    return "\n".join(lines)


def github_summary(state: dict) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    text = progress_text(state)
    if summary_path:
        with Path(summary_path).open("a", encoding="utf-8") as handle:
            handle.write(text)
    else:
        print(text)


def main() -> None:
    parser = argparse.ArgumentParser(description="Show Autopilot progress.")
    parser.add_argument("--json", action="store_true", help="print raw state JSON")
    parser.add_argument("--github-summary", action="store_true", help="append to step summary")
    parser.add_argument(
        "--should-continue",
        action="store_true",
        help="exit 0 if more work remains",
    )
    parser.add_argument("--watch", action="store_true", help="refresh every 30 seconds")
    args = parser.parse_args()

    if args.should_continue:
        raise SystemExit(0 if should_continue() else 1)

    if not STATE_PATH.is_file():
        print("Autopilot has not started. Trigger the autopilot workflow first.")
        raise SystemExit(0)

    state = load_state()
    if args.json:
        print(json.dumps(state, indent=2))
    elif args.github_summary:
        github_summary(state)
    elif args.watch:
        while True:
            print(render(state))
            print()
            time.sleep(30)
            state = load_state()
    else:
        print(render(state))


if __name__ == "__main__":
    main()
