import json
from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from PIL import Image

from scripts.eval.datasets import (
    coco_gt,
    resolve_image_paths,
    rwf_clip_labels,
    urfd_gt,
    yolo_gt,
)
from scripts.eval.metrics import (
    BoxLabel,
    BoxPrediction,
    EventInterval,
    aggregate_event_results,
    average_precision,
    evaluate_clip_labels,
    evaluate_detections,
    evaluate_events,
    iou,
    temporal_iou,
)
from scripts.eval.predict import predict_images
from scripts.eval.schema import (
    load_box_gt,
    load_box_predictions,
    load_clip_labels,
    load_event_gt,
    save_clip_labels,
    save_predictions,
)


class TestBoxIou:
    def test_identical_boxes(self):
        assert iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0

    def test_disjoint_boxes(self):
        assert iou((0, 0, 1, 1), (5, 5, 6, 6)) == 0.0

    def test_partial_overlap(self):
        assert iou((0, 0, 10, 10), (5, 0, 15, 10)) == pytest.approx(1 / 3)


class TestTemporalIou:
    def test_identical_intervals(self):
        assert temporal_iou(
            EventInterval("fall", 0, 5), EventInterval("fall", 0, 5)
        ) == 1.0

    def test_partial_overlap(self):
        assert temporal_iou(
            EventInterval("fall", 0, 10), EventInterval("fall", 5, 15)
        ) == pytest.approx(1 / 3)

    def test_point_events(self):
        assert temporal_iou(
            EventInterval("weapon", 2, 2), EventInterval("weapon", 2, 2)
        ) == 1.0
        assert temporal_iou(
            EventInterval("weapon", 2, 2), EventInterval("weapon", 3, 3)
        ) == 0.0


class TestAveragePrecision:
    def test_perfect_predictions_score_one(self):
        assert average_precision([True], [0.9], num_gt=1) == 1.0

    def test_no_predictions_score_zero(self):
        assert average_precision([], [], num_gt=2) == 0.0

    def test_false_positive_above_true_positive_lowers_ap(self):
        ap = average_precision([True, False, True], [0.9, 0.8, 0.7], num_gt=2)
        assert ap == pytest.approx(0.835, abs=0.005)


class TestDetectionMap:
    def test_map_averages_classes_present_in_gt(self):
        gt = {
            "a": [
                BoxLabel("person", (0, 0, 10, 10)),
                BoxLabel("weapon", (20, 20, 30, 30)),
            ]
        }
        predictions = {
            "a": [BoxPrediction("person", 0.9, (0, 0, 10, 10))]
        }

        result = evaluate_detections(gt, predictions)

        assert result.per_class_ap["person"] == 1.0
        assert result.per_class_ap["weapon"] == 0.0
        assert result.mean_ap == 0.5
        assert result.num_gt_boxes == 2
        assert result.num_predictions == 1

    def test_predictions_for_images_without_gt_are_not_ignored(self):
        gt = {"a": []}
        predictions = {"a": [BoxPrediction("person", 0.9, (0, 0, 10, 10))]}

        result = evaluate_detections(gt, predictions)

        assert result.per_class_ap == {}
        assert result.mean_ap == 0.0


class TestEventEvaluation:
    def test_exact_match_is_true_positive(self):
        result = evaluate_events(
            [EventInterval("fall", 0, 10)],
            [EventInterval("fall", 0, 10)],
        )
        scores = result.per_type["fall"]
        assert (scores.true_positives, scores.false_positives, scores.false_negatives) == (1, 0, 0)
        assert scores.precision == scores.recall == scores.f1 == 1.0

    def test_extra_prediction_is_false_alarm(self):
        result = evaluate_events(
            [EventInterval("fall", 0, 10)],
            [EventInterval("fall", 0, 10), EventInterval("fall", 30, 35)],
            duration_seconds=60.0,
        )
        scores = result.per_type["fall"]
        assert (scores.true_positives, scores.false_positives) == (1, 1)
        assert scores.precision == 0.5
        assert result.false_alarms_per_minute == 1.0

    def test_missed_event_is_false_negative(self):
        result = evaluate_events(
            [EventInterval("fall", 0, 10)], [], iou_threshold=0.3
        )
        scores = result.per_type["fall"]
        assert scores.true_positives == 0
        assert scores.false_negatives == 1
        assert scores.recall == 0.0

    def test_types_are_scored_separately(self):
        result = evaluate_events(
            [EventInterval("fall", 0, 10)],
            [EventInterval("weapon", 0, 10)],
        )
        assert result.per_type["fall"].false_negatives == 1
        assert result.per_type["weapon"].false_positives == 1
        assert result.overall.true_positives == 0

    def test_aggregate_sums_counts_across_clips(self):
        first = evaluate_events(
            [EventInterval("fall", 0, 5)], [EventInterval("fall", 0, 5)]
        )
        second = evaluate_events(
            [EventInterval("fall", 10, 15)], []
        )

        result = aggregate_event_results([first, second], duration_seconds=120.0)

        assert result.per_type["fall"].true_positives == 1
        assert result.per_type["fall"].false_negatives == 1
        assert result.overall.precision == 1.0
        assert result.overall.recall == 0.5


