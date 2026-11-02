"""Live phone-stream REST and WebSocket endpoints."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Response,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import select

from app.auth import get_current_active_user
from app.config import settings
from app.db.models import (
    Camera,
    CameraSourceType,
    CameraStatus,
    ThreatRule,
    User,
    UserRole,
    Zone,
)
from app.db.session import async_session_maker, get_session_dependency
from app.live.manager import LiveSession, manager
from app.live.tokens import (
    InvalidCaptureTokenError,
    create_capture_token,
    decode_capture_token,
)
from app.logging import get_logger
from workers.cv_worker.camera_config import build_runtime
from workers.cv_worker.live_rules import default_live_rules, full_frame_zone

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from workers.cv_worker.rules.base import BehaviorRule

logger = get_logger(__name__)

router = APIRouter(prefix="/live", tags=["live"])

LIVE_CAMERA_NAME = "Phone live stream"
CAPTURE_TOKEN_MINUTES = 60


class CreateLiveSession(BaseModel):
    camera_id: int | None = None


class LiveSessionResponse(BaseModel):
    id: str
    camera_id: int
    camera_name: str
    capture_token: str
    expires_at: datetime
    status: str


class LiveSessionStatus(BaseModel):
    id: str
    camera_id: int
    camera_name: str
    status: str


async def _owned_camera(camera_id: int, db: AsyncSession, user: User) -> Camera:
    camera = await db.get(Camera, camera_id)
    if camera is None or (user.role != UserRole.ADMIN and camera.owner_id != user.id):
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera


async def _live_camera(db: AsyncSession, user: User) -> Camera:
    result = await db.execute(
        select(Camera).where(
            Camera.owner_id == user.id,
            Camera.name == LIVE_CAMERA_NAME,
        )
    )
    camera = result.scalars().first()
    if camera is not None:
        return camera

    camera = Camera(
        name=LIVE_CAMERA_NAME,
        source_type=CameraSourceType.WEBCAM,
        source_url="live://phone",
        status=CameraStatus.ONLINE,
        owner_id=user.id,
        config_json={"virtual": "phone_live"},
    )
    db.add(camera)
    await db.commit()
    await db.refresh(camera)
    return camera


async def _runtime_rules(db: AsyncSession, camera: Camera) -> tuple[list[Zone], list[BehaviorRule]]:
    zone_rows = list(
        (await db.execute(select(Zone).where(Zone.camera_id == camera.id))).scalars().all()
    )
    rule_rows = list(
        (await db.execute(select(ThreatRule).where(ThreatRule.camera_id == camera.id)))
        .scalars()
        .all()
    )
    runtime = build_runtime(camera, zone_rows, rule_rows)
    if runtime.rules:
        return runtime.zones, runtime.rules

    # A fresh virtual camera has no administrator-authored configuration. Use
    # the same full-frame rule set as an uploaded clip so live incidents still
    # work out of the box.
    return [full_frame_zone()], default_live_rules()


@router.post(
    "/sessions",
    response_model=LiveSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_live_session(
    payload: CreateLiveSession,
    db: AsyncSession = Depends(get_session_dependency),
    current_user: User = Depends(get_current_active_user),
) -> LiveSessionResponse:
    if payload.camera_id is not None:
        camera = await _owned_camera(payload.camera_id, db, current_user)
    else:
        camera = await _live_camera(db, current_user)

    zones, rules = await _runtime_rules(db, camera)
    live = manager.create(
        owner_id=current_user.id,
        camera_id=camera.id,
        camera_name=camera.name,
        zones=zones,
        rules=rules,
    )
    token = create_capture_token(
        session_id=live.id,
        owner_id=current_user.id,
        camera_id=camera.id,
        expires_minutes=CAPTURE_TOKEN_MINUTES,
    )
    return LiveSessionResponse(
        id=live.id,
        camera_id=camera.id,
        camera_name=camera.name,
        capture_token=token,
        expires_at=datetime.now(UTC) + timedelta(minutes=CAPTURE_TOKEN_MINUTES),
        status=live.status,
    )


@router.get("/sessions/{session_id}", response_model=LiveSessionStatus)
async def get_live_session(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
) -> LiveSessionStatus:
    live = _owned_session(session_id, current_user)
    return LiveSessionStatus(
        id=live.id,
        camera_id=live.camera_id,
        camera_name=live.camera_name,
        status=live.status,
    )


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
async def stop_live_session(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
):
    _owned_session(session_id, current_user)
    await manager.stop(session_id)


def _owned_session(session_id: str, user: User) -> LiveSession:
    live = manager.get(session_id)
    if live is None or (user.role != UserRole.ADMIN and live.owner_id != user.id):
        raise HTTPException(status_code=404, detail="Live session not found")
    return live


async def _user_from_access_token(token: str) -> User | None:
    try:
        payload = jwt.decode(
            token,
            settings.auth.secret_key,
            algorithms=[settings.auth.algorithm],
        )
        if payload.get("type") != "access":
            return None
        email = payload.get("sub")
        if not email:
            return None
    except JWTError:
        return None

    async with async_session_maker() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
    return user if user is not None and user.is_active else None


@router.websocket("/sessions/{session_id}/ingest")
async def ingest_live_frames(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(...),
) -> None:
    try:
        payload = decode_capture_token(token)
    except InvalidCaptureTokenError:
        await websocket.close(code=4401)
        return

    live = manager.get(session_id)
    if live is None or payload.get("sid") != session_id:
        await websocket.close(code=4404)
        return

    await websocket.accept()
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
            data = message.get("bytes")
            if data:
                await live.submit_frame(data)
                continue
            text = message.get("text")
            if not text:
                continue
            try:
                command = json.loads(text)
            except json.JSONDecodeError:
                continue
            if command.get("type") == "stop":
                break
    except WebSocketDisconnect:
        pass
    finally:
        await live.phone_disconnected()


@router.websocket("/sessions/{session_id}/watch")
async def watch_live_session(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(...),
) -> None:
    user = await _user_from_access_token(token)
    if user is None:
        await websocket.close(code=4401)
        return

    live = manager.get(session_id)
    if live is None or (user.role != UserRole.ADMIN and live.owner_id != user.id):
        await websocket.close(code=4404)
        return

    await websocket.accept()
    viewer = live.add_viewer(websocket)
    await websocket.send_text(
        json.dumps(
            {
                "type": "status",
                "status": live.status,
                "camera_id": live.camera_id,
                "camera_name": live.camera_name,
            }
        )
    )
    try:
        while True:
            kind, payload = await viewer.queue.get()
            if kind == "bytes":
                await websocket.send_bytes(payload)  # type: ignore[arg-type]
            else:
                await websocket.send_text(payload)  # type: ignore[arg-type]
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        live.remove_viewer(viewer)


__all__ = ["manager", "router"]
