"""Auth provider seam for external identity providers (enterprise SSO/OIDC).

The community core handles local password auth directly (it owns the user store).
This seam is for *external* identity providers — the private enterprise package
registers WorkOS-backed SSO/SAML/OIDC providers into ``auth_provider_registry``;
core then JIT-provisions or links a user from the returned :class:`AuthIdentity`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class AuthIdentity:
    """A verified identity returned by an external provider."""

    email: str
    external_id: str | None = None
    full_name: str | None = None
    provider: str = "unknown"
    attributes: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class AuthProvider(Protocol):
    key: str  # e.g. "workos-saml"

    def authenticate(self, credentials: dict[str, Any]) -> AuthIdentity | None:
        """Verify provider-specific credentials (OIDC code, SAML response, ...)."""
        ...
