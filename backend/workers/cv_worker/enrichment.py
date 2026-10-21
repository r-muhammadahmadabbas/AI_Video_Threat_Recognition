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

import math
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
        track.pose_checked = False
        track.pose_fall_detected = False
        track.violence_detected = False
        track.violence_checked = analysis.violence_checked

        _attach_weapons(track, analysis)
        _attach_falls(track, analysis)
        if analysis.violence:
            track.violence_detected = True
        if analysis.pose_keypoints is not None:
            pose_fall = _pose_posture(analysis.pose_keypoints, track.bbox)
            if pose_fall is not None:
                track.pose_checked = True
                track.pose_fall_detected = pose_fall
                if pose_fall:
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


def _pose_posture(keypoints: np.ndarray, bbox) -> bool | None:
    """Classify the pose skeleton associated with ``bbox`` as fallen/upright.

    ``keypoints`` has shape ``(N, 17, 2)`` with COCO joint order. A skeleton
    belongs to the track when its nose falls inside the person's bounding box.
    Missing joints are reported as ``0`` by the pose runner and are skipped.

    Returns ``None`` when no skeleton matches the track, otherwise whether the
    skeleton is plausibly horizontal with the head at ankle height. The
    plausibility checks matter: a close-up weapon can be misdetected as a
    person, and the pose model can then invent joints whose hips sit below the
    ankles. The old nose-vs-ankle test trusted that invalid skeleton and raised
    a person-down alert, so the joint chain is validated first.
    """
    x1, y1, x2, y2 = bbox
    bbox_height = max(1.0, y2 - y1)
    matched = False

    for skeleton in keypoints:
        if len(skeleton) < 17:
            continue

        nose_x, nose_y = skeleton[0]
        if nose_x <= 0 or nose_y <= 0:
            continue
        if not (x1 <= nose_x <= x2 and y1 <= nose_y <= y2):
            continue
        matched = True

        shoulders = _valid_points(skeleton, (5, 6))
        hips = _valid_points(skeleton, (11, 12))
        ankles = _valid_points(skeleton, (15, 16))
        if not shoulders or not hips or not ankles:
            continue

        shoulder_x, shoulder_y = _centroid(shoulders)
        hip_x, hip_y = _centroid(hips)
        _, ankle_y = _centroid(ankles)

        # Hips and knees cannot be below the ankles in a real standing or
        # fallen skeleton; this is the signature of pose hallucination on a
        # close-up object.
        if hip_y > ankle_y + 0.15 * bbox_height:
            continue
        knees = _valid_points(skeleton, (13, 14))
        if knees:
            _, knee_y = _centroid(knees)
            if knee_y > ankle_y + 0.15 * bbox_height:
                continue

        torso_length = math.hypot(hip_x - shoulder_x, hip_y - shoulder_y)
        if torso_length <= 1.0:
            continue

        torso_horizontal = abs(hip_y - shoulder_y) <= 0.5 * torso_length
        head_low = nose_y >= 0.7 * ankle_y
        return bool(torso_horizontal and head_low)

    return False if matched else None


def _valid_points(
    skeleton: np.ndarray, indices: tuple[int, ...]
) -> list[tuple[float, float]]:
    return [
        (float(skeleton[index][0]), float(skeleton[index][1]))
        for index in indices
        if skeleton[index][0] > 0 and skeleton[index][1] > 0
    ]


def _centroid(points: list[tuple[float, float]]) -> tuple[float, float]:
    return (
        sum(point[0] for point in points) / len(points),
        sum(point[1] for point in points) / len(points),
    )
