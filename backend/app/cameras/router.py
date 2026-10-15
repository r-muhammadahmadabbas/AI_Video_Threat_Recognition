from datetime import datetime

import cv2
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_active_user, require_role
from app.db.models import Camera, CameraSourceType, CameraStatus, User, UserRole
from app.db.session import get_session_dependency
from app.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/cameras", tags=["cameras"])


class CameraBase(BaseModel):
    name: str
    source_type: CameraSourceType
    source_url: str
    username: str | None = None
    password: str | None = None
    inference_enabled: bool = True
    inference_fps: float = 5.0
    config_json: dict = {}


class CameraCreate(CameraBase):
    pass


class CameraUpdate(BaseModel):
    name: str | None = None
    source_url: str | None = None
    username: str | None = None
    password: str | None = None
    is_active: bool | None = None
    inference_enabled: bool | None = None
    inference_fps: float | None = None
    config_json: dict | None = None


class CameraResponse(CameraBase):
    id: int
    status: CameraStatus
    fps: float | None
    width: int | None
    height: int | None
    is_active: bool
    owner_id: int | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CameraListResponse(BaseModel):
    items: list[CameraResponse]
    total: int
    page: int
    page_size: int


@router.post("", response_model=CameraResponse, status_code=status.HTTP_201_CREATED)
async def create_camera(
    camera_data: CameraCreate,
    session: AsyncSession = Depends(get_session_dependency),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> Camera:
    camera = Camera(
        **camera_data.model_dump(),
        owner_id=current_user.id if current_user.role != UserRole.ADMIN else None,
    )
    session.add(camera)
    await session.commit()
    await session.refresh(camera)
    logger.info("Camera created", camera_id=camera.id, name=camera.name, by=current_user.id)
    return camera


@router.get("", response_model=CameraListResponse)
async def list_cameras(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_active: bool | None = None,
    status: CameraStatus | None = None,
    session: AsyncSession = Depends(get_session_dependency),
    current_user: User = Depends(get_current_active_user),
) -> CameraListResponse:
    query = select(Camera)
    if current_user.role != UserRole.ADMIN:
        query = query.where(Camera.owner_id == current_user.id)
    if is_active is not None:
        query = query.where(Camera.is_active == is_active)
    if status is not None:
        query = query.where(Camera.status == status)

    total_result = await session.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar()

    query = query.order_by(Camera.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(query)
    cameras = result.scalars().all()

    return CameraListResponse(items=list(cameras), total=total, page=page, page_size=page_size)


@router.get("/{camera_id}", response_model=CameraResponse)
async def get_camera(
    camera_id: int,
    session: AsyncSession = Depends(get_session_dependency),
    current_user: User = Depends(get_current_active_user),
) -> Camera:
    query = select(Camera).where(Camera.id == camera_id)
    if current_user.role != UserRole.ADMIN:
        query = query.where(Camera.owner_id == current_user.id)
    result = await session.execute(query)
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera


@router.patch("/{camera_id}", response_model=CameraResponse)
async def update_camera(
    camera_id: int,
    camera_data: CameraUpdate,
    session: AsyncSession = Depends(get_session_dependency),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> Camera:
    query = select(Camera).where(Camera.id == camera_id)
    if current_user.role != UserRole.ADMIN:
        query = query.where(Camera.owner_id == current_user.id)
    result = await session.execute(query)
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    update_data = camera_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(camera, field, value)

    await session.commit()
    await session.refresh(camera)
    logger.info("Camera updated", camera_id=camera.id, by=current_user.id)
    return camera


@router.delete("/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_camera(
    camera_id: int,
    session: AsyncSession = Depends(get_session_dependency),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> None:
    query = select(Camera).where(Camera.id == camera_id)
    result = await session.execute(query)
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    await session.delete(camera)
    await session.commit()
    logger.info("Camera deleted", camera_id=camera_id, by=current_user.id)


@router.get("/{camera_id}/snapshot")
async def get_camera_snapshot(
    camera_id: int,
    session: AsyncSession = Depends(get_session_dependency),
    current_user: User = Depends(get_current_active_user),
) -> Response:
    """Return a single JPEG frame from the camera's video stream."""
    query = select(Camera).where(Camera.id == camera_id)
    if current_user.role != UserRole.ADMIN:
        query = query.where(Camera.owner_id == current_user.id)
    result = await session.execute(query)
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    # Open the video source and grab one frame
    cap = cv2.VideoCapture(str(camera.source_url))
    if camera.username and camera.password:
        # For RTSP with auth, the URL already contains credentials
        pass

    if not cap.isOpened():
        raise HTTPException(status_code=503, detail="Could not open camera stream")

    try:
        ret, frame = cap.read()
        if not ret or frame is None:
            raise HTTPException(status_code=503, detail="Failed to read frame from camera")
        ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not ok:
            raise HTTPException(status_code=500, detail="Failed to encode frame")
        return Response(content=encoded.tobytes(), media_type="image/jpeg")
    finally:
        cap.release()
