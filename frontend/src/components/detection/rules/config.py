"""Thresholds for rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class CrowdAnomalyConfig:
    """Thresholds for crowd anomaly candidate detection (Sprint 7C).

    Attributes:
        observation_window_seconds: how many frames of baseline are required before
            the rule is allowed to trigger. Prevents a camera warming up from
            alerting on its first moments.
        min_tracks: minimum active track count for the rule to be eligible at all.
            Below this the score is ignored, so sparse scenes never fire.
        score_threshold: weighted anomaly score above which the rule fires.
        min_duration_seconds: how long the score must stay above threshold before
            triggering. Filters single-frame bursts.
        cooldown_seconds: minimum gap between two incidents for the same track.
        point: which point of the bbox to use for zone containment (if zone-bound).
    """

    model_config = ConfigDict(extra="forbid")

    dwell_seconds: float = Field(default=30.0, gt=0.0)
    min_confidence: float = Field(default=0.25, ge=0.0, le=1.0)
    cooldown_seconds: float = Field(default=300.0, ge=0.0)
    point: Literal["bottom_center", "center"] = "bottom_center"

    @model_validator(mode="after")
    def _exit_must_be_tighter_than_entry(self) -> CrowdAnomalyConfig:
        _require_ordered_margins(self.entry_margin, self.exit_margin)
        return self


class AltercationConfig(BaseModel):
    """Thresholds for physical-altercation candidate detection (Sprint 6A/6B).

    The rule looks at pairs of tracked people who are both inside the bound
    zone. A pair counts as a candidate when it stays within a small center
    distance while both members move and the relative centroid speed stays
    high, evaluated over a rolling time window. Every threshold here is a
    number an administrator tunes per camera: what is suspicious in a corridor
    may be normal in a sports area.

    Attributes:
        entry_margin/exit_margin: hysteresis multipliers, as for every rule.
        point: which bbox point the engine tests against the zone polygon.
        max_pair_distance_px: maximum center distance between the two members
            of the pair for the pair to count as "nearby". Every rule config
            omits nonsense thresholds.
        min_movement_px_per_s: how far each member must travel per second for
            the pair to count as actively moving. Filters single-frame noise.
        min_relative_speed_px_per_s: minimum relative centroid speed of the
            pair. A constant 0 means two people standing still never trigger.
        speed_window_seconds: rolling window the velocity signals are measured
            over. Smaller windows are more sensitive to sudden movements;
            larger windows are more stable.
        min_aggression_frames: consecutive frames the score must stay above
            threshold before triggering. Filters single-frame noise.
        min_confidence: minimum detection confidence to consider at all.
        cooldown_seconds: minimum gap between two incidents for the same pair.
    """

    model_config = ConfigDict(extra="forbid")

    dwell_seconds: float = Field(default=5.0, gt=0.0)
    min_confidence: float = Field(default=0.25, ge=0.0, le=1.0)
    cooldown_seconds: float = Field(default=300.0, ge=0.0)
    point: Literal["bottom_center", "center"] = "bottom_center"

    @model_validator(mode="after")
    def _exit_must_be_tighter_than_entry(self) -> AltercationConfig:
        _require_ordered_margins(self.entry_margin, self.exit_margin)
        return self


class WeaponConfig(BaseModel):
    """Thresholds for weapon detection.

    Attributes:
        dwell_seconds: continuous residency time that counts as weapon alert.
        min_confidence: minimum detection confidence to consider.
        cooldown_seconds: minimum gap between two incidents for the same track.
        point: which point of the bbox to use for zone containment (if zone-bound).
    """

    model_config = ConfigDict(extra="forbid")

    dwell_seconds: float = Field(default=5.0, gt=0.0)
    min_confidence: float = Field(default=0.25, ge=0.0, le=1.0)
    cooldown_seconds: float = Field(default=300.0, ge=0.0)
    point: Literal["bottom_center", "center"] = "bottom_center"


class AltercationConfig(BaseModel):
    """Thresholds for physical-altercation candidate detection (Sprint 6A/6B).

    The rule looks at pairs of tracked people who are both inside the bound
    zone. A pair counts as a candidate when it stays within a small center
    distance while both members move and the relative centroid speed stays
    high, evaluated over a rolling time window. Every threshold here is a
    number an administrator tunes per camera: what is suspicious in a corridor
    may be normal in a sports area.

    Attributes:
        entry_margin/exit_margin: hysteresis multipliers, as for every rule.
        point: which bbox point the engine tests against the zone polygon.
        max_pair_distance_px: maximum center distance between the two members
            of the pair for the pair to count as "nearby". Every rule config
            omits nonsense thresholds.
        min_movement_px_per_s: how far each member must travel per second for
            the pair to count as actively moving. Filters single-frame noise.
        min_relative_speed_px_per_s: minimum relative centroid speed of the
            pair. A constant 0 means two people standing still never trigger.
        speed_window_seconds: rolling window the velocity signals are measured
            over. Smaller windows are more sensitive to sudden movements;
            larger windows are more stable.
        min_aggression_frames: consecutive frames the score must stay above
            threshold before triggering. Filters single-frame noise.
        min_confidence: minimum detection confidence to consider at all.
        cooldown_seconds: minimum gap between two incidents for the same pair.
    """

    model_config = ConfigDict(extra="forbid")

    dwell_seconds: float = Field(default=5.0, gt=0.0)
    min_confidence: float = Field(default=0.25, ge=0.0, le=1.0)
    cooldown_seconds: float = Field(default=300.0, ge=0.0)
    point: Literal["bottom_center", "center"] = "bottom_center"

    @model_validator(mode="after")
    def _exit_must_be_tighter_than_entry(self) -> AltercationConfig:
        _require_ordered_margins(self.entry_margin, self.exit_margin)
        return self