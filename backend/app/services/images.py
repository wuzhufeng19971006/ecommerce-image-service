from __future__ import annotations

import base64
import binascii
import hashlib
import io
import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

Image.MAX_IMAGE_PIXELS = 40_000_000

ALLOWED_INPUT_FORMATS = {"JPEG", "PNG", "WEBP"}
ALLOWED_OUTPUT_FORMATS = {"JPEG", "PNG", "WEBP"}
FORMAT_INFO = {
    "JPEG": ("image/jpeg", "jpg"),
    "PNG": ("image/png", "png"),
    "WEBP": ("image/webp", "webp"),
}


class ImageValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ImagePayload:
    data: bytes
    mime_type: str
    extension: str
    width: int
    height: int
    sha256: str

    @property
    def size_bytes(self) -> int:
        return len(self.data)


def _safe_original_name(name: str | None) -> str:
    value = (name or "image").replace("\\", "/").split("/")[-1]
    value = re.sub(r"[\x00-\x1f\x7f]", "", value).strip()
    return value[:200] or "image"


def safe_original_name(name: str | None) -> str:
    return _safe_original_name(name)


def _check_dimensions(width: int, height: int) -> None:
    if width < 32 or height < 32:
        raise ImageValidationError("图片尺寸过小，请上传清晰的产品图")
    if width * height > 40_000_000:
        raise ImageValidationError("图片像素过大，请压缩后再上传")


def normalize_upload(data: bytes, original_name: str | None, max_bytes: int, max_dimension: int) -> ImagePayload:
    if not data:
        raise ImageValidationError("上传文件为空")
    if len(data) > max_bytes:
        raise ImageValidationError(f"图片不能超过 {max_bytes // (1024 * 1024)} MB")
    try:
        with Image.open(io.BytesIO(data)) as probe:
            image_format = (probe.format or "").upper()
            if image_format not in ALLOWED_INPUT_FORMATS:
                raise ImageValidationError("仅支持 JPG、PNG、WebP 图片")
            probe.verify()
        with Image.open(io.BytesIO(data)) as image:
            _check_dimensions(image.width, image.height)
            image = ImageOps.exif_transpose(image)
            has_alpha = image.mode in {"RGBA", "LA", "PA"} or (
                image.mode == "P" and "transparency" in image.info
            )
            if max(image.size) > max_dimension:
                image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            if has_alpha:
                image.convert("RGBA").save(buffer, format="PNG", optimize=True)
                mime, extension = FORMAT_INFO["PNG"]
            else:
                image.convert("RGB").save(
                    buffer, format="JPEG", quality=92, optimize=True, progressive=True
                )
                mime, extension = FORMAT_INFO["JPEG"]
            normalized = buffer.getvalue()
    except ImageValidationError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ImageValidationError("图片无法识别或已损坏") from exc
    except Image.DecompressionBombError as exc:  # type: ignore[attr-defined]
        raise ImageValidationError("图片像素过大，请压缩后再上传") from exc

    with Image.open(io.BytesIO(normalized)) as check:
        width, height = check.size
    return ImagePayload(
        data=normalized,
        mime_type=mime,
        extension=extension,
        width=width,
        height=height,
        sha256=hashlib.sha256(normalized).hexdigest(),
    )


