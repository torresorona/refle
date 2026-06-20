"""Open-core extension seams."""

from refle_extensions.licensing import (
    LicenseInfo,
    LicenseProvider,
    OSSLicenseProvider,
    Tier,
    get_license,
    has_feature,
    set_license_provider,
)
from refle_extensions.registry import (
    Registry,
    agent_registry,
    auth_provider_registry,
    connector_registry,
)

__all__ = [
    "Registry",
    "connector_registry",
    "agent_registry",
    "auth_provider_registry",
    "LicenseInfo",
    "LicenseProvider",
    "OSSLicenseProvider",
    "Tier",
    "get_license",
    "has_feature",
    "set_license_provider",
]
