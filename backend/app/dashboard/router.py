"""Dashboard statistics endpoint (Sprint 5D)."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_active_user
from app.db.models import (
    Camera,
    CameraStatus,
    Incident,
    IncidentStatus,
    ThreatRuleSeverity,
    User,
    UserRole,
)
from app.db.session import get_session_dependency
from app.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class DashboardStatsResponse(BaseModel):
    total_cameras: int
    online_cameras: int
    total_incidents: int
    pending_incidents: int
    verified_incidents: int
    dismissed_incidents: int
    very_high_risk_incidents: int  # critical/high severity in detected/pending_review
    incidents_last_24h: int


@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    session: AsyncSession = Depends(get_session_dependency),
    current_user: User = Depends(get_current_active_user),
) -> DashboardStatsResponse:
    """Aggregate counts for the dashboard overview.

    Counts are scoped to the current user's cameras (admins see all).
    """
    base_camera = select(Camera)
    base_incident = select(Incident).join(Camera)

    if current_user.role != UserRole.ADMIN:
        base_camera = base_camera.where(Camera.owner_id == current_user.id)
        base_incident = base_incident.where(Camera.owner_id == current_user.id)

    # Camera counts
    total_cameras = (
        await session.execute(select(func.count()).select_from(base_camera.subquery()))
    ).scalar_one()
    online_cameras = (
        await session.execute(
            select(func.count()).select_from(
                base_camera.where(Camera.status == CameraStatus.ONLINE).subquery()
            )
        )
    ).scalar_one()

    # Incident counts
    total_incidents = (
        await session.execute(select(func.count()).select_from(base_incident.subquery()))
    ).scalar_one()
    pending_incidents = (
        await session.execute(
            select(func.count()).select_from(
                base_incident.where(Incident.status == IncidentStatus.PENDING_REVIEW).subquery()
            )
        )
    ).scalar_one()
    verified_incidents = (
        await session.execute(
            select(func.count()).select_from(
                base_incident.where(Incident.status == IncidentStatus.VERIFIED).subquery()
            )
        )
    ).scalar_one()
    dismissed_incidents = (
        await session.execute(
            select(func.count()).select_from(
                base_incident.where(Incident.status == IncidentStatus.DISMISSED).subquery()
            )
        )
    ).scalar_one()

    # Very high risk: critical or high severity AND in a mutable state (detected/pending_review)
    very_high_risk_incidents = (
        await session.execute(
            select(func.count()).select_from(
                base_incident.where(
                    Incident.severity.in_([ThreatRuleSeverity.CRITICAL, ThreatRuleSeverity.HIGH]),
                    Incident.status.in_([IncidentStatus.DETECTED, IncidentStatus.PENDING_REVIEW]),
                ).subquery()
            )
        )
    ).scalar_one()

    # Incidents in last 24h
    since = datetime.utcnow() - timedelta(hours=24)
    incidents_last_24h = (
        await session.execute(
            select(func.count()).select_from(
                base_incident.where(Incident.first_seen_at >= since).subquery()
            )
        )
    ).scalar_one()

    return DashboardStatsResponse(
        total_cameras=total_cameras,
        online_cameras=online_cameras,
        total_incidents=total_incidents,
        pending_incidents=pending_incidents,
        verified_incidents=verified_incidents,
        dismissed_incidents=dismissed_incidents,
        very_high_risk_incidents=very_high_risk_incidents,
        incidents_last_24h=incidents_last_24h,
    )
