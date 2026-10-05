"""Shared rule types: the contract every behavioural rule implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from workers.cv_worker.rules.config import ZoneConfig
from workers.cv_worker.rules.geometry import Polygon
from workers.cv_worker.tracker import TrackedObject


@dataclass(frozen=True)
class Zone:
    """A polygon zone as the rule engine sees it, in pixel space."""

    zone_id: str
    name: str
    polygon: Polygon
    is_active: bool = True
    config: ZoneConfig = field(default_factory=ZoneConfig)


@dataclass
class ZoneRuntime:
    """A zone plus its derived hysteresis rings.

    The expanded and shrunken rings are computed once when the zone is bound to
    a frame size rather than on every frame, since they only depend on the
    polygon and the margin multipliers.
    """

    zone: Zone
    expanded: Polygon
    shrunk: Polygon


@dataclass(frozen=True)
class TrackObservation:
    """One track as seen in one frame, against one zone."""

    track: TrackedObject
    inside_expanded: bool
    inside_shrunk: bool
    probe_point: tuple[float, float]

    @property
    def definitively_inside(self) -> bool:
        """Inside even by the conservative test, so definitely not leaving."""
        return self.inside_shrunk

    @property
    def definitively_outside(self) -> bool:
        """Outside even by the permissive test, so definitely not inside."""
        return not self.inside_expanded


@dataclass
class RuleTrigger:
    """A rule firing. One trigger becomes at most one incident."""

    rule_id: str
    rule_name: str
    zone_id: str
    zone_name: str
    tracker_id: int
    timestamp: float
    severity: str
    confidence: float
    details: dict[str, Any] = field(default_factory=dict)


class BehaviorRule(ABC):
    """A rule that consumes per-frame track observations and emits triggers.

    Concrete rules declare their identity (``rule_id``, ``rule_name``) as
    dataclass fields. The ABC deliberately does not declare them as abstract
    properties, because ``dataclasses`` resolves a field default by attribute
    lookup and would pick up an inherited property object as that default.
    """

    @abstractmethod
    def update(
        self, observations: list[TrackObservation], timestamp: float
    ) -> list[RuleTrigger]:
        """Advance the rule's temporal state and return any new triggers."""

    @abstractmethod
    def reset(self) -> None:
        """Drop all temporal state. Called when a zone is edited or unbound."""


def probe_point_for(track: TrackedObject, choice: str) -> tuple[float, float]:
    """Return the point of the track used for zone containment.

    ``bottom_center`` approximates the subject's feet, which is what an
    operator uses to judge whether someone has stepped into a zone.
    """
    if choice == "center":
        return track.center
    return track.bottom_center