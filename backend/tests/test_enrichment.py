import numpy as np

from tests.zone_fixtures import make_track
from workers.cv_worker.analyzer import FrameAnalysis
from workers.cv_worker.detector import Detection
from workers.cv_worker.enrichment import apply_enrichment
from workers.cv_worker.tracker import TrackSnapshot
from workers.cv_worker.weapon_detector import WeaponDetection


def snapshot(*tracks) -> TrackSnapshot:
    return TrackSnapshot(timestamp=0.0, tracked=list(tracks))


def weapon(name="firearm", confidence=0.8, bbox=(140.0, 140.0, 160.0, 160.0)):
    return WeaponDetection(class_name=name, confidence=confidence, bbox=bbox)


def fall(confidence=0.8, bbox=(140.0, 140.0, 160.0, 160.0)):
    return Detection(
        bbox=bbox, confidence=confidence, class_id=0, class_name="fallen"
    )


class TestWeaponAssociation:
    def test_weapon_centered_on_person_is_attached(self):
        track = make_track(bbox=(100.0, 100.0, 200.0, 300.0))
        analysis = FrameAnalysis(weapons=[weapon()])

        apply_enrichment(snapshot(track), analysis)

        assert track.weapon_detected is True
        assert track.weapon_confidence == 0.8

    def test_weapon_center_outside_the_person_is_not_attached(self):
        track = make_track(bbox=(100.0, 100.0, 200.0, 300.0))
        analysis = FrameAnalysis(weapons=[weapon(bbox=(210.0, 150.0, 230.0, 170.0))])

        apply_enrichment(snapshot(track), analysis)

        assert track.weapon_detected is False
        assert track.weapon_confidence == 0.0

    def test_strongest_associated_weapon_wins(self):
        track = make_track(bbox=(100.0, 100.0, 200.0, 300.0))
        analysis = FrameAnalysis(
            weapons=[
                weapon("melee_weapon", 0.4),
                weapon("firearm", 0.9),
            ]
        )

        apply_enrichment(snapshot(track), analysis)

        assert track.weapon_confidence == 0.9

    def test_flags_do_not_leak_between_frames(self):
        track = make_track(bbox=(100.0, 100.0, 200.0, 300.0))
        apply_enrichment(snapshot(track), FrameAnalysis(weapons=[weapon()]))
        assert track.weapon_detected is True

        apply_enrichment(snapshot(track), FrameAnalysis())

        assert track.weapon_detected is False
        assert track.weapon_confidence == 0.0


class TestViolenceEnrichment:
    def test_violence_marks_every_active_track(self):
        first = make_track(1)
        second = make_track(2, bbox=(300.0, 100.0, 400.0, 300.0))

        apply_enrichment(snapshot(first, second), FrameAnalysis(violence=True))

        assert first.violence_detected is True
        assert second.violence_detected is True

    def test_no_violence_leaves_tracks_clear(self):
        track = make_track()

        apply_enrichment(snapshot(track), FrameAnalysis(violence=False))

        assert track.violence_detected is False

    def test_violence_checked_flag_is_copied(self):
        track = make_track()

        apply_enrichment(
            snapshot(track), FrameAnalysis(violence=False, violence_checked=True)
        )
        assert track.violence_checked is True

        apply_enrichment(snapshot(track), FrameAnalysis())
        assert track.violence_checked is False


def keypoints(nose, left_ankle, right_ankle) -> np.ndarray:
    pose = np.zeros((1, 17, 2), dtype=np.float32)
    pose[0][0] = nose
    pose[0][15] = left_ankle
    pose[0][16] = right_ankle
    return pose


class TestPoseFallEnrichment:
    def test_head_at_ankle_height_marks_track_fallen(self):
        track = make_track(bbox=(100.0, 100.0, 200.0, 450.0))
        pose = keypoints(nose=(150.0, 400.0), left_ankle=(150.0, 405.0), right_ankle=(150.0, 405.0))

        apply_enrichment(snapshot(track), FrameAnalysis(pose_keypoints=pose))

        assert track.fall_detected is True

    def test_standing_skeleton_is_not_fallen(self):
        track = make_track(bbox=(100.0, 100.0, 200.0, 450.0))
        pose = keypoints(nose=(150.0, 150.0), left_ankle=(150.0, 400.0), right_ankle=(150.0, 400.0))

        apply_enrichment(snapshot(track), FrameAnalysis(pose_keypoints=pose))

        assert track.fall_detected is False

    def test_skeleton_outside_the_box_is_ignored(self):
        track = make_track(bbox=(100.0, 100.0, 200.0, 450.0))
        pose = keypoints(nose=(500.0, 400.0), left_ankle=(500.0, 405.0), right_ankle=(500.0, 405.0))

        apply_enrichment(snapshot(track), FrameAnalysis(pose_keypoints=pose))

        assert track.fall_detected is False

    def test_skeleton_without_ankles_is_ignored(self):
        track = make_track(bbox=(100.0, 100.0, 200.0, 450.0))
        pose = keypoints(nose=(150.0, 400.0), left_ankle=(0.0, 0.0), right_ankle=(0.0, 0.0))

        apply_enrichment(snapshot(track), FrameAnalysis(pose_keypoints=pose))

        assert track.fall_detected is False

class TestFallAssociation:
    def test_fall_centered_on_person_is_attached(self):
        track = make_track(bbox=(100.0, 100.0, 200.0, 300.0))
        analysis = FrameAnalysis(falls=[fall()])

        apply_enrichment(snapshot(track), analysis)

        assert track.fall_detected is True
        assert track.fall_confidence == 0.8

    def test_fall_center_outside_the_person_is_not_attached(self):
        track = make_track(bbox=(100.0, 100.0, 200.0, 300.0))
        analysis = FrameAnalysis(falls=[fall(bbox=(210.0, 150.0, 230.0, 170.0))])

        apply_enrichment(snapshot(track), analysis)

        assert track.fall_detected is False

    def test_fall_flag_clears_next_frame(self):
        track = make_track(bbox=(100.0, 100.0, 200.0, 300.0))
        apply_enrichment(snapshot(track), FrameAnalysis(falls=[fall()]))
        assert track.fall_detected is True

        apply_enrichment(snapshot(track), FrameAnalysis())

        assert track.fall_detected is False
        assert track.fall_confidence == 0.0
