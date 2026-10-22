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
        dropout_grace_seconds: how long a missing track keeps its presence
            state. Trackers commonly drop a detection for a frame or two while
            the subject has not actually left the zone. Reusing the state
            across that gap prevents the same entry from opening a second
            incident. An observed exit still clears state immediately; zero
            disables the grace window.
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
    dropout_grace_seconds: float = Field(default=1.0, ge=0.0)
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
        stationary_min_frames: minimum ``track.frames_seen`` before the
            stationary-object guard applies. A newly created track has not
            shown enough continuity to distinguish a person from a static
            false positive, so its dwell is judged normally until this many
            observations have accumulated.
        stationary_max_path_px: cumulative center-path length below which a
            sufficiently persistent track is treated as a stationary object
            rather than a person. Real people move (even if only slightly) and
            a person who loiters has usually walked to the spot, while a
            tripod, poster or other static false positive keeps a near-zero
            path. Set to zero to disable the guard.
    """

    model_config = ConfigDict(extra="forbid")

    dwell_seconds: float = Field(default=30.0, gt=0.0)
    grace_seconds: float = Field(default=5.0, ge=0.0)
    min_confidence: float = Field(default=0.25, ge=0.0, le=1.0)
    cooldown_seconds: float = Field(default=300.0, ge=0.0)
    point: Literal["bottom_center", "center"] = "bottom_center"
    require_min_frames: int = Field(default=2, ge=1)
    stationary_min_frames: int = Field(default=15, ge=1)
    stationary_max_path_px: float = Field(default=4.0, ge=0.0)
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
    current bbox and only for tracks that are inside the bound zone.

    Attributes:
        aspect_ratio_threshold: width / height ratio above which the track is
            considered horizontal. ``> 1.0`` means wider than tall.
        min_confidence: minimum detection confidence to consider.
        cooldown_seconds: minimum gap between two incidents for the same track.
        min_frames_down: consecutive frames the ratio must exceed the threshold
            before triggering. Filters single-frame pose jitter.
        min_track_frames: total observations a track must have before geometry
            alone can raise an incident. A wide box on a brand-new track is
            usually box jitter or a misdetected object, not a person who has
            been lying still; confident fall/pose evidence still bypasses this.
        upright_pose_veto_seconds: how long a checked, upright pose keeps
            vetoing geometry-only evidence. Crouching, sitting, bending and a
            shooting stance can all make the box wide while the skeleton is
            upright. Pose runs less often than person detection, so the veto
            has to outlive the pose frame; when the window expires, geometry
            still works as a fallback for cameras without usable pose.
        min_fall_confidence: minimum fall-model confidence that counts as
            evidence. The model runs at a lower threshold so weak hits can
            still veto fight alerts; only confident hits raise an incident.
        weak_fall_confidence: lower edge of the weak fall-model band. A single
            hit in this band is not an incident, but repeated hits can build
            smoothed evidence and recover falls whose best frame is below
            ``min_fall_confidence``. Must not exceed ``min_fall_confidence``.
        fall_smoothing_decay: weight kept on the previous weak-fall score. The
            score rises on a weak hit and decays otherwise, so an isolated
            crouch/sitting false hit cannot raise an incident.
        min_smoothed_fall_score: normalized weak-fall evidence required to
            trigger. Scores are normalized against ``min_fall_confidence``, so
            one incident-threshold hit would score 1.0; the default therefore
            needs at least two moderately weak hits to accumulate.
        point: which point of the bbox to use for zone containment (if zone-bound).
        entry_margin/exit_margin: hysteresis multipliers used to derive this
            rule's containment rings, as for every zone-bound rule.
    """

    model_config = ConfigDict(extra="forbid")

    aspect_ratio_threshold: float = Field(default=1.2, gt=1.0, le=5.0)
    min_confidence: float = Field(default=0.25, ge=0.0, le=1.0)
    cooldown_seconds: float = Field(default=60.0, ge=0.0)
    min_frames_down: int = Field(default=3, ge=1)
    min_track_frames: int = Field(default=3, ge=1)
    upright_pose_veto_seconds: float = Field(default=2.0, ge=0.0)
    min_fall_confidence: float = Field(default=0.60, ge=0.0, le=1.0)
    weak_fall_confidence: float = Field(default=0.40, ge=0.0, le=1.0)
    fall_smoothing_decay: float = Field(default=0.5, ge=0.0, lt=1.0)
    min_smoothed_fall_score: float = Field(default=0.60, gt=0.0, le=1.0)
    point: Literal["bottom_center", "center"] = "bottom_center"
    entry_margin: float = Field(default=1.02, gt=0.0, le=2.0)
    exit_margin: float = Field(default=0.98, gt=0.0, le=2.0)

    @model_validator(mode="after")
    def _exit_must_be_tighter_than_entry(self) -> PersonDownConfig:
        _require_ordered_margins(self.entry_margin, self.exit_margin)
        return self

    @model_validator(mode="after")
    def _weak_fall_edge_below_incident_edge(self) -> PersonDownConfig:
        if self.weak_fall_confidence > self.min_fall_confidence:
            raise ValueError(
                "weak_fall_confidence must not exceed min_fall_confidence, "
                "otherwise the weak-fall band is empty"
            )
        return self


