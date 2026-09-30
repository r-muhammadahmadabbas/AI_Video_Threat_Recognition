from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session_dependency, engine
from app.config import settings

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def liveness():
    return {"status": "ok", "service": "api", "environment": settings.environment}


@router.get("/ready")
async def readiness(session: AsyncSession = Depends(get_session_dependency)):
    try:
        await session.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    # Check Redis
    try:
        import redis.asyncio as redis
        r = redis.from_url(settings.redis.url)
        await r.ping()
        await r.close()
        redis_status = "connected"
    except Exception:
        redis_status = "disconnected"

    healthy = db_status == "connected" and redis_status == "connected"
    status_code = status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ok" if healthy else "error",
        "service": "api",
        "database": db_status,
        "redis": redis_status,
    }