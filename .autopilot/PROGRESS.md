# Autopilot progress

- Updated: 2026-10-21T23:59:56+00:00
- Status: running
- Progress: 7/17 tasks, 0 blocked, 0 runs
- Current: Sprint 4/8 (Fall accuracy) / Task 1 (Improve fall recall without adding false alarms)
- Last result: approved: Fight rule and pipeline violence path now fuse classifier verdicts with a configurable EMA smoother plus hysteresis (entry on positive_hits and smoothed score, exit on decay), test-backed and reversible, but accuracy was NOT measured because backend/models/ is missing so no baseline was updated.

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
| Fall accuracy | Improve fall recall without adding false alarms | current |
| Fall accuracy | Calibrate fall confidence | pending |
| Loitering and crowd accuracy | Improve loitering trajectory evidence | pending |
| Loitering and crowd accuracy | Improve crowd anomaly baseline | pending |
| Weapon accuracy | Improve weapon temporal evidence | pending |
| Weapon accuracy | Calibrate weapon threshold | pending |
| Zone and live evaluation | Add live zone-entry evaluation | pending |
| Zone and live evaluation | Close zone-entry accuracy gaps | pending |
| Regression and final report | Run the full accuracy regression | pending |
| Regression and final report | Write the final accuracy report and next backlog | pending |
