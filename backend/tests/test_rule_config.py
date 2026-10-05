import pytest
from pydantic import ValidationError

from workers.cv_worker.rules.config import (
    LoiterConfig,
    ZoneConfig,
    ZoneEntryConfig,
    build_config,
)


class TestZoneEntryConfig:
    def test_defaults_are_documented_values(self):
        cfg = ZoneEntryConfig()
        assert cfg.entry_margin == 1.02
        assert cfg.exit_margin == 0.98
        assert cfg.min_frames_in_zone == 2
        assert cfg.min_confidence == 0.25
        assert cfg.cooldown_seconds == 60.0
        assert cfg.point == "bottom_center"

    def test_overrides_are_applied(self):
        cfg = ZoneEntryConfig(entry_margin=1.1, min_frames_in_zone=5)
        assert cfg.entry_margin == 1.1
        assert cfg.min_frames_in_zone == 5

    def test_rejects_inverted_hysteresis(self):
        with pytest.raises(ValidationError, match="hysteresis band inverts"):
            ZoneEntryConfig(entry_margin=0.9, exit_margin=1.1)

    def test_allows_equal_margins(self):
        cfg = ZoneEntryConfig(entry_margin=1.0, exit_margin=1.0)
        assert cfg.entry_margin == cfg.exit_margin

    def test_rejects_negative_margin(self):
        with pytest.raises(ValidationError):
            ZoneEntryConfig(entry_margin=-0.1)

    def test_rejects_confidence_above_one(self):
        with pytest.raises(ValidationError):
            ZoneEntryConfig(min_confidence=1.5)

    def test_rejects_zero_frames(self):
        with pytest.raises(ValidationError):
            ZoneEntryConfig(min_frames_in_zone=0)

    def test_rejects_unknown_key(self):
        with pytest.raises(ValidationError):
            ZoneEntryConfig(min_frame_in_zone=3)

    def test_rejects_invalid_point_choice(self):
        with pytest.raises(ValidationError):
            ZoneEntryConfig(point="top_left")


class TestLoiterConfig:
    def test_defaults(self):
        cfg = LoiterConfig()
        assert cfg.dwell_seconds == 30.0
        assert cfg.grace_seconds == 5.0
        assert cfg.reset_on_exit is True
        assert cfg.require_min_frames == 2

    def test_rejects_zero_dwell(self):
        with pytest.raises(ValidationError):
            LoiterConfig(dwell_seconds=0)

    def test_rejects_negative_grace(self):
        with pytest.raises(ValidationError):
            LoiterConfig(grace_seconds=-1)

    def test_residence_counts_inside_time(self):
        cfg = LoiterConfig(grace_seconds=5.0)
        assert cfg.residence_seconds(inside_seconds=30.0, outside_seconds=0.0) == 30.0

    def test_brief_exit_keeps_full_residence(self):
        cfg = LoiterConfig(grace_seconds=5.0)
        assert cfg.residence_seconds(inside_seconds=30.0, outside_seconds=3.0) == 30.0

    def test_exit_at_grace_boundary_keeps_residence(self):
        cfg = LoiterConfig(grace_seconds=5.0)
        assert cfg.residence_seconds(inside_seconds=30.0, outside_seconds=5.0) == 30.0

    def test_long_exit_discounts_time(self):
        cfg = LoiterConfig(grace_seconds=5.0)
        assert cfg.residence_seconds(inside_seconds=30.0, outside_seconds=10.0) == 20.0

    def test_residence_never_negative(self):
        cfg = LoiterConfig(grace_seconds=5.0)
        assert cfg.residence_seconds(inside_seconds=3.0, outside_seconds=60.0) == 0.0

    def test_zero_grace_discounts_any_exit(self):
        cfg = LoiterConfig(grace_seconds=0.0)
        assert cfg.residence_seconds(inside_seconds=30.0, outside_seconds=0.1) == 29.9


class TestZoneConfig:
    def test_normalized_needs_no_reference_size(self):
        cfg = ZoneConfig(coordinate_space="normalized")
        assert cfg.reference_width is None

    def test_pixel_space_requires_reference_size(self):
        with pytest.raises(ValidationError, match="requires reference_width"):
            ZoneConfig(coordinate_space="pixel")

    def test_pixel_space_with_reference_size(self):
        cfg = ZoneConfig(
            coordinate_space="pixel", reference_width=1920, reference_height=1080
        )
        assert cfg.reference_width == 1920

    def test_rejects_unknown_coordinate_space(self):
        with pytest.raises(ValidationError):
            ZoneConfig(coordinate_space="fractions")


class TestBuildConfig:
    def test_none_yields_defaults(self):
        cfg = build_config(ZoneEntryConfig, None)
        assert cfg.entry_margin == 1.02

    def test_empty_dict_yields_defaults(self):
        cfg = build_config(ZoneEntryConfig, {})
        assert cfg.entry_margin == 1.02

    def test_valid_overrides_applied(self):
        cfg = build_config(LoiterConfig, {"dwell_seconds": 12.5})
        assert cfg.dwell_seconds == 12.5

    def test_typo_in_config_fails_loudly(self):
        with pytest.raises(ValidationError):
            build_config(LoiterConfig, {"loiter_seconds": 12.5})

    def test_bad_type_fails(self):
        with pytest.raises(ValidationError):
            build_config(LoiterConfig, {"dwell_seconds": "thirty"})