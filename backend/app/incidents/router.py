from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import get_current_active_user, require_role
from app.db.session import get_session_dependency
from app.db.models import (
    Camera,
    Incident,
    IncidentStatus,
    ThreatRule,
    ThreatRuleSeverity,
    User,
    UserRole,
    Zone,
)
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


class IncidentCreate(BaseModel):
    """A detection originating a new incident.

    Callers cannot choose a status: an incident always starts unreviewed so
    that no path can create one already marked verified.
    """

    camera_id: int
    event_type: str = Field(min_length=1, max_length=100)
    severity: ThreatRuleSeverity
    confidence: float = Field(ge=0.0, le=1.0)
    first_seen_at: datetime
    last_seen_at: datetime
    zone_id: int | None = None
    rule_id: int | None = None
    track_ids: list[int] = Field(default_factory=list)
    model_version: str = Field(min_length=1, max_length=100)
    metadata: dict = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


async def _owned_camera(camera_id: int, session: AsyncSession, user: User) -> Camera:
    """Load a camera, hiding existence from users who may not see it.

    A 404 rather than a 403 for someone else's camera stops an attacker
    probing which camera ids are real.
    """
    result = await session.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    if user.role != UserRole.ADMIN and camera.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera


async def _camera_owned_resource(
    model: type[Zone] | type[ThreatRule],
    resource_id: int,
    camera_id: int,
    session: AsyncSession,
    label: str,
) -> None:
    """Reject a zone or rule that belongs to a different camera.

    Attaching someone else's zone to an incident would record evidence
    against the wrong place, so the mismatch fails the request outright.
    """
    result = await session.execute(
        select(model.id).where(model.id == resource_id, model.camera_id == camera_id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=422,
            detail=f"{label} {resource_id} does not belong to camera {camera_id}",
        )


@router.post("", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
async def create_incident(
    payload: IncidentCreate,
    session: AsyncSession = Depends(get_session_dependency),
    current_user: User = Depends(get_current_active_user),
) -> Incident:
    await _owned_camera(payload.camera_id, session, current_user)
    if payload.zone_id is not None:
        await _camera_owned_resource(Zone, payload.zone_id, payload.camera_id, session, "Zone")
    if payload.rule_id is not None:
        await _camera_owned_resource(
            ThreatRule, payload.rule_id, payload.camera_id, session, "Rule"
        )

    incident = Incident(
        camera_id=payload.camera_id,
        zone_id=payload.zone_id,
        rule_id=payload.rule_id,
        event_type=payload.event_type,
        severity=payload.severity,
        status=IncidentStatus.DETECTED,
        first_seen_at=payload.first_seen_at,
        last_seen_at=payload.last_seen_at,
        confidence=payload.confidence,
        model_version=payload.model_version,
        track_ids=payload.track_ids,
        metadata_json=payload.metadata,
    )
    session.add(incident)
    await session.commit()
    await session.refresh(incident)
    logger.info(
        "Incident created",
        incident_id=incident.id,
        camera_id=incident.camera_id,
        event_type=incident.event_type,
        confidence=incident.confidence,
    )
    return incident


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