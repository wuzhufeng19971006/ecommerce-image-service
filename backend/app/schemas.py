from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

WorkflowId = Literal["try_on", "white_bg", "scene", "detail", "five_shots"]
JobStatus = Literal["queued", "running", "succeeded", "failed", "canceled"]
InputRole = Literal["garment", "model", "approved", "reference", "edit_target"]
SizeOption = Literal["1024x1024", "1024x1536", "1536x1024"]
QualityOption = Literal["auto", "low", "medium", "high"]


class ApiErrorBody(BaseModel):
    code: str
    message: str


class ApiErrorResponse(BaseModel):
    error: ApiErrorBody


class JobOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style: str | None = None
    gender: Literal["female", "male"] = "female"
    shot: Literal["full_body", "half_body"] = "full_body"
    pose: Literal["natural", "editorial"] = "natural"
    side: Literal["front", "back"] = "front"
    size: SizeOption = "1024x1536"
    quality: QualityOption = "auto"


class InputAssetIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(min_length=8, max_length=64)
    role: InputRole


class JobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow: WorkflowId
    inputs: list[InputAssetIn] = Field(min_length=1, max_length=4)
    options: JobOptions = Field(default_factory=JobOptions)
    instruction: str = Field(default="", max_length=2000)


class RevisionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feedback: str = Field(min_length=1, max_length=1000)
    output_id: str | None = None
    size: SizeOption | None = None
    quality: QualityOption | None = None


class AssetOut(BaseModel):
    id: str
    kind: Literal["upload", "output"]
    url: str
    thumb_url: str | None
    download_url: str
    original_name: str
    mime_type: str
    width: int
    height: int
    size_bytes: int
    created_at: datetime


class JobInputOut(BaseModel):
    role: InputRole
    asset: AssetOut


class JobErrorOut(BaseModel):
    code: str
    message: str


class JobOut(BaseModel):
    id: str
    workflow: WorkflowId
    status: JobStatus
    instruction: str
    final_prompt: str
    model: str
    options: JobOptions
    size: SizeOption
    quality: QualityOption
    inputs: list[JobInputOut]
    outputs: list[AssetOut]
    error: JobErrorOut | None
    usage: dict | None
    duration_ms: int | None
    parent_job_id: str | None = None
    shots_total: int = 1
    shots_done: int = 0
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class JobPage(BaseModel):
    items: list[JobOut]
    total: int
    page: int
    page_size: int


class GalleryItem(BaseModel):
    job_id: str
    workflow: WorkflowId
    created_at: datetime
    instruction: str
    final_prompt: str
    options: JobOptions
    output: AssetOut


class GalleryPage(BaseModel):
    items: list[GalleryItem]
    total: int
    page: int
    page_size: int


class ConfigOut(BaseModel):
    app_name: str
    version: str
    model: str
    api_base: str
    configured: bool
    mock: bool
    max_reference_images: int


class HealthOut(BaseModel):
    ok: bool
    database: str
    configured: bool
    mock: bool
    model: str
    version: str
