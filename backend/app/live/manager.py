"""In-process live phone stream sessions.

Each session owns one :class:`~workers.cv_worker.main.CVWorker` thread, one
latest-frame source, and one fan-out queue per dashboard viewer. The browser
sends JPEG frames; inference runs through the exact same worker that handles
RTSP cameras, so incidents and evidence clips do not have a second code path.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
import uuid
from contextlib import suppress
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.config import settings
from app.evidence.storage import LocalEvidenceStore
from app.live.down_state import PERSON_DOWN_RULE_ID, DownStateTracker
from app.live.snapshots import remember_frame
from app.logging import get_logger
from workers.cv_worker.incident_sink import DatabaseIncidentSink
from workers.cv_worker.main import CVWorker
from workers.cv_worker.video_source import Frame, LiveFrameSource

if TYPE_CHECKING:
    from fastapi import WebSocket

    from workers.cv_worker.analyzer import FrameAnalysis
    from workers.cv_worker.detector import Detection
    from workers.cv_worker.rules.base import BehaviorRule, RuleTrigger, Zone
    from workers.cv_worker.tracker import TrackSnapshot

logger = get_logger(__name__)

ViewerItem = tuple[str, bytes | str]
IDLE_SESSION_SECONDS = 300.0
NO_FRAME_SECONDS = 900.0
CLEANUP_INTERVAL_SECONDS = 20.0


@dataclass
class Viewer:
    ws: WebSocket
    queue: asyncio.Queue[ViewerItem] = field(default_factory=lambda: asyncio.Queue(maxsize=2))


def _detection_payload(track: Any, timestamp: float) -> dict[str, Any]:
    fall = bool(track.fall_detected)
    return {
        "timestamp": round(timestamp, 2),
        "bbox": [round(float(value), 1) for value in track.bbox],
        "track_id": int(track.tracker_id),
        "class_name": "person",
        "confidence": round(float(track.confidence), 3),
        "is_threat": bool(track.weapon_detected or fall or track.violence_detected),
        "weapon": bool(track.weapon_detected),
        "weapon_conf": round(float(track.weapon_confidence), 3),
        "fall": fall,
        "violence": bool(track.violence_detected),
    }


class LiveSession:
    def __init__(
        self,
        *,
        owner_id: int,
        camera_id: int,
        camera_name: str,
        zones: list[Zone],
        rules: list[BehaviorRule],
    ) -> None:
        self.id = uuid.uuid4().hex
        self.owner_id = owner_id
        self.camera_id = camera_id
        self.camera_name = camera_name
        self.created_at = time.time()
        self.last_frame_at = self.created_at
        self.status = "waiting"
        self._loop = asyncio.get_running_loop()
        self._source = LiveFrameSource(f"live-{self.id}")
        self._worker = CVWorker(
            source_id=f"live-{self.id}",
            source_path="browser://phone",
            source_type="live",
            camera_id=camera_id,
            zones=zones,
            rules=rules,
            incident_sink=DatabaseIncidentSink(loop=self._loop),
            evidence_store=LocalEvidenceStore(settings.video.evidence_dir),
            enable_violence=any(rule.rule_id == "fight" for rule in rules),
            enable_weapon=any(rule.rule_id == "weapon" for rule in rules),
            enable_fall=any(rule.rule_id == "person_down" for rule in rules),
            video_source=self._source,
            on_processed=self._on_processed,
            on_trigger=self._on_trigger,
        )
        self._thread: threading.Thread | None = None
        self._viewers: list[Viewer] = []
        self._latest_frame: bytes | None = None
        self._latest_metadata: dict[str, Any] | None = None
        self._down_state = DownStateTracker()
        self._stopping = False

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._worker.start,
            name=f"live-session-{self.id}",
            daemon=True,
        )
        self._thread.start()

    async def submit_frame(self, data: bytes) -> None:
        if self._stopping or not data:
            return
        self._source.push_jpeg(data)
        self._latest_frame = data
        self.last_frame_at = time.time()
        remember_frame(self.camera_id, data)
        if self.status != "live":
            self.status = "live"
            self._broadcast_text({"type": "status", "status": "live"})
        self._broadcast("bytes", data)

    def add_viewer(self, ws: WebSocket) -> Viewer:
        viewer = Viewer(ws=ws)
        self._viewers.append(viewer)
        if self._latest_frame is not None:
            self._put(viewer, "bytes", self._latest_frame)
        if self._latest_metadata is not None:
            self._put(
                viewer,
                "text",
                json.dumps({**self._latest_metadata, "type": "metadata"}),
            )
        return viewer

    def remove_viewer(self, viewer: Viewer) -> None:
        if viewer in self._viewers:
            self._viewers.remove(viewer)

    async def phone_disconnected(self) -> None:
        """The phone tab closed. Keep the session so the same QR can reconnect."""
        if self._stopping:
            return
        self.status = "waiting"
        self._broadcast_text({"type": "status", "status": "waiting"})
        logger.info("Phone disconnected; session kept", session_id=self.id)

    async def stop(self) -> None:
        if self._stopping:
            return
        self._stopping = True
        self.status = "stopped"
        self._down_state.reset()
        self._source.release()
        await asyncio.to_thread(self._join_worker)
        self._broadcast_text({"type": "status", "status": "stopped"})
        for viewer in list(self._viewers):
            with suppress(Exception):
                await viewer.ws.close()
        self._viewers.clear()
        logger.info("Live session stopped", session_id=self.id, camera_id=self.camera_id)

    def is_stale(self, now: float) -> bool:
        if self.last_frame_at == self.created_at:
            return now - self.created_at > IDLE_SESSION_SECONDS
        return now - self.last_frame_at > NO_FRAME_SECONDS

    def _join_worker(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=10)

    def _on_processed(
        self,
        frame: Frame,
        snapshot: TrackSnapshot | None,
        detections: list[Detection],
        analysis: FrameAnalysis | None,
        triggers: list[RuleTrigger],
    ) -> None:
        del detections  # person boxes come from the tracker snapshot
        height, width = frame.data.shape[:2]
        timestamp = round(frame.timestamp, 2)
        tracks = snapshot.tracked if snapshot is not None else []
        down_states = self._down_state.update(
            timestamp=frame.timestamp,
            tracks=tracks,
            falls=analysis.falls if analysis is not None else [],
            triggers=triggers,
        )

        rows: list[dict[str, Any]] = []
        rows.extend(_detection_payload(track, frame.timestamp) for track in tracks)
        if analysis is not None:
            rows.extend(
                {
                    "timestamp": timestamp,
                    "bbox": [round(float(value), 1) for value in weapon.bbox],
                    "track_id": -1,
                    "class_name": weapon.class_name,
                    "confidence": round(float(weapon.confidence), 3),
                    "is_threat": True,
                    "weapon": True,
                    "weapon_conf": round(float(weapon.confidence), 3),
                    "fall": False,
                    "violence": False,
                }
                for weapon in analysis.weapons
            )

        events: list[dict[str, Any]] = [
            {
                "rule": trigger.rule_id,
                "severity": trigger.severity,
                "timestamp": trigger.timestamp,
                "tracker_ids": [trigger.tracker_id],
                "details": trigger.details,
            }
            for trigger in triggers
        ]
        event_keys = {(event["rule"], tuple(event["tracker_ids"])) for event in events}

        for state in down_states:
            if not any(row["track_id"] == state.track_id for row in rows):
                rows.append(
                    {
                        "timestamp": timestamp,
                        "bbox": [round(float(value), 1) for value in state.bbox],
                        "track_id": state.track_id,
                        "class_name": "person",
                        "confidence": round(float(state.confidence), 3),
                        "is_threat": True,
                        "weapon": False,
                        "weapon_conf": 0.0,
                        "fall": True,
                        "violence": False,
                    }
                )

            key = (PERSON_DOWN_RULE_ID, (state.track_id,))
            if key in event_keys:
                continue
            event_keys.add(key)
            events.append(
                {
                    "rule": PERSON_DOWN_RULE_ID,
                    "severity": "high",
                    "timestamp": timestamp,
                    "tracker_ids": [state.track_id],
                    "details": {
                        "event": PERSON_DOWN_RULE_ID,
                        "persistent": True,
                        "bbox": [round(float(value), 1) for value in state.bbox],
                        "since": round(float(state.since), 2),
                        "last_seen": round(float(state.last_seen), 2),
                    },
                }
            )

        payload = {
            "timestamp": timestamp,
            "frame_width": width,
            "frame_height": height,
            "detections": rows,
            "events": events,
        }
        self._loop.call_soon_threadsafe(self._set_metadata, payload)

    def _on_trigger(self, trigger: RuleTrigger, incident_id: int | None) -> None:
        payload = {
            "type": "incident",
            "incident_id": incident_id,
            "rule": trigger.rule_id,
            "rule_name": trigger.rule_name,
            "severity": trigger.severity,
            "timestamp": trigger.timestamp,
            "tracker_ids": [trigger.tracker_id],
        }
        self._loop.call_soon_threadsafe(self._broadcast_text, payload)

    def _set_metadata(self, payload: dict[str, Any]) -> None:
        self._latest_metadata = payload
        self._broadcast_text({**payload, "type": "metadata"})

    def _broadcast_text(self, payload: dict[str, Any]) -> None:
        self._broadcast("text", json.dumps(payload))

    def _broadcast(self, kind: str, payload: bytes | str) -> None:
        for viewer in list(self._viewers):
            self._put(viewer, kind, payload)

    @staticmethod
    def _put(viewer: Viewer, kind: str, payload: bytes | str) -> None:
        if viewer.queue.full():
            with suppress(asyncio.QueueEmpty):
                viewer.queue.get_nowait()
        with suppress(asyncio.QueueFull):
            viewer.queue.put_nowait((kind, payload))


class LiveSessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, LiveSession] = {}
        self._cleanup_task: asyncio.Task | None = None

    def create(
        self,
        *,
        owner_id: int,
        camera_id: int,
        camera_name: str,
        zones: list[Zone],
        rules: list[BehaviorRule],
    ) -> LiveSession:
        session = LiveSession(
            owner_id=owner_id,
            camera_id=camera_id,
            camera_name=camera_name,
            zones=zones,
            rules=rules,
        )
        self._sessions[session.id] = session
        session.start()
        self._ensure_cleanup()
        return session

    def get(self, session_id: str) -> LiveSession | None:
        return self._sessions.get(session_id)

    async def stop(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session is not None:
            await session.stop()

    async def shutdown(self) -> None:
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            self._cleanup_task = None
        for session_id in list(self._sessions):
            await self.stop(session_id)

    def _ensure_cleanup(self) -> None:
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self) -> None:
        while True:
            await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
            now = time.time()
            for session_id, session in list(self._sessions.items()):
                if session.is_stale(now):
                    logger.info("Stopping stale live session", session_id=session_id)
                    await self.stop(session_id)


manager = LiveSessionManager()
