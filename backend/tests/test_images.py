import io

import pytest
from PIL import Image

from app.services.images import (
    ImageValidationError,
    decode_output_image,
    make_mock_image,
    normalize_upload,
)


def _png_bytes(size=(800, 1000), color=(220, 210, 200)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def test_normalize_upload_reencodes_image():
    payload = normalize_upload(_png_bytes(), "dress.png", 15 * 1024 * 1024, 3072)
    assert payload.width == 800
    assert payload.height == 1000
    assert payload.mime_type == "image/jpeg"
    assert payload.data.startswith(b"\xff\xd8")


def test_normalize_upload_rejects_unknown_format():
    with pytest.raises(ImageValidationError):
        normalize_upload(b"not an image", "x.png", 15 * 1024 * 1024, 3072)


def test_decode_output_image_accepts_data_url():
    import base64

    data = _png_bytes((512, 512))
    payload = decode_output_image(
        "data:image/png;base64," + base64.b64encode(data).decode(),
        40 * 1024 * 1024,
    )
    assert payload.width == 512
    assert payload.mime_type == "image/png"


def test_mock_image_is_generated():
    payload = make_mock_image("一件米色风衣", "1024x1536")
    assert payload.width == 1024
    assert payload.height == 1536
    assert payload.data.startswith(b"\x89PNG")
