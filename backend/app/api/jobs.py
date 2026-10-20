from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..config import Settings
from ..models import Asset, Job, JobOutput, utc_now
from ..schemas import (
    InputAssetIn,
    JobCreate,
    JobOut,
    JobOptions,
    JobPage,
    JobStatus,
    RevisionCreate,
    WorkflowId,
)
from ..services.five_shots import build_five_shot_prompts, build_series_prompt_text
from ..services.prompts import (
    PromptValidationError,
    build_prompt,
    normalize_options,
    validate_input_roles,
)
from ..services.runner import JobRunner
from .deps import ApiError, get_runner, get_session, get_settings
from .serializers import job_out, load_assets

router = APIRouter(prefix="/jobs", tags=["jobs"])
ROLE_ORDER = {
    "garment": 0,
    "model": 1,
    "approved": 2,
    "reference": 3,
    "edit_target": 4,
}


def _ordered_inputs(inputs: list) -> list[dict]:
    raw = [item.model_dump() for item in inputs]
    return sorted(raw, key=lambda item: ROLE_ORDER.get(item["role"], 9))


async def _validate_assets(
    session: AsyncSession, inputs: list[dict]
) -> dict[str, Asset]:
    asset_ids = [item["asset_id"] for item in inputs]
    result = await session.execute(select(Asset).where(Asset.id.in_(asset_ids)))
    assets = {asset.id: asset for asset in result.scalars().all()}
    if len(assets) != len(set(asset_ids)):
        raise ApiError(422, "INPUT_ASSET_NOT_FOUND", "有参考图不存在或已被删除，请重新上传")
    for item in inputs:
        asset = assets[item["asset_id"]]
        if item["role"] == "edit_target":
            if asset.kind != "output":
                raise ApiError(422, "INPUT_ASSET_INVALID", "改图对象必须是已生成的作品")
        elif asset.kind != "upload":
            raise ApiError(422, "INPUT_ASSET_INVALID", "只能使用上传的图片作为参考图")
    return assets


async def _create_job(
    session: AsyncSession,
    runner: JobRunner,
    settings: Settings,
    *,
    workflow: WorkflowId,
    inputs: list[dict],
    options: JobOptions,
    instruction: str,
    parent_job_id: str | None = None,
) -> Job:
    if not settings.is_configured:
        raise ApiError(
            503,
            "RELAY_NOT_CONFIGURED",
            "尚未配置中转站接口密钥，请在项目根目录 .env 中填写 IMAGE_API_KEY",
        )
    try:
        validate_input_roles(
            workflow,
            [InputAssetIn(asset_id=item["asset_id"], role=item["role"]) for item in inputs],
        )
        normalized = normalize_options(workflow, options)
        if workflow == "five_shots":
            shots = build_five_shot_prompts(normalized, instruction)
            prompt = build_series_prompt_text(shots)
            for shot in shots:
                if len(shot.prompt) > 6000:
                    raise PromptValidationError(f"第 {shot.order} 张提示词过长，请精简补充要求")
        else:
            prompt = build_prompt(
                workflow,
                normalized,
                instruction,
                [item["role"] for item in inputs],
            )
    except PromptValidationError as exc:
        raise ApiError(422, "JOB_OPTIONS_INVALID", str(exc)) from exc
    if workflow != "five_shots" and len(prompt) > 6000:
        raise ApiError(422, "PROMPT_TOO_LONG", "提示词过长，请精简补充要求")

    job = Job(
        id=uuid.uuid4().hex,
        parent_job_id=parent_job_id,
        workflow=workflow,
        status="queued",
        instruction=instruction.strip(),
        final_prompt=prompt,
        model=settings.image_model,
        options_json=normalized.model_dump(),
        inputs_json=inputs,
        shots_total=5 if workflow == "five_shots" else 1,
        shots_done=0,
        outputs=[],
    )
    session.add(job)
    await session.commit()
    await runner.enqueue(job.id)
    return job


@router.post("", response_model=JobOut, status_code=202)
async def create_job(
    payload: JobCreate,
    session: AsyncSession = Depends(get_session),
    runner: JobRunner = Depends(get_runner),
    settings: Settings = Depends(get_settings),
) -> JobOut:
    inputs = _ordered_inputs(payload.inputs)
    assets = await _validate_assets(session, inputs)
    job = await _create_job(
        session,
        runner,
        settings,
        workflow=payload.workflow,  # type: ignore[arg-type]
        inputs=inputs,
        options=payload.options,
        instruction=payload.instruction,
    )
    return job_out(job, assets)


