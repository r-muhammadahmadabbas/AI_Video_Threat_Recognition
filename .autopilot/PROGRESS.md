# Autopilot progress

- Updated: 2026-10-21T23:17:26+00:00
- Status: running
- Progress: 5/17 tasks, 0 blocked, 0 runs
- Current: Sprint 3/8 (Fight false-alarm reduction) / Task 1 (Reduce fight false alarms on normal motion)
- Last result: approved: Adds a test-backed, leakage-safe validation-only threshold calibration path plus an honest not_run calibration report and updated baseline; no production thresholds changed and no accuracy claimed because model weights and labelled validation/holdout clips are absent.

## Sprint board

| Sprint | Task | Status |
| --- | --- | --- |
| Benchmark and holdout baseline | Define benchmark manifest and holdout split | done |
| Benchmark and holdout baseline | Record baseline metrics from existing results | done |
| Benchmark and holdout baseline | Add missing-data regression coverage | done |
| Person-down accuracy | Strengthen person-down temporal evidence | done |
| Person-down accuracy | Calibrate person-down thresholds | done |
| Fight false-alarm reduction | Reduce fight false alarms on normal motion | current |
| Fight false-alarm reduction | Improve fight temporal fusion | pending |
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
