"""Tests for the clip event prediction runner."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from scripts.eval.metrics import EventInterval
from scripts.eval.predict_events import (
    clip_id_for,
    events_to_intervals,
    predict_clip_from_capture,
    video_files,
)
from scripts.eval.schema import ClipEvents, load_event_gt, save_clip_events


class FakeCapture:
    def __init__(self, frames, fps):
        self._frames = list(frames)
        self._index = 0
        self._fps = fps

    def get(self, property_id):
        assert property_id == cv2.CAP_PROP_FPS
        return self._fps

    def read(self):
        if self._index >= len(self._frames):
            return False, None
        frame = self._frames[self._index]
        self._index += 1
        return True, frame


class FakePipeline:
    """Emits one detection per processed frame, like a perfectly noisy rule."""

    def __init__(self):
        self.reset_calls = 0
        self.timestamps: list[float] = []
        self.events: list[SimpleNamespace] = []

    def reset_session(self):
        self.reset_calls += 1
        self.timestamps.clear()
        self.events.clear()

    def process_frame(self, frame, timestamp):
        self.timestamps.append(timestamp)
        self.events.append(SimpleNamespace(rule="person_down", timestamp=timestamp))
        return frame, []


class TestEventsToIntervals:
    def test_events_within_gap_merge_into_one_interval(self):
        events = [
            SimpleNamespace(rule="weapon", timestamp=1.0),
            SimpleNamespace(rule="weapon", timestamp=1.5),
        ]

        intervals = events_to_intervals(
            events, gap_tolerance=1.0, min_duration=0.5
        )

        assert intervals == [EventInterval("weapon", 1.0, 2.0)]

    def test_events_beyond_gap_become_separate_intervals(self):
        events = [
            SimpleNamespace(rule="weapon", timestamp=1.0),
            SimpleNamespace(rule="weapon", timestamp=1.5),
            SimpleNamespace(rule="weapon", timestamp=5.0),
        ]

        intervals = events_to_intervals(
            events, gap_tolerance=1.0, min_duration=0.5
        )

        assert intervals == [
            EventInterval("weapon", 1.0, 2.0),
            EventInterval("weapon", 5.0, 5.5),
        ]

    def test_single_event_is_extended_by_min_duration(self):
        events = [SimpleNamespace(rule="person_down", timestamp=2.0)]

        intervals = events_to_intervals(
            events, gap_tolerance=1.0, min_duration=1.0
        )

        assert intervals == [EventInterval("person_down", 2.0, 3.0)]

    def test_rules_are_scored_independently(self):
        events = [
            SimpleNamespace(rule="weapon", timestamp=1.0),
            SimpleNamespace(rule="person_down", timestamp=1.0),
        ]

        intervals = events_to_intervals(
            events, gap_tolerance=1.0, min_duration=0.5
        )

        assert [interval.event_type for interval in intervals] == [
            "person_down",
            "weapon",
        ]


class TestPredictClip:
    def test_sampling_uses_source_timestamps_and_resets_pipeline(self):
        frames = [np.full((4, 4, 3), 255, dtype=np.uint8) for _ in range(10)]
        capture = FakeCapture(frames, fps=25.0)
        pipeline = FakePipeline()

        clip = predict_clip_from_capture(capture, "clip.mp4", pipeline, target_fps=5.0)

        assert pipeline.reset_calls == 1
        assert pipeline.timestamps == pytest.approx([0.0, 0.2])
        assert clip.duration == pytest.approx(0.4)
        assert clip.events == [EventInterval("person_down", 0.0, 0.4)]

    def test_invalid_fps_falls_back_and_still_processes(self):
        frames = [np.full((4, 4, 3), 255, dtype=np.uint8)]
        capture = FakeCapture(frames, fps=0.0)
        pipeline = FakePipeline()

        clip = predict_clip_from_capture(capture, "clip.mp4", pipeline, target_fps=1.0)

        assert pipeline.timestamps == pytest.approx([0.0])
        assert clip.duration == pytest.approx(1.0 / 25.0)


class TestClipIds:
    def test_relative_ids_disambiguate_nested_layouts(self, tmp_path):
        nested = tmp_path / "val" / "Fight" / "a.avi"

        assert clip_id_for(nested, tmp_path) == "val/Fight/a.avi"

    def test_plain_name_without_base(self):
        assert clip_id_for(Path("clip.mp4")) == "clip.mp4"

    def test_paths_outside_base_fall_back_to_name(self, tmp_path):
        assert clip_id_for(Path("other/clip.mp4"), tmp_path) == "clip.mp4"


class TestVideoFiles:
    def test_filters_to_video_suffixes_sorted(self, tmp_path):
        (tmp_path / "b.mp4").write_bytes(b"x")
        (tmp_path / "a.MP4").write_bytes(b"x")
        (tmp_path / "notes.txt").write_bytes(b"x")

        assert [path.name for path in video_files(tmp_path)] == ["a.MP4", "b.mp4"]


class TestSchemaClips:
    def test_save_clip_events_round_trips_through_loader(self, tmp_path):
        clips = {
            "fall_01.mp4": ClipEvents(
                clip="fall_01.mp4",
                duration=12.5,
                events=[EventInterval("person_down", 3.0, 5.5)],
            )
        }
        path = tmp_path / "pred_events.jsonl"

        save_clip_events(path, clips)
        loaded = load_event_gt(path)

        assert loaded["fall_01.mp4"].duration == 12.5
        assert loaded["fall_01.mp4"].events == [
            EventInterval("person_down", 3.0, 5.5)
        ]
