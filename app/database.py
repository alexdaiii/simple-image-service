import logging
from typing import AsyncIterator, Any, Generator, AsyncGenerator

from fastapi import Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.utils import get_settings

_engine: AsyncEngine | None = None

log = logging.getLogger(__name__)


async def open_database_conn_pool():
    global _engine
    if _engine:
        return

    log.info("Opening database connection pool")
    _engine = create_async_engine(
        get_settings().sqlite_db,
        pool_pre_ping=True,
        future=True,
    )
    log.info("Database connection pool opened")


def get_engine() -> Generator[AsyncEngine, Any, None]:
    global _engine

    if not _engine:
        raise ValueError(
            "Database engine is not set. Call open_database_conn_pool first."
        )

    yield _engine


async def close_database_conn_pool():
    global _engine
    if _engine:
        log.info("Closing database connection pool")
        await _engine.dispose()
        log.info("Database connection pool closed")


async def get_sessionmaker(
    engine: AsyncEngine = Depends(get_engine),
) -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    async_session = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    yield async_session


async def get_session(
    async_session: async_sessionmaker[AsyncSession] = Depends(get_sessionmaker),
) -> AsyncIterator[AsyncSession]:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except HTTPException as e:
            await session.rollback()
            raise e
        except Exception:
            await session.rollback()
            log.error("Unhandled exception during database session")
            raise HTTPException(
                status_code=500,
                detail="Internal server error",
            )


async def init_db():
    """Creates the database tables."""
    global _engine
    try:
        async with _engine.begin() as conn:
            log.info("Creating database tables if they do not exist")
            await conn.execute(
                text(
                    """
CREATE TABLE IF NOT EXISTS images (
    project TEXT,
    key TEXT,
    width INTEGER,
    height INTEGER,
    size INTEGER,
    format TEXT,
    s3_path TEXT,
    PRIMARY KEY (project, key)
)
"""
                )
            )
            await conn.commit()
    except ConnectionRefusedError:
        log.error(
            "Database connection refused. Either the database is not "
            "running, is starting up, or the database connection is not "
            "configured correctly. Please restart the server."
        )

    log.info("Database tables created or already exist")


__all__ = [
    "open_database_conn_pool",
    "close_database_conn_pool",
    "get_engine",
    "get_sessionmaker",
    "get_session",
    "init_db",
]