def decode_output_image(value: str, max_bytes: int) -> ImagePayload:
    if not value or not isinstance(value, str):
        raise ImageValidationError("接口没有返回有效图片")
    raw = value.strip()
    if raw.startswith("data:"):
        comma = raw.find(",")
        if comma == -1:
            raise ImageValidationError("接口返回的图片数据格式异常")
        raw = raw[comma + 1 :]
    raw = re.sub(r"\s+", "", raw)
    if len(raw) > max_bytes * 2:
        raise ImageValidationError("接口返回的图片过大")
    try:
        decoded = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        try:
            padded = raw.replace("-", "+").replace("_", "/")
            padded += "=" * (-len(padded) % 4)
            decoded = base64.b64decode(padded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ImageValidationError("接口返回的图片 base64 数据无效") from exc
    if not decoded:
        raise ImageValidationError("接口返回的图片为空")
    if len(decoded) > max_bytes:
        raise ImageValidationError("接口返回的图片过大")
    try:
        with Image.open(io.BytesIO(decoded)) as image:
            image_format = (image.format or "").upper()
            if image_format not in ALLOWED_OUTPUT_FORMATS:
                raise ImageValidationError("接口返回了不支持的图片格式")
            _check_dimensions(image.width, image.height)
            image.load()
            image = ImageOps.exif_transpose(image)
            has_alpha = image.mode in {"RGBA", "LA", "PA"} or (
                image.mode == "P" and "transparency" in image.info
            )
            buffer = io.BytesIO()
            if image_format == "PNG":
                image.convert("RGBA" if has_alpha else "RGB").save(
                    buffer, format="PNG", optimize=True
                )
                mime, extension = FORMAT_INFO["PNG"]
            elif image_format == "WEBP":
                image.convert("RGBA" if has_alpha else "RGB").save(
                    buffer, format="WEBP", quality=95, method=4
                )
                mime, extension = FORMAT_INFO["WEBP"]
            else:
                image.convert("RGB").save(
                    buffer, format="JPEG", quality=95, optimize=True, progressive=True
                )
                mime, extension = FORMAT_INFO["JPEG"]
            normalized = buffer.getvalue()
            width, height = image.size
    except ImageValidationError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ImageValidationError("接口返回的图片无法识别") from exc
    return ImagePayload(
        data=normalized,
        mime_type=mime,
        extension=extension,
        width=width,
        height=height,
        sha256=hashlib.sha256(normalized).hexdigest(),
    )


def make_thumbnail(payload: ImagePayload, max_dimension: int) -> ImagePayload:
    try:
        with Image.open(io.BytesIO(payload.data)) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
            has_alpha = image.mode in {"RGBA", "LA", "PA"} or (
                image.mode == "P" and "transparency" in image.info
            )
            buffer = io.BytesIO()
            if has_alpha:
                image.convert("RGBA").save(buffer, format="PNG", optimize=True)
                mime, extension = FORMAT_INFO["PNG"]
            else:
                image.convert("RGB").save(
                    buffer, format="JPEG", quality=88, optimize=True, progressive=True
                )
                mime, extension = FORMAT_INFO["JPEG"]
            data = buffer.getvalue()
            width, height = image.size
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ImageValidationError("缩略图生成失败") from exc
    return ImagePayload(
        data=data,
        mime_type=mime,
        extension=extension,
        width=width,
        height=height,
        sha256=hashlib.sha256(data).hexdigest(),
    )


def parse_size(size: str) -> tuple[int, int]:
    try:
        width_str, height_str = size.lower().split("x", 1)
        width, height = int(width_str), int(height_str)
    except (ValueError, AttributeError) as exc:
        raise ImageValidationError("图片尺寸参数无效") from exc
    if width <= 0 or height <= 0:
        raise ImageValidationError("图片尺寸参数无效")
    return width, height


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/msyhbd.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]
    for path in candidates:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def make_mock_image(prompt: str, size: str, index: int = 0) -> ImagePayload:
    width, height = parse_size(size)
    image = Image.new("RGB", (width, height), "#F0E9DE")
    draw = ImageDraw.Draw(image)
    for y in range(height):
        ratio = y / max(height - 1, 1)
        r = int(238 - 28 * ratio)
        g = int(230 - 30 * ratio)
        b = int(218 - 26 * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Soft arch backdrop
    draw.rounded_rectangle(
        (int(width * 0.09), int(height * 0.08), int(width * 0.91), int(height * 0.9)),
        radius=int(width * 0.2),
        fill=(250, 247, 241),
    )
    # Minimal hanger illustration
    cx = width // 2
    top = int(height * 0.2)
    draw.ellipse(
        (cx - 22, top - 26, cx + 22, top + 18),
        outline=(130, 110, 94),
        width=4,
    )
    draw.line([(cx, top + 18), (cx, top + 55)], fill=(130, 110, 94), width=4)
    draw.polygon(
        [(cx, top + 52), (cx - int(width * 0.2), top + 132), (cx + int(width * 0.2), top + 132)],
        outline=(130, 110, 94),
        width=4,
    )
    # Simple dress silhouette
    shoulder = int(height * 0.37)
    hem = int(height * 0.7)
    draw.polygon(
        [
            (cx - int(width * 0.1), shoulder),
            (cx - int(width * 0.045), shoulder),
            (cx - int(width * 0.15), hem),
            (cx + int(width * 0.15), hem),
            (cx + int(width * 0.045), shoulder),
            (cx + int(width * 0.1), shoulder),
            (cx + int(width * 0.12), shoulder + 20),
            (cx - int(width * 0.12), shoulder + 20),
        ],
        fill=(190, 158, 129),
    )
    draw.line(
        [(cx - int(width * 0.1), shoulder + 12), (cx + int(width * 0.1), shoulder + 12)],
        fill=(145, 112, 85),
        width=3,
    )
    font_title = _load_font(max(30, width // 22))
    font_body = _load_font(max(18, width // 46))
    title = "衣图 AI · 演示预览"
    sub = f"MOCK / {size} / #{index + 1}"
    snippet = prompt.replace("\n", " ")[:28] + ("..." if len(prompt) > 28 else "")
    draw.text((int(width * 0.12), int(height * 0.77)), title, font=font_title, fill=(43, 38, 33))
    draw.text((int(width * 0.12), int(height * 0.82)), sub, font=font_body, fill=(138, 111, 91))
    draw.text((int(width * 0.12), int(height * 0.86)), snippet, font=font_body, fill=(98, 87, 77))
    draw.rectangle(
        (int(width * 0.12), int(height * 0.92), int(width * 0.12) + int(width * 0.16), int(height * 0.923)),
        fill=(180, 88, 59),
    )
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    data = buffer.getvalue()
    return ImagePayload(
        data=data,
        mime_type="image/png",
        extension="png",
        width=width,
        height=height,
        sha256=hashlib.sha256(data).hexdigest(),
    )
