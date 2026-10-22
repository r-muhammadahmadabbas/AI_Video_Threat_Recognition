# Final accuracy report

- Sprint: 8/8, task 2 (write the final accuracy report and next backlog)
- Date: 2026-10-22
- Scope: all rules (`person_down`, `fight`, `loitering`, `crowd_anomaly`, `weapon`,
  `zone_entry`)
- Accuracy measured: no. `backend/models/` and the raw labelled datasets under
  `backend/data/` are absent, so detector inference and threshold calibration
  could not be run. Every number below is re-scored from committed ground truth
  and predictions, or transcribed from a stored report. No before/after
  inference claim is made.

## What improved

The sprint improved rule correctness and evaluation coverage. Unit tests prove the
behaviour; they do not prove accuracy on live data.

| Rule | Change delivered | Test evidence | Accuracy measured |
| --- | --- | --- | --- |
| `person_down` | Upright-pose veto for geometry-only evidence, track-age guard, and weak-band fall-score EMA with pose reset | `test_person_down.py`, `test_pipeline.py` | No |
| `fight` | Nearby moving-pair interaction gate plus EMA smoothing and hysteresis exit | `test_fight_rule.py`, `test_pipeline.py` | No |
| `loitering` | Center-path trajectory, stationary-object rejection, and dropout continuity | `test_loitering.py` | No |
| `crowd_anomaly` | Per-zone density (people per megapixel) and one-sided motion baselines | `test_crowd_anomaly.py` | No |
| `weapon` | Calibration report now records `not_run`; no threshold was tuned and existing detector thresholds are unchanged | `test_calibration.py` | No |
| `zone_entry` | Model-free live-path evaluator plus presence retention across brief tracker dropouts | `test_live_zone_entry.py`, `test_zone_entry.py` | No |
| evaluation | Baseline scoreboard, missing-data guards, and reproducible offline regression runner | `test_scoreboard.py`, `test_eval_harness.py`, `test_regression.py` | Re-scored only; inference not measured |

## Exact evidence

The offline regression re-scored all five committed event/clip benchmarks from
their ground truth and predictions: **5 reproduced, 0 mismatched, 4 not run**.
This confirms the stored numbers are reproducible; it is not a fresh accuracy
measurement.

### Reproducible event/clip benchmarks

| Benchmark | Kind | TP | FP | FN | Precision | Recall | F1 | False alarms / 10 min |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `fall_events_urfd_5fps_c40` | events | 23 | 30 | 7 | 0.4340 | 0.7667 | 0.5542 | 45.1543 |
| `fall_events_urfd_5fps_c60` | events | 21 | 22 | 9 | 0.4884 | 0.7000 | 0.5753 | 33.1131 |
| `urfd_combined_5fps_events` | events | 23 | 81 | 7 | 0.2212 | 0.7667 | 0.3433 | 121.9165 |
| `rwf_val_clips_5fps` | clips | 0 | 0 | 200 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `rwf_val_clips_violence_2fps` | clips | 168 | 47 | 32 | 0.7814 | 0.8400 | 0.8096 | 14.1000 |

The fall `c40`/`c60` rows are a stored whole-benchmark tradeoff, not a
validation/holdout calibration. No threshold was selected from them. The RWF
`5fps` row is a real stored-benchmark gap: zero true positives and 200 false
negatives, while the `2fps` row reaches F1 0.8096. It is not caused by the
regression runner, which reproduces both files exactly.

### Stored detection AP (not re-run)

| Benchmark | mAP |
| --- | --- |
| `coco_person_100` | 0.6325 |
| `coco_person_500` | 0.6432 |
| `weapons_val_500` | 0.8545 |

- person_down threshold calibration: `not_run` (selected threshold: `null`)
- weapon threshold calibration: `not_run` (selected threshold: `null`)
- Latency: unavailable in every stored report; no timing data exists.

### Not run

| Benchmark | Reason |
| --- | --- |
| `coco_person_100` | COCO annotations/images and model weights are absent |
| `coco_person_500` | COCO annotations/images and model weights are absent |
| `fall_events_urfd_5fps_overlap` | no matching prediction file is stored |
| `weapons_val_500` | YOLO labels/images and model weights are absent |

## Still blocked

- `backend/models/` is missing, so no detector or fall/fight/weapon inference can
  be rerun.
- `backend/data/` is empty, so the raw COCO, URFD, RWF, and weapon clips/labels
  needed for a fresh harness run are absent.
- No validation/holdout split manifest exists, so validation-only calibration
  cannot be executed. No holdout label was used for tuning.
- Detection AP and latency remain stored-only. There is no measured
  before/after result for any rule in this sprint.

## Next three experiments (prioritized backlog)

1. **P0 — Restore assets and run the harness end to end.** Add model weights,
   labelled clips, and a disjoint validation/holdout manifest, then run
   `predict`, `predict_events`, `run_eval`, and `calibrate`. Success: fresh
   metrics for every available rule, non-null precision/recall/F1, and no
   missing-asset `not_run` rows.
2. **P1 — Calibrate fall/person-down on validation and report holdout.** The
   current `c40`/`c60` rows are whole-benchmark only, with 45.15 and 33.11 false
   alarms per 10 minutes. Success: a threshold selected on validation only, a
   single holdout score at that threshold, and no holdout tuning.
3. **P2 — Measure fight false-alarm reduction and resolve the RWF 5fps zero
   recall.** Compare the interaction gate plus EMA/hysteresis against the
   stored baseline on labelled fight/normal clips, and explain why the `5fps`
   benchmark scores 0 TP/200 FN while `2fps` reaches F1 0.8096. Success:
   before/after fight precision, recall, F1, and false alarms per 10 minutes,
   with the `5fps` result reconciled to its raw clips and labels.
