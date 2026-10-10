"""Typed rule configuration.

Every tunable used by the behavioural rules lives here so that thresholds are
per rule and per camera, editable by an administrator, and never hardcoded in
the detection code. Instances are normally built from the ``config_json``
column on ``ThreatRule`` and ``Zone``.

Unknown keys are rejected rather than ignored: a typo like ``loiter_seconds``
should fail loudly at load time instead of silently reverting to a default and
quietly never firing.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _require_ordered_margins(entry_margin: float, exit_margin: float) -> None:
    """Shared guard: the exit test must never be looser than the entry test.

    If ``exit_margin > entry_margin`` the two rings cross and the hysteresis
    band inverts, which makes a subject on the boundary flicker between inside
    and outside on successive frames - exactly the failure the band exists to
    prevent.
    """
    if exit_margin > entry_margin:
        raise ValueError(
            "exit_margin must be less than or equal to entry_margin, otherwise "
            "the hysteresis band inverts and a subject on the boundary flickers"
        )


class ZoneEntryConfig(BaseModel):
    """Thresholds for restricted-zone entry.

    Attributes:
        entry_margin: multiplier applied to expand the zone for the entry test.
            Slightly above ``1.0`` so a subject who is clearly across the line
            triggers without needing to be well inside.
        exit_margin: multiplier applied to shrink the zone for the exit test.
            Below ``1.0`` so a subject must clearly leave before the zone is
            considered vacated. The gap between the two is the hysteresis band
            that stops a subject standing on the boundary from oscillating.
        min_frames_in_zone: consecutive frames the track must be inside before an
            incident opens. Filters single-frame detection jitter.
        min_confidence: minimum detection confidence to consider at all.
        cooldown_seconds: minimum gap between two incidents for the same track
            in the same zone. Prevents one breach producing hundreds of alerts.
        point: which point of the bounding box to test against the polygon.
            ``bottom_center`` is the default because it approximates where the
            subject's feet are, which is what an operator judges as "inside".
        require_min_frames: consecutive frames inside before dwell time counts.
        entry_margin/exit_margin: hysteresis multipliers used to derive this
            rule's containment rings, exactly as for restricted-zone entry. Every
            rule needs them because every rule must decide a stable inside and
            outside state before it can judge duration or breach.
    """

    model_config = ConfigDict(extra="forbid")

    entry_margin: float = Field(default=1.02, gt=0.0, le=2.0)
    exit_margin: float = Field(default=0.98, gt=0.0, le=2.0)
    min_frames_in_zone: int = Field(default=2, ge=1)
    min_confidence: float = Field(default=0.25, ge=0.0, le=1.0)
    cooldown_seconds: float = Field(default=60.0, ge=0.0)
    point: Literal["bottom_center", "center"] = "bottom_center"

    @model_validator(mode="after")
    def _exit_must_be_tighter_than_entry(self) -> ZoneEntryConfig:
        _require_ordered_margins(self.entry_margin, self.exit_margin)
        return self


class LoiterConfig(BaseModel):
    """Thresholds for loitering.

    Attributes:
        dwell_seconds: continuous residency time that counts as loitering.
        grace_seconds: how long a brief exit keeps the residency clock alive.
            At zero any exit resets the timer, so a subject pacing in and out
            never accumulates dwell. With a positive grace, stepping just
            outside for a moment pauses the clock rather than clearing it, which
            stops a subject hovering on the line from having to restart, while
            still resetting if they really leave.
        min_confidence: minimum detection confidence to consider.
        cooldown_seconds: minimum gap between two incidents for the same track.
        point: which point of the bounding box to test against the polygon.
        require_min_frames: consecutive frames inside before dwell time counts.
            Stops a single noisy frame from starting a residency clock.
    """

    model_config = ConfigDict(extra="forbid")

    dwell_seconds: float = Field(default=30.0, gt=0.0)
    grace_seconds: float = Field(default=5.0, ge=0.0)
    min_confidence: float = Field(default=0.25, ge=0.0, le=1.0)
    cooldown_seconds: float = Field(default=300.0, ge=0.0)
    point: Literal["bottom_center", "center"] = "bottom_center"
    require_min_frames: int = Field(default=2, ge=1)
    entry_margin: float = Field(default=1.02, gt=0.0, le=2.0)
    exit_margin: float = Field(default=0.98, gt=0.0, le=2.0)

    @model_validator(mode="after")
    def _exit_must_be_tighter_than_entry(self) -> LoiterConfig:
        _require_ordered_margins(self.entry_margin, self.exit_margin)
        return self

    def exit_is_tolerated(self, exit_seconds: float) -> bool:
        """Whether an exit of this length keeps the residency clock alive.

        This single knob expresses the "brief exit" decision from the sprint
        plan. ``grace_seconds`` at zero means any exit breaks continuity, so
        pacing in and out never accumulates dwell time; a positive grace means a
        momentary step out merely pauses the clock.
        """
        return exit_seconds <= self.grace_seconds


class PersonDownConfig(BaseModel):
    """Thresholds for person-down (horizontal posture) detection.

    A person is considered "down" when their bounding box is wider than it is
    tall by a configurable margin. This is evaluated per-frame on the track's
    current bbox.

    Attributes:
        aspect_ratio_threshold: width / height ratio above which the track is
            considered horizontal. ``> 1.0`` means wider than tall.
        min_confidence: minimum detection confidence to consider.
        cooldown_seconds: minimum gap between two incidents for the same track.
        min_frames_down: consecutive frames the ratio must exceed the threshold
            before triggering. Filters single-frame pose jitter.
        point: which point of the bbox to use for zone containment (if zone-bound).
    """

    model_config = ConfigDict(extra="forbid")

    aspect_ratio_threshold: float = Field(default=1.2, gt=1.0, le=5.0)
    min_confidence: float = Field(default=0.25, ge=0.0, le=1.0)
    cooldown_seconds: float = Field(default=60.0, ge=0.0)
    min_frames_down: int = Field(default=3, ge=1)
    point: Literal["bottom_center", "center"] = "bottom_center"


class ZoneConfig(BaseModel):
    """Coordinate convention for a zone polygon.

    ``normalized`` means vertices are fractions of the frame (``0..1``) and are
    therefore resolution independent, which is what the API stores by default.
    ``pixel`` means vertices are absolute pixel coordinates for a specific frame
    size, so ``reference_width``/``reference_height`` are required to scale.
    """

    model_config = ConfigDict(extra="forbid")

    coordinate_space: Literal["normalized", "pixel"] = "normalized"
    reference_width: int | None = Field(default=None, gt=0)
    reference_height: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _pixel_space_needs_reference_size(self) -> ZoneConfig:
        if self.coordinate_space == "pixel" and (
            self.reference_width is None or self.reference_height is None
        ):
            raise ValueError(
                "coordinate_space='pixel' requires reference_width and reference_height"
            )
        return self


def build_config(model: type[BaseModel], raw: dict[str, Any] | None) -> BaseModel:
    """Build a validated config from a raw ``config_json`` mapping.

    ``None`` and an empty mapping both yield the documented defaults. Anything
    else is validated, so bad administrator input surfaces immediately.
    """
    if not raw:
        return model()
    return model.model_validate(raw)