class TestClipMetrics:
    def test_confusion_counts_and_scores(self):
        gt = {
            "a.mp4": {"violence"},
            "b.mp4": set(),
            "c.mp4": {"violence"},
            "d.mp4": set(),
        }
        predicted = {
            "a.mp4": {"violence"},
            "b.mp4": {"violence"},
            "c.mp4": set(),
            "d.mp4": set(),
        }

        result = evaluate_clip_labels(gt, predicted, "violence")

        assert (result.true_positives, result.false_positives) == (1, 1)
        assert (result.false_negatives, result.true_negatives) == (1, 1)
        assert result.precision == 0.5
        assert result.recall == 0.5
        assert result.accuracy == 0.5

    def test_clips_missing_from_predictions_are_false_negatives(self):
        result = evaluate_clip_labels({"a.mp4": {"violence"}}, {}, "violence")

        assert result.false_negatives == 1
        assert result.recall == 0.0
        assert result.accuracy == 0.0


class TestDatasets:
    def test_coco_boxes_are_converted_to_xyxy(self, tmp_path):
        annotation_path = tmp_path / "instances.json"
        annotation_path.write_text(
            json.dumps(
                {
                    "images": [
                        {"id": 1, "file_name": "a.jpg"},
                        {"id": 2, "file_name": "b.jpg"},
                    ],
                    "categories": [
                        {"id": 1, "name": "person"},
                        {"id": 2, "name": "car"},
                    ],
                    "annotations": [
                        {
                            "id": 1,
                            "image_id": 1,
                            "category_id": 1,
                            "bbox": [10, 20, 30, 40],
                        },
                        {
                            "id": 2,
                            "image_id": 1,
                            "category_id": 2,
                            "bbox": [0, 0, 5, 5],
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )

        gt = coco_gt(annotation_path)

        assert gt["a.jpg"][0].bbox == (10.0, 20.0, 40.0, 60.0)
        assert set(gt) == {"a.jpg", "b.jpg"}
        assert gt["b.jpg"] == []

    def test_yolo_labels_are_denormalized_with_image_size(self, tmp_path):
        images = tmp_path / "images"
        labels = tmp_path / "labels"
        images.mkdir()
        labels.mkdir()
        Image.new("RGB", (100, 50)).save(images / "img.png")
        (labels / "img.txt").write_text("0 0.5 0.5 0.2 0.4\n", encoding="utf-8")
        classes = tmp_path / "classes.txt"
        classes.write_text("person\n", encoding="utf-8")

        gt = yolo_gt(images, labels, classes)

        label = gt["img.png"][0]
        assert label.class_name == "person"
        assert label.bbox == pytest.approx((40.0, 15.0, 60.0, 35.0))

    def test_yolo_gt_can_keep_only_requested_classes(self, tmp_path):
        images = tmp_path / "images"
        labels = tmp_path / "labels"
        images.mkdir()
        labels.mkdir()
        Image.new("RGB", (100, 50)).save(images / "img.png")
        (labels / "img.txt").write_text(
            "0 0.5 0.5 0.2 0.4\n1 0.1 0.1 0.1 0.1\n", encoding="utf-8"
        )
        classes = tmp_path / "classes.txt"
        classes.write_text("firearm\nperson\n", encoding="utf-8")

        gt = yolo_gt(images, labels, classes, classes=("firearm",))

        assert [label.class_name for label in gt["img.png"]] == ["firearm"]

    def test_missing_images_fail_loudly(self, tmp_path):
        gt = {"missing.jpg": []}
        with pytest.raises(FileNotFoundError, match=r"missing\.jpg"):
            resolve_image_paths(gt, tmp_path)

    def test_urfd_csv_becomes_fall_intervals(self, tmp_path):
        csv_path = tmp_path / "urfall-cam0-falls.csv"
        csv_path.write_text(
            "sequence,frame,label,HeightWidthRatio\n"
            "fall-01,0,-1,1.0\n"
            "fall-01,1,0,1.0\n"
            "fall-01,2,1,1.0\n"
            "fall-01,3,1,1.0\n"
            "fall-01,4,-1,1.0\n"
            "adl-01,0,-1,1.0\n",
            encoding="utf-8",
        )

        clips = urfd_gt(csv_path, fps=2.0)

        fall = clips["fall-01-cam0.mp4"]
        assert fall.events == [EventInterval("person_down", 0.5, 2.0)]
        assert fall.duration == pytest.approx(2.5)
        assert clips["adl-01-cam0.mp4"].events == []

    def test_rwf_folder_tree_labels_fight_and_nonfight(self, tmp_path):
        fight = tmp_path / "val" / "Fight"
        nonfight = tmp_path / "val" / "NonFight"
        fight.mkdir(parents=True)
        nonfight.mkdir(parents=True)
        (fight / "a.avi").write_bytes(b"x")
        (nonfight / "b.avi").write_bytes(b"x")
        (tmp_path / "val" / "notes.txt").write_bytes(b"x")

        labels = rwf_clip_labels(tmp_path)

        assert labels == {"a.avi": {"violence"}, "b.avi": set()}


class TestSchema:
    def test_predictions_round_trip(self, tmp_path):
        path = tmp_path / "preds.jsonl"
        predictions = {
            "a.jpg": [BoxPrediction("person", 0.912345, (1.0, 2.0, 3.0, 4.0))]
        }

        save_predictions(path, predictions)
        loaded = load_box_predictions(path)

        assert loaded == predictions

    def test_box_gt_and_event_gt_loaders(self, tmp_path):
        boxes_path = tmp_path / "boxes.jsonl"
        boxes_path.write_text(
            '{"image": "a.jpg", "boxes": [{"class": "person", '
            '"bbox": [0, 1, 2, 3]}]}\n',
            encoding="utf-8",
        )
        events_path = tmp_path / "events.jsonl"
        events_path.write_text(
            '{"clip": "a.mp4", "duration": 12.0, "events": '
            '[{"type": "fall", "start": 1.0, "end": 2.0}]}\n',
            encoding="utf-8",
        )

        boxes = load_box_gt(boxes_path)
        clips = load_event_gt(events_path)

        assert boxes["a.jpg"][0].bbox == (0.0, 1.0, 2.0, 3.0)
        assert clips["a.mp4"].duration == 12.0
        assert clips["a.mp4"].events[0] == EventInterval("fall", 1.0, 2.0)

    def test_clip_labels_round_trip(self, tmp_path):
        path = tmp_path / "labels.jsonl"
        labels = {"a.avi": {"violence"}, "b.avi": set()}

        save_clip_labels(path, labels)

        assert load_clip_labels(path) == labels


@dataclass
class _FakeDetection:
    class_name: str
    confidence: float
    bbox: tuple[float, float, float, float]


class _FakeAnalyzer:
    def __init__(self):
        self.resets = 0

    def reset(self):
        self.resets += 1

    def analyze(self, _frame):
        return SimpleNamespace(
            persons=[_FakeDetection("person", 0.9, (0.0, 0.0, 5.0, 5.0))],
            weapons=[_FakeDetection("firearm", 0.6, (1.0, 1.0, 2.0, 2.0))],
        )


class TestPredictImages:
    def test_predictions_include_persons_and_weapons(self, tmp_path):
        image_path = tmp_path / "img.png"
        Image.new("RGB", (10, 10)).save(image_path)
        analyzer = _FakeAnalyzer()

        predictions = predict_images({"img.png": image_path}, analyzer)

        assert analyzer.resets == 1
        classes = [p.class_name for p in predictions["img.png"]]
        assert classes == ["person", "firearm"]
        assert predictions["img.png"][0].confidence == 0.9
