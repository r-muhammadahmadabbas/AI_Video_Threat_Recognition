from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import get_current_active_user, require_role
from app.db.session import get_session_dependency
from app.db.models import Incident, IncidentStatus, ThreatRuleSeverity, Camera, User, UserRole
from app.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/incidents", tags=["incidents"])


class IncidentResponse(BaseModel):
    id: int
    camera_id: int
    zone_id: Optional[int]
    rule_id: Optional[int]
    event_type: str
    severity: ThreatRuleSeverity
    status: IncidentStatus
    first_seen_at: datetime
    last_seen_at: datetime
    confidence: float
    model_version: str
    rule_version: int
    track_ids: List[int]
    snapshot_uri: Optional[str]
    clip_uri: Optional[str]
    verified_by_id: Optional[int]
    verified_at: Optional[datetime]
    notification_status: Optional[str]
    metadata_json: dict
    resolved_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class IncidentListResponse(BaseModel):
    items: List[IncidentResponse]
    total: int
    page: int
    page_size: int


class IncidentVerify(BaseModel):
    verified: bool  # true = verify, false = dismiss


@router.get("", response_model=IncidentListResponse)
async def list_incidents(
    camera_id: Optional[int] = None,
    event_type: Optional[str] = None,
    severity: Optional[ThreatRuleSeverity] = None,
    status: Optional[IncidentStatus] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session_dependency),
    current_user: User = Depends(get_current_active_user),
) -> IncidentListResponse:
    query = select(Incident).join(Camera)
    if current_user.role != UserRole.ADMIN:
        query = query.where(Camera.owner_id == current_user.id)
    if camera_id:
        query = query.where(Incident.camera_id == camera_id)
    if event_type:
        query = query.where(Incident.event_type == event_type)
    if severity:
        query = query.where(Incident.severity == severity)
    if status:
        query = query.where(Incident.status == status)
    if date_from:
        query = query.where(Incident.first_seen_at >= date_from)
    if date_to:
        query = query.where(Incident.first_seen_at <= date_to)

    total_result = await session.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar()

    query = query.order_by(desc(Incident.first_seen_at)).offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(query)
    incidents = result.scalars().all()

    return IncidentListResponse(items=list(incidents), total=total, page=page, page_size=page_size)


@router.get("/{incident_id}", response_model=IncidentResponse)
async def get_incident(
    incident_id: int,
    session: AsyncSession = Depends(get_session_dependency),
    current_user: User = Depends(get_current_active_user),
) -> Incident:
    query = select(Incident).join(Camera).where(Incident.id == incident_id)
    if current_user.role != UserRole.ADMIN:
        query = query.where(Camera.owner_id == current_user.id)
    result = await session.execute(query)
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.post("/{incident_id}/verify", response_model=IncidentResponse)
async def verify_incident(
    incident_id: int,
    verify_data: IncidentVerify,
    session: AsyncSession = Depends(get_session_dependency),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> Incident:
    query = select(Incident).join(Camera).where(Incident.id == incident_id)
    if current_user.role != UserRole.ADMIN:
        query = query.where(Camera.owner_id == current_user.id)
    result = await session.execute(query)
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    if incident.status not in (IncidentStatus.DETECTED, IncidentStatus.PENDING_REVIEW):
        raise HTTPException(status_code=400, detail=f"Cannot verify incident in status {incident.status}")

    incident.status = IncidentStatus.VERIFIED if verify_data.verified else IncidentStatus.DISMISSED
    incident.verified_by_id = current_user.id
    incident.verified_at = datetime.utcnow()
    incident.resolved_at = datetime.utcnow()

    await session.commit()
    await session.refresh(incident)
    logger.info("Incident verified", incident_id=incident.id, verified=verify_data.verified, by=current_user.id)
    return incident


@router.post("/{incident_id}/dismiss", response_model=IncidentResponse)
async def dismiss_incident(
    incident_id: int,
    session: AsyncSession = Depends(get_session_dependency),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> Incident:
    query = select(Incident).join(Camera).where(Incident.id == incident_id)
    if current_user.role != UserRole.ADMIN:
        query = query.where(Camera.owner_id == current_user.id)
    result = await session.execute(query)
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident.status = IncidentStatus.DISMISSED
    incident.verified_by_id = current_user.id
    incident.verified_at = datetime.utcnow()
    incident.resolved_at = datetime.utcnow()

    await session.commit()
    await session.refresh(incident)
    logger.info("Incident dismissed", incident_id=incident.id, by=current_user.id)
    return incident