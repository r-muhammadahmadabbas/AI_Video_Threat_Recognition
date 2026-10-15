#!/usr/bin/env python3
"""Fix TypeScript errors in frontend files."""

import re

# Fix 1: rules/config.py - Add dwell_seconds to WeaponConfig
with open("backend/workers/cv_worker/rules/config.py", "r") as f:
    content = f.read()

content = content.replace(
    "    min_confidence: float = Field(default=0.25, ge=0.0, le=1.0)\n    cooldown_seconds: float = Field(default=300.0, ge=0.0)\n    point: Literal[\"bottom_center\", \"center\"] = \"bottom_center\"",
    "    min_confidence: float = Field(default=0.25, ge=0.0, le=1.0)\n    cooldown_seconds: float = Field(default=300.0, ge=0.0)\n    point: Literal[\"bottom_center\", \"center\"] = \"bottom_center\"    dwell_seconds: float = Field(default=5.0, gt=0.0)"
)

with open("backend/workers/cv_worker/rules/config.py", "w") as f:
    f.write(content)

print("config.py fixed")

# Fix 2: tests/test_weapon.py - Fix import
with open("backend/tests/test_weapon.py", "r") as f:
    content = f.read()

content = content.replace(
    "from workers.cv_worker.tracker import TrackedObject, TrackState",
    "from workers.cv_worker.tracker import TrackedObject, TrackState"
)

with open("backend/tests/test_weapon.py", "w") as f:
    f.write(content)

print("test_weapon.py fixed")

# Fix 3: tests/test_crowd_anomaly.py - Fix import
with open("backend/tests/test_crowd_anomaly.py", "r") as f:
    content = f.read()

content = content.replace(
    "from workers.cv_worker.tracker import TrackObservation, TrackedObject",
    "from workers.cv_worker.tracker import TrackObservation, TrackedObject, TrackState"
)

with open("backend/tests/test_crowd_anomaly.py", "w") as f:
    f.write(content)

print("test_crowd_anomaly.py fixed")

# Fix 4: rules/__init__.py - Add exports
with open("backend/workers/cv_worker/rules/__init__.py", "r") as f:
    content = f.read()

# Add WeaponConfig and WeaponRule to imports if not already there
if "from workers.cv_worker.rules.weapon import WeaponRule" not in content:
    content = content.replace(
        "from workers.cv_worker.rules.altercation import AltercationRule",
        "from workers.cv_worker.rules.altercation import AltercationRule\nfrom workers.cv_worker.rules.weapon import WeaponRule"
    )

# Add to __all__
if '"WeaponConfig"' not in content:
    content = content.replace(
        '"CrowdAnomalyConfig",',
        '"CrowdAnomalyConfig",\n    "WeaponConfig",'
    )
if '"WeaponRule"' not in content:
    content = content.replace(
        '"CrowdMotionRule",',
        '"CrowdMotionRule",\n    "WeaponRule",'
    )

with open("backend/workers/cv_worker/rules/__init__.py", "w") as f:
    f.write(content)

print("config.py and __init__.py fixed")