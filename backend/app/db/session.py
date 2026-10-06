from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.logging import get_logger

logger = get_logger(__name__)

# NullPool (sqlite) rejects pool sizing arguments, so the two database
# backends must be configured separately instead of passing 0/0/0 and hoping.
if settings.use_sqlite:
    engine_kwargs: dict = {"poolclass": NullPool}
else:
    engine_kwargs = {
        "pool_size": settings.database.pool_size,
        "max_overflow": settings.database.max_overflow,
        "pool_timeout": settings.database.pool_timeout,
    }

engine = create_async_engine(
    settings.db_url,
    echo=settings.debug,
    **engine_kwargs,
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
