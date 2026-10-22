# Accuracy regression
Re-ran every benchmark with committed ground truth and predictions via `python -m scripts.eval.regression`.
Not-run benchmarks need model weights or raw datasets; no metric is invented.

- reproduced: 5, mismatched: 0, not run: 4

| Benchmark | Kind | TP | FP | FN | Precision | Recall | F1 | False alarms / 10 min |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `fall_events_urfd_5fps_c40` | events | 23 | 30 | 7 | 0.4340 | 0.7667 | 0.5542 | 45.1543 |
| `fall_events_urfd_5fps_c60` | events | 21 | 22 | 9 | 0.4884 | 0.7000 | 0.5753 | 33.1131 |
| `urfd_combined_5fps_events` | events | 23 | 81 | 7 | 0.2212 | 0.7667 | 0.3433 | 121.9165 |
| `rwf_val_clips_5fps` | clips | 0 | 0 | 200 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `rwf_val_clips_violence_2fps` | clips | 168 | 47 | 32 | 0.7814 | 0.8400 | 0.8096 | 14.1000 |

## Not run

| Benchmark | Kind | Reason |
| --- | --- | --- |
| `coco_person_100` | detections | stored predictions exist, but COCO annotations/images and model weights are absent |
| `coco_person_500` | detections | stored predictions exist, but COCO annotations/images and model weights are absent |
| `fall_events_urfd_5fps_overlap` | events | no matching prediction file is stored; the c40/c60 files produce different counts |
| `weapons_val_500` | detections | stored predictions exist, but YOLO labels/images and model weights are absent |
