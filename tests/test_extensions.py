"""The open-core extension seams."""

import pytest
from refle_extensions.licensing import Tier, get_license, has_feature
from refle_extensions.registry import Registry


def test_registry_register_and_get():
    reg: Registry[str] = Registry("thing")
    reg.register("a", "alpha")
    assert reg.get("a") == "alpha"
    assert reg.names() == ["a"]
    assert "a" in reg


def test_registry_rejects_duplicates_unless_override():
    reg: Registry[str] = Registry("thing")
    reg.register("a", "alpha")
    with pytest.raises(ValueError):
        reg.register("a", "beta")
    reg.register("a", "beta", override=True)
    assert reg.get("a") == "beta"


def test_registry_unknown_key():
    reg: Registry[str] = Registry("thing")
    with pytest.raises(KeyError):
        reg.get("missing")


def test_default_license_is_oss_with_no_features():
    info = get_license()
    assert info.tier is Tier.oss
    assert info.features == frozenset()
    assert has_feature("sso") is False
