from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_active_user, require_role
from app.config import settings
from app.db.session import get_session_dependency
from app.db.models import IncidentEvidence, Incident, Camera, User, UserRole
from app.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/evidence", tags=["evidence"])


class EvidenceResponse(BaseModel):
    id: int
    incident_id: int
    evidence_type: str
    uri: str
    thumbnail_uri: Optional[str]
    duration_seconds: Optional[float]
    size_bytes: Optional[int]
    metadata_json: dict
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EvidenceListResponse(BaseModel):
    items: List[EvidenceResponse]
    total: int
    page: int
    page_size: int


@router.get("/incident/{incident_id}", response_model=EvidenceListResponse)
async def list_evidence_for_incident(
    incident_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session_dependency),
    current_user: User = Depends(get_current_active_user),
) -> EvidenceListResponse:
    query = select(IncidentEvidence).join(Incident).join(Camera).where(IncidentEvidence.incident_id == incident_id)
    if current_user.role != UserRole.ADMIN:
        query = query.where(Camera.owner_id == current_user.id)

    total_result = await session.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar()

    query = query.order_by(IncidentEvidence.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(query)
    evidence = result.scalars().all()

    return EvidenceListResponse(items=list(evidence), total=total, page=page, page_size=page_size)


@router.get("/{evidence_id}", response_model=EvidenceResponse)
async def get_evidence(
    evidence_id: int,
    session: AsyncSession = Depends(get_session_dependency),
    current_user: User = Depends(get_current_active_user),
) -> IncidentEvidence:
    query = select(IncidentEvidence).join(Incident).join(Camera).where(IncidentEvidence.id == evidence_id)
    if current_user.role != UserRole.ADMIN:
        query = query.where(Camera.owner_id == current_user.id)
    result = await session.execute(query)
    evidence = result.scalar_one_or_none()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")
    return evidence


@router.get("/{evidence_id}/file")
async def get_evidence_file(
    evidence_id: int,
    session: AsyncSession = Depends(get_session_dependency),
    current_user: User = Depends(get_current_active_user),
) -> FileResponse:
    query = select(IncidentEvidence).join(Incident).join(Camera).where(IncidentEvidence.id == evidence_id)
    if current_user.role != UserRole.ADMIN:
        query = query.where(Camera.owner_id == current_user.id)
    result = await session.execute(query)
    evidence = result.scalar_one_or_none()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")

    import os
    file_path = evidence.uri
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Evidence file not found on disk")

    media_type = "video/mp4" if evidence.evidence_type == "clip" else "image/jpeg"
    return FileResponse(file_path, media_type=media_type, filename=os.path.basename(file_path))


@router.get("/{evidence_id}/thumbnail")
async def get_evidence_thumbnail(
    evidence_id: int,
    session: AsyncSession = Depends(get_session_dependency),
    current_user: User = Depends(get_current_active_user),
) -> FileResponse:
    query = select(IncidentEvidence).join(Incident).join(Camera).where(IncidentEvidence.id == evidence_id)
    if current_user.role != UserRole.ADMIN:
        query = query.where(Camera.owner_id == current_user.id)
    result = await session.execute(query)
    evidence = result.scalar_one_or_none()
    if not evidence or not evidence.thumbnail_uri:
        raise HTTPException(status_code=404, detail="Thumbnail not found")

    import os
    file_path = evidence.thumbnail_uri
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Thumbnail file not found on disk")

    return FileResponse(file_path, media_type="image/jpeg", filename=os.path.basename(file_path))