"""Tests for turning a camera's database config into worker runtime types."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from workers.cv_worker.camera_config import (
    FULL_FRAME_ZONE_ID,
    build_runtime,
)
from workers.cv_worker.rules.fight import FightRule
from workers.cv_worker.rules.person_down import PersonDownRule


def camera(**overrides):
    base = {
        "id": 7,
        "name": "Dock",
        "source_type": "file",
        "source_url": "dock.mp4",
        "width": 1280,
        "height": 720,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def zone_row(zone_id: int = 3, polygon=None, active: bool = True):
    return SimpleNamespace(
        id=zone_id,
        name="Restricted dock",
        polygon=polygon or [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]],
        is_active=active,
    )


def rule_row(
    rule_id: int,
    rule_type: str,
    *,
    zone_id: int | None = None,
    active: bool = True,
    severity: str = "high",
    config: dict | None = None,
):
    return SimpleNamespace(
        id=rule_id,
        name=rule_type.replace("_", " ").title(),
        rule_type=SimpleNamespace(value=rule_type),
        zone_id=zone_id,
        is_active=active,
        severity=SimpleNamespace(value=severity),
        config_json=config or {},
        cooldown_seconds=30,
    )


class TestBuildRuntime:
    def test_builds_zones_and_rules(self):
        runtime = build_runtime(camera(), [zone_row()], [rule_row(1, "fight", zone_id=3)])

        assert runtime.camera_id == 7
        assert runtime.source_url == "dock.mp4"
        assert [zone.zone_id for zone in runtime.zones] == ["3"]
        assert isinstance(runtime.rules[0], FightRule)
        assert runtime.rules[0].zone_id == "3"
        assert runtime.rules[0].config.cooldown_seconds == 30.0
        assert runtime.fight_enabled is True
        assert runtime.weapon_enabled is False

    def test_pixel_polygon_uses_camera_reference_size(self):
        runtime = build_runtime(
            camera(),
            [zone_row(polygon=[[10.0, 20.0], [600.0, 20.0], [600.0, 400.0]])],
            [],
        )

        zone = runtime.zones[0]
        assert zone.config.coordinate_space == "pixel"
        assert zone.config.reference_width == 1280
        assert zone.config.reference_height == 720

    def test_normalized_polygon_stays_normalized(self):
        runtime = build_runtime(camera(), [zone_row()], [])
        assert runtime.zones[0].config.coordinate_space == "normalized"

    def test_zone_bound_rules_need_the_zone(self):
        runtime = build_runtime(camera(), [], [rule_row(1, "loitering", zone_id=99)])
        assert runtime.rules == []

    def test_rule_without_zone_gets_full_frame_zone(self):
        runtime = build_runtime(
            camera(), [], [rule_row(1, "person_down")]
        )

        assert [zone.zone_id for zone in runtime.zones] == [FULL_FRAME_ZONE_ID]
        assert isinstance(runtime.rules[0], PersonDownRule)
        assert runtime.fall_enabled is True

    def test_inactive_rules_and_zones_are_skipped(self):
        runtime = build_runtime(
            camera(),
            [zone_row(active=False)],
            [rule_row(1, "fight", active=False)],
        )

        assert runtime.rules == []
        assert runtime.zones == []

    def test_weapon_rule_enables_weapon_model(self):
        runtime = build_runtime(
            camera(), [], [rule_row(1, "weapon")]
        )
        assert runtime.weapon_enabled is True

    def test_invalid_config_raises(self):
        with pytest.raises(ValueError, match="min_consecutive_frames"):
            build_runtime(
                camera(),
                [],
                [
                    rule_row(
                        1, "fight", config={"min_consecutive_frames": 0}
                    )
                ],
            )

    def test_polygon_with_fewer_than_three_points_raises(self):
        with pytest.raises(ValueError, match="fewer than 3"):
            build_runtime(camera(), [zone_row(polygon=[[0.1, 0.1]])], [])
