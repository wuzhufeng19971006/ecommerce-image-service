from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.config import Settings
from app.db import create_database, init_db
from app.models import Job
from app.services.runner import JobRunner
from app.services.storage import Storage


@pytest.mark.asyncio
async def test_startup_recovery_marks_running_failed_and_requeues(tmp_path: Path):
    settings = Settings(
        app_data_dir=tmp_path / "data",
        image_mock=True,
        serve_frontend=False,
        image_workers=1,
    )
    engine, session_factory = create_database(settings)
    await init_db(engine)
    storage = Storage(settings.data_dir)
    runner = JobRunner(settings, session_factory, storage)
    now = datetime.now(timezone.utc)
    async with session_factory() as session:
        session.add(
            Job(
                id="a" * 32,
                workflow="try_on",
                status="running",
                instruction="",
                final_prompt="test",
                model=settings.image_model,
                options_json={},
                inputs_json=[],
                outputs=[],
                created_at=now,
                started_at=now,
            )
        )
        session.add(
            Job(
                id="b" * 32,
                workflow="white_bg",
                status="queued",
                instruction="",
                final_prompt="test",
                model=settings.image_model,
                options_json={},
                inputs_json=[],
                outputs=[],
                created_at=now,
            )
        )
        await session.commit()

    await runner.recover()

    async with session_factory() as session:
        interrupted = await session.get(Job, "a" * 32)
        queued = await session.get(Job, "b" * 32)
        assert interrupted is not None
        assert interrupted.status == "failed"
        assert interrupted.error_code == "SERVICE_RESTARTED"
        assert queued is not None
        assert queued.status == "queued"
    assert runner.queue.qsize() == 1
    await engine.dispose()
