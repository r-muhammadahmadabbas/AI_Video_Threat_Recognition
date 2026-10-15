import re

with open("backend/workers/cv_worker/rules/config.py", "r") as f:
    content = f.read()

# Add dwell_seconds to WeaponConfig
content = content.replace(
    '    min_confidence: float = Field(default=0.25, ge=0.0, le=1.0)\n    cooldown_seconds: float = Field(default=300.0, ge=0.0)',
    '''    min_confidence: float = Field(default=0.25, ge=0.0, le=1.0)
    cooldown_seconds: float = Field(default=300.0, ge=0.0)
    dwell_seconds: float = Field(default=5.0, gt=0.0)'''
)

with open("backend/workers/cv_worker/rules/config.py", "w") as f:
    f.write(content)

print("config.py fixed")