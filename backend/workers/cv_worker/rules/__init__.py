"""Behavioural threat rules for the CV worker.

Public surface:

* :mod:`geometry` - polygon containment and hysteresis scaling;
* :mod:`config` - typed, validated per-rule thresholds;
* :mod:`base` - the contract every rule implements;
* :mod:`restricted_zone`, :mod:`loitering` - concrete rules;
* :mod:`altercation`, :mod:`person_down` - pair and posture rules;
* :mod:`fight` - the violence classifier expressed as a temporal rule;
* :mod:`crowd` - crowd-level anomaly scoring;
* :mod:`engine` - binds zones and rules to one camera.
"""

from workers.cv_worker.rules.altercation import AltercationRule
from workers.cv_worker.rules.base import (
    BehaviorRule,
    RuleTrigger,
    TrackObservation,
    Zone,
    ZoneRuntime,
    probe_point_for,
)
from workers.cv_worker.rules.config import (
    AltercationConfig,
    CrowdAnomalyConfig,
    FightConfig,
    LoiterConfig,
    PersonDownConfig,
    WeaponConfig,
    ZoneConfig,
    ZoneEntryConfig,
    build_config,
)
from workers.cv_worker.rules.crowd import CrowdMotionRule
from workers.cv_worker.rules.engine import RuleEngine, zone_to_pixel_polygon
from workers.cv_worker.rules.fight import FightRule
from workers.cv_worker.rules.geometry import InvalidPolygonError, Polygon
from workers.cv_worker.rules.loitering import LoiterRule
from workers.cv_worker.rules.person_down import PersonDownRule
from workers.cv_worker.rules.restricted_zone import PresenceState, ZoneEntryRule
from workers.cv_worker.rules.weapon import WeaponRule

__all__ = [
    "AltercationConfig",
    "AltercationRule",
    "BehaviorRule",
    "CrowdAnomalyConfig",
    "CrowdMotionRule",
    "FightConfig",
    "FightRule",
    "InvalidPolygonError",
    "LoiterConfig",
    "LoiterRule",
    "PersonDownConfig",
    "PersonDownRule",
    "Polygon",
    "PresenceState",
    "RuleEngine",
    "RuleTrigger",
    "TrackObservation",
    "WeaponConfig",
    "WeaponRule",
    "Zone",
    "ZoneConfig",
    "ZoneEntryConfig",
    "ZoneEntryRule",
    "ZoneRuntime",
    "build_config",
    "probe_point_for",
    "zone_to_pixel_polygon",
]
