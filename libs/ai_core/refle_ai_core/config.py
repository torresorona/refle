"""AI gateway settings (REFLE_AI_ prefix), plus cloud provider API keys."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AISettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="REFLE_AI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # provider: "gemini" | "openai" | "local"
    provider: str = "gemini"
    model: str = "gemini-3.5-flash"
    embedding_model: str = "gemini-embedding-001"

    # Sovereign mode: any OpenAI-compatible endpoint (Ollama, vLLM, ...).
    local_base_url: str = "http://localhost:11434/v1"
    local_model: str = "llama3.1"

    # Cloud keys use their conventional env names (no REFLE_AI_ prefix).
    gemini_api_key: str | None = Field(default=None, validation_alias="GEMINI_API_KEY")
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")


@lru_cache
def get_ai_settings() -> AISettings:
    return AISettings()
