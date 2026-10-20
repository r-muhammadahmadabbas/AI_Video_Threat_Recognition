from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.db.session import close_db, init_db
from app.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Application starting up", environment=settings.environment)
    await init_db()
    logger.info("Database initialized")
    yield
    logger.info("Application shutting down")
    await close_db()
    logger.info("Database connections closed")


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Video Threat Recognition",
        version="0.1.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        logger.warning("Validation error", path=request.url.path, errors=exc.errors())
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": exc.errors(), "message": "Validation failed"},
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.error("Database error", path=request.url.path, error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Database error", "message": "Internal server error"},
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception", path=request.url.path, error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error", "message": "An unexpected error occurred"},
        )

    @app.get("/health/live", tags=["health"])
    async def liveness() -> dict:
        return {"status": "ok", "service": "api"}

    @app.get("/health/ready", tags=["health"])
    async def readiness() -> dict:
        from app.db.session import engine
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return {"status": "ok", "service": "api", "database": "connected"}
        except Exception as e:
            logger.error("Readiness check failed", error=str(e))
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "error", "service": "api", "database": "disconnected"},
            )

    from app.audit.router import router as audit_router
    from app.auth.router import router as auth_router
    from app.cameras.router import router as cameras_router
    from app.dashboard.router import router as dashboard_router
    from app.detection.router import router as detection_router
    from app.evidence.router import router as evidence_router
    from app.incidents.router import router as incidents_router
    from app.rules.router import router as rules_router
    from app.users.router import router as users_router
    from app.zones.router import router as zones_router

    app.include_router(auth_router, tags=["auth"])
    app.include_router(cameras_router, tags=["cameras"])
    app.include_router(detection_router, tags=["detection"])
    app.include_router(incidents_router, tags=["incidents"])
    app.include_router(zones_router, tags=["zones"])
    app.include_router(rules_router, tags=["rules"])
    app.include_router(evidence_router, tags=["evidence"])
    app.include_router(users_router, tags=["users"])
    app.include_router(audit_router, tags=["audit"])
    app.include_router(dashboard_router, tags=["dashboard"])

    return app


app = create_app()
