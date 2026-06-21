"""Application settings, loaded from environment / .env with the REFLE_ prefix."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="REFLE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: str = "development"
    secret_key: str = "dev-only-insecure-secret-change-me-in-production"

    # Async SQLAlchemy URL (asyncpg driver).
    database_url: str = "postgresql+asyncpg://refle:refle@localhost:5432/refle"
    redis_url: str = "redis://localhost:6379/0"

    # NoDecode: skip pydantic-settings JSON-decoding so a plain CSV env value
    # (e.g. "a,b") reaches the validator below instead of failing as invalid JSON.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    # Object storage (MinIO / S3-compatible).
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "refle"
    s3_secret_key: str = "refle-secret"
    s3_bucket: str = "refle-evidence"

    # Email
    resend_api_key: str | None = Field(default=None, validation_alias="RESEND_API_KEY")
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_tls: bool = True
    smtp_from: str = "notifications@refle.ai"

    # Enterprise: a license key unlocks features registered by refle-enterprise.
    license_key: str | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        """Allow REFLE_CORS_ORIGINS to be a comma-separated string."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.env.lower() in {"production", "prod"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
