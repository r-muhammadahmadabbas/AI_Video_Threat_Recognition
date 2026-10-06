"""Behavioural threat rules for the CV worker.

Public surface:

* :mod:`geometry` - polygon containment and hysteresis scaling;
* :mod:`config` - typed, validated per-rule thresholds;
* :mod:`base` - the contract every rule implements;
* :mod:`restricted_zone`, :mod:`loitering` - concrete rules;
* :mod:`engine` - binds zones and rules to one camera.
"""

from workers.cv_worker.rules.base import (
    BehaviorRule,
    RuleTrigger,
    TrackObservation,
    Zone,
    ZoneRuntime,
    probe_point_for,
)
from workers.cv_worker.rules.config import (
    LoiterConfig,
    ZoneConfig,
    ZoneEntryConfig,
    build_config,
)
from workers.cv_worker.rules.engine import RuleEngine, zone_to_pixel_polygon
from workers.cv_worker.rules.geometry import InvalidPolygonError, Polygon
from workers.cv_worker.rules.loitering import LoiterRule
from workers.cv_worker.rules.restricted_zone import PresenceState, ZoneEntryRule

__all__ = [
    "BehaviorRule",
    "InvalidPolygonError",
    "LoiterConfig",
    "LoiterRule",
    "Polygon",
    "PresenceState",
    "RuleEngine",
    "RuleTrigger",
    "TrackObservation",
    "Zone",
    "ZoneConfig",
    "ZoneEntryConfig",
    "ZoneEntryRule",
    "ZoneRuntime",
    "build_config",
    "probe_point_for",
    "zone_to_pixel_polygon",
]
