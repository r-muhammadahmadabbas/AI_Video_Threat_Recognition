"""Default rules for an unconfigured phone live stream.

A browser stream has no administrator-authored zones or rules. It still needs
the same behavioural coverage as an uploaded clip, so the session runs every
rule against one full-frame zone. Incidents are filed against the virtual
camera, and the existing worker handles evidence capture exactly as it does for
an RTSP camera.
"""

from __future__ import annotations

from workers.cv_worker.camera_config import FULL_FRAME_ZONE_ID
from workers.cv_worker.rules.base import BehaviorRule, Zone
from workers.cv_worker.rules.config import (
    CrowdAnomalyConfig,
    FightConfig,
    LoiterConfig,
    PersonDownConfig,
    WeaponConfig,
)
from workers.cv_worker.rules.crowd import CrowdMotionRule
from workers.cv_worker.rules.fight import FightRule
from workers.cv_worker.rules.geometry import Polygon
from workers.cv_worker.rules.loitering import LoiterRule
from workers.cv_worker.rules.person_down import PersonDownRule
from workers.cv_worker.rules.weapon import WeaponRule


def full_frame_zone() -> Zone:
    return Zone(
        zone_id=FULL_FRAME_ZONE_ID,
        name="Full frame",
        polygon=Polygon.from_vertices(
            [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        ),
    )


def default_live_rules() -> list[BehaviorRule]:
    return [
        LoiterRule(
            rule_id="loitering",
            rule_name="Loitering",
            zone_id=FULL_FRAME_ZONE_ID,
            zone_name="Full frame",
            severity="low",
            config=LoiterConfig(),
        ),
        PersonDownRule(
            rule_id="person_down",
            rule_name="Person down",
            zone_id=FULL_FRAME_ZONE_ID,
            zone_name="Full frame",
            severity="high",
            config=PersonDownConfig(),
        ),
        WeaponRule(
            rule_id="weapon",
            rule_name="Weapon detected",
            zone_id=FULL_FRAME_ZONE_ID,
            zone_name="Full frame",
            severity="high",
            config=WeaponConfig(),
        ),
        FightRule(
            rule_id="fight",
            rule_name="Physical altercation",
            zone_id=FULL_FRAME_ZONE_ID,
            zone_name="Full frame",
            severity="high",
            config=FightConfig(),
        ),
        CrowdMotionRule(
            rule_id="crowd_anomaly",
            rule_name="Crowd anomaly",
            zone_id=FULL_FRAME_ZONE_ID,
            zone_name="Full frame",
            severity="medium",
            config=CrowdAnomalyConfig(),
        ),
    ]
