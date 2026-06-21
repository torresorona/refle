"""Text embeddings for RAG.

Two backends behind one interface:
- ``HashEmbedder``: deterministic, offline (bag-of-hashed-tokens). The dev/test
  default so retrieval works with zero configuration or API keys.
- ``GeminiEmbedder``: real embeddings via the Generative Language API.

Both emit ``EMBED_DIM``-length vectors so the pgvector column dimension is stable
regardless of backend.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence
from typing import Protocol

import httpx

from refle_ai_core.config import AISettings, get_ai_settings

EMBED_DIM = 768

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class Embedder(Protocol):
    dim: int

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class HashEmbedder:
    """Deterministic offline embeddings — shared tokens produce closer vectors."""

    dim = EMBED_DIM

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self.dim
            for token in _tokenize(text):
                h = int(hashlib.md5(token.encode()).hexdigest(), 16)
                vec[h % self.dim] += 1.0 if (h >> 8) & 1 else -1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            vectors.append([v / norm for v in vec])
        return vectors


class GeminiEmbedder:
    dim = EMBED_DIM

    def __init__(self, model: str, api_key: str | None) -> None:
        self.model = model
        self._api_key = api_key

    def embed(self, texts: Sequence[str]) -> list[list[float]]:  # pragma: no cover - needs key
        if not self._api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}"
            ":batchEmbedContents"
        )
        payload = {
            "requests": [
                {
                    "model": f"models/{self.model}",
                    "content": {"parts": [{"text": t}]},
                    "outputDimensionality": self.dim,
                }
                for t in texts
            ]
        }
        with httpx.Client(timeout=60) as client:
            resp = client.post(url, headers={"x-goog-api-key": self._api_key}, json=payload)
            resp.raise_for_status()
            data = resp.json()
        return [e["values"] for e in data["embeddings"]]


def get_embedder(settings: AISettings | None = None) -> Embedder:
    settings = settings or get_ai_settings()
    if settings.embedding_provider == "gemini" and settings.gemini_api_key:
        return GeminiEmbedder(settings.embedding_model, settings.gemini_api_key)
    return HashEmbedder()
