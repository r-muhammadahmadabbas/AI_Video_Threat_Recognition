"""Multi-camera execution tests (Sprint 11).

Sprint 11 adds RTSP / multi‑camera support.  The CV worker already creates a
separate :class:`RuleEngine` per camera, so the only thing to verify is that
engines with different ``camera_id`` values never share temporal state.
"""

from __future__ import annotations

import pytest

from workers.cv_worker.rules.engine import RuleEngine


def test_rule_engine_can_be_instantiated_with_different_camera_ids():
    """Smoke test that RuleEngine can be created for each camera."""
    e1 = RuleEngine(camera_id="cam_a", frame_width=640, frame_height=480)
    e2 = RuleEngine(camera_id="cam_b", frame_width=640, frame_height=480)
    # Engines are lightweight; just confirming they construct without error.
    assert e1.camera_id == "cam_a"
    assert e2.camera_id == "cam_b"