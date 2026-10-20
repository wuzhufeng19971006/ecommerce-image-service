from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Asset, Job, JobOutput
from ..schemas import GalleryPage
from .deps import get_session
from .serializers import gallery_item

router = APIRouter(prefix="/gallery", tags=["gallery"])


@router.get("", response_model=GalleryPage)
async def list_gallery(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=16, ge=1, le=48),
    workflow: str | None = Query(
        default=None,
        pattern="^(try_on|white_bg|scene|detail|five_shots)$",
    ),
    session: AsyncSession = Depends(get_session),
) -> GalleryPage:
    conditions = [Job.status == "succeeded"]
    if workflow:
        conditions.append(Job.workflow == workflow)
    count_query = (
        select(func.count())
        .select_from(JobOutput)
        .join(Job, Job.id == JobOutput.job_id)
        .where(*conditions)
    )
    total = int((await session.scalar(count_query)) or 0)
    query = (
        select(JobOutput, Job, Asset)
        .join(Job, Job.id == JobOutput.job_id)
        .join(Asset, Asset.id == JobOutput.asset_id)
        .where(*conditions)
        .order_by(Job.created_at.desc(), JobOutput.position.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await session.execute(query)).all()
    return GalleryPage(
        items=[gallery_item(job, asset) for _output, job, asset in rows],
        total=total,
        page=page,
        page_size=page_size,
    )
