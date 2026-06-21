"""Built-in connectors. Call ``register_builtin_connectors()`` at app/worker startup.

The private enterprise package registers premium connectors into the same
``connector_registry`` the same way.
"""

from refle_extensions.registry import connector_registry

from refle_integrations.connectors.aws import AWSConnector
from refle_integrations.connectors.demo import DemoConnector
from refle_integrations.connectors.github import GitHubConnector
from refle_integrations.connectors.okta import OktaConnector

_BUILTINS = [DemoConnector, AWSConnector, GitHubConnector, OktaConnector]


def register_builtin_connectors() -> None:
    for connector_cls in _BUILTINS:
        instance = connector_cls()
        if instance.key not in connector_registry:
            connector_registry.register(instance.key, instance)


__all__ = [
    "register_builtin_connectors",
    "AWSConnector",
    "DemoConnector",
    "GitHubConnector",
    "OktaConnector",
]
