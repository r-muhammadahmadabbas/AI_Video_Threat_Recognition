"""Attach extra model outputs to tracked people.

The person detector is the only model whose boxes become tracks. Weapon, pose
and violence outputs describe those same people, so this module associates each
output with the track it belongs to before the rules run. Rules then read one
consistent :class:`~workers.cv_worker.tracker.TrackedObject` regardless of
which model produced the evidence.

Enrichment is strictly per-frame: every flag is cleared at the start of the
update. A stale ``weapon_detected`` carried over from an earlier frame would
let a person who briefly stood near a weapon keep alerting for the rest of the
track's life, so dropouts must be visible to the rules (which own any desired
grace window).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

    from workers.cv_worker.analyzer import FrameAnalysis
    from workers.cv_worker.tracker import TrackedObject, TrackSnapshot


def apply_enrichment(snapshot: TrackSnapshot, analysis: FrameAnalysis) -> None:
    """Write this frame's weapon/fall/violence evidence onto active tracks."""
    for track in snapshot.tracked:
        track.weapon_detected = False
        track.weapon_confidence = 0.0
        track.fall_detected = False
        track.fall_confidence = 0.0
        track.violence_detected = False
        track.violence_checked = analysis.violence_checked

        _attach_weapons(track, analysis)
        _attach_falls(track, analysis)
        if analysis.violence:
            track.violence_detected = True
        if analysis.pose_keypoints is not None and _pose_shows_fall(
            analysis.pose_keypoints, track.bbox
        ):
            track.fall_detected = True


def _attach_weapons(track: TrackedObject, analysis: FrameAnalysis) -> None:
    """Associate a weapon whose center lies inside the person's box.

    Center containment is used rather than mere overlap so two people standing
    shoulder to shoulder cannot both claim the same weapon box. The strongest
    associated weapon wins, since several threat classes can be reported for
    one object after flip augmentation.
    """
    for weapon in analysis.weapons:
        wx = (weapon.bbox[0] + weapon.bbox[2]) / 2.0
        wy = (weapon.bbox[1] + weapon.bbox[3]) / 2.0
        x1, y1, x2, y2 = track.bbox
        if x1 <= wx <= x2 and y1 <= wy <= y2:
            track.weapon_detected = True
            track.weapon_confidence = max(track.weapon_confidence, weapon.confidence)


def _attach_falls(track: TrackedObject, analysis: FrameAnalysis) -> None:
    """Associate a fallen-posture detection whose center lies on the track.

    The fall model reports the fallen person as its own box; like weapons, the
    box center must belong to the person track so a fallen neighbour does not
    mark everyone as down.
    """
    for fall in analysis.falls:
        fx = (fall.bbox[0] + fall.bbox[2]) / 2.0
        fy = (fall.bbox[1] + fall.bbox[3]) / 2.0
        x1, y1, x2, y2 = track.bbox
        if x1 <= fx <= x2 and y1 <= fy <= y2:
            track.fall_detected = True
            track.fall_confidence = max(track.fall_confidence, fall.confidence)
            return


def _pose_shows_fall(keypoints: np.ndarray, bbox) -> bool:
    """Whether a pose skeleton inside ``bbox`` has its head at ankle height.

    ``keypoints`` has shape ``(N, 17, 2)`` with COCO joint order (nose 0, ankles
    15/16). A skeleton belongs to the track when its nose falls inside the
    person's bounding box. Missing joints are reported as ``0`` by the pose
    runner and are skipped rather than treated as a real coordinate.
    """
    x1, y1, x2, y2 = bbox

    for skeleton in keypoints:
        if len(skeleton) < 17:
            continue

        nose_x, nose_y = skeleton[0]
        if nose_x <= 0 or nose_y <= 0:
            continue
        if not (x1 <= nose_x <= x2 and y1 <= nose_y <= y2):
            continue

        ankles = [skeleton[15][1], skeleton[16][1]]
        ankles = [ankle for ankle in ankles if ankle > 0]
        if not ankles:
            continue

        if nose_y > (sum(ankles) / len(ankles)) * 0.7:
            return True

    return False
