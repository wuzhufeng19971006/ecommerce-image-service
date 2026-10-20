from __future__ import annotations

import base64
import io

import httpx
import pytest
import respx
from PIL import Image

from app.config import Settings
from app.services.relay import RelayClient, RelayError


def _b64_png() -> str:
    buffer = io.BytesIO()
    Image.new("RGB", (512, 640), (120, 100, 90)).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


@pytest.fixture
def relay_settings() -> Settings:
    return Settings(
        image_api_base="https://relay.test/v1",
        image_api_key="test-key",
        image_model="image-2.5",
        image_timeout_seconds=60,
        image_mock=False,
    )


@pytest.mark.asyncio
async def test_edit_parses_sse(relay_settings: Settings):
    client = RelayClient(relay_settings)
    frame = (
        'data: {"b64_json":"' + _b64_png() + '"}\n\n'
        'data: {"usage":{"total_tokens":12}}\n\n'
        "data: [DONE]\n\n"
    )
    with respx.mock:
        route = respx.post("https://relay.test/v1/images/edits").mock(
            return_value=httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=frame.encode(),
            )
        )
        result = await client.edit(
            "test prompt",
            [("garment.png", b"fake-image", "image/png")],
            "1024x1536",
            "auto",
        )
    assert route.called
    assert len(result.images) == 1
    assert result.images[0].width == 512
    assert result.usage == {"total_tokens": 12}


@pytest.mark.asyncio
async def test_edit_parses_json(relay_settings: Settings):
    client = RelayClient(relay_settings)
    payload = {"data": [{"b64_json": _b64_png()}]}
    with respx.mock:
        respx.post("https://relay.test/v1/images/edits").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = await client.edit(
            "test prompt",
            [("garment.png", b"fake-image", "image/png")],
            "1024x1536",
            "auto",
        )
    assert len(result.images) == 1


@pytest.mark.asyncio
async def test_auth_error_mapping(relay_settings: Settings):
    client = RelayClient(relay_settings)
    with respx.mock:
        respx.post("https://relay.test/v1/images/edits").mock(
            return_value=httpx.Response(
                401, json={"error": {"message": "bad key"}}
            )
        )
        with pytest.raises(RelayError) as exc_info:
            await client.edit(
                "test prompt",
                [("garment.png", b"fake-image", "image/png")],
                "1024x1536",
                "auto",
            )
    assert exc_info.value.code == "RELAY_AUTH"


@pytest.mark.asyncio
async def test_no_image_raises(relay_settings: Settings):
    client = RelayClient(relay_settings)
    with respx.mock:
        respx.post("https://relay.test/v1/images/edits").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        with pytest.raises(RelayError) as exc_info:
            await client.edit(
                "test prompt",
                [("garment.png", b"fake-image", "image/png")],
                "1024x1536",
                "auto",
            )
    assert exc_info.value.code == "RELAY_NO_IMAGE"
