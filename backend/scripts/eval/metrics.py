"""Detection and event metrics, implemented without third-party eval deps.

Boxes are axis-aligned ``(x1, y1, x2, y2)`` in pixels. Events are time
intervals with a type. Everything here is pure so results are reproducible
and directly unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass

BBox = tuple[float, float, float, float]


@dataclass(frozen=True)
class BoxLabel:
    """One ground-truth box."""

    class_name: str
    bbox: BBox


@dataclass(frozen=True)
class BoxPrediction:
    """One predicted box; ``confidence`` orders the precision-recall curve."""

    class_name: str
    confidence: float
    bbox: BBox


@dataclass(frozen=True)
class EventInterval:
    """One event in time, used for P/R/F1 scoring of rule triggers."""

    event_type: str
    start: float
    end: float

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


def iou(a: BBox, b: BBox) -> float:
    """Intersection over union of two boxes; 0.0 when they do not overlap."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    intersection = iw * ih
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - intersection
    return intersection / union if union > 0 else 0.0


def temporal_iou(a: EventInterval, b: EventInterval) -> float:
    """IoU of two time intervals; point events match only at the same instant."""
    intersection = max(0.0, min(a.end, b.end) - max(a.start, b.start))
    union = max(a.end, b.end) - min(a.start, b.start)
    if union <= 0:
        return 1.0 if a.start == b.start else 0.0
    return intersection / union


def average_precision(
    tp_flags: list[bool], scores: list[float], num_gt: int, num_points: int = 101
) -> float:
    """VOC-style AP with ``num_points`` recall levels (COCO's default 101).

    ``tp_flags`` and ``scores`` are parallel arrays over every prediction of
    one class across all images; ``num_gt`` is that class's total box count.
    """
    if num_gt <= 0 or not tp_flags:
        return 0.0

    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    recalls = [0.0]
    precisions = [0.0]
    hits = 0
    for rank, index in enumerate(order, start=1):
        hits += 1 if tp_flags[index] else 0
        recalls.append(hits / num_gt)
        precisions.append(hits / rank)

    # Precision envelope: every point takes the best precision at equal or
    # higher recall, which is the standard way to make the PR curve monotone.
    for i in range(len(precisions) - 2, -1, -1):
        precisions[i] = max(precisions[i], precisions[i + 1])

    total = 0.0
    for step in range(num_points):
        recall_level = step / (num_points - 1)
        total += max(
            (
                precision
                for recall, precision in zip(recalls, precisions, strict=True)
                if recall >= recall_level
            ),
            default=0.0,
        )
    return total / num_points


@dataclass
class DetectionEvalResult:
    """Per-class AP plus the mean, over one dataset run."""

    per_class_ap: dict[str, float]
    mean_ap: float
    num_images: int
    num_gt_boxes: int
    num_predictions: int


def evaluate_detections(
    gt_by_image: dict[str, list[BoxLabel]],
    predictions_by_image: dict[str, list[BoxPrediction]],
    iou_threshold: float = 0.5,
) -> DetectionEvalResult:
    """Greedy-matching mAP over all classes present in the ground truth."""
    classes = sorted(
        {label.class_name for labels in gt_by_image.values() for label in labels}
    )
    per_class_ap: dict[str, float] = {}

    for class_name in classes:
        tp_flags: list[bool] = []
        scores: list[float] = []
        num_gt = 0

        for image_id, labels in gt_by_image.items():
            class_labels = [label for label in labels if label.class_name == class_name]
            num_gt += len(class_labels)
            class_predictions = sorted(
                (
                    p
                    for p in predictions_by_image.get(image_id, [])
                    if p.class_name == class_name
                ),
                key=lambda p: p.confidence,
                reverse=True,
            )

            matched: set[int] = set()
            for prediction in class_predictions:
                best_iou = 0.0
                best_index = -1
                for index, label in enumerate(class_labels):
                    if index in matched:
                        continue
                    value = iou(prediction.bbox, label.bbox)
                    if value > best_iou:
                        best_iou, best_index = value, index
                hit = best_index >= 0 and best_iou >= iou_threshold
                if hit:
                    matched.add(best_index)
                tp_flags.append(hit)
                scores.append(prediction.confidence)

        per_class_ap[class_name] = average_precision(tp_flags, scores, num_gt)

    mean_ap = (
        sum(per_class_ap.values()) / len(per_class_ap) if per_class_ap else 0.0
    )
    return DetectionEvalResult(
        per_class_ap=per_class_ap,
        mean_ap=mean_ap,
        num_images=len(gt_by_image),
        num_gt_boxes=sum(len(labels) for labels in gt_by_image.values()),
        num_predictions=sum(
            len(predictions) for predictions in predictions_by_image.values()
        ),
    )


