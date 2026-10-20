from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application settings loaded from the repository root .env file."""

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "衣图 AI"
    app_version: str = "0.1.0"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    app_data_dir: Path = Path("./data")
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    serve_frontend: bool = True

    image_api_base: str = "https://api.apikey.fan/v1"
    image_api_key: str = ""
    image_model: str = "gpt-image-2"
    image_timeout_seconds: int = 900
    image_workers: int = 1
    image_mock: bool = False

    max_upload_bytes: int = 15 * 1024 * 1024
    max_output_bytes: int = 40 * 1024 * 1024
    max_reference_images: int = 4
    max_input_dimension: int = 3072
    thumbnail_dimension: int = 640

    @field_validator("image_api_base")
    @classmethod
    def _clean_base(cls, value: str) -> str:
        value = value.strip().rstrip("/")
        return value or "https://api.apikey.fan/v1"

    @property
    def data_dir(self) -> Path:
        path = self.app_data_dir
        if not path.is_absolute():
            path = ROOT_DIR / path
        return path.resolve()

    @property
    def database_path(self) -> Path:
        return self.data_dir / "app.db"

    @property
    def frontend_dist(self) -> Path:
        return ROOT_DIR / "frontend" / "dist"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def is_configured(self) -> bool:
        return self.image_mock or bool(self.image_api_key.strip())

    @property
    def workers(self) -> int:
        return max(1, min(self.image_workers, 4))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
