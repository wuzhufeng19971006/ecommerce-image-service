from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..schemas import ConfigOut, HealthOut
from ..services.prompts import get_meta
from .deps import get_session, get_settings

router = APIRouter(tags=["meta"])


def _safe_api_base(value: str) -> str:
    try:
        parsed = urlsplit(value)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
    except ValueError:
        pass
    return value.split("?", 1)[0]


@router.get("/config", response_model=ConfigOut)
async def config(settings: Settings = Depends(get_settings)) -> ConfigOut:
    return ConfigOut(
        app_name=settings.app_name,
        version=settings.app_version,
        model=settings.image_model,
        api_base=_safe_api_base(settings.image_api_base),
        configured=settings.is_configured,
        mock=settings.image_mock,
        max_reference_images=settings.max_reference_images,
    )


@router.get("/meta")
async def meta(settings: Settings = Depends(get_settings)) -> dict:
    payload = get_meta(settings.max_reference_images)
    payload["mock"] = settings.image_mock
    payload["configured"] = settings.is_configured
    payload["model"] = settings.image_model
    return payload


@router.get("/health", response_model=HealthOut)
async def health(
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> HealthOut:
    database = "ok"
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        database = "error"
    return HealthOut(
        ok=database == "ok",
        database=database,
        configured=settings.is_configured,
        mock=settings.image_mock,
        model=settings.image_model,
        version=settings.app_version,
    )
