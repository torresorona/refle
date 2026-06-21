# refle

**AI-Powered Automated Compliance for your Business.**

refle is an open-core compliance-automation platform — an alternative to Vanta and
Drata — that weaves AI through the product: a chat assistant for clarifying security
controls, agentic generation of documentation and posture-change notifications, and
**sovereign** mode that runs entirely against local models so your data never leaves
your boundary.

> Status: **Phases 0–4 complete** — foundation, compliance core + auth, automated control
> testing, AI RAG chat, and **Agentic AI** (human-in-the-loop policy drafting & email notifications) — all on `main` and verified end-to-end (including live Gemini and Resend).
> **Phase 5 (Enterprise/SaaS)** is next. See [What works today](#what-works-today) and the
> [roadmap](#roadmap).

## What works today

- **Auth & orgs** — sign-up creates an organization (owner); email/password login over an
  **httpOnly session cookie**; org invitations and role-based access (owner / admin /
  member / auditor).
- **SOC 2 controls & posture** — seeded control catalog, per-org control status, and a live
  posture dashboard (% passing).
- **Evidence** — upload artifacts to object storage (sha256-hashed), link them to controls,
  download via presigned URLs.
- **Policies** — AI-assisted drafting (via Gemini Pro), built-in web editor for drafts, versioning, and capturing per-employee acceptance.
- **Automated control testing** — connect an integration (Demo / AWS / GitHub / Okta), run a
  sync, and have control tests update posture and open remediation tasks automatically;
  scheduled hourly via Celery.
- **AI assistant (RAG)** — ask about your controls/policies/evidence and get answers with
  **citations** (pgvector retrieval). Runs offline with deterministic embeddings, or point
  it at **Gemini** (default), OpenAI, or a local model via one env var.
- **Agentic Workflows & Notifications** — AI-generated summaries of posture changes delivered via **email** and in-app notifications whenever automated tests detect a control failure. Supports **Generic SMTP** (for self-hosted/Google Workspace/Office365 setups) or **Resend API**. Note: *Refle Enterprise* offers custom email integration capabilities and *Refle Hosted* offers a compliant Resend alternative for custom domain notification delivery.

All of the above is covered by tests and was verified end-to-end, including a live Gemini
key (`gemini-3.5-flash` generation + `gemini-embedding-001` indexing) and live Resend integration.

## What's here

| Area | Decision |
| --- | --- |
| Frontend | Next.js (App Router, TypeScript) in `apps/web` |
| Backend | Python / FastAPI in `services/api`; background workers (Celery) in `services/worker` |
| Data | PostgreSQL + `pgvector`, Redis, MinIO (S3-compatible) |
| First framework | **SOC 2** (data model is crosswalk-ready for ISO 27001, etc.) |
| AI | Provider-agnostic gateway (`libs/ai_core`); default model `gemini-3.5-flash`; OpenAI and local (Ollama/vLLM) configurable |
| Connectors | Pluggable framework + Demo, AWS, GitHub, Okta |

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
make seed         # load the SOC 2 control catalog
make api          # FastAPI on http://localhost:8000  (separate terminal)
make web          # Next.js on http://localhost:3000  (separate terminal)
make worker       # Celery worker for scheduled syncs (optional)
```

Open http://localhost:3000, create an organization, and explore the **Controls, Evidence,
Policies, Integrations, and Assistant** tabs. Connect the **Demo** integration and hit
*Sync* to watch automated tests move your posture. API docs are at http://localhost:8000/docs.

**Enable real AI** (optional): add a Google AI Studio key to `.env` as `GEMINI_API_KEY`
(starts with `AIza`), set `REFLE_AI_EMBEDDING_PROVIDER=gemini`, restart the API, then click
**Reindex** in the Assistant tab. Without a key, the assistant uses offline embeddings and
returns retrieval-only answers (still with citations).

**Enable Email Notifications**:
To send emails, `refle` acts as a generic SMTP client. Configure the following environment variables to send emails through your existing provider (e.g. Google Workspace, Office365, or a local Postfix relay):
```env
REFLE_SMTP_HOST=smtp.gmail.com
REFLE_SMTP_PORT=465
REFLE_SMTP_USER=youremail@company.com
REFLE_SMTP_PASSWORD=your_app_password
REFLE_SMTP_TLS=true
REFLE_SMTP_FROM=notifications@company.com
```
*(Alternatively, you can provide a `REFLE_RESEND_API_KEY` to use Resend's API directly).*

Run `make help` to see all developer tasks.

## Repository layout

```
apps/web            Next.js frontend
services/api        FastAPI app (source of truth for the OpenAPI contract)
services/worker     Celery workers (scheduled scans, control tests, agent runs)
libs/core           settings, async DB, compliance domain model
libs/extensions     open-core extension seams (registries + license interface)
libs/integrations   connector framework + Demo/AWS/GitHub/Okta connectors + sync engine
libs/ai_core        provider-agnostic LLM gateway + embeddings (RAG)
content/            SOC 2 control catalog + policy templates (seed data)
deploy/             docker-compose, Helm, Terraform
```

## Roadmap

- ✅ **Phase 0 — Foundation**: monorepo, services, DB, extension seams, AI gateway.
- ✅ **Phase 1 — Compliance core + auth**: cookie auth, orgs/RBAC/invitations, SOC 2 catalog,
  controls + posture, evidence upload, policy versioning + acceptance.
- ✅ **Phase 2 — Automation**: connector framework + Demo/AWS/GitHub/Okta, scheduled tests,
  auto remediation tasks, encrypted credentials.
- ✅ **Phase 3 — AI chat**: provider-agnostic gateway, pgvector RAG over
  controls/policies/evidence, chat with citations (Gemini default, offline fallback).
- ✅ **Phase 4 — Agentic AI**: **human-in-the-loop** AI drafting of policies/docs
  (draft → web editor review → publish) and **posture-change monitoring with email
  notifications (via Resend)** + plain-language AI summaries. Agents run on the same gateway and register
  through the `agent_registry` seam; every run is recorded for audit. No auto-publish, no
  auto-remediation in the community core.
- ⏭ **Phase 5 — Enterprise/SaaS** *(next)*: multi-tenant control plane, SSO/SAML + SCIM, billing
  (private `refle-enterprise` repo).
- **Phase 6 — Expansion**: auditor portal, evidence-package export, ISO 27001 crosswalk,
  sovereign/local-mode polish.

## License

Apache 2.0 — see [LICENSE](LICENSE).
