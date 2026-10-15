"""Thresholds for behavioral threat rules."""

from __future__ import annotations

from dataclasses import field
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal


class ZoneConfig(BaseModel):
    """Thresholds for zone-based rules (altercation, crowd anomaly)."""

    model_config = ConfigDict(extra="forbid")

    entry_margin: float = Field(default=1.02, gt=0.0, le=2.0)
    exit_margin: float = Field(default=0.98, gt=0.0, le=2.0)
    point: Literal["bottom_center", "center"] = "bottom_center"


class AltercationConfig(BaseModel):
    """Thresholds for physical-altercation candidate detection (Sprint 6A/6B)."""

    model_config = ConfigDict(extra="forbid")

    dwell_seconds: float = Field(default=5.0, gt=0.0)
    min_confidence: float = Field(default=0.25, ge=0.0, le=1.0)
    cooldown_seconds: float = Field(default=300.0, ge=0.0)
    min_movement_px_per_s: float = Field(default=20.0, gt=0.0)
    min_relative_speed_px_per_s: float = Field(default=60.0, gt=0.0)
    speed_window_seconds: float = Field(default=1.0, gt=0.0)
    min_aggression_frames: int = Field(default=5, ge=1)
    min_confidence: float = Field(default=0.25, ge=0.0, le=1.0)
    cooldown_seconds: float = Field(default=300.0, ge=0.0)


class CrowdAnomalyConfig(BaseModel):
    """Thresholds for crowd anomaly candidate detection (Sprint 7C)."""

    model_config = ConfigDict(extra="forbid")

    observation_window_seconds: float = Field(default=2.0, gt=0.0)
    baseline_window_seconds: float = Field(default=30.0, gt=0.0)
    min_baseline_snapshots: int = Field(default=3, ge=1)
    min_tracks: int = Field(default=3, ge=1)
    score_threshold: float = Field(default=1.5, gt=0.0)
    min_duration_seconds: float = Field(default=3.0, gt=0.0)
    cooldown_seconds: float = Field(default=300.0, ge=0.0)
    weight_track_count: float = Field(default=1.0, ge=0.0)
    weight_mean_speed: float = Field(default=1.0, ge=0.0)
    weight_direction_dispersion: float = Field(default=1.0, ge=0.0)
    weight_mean_pair_distance: float = Field(default=1.0, ge=0.0)
