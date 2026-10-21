"""Load a camera's zones and threat rules from the database.

The live worker is started per camera. Its behaviour is administrator-authored:
which zones exist on that camera and which rules (and thresholds) are active.
This module turns those rows into the worker's own runtime types, so the run
loop never touches SQLAlchemy models.

The upload pipeline has no administrator zones, so it keeps its own hard-coded
full-frame rule set; this loader is only for cameras.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select

from app.logging import get_logger
from workers.cv_worker.rules.base import BehaviorRule, Zone
from workers.cv_worker.rules.config import (
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
from workers.cv_worker.rules.fight import FightRule
from workers.cv_worker.rules.geometry import Polygon
from workers.cv_worker.rules.loitering import LoiterRule
from workers.cv_worker.rules.person_down import PersonDownRule
from workers.cv_worker.rules.restricted_zone import ZoneEntryRule
from workers.cv_worker.rules.weapon import WeaponRule

logger = get_logger(__name__)

#: Synthetic zone for rules that are camera-wide rather than zone-bound.
FULL_FRAME_ZONE_ID = "camera-full-frame"

#: Default drawing surface when a camera has no stored resolution. Matches the
#: zones page's 640x480 fallback.
_FALLBACK_WIDTH = 640
_FALLBACK_HEIGHT = 480

#: Database rule type -> (config model, rule implementation).
_RULE_TYPES: dict[str, tuple[Any, Any]] = {
    "restricted_zone_entry": (ZoneEntryConfig, ZoneEntryRule),
    "loitering": (LoiterConfig, LoiterRule),
    "person_down": (PersonDownConfig, PersonDownRule),
    "weapon": (WeaponConfig, WeaponRule),
    "fight": (FightConfig, FightRule),
    "crowd_anomaly": (CrowdAnomalyConfig, CrowdMotionRule),
}


@dataclass(frozen=True)
class CameraRuntimeConfig:
    """Everything the worker needs from one camera's database rows."""

    camera_id: int
    name: str
    source_type: str
    source_url: str
    zones: list[Zone] = field(default_factory=list)
    rules: list[BehaviorRule] = field(default_factory=list)
    fight_enabled: bool = False
    weapon_enabled: bool = False
    fall_enabled: bool = False


def _ring_points(raw: Any) -> list[tuple[float, float]]:
    """Accept the point shapes the API and older rows can contain."""
    if not raw:
        return []
    points: list[tuple[float, float]] = []
    for item in raw:
        if isinstance(item, dict):
            points.append((float(item["x"]), float(item["y"])))
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            points.append((float(item[0]), float(item[1])))
        elif isinstance(item, (list, tuple)):
            # A nested ring of points: [[x, y], ...] or [{"x":..}, ...].
            points.extend(_ring_points(item))
        else:
            raise ValueError(f"Unsupported polygon point: {item!r}")
    return points


def _first_ring(raw: Any) -> list[tuple[float, float]]:
    """Polygons travel as a list of rings; rules use the outer ring only."""
    if raw and isinstance(raw[0], (list, tuple)) and raw[0] and isinstance(
        raw[0][0], (list, tuple, dict)
    ):
        return _ring_points(raw[0])
    return _ring_points(raw)


def _zone_from_row(row: Any, camera: Any) -> Zone:
    points = _first_ring(row.polygon)
    if len(points) < 3:
        raise ValueError(f"zone {row.id} has fewer than 3 points")

    pixel_space = any(abs(value) > 1.5 for point in points for value in point)
    if pixel_space:
        config = ZoneConfig(
            coordinate_space="pixel",
            reference_width=int(getattr(camera, "width", None) or _FALLBACK_WIDTH),
            reference_height=int(getattr(camera, "height", None) or _FALLBACK_HEIGHT),
        )
    else:
        config = ZoneConfig(coordinate_space="normalized")

    return Zone(
        zone_id=str(row.id),
        name=row.name,
        polygon=Polygon.from_vertices(points),
        is_active=bool(row.is_active),
        config=config,
    )


