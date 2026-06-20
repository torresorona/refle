# Licensing & the open-core model

refle follows an **open-core** model, structured as two repositories.

## This repository (community core)

Everything in this repository is licensed under **Apache License 2.0** (see
[LICENSE](LICENSE)). It is fully functional on its own: you can self-host the community
core for a single organization with no license key and no enterprise dependencies.

## The enterprise repository (separate, private)

Proprietary, commercially-licensed features live in a **separate private repository**
(`refle-enterprise`). It depends on the packages published from this repo
(`refle-core`, `refle-extensions`, …) and **composes on top of them** — it never forks
or copies core.

Enterprise features include:

- Multi-tenant SaaS control plane
- SSO/SAML and SCIM
- Billing and usage metering
- Premium connectors
- Advanced AI agents (auto-remediation, full audit-package generation)
- Long-retention / advanced audit log, auditor portal

## How they compose

Core defines **extension seams** in [`libs/extensions`](libs/extensions):

- **Registries** (`connector_registry`, `agent_registry`, `auth_provider_registry`) —
  enterprise registers additional implementations at startup.
- **License interface** (`LicenseProvider`, `has_feature`) — community ships the
  `OSSLicenseProvider`; enterprise calls `set_license_provider(...)` with a validator
  that reads `REFLE_LICENSE_KEY` and unlocks the corresponding features.

Because enterprise lives in its own repository, the rule *"core must never depend on
enterprise"* is enforced structurally: core only ever references the interfaces above.

## Contributing

Contributions to this repository require signing a **Contributor License Agreement
(CLA)** so that contributed code can also be distributed in the commercial build. See
[CONTRIBUTING.md](CONTRIBUTING.md).
