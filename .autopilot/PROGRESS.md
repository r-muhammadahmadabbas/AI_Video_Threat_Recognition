# Autopilot progress

- Updated: 2026-10-22T02:11:15+00:00
- Status: running
- Progress: 15/17 tasks, 0 blocked, 0 runs
- Current: Sprint 8/8 (Regression and final report) / Task 1 (Run the full accuracy regression)
- Last result: approved: Adds a dropout_grace_seconds window (default 1.0) to ZoneEntryConfig and ages instead of immediately deleting ZoneEntryRule presence state, so a 1-2 frame tracker dropout no longer duplicates a zone-entry incident; small, in-scope, test-backed, and regression-free, with accuracy explicitly not measured because model weights and labelled clips are missing.

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
| Loitering and crowd accuracy | Improve crowd anomaly baseline | done |
| Weapon accuracy | Improve weapon temporal evidence | done |
| Weapon accuracy | Calibrate weapon threshold | done |
| Zone and live evaluation | Add live zone-entry evaluation | done |
| Zone and live evaluation | Close zone-entry accuracy gaps | done |
| Regression and final report | Run the full accuracy regression | current |
| Regression and final report | Write the final accuracy report and next backlog | pending |
