# Autopilot progress

- Updated: 2026-10-22T00:49:37+00:00
- Status: running
- Progress: 10/17 tasks, 0 blocked, 0 runs
- Current: Sprint 5/8 (Loitering and crowd accuracy) / Task 2 (Improve crowd anomaly baseline)
- Last result: approved: Approved: the loitering rule now records per-track center-path trajectory, rejects persistent stationary-object tracks, and preserves dwell across brief tracker dropouts, with 8 new regression tests; deterministic gates pass, guardian and evaluator both approve, and no accuracy claim is made because model weights and labelled loitering clips are missing.

## Sprint board

| Sprint | Task | Status |
| --- | --- | --- |
| Benchmark and holdout baseline | Define benchmark manifest and holdout split | done |
| Benchmark and holdout baseline | Record baseline metrics from existing results | done |
| Benchmark and holdout baseline | Add missing-data regression coverage | done |
| Person-down accuracy | Strengthen person-down temporal evidence | done |
| Person-down accuracy | Calibrate person-down thresholds | done |
| Fight false-alarm reduction | Reduce fight false alarms on normal motion | done |
| Fight false-alarm reduction | Improve fight temporal fusion | done |
| Fall accuracy | Improve fall recall without adding false alarms | done |
| Fall accuracy | Calibrate fall confidence | done |
| Loitering and crowd accuracy | Improve loitering trajectory evidence | done |
| Loitering and crowd accuracy | Improve crowd anomaly baseline | current |
| Weapon accuracy | Improve weapon temporal evidence | pending |
| Weapon accuracy | Calibrate weapon threshold | pending |
| Zone and live evaluation | Add live zone-entry evaluation | pending |
| Zone and live evaluation | Close zone-entry accuracy gaps | pending |
| Regression and final report | Run the full accuracy regression | pending |
| Regression and final report | Write the final accuracy report and next backlog | pending |
