from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import Settings


class Base(DeclarativeBase):
    pass


def create_database(
    settings: Settings,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    url = f"sqlite+aiosqlite:///{settings.database_path.as_posix()}"
    engine = create_async_engine(
        url,
        echo=False,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, session_factory


async def init_db(engine: AsyncEngine) -> None:
    # Importing models registers all tables on Base.metadata.
    from . import models  # noqa: F401

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        columns = {
            row[1]
            for row in (await connection.execute(text("PRAGMA table_info(jobs)"))).all()
        }
        if "parent_job_id" not in columns:
            await connection.execute(
                text("ALTER TABLE jobs ADD COLUMN parent_job_id VARCHAR(32)")
            )
        if "shots_total" not in columns:
            await connection.execute(
                text("ALTER TABLE jobs ADD COLUMN shots_total INTEGER NOT NULL DEFAULT 1")
            )
        if "shots_done" not in columns:
            await connection.execute(
                text("ALTER TABLE jobs ADD COLUMN shots_done INTEGER NOT NULL DEFAULT 0")
            )
        await connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_jobs_parent_job_id "
                "ON jobs (parent_job_id)"
            )
        )


async def session_scope(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session
