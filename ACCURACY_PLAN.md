# Accuracy plan

Status: active. Started 2026-11-02.

The score for every change is two numbers on our own clips: false incidents per hour, and real events missed. Public URFD, RWF, COCO, and weapon scores stay as a reference. They do not decide what we ship.

A larger person model improves person boxes. It does not fix fall, weapon, or fight false alarms. Those come from separate weight files. Thresholds and zone shape run on the CPU. A free GPU is used only when a model file changes.

## Order of work

Do these in order. Skip a step only after the score on the holdout clips is written down.

1. Measure the current system on our clips.
2. Cut false positives with one rule setting at a time.
3. Compare a bigger person model (`yolo26s`, then `yolo26m`) on the same clips.
4. Fine-tune one specialist model only if step 2 still fails for that rule.

## Clips

Keep three folders. Never tune on the holdout.

| Folder | Contents | Used for |
| --- | --- | --- |
| `data/accuracy/train/` | Dismissed false alarms, plus extra examples of the real event | Fine-tuning only |
| `data/accuracy/val/` | About 10 real events and 30 minutes of normal activity per rule | Choosing the threshold or model |
| `data/accuracy/holdout/` | A second set, same mix, never opened while tuning | The number we report |

Record from the real camera. For the door pilot, normal activity means walking past, standing in the doorway, sitting, and bending. Label each clip with the rule name and `positive` or `negative`.

Run the worker on a clip on the CPU. Overnight is fine. Write the two scores into `backend/eval_results/site_scores.md` before changing anything.

Zone-entry geometry can be replayed without weights through `scripts.eval.live_zone_entry`. Event thresholds are chosen on validation and scored once on holdout through `python -m scripts.eval.calibrate`.

## Step 1 — Baseline

Current person detector: `yolo26n` (`MODEL_DETECTOR_NAME`). Device: `cpu`.

Specialist weights, loaded only when that rule is on:

| Rule | Model |
| --- | --- |
| Restricted zone, loitering, crowd | `yolo26n` only |
| Person down | `yolo26n`, `models/pose/yolo26s-pose.pt`, `models/fall/best.pt` |
| Weapon | `yolo26n`, `models/model/best.pt` |
| Fight | `models/violence/best.pt` |

Pilot order: restricted-zone entry, then loitering. Leave fall, fight, and weapon off until the door rule is scored.

## Step 2 — Thresholds on the CPU

Defaults live in `backend/workers/cv_worker/rules/config.py`. Per-camera overrides go in the rule `config_json`. Change one field, rerun `val/`, keep the change only if false alarms drop and the real events still fire.

| Rule | Field | Starting point |
| --- | --- | --- |
| Zone entry | `min_frames_in_zone` | 2. Require more consecutive frames inside. |
| Zone entry | Polygon | The test point is the feet (`bottom_center`). The shape has to include the floor, not only the door frame. |
| Every rule | `min_confidence` | 0.25. Raise it on that camera. |
| Person down | `min_fall_confidence`, `min_frames_down` | 0.60 and 3. |
| Weapon | `min_confidence`, `dwell_seconds` | 0.25 and 5 seconds. |
| Fight | `min_consecutive_frames` | Require the violence score to hold. |

Cooldown hides repeat alerts. It is not an accuracy fix.

After `val/` looks better, run `holdout/` once. Record both scores.

## Step 3 — Bigger person model

Run the same `val/` clips through `yolo26n`, `yolo26s`, and `yolo26m`. Keep the largest that still manages a few frames per second and misses fewer people. Leave `yolo26l` and `yolo26x` until a stronger machine exists.

Set the winner with `MODEL_DETECTOR_NAME` and score `holdout/` once. This step affects zone, loitering, and crowd only.

Do this comparison on Kaggle. The laptop stays on the threshold work.

## Step 4 — Fine-tune one specialist

Start this only when step 2 cannot make that rule acceptable.

One model per run: fall, weapon, or violence. Train on `train/` plus the public set already used for that model. Score on `val/`. Touch `holdout/` once, after the winner is chosen. Copy the new `best.pt` into `backend/models` only when holdout false alarms are lower than the baseline and real events are still caught.

Fight weights were fine-tuned on RWF-2000, which blocks commercial use until there is written approval. Fall (URFD) and weapon (Weapons-130K) licenses still need a check. See `PRECAUTIONS.md` before treating a retrained file as shippable.

## Free GPUs

Use a GPU only for step 3 and step 4. Save a checkpoint every epoch. The session disk is wiped when it ends.

| Place | What you get | Role |
| --- | --- | --- |
| [Kaggle](https://www.kaggle.com/docs/efficient-gpu-usage) | About 30 GPU hours per week after phone verification. No card. Session cap 12 hours. Accelerator is a T4. | Default place for the size comparison and any fine-tune. Turn the GPU on only while it is training, and write weights to the notebook output. |
| [Google Colab](https://research.google.com/colaboratory/faq.html) | Free. A GPU is often a T4 when one is available, and it is not guaranteed. A notebook lasts at most 12 hours and stops when idle. | Short eval if Kaggle is queued. |
| Lightning AI | A few credits with no card. Further free credits ask for a card. | After Kaggle and Colab are used up. |
| Hugging Face ZeroGPU | About 5 GPU minutes a day. | Demos only. Not for training. |

## Done when

- Holdout scores for restricted-zone entry are written down, and they beat the baseline.
- The person-model name in use is recorded next to those scores.
- Fall, weapon, and fight each stay off, or have their own holdout line showing fewer false alarms than the baseline.