@dataclass
class EventTypeResult:
    """Confusion counts and derived P/R/F1 for one event type."""

    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float


def _score_counts(tp: int, fp: int, fn: int) -> EventTypeResult:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall)
        else 0.0
    )
    return EventTypeResult(
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        precision=precision,
        recall=recall,
        f1=f1,
    )


@dataclass
class EventEvalResult:
    """Per-type event scores plus micro totals and alarm rate."""

    per_type: dict[str, EventTypeResult]
    overall: EventTypeResult
    false_alarms_per_minute: float | None


def evaluate_events(
    gt_events: list[EventInterval],
    predicted_events: list[EventInterval],
    iou_threshold: float = 0.3,
    duration_seconds: float | None = None,
) -> EventEvalResult:
    """Greedy-match predicted events to GT by type and temporal IoU.

    A prediction is a true positive only when it overlaps a GT event of the
    same type by at least ``iou_threshold``; everything unmatched on either
    side is a false positive or a false negative respectively.
    """
    event_types = sorted(
        {e.event_type for e in gt_events}
        | {e.event_type for e in predicted_events}
    )
    per_type: dict[str, EventTypeResult] = {}
    total_tp = total_fp = total_fn = 0

    for event_type in event_types:
        type_gt = [e for e in gt_events if e.event_type == event_type]
        type_predictions = [
            e for e in predicted_events if e.event_type == event_type
        ]

        matched_gt: set[int] = set()
        tp = fp = 0
        for prediction in type_predictions:
            best_iou = 0.0
            best_index = -1
            for index, gt_event in enumerate(type_gt):
                if index in matched_gt:
                    continue
                value = temporal_iou(prediction, gt_event)
                if value > best_iou:
                    best_iou, best_index = value, index
            if best_index >= 0 and best_iou >= iou_threshold:
                matched_gt.add(best_index)
                tp += 1
            else:
                fp += 1

        fn = len(type_gt) - len(matched_gt)
        per_type[event_type] = _score_counts(tp, fp, fn)
        total_tp += tp
        total_fp += fp
        total_fn += fn

    alarms_per_minute = (
        total_fp / (duration_seconds / 60.0) if duration_seconds else None
    )
    return EventEvalResult(
        per_type=per_type,
        overall=_score_counts(total_tp, total_fp, total_fn),
        false_alarms_per_minute=alarms_per_minute,
    )


@dataclass
class ClipEvalResult:
    """Clip-level confusion counts for one label plus derived scores."""

    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    precision: float
    recall: float
    f1: float
    accuracy: float


def evaluate_clip_labels(
    gt_labels: dict[str, set[str]],
    predicted_labels: dict[str, set[str]],
    label: str,
) -> ClipEvalResult:
    """Score whole-clip labels for datasets annotated per clip (RWF-2000).

    A clip is positive when it shows the phenomenon anywhere in the clip, so
    temporal localization is intentionally out of scope here; use event IoU
    scoring when the dataset provides intervals (URFD).
    """
    clips = sorted(set(gt_labels) | set(predicted_labels))
    tp = fp = fn = tn = 0

    for clip in clips:
        gt_positive = label in gt_labels.get(clip, set())
        predicted_positive = label in predicted_labels.get(clip, set())
        if gt_positive and predicted_positive:
            tp += 1
        elif predicted_positive:
            fp += 1
        elif gt_positive:
            fn += 1
        else:
            tn += 1

    scores = _score_counts(tp, fp, fn)
    total = len(clips)
    return ClipEvalResult(
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        true_negatives=tn,
        precision=scores.precision,
        recall=scores.recall,
        f1=scores.f1,
        accuracy=(tp + tn) / total if total else 0.0,
    )


def aggregate_event_results(
    results: list[EventEvalResult], duration_seconds: float | None = None
) -> EventEvalResult:
    """Micro-average per-clip results into one dataset-level result."""
    event_types = sorted(
        {event_type for result in results for event_type in result.per_type}
    )
    per_type: dict[str, EventTypeResult] = {}
    total_tp = total_fp = total_fn = 0

    for event_type in event_types:
        tp = sum(
            result.per_type[event_type].true_positives
            for result in results
            if event_type in result.per_type
        )
        fp = sum(
            result.per_type[event_type].false_positives
            for result in results
            if event_type in result.per_type
        )
        fn = sum(
            result.per_type[event_type].false_negatives
            for result in results
            if event_type in result.per_type
        )
        per_type[event_type] = _score_counts(tp, fp, fn)
        total_tp += tp
        total_fp += fp
        total_fn += fn

    alarms_per_minute = (
        total_fp / (duration_seconds / 60.0) if duration_seconds else None
    )
    return EventEvalResult(
        per_type=per_type,
        overall=_score_counts(total_tp, total_fp, total_fn),
        false_alarms_per_minute=alarms_per_minute,
    )
