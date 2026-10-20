from __future__ import annotations

import io
from pathlib import Path

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from PIL import Image

from app.config import Settings
from app.main import create_app


@pytest.fixture
def png_bytes() -> bytes:
    image = Image.new("RGB", (640, 900), (238, 228, 214))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        app_data_dir=tmp_path / "data",
        image_mock=True,
        image_api_key="",
        image_workers=1,
        serve_frontend=False,
        cors_origins="http://testserver",
        image_timeout_seconds=60,
    )


@pytest_asyncio.fixture
async def app(settings: Settings):
    application = create_app(settings)
    async with LifespanManager(application):
        yield application


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as session:
        yield session


async def upload_png(client: AsyncClient, data: bytes, name: str = "dress.png"):
    response = await client.post(
        "/api/assets",
        files={"file": (name, data, "image/png")},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def wait_for_job(client: AsyncClient, job_id: str, timeout: float = 8.0):
    import asyncio

    deadline = asyncio.get_event_loop().time() + timeout
    latest = None
    while asyncio.get_event_loop().time() < deadline:
        response = await client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200, response.text
        latest = response.json()
        if latest["status"] in {"succeeded", "failed", "canceled"}:
            return latest
        await asyncio.sleep(0.1)
    raise AssertionError(f"job did not finish: {latest}")
