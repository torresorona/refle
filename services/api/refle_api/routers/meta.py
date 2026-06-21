"""Deployment metadata: version, license tier/features, AI gateway, registries.

This endpoint is what the web shell reads to prove the full contract end to end,
and it demonstrates the open-core seams (license + registries) in action.
"""

from __future__ import annotations

from fastapi import APIRouter
from refle_ai_core.gateway import AIGateway
from refle_core.config import get_settings
from refle_extensions.licensing import get_license
from refle_extensions.registry import agent_registry, connector_registry

from refle_api import __version__

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("")
async def meta() -> dict:
    license_info = get_license()
    gateway = AIGateway().info
    return {
        "name": "refle",
        "version": __version__,
        "edition": get_settings().edition,
        "license": {
            "tier": license_info.tier.value,
            "features": sorted(license_info.features),
        },
        "ai": {
            "provider": gateway.provider,
            "model": gateway.model,
            "sovereign": gateway.sovereign,
        },
        "connectors": connector_registry.names(),
        "agents": agent_registry.names(),
    }
