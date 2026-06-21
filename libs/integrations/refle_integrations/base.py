"""The connector framework.

A connector authenticates to an external system, ``collect()``s normalized
:class:`Resource` records, and exposes :class:`ControlTest`s — pure functions over
those resources that yield pass/fail evidence for one or more SOC 2 controls.
This keeps evidence collection and evaluation cleanly separable and testable.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class Resource:
    """A normalized item collected from an external system."""

    kind: str  # e.g. "iam_user", "github_repo", "okta_user"
    external_id: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class TestResult:
    passed: bool
    detail: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)


# A control test evaluates the resources a connector collected.
ControlTestFn = Callable[[Sequence[Resource]], TestResult]


@dataclass
class ControlTest:
    key: str  # unique id, e.g. "aws.iam.mfa_enabled"
    control_codes: list[str]  # SOC 2 codes satisfied, e.g. ["CC6.1"]
    description: str
    run: ControlTestFn


@runtime_checkable
class Connector(Protocol):
    key: str  # e.g. "aws"
    name: str
    description: str
    credential_fields: list[str]  # field names the UI prompts for
    tests: list[ControlTest]

    def authenticate(self, credentials: dict[str, Any]) -> Any: ...

    def collect(self, session: Any) -> list[Resource]: ...
