"""Short-lived tokens for phone live-stream capture.

The phone has no account session. The dashboard creates a live session and
encodes a signed, scoped token into the QR code; the token only authorises
sending frames to that one session until it expires.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt

from app.config import settings

CAPTURE_TOKEN_TYPE = "live_capture"  # noqa: S105


class InvalidCaptureTokenError(Exception):
    """Raised when a live capture token is malformed or expired."""


def create_capture_token(
    *,
    session_id: str,
    owner_id: int,
    camera_id: int,
    expires_minutes: int = 60,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "type": CAPTURE_TOKEN_TYPE,
        "sid": session_id,
        "owner_id": owner_id,
        "camera_id": camera_id,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, settings.auth.secret_key, algorithm=settings.auth.algorithm)


def decode_capture_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.auth.secret_key,
            algorithms=[settings.auth.algorithm],
        )
    except JWTError as exc:
        raise InvalidCaptureTokenError("Invalid or expired capture token") from exc

    if payload.get("type") != CAPTURE_TOKEN_TYPE:
        raise InvalidCaptureTokenError("Invalid capture token type")
    if not payload.get("sid"):
        raise InvalidCaptureTokenError("Capture token is missing a session id")
    return payload
