from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Asset, Job
from ..schemas import AssetOut, GalleryItem, JobErrorOut, JobInputOut, JobOptions, JobOut


def utc_or_utcnow(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def asset_out(asset: Asset) -> AssetOut:
    base = f"/api/assets/{asset.id}/content"
    return AssetOut(
        id=asset.id,
        kind=asset.kind,  # type: ignore[arg-type]
        url=base,
        thumb_url=f"{base}?variant=thumb" if asset.thumb_filename else base,
        download_url=f"{base}?download=1",
        original_name=asset.original_name,
        mime_type=asset.mime_type,
        width=asset.width,
        height=asset.height,
        size_bytes=asset.size_bytes,
        created_at=utc_or_utcnow(asset.created_at) or datetime.now(timezone.utc),
    )


def _options(job: Job) -> JobOptions:
    try:
        return JobOptions(**job.options_json)
    except Exception:
        return JobOptions()


def job_out(job: Job, asset_map: dict[str, Asset]) -> JobOut:
    options = _options(job)
    inputs: list[JobInputOut] = []
    for item in job.inputs_json:
        asset = asset_map.get(item.get("asset_id", ""))
        if asset is not None:
            inputs.append(JobInputOut(role=item["role"], asset=asset_out(asset)))
    outputs = [asset_out(output.asset) for output in job.outputs if output.asset]
    error = None
    if job.error_code:
        error = JobErrorOut(
            code=job.error_code, message=job.error_message or "生成失败"
        )
    return JobOut(
        id=job.id,
        workflow=job.workflow,  # type: ignore[arg-type]
        status=job.status,  # type: ignore[arg-type]
        instruction=job.instruction,
        final_prompt=job.final_prompt,
        model=job.model,
        options=options,
        size=options.size,
        quality=options.quality,
        inputs=inputs,
        outputs=outputs,
        error=error,
        usage=job.usage_json,
        duration_ms=job.duration_ms,
        parent_job_id=job.parent_job_id,
        shots_total=job.shots_total,
        shots_done=job.shots_done,
        created_at=utc_or_utcnow(job.created_at) or datetime.now(timezone.utc),
        started_at=utc_or_utcnow(job.started_at),
        finished_at=utc_or_utcnow(job.finished_at),
    )


def gallery_item(job: Job, asset: Asset) -> GalleryItem:
    return GalleryItem(
        job_id=job.id,
        workflow=job.workflow,  # type: ignore[arg-type]
        created_at=utc_or_utcnow(job.created_at) or datetime.now(timezone.utc),
        instruction=job.instruction,
        final_prompt=job.final_prompt,
        options=_options(job),
        output=asset_out(asset),
    )


async def load_assets(
    session: AsyncSession, asset_ids: list[str] | set[str]
) -> dict[str, Asset]:
    ids = [asset_id for asset_id in asset_ids if asset_id]
    if not ids:
        return {}
    result = await session.execute(select(Asset).where(Asset.id.in_(ids)))
    return {asset.id: asset for asset in result.scalars().all()}
