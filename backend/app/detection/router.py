"""Video/image upload and threat detection API endpoints."""

from __future__ import annotations

import asyncio
import base64
import tempfile
import threading
from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.logging import get_logger
from workers.cv_worker.pipeline import DetectionPipeline

logger = get_logger(__name__)
router = APIRouter()

_pipeline: DetectionPipeline | None = None
_pipeline_lock = threading.Lock()


def _get_pipeline() -> DetectionPipeline:
    """Lazily build a single shared pipeline (models load once per process)."""
    global _pipeline
    if _pipeline is None:
        with _pipeline_lock:
            if _pipeline is None:
                logger.info("Loading detection models")
                _pipeline = DetectionPipeline(confidence=0.30)
    return _pipeline


class DetectionResult(BaseModel):
    timestamp: float
    class_name: str
    confidence: float
    bbox: list[float]
    is_threat: bool
    track_id: int
    weapon: bool
    weapon_conf: float
    fall: bool = False
    violence: bool = False
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


def _encode_frame(frame: np.ndarray) -> str:
    return base64.b64encode(
        cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])[1]
    ).decode()


def _process_video_file(path: Path) -> DetectionResponse:
    pipeline = _get_pipeline()
    pipeline.reset_session()

    cap = cv2.VideoCapture(str(path))
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
            img_b64 = _encode_frame(annotated)

            for detection in dets:
                detection["frame_image"] = img_b64
                all_detections.append(DetectionResult(**detection))

            for event in pipeline.events:
                if event.timestamp == ts:
                    all_events.append(
                        RuleEventResult(
                            rule=event.rule,
                            severity=event.severity,
                            timestamp=event.timestamp,
                            tracker_ids=event.tracker_ids,
                            details=event.details,
                        )
                    )
        frame_idx += 1
    cap.release()

    seen: set[tuple[str, float]] = set()
    unique_events: list[RuleEventResult] = []
    for event in all_events:
        key = (event.rule, event.timestamp)
        if key not in seen:
            seen.add(key)
            unique_events.append(event)

    return DetectionResponse(
        total_frames=total_frames,
        detections=all_detections,
        events=unique_events,
    )


def _process_image_bytes(content: bytes) -> DetectionResponse:
    frame = cv2.imdecode(np.frombuffer(content, np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not decode image file",
        )

    pipeline = _get_pipeline()
    pipeline.reset_session()

    annotated, dets = pipeline.process_frame(frame, 0.0)
    img_b64 = _encode_frame(annotated)

    detections = []
    for detection in dets:
        detection["frame_image"] = img_b64
        detections.append(DetectionResult(**detection))

    events = [
        RuleEventResult(
            rule=event.rule,
            severity=event.severity,
            timestamp=event.timestamp,
            tracker_ids=event.tracker_ids,
            details=event.details,
        )
        for event in pipeline.events
    ]

    return DetectionResponse(total_frames=1, detections=detections, events=events)


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
        result = await asyncio.to_thread(_process_video_file, tmp_path)
        logger.info(
            "Done",
            detections=len(result.detections),
            events=len(result.events),
        )
        return result
    finally:
        import time

        for _ in range(5):
            try:
                tmp_path.unlink(missing_ok=True)
                break
            except PermissionError:
                time.sleep(0.5)


@router.post("/api/detect/image", response_model=DetectionResponse)
async def detect_image(image: UploadFile = File(...)) -> DetectionResponse:
    logger.info("Image received", filename=image.filename)
    content = await image.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty image upload",
        )
    return await asyncio.to_thread(_process_image_bytes, content)
