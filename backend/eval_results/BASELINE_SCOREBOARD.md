# Baseline scoreboard

Generated from `backend/eval_results` by `python -m scripts.eval.scoreboard`.

- metrics are transcribed from existing reports; the offline harness was not rerun because model weights are missing
- null means the metric was not available in the stored results; the reason is recorded in each row's missing map
- false alarms per 10 minutes are the stored per-minute rate scaled by 10
- fall_events_urfd_5fps_overlap: no matching raw prediction file is stored, and the c40/c60 prediction files do not reproduce these counts
- person-down threshold calibration status: not_run
- person-down calibration reason: model weights, labelled validation/holdout clips, and a validation/holdout split manifest are absent; the stored c40/c60 reports cover the whole URFD benchmark, so they cannot serve as split evidence

| Benchmark | Kind | Precision | Recall | F1 | False alarms / 10 min | Latency (ms) | mAP |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `coco_person_100` | detections | null | null | null | null | null | 0.6325 |
| `coco_person_500` | detections | null | null | null | null | null | 0.6432 |
| `fall_events_urfd_5fps_c40` | events | 0.4340 | 0.7667 | 0.5542 | 45.1543 | null | n/a |
| `fall_events_urfd_5fps_c60` | events | 0.4884 | 0.7000 | 0.5753 | 33.1131 | null | n/a |
| `fall_events_urfd_5fps_overlap` | events | 0.3607 | 0.7333 | 0.4835 | 58.7006 | null | n/a |
| `rwf_val_clips_5fps` | clips | 0.0000 | 0.0000 | 0.0000 | 0.0000 | null | n/a |
| `rwf_val_clips_violence_2fps` | clips | 0.7814 | 0.8400 | 0.8096 | 14.1000 | null | n/a |
| `urfd_combined_5fps_events` | events | 0.2212 | 0.7667 | 0.3433 | 121.9165 | null | n/a |
| `weapons_val_500` | detections | null | null | null | null | null | 0.8545 |

## Missing values

| Benchmark | Missing fields | Reason |
| --- | --- | --- |
| `coco_person_100` | precision, recall, f1 | existing detection report records AP/mAP only; no thresholded TP/FP/FN counts are stored |
| `coco_person_100` | false_alarms_per_10_minutes | existing detection report has no event stream or total clip duration |
| `coco_person_100` | latency_ms | existing eval report has no timing data; rerun the harness with per-frame timing to measure latency |
| `coco_person_500` | precision, recall, f1 | existing detection report records AP/mAP only; no thresholded TP/FP/FN counts are stored |
| `coco_person_500` | false_alarms_per_10_minutes | existing detection report has no event stream or total clip duration |
| `coco_person_500` | latency_ms | existing eval report has no timing data; rerun the harness with per-frame timing to measure latency |
| `fall_events_urfd_5fps_c40` | latency_ms | existing eval report has no timing data; rerun the harness with per-frame timing to measure latency |
| `fall_events_urfd_5fps_c60` | latency_ms | existing eval report has no timing data; rerun the harness with per-frame timing to measure latency |
| `fall_events_urfd_5fps_overlap` | latency_ms | existing eval report has no timing data; rerun the harness with per-frame timing to measure latency |
| `rwf_val_clips_5fps` | latency_ms | existing eval report has no timing data; rerun the harness with per-frame timing to measure latency |
| `rwf_val_clips_violence_2fps` | latency_ms | existing eval report has no timing data; rerun the harness with per-frame timing to measure latency |
| `urfd_combined_5fps_events` | latency_ms | existing eval report has no timing data; rerun the harness with per-frame timing to measure latency |
| `weapons_val_500` | precision, recall, f1 | existing detection report records AP/mAP only; no thresholded TP/FP/FN counts are stored |
| `weapons_val_500` | false_alarms_per_10_minutes | existing detection report has no event stream or total clip duration |
| `weapons_val_500` | latency_ms | existing eval report has no timing data; rerun the harness with per-frame timing to measure latency |
