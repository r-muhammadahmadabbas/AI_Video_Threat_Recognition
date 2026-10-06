"""Tests for worker-side incident persistence.

The worker writes straight to the database (it is a machine actor with no
user session), so these tests drive the real SQLAlchemy stack against a
throwaway SQLite file rather than mocking the insert - that is the only way
to prove a trigger actually becomes a reviewable incident.
"""

import asyncio
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from workers.cv_worker.incident_sink import DatabaseIncidentSink, IncidentRecord


def _record(**overrides) -> IncidentRecord:
    base = dict(
        camera_id=3,
        event_type="zone_entry",
        severity="high",
        confidence=0.91,
        first_seen_at=datetime(2026, 1, 1, 12, 0, 0),
        last_seen_at=datetime(2026, 1, 1, 12, 0, 0),
        track_ids=(4,),
        model_version="yolo26n",
        metadata={"zone_name": "Server Room"},
    )
    base.update(overrides)
    return IncidentRecord(**base)


class TestIncidentRecord:
    def test_from_trigger_maps_epoch_to_naive_utc(self):
        ts = datetime(2026, 6, 1, 10, 30, 0, tzinfo=UTC).timestamp()
        record = IncidentRecord.from_trigger(
            camera_id=2,
            event_type="loitering",
            severity="medium",
            confidence=0.8,
            timestamp=ts,
            track_ids=(1,),
            model_version="yolo26n",
            metadata={"zone_id": "z1"},
        )
        assert record.first_seen_at == datetime(2026, 6, 1, 10, 30, 0)
        assert record.first_seen_at.tzinfo is None
        assert record.last_seen_at == record.first_seen_at
        assert record.track_ids == (1,)
        assert record.metadata["zone_id"] == "z1"


class TestDatabaseIncidentSink:
    def test_refuses_record_without_camera(self):
        sink = DatabaseIncidentSink()
        with pytest.raises(ValueError, match="camera id"):
            asyncio.run(sink._insert(_record(camera_id=None)))

    def test_files_incident_row(self, tmp_path):
        from app.db.base import Base
        from app.db.models import Incident

        engine = create_async_engine(
            f"sqlite+aiosqlite:///{tmp_path / 'sink.db'}"
        )
        maker = async_sessionmaker(engine, expire_on_commit=False)

        async def prepare_and_insert() -> None:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

        asyncio.run(prepare_and_insert())

        with patch("app.db.session.async_session_maker", maker):
            DatabaseIncidentSink().record(_record())

        async def fetch():
            async with maker() as session:
                result = await session.execute(select(Incident))
                return result.scalars().all()

        incidents = asyncio.run(fetch())
        assert len(incidents) == 1
        incident = incidents[0]
        assert incident.camera_id == 3
        assert incident.event_type == "zone_entry"
        assert incident.severity.value == "high"
        assert incident.status.value == "detected"
        assert incident.confidence == 0.91
        assert incident.track_ids == [4]
        assert incident.metadata_json["zone_name"] == "Server Room"

        asyncio.run(engine.dispose())