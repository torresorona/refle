# Contributing to refle

Thanks for your interest in contributing! refle is open core — this repository is the
Apache-2.0 community core. Please read [LICENSING.md](LICENSING.md) first.

## Contributor License Agreement

By submitting a pull request you agree to the project **CLA**, which lets your
contribution be distributed both in the open-source core and in the commercial build.

## Development setup

See [docs/development.md](docs/development.md) for the full guide. In short:

```bash
cp .env.example .env
make install
make up && make migrate
make api    # and, in another terminal, `make web`
```

## Before you open a PR

```bash
make lint   # ruff (Python) + next lint (web)
make test   # pytest
make fmt    # ruff format
```

## Guidelines

- **Never import enterprise code from core.** New extensibility belongs behind a seam in
  `libs/extensions` (a registry or the license interface), not a hard dependency.
- **Keep the API the source of truth.** Add endpoints in `services/api`; the TypeScript
  client is generated from its OpenAPI schema — don't hand-write API types in the web app.
- **Tenant-scope new tables.** Domain models that belong to an organization should use
  `TenantMixin` (`organization_id`).
- **Connectors** implement the `Connector` protocol in `libs/integrations` and register
  via `connector_registry`; keep collection (`collect`) separate from evaluation (`tests`).
- Match the style of surrounding code; run the formatter.
