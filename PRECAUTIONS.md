# Precautions Before Commercial Use

Living document. Add new risks as they are found. Last updated: 2026-10-20.

## 1. Dataset and model licenses

### RWF-2000 (fight / violence model) — COMMERCIAL USE BLOCKED
- Source: SMIIP Lab, Duke Kunshan University (Cheng, Cai, Li, ICPR 2020).
- License terms published with the dataset:
  1. No modifying or redistributing without SMIIP Lab approval.
  2. **No commercial use without SMIIP Lab approval.**
  3. No use that harms privacy or mental health.
  4. Cite the paper in academic publications.
- Current state: `backend/models/violence/best.pt` was fine-tuned on RWF-2000. Until written approval is obtained, treat the fight feature as research-only.
- The public repository already references RWF-2000 (`backend/scripts/train_rwf_classifier.py`, `backend/eval_results/rwf_val_*`, commit messages). Removing references changes visibility, not the legal position.
- Options: obtain written permission; retrain on a commercially licensed dataset; or train on customer-owned footage.
- The model weights are gitignored and are **not** in the repository; they must be copied to any deployment separately.

### Weapons-130K (weapon model) — VERIFY BEFORE LAUNCH
- Source: Kaggle dataset; license terms not yet reviewed by us.
- Confirm the dataset license and whether derivative models may be used commercially before selling the weapon feature.

### URFD (fall model) — VERIFY BEFORE LAUNCH
- Source: University of Rzeszów fall detection dataset.
- Usually distributed for research use; confirm terms and whether models trained on it may be sold.

### COCO (person detector evaluation) — LOW RISK, EVALUATION ONLY
- Annotations: CC BY 4.0. Images come from Flickr under varying licenses.
- Used only for local evaluation; no COCO images or annotations are shipped with the product.

## 2. Software license obligations

- **Ultralytics (YOLO) is AGPL-3.0** unless a commercial Ultralytics license is purchased. Running it as a network service can trigger source-disclosure obligations. This affects every model in this project (person, weapons, pose, fall, fight).
- Review licenses for the rest of the stack (FastAPI, PyTorch, OpenCV, supervision, React, etc.) before distribution.
- Get legal review before selling or hosting the product; this document is not legal advice.

## 3. Accuracy and safety limits

- Measured performance (public data, CPU):
  - Weapons: 0.85 mAP@0.5, per-class thresholds tuned.
  - Falls: ~77% recall / ~43% precision on URFD (7 of 30 falls missed); ~4.5 false alarms/min.
  - Fights: ~78% precision / ~84% recall on RWF-2000; ~1.4 false alarms/min.
  - Combined fall + fight on URFD exercise footage: ~12 false alarms/min.
- Performance will drop on footage unlike the training data (different cameras, lighting, crowds, resolutions).
- The product must be positioned as an **alerting aid with human review**, not as the sole trigger for emergency response, discipline, or law-enforcement action.
- False negatives are possible; never promise guaranteed detection in contracts or marketing.

## 4. Privacy and legal

- Recording and processing people on camera requires compliance with local law (GDPR, workplace monitoring rules, consent/notice requirements).
- Do not add face recognition or identity matching without a separate legal review.
- Set and enforce video retention limits; do not store footage longer than needed.
- Restrict who can view alerts and footage; log access.

## 5. Security items still open (from the product audit)

- Camera credentials are stored in plaintext — encrypt at rest and mask in the UI/API.
- `/detect` is unauthenticated and has no upload size/duration limits — add auth, rate limits, and validation.
- Audit log is never written — implement it before handling real customer data.
- Notification directories are empty and retention/S3 cleanup is unused — wire them or remove the claims.
- CORS defaults and `docker-compose` dev secrets must be tightened before deployment.

## 6. Deployment checklist

- [ ] Copy `backend/models/violence/best.pt` to the server (gitignored, not in the repo).
- [ ] Confirm licenses for RWF-2000 / Weapons-130K / URFD / Ultralytics, or replace the affected models.
- [ ] Keep the model confidence thresholds as shipped (fall 0.40, fight 0.80 + 2-hit persistence, weapon per-class values); re-tune if cameras differ.
- [ ] Run the test suite (`python -m pytest -q` in `backend/`) and smoke-test one real upload and one live camera.
- [ ] Enable HTTPS, rotate all default secrets, and disable debug mode.
