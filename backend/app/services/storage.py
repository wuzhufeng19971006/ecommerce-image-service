from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .images import ImagePayload, ImageValidationError, make_thumbnail


@dataclass(frozen=True)
class StoredAsset:
    id: str
    filename: str
    thumb_filename: str
    width: int
    height: int
    size_bytes: int
    sha256: str
    mime_type: str


class Storage:
    def __init__(self, data_dir: Path, thumbnail_dimension: int = 640) -> None:
        self.data_dir = data_dir.resolve()
        self.thumbnail_dimension = thumbnail_dimension
        for folder in ("uploads", "outputs", "thumbs"):
            (self.data_dir / folder).mkdir(parents=True, exist_ok=True)

    def _month_folder(self, kind: str) -> str:
        prefix = "uploads" if kind == "upload" else "outputs"
        stamp = datetime.now(timezone.utc).strftime("%Y/%m")
        return f"{prefix}/{stamp}"

    def _safe_path(self, relative_path: str) -> Path:
        candidate = (self.data_dir / relative_path).resolve()
        if not candidate.is_relative_to(self.data_dir):
            raise ImageValidationError("非法的文件路径")
        return candidate

    def _write_atomic(self, relative_path: str, data: bytes) -> None:
        target = self._safe_path(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_name(target.name + ".tmp")
        try:
            with open(temp, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, target)
        finally:
            if temp.exists():
                try:
                    temp.unlink()
                except OSError:
                    pass

    def save_asset(
        self,
        kind: str,
        payload: ImagePayload,
        original_name: str = "",
    ) -> StoredAsset:
        if kind not in {"upload", "output"}:
            raise ImageValidationError("非法的素材类型")
        asset_id = uuid.uuid4().hex
        folder = self._month_folder(kind)
        relative = f"{folder}/{asset_id}.{payload.extension}"
        thumb = make_thumbnail(payload, self.thumbnail_dimension)
        thumb_relative = f"thumbs/{folder.split('/', 1)[1]}/{asset_id}.{thumb.extension}"
        self._write_atomic(relative, payload.data)
        try:
            self._write_atomic(thumb_relative, thumb.data)
        except Exception:
            self._safe_path(relative).unlink(missing_ok=True)
            raise
        return StoredAsset(
            id=asset_id,
            filename=relative,
            thumb_filename=thumb_relative,
            width=payload.width,
            height=payload.height,
            size_bytes=payload.size_bytes,
            sha256=payload.sha256,
            mime_type=payload.mime_type,
        )

    def path_for(self, relative_path: str | None) -> Path | None:
        if not relative_path:
            return None
        path = self._safe_path(relative_path)
        return path if path.is_file() else None

    def read(self, relative_path: str) -> bytes:
        path = self._safe_path(relative_path)
        if not path.is_file():
            raise FileNotFoundError(relative_path)
        return path.read_bytes()

    def delete(self, relative_path: str | None) -> None:
        if not relative_path:
            return
        path = self._safe_path(relative_path)
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