class WeaponConfig(BaseModel):
    """Thresholds for weapon detection.

    Attributes:
        dwell_seconds: continuous residency time that counts as weapon alert.
        grace_seconds: how long a brief exit keeps the residency clock alive.
        min_confidence: minimum detection confidence to consider.
        cooldown_seconds: minimum gap between two incidents for the same track.
        point: which point of the bbox to use for zone containment (if zone-bound).
        entry_margin/exit_margin: hysteresis multipliers used to derive this
            rule's containment rings, as for every zone-bound rule.
    """

    model_config = ConfigDict(extra="forbid")

    dwell_seconds: float = Field(default=5.0, gt=0.0)
    grace_seconds: float = Field(default=0.0, ge=0.0)
    min_confidence: float = Field(default=0.25, ge=0.0, le=1.0)
    cooldown_seconds: float = Field(default=300.0, ge=0.0)
    point: Literal["bottom_center", "center"] = "bottom_center"
    entry_margin: float = Field(default=1.02, gt=0.0, le=2.0)
    exit_margin: float = Field(default=0.98, gt=0.0, le=2.0)

    @model_validator(mode="after")
    def _exit_must_be_tighter_than_entry(self) -> WeaponConfig:
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
            A pair only participates once both members are definitively in the
            zone, so subjects hovering on the line do not flicker.
        point: which bbox point the engine tests against the zone polygon.
        max_pair_distance_px: maximum distance between the two centers for the
            pair to count as "nearby". Above this the pair's history resets.
        min_movement_px_per_s: how far each member must travel per second for
            the pair to count as actively moving. Filters people standing close
            (just talking) while still flagging engaged motion.
        min_relative_speed_px_per_s: minimum relative centroid speed of the
            pair. A constant 0 means two people standing still never fires;
            the signal is about approach/agitation, not mere proximity.
        speed_window_seconds: the rolling window the velocity signals are
            measured over. Wider windows smooth single-frame jitter; narrower
            windows react faster.
        min_aggression_frames: consecutive frames on which all signals hold
            before a trigger opens. This is the "require persistence" part of
            the temporal rule, so a single fast approach is not enough.
        min_confidence: minimum detection confidence to consider at all.
        cooldown_seconds: minimum gap between two triggers for the same pair.
    """

    model_config = ConfigDict(extra="forbid")

    entry_margin: float = Field(default=1.02, gt=0.0, le=2.0)
    exit_margin: float = Field(default=0.98, gt=0.0, le=2.0)
    point: Literal["bottom_center", "center"] = "bottom_center"
    max_pair_distance_px: float = Field(default=150.0, gt=0.0)
    min_movement_px_per_s: float = Field(default=20.0, ge=0.0)
    min_relative_speed_px_per_s: float = Field(default=60.0, ge=0.0)
    speed_window_seconds: float = Field(default=1.0, gt=0.0)
    min_aggression_frames: int = Field(default=5, ge=1)
    min_confidence: float = Field(default=0.25, ge=0.0, le=1.0)
    cooldown_seconds: float = Field(default=180.0, ge=0.0)

    @model_validator(mode="after")
    def _exit_must_be_tighter_than_entry(self) -> AltercationConfig:
        _require_ordered_margins(self.entry_margin, self.exit_margin)
        return self


class FightConfig(BaseModel):
    """Thresholds for fight detection from the violence classifier.

    The classifier answers a per-frame question ("does this frame show a
    fight?"), which is noisy on its own. The rule turns it into an event by
    requiring a short run of consecutive positive frames and then opening one
    trigger per episode, with a cooldown.

    Because the classifier is frame-level, it also flags normal fast motion,
    crowds, hugging and camera shake. The interaction gate therefore requires
    two nearby moving people whose velocities differ, not an isolated track.
    Attributes:
        min_consecutive_frames: consecutive model-positive frames before a
            trigger opens. Two hits at the worker's cadence filter single-frame
            blips (someone crouching fast) without missing real fights.
        min_confidence: minimum person confidence to attribute the event to a
            track. The classifier itself has already made the decision.
        max_zone_tracks: maximum eligible tracks before the frame is treated
            as crowd movement rather than a fight, since a frame-level
            classifier marks everyone in a busy scene.
        max_pair_distance_px: maximum distance between two participants for
            their motion to count as an interaction.
        min_movement_px_per_s: each participant must move at least this fast;
            a fast person passing a stationary one is not a fight.
        min_relative_speed_px_per_s: the participants' velocity vectors must
            differ by this much; people moving together or hugging fail.
        speed_window_seconds: track history used to estimate velocity.
        point: which point of the bbox to use for zone containment.
        entry_margin/exit_margin: hysteresis multipliers used to derive this
            rule's containment rings, as for every zone-bound rule.
        fall_suppression_seconds: a fall trips the violence classifier too, so
            fight triggers are vetoed this long after a confident fall-model
            hit. Weak fall hits use ``weak_fall_suppression_seconds`` instead
            (a short veto for a single doubtful frame).
        weak_fall_suppression_seconds: veto window for low-confidence fall
            evidence, kept short so a bad fall frame cannot hide a fight.
        strong_fall_confidence: fall-model confidence from which the long veto
            applies.
        smoothing_decay: weight kept on the previous smoothed score. The score
            rises on a positive model frame and decays on a negative one, so a
            single missed classifier frame does not split one fight into two
            episodes. Zero disables smoothing and makes every checked frame a
            hard positive or negative.
        min_smoothed_score: smoothed evidence required to open a trigger.
        exit_smoothed_score: smoothed evidence below which an active episode
            closes. Keeping this below ``min_smoothed_score`` gives the score
            hysteresis, so a brief negative does not immediately end an alert.
        cooldown_seconds: minimum gap between two triggers.
    """

    model_config = ConfigDict(extra="forbid")

    min_consecutive_frames: int = Field(default=2, ge=1)
    min_confidence: float = Field(default=0.25, ge=0.0, le=1.0)
    max_zone_tracks: int = Field(default=8, ge=2)
    max_pair_distance_px: float = Field(default=150.0, gt=0.0)
    min_movement_px_per_s: float = Field(default=20.0, ge=0.0)
    min_relative_speed_px_per_s: float = Field(default=60.0, ge=0.0)
    speed_window_seconds: float = Field(default=1.0, gt=0.0)
    point: Literal["bottom_center", "center"] = "bottom_center"
    entry_margin: float = Field(default=1.02, gt=0.0, le=2.0)
    exit_margin: float = Field(default=0.98, gt=0.0, le=2.0)
    fall_suppression_seconds: float = Field(default=3.0, ge=0.0)
    weak_fall_suppression_seconds: float = Field(default=1.0, ge=0.0)
    strong_fall_confidence: float = Field(default=0.60, ge=0.0, le=1.0)
    smoothing_decay: float = Field(default=0.5, ge=0.0, lt=1.0)
    min_smoothed_score: float = Field(default=0.5, gt=0.0, le=1.0)
    exit_smoothed_score: float = Field(default=0.25, ge=0.0, lt=1.0)
    cooldown_seconds: float = Field(default=60.0, ge=0.0)

    @model_validator(mode="after")
    def _exit_must_be_tighter_than_entry(self) -> FightConfig:
        _require_ordered_margins(self.entry_margin, self.exit_margin)
        return self

    @model_validator(mode="after")
    def _score_exit_must_not_exceed_entry(self) -> FightConfig:
        if self.exit_smoothed_score > self.min_smoothed_score:
            raise ValueError(
                "exit_smoothed_score must not exceed min_smoothed_score, "
                "otherwise the smoothed evidence rings invert and an episode "
                "can close before it is allowed to open"
            )
        return self


class CrowdAnomalyConfig(BaseModel):
    """Thresholds for abnormal-crowd-movement candidate detection (Sprint 7A/7B).

    The rule aggregates per-frame crowd features over a short observation
    window, compares them to a rolling short-term baseline per camera, and
    emits a transparent weighted anomaly score. The score is the sum over the
    four features of ``weight * |current - baseline| / max(baseline, 1.0)``,
    so each feature's contribution is visible and tunable per camera (7D).

    Attributes:
        entry_margin/exit_margin: hysteresis multipliers, as for every rule.
        point: which bbox point the engine tests against the zone polygon.
        observation_window_seconds: rolling window the current features are
            averaged over. Shorter reacts faster; longer smooths frame noise.
        baseline_window_seconds: rolling window the baseline is estimated over.
            Must be longer than the observation window so the baseline reflects
            the "normal" behaviour just before the current moment, not the
            current behaviour itself.
        min_baseline_snapshots: how many frames of baseline are required before
            the rule is allowed to trigger. Prevents a camera warming up from
            alerting on its first moments.
        min_tracks: minimum active track count for the rule to be eligible at
            all. Below this the score is ignored, so sparse scenes never fire.
        min_confidence: minimum detection confidence to consider at all.
        score_threshold: weighted anomaly score above which the scene is a
            candidate. Tune per camera by replaying known clips (7D).
        min_duration_seconds: how long the score must stay above the threshold
            before a trigger opens. This is the persistence guard: a one-frame
            surge (e.g. a dropped track) must not alert.
        cooldown_seconds: minimum gap between two triggers for this zone.
        weight_track_count: contribution weight for the per-zone density feature
            (people per megapixel of zone footprint). The name is retained for
            configuration compatibility; density replaced the raw track count in
            the score, and raw count is now only used by ``min_tracks``.
        weight_mean_speed: contribution weight for the mean per-track speed.
        weight_direction_dispersion: contribution weight for the angular spread
            of track velocity directions.
        weight_mean_pair_distance: contribution weight for the mean pairwise
            center distance. This is the inverse proxy for zone density:
            a crowd packing together shows up as a sharp drop in pair distance.
    """

    model_config = ConfigDict(extra="forbid")

    entry_margin: float = Field(default=1.02, gt=0.0, le=2.0)
    exit_margin: float = Field(default=0.98, gt=0.0, le=2.0)
    point: Literal["bottom_center", "center"] = "bottom_center"
    observation_window_seconds: float = Field(default=2.0, gt=0.0)
    baseline_window_seconds: float = Field(default=30.0, gt=0.0)
    min_baseline_snapshots: int = Field(default=3, ge=1)
    min_tracks: int = Field(default=3, ge=1)
    min_confidence: float = Field(default=0.25, ge=0.0, le=1.0)
    score_threshold: float = Field(default=1.5, gt=0.0)
    min_duration_seconds: float = Field(default=3.0, gt=0.0)
    cooldown_seconds: float = Field(default=300.0, ge=0.0)
    weight_track_count: float = Field(default=1.0, ge=0.0)
    weight_mean_speed: float = Field(default=1.0, ge=0.0)
    weight_direction_dispersion: float = Field(default=1.0, ge=0.0)
    weight_mean_pair_distance: float = Field(default=1.0, ge=0.0)

    @model_validator(mode="after")
    def _baseline_must_be_longer_than_observation(self) -> CrowdAnomalyConfig:
        if self.baseline_window_seconds <= self.observation_window_seconds:
            raise ValueError(
                "baseline_window_seconds must be greater than "
                "observation_window_seconds, otherwise the baseline would "
                "reflect the current behaviour rather than the norm"
            )
        return self

    @model_validator(mode="after")
    def _exit_must_be_tighter_than_entry(self) -> CrowdAnomalyConfig:
        _require_ordered_margins(self.entry_margin, self.exit_margin)
        return self


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
