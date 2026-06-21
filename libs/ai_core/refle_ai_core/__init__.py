"""Provider-agnostic AI gateway."""

from refle_ai_core.config import AISettings, get_ai_settings
from refle_ai_core.embeddings import EMBED_DIM, Embedder, get_embedder
from refle_ai_core.gateway import AIGateway, GatewayInfo, build_provider
from refle_ai_core.providers.base import Message

__all__ = [
    "AISettings",
    "get_ai_settings",
    "AIGateway",
    "GatewayInfo",
    "build_provider",
    "Message",
    "EMBED_DIM",
    "Embedder",
    "get_embedder",
]
