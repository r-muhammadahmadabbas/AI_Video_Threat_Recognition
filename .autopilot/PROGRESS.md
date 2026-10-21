# Autopilot progress

- Updated: 2026-10-21T23:33:39+00:00
- Status: running
- Progress: 6/17 tasks, 0 blocked, 0 runs
- Current: Sprint 3/8 (Fight false-alarm reduction) / Task 2 (Improve fight temporal fusion)
- Last result: approved: Fight rule now requires a nearby moving pair with differing velocities before firing, suppressing fast single-person motion, hugging, camera shake, and crowd movement, with non-vacuous unit tests and preserved true-positive coverage; accuracy was not measured because model weights and labelled clips are missing.

## Sprint board

| Sprint | Task | Status |
| --- | --- | --- |
| Benchmark and holdout baseline | Define benchmark manifest and holdout split | done |
| Benchmark and holdout baseline | Record baseline metrics from existing results | done |
| Benchmark and holdout baseline | Add missing-data regression coverage | done |
| Person-down accuracy | Strengthen person-down temporal evidence | done |
| Person-down accuracy | Calibrate person-down thresholds | done |
| Fight false-alarm reduction | Reduce fight false alarms on normal motion | done |
| Fight false-alarm reduction | Improve fight temporal fusion | current |
| Fall accuracy | Improve fall recall without adding false alarms | pending |
| Fall accuracy | Calibrate fall confidence | pending |
| Loitering and crowd accuracy | Improve loitering trajectory evidence | pending |
| Loitering and crowd accuracy | Improve crowd anomaly baseline | pending |
| Weapon accuracy | Improve weapon temporal evidence | pending |
| Weapon accuracy | Calibrate weapon threshold | pending |
| Zone and live evaluation | Add live zone-entry evaluation | pending |
| Zone and live evaluation | Close zone-entry accuracy gaps | pending |
| Regression and final report | Run the full accuracy regression | pending |
| Regression and final report | Write the final accuracy report and next backlog | pending |
