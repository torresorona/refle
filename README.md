# refle

**AI-Powered Automated Compliance for your Business.**

refle is an open-core compliance-automation platform — an alternative to Vanta and
Drata — that weaves AI through the product: a chat assistant for clarifying security
controls, agentic generation of documentation and posture-change notifications, and
**sovereign** mode that runs entirely against local models so your data never leaves
your boundary.

> Status: **early foundation (Phase 0)**. The monorepo, services, extension seams, and
> AI gateway are scaffolded and runnable. The compliance engine, connectors, and AI
> features land in subsequent phases — see [the roadmap](#roadmap).

## What's here

| Area | Decision |
| --- | --- |
| Frontend | Next.js (App Router, TypeScript) in `apps/web` |
| Backend | Python / FastAPI in `services/api`; background workers (Celery) in `services/worker` |
| Data | PostgreSQL + `pgvector`, Redis, MinIO (S3-compatible) |
| First framework | **SOC 2** (data model is crosswalk-ready for ISO 27001, etc.) |
| AI | Provider-agnostic gateway (`libs/ai_core`); default model `gemini-3.5-flash`; OpenAI and local (Ollama/vLLM) configurable |
| First connectors | AWS, GitHub, Okta (Phase 2) |

## Open core

This repository is **100% Apache-2.0 community core**. The proprietary enterprise tier
(multi-tenant SaaS control plane, SSO/SAML + SCIM, billing, premium connectors, advanced
AI agents) lives in a **separate private repository** that depends on these packages and
composes on top through the seams in `libs/extensions` (registries + a license/feature
interface). Core never imports enterprise code. See [LICENSING.md](LICENSING.md).

## Quickstart

Prerequisites: **Docker**, **Node 20+**, and [**uv**](https://docs.astral.sh/uv/).

```bash
cp .env.example .env
make install      # npm install + uv sync --all-packages
make up           # start Postgres, Redis, MinIO
make migrate      # apply database migrations
make api          # FastAPI on http://localhost:8000  (separate terminal)
make web          # Next.js on http://localhost:3000  (separate terminal)
```

Open http://localhost:3000 — the dashboard reads `/meta` from the API and shows the
version, license tier, and active AI model. API docs are at http://localhost:8000/docs.

Run `make help` to see all developer tasks.

## Repository layout

```
apps/web            Next.js frontend
services/api        FastAPI app (source of truth for the OpenAPI contract)
services/worker     Celery workers (scheduled scans, control tests, agent runs)
libs/core           settings, async DB, compliance domain model
libs/extensions     open-core extension seams (registries + license interface)
libs/integrations   connector framework (+ AWS/GitHub/Okta in Phase 2)
libs/ai_core        provider-agnostic LLM gateway
content/            SOC 2 control catalog + policy templates (seed data)
deploy/             docker-compose, Helm, Terraform
```

## Roadmap

- **Phase 0 — Foundation** *(in progress)*: monorepo, services, DB, extension seams, AI gateway.
- **Phase 1 — Compliance core**: SOC 2 catalog, controls UI, evidence upload, policies, posture dashboard.
- **Phase 2 — Automation**: connector framework + AWS/GitHub/Okta, scheduled tests, remediation tasks.
- **Phase 3 — AI chat**: RAG over controls/policies/evidence with citations.
- **Phase 4 — Agentic AI**: doc generation + posture-change monitoring & notifications.
- **Phase 5 — Enterprise/SaaS**: multi-tenant control plane, SSO/SAML, billing (private repo).
- **Phase 6 — Expansion**: auditor portal, evidence export, ISO 27001 crosswalk, sovereign polish.

## License

Apache 2.0 — see [LICENSE](LICENSE).
