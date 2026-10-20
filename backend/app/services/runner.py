from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..config import Settings
from ..models import Asset, Job, JobOutput, utc_now
from ..schemas import JobOptions
from .five_shots import build_five_shot_prompts, build_series_prompt_text
from .images import ImageValidationError, ImagePayload, make_mock_image
from .prompts import PromptValidationError, build_prompt, normalize_options
from .relay import RelayClient, RelayError
from .storage import Storage

logger = logging.getLogger(__name__)

ROLE_ORDER = {
    "garment": 0,
    "model": 1,
    "approved": 2,
    "reference": 3,
    "edit_target": 4,
}


class JobRunner:
    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        storage: Storage,
        relay: RelayClient | None = None,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.storage = storage
        self.relay = relay or RelayClient(settings)
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self._workers: list[asyncio.Task] = []
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        await self.recover()
        for index in range(self.settings.workers):
            task = asyncio.create_task(self._worker_loop(), name=f"image-worker-{index + 1}")
            self._workers.append(task)
        logger.info("job runner started with %s worker(s)", len(self._workers))

    async def stop(self) -> None:
        for task in self._workers:
            task.cancel()
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        self._started = False
        logger.info("job runner stopped")

    async def recover(self) -> None:
        now = utc_now()
        async with self.session_factory() as session:
            await session.execute(
                update(Job)
                .where(Job.status == "running")
                .values(
                    status="failed",
                    error_code="SERVICE_RESTARTED",
                    error_message="服务重启，本次生成被中断，请重新生成",
                    finished_at=now,
                )
            )
            await session.commit()
            queued = (
                await session.execute(
                    select(Job.id).where(Job.status == "queued").order_by(Job.created_at)
                )
            ).scalars().all()
        for job_id in queued:
            await self.enqueue(job_id)
        if queued:
            logger.info("re-enqueued %s queued job(s)", len(queued))

    async def enqueue(self, job_id: str) -> None:
        await self.queue.put(job_id)

    async def _worker_loop(self) -> None:
        while True:
            job_id = await self.queue.get()
            try:
                await self.process(job_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("unexpected worker failure for job %s", job_id)
            finally:
                self.queue.task_done()

    async def process(self, job_id: str) -> None:
        async with self.session_factory() as session:
            # Atomically claim a queued job. This prevents a worker from
            # overwriting a cancel request that raced with queue pickup.
            claimed = await session.execute(
                update(Job)
                .where(Job.id == job_id, Job.status == "queued")
                .values(
                    status="running",
                    started_at=utc_now(),
                    error_code=None,
                    error_message=None,
                )
            )
            await session.commit()
            if claimed.rowcount != 1:
                logger.info("skip job %s: not queued anymore", job_id)
                return
            job = await session.get(Job, job_id)
            if job is None:
                logger.warning("job %s no longer exists", job_id)
                return

            started = time.monotonic()
            stored_paths: list[str] = []
            try:
                inputs = sorted(
                    job.inputs_json,
                    key=lambda item: ROLE_ORDER.get(item.get("role", "reference"), 9),
                )
                asset_ids = [item["asset_id"] for item in inputs]
                assets = (
                    await session.execute(select(Asset).where(Asset.id.in_(asset_ids)))
                ).scalars().all()
                asset_map = {asset.id: asset for asset in assets}
                missing = [asset_id for asset_id in asset_ids if asset_id not in asset_map]
                if missing:
                    raise FileNotFoundError("输入素材记录缺失")

                options = normalize_options(
                    job.workflow, JobOptions(**job.options_json)
                )
                job.options_json = options.model_dump()
                roles = [item["role"] for item in inputs]
                if job.workflow == "five_shots":
                    shots = build_five_shot_prompts(options, job.instruction)
                    prompt = build_series_prompt_text(shots)
                    for shot in shots:
                        if len(shot.prompt) > 6000:
                            raise PromptValidationError(
                                f"第 {shot.order} 张提示词过长，请精简补充要求"
                            )
                else:
                    prompt = build_prompt(
                        job.workflow,
                        options,
                        job.instruction,
                        roles,
                    )
                    if len(prompt) > 6000:
                        raise PromptValidationError("提示词过长，请精简补充要求")
                job.final_prompt = prompt
                await session.commit()

                if job.workflow == "five_shots":
                    await self._run_five_shots(
                        session, job, inputs, asset_map, options, started
                    )
                    return

                if self.settings.image_mock:
                    images = [make_mock_image(prompt, options.size, 0)]
                    usage: dict | None = {"mock": True}
                else:
                    files: list[tuple[str, bytes, str]] = []
                    for index, item in enumerate(inputs):
                        asset = asset_map[item["asset_id"]]
                        data = self.storage.read(asset.filename)
                        extension = Path(asset.filename).suffix.lstrip(".") or "png"
                        role = item.get("role", "reference")
                        files.append(
                            (f"{role}-{index + 1}.{extension}", data, asset.mime_type)
                        )
                    if not files:
                        result = await self.relay.generate(
                            prompt, options.size, options.quality
                        )
                    else:
                        result = await self.relay.edit(
                            prompt, files, options.size, options.quality
                        )
                    images = result.images
                    usage = result.usage

                if not images:
                    raise RelayError("RELAY_NO_IMAGE", "接口没有返回图片")

                for position, payload in enumerate(images[:4]):
                    stored = self.storage.save_asset(
                        "output", payload, f"{job.workflow}-{position + 1}"
                    )
                    stored_paths.append(stored.filename)
                    if stored.thumb_filename:
                        stored_paths.append(stored.thumb_filename)
                    asset = Asset(
                        id=stored.id,
                        kind="output",
                        filename=stored.filename,
                        thumb_filename=stored.thumb_filename,
                        original_name=f"{job.workflow}-{position + 1}.{payload.extension}",
                        mime_type=stored.mime_type,
                        width=stored.width,
                        height=stored.height,
                        size_bytes=stored.size_bytes,
                        sha256=stored.sha256,
                    )
                    session.add(asset)
                    session.add(
                        JobOutput(job_id=job.id, asset_id=stored.id, position=position)
                    )

                duration_ms = int((time.monotonic() - started) * 1000)
                job.status = "succeeded"
                job.shots_total = 1
                job.shots_done = 1
                job.usage_json = usage
                job.duration_ms = duration_ms
                job.finished_at = utc_now()
                job.error_code = None
                job.error_message = None
                await session.commit()
                logger.info("job %s succeeded in %sms", job.id, duration_ms)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await session.rollback()
                for relative in stored_paths:
                    self.storage.delete(relative)
                await self._mark_failed(job_id, exc, started)
                logger.warning("job %s failed: %s", job_id, exc)


    async def _run_five_shots(
        self,
        session: AsyncSession,
        job: Job,
        inputs: list[dict],
        asset_map: dict[str, Asset],
        options: JobOptions,
        started: float,
    ) -> None:
        shots = build_five_shot_prompts(options, job.instruction)
        job.shots_total = len(shots)
        job.shots_done = 0
        await session.commit()

        anchor: ImagePayload | None = None
        usage_calls: list[dict] = []
        for shot in shots:
            try:
                files: list[tuple[str, bytes, str]] = []
                for index, item in enumerate(inputs):
                    asset = asset_map[item["asset_id"]]
                    data = self.storage.read(asset.filename)
                    extension = Path(asset.filename).suffix.lstrip(".") or "png"
                    files.append(
                        (f"product-{index + 1}.{extension}", data, asset.mime_type)
                    )
                if shot.uses_anchor:
                    if anchor is None:
                        raise RuntimeError("首张一致性参考尚未生成")
                    files.append(("anchor-hero.png", anchor.data, anchor.mime_type))

                if self.settings.image_mock:
                    image = make_mock_image(shot.prompt, options.size, shot.order - 1)
                    usage: dict | None = {"mock": True}
                else:
                    result = await self.relay.edit(
                        shot.prompt, files, options.size, options.quality
                    )
                    if not result.images:
                        raise RelayError(
                            "RELAY_NO_IMAGE",
                            f"第 {shot.order} 张「{shot.name}」没有返回图片",
                        )
                    image = result.images[0]
                    usage = result.usage

                stored = self.storage.save_asset(
                    "output", image, f"five-{shot.order}-{shot.name}"
                )
                asset = Asset(
                    id=stored.id,
                    kind="output",
                    filename=stored.filename,
                    thumb_filename=stored.thumb_filename,
                    original_name=f"five-{shot.order}-{shot.name}.{image.extension}",
                    mime_type=stored.mime_type,
                    width=stored.width,
                    height=stored.height,
                    size_bytes=stored.size_bytes,
                    sha256=stored.sha256,
                )
                session.add(asset)
                session.add(
                    JobOutput(
                        job_id=job.id,
                        asset_id=stored.id,
                        position=shot.order - 1,
                    )
                )
                job.shots_done = shot.order
                if usage:
                    usage_calls.append(
                        {"shot": shot.order, "id": shot.id, "usage": usage}
                    )
                job.usage_json = {
                    "mock": self.settings.image_mock,
                    "calls": usage_calls,
                }
                await session.commit()
                if shot.id == "hero":
                    anchor = image
                logger.info(
                    "job %s shot %s/%s (%s) saved",
                    job.id,
                    shot.order,
                    len(shots),
                    shot.name,
                )
            except asyncio.CancelledError:
                raise
            except RelayError as exc:
                raise RelayError(
                    exc.code,
                    f"第 {shot.order} 张「{shot.name}」失败：{exc.message}",
                    status_code=exc.status_code,
                    upstream_detail=exc.upstream_detail,
                ) from exc
            except (PromptValidationError, ImageValidationError, FileNotFoundError):
                raise
            except Exception as exc:
                logger.exception(
                    "job %s shot %s (%s) failed", job.id, shot.order, shot.name
                )
                raise RelayError(
                    "SERIES_SHOT_FAILED",
                    f"第 {shot.order} 张「{shot.name}」生成失败，请稍后重试",
                ) from exc

        duration_ms = int((time.monotonic() - started) * 1000)
        job.status = "succeeded"
        job.duration_ms = duration_ms
        job.finished_at = utc_now()
        job.error_code = None
        job.error_message = None
        await session.commit()
        logger.info("five-shot job %s succeeded in %sms", job.id, duration_ms)

    async def _mark_failed(self, job_id: str, exc: Exception, started: float) -> None:
        if isinstance(exc, RelayError):
            code = exc.code
            message = exc.message
        elif isinstance(exc, (PromptValidationError, ImageValidationError)):
            code = "PROMPT_INVALID" if isinstance(exc, PromptValidationError) else "IMAGE_INVALID"
            message = str(exc)
        elif isinstance(exc, FileNotFoundError):
            code = "INPUT_FILE_MISSING"
            message = "输入素材文件缺失，请重新上传后再试"
        else:
            code = "INTERNAL_ERROR"
            message = "生成失败，请稍后重试"
            logger.exception("unexpected job failure")
        duration_ms = int((time.monotonic() - started) * 1000)
        async with self.session_factory() as session:
            job = await session.get(Job, job_id)
            if job is None:
                return
            job.status = "failed"
            job.error_code = code
            job.error_message = message[:1000]
            job.duration_ms = duration_ms
            job.finished_at = utc_now()
            await session.commit()
