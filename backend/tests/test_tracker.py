import pytest

from workers.cv_worker.detector import Detection
from workers.cv_worker.tracker import ByteTrackTracker, TrackState


def _person(x: float, y: float = 100.0, w: float = 100.0, h: float = 200.0, conf: float = 0.9):
    return Detection(
        bbox=(x, y, x + w, y + h),
        confidence=conf,
        class_id=0,
        class_name="person",
    )


@pytest.fixture
def tracker():
    return ByteTrackTracker(
        frame_rate=30.0,
        track_activation_threshold=0.25,
        lost_track_buffer=30,
        minimum_matching_threshold=0.8,
        max_missed_frames=3,
    )


class TestTrackedObject:
    def test_center(self):
        t = ByteTrackTracker()
        snap = t.update([_person(0.0)], 100.0)
        obj = snap.tracked[0]
        assert obj.center == (50.0, 200.0)

    def test_bottom_center(self):
        t = ByteTrackTracker()
        snap = t.update([_person(0.0)], 100.0)
        assert snap.tracked[0].bottom_center == (50.0, 300.0)

    def test_dwell_seconds_zero_on_first_frame(self, tracker):
        snap = tracker.update([_person(0.0)], 100.0)
        assert snap.tracked[0].dwell_seconds == 0.0

    def test_dwell_seconds_accumulates(self, tracker):
        tracker.update([_person(0.0)], 100.0)
        snap = tracker.update([_person(5.0)], 110.0)
        assert snap.tracked[0].dwell_seconds == pytest.approx(10.0)

    def test_is_inside_zone(self, tracker):
        snap = tracker.update([_person(0.0)], 100.0)
        obj = snap.tracked[0]
        assert obj.is_inside((0.0, 0.0, 200.0, 400.0)) is True
        assert obj.is_inside((500.0, 0.0, 600.0, 400.0)) is False

    def test_is_inside_uses_bottom_center(self, tracker):
        snap = tracker.update([_person(0.0, y=0.0)], 100.0)
        obj = snap.tracked[0]
        # bottom_center y = 200, so a zone ending at 150 must not match
        assert obj.is_inside((0.0, 0.0, 200.0, 150.0)) is False


class TestByteTrackIdentity:
    def test_same_object_keeps_id(self, tracker):
        snap1 = tracker.update([_person(0.0)], 100.0)
        snap2 = tracker.update([_person(5.0)], 101.0)
        snap3 = tracker.update([_person(10.0)], 102.0)
        id1 = snap1.tracked[0].tracker_id
        assert snap2.tracked[0].tracker_id == id1
        assert snap3.tracked[0].tracker_id == id1

    def test_two_objects_get_distinct_ids(self, tracker):
        snap = tracker.update([_person(0.0), _person(300.0)], 100.0)
        ids = {o.tracker_id for o in snap.tracked}
        assert len(ids) == 2

    def test_identity_survives_detection_order_change(self, tracker):
        snap = tracker.update([_person(0.0), _person(500.0)], 100.0)
        left = next(o for o in snap.tracked if o.bbox[0] < 300)
        right = next(o for o in snap.tracked if o.bbox[0] >= 300)
        id_left, id_right = left.tracker_id, right.tracker_id
        assert id_left != id_right

        # Same two objects, submitted in reverse order, drifting slightly
        snap = tracker.update([_person(503.0), _person(3.0)], 101.0)
        left = next(o for o in snap.tracked if o.bbox[0] < 300)
        right = next(o for o in snap.tracked if o.bbox[0] >= 300)
        assert left.tracker_id == id_left
        assert right.tracker_id == id_right

    def test_identity_follows_object_through_crossing(self, tracker):
        # Object A walks right, object B walks left; they pass each other.
        # 10 px/frame is a realistic walking pace for a 30 fps stream.
        start_a, start_b, speed = 50.0, 450.0, 10.0

        snap = tracker.update(
            [_person(start_a), _person(start_b)], 100.0
        )
        by_x = sorted(snap.tracked, key=lambda o: o.bbox[0])
        id_a, id_b = by_x[0].tracker_id, by_x[1].tracker_id
        assert id_a != id_b

        timestamp = 100.0
        for step in range(1, 41):
            timestamp += 1.0
            pos_a = start_a + speed * step
            pos_b = start_b - speed * step
            snap = tracker.update([_person(pos_a), _person(pos_b)], timestamp)

            assert len(snap.tracked) == 2, f"lost a track at step {step}"

            # At step 20 the objects sit at exactly the same x, so
            # left/right ordering is a tie. Only assert ordering once
            # they have physically separated again.
            if step == 20:
                continue

            left = min(snap.tracked, key=lambda o: o.bbox[0])
            right = max(snap.tracked, key=lambda o: o.bbox[0])
            expected_left = id_a if step < 20 else id_b
            expected_right = id_b if step < 20 else id_a
            assert left.tracker_id == expected_left, f"left mismatch at step {step}"
            assert right.tracker_id == expected_right, f"right mismatch at step {step}"

    def test_frames_seen_increments(self, tracker):
        tracker.update([_person(0.0)], 100.0)
        tracker.update([_person(3.0)], 101.0)
        snap = tracker.update([_person(6.0)], 102.0)
        assert snap.tracked[0].frames_seen == 3


