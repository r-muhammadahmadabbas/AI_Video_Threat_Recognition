from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_active_user
from app.config import settings
from app.db.models import Camera, Incident, IncidentEvidence, User, UserRole
from app.db.session import get_session_dependency
from app.evidence.storage import EvidenceStoreError, LocalEvidenceStore
from app.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/evidence", tags=["evidence"])


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    incident_id: int
    evidence_type: str
    uri: str
    thumbnail_uri: str | None
    duration_seconds: float | None
    size_bytes: int | None
    metadata_json: dict
    created_at: datetime
    updated_at: datetime


class EvidenceListResponse(BaseModel):
    items: list[EvidenceResponse]
    total: int
    page: int
    page_size: int


def _evidence_store() -> LocalEvidenceStore:
    """The store every evidence file is resolved through.

    Keys recorded in the database are relative paths; the store owns the root,
    so a tampered key can never point outside the evidence directory.
    """
    return LocalEvidenceStore(settings.video.evidence_dir)


async def _get_owned_evidence(
    session: AsyncSession, evidence_id: int, current_user: User
) -> IncidentEvidence:
    query = (
        select(IncidentEvidence)
        .join(Incident)
        .join(Camera)
        .where(IncidentEvidence.id == evidence_id)
    )
    if current_user.role != UserRole.ADMIN:
        query = query.where(Camera.owner_id == current_user.id)
    result = await session.execute(query)
    evidence = result.scalar_one_or_none()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")
    return evidence


def _resolve_evidence_file(evidence: IncidentEvidence) -> str:
    """The on-disk path for evidence, guaranteed inside the store root."""
    try:
        path = _evidence_store().resolve(evidence.uri)
    except EvidenceStoreError:
        raise HTTPException(
            status_code=404, detail="Evidence file not found on disk"
        ) from None

    if not Path(path).is_file():
        raise HTTPException(status_code=404, detail="Evidence file not found on disk")
    return path


def _parse_range(range_header: str | None, size: int) -> tuple[int, int] | None:
    """Parse a single ``bytes=start-end`` range; ``None`` when unsupported.

    Only single ranges are honoured - multi-range requests fall back to the
    whole file, which is valid per RFC 9110. A range starting past the end of
    the file is also rejected (the caller should reply 416).
    """
    if not range_header or not range_header.startswith("bytes="):
        return None
    spec = range_header[len("bytes=") :].strip()
    if "," in spec:
        return None
    try:
        start_s, separator, end_s = spec.partition("-")
        if not separator:
            return None
        if not start_s:
            start = max(0, size - int(end_s))
            end = size - 1
        else:
            start = int(start_s)
            end = int(end_s) if end_s else size - 1
    except ValueError:
        return None
    if start >= size:
        return None
    return (start, min(end, size - 1))


def _file_response(path: str, media_type: str, request: Request) -> Response:
    """Stream a file with single-range byte support for seeking playback."""
    size = _file_size(path)
    parsed = _parse_range(request.headers.get("range"), size)
    if parsed is None:
        return FileResponse(path, media_type=media_type, headers={"Accept-Ranges": "bytes"})

    start, end = parsed
    length = end - start + 1
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Range": f"bytes {start}-{end}/{size}",
        "Content-Length": str(length),
    }

    def generate() -> Iterator[bytes]:
        with Path(path).open("rb") as fh:
            fh.seek(start)
            remaining = length
            while remaining > 0:
                chunk = fh.read(min(262144, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    return StreamingResponse(
        generate(),
        status_code=status.HTTP_206_PARTIAL_CONTENT,
        media_type=media_type,
        headers=headers,
    )


def _file_size(path: str) -> int:
    return Path(path).stat().st_size


@router.get("/incident/{incident_id}", response_model=EvidenceListResponse)
async def list_evidence_for_incident(
    incident_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session_dependency),
    current_user: User = Depends(get_current_active_user),
) -> EvidenceListResponse:
    query = (
        select(IncidentEvidence)
        .join(Incident)
        .join(Camera)
        .where(IncidentEvidence.incident_id == incident_id)
    )
    if current_user.role != UserRole.ADMIN:
        query = query.where(Camera.owner_id == current_user.id)

    total_result = await session.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar_one()

    query = (
        query.order_by(IncidentEvidence.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(query)
    evidence = result.scalars().all()

    return EvidenceListResponse(
        items=[EvidenceResponse.model_validate(e) for e in evidence],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{evidence_id}", response_model=EvidenceResponse)
async def get_evidence(
    evidence_id: int,
    session: AsyncSession = Depends(get_session_dependency),
    current_user: User = Depends(get_current_active_user),
) -> IncidentEvidence:
    return await _get_owned_evidence(session, evidence_id, current_user)


@router.get("/{evidence_id}/file")
async def get_evidence_file(
    evidence_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session_dependency),
    current_user: User = Depends(get_current_active_user),
) -> Response:
    evidence = await _get_owned_evidence(session, evidence_id, current_user)
    path = _resolve_evidence_file(evidence)
    media_type = "video/mp4" if evidence.evidence_type == "clip" else "image/jpeg"
    return _file_response(path, media_type, request)


@router.get("/{evidence_id}/thumbnail")
async def get_evidence_thumbnail(
    evidence_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session_dependency),
    current_user: User = Depends(get_current_active_user),
) -> Response:
    evidence = await _get_owned_evidence(session, evidence_id, current_user)
    if not evidence.thumbnail_uri:
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    try:
        path = _evidence_store().resolve(evidence.thumbnail_uri)
    except EvidenceStoreError:
        raise HTTPException(status_code=404, detail="Thumbnail not found on disk") from None

    if not Path(path).is_file():
        raise HTTPException(status_code=404, detail="Thumbnail not found on disk")
    return _file_response(path, "image/jpeg", request)
