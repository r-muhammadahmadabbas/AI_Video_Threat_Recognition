from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from app.config import settings
from app.logging import get_logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

logger = get_logger(__name__)

engine = create_async_engine(
    settings.db_url,
    echo=settings.debug,
    poolclass=NullPool if settings.use_sqlite else None,
    pool_size=settings.database.pool_size if not settings.use_sqlite else 0,
    max_overflow=settings.database.max_overflow if not settings.use_sqlite else 0,
    pool_timeout=settings.database.pool_timeout if not settings.use_sqlite else 0,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def init_db() -> None:
    logger.info("Initializing database connection", url=settings.db_url)
    async with engine.begin() as conn:
        from app.db.base import Base
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    logger.info("Closing database connection")
    await engine.dispose()


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_session_dependency() -> AsyncGenerator[AsyncSession, None]:
    async with get_session() as session:
        yield session