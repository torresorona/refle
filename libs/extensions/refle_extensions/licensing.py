"""License / feature-flag seam.

Community ships :class:`OSSLicenseProvider` (no enterprise features). The private
``refle-enterprise`` package calls :func:`set_license_provider` at startup with a
validator that reads ``REFLE_LICENSE_KEY`` and unlocks the corresponding features.
Core gates enterprise behaviour exclusively through :func:`has_feature`.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field


class Tier(enum.StrEnum):
    oss = "oss"
    enterprise = "enterprise"


@dataclass(frozen=True)
class LicenseInfo:
    tier: Tier
    features: frozenset[str] = field(default_factory=frozenset)
    licensed_to: str | None = None


class LicenseProvider:
    def get_license(self) -> LicenseInfo:  # pragma: no cover - interface
        raise NotImplementedError


class OSSLicenseProvider(LicenseProvider):
    def get_license(self) -> LicenseInfo:
        return LicenseInfo(tier=Tier.oss, features=frozenset())


_provider: LicenseProvider = OSSLicenseProvider()


def set_license_provider(provider: LicenseProvider) -> None:
    global _provider
    _provider = provider


def get_license() -> LicenseInfo:
    return _provider.get_license()


def has_feature(name: str) -> bool:
    return name in get_license().features
