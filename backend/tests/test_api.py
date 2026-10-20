from __future__ import annotations

import base64

import pytest
from httpx import AsyncClient

from app.services.images import make_thumbnail
from tests.conftest import upload_png, wait_for_job


@pytest.mark.asyncio
async def test_config_and_meta(client: AsyncClient):
    config = await client.get("/api/config")
    assert config.status_code == 200
    data = config.json()
    assert data["configured"] is True
    assert data["mock"] is True
    assert data["model"]

    meta = await client.get("/api/meta")
    assert meta.status_code == 200
    payload = meta.json()
    assert len(payload["workflows"]) == 5
    assert payload["workflows"][0]["id"] == "try_on"
    assert payload["workflows"][-1]["id"] == "five_shots"
    assert len(payload["workflows"][-1]["shot_plan"]) == 5

    health = await client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["ok"] is True


@pytest.mark.asyncio
async def test_upload_and_mock_generation_flow(client: AsyncClient, png_bytes: bytes):
    asset = await upload_png(client, png_bytes)
    assert asset["url"].startswith("/api/assets/")
    assert asset["width"] == 640
    content = await client.get(asset["url"])
    assert content.status_code == 200
    assert content.headers["content-type"].startswith("image/")

    response = await client.post(
        "/api/jobs",
        json={
            "workflow": "try_on",
            "inputs": [{"asset_id": asset["id"], "role": "garment"}],
            "options": {"style": "studio", "size": "1024x1536", "quality": "auto"},
            "instruction": "自然通勤",
        },
    )
    assert response.status_code == 202, response.text
    created = response.json()
    assert created["status"] == "queued"
    finished = await wait_for_job(client, created["id"])
    assert finished["status"] == "succeeded", finished
    assert len(finished["outputs"]) == 1
    output = finished["outputs"][0]
    assert output["width"] == 1024
    preview = await client.get(output["url"])
    assert preview.status_code == 200
    thumb = await client.get(output["thumb_url"])
    assert thumb.status_code == 200
    download = await client.get(output["download_url"])
    assert download.status_code == 200
    assert "attachment" in download.headers.get("content-disposition", "")

    gallery = await client.get("/api/gallery")
    assert gallery.status_code == 200
    assert gallery.json()["total"] == 1
    assert gallery.json()["items"][0]["output"]["id"] == output["id"]

    jobs = await client.get("/api/jobs")
    assert jobs.status_code == 200
    assert jobs.json()["total"] == 1


@pytest.mark.asyncio
async def test_retry_creates_new_job(client: AsyncClient, png_bytes: bytes):
    asset = await upload_png(client, png_bytes)
    response = await client.post(
        "/api/jobs",
        json={
            "workflow": "white_bg",
            "inputs": [{"asset_id": asset["id"], "role": "garment"}],
            "options": {"style": "white", "size": "1024x1024", "quality": "auto"},
        },
    )
    job = response.json()
    finished = await wait_for_job(client, job["id"])
    assert finished["status"] == "succeeded"
    retry = await client.post(f"/api/jobs/{job['id']}/retry")
    assert retry.status_code == 202, retry.text
    new_job = retry.json()
    assert new_job["id"] != job["id"]
    retried = await wait_for_job(client, new_job["id"])
    assert retried["status"] == "succeeded"


