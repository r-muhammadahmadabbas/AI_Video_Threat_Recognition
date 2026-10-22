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
        assert cfg.dropout_grace_seconds == 1.0
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
        assert cfg.require_min_frames == 2
        assert cfg.stationary_min_frames == 15
        assert cfg.stationary_max_path_px == 4.0

    def test_rejects_zero_dwell(self):
        with pytest.raises(ValidationError):
            LoiterConfig(dwell_seconds=0)

    def test_rejects_negative_grace(self):
        with pytest.raises(ValidationError):
            LoiterConfig(grace_seconds=-1)

    def test_rejects_invalid_stationary_guard(self):
        with pytest.raises(ValidationError, match="stationary_min_frames"):
            LoiterConfig(stationary_min_frames=0)
        with pytest.raises(ValidationError, match="stationary_max_path_px"):
            LoiterConfig(stationary_max_path_px=-1.0)

    def test_exit_at_grace_boundary_is_tolerated(self):
        cfg = LoiterConfig(grace_seconds=5.0)
        assert cfg.exit_is_tolerated(5.0) is True

    def test_exit_just_beyond_grace_is_not_tolerated(self):
        cfg = LoiterConfig(grace_seconds=5.0)
        assert cfg.exit_is_tolerated(5.1) is False

    def test_zero_grace_rejects_any_exit(self):
        cfg = LoiterConfig(grace_seconds=0.0)
        assert cfg.exit_is_tolerated(0.0) is True
        assert cfg.exit_is_tolerated(0.001) is False

    def test_large_grace_tolerates_long_exit(self):
        cfg = LoiterConfig(grace_seconds=600.0)
        assert cfg.exit_is_tolerated(300.0) is True

    def test_loitering_carries_the_same_hysteresis_margins_as_entry(self):
        # Every rule needs a stable inside/outside decision before it can judge
        # duration, so loitering must expose margins too.
        cfg = LoiterConfig()
        assert cfg.entry_margin > cfg.exit_margin

    def test_rejects_inverted_hysteresis(self):
        with pytest.raises(ValidationError, match="hysteresis band inverts"):
            LoiterConfig(entry_margin=0.9, exit_margin=1.1)


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
