from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_active_user, require_role
from app.db.session import get_session_dependency
from app.db.models import Zone, ZoneType, Camera, User, UserRole
from app.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/zones", tags=["zones"])


class ZoneBase(BaseModel):
    name: str
    zone_type: ZoneType
    polygon: List[List[float]]
    is_active: bool = True
    config_json: dict = {}


class ZoneCreate(ZoneBase):
    camera_id: int


class ZoneUpdate(BaseModel):
    name: Optional[str] = None
    zone_type: Optional[ZoneType] = None
    polygon: Optional[List[List[float]]] = None
    is_active: Optional[bool] = None
    config_json: Optional[dict] = None


class ZoneResponse(ZoneBase):
    id: int
    camera_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ZoneListResponse(BaseModel):
    items: List[ZoneResponse]
    total: int
    page: int
    page_size: int


def verify_camera_access(camera_id: int, user: User, session: AsyncSession) -> Camera:
    from app.db.models import Camera
    query = select(Camera).where(Camera.id == camera_id)
    if user.role != UserRole.ADMIN:
        query = query.where(Camera.owner_id == user.id)
    camera = session.execute(query).scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera


@router.post("", response_model=ZoneResponse, status_code=status.HTTP_201_CREATED)
async def create_zone(
    zone_data: ZoneCreate,
    session: AsyncSession = Depends(get_session_dependency),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> Zone:
    verify_camera_access(zone_data.camera_id, current_user, session)
    zone = Zone(**zone_data.model_dump())
    session.add(zone)
    await session.commit()
    await session.refresh(zone)
    logger.info("Zone created", zone_id=zone.id, camera_id=zone.camera_id, type=zone.zone_type)
    return zone


@router.get("", response_model=ZoneListResponse)
async def list_zones(
    camera_id: Optional[int] = None,
    zone_type: Optional[ZoneType] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session_dependency),
    current_user: User = Depends(get_current_active_user),
) -> ZoneListResponse:
    query = select(Zone).join(Camera)
    if current_user.role != UserRole.ADMIN:
        query = query.where(Camera.owner_id == current_user.id)
    if camera_id:
        query = query.where(Zone.camera_id == camera_id)
    if zone_type:
        query = query.where(Zone.zone_type == zone_type)

    total_result = await session.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar()

    query = query.order_by(Zone.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(query)
    zones = result.scalars().all()

    return ZoneListResponse(items=list(zones), total=total, page=page, page_size=page_size)


@router.get("/{zone_id}", response_model=ZoneResponse)
async def get_zone(
    zone_id: int,
    session: AsyncSession = Depends(get_session_dependency),
    current_user: User = Depends(get_current_active_user),
) -> Zone:
    query = select(Zone).join(Camera).where(Zone.id == zone_id)
    if current_user.role != UserRole.ADMIN:
        query = query.where(Camera.owner_id == current_user.id)
    result = await session.execute(query)
    zone = result.scalar_one_or_none()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    return zone


@router.patch("/{zone_id}", response_model=ZoneResponse)
async def update_zone(
    zone_id: int,
    zone_data: ZoneUpdate,
    session: AsyncSession = Depends(get_session_dependency),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> Zone:
    query = select(Zone).join(Camera).where(Zone.id == zone_id)
    if current_user.role != UserRole.ADMIN:
        query = query.where(Camera.owner_id == current_user.id)
    result = await session.execute(query)
    zone = result.scalar_one_or_none()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")

    update_data = zone_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(zone, field, value)

    await session.commit()
    await session.refresh(zone)
    logger.info("Zone updated", zone_id=zone.id, by=current_user.id)
    return zone


@router.delete("/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_zone(
    zone_id: int,
    session: AsyncSession = Depends(get_session_dependency),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> None:
    query = select(Zone).join(Camera).where(Zone.id == zone_id)
    if current_user.role != UserRole.ADMIN:
        query = query.where(Camera.owner_id == current_user.id)
    result = await session.execute(query)
    zone = result.scalar_one_or_none()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")

    await session.delete(zone)
    await session.commit()
    logger.info("Zone deleted", zone_id=zone_id, by=current_user.id)