@router.get("", response_model=JobPage)
async def list_jobs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    status: JobStatus | None = Query(default=None),
    workflow: str | None = Query(
        default=None,
        pattern="^(try_on|white_bg|scene|detail|five_shots)$",
    ),
    session: AsyncSession = Depends(get_session),
) -> JobPage:
    conditions = []
    if status:
        conditions.append(Job.status == status)
    if workflow:
        conditions.append(Job.workflow == workflow)
    count_query = select(func.count()).select_from(Job)
    query = select(Job).options(
        selectinload(Job.outputs).selectinload(JobOutput.asset)
    )
    if conditions:
        count_query = count_query.where(*conditions)
        query = query.where(*conditions)
    total = int((await session.scalar(count_query)) or 0)
    result = await session.execute(
        query.order_by(Job.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    jobs = list(result.scalars().all())
    input_ids: set[str] = set()
    for job in jobs:
        for item in job.inputs_json:
            input_ids.add(item.get("asset_id", ""))
    asset_map = await load_assets(session, input_ids)
    return JobPage(
        items=[job_out(job, asset_map) for job in jobs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{job_id}", response_model=JobOut)
async def get_job(
    job_id: str,
    session: AsyncSession = Depends(get_session),
) -> JobOut:
    result = await session.execute(
        select(Job)
        .where(Job.id == job_id)
        .options(selectinload(Job.outputs).selectinload(JobOutput.asset))
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise ApiError(404, "JOB_NOT_FOUND", "任务不存在")
    asset_map = await load_assets(
        session, {item.get("asset_id", "") for item in job.inputs_json}
    )
    return job_out(job, asset_map)


@router.post("/{job_id}/cancel", response_model=JobOut)
async def cancel_job(
    job_id: str,
    session: AsyncSession = Depends(get_session),
) -> JobOut:
    result = await session.execute(
        select(Job)
        .where(Job.id == job_id)
        .options(selectinload(Job.outputs).selectinload(JobOutput.asset))
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise ApiError(404, "JOB_NOT_FOUND", "任务不存在")
    if job.status == "running":
        raise ApiError(409, "JOB_RUNNING", "任务已开始生成，无法取消")
    if job.status != "queued":
        raise ApiError(409, "JOB_ALREADY_FINISHED", "任务已结束，无法取消")
    job.status = "canceled"
    job.finished_at = utc_now()
    await session.commit()
    asset_map = await load_assets(
        session, {item.get("asset_id", "") for item in job.inputs_json}
    )
    return job_out(job, asset_map)


@router.post("/{job_id}/retry", response_model=JobOut, status_code=202)
async def retry_job(
    job_id: str,
    session: AsyncSession = Depends(get_session),
    runner: JobRunner = Depends(get_runner),
    settings: Settings = Depends(get_settings),
) -> JobOut:
    job = await session.get(Job, job_id)
    if job is None:
        raise ApiError(404, "JOB_NOT_FOUND", "任务不存在")
    if job.status in {"queued", "running"}:
        raise ApiError(409, "JOB_ACTIVE", "任务仍在进行中，不能重复提交")
    inputs = [dict(item) for item in job.inputs_json]
    assets = await _validate_assets(session, inputs)
    try:
        options = JobOptions(**job.options_json)
    except Exception:
        options = JobOptions()
    new_job = await _create_job(
        session,
        runner,
        settings,
        workflow=job.workflow,  # type: ignore[arg-type]
        inputs=inputs,
        options=options,
        instruction=job.instruction,
        parent_job_id=job.parent_job_id,
    )
    return job_out(new_job, assets)


@router.post("/{job_id}/revise", response_model=JobOut, status_code=202)
async def revise_job(
    job_id: str,
    payload: RevisionCreate,
    session: AsyncSession = Depends(get_session),
    runner: JobRunner = Depends(get_runner),
    settings: Settings = Depends(get_settings),
) -> JobOut:
    result = await session.execute(
        select(Job)
        .where(Job.id == job_id)
        .options(selectinload(Job.outputs).selectinload(JobOutput.asset))
    )
    parent = result.scalar_one_or_none()
    if parent is None:
        raise ApiError(404, "JOB_NOT_FOUND", "原任务不存在")
    if parent.workflow == "five_shots":
        raise ApiError(409, "SERIES_REVISION_UNSUPPORTED", "五图套图暂不支持单张定向改图")
    if parent.status != "succeeded":
        raise ApiError(409, "JOB_NOT_SUCCEEDED", "只有成功生成的作品才能定向调整")
    if not parent.outputs:
        raise ApiError(409, "JOB_NO_OUTPUT", "原任务没有可调整的图片")

    target = None
    if payload.output_id:
        target = next(
            (item for item in parent.outputs if item.asset_id == payload.output_id),
            None,
        )
        if target is None:
            raise ApiError(422, "OUTPUT_NOT_FOUND", "指定的作品不属于原任务")
    else:
        target = parent.outputs[0]

    base_inputs = [
        dict(item) for item in parent.inputs_json if item.get("role") != "edit_target"
    ]
    base_inputs.sort(key=lambda item: ROLE_ORDER.get(item.get("role", ""), 9))
    # One edit target plus at most three source references keeps the edit request
    # inside the same four-image envelope as normal generation.
    kept: list[dict] = []
    for item in base_inputs:
        if len(kept) >= 3:
            break
        kept.append(item)
    if not any(item.get("role") == "garment" for item in kept):
        raise ApiError(422, "JOB_INPUT_INVALID", "原任务缺少服装主图，无法调整")
    inputs = kept + [{"asset_id": target.asset_id, "role": "edit_target"}]

    try:
        options = JobOptions(**parent.options_json)
    except Exception:
        options = JobOptions()
    if payload.size is not None:
        options.size = payload.size
    if payload.quality is not None:
        options.quality = payload.quality

    new_job = await _create_job(
        session,
        runner,
        settings,
        workflow=parent.workflow,  # type: ignore[arg-type]
        inputs=inputs,
        options=options,
        instruction=payload.feedback,
        parent_job_id=parent.id,
    )
    asset_map = await load_assets(
        session, {item["asset_id"] for item in inputs}
    )
    return job_out(new_job, asset_map)