def _full_frame_zone() -> Zone:
    return Zone(
        zone_id=FULL_FRAME_ZONE_ID,
        name="Full frame",
        polygon=Polygon.from_vertices([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]),
        config=ZoneConfig(coordinate_space="normalized"),
    )


def _rule_kwargs(row: Any, zone: Zone) -> dict[str, Any]:
    raw_config = dict(getattr(row, "config_json", None) or {})
    cooldown = getattr(row, "cooldown_seconds", None)
    if cooldown is not None:
        raw_config.setdefault("cooldown_seconds", float(cooldown))
    severity = getattr(row, "severity", "medium")
    return {
        "rule_id": str(row.rule_type.value),
        "rule_name": row.name,
        "zone_id": zone.zone_id,
        "zone_name": zone.name,
        "severity": getattr(severity, "value", str(severity)),
        "config": raw_config,
    }


def _build_rule(row: Any, zone: Zone) -> BehaviorRule | None:
    rule_type = getattr(row.rule_type, "value", str(row.rule_type))
    spec = _RULE_TYPES.get(rule_type)
    if spec is None:
        logger.warning("Skipping rule type the worker cannot run", rule_type=rule_type)
        return None
    kwargs = _rule_kwargs(row, zone)
    raw = kwargs.pop("config")
    config_cls, rule_cls = spec
    return rule_cls(config=build_config(config_cls, raw), **kwargs)


def build_runtime(camera: Any, zone_rows: list[Any], rule_rows: list[Any]) -> CameraRuntimeConfig:
    """Turn DB rows into worker types; pure so it is testable without a DB."""
    zones = [_zone_from_row(row, camera) for row in zone_rows if row.is_active]
    by_id = {zone.zone_id: zone for zone in zones}

    rules: list[BehaviorRule] = []
    for row in rule_rows:
        if not row.is_active:
            continue
        zone_id = str(row.zone_id) if row.zone_id is not None else FULL_FRAME_ZONE_ID
        zone = by_id.get(zone_id)
        if zone is None:
            if zone_id != FULL_FRAME_ZONE_ID:
                logger.warning(
                    "Rule references an inactive or missing zone; skipping",
                    rule_id=row.id,
                    zone_id=row.zone_id,
                )
                continue
            zone = _full_frame_zone()
            by_id[zone.zone_id] = zone
            zones.append(zone)
        rule = _build_rule(row, zone)
        if rule is not None:
            rules.append(rule)

    enabled = {
        getattr(row.rule_type, "value", str(row.rule_type)) if row.is_active else ""
        for row in rule_rows
    }
    return CameraRuntimeConfig(
        camera_id=int(camera.id),
        name=camera.name,
        source_type=getattr(camera.source_type, "value", str(camera.source_type)),
        source_url=camera.source_url,
        zones=zones,
        rules=rules,
        fight_enabled="fight" in enabled,
        weapon_enabled="weapon" in enabled,
        fall_enabled="person_down" in enabled or "fight" in enabled,
    )


async def _load(camera_id: int) -> CameraRuntimeConfig:
    from app.db import models, session  # noqa: PLC0415 - avoids building an engine on file replay

    async with session.async_session_maker() as db:
        camera = await db.get(models.Camera, camera_id)
        if camera is None:
            raise ValueError(f"camera {camera_id} does not exist")
        zone_rows = list(
            (
                await db.execute(
                    select(models.Zone).where(models.Zone.camera_id == camera_id)
                )
            )
            .scalars()
            .all()
        )
        rule_rows = list(
            (
                await db.execute(
                    select(models.ThreatRule).where(
                        models.ThreatRule.camera_id == camera_id
                    )
                )
            )
            .scalars()
            .all()
        )
    return build_runtime(camera, zone_rows, rule_rows)


def load_camera_runtime(camera_id: int) -> CameraRuntimeConfig:
    """Read one camera's configuration. Raises when the camera is missing."""
    return asyncio.run(_load(camera_id))
