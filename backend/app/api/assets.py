from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..models import Asset, Job, JobOutput
from ..schemas import AssetOut
from ..services.images import ImageValidationError, normalize_upload, safe_original_name
from ..services.storage import Storage
from .deps import ApiError, get_session, get_settings, get_storage
from .serializers import asset_out

router = APIRouter(prefix="/assets", tags=["assets"])


@router.post("", response_model=AssetOut, status_code=201)
async def upload_asset(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    storage: Storage = Depends(get_storage),
    settings: Settings = Depends(get_settings),
) -> AssetOut:
    if not file.filename:
        raise ApiError(400, "UPLOAD_INVALID", "请选择要上传的图片")
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise ApiError(
            413,
            "UPLOAD_TOO_LARGE",
            f"图片不能超过 {settings.max_upload_bytes // (1024 * 1024)} MB",
        )
    try:
        payload = normalize_upload(
            data,
            file.filename,
            settings.max_upload_bytes,
            settings.max_input_dimension,
        )
        stored = storage.save_asset(
            "upload", payload, safe_original_name(file.filename)
        )
    except ImageValidationError as exc:
        raise ApiError(400, "UPLOAD_INVALID", str(exc)) from exc
    except OSError as exc:
        raise ApiError(500, "STORAGE_WRITE_FAILED", "图片保存失败，请检查磁盘空间") from exc

    asset = Asset(
        id=stored.id,
        kind="upload",
        filename=stored.filename,
        thumb_filename=stored.thumb_filename,
        original_name=safe_original_name(file.filename),
        mime_type=stored.mime_type,
        width=stored.width,
        height=stored.height,
        size_bytes=stored.size_bytes,
        sha256=stored.sha256,
    )
    session.add(asset)
    await session.commit()
    await session.refresh(asset)
    return asset_out(asset)


@router.get("/{asset_id}/content")
async def get_asset_content(
    asset_id: str,
    variant: str = Query(default="full", pattern="^(full|thumb)$"),
    download: bool = Query(default=False),
    session: AsyncSession = Depends(get_session),
    storage: Storage = Depends(get_storage),
) -> FileResponse:
    asset = await session.get(Asset, asset_id)
    if asset is None:
        raise ApiError(404, "ASSET_NOT_FOUND", "素材不存在")
    relative = asset.thumb_filename if variant == "thumb" else asset.filename
    path = storage.path_for(relative or asset.filename)
    if path is None:
        raise ApiError(404, "ASSET_FILE_NOT_FOUND", "素材文件不存在")
    media_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    suffix = Path(path).suffix or ".png"
    filename = asset.original_name or f"image{suffix}"
    if not Path(filename).suffix:
        filename += suffix
    headers = {"Cache-Control": "public, max-age=31536000, immutable"}
    if download:
        return FileResponse(
            path,
            media_type=media_type,
            filename=filename,
            content_disposition_type="attachment",
            headers=headers,
        )
    return FileResponse(path, media_type=media_type, headers=headers)


@router.delete("/{asset_id}", status_code=204)
async def delete_asset(
    asset_id: str,
    session: AsyncSession = Depends(get_session),
    storage: Storage = Depends(get_storage),
) -> Response:
    asset = await session.get(Asset, asset_id)
    if asset is None:
        raise ApiError(404, "ASSET_NOT_FOUND", "素材不存在")
    if asset.kind != "upload":
        raise ApiError(409, "ASSET_IN_USE", "生成结果不能删除")
    output_ref = (
        await session.execute(
            select(JobOutput.id).where(JobOutput.asset_id == asset_id).limit(1)
        )
    ).first()
    if output_ref:
        raise ApiError(409, "ASSET_IN_USE", "该素材已被作品引用，不能删除")
    jobs = (
        await session.execute(select(Job.id, Job.inputs_json))
    ).all()
    for _job_id, inputs in jobs:
        for item in inputs or []:
            if item.get("asset_id") == asset_id:
                raise ApiError(409, "ASSET_IN_USE", "该素材已被任务引用，不能删除")
    await session.delete(asset)
    await session.commit()
    storage.delete(asset.filename)
    storage.delete(asset.thumb_filename)
    return Response(status_code=204)
