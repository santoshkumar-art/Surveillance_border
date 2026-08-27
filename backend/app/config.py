"""Application configuration loaded from environment variables / .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings. Every field can be overridden with a ``BSS_`` env var."""

    model_config = SettingsConfigDict(
        env_prefix="BSS_",
        env_file=(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- security -----------------------------------------------------------
    secret_key: str = "dev-only-insecure-secret-key"
    access_token_ttl_minutes: int = 720
    algorithm: str = "HS256"

    admin_username: str = "officer"
    admin_password: str = "border123"
    admin_full_name: str = "Border Control Officer"

    # --- storage ------------------------------------------------------------
    data_dir: Path = REPO_ROOT / "data"
    models_dir: Path = REPO_ROOT / "models"
    database_url: str = ""
    max_upload_mb: int = 2048

    # --- inference ----------------------------------------------------------
    frame_stride: int = Field(default=5, ge=1, le=120)
    detection_confidence: float = Field(default=0.35, ge=0.01, le=0.99)
    face_confidence: float = Field(default=0.6, ge=0.01, le=0.99)
    plate_confidence: float = Field(default=0.3, ge=0.01, le=0.99)
    drone_confidence: float = Field(default=0.35, ge=0.01, le=0.99)
    inference_image_size: int = Field(default=640, ge=320, le=1280)
    enable_plate_ocr: bool = True
    write_annotated_video: bool = True

    # --- api ----------------------------------------------------------------
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @field_validator("data_dir", "models_dir", mode="after")
    @classmethod
    def _absolute(cls, value: Path) -> Path:
        return value if value.is_absolute() else (REPO_ROOT / value).resolve()

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def thumbnails_dir(self) -> Path:
        return self.data_dir / "thumbnails"

    @property
    def sqlalchemy_url(self) -> str:
        if not self.database_url:
            return f"sqlite:///{self.data_dir / 'border_security.db'}"
        prefix = "sqlite:///"
        if self.database_url.startswith(prefix):
            raw = self.database_url[len(prefix) :]
            path = Path(raw)
            if not path.is_absolute():
                path = (REPO_ROOT / path).resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            return f"{prefix}{path}"
        return self.database_url

    def ensure_directories(self) -> None:
        for directory in (
            self.data_dir,
            self.models_dir,
            self.uploads_dir,
            self.processed_dir,
            self.thumbnails_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
