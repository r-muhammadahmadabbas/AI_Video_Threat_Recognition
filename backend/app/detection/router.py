"""Video upload and threat detection API endpoint."""

from __future__ import annotations

import base64
import tempfile
from pathlib import Path

import cv2
from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.logging import get_logger
from workers.cv_worker.pipeline import DetectionPipeline

logger = get_logger(__name__)
router = APIRouter()


class DetectionResult(BaseModel):
    timestamp: float
    class_name: str
    confidence: float
    bbox: list[float]
    is_threat: bool
    track_id: int
    weapon: bool
    weapon_conf: float
    frame_image: str | None = None


class RuleEventResult(BaseModel):
    rule: str
    severity: str
    timestamp: float
    tracker_ids: list[int]
    details: dict


class DetectionResponse(BaseModel):
    total_frames: int
    detections: list[DetectionResult]
    events: list[RuleEventResult]


@router.get("/")
async def serve_index() -> FileResponse:
    index_path = Path(__file__).parent.parent / "static" / "index.html"
    return FileResponse(str(index_path))


@router.post("/api/detect", response_model=DetectionResponse)
async def detect_threats(video: UploadFile = File(...)) -> DetectionResponse:
    logger.info("Video received", filename=video.filename)

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        content = await video.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        pipeline = DetectionPipeline(confidence=0.30)
        cap = cv2.VideoCapture(str(tmp_path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_idx = 0
        all_detections: list[DetectionResult] = []
        all_events: list[RuleEventResult] = []

        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if frame_idx % 25 == 0:
                ts = round(frame_idx / fps, 2)
                annotated, dets = pipeline.process_frame(frame, ts)

                img_b64 = base64.b64encode(
                    cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])[1]
                ).decode()

                for d in dets:
                    d["frame_image"] = img_b64
                    all_detections.append(DetectionResult(**d))

                for ev in pipeline.events:
                    if ev.timestamp == ts:
                        all_events.append(
                            RuleEventResult(
                                rule=ev.rule,
                                severity=ev.severity,
                                timestamp=ev.timestamp,
                                tracker_ids=ev.tracker_ids,
                                details=ev.details,
                            )
                        )
            frame_idx += 1
        cap.release()

        # Deduplicate events by rule+timestamp
        seen = set()
        unique_events = []
        for e in all_events:
            key = (e.rule, e.timestamp)
            if key not in seen:
                seen.add(key)
                unique_events.append(e)

        logger.info(
            "Done",
            detections=len(all_detections),
            events=len(unique_events),
        )
        return DetectionResponse(
            total_frames=total_frames,
            detections=all_detections,
            events=unique_events,
        )
    finally:
        import time
        for _ in range(5):
            try:
                tmp_path.unlink(missing_ok=True)
                break
            except PermissionError:
                time.sleep(0.5)