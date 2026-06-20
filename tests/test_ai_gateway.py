"""Provider-agnostic AI gateway selection."""

import pytest
from refle_ai_core.config import AISettings
from refle_ai_core.gateway import AIGateway, build_provider
from refle_ai_core.providers.gemini import GeminiProvider
from refle_ai_core.providers.openai_compatible import OpenAICompatibleProvider


def test_default_provider_is_gemini_flash():
    gw = AIGateway(AISettings())
    assert gw.info.provider == "gemini"
    assert gw.info.model == "gemini-3.5-flash"
    assert gw.info.sovereign is False
    assert isinstance(gw.provider, GeminiProvider)


def test_local_provider_is_sovereign():
    gw = AIGateway(AISettings(provider="local", local_model="llama3.1"))
    assert gw.info.sovereign is True
    assert gw.info.model == "llama3.1"
    assert isinstance(gw.provider, OpenAICompatibleProvider)


def test_openai_provider():
    provider = build_provider(AISettings(provider="openai", model="gpt-4o-mini"))
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.model == "gpt-4o-mini"


def test_unknown_provider_raises():
    with pytest.raises(ValueError):
        build_provider(AISettings(provider="nope"))