@pytest.mark.asyncio
async def test_invalid_job_inputs(client: AsyncClient, png_bytes: bytes):
    asset = await upload_png(client, png_bytes)
    response = await client.post(
        "/api/jobs",
        json={
            "workflow": "try_on",
            "inputs": [{"asset_id": asset["id"], "role": "reference"}],
            "options": {"style": "studio"},
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "JOB_OPTIONS_INVALID"


@pytest.mark.asyncio
async def test_asset_delete_guard(client: AsyncClient, png_bytes: bytes):
    asset = await upload_png(client, png_bytes)
    response = await client.delete(f"/api/assets/{asset['id']}")
    assert response.status_code == 204
    missing = await client.get(asset["url"])
    assert missing.status_code == 404

    asset = await upload_png(client, png_bytes, "dress-2.png")
    response = await client.post(
        "/api/jobs",
        json={
            "workflow": "detail",
            "inputs": [{"asset_id": asset["id"], "role": "garment"}],
            "options": {"style": "fabric", "size": "1024x1024", "quality": "auto"},
        },
    )
    assert response.status_code == 202
    blocked = await client.delete(f"/api/assets/{asset['id']}")
    assert blocked.status_code == 409


@pytest.mark.asyncio
async def test_upload_rejects_fake_image(client: AsyncClient):
    response = await client.post(
        "/api/assets",
        files={"file": ("fake.png", b"not really a png", "image/png")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UPLOAD_INVALID"


@pytest.mark.asyncio
async def test_five_shot_generation(client: AsyncClient, png_bytes: bytes):
    product_one = await upload_png(client, png_bytes, "product-one.png")
    product_two = await upload_png(client, png_bytes, "product-two.png")
    response = await client.post(
        "/api/jobs",
        json={
            "workflow": "five_shots",
            "inputs": [
                {"asset_id": product_one["id"], "role": "garment"},
                {"asset_id": product_two["id"], "role": "reference"},
            ],
            "options": {"size": "1024x1024", "quality": "auto"},
            "instruction": "套装，注意腰头和裤脚",
        },
    )
    assert response.status_code == 202, response.text
    job = response.json()
    assert job["shots_total"] == 5
    assert job["shots_done"] == 0
    finished = await wait_for_job(client, job["id"], timeout=15)
    assert finished["status"] == "succeeded", finished
    assert finished["shots_total"] == 5
    assert finished["shots_done"] == 5
    assert len(finished["outputs"]) == 5
    assert "【第1张 · 主图】" in finished["final_prompt"]
    assert "【第5张 · 补充信息图】" in finished["final_prompt"]
    assert all(output["kind"] == "output" for output in finished["outputs"])

    gallery = await client.get("/api/gallery?workflow=five_shots&page_size=20")
    assert gallery.status_code == 200
    assert gallery.json()["total"] == 5


@pytest.mark.asyncio
async def test_targeted_revision_uses_edit_target(client: AsyncClient, png_bytes: bytes):
    garment = await upload_png(client, png_bytes, "garment.png")
    model = await upload_png(client, png_bytes, "model.png")
    approved = await upload_png(client, png_bytes, "approved.png")
    response = await client.post(
        "/api/jobs",
        json={
            "workflow": "try_on",
            "inputs": [
                {"asset_id": garment["id"], "role": "garment"},
                {"asset_id": model["id"], "role": "model"},
                {"asset_id": approved["id"], "role": "approved"},
            ],
            "options": {"style": "studio", "size": "1024x1536", "quality": "auto"},
            "instruction": "自然站姿",
        },
    )
    assert response.status_code == 202, response.text
    job = response.json()
    parent = await wait_for_job(client, job["id"])
    assert parent["status"] == "succeeded"
    assert parent["outputs"]

    revision = await client.post(
        f"/api/jobs/{job['id']}/revise",
        json={
            "feedback": "站姿太僵，手指像展示式张开；皮肤磨皮太重。保持脸和服装不变。",
            "output_id": parent["outputs"][0]["id"],
        },
    )
    assert revision.status_code == 202, revision.text
    revised = revision.json()
    assert revised["parent_job_id"] == job["id"]
    assert any(item["role"] == "edit_target" for item in revised["inputs"])
    assert "EDIT TARGET" in revised["final_prompt"]
    assert "站姿太僵" in revised["final_prompt"]
    assert revised["inputs"][-1]["asset"]["kind"] == "output"

    finished = await wait_for_job(client, revised["id"])
    assert finished["status"] == "succeeded", finished
    assert finished["outputs"][0]["id"] != parent["outputs"][0]["id"]


@pytest.mark.asyncio
async def test_cancel_finished_job_rejected(client: AsyncClient, png_bytes: bytes):
    asset = await upload_png(client, png_bytes)
    response = await client.post(
        "/api/jobs",
        json={
            "workflow": "scene",
            "inputs": [{"asset_id": asset["id"], "role": "garment"}],
            "options": {"style": "city", "size": "1024x1536", "quality": "auto"},
        },
    )
    job = response.json()
    await wait_for_job(client, job["id"])
    cancel = await client.post(f"/api/jobs/{job['id']}/cancel")
    assert cancel.status_code == 409
