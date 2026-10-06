"""Shared rule types: the contract every behavioural rule implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from workers.cv_worker.rules.config import ZoneConfig

if TYPE_CHECKING:
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
    *properties*, because ``dataclasses`` resolves a field default by attribute
    lookup and would pick up an inherited property object as that default.

    The bare annotations below add no class attribute and create no dataclass
    field (``BehaviorRule`` is not itself a dataclass, so ``dataclasses`` never
    reads them); they exist so static checkers see the identity every rule has.
    """

    rule_id: str
    rule_name: str
    zone_id: str
    config: Any

    @abstractmethod
    def update(
        self, observations: list[TrackObservation], timestamp: float, dt: float = 0.0
    ) -> list[RuleTrigger]:
        """Advance the rule's temporal state and return any new triggers.

        ``timestamp`` is the capture time of the frame; ``dt`` is the seconds
        elapsed since the previous frame. Time-driven rules accumulate from
        ``dt`` rather than ``timestamp`` so that replaying a clip offline
        reproduces identical durations on every run.
        """

    def hysteresis_margins(self) -> tuple[float, float]:
        """``(entry_margin, exit_margin)`` used to derive this rule's rings.

        Concrete by default: every rule config exposes the same two fields,
        because every rule needs a stable inside/outside decision before it can
        judge duration or breach. Rules whose config omits them would raise, so
        this exists as one place to read them rather than duplicating the lookup.
        """
        config = self.config
        return float(config.entry_margin), float(config.exit_margin)

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
