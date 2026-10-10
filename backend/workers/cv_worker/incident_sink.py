"""Persistence of rule triggers as reviewable incidents.

A rule firing in the CV worker is worthless to an operator until it exists as
an incident the dashboard can list, display and verify. The worker runs as its
own process, so it needs its own route to the database - going through the
HTTP API would mean a machine process holding user credentials it has no
business holding.

Sinks are injected rather than hard-coded so a worker can run without a
database (file replay, CI, experiments) and still produce useful logs.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol

from app.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Mapping

logger = get_logger(__name__)

__all__ = [
    "DatabaseIncidentSink",
    "EvidenceAttachment",
    "IncidentRecord",
    "IncidentSink",
    "LogIncidentSink",
]


@dataclass(frozen=True)
class IncidentRecord:
    """Everything a trigger knows, expressed without database types.

    The rule engine's ``rule_id``/``zone_id`` are per-worker strings with no
    database counterpart, so they travel as references in ``metadata`` and the
    numeric foreign keys stay unset rather than being guessed.
    """

    camera_id: int | None
    event_type: str
    severity: str
    confidence: float
    first_seen_at: datetime
    last_seen_at: datetime
    track_ids: tuple[int, ...]
    model_version: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_trigger(
        cls,
        *,
        camera_id: int | None,
        event_type: str,
        severity: str,
        confidence: float,
        timestamp: float,
        track_ids: tuple[int, ...],
        model_version: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> IncidentRecord:
        """Build a record from a rule trigger's epoch timestamp.

        Stored as naive UTC to match the rest of the schema, which uses
        ``datetime.utcnow()`` for review timestamps.
        """
        seen = datetime.fromtimestamp(timestamp, tz=UTC).replace(tzinfo=None)
        return cls(
            camera_id=camera_id,
            event_type=event_type,
            severity=severity,
            confidence=confidence,
            first_seen_at=seen,
            last_seen_at=seen,
            track_ids=track_ids,
            model_version=model_version,
            metadata=dict(metadata or {}),
        )


class IncidentSink(Protocol):
    """Receives incidents as they are triggered.

    ``record`` returns the stored incident's id (when persistence produced
    one) so the caller can attach evidence to the right row. Sinks that do not
    persist (logging) return ``None``.
    """

    def record(self, record: IncidentRecord) -> int | None: ...

    def attach_evidence(self, incident_id: int, attachment: EvidenceAttachment) -> None: ...


@dataclass(frozen=True)
class EvidenceAttachment:
    """A stored artifact linked to one incident, addressed by storage key."""

    key: str
    incident_id: int
    evidence_type: str = "clip"
    thumbnail_key: str | None = None
    duration_seconds: float | None = None
    size_bytes: int | None = None
    metadata_json: Mapping[str, Any] = field(default_factory=dict)


class LogIncidentSink:
    """Records nothing to storage.

    The default when the worker has no camera to file under - replaying a
    file that was never registered as a camera must not invent one.
    """

    def record(self, record: IncidentRecord) -> int | None:
        logger.warning(
            "Threat trigger (logged only, not filed)",
            camera_id=record.camera_id,
            event_type=record.event_type,
            severity=record.severity,
            confidence=record.confidence,
            metadata=dict(record.metadata),
        )
        return None

    def attach_evidence(self, incident_id: int, attachment: EvidenceAttachment) -> None:
        del incident_id  # nothing to attach to; the trigger was only logged
        logger.info(
            "Evidence captured (nothing to attach to; trigger was logged only)",
            evidence_type=attachment.evidence_type,
            key=attachment.key,
        )


class DatabaseIncidentSink:
    """Writes incidents through the application's own session factory.

    Shares the API's models and session setup, so schema changes cannot drift
    between the two processes.
    """

    # The camera id travels with each record, so one instance stays reusable
    # and a filed incident cannot drift from the camera that produced it.
    def record(self, record: IncidentRecord) -> int | None:
        return asyncio.run(self._insert(record))

    async def _insert(self, record: IncidentRecord) -> int:
        # Imported here rather than at module scope: importing the session
        # factory builds a database engine, and a worker replaying files
        # with no camera id should never pay for one.
        from app.db.models import (  # noqa: PLC0415
            Incident,
            IncidentStatus,
            ThreatRuleSeverity,
        )
        from app.db.session import async_session_maker  # noqa: PLC0415

        if record.camera_id is None:
            # Refuse rather than file an incident against camera id 0: a
            # misattributed threat is worse than an unfiled one.
            raise ValueError(
                "Cannot file an incident without a camera id "
                f"(event_type={record.event_type!r})"
            )

        incident = Incident(
            camera_id=record.camera_id,
            event_type=record.event_type,
            severity=ThreatRuleSeverity(record.severity),
            status=IncidentStatus.DETECTED,
            first_seen_at=record.first_seen_at,
            last_seen_at=record.last_seen_at,
            confidence=record.confidence,
            model_version=record.model_version,
            track_ids=list(record.track_ids),
            metadata_json=dict(record.metadata),
        )
        async with async_session_maker() as session:
            session.add(incident)
            await session.commit()
            await session.refresh(incident)
            incident_id = incident.id

        logger.warning(
            "Incident created",
            incident_id=incident_id,
            camera_id=record.camera_id,
            event_type=record.event_type,
            severity=record.severity,
            confidence=record.confidence,
        )
        return incident_id

    def attach_evidence(self, incident_id: int, attachment: EvidenceAttachment) -> None:
        asyncio.run(self._insert_evidence(incident_id, attachment))

    async def _insert_evidence(
        self, incident_id: int, attachment: EvidenceAttachment
    ) -> None:
        from app.db.models import IncidentEvidence  # noqa: PLC0415
        from app.db.session import async_session_maker  # noqa: PLC0415

        evidence = IncidentEvidence(
            incident_id=incident_id,
            evidence_type=attachment.evidence_type,
            uri=attachment.key,
            thumbnail_uri=attachment.thumbnail_key,
            duration_seconds=attachment.duration_seconds,
            size_bytes=attachment.size_bytes,
            metadata_json=dict(attachment.metadata_json),
        )
        async with async_session_maker() as session:
            session.add(evidence)
            await session.commit()

        logger.info(
            "Evidence attached",
            incident_id=incident_id,
            evidence_id=evidence.id,
            evidence_type=attachment.evidence_type,
            key=attachment.key,
        )
