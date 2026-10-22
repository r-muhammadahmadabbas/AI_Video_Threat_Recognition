"""Rule engine: binds zones and behavioural rules to one camera (Sprint 3D).

Responsibilities:

* resolve a zone's stored polygon into this camera's frame pixel space;
* turn each track into containment readings for every rule bound to that zone;
* de-duplicate triggers into incidents, so one breach of one rule by one track
  opens a single incident rather than one per frame.

The engine owns **one camera**. Because a tracker also owns one camera, two
engines never share track identity or temporal state.

Hysteresis rings live on :class:`RuleBinding`, not on the zone, because the
margins that define them come from the rule's config: two rules on the same
zone may legitimately disagree about how close to the line counts as "inside".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from workers.cv_worker.rules.base import (
    BehaviorRule,
    RuleTrigger,
    TrackObservation,
    Zone,
    probe_point_for,
)
from workers.cv_worker.rules.geometry import InvalidPolygonError, Polygon

if TYPE_CHECKING:
    from workers.cv_worker.rules.config import ZoneConfig
    from workers.cv_worker.tracker import TrackedObject

# Dedup keys untouched for this long are dropped, so the mapping cannot grow
# without bound on a camera that runs for weeks.
_DEDUP_RETENTION_SECONDS = 3600.0


def zone_to_pixel_polygon(zone: Zone, frame_width: int, frame_height: int) -> Polygon:
    """Resolve a stored zone polygon into this frame's pixel coordinates.

    Normalized vertices are fractions of the frame and scale directly. Pixel
    vertices were authored against a specific resolution and are scaled
    proportionally, so a zone drawn at 720p still lands correctly on a 1080p
    stream.
    """
    config: ZoneConfig = zone.config

    if config.coordinate_space == "normalized":
        return zone.polygon.to_pixels(frame_width, frame_height)

    # ZoneConfig's validator guarantees a pixel-space zone carries both
    # reference sizes; re-checked here so the narrowing below is explicit
    # rather than relying on a validator that ran elsewhere.
    reference_width = config.reference_width
    reference_height = config.reference_height
    if reference_width is None or reference_height is None:
        raise InvalidPolygonError(
            f"zone '{zone.zone_id}' uses pixel coordinates without a reference size"
        )

    if reference_width == frame_width and reference_height == frame_height:
        return zone.polygon

    sx = frame_width / reference_width
    sy = frame_height / reference_height
    return Polygon.from_vertices([(x * sx, y * sy) for x, y in zone.polygon.vertices])


@dataclass
class RuleBinding:
    """One rule bound to one zone, with the rule's containment rings derived."""

    rule: BehaviorRule
    zone_id: str
    expanded: Polygon
    shrunk: Polygon

    def rederive(self, polygon: Polygon) -> None:
        entry, exit_ = self.rule.hysteresis_margins()
        self.expanded = polygon.scaled_about_centroid(entry)
        self.shrunk = polygon.scaled_about_centroid(exit_)


@dataclass
class RuleEngine:
    """Applies behavioural rules to one camera's tracked objects."""

    camera_id: str
    frame_width: int
    frame_height: int
    _zones: dict[str, Zone] = field(default_factory=dict, init=False)
    _bindings: list[RuleBinding] = field(default_factory=list, init=False)
    _last_incident: dict[tuple[str, str, int], float] = field(
        default_factory=dict, init=False
    )

    def load_zone(self, zone: Zone) -> Zone:
        """Register a zone, converting its polygon into this frame's pixels."""
        resolved = Zone(
            zone_id=zone.zone_id,
            name=zone.name,
            polygon=zone_to_pixel_polygon(zone, self.frame_width, self.frame_height),
            is_active=zone.is_active,
            config=zone.config,
        )
        self._zones[zone.zone_id] = resolved

        for binding in self._bindings_for(zone.zone_id):
            binding.rederive(resolved.polygon)
            binding.rule.bind_zone(resolved)

        return resolved

    def bind_rule(self, rule: BehaviorRule, zone_id: str) -> None:
        zone = self._zones.get(zone_id)
        if zone is None:
            raise KeyError(
                f"cannot bind rule '{rule.rule_id}': zone '{zone_id}' is not loaded"
            )

        rule.bind_zone(zone)
        binding = RuleBinding(
            rule=rule, zone_id=zone_id, expanded=zone.polygon, shrunk=zone.polygon
        )
        binding.rederive(zone.polygon)
        self._bindings.append(binding)

    def _bindings_for(self, zone_id: str) -> list[RuleBinding]:
        return [b for b in self._bindings if b.zone_id == zone_id]

    def process(
        self, tracks: list[TrackedObject], timestamp: float, dt: float = 0.0
    ) -> list[RuleTrigger]:
        """Run every bound rule and return triggers merged into incidents."""
        raw: list[RuleTrigger] = []

        for binding in self._bindings:
            zone = self._zones.get(binding.zone_id)
            if zone is None or not zone.is_active:
                continue

            raw.extend(
                binding.rule.update(
                    self._observations_for(binding, tracks), timestamp, dt
                )
            )

        return self._dedup(raw, timestamp)

    @staticmethod
    def _observations_for(
        binding: RuleBinding, tracks: list[TrackedObject]
    ) -> list[TrackObservation]:
        """Build containment readings for one rule on one zone.

        The rings and the probe point both come from the rule's config, so an
        administrator who switches a rule to ``center`` gets that behaviour
        without any other component needing to know.
        """
        point_choice = binding.rule.config.point
        observations = []

        for track in tracks:
            point = probe_point_for(track, point_choice)
            observations.append(
                TrackObservation(
                    track=track,
                    inside_expanded=binding.expanded.contains(point),
                    inside_shrunk=binding.shrunk.contains(point),
                    probe_point=point,
                )
            )

        return observations

    def _dedup(
        self, triggers: list[RuleTrigger], timestamp: float
    ) -> list[RuleTrigger]:
        """Merge repeated frames into one incident per key per window.

        The key is ``(rule, zone, track)``: the same subject breaching the same
        rule in the same zone repeatedly is one incident. Different subjects
        stay distinct, because two breaches are two things to review.
        """
        accepted: list[RuleTrigger] = []
        self._prune(timestamp)

        for trigger in triggers:
            key = (trigger.rule_id, trigger.zone_id, trigger.tracker_id)
            last = self._last_incident.get(key)

            if last is not None and timestamp - last < self._cooldown_for(trigger.rule_id):
                continue

            self._last_incident[key] = timestamp
            accepted.append(trigger)

        return accepted

    def _cooldown_for(self, rule_id: str) -> float:
        for binding in self._bindings:
            if binding.rule.rule_id == rule_id:
                return float(binding.rule.config.cooldown_seconds)
        return 0.0

    def _prune(self, timestamp: float) -> None:
        stale = [
            key
            for key, at in self._last_incident.items()
            if timestamp - at >= _DEDUP_RETENTION_SECONDS
        ]
        for key in stale:
            del self._last_incident[key]

    @property
    def zone_ids(self) -> list[str]:
        return list(self._zones)

    @property
    def bound_rule_ids(self) -> list[str]:
        return [binding.rule.rule_id for binding in self._bindings]

    def get_zone(self, zone_id: str) -> Zone | None:
        return self._zones.get(zone_id)

    def reset(self) -> None:
        """Drop all temporal state. Used when a zone is edited or unbound."""
        for binding in self._bindings:
            binding.rule.reset()
        self._last_incident.clear()