class TestTrackLifecycle:
    def test_first_frame_state_is_new(self, tracker):
        snap = tracker.update([_person(0.0)], 100.0)
        assert snap.tracked[0].state == TrackState.NEW
        assert snap.tracked[0].tracker_id in snap.new_track_ids

    def test_state_becomes_tracked(self, tracker):
        tracker.update([_person(0.0)], 100.0)
        snap = tracker.update([_person(3.0)], 101.0)
        assert snap.tracked[0].state == TrackState.TRACKED
        assert snap.new_track_ids == set()

    def test_missing_frame_marks_lost(self, tracker):
        tracker.update([_person(0.0)], 100.0)
        tracker.update([_person(3.0)], 101.0)
        snap = tracker.update([], 102.0)
        assert snap.tracked == []
        assert len(snap.lost_track_ids) == 1

    def test_reacquire_after_lost(self, tracker):
        tracker.update([_person(0.0)], 100.0)
        tracker.update([_person(3.0)], 101.0)
        tracker.update([], 102.0)
        snap = tracker.update([_person(6.0)], 103.0)
        assert len(snap.tracked) == 1
        assert snap.tracked[0].state == TrackState.TRACKED
        assert snap.tracked[0].missed_frames == 0

    def test_track_retired_after_max_missed_frames(self, tracker):
        for i in range(3):
            tracker.update([_person(i * 3.0)], 100.0 + i)
        tracker.update([], 200.0)
        assert tracker.active_track_count == 1
        tracker.update([], 201.0)
        assert tracker.active_track_count == 1
        tracker.update([], 202.0)
        assert tracker.active_track_count == 1
        tracker.update([], 203.0)
        assert tracker.active_track_count == 0

    def test_by_id_lookup(self, tracker):
        snap = tracker.update([_person(0.0)], 100.0)
        tid = snap.tracked[0].tracker_id
        assert snap.by_id(tid) is not None
        assert snap.by_id(9999) is None

    def test_empty_frame_snapshot_is_empty(self, tracker):
        snap = tracker.update([], 100.0)
        assert snap.tracked == []
        assert snap.new_track_ids == set()
        assert snap.lost_track_ids == set()


class TestTrackerManagement:
    def test_active_track_count(self, tracker):
        assert tracker.active_track_count == 0
        tracker.update([_person(0.0), _person(400.0)], 100.0)
        assert tracker.active_track_count == 2

    def test_total_ids_created(self, tracker):
        tracker.update([_person(0.0), _person(500.0)], 100.0)
        assert tracker.total_ids_created == 2

    def test_reset_clears_state(self, tracker):
        tracker.update([_person(0.0)], 100.0)
        assert tracker.active_track_count == 1
        tracker.reset()
        assert tracker.active_track_count == 0
        assert tracker.total_ids_created == 0

    def test_ids_restart_after_reset(self, tracker):
        tracker.update([_person(0.0)], 100.0)
        tracker.reset()
        snap = tracker.update([_person(0.0)], 200.0)
        assert snap.tracked[0].tracker_id == 1


class TestCameraIsolation:
    def test_two_trackers_do_not_share_ids(self):
        cam_a = ByteTrackTracker()
        cam_b = ByteTrackTracker()

        snap_a = cam_a.update([_person(0.0)], 100.0)
        snap_b = cam_b.update([_person(0.0)], 100.0)

        assert snap_a.tracked[0].tracker_id == snap_b.tracked[0].tracker_id
        assert cam_a.active_track_count == 1
        assert cam_b.active_track_count == 1

        # Camera B sees nothing; camera A must be unaffected
        cam_b.update([], 101.0)
        assert cam_a.active_track_count == 1
        assert cam_b.active_track_count == 1

    def test_tracks_in_one_camera_absent_from_other(self):
        cam_a = ByteTrackTracker()
        cam_b = ByteTrackTracker()

        snap_a = cam_a.update([_person(0.0), _person(400.0)], 100.0)
        snap_b = cam_b.update([_person(0.0)], 100.0)

        assert len(snap_a.tracked) == 2
        assert len(snap_b.tracked) == 1


class TestMultiClass:
    def test_mixed_classes_tracked(self, tracker):
        person = _person(0.0)
        car = Detection(
            bbox=(300.0, 300.0, 500.0, 400.0),
            confidence=0.8,
            class_id=2,
            class_name="car",
        )
        snap = tracker.update([person, car], 100.0)
        assert len(snap.tracked) == 2
        assert {o.class_name for o in snap.tracked} == {"person", "car"}