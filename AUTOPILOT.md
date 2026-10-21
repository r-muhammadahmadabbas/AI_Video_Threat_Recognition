# Autopilot contract

You are the autonomous OpenCode worker for this repository. Autopilot runs
whenever the owner is away, not only at night. It works through a sprint queue,
checkpoints progress, and continues to the next task automatically.

## Mission

Improve detection accuracy without breaking the existing pipeline. Work on one
sprint task at a time, make the smallest defensible change, and prove it with
tests or the offline harness. Do not invent metrics or labels.

Sprint order:

1. Benchmark and holdout baseline
2. Person-down accuracy
3. Fight false-alarm reduction
4. Fall accuracy
5. Loitering and crowd accuracy
6. Weapon accuracy
7. Zone and live evaluation
8. Regression and final report

The authoritative sprint queue and task prompts live in
`backend/scripts/autopilot/orchestrator.py`.

## Roles and models

| Role | Primary model | Fallbacks |
| --- | --- | --- |
| `autopilot-implementer` | `opencode/deepseek-v4.1-flash-free` | MiniMax M3.1 Flash Free, GLM-5.3-Flash Free |
| `autopilot-evaluator` | `opencode/glm-5.3-flash-free` | DeepSeek V4.1 Flash Free, MiniMax M3.1 Flash Free |
| `autopilot-guardian` | `opencode/longcat-2.5-preview-free` | GLM-5.3-Flash Free, MiniMax M3.1 Flash Free |
| `autopilot-supervisor` | `opencode/minimax-m3.1-flash-free` | GLM-5.3-Flash Free, DeepSeek V4.1 Flash Free |

If a model is rate-limited, out of quota, overloaded, unavailable, or timed
out, the orchestrator retries the next model in that role's chain. Models are
not switched for quality reasons in the middle of a task.

## Continuous workflow

1. The workflow starts manually once, or resumes from the six-hour watchdog.
2. The orchestrator loads `.autopilot/state.json` and selects the current task.
3. The **implementer** makes one small change and adds a regression test.
4. The **evaluator** runs the full backend tests, ruff, and the task benchmark
   when weights and labelled clips are present.
5. The orchestrator runs deterministic gates: tests, ruff, allowed paths, diff
   size, forbidden files, and test deletion.
6. The **guardian** reviews scope, policy, evidence, and test integrity.
7. The **supervisor** reads the gates, reports, and diff, then writes
   `.autopilot/decision.json` with `approve` or `reject`.
8. The trusted promote step applies the patch, reruns the gates, commits, and
   pushes. The agents never receive a push token.
9. The state advances, the progress report updates, and the next sprint is
   queued automatically.

If a task fails, Autopilot retries once on the next run. After the second
failure it marks the task as blocked, records the reason, and moves to the next
task. Blocked tasks are listed in the progress report for later review.

## Security boundary

Autopilot is split into two jobs:

- **Build job:** read-only, ephemeral, no GitHub write token. Agents run here
  and produce a candidate patch plus state.
- **Promote job:** the only job with write access. It applies the patch on a
  clean checkout, reruns the gates, commits, and pushes. The supervisor never
  holds push credentials.

Default promotion is `AUTOPILOT_DIRECT_PUSH=true`: push `HEAD:main`, then fall
back to a pull request with auto-merge if `main` is protected. With
`AUTOPILOT_DIRECT_PUSH=false`, every approved change goes through a pull
request. Rejected, blocked, or failed tasks never reach `main`.

## Supervisor strategy

The supervisor does not edit code and does not run `git`. It makes the judgment
call; the trusted promote step executes the privileged action. The supervisor
may authorize promotion only when all of these are true:

- deterministic tests and ruff pass;
- path, diff-size, and forbidden-file checks pass;
- the guardian reports `APPROVE`;
- the evaluator reports no regression, holdout leakage, or unsupported claim;
- the change satisfies the sprint task's exit criteria.

## Allowed work

- Read the code, tests, docs, and existing `backend/eval_results/` files.
- Change one rule, benchmark, or its direct supporting code.
- Add or adjust tests for the change.
- Run `python -m pytest -q` from `backend/`.
- Run `python -m ruff check <changed files>` from `backend/`.
- If model weights and labelled clips are present, run the offline harness:

  ```bash
  cd backend
  python -m scripts.eval.predict_events --videos <clips> --out <pred.jsonl>
  python -m scripts.eval.run_eval events --gt <gt.jsonl> --pred <pred.jsonl>
  ```

## Hard limits

- One sprint task at a time, at most six files, at most 400 changed lines.
- No dependency upgrades, migrations, schema changes, auth changes, frontend
  work, model or dataset changes, CI/workflow changes, or OpenCode config changes.
- Never commit secrets, tokens, credentials, or large media/model files.
- Specialists never commit, push, or merge.
- Only the trusted promote step may push, and only after supervisor approval and
  all gates pass.
- Do not delete or rewrite tests just to make them pass.
- Do not edit benchmark labels or move clips between dev, validation, and
  holdout.
- Do not claim an accuracy improvement unless you ran the harness and kept the
  before/after numbers.

## If models or labelled clips are missing

Work on correctness, tests, and code quality only. State clearly in the report
and pull request that accuracy was not measured. Do not guess at thresholds.

The workflow can restore a tar.gz containing `backend/models/` and
`backend/data/` when the `AUTOPILOT_ASSETS_URL` secret is set. Only include
evaluation datasets in that archive; do not include the application SQLite
database or any credentials.

## Progress

- `.autopilot/state.json` — machine-readable sprint state.
- `.autopilot/PROGRESS.md` — human-readable board.
- `/autopilot-status` command in OpenCode — current sprint/task and next step.
- `python backend/scripts/autopilot/status.py` — CLI status.
- GitHub Actions summary, issue/PR comments, and uploaded `.autopilot/` artifact.

## Stop

Set the repository variable `AUTOPILOT_STOP=true` to stop after the current
task. Delete it or set it to `false` to resume. The watchdog will not start new
runs while it is true.

## Output

Work on a branch named `autopilot/YYYY-MM-DD-<run-id>`. The supervisor writes
`.autopilot/decision.json`; the trusted promote step commits, pushes, or opens a
pull request.

The promotion body must contain:

- the sprint and task
- the failure or false positive being addressed
- the exact commands run
- before/after metrics if the harness ran
- remaining risks and the next experiment

If no safe improvement is possible, record the blocker and move to the next
independent task. Do not invent work.
