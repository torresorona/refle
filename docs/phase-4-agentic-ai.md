# Phase 4 — Agentic AI (detailed implementation plan)

This is the in-repo, execution-ready plan for Phase 4. It is written to be picked up
cold by a coding agent (e.g. Antigravity + Gemini Pro 3.1). Each work item lists the
files to touch, the interface to build, acceptance criteria, and tests.

**Phase 4 delivers the second AI "front":** agents that *do work* — draft documents and
watch posture — on the existing provider-agnostic gateway. **Human-in-the-loop is
mandatory in the community core: nothing auto-publishes and nothing auto-remediates.**

---

## 0. Where you're building (current state)

Phases 0–3 are done and on `main`. Build on these:

| Area | Path | Notes |
| --- | --- | --- |
| LLM gateway | `libs/ai_core/refle_ai_core/gateway.py` | `AIGateway.chat()`, provider-agnostic |
| Providers | `libs/ai_core/refle_ai_core/providers/` | `gemini.py` (header auth), `openai_compatible.py` |
| AI settings | `libs/ai_core/refle_ai_core/config.py` | `AISettings` (env prefix `REFLE_AI_`) |
| Embeddings/RAG | `libs/ai_core/.../embeddings.py`, `services/api/refle_api/rag.py` | `retrieve()` for context |
| Agent seam | `libs/extensions/refle_extensions/registry.py` | `agent_registry` (already exists, empty) |
| Policies | `libs/core/refle_core/models/policy.py`, `services/api/refle_api/routers/policies.py` | versioning + acceptance |
| Sync engine | `libs/integrations/refle_integrations/engine.py` | `run_connection()` → results + posture + remediation |
| Worker | `services/worker/refle_worker/celery_app.py` | `sync_all_connections` beat task |
| Domain models | `libs/core/refle_core/models/` | tenant-scoped via `TenantMixin`; register in `models/__init__.py` |

---

## 1. Model strategy — use a stronger model for agents

Chat (`/ai/chat`) stays on the cheap, fast tier (`gemini-3.5-flash`). **Agentic tasks
(policy drafting, posture summarization, reasoning) need more capability → use Gemini
Pro 3.1 as a separate "agent" tier.** Keep it provider-agnostic and configurable.

- Add to `AISettings`: `agent_model: str = "gemini-3.1-pro"` (env `REFLE_AI_AGENT_MODEL`).
  > ⚠️ Confirm the exact model id against the live API before relying on it — we already
  > hit this with `gemini-3.5-flash`. If it 404s, the gateway should surface a clean error
  > (see the `/ai/chat` fallback pattern), not a 500.
- `AIGateway` gains an agent-tier path, e.g. `AIGateway.for_agent()` or a `model=` override
  on `chat()`, so agents call the Pro model while chat stays on flash.
- **Structured output**: agents should request JSON via Gemini's `responseSchema`
  (`generationConfig.responseMimeType="application/json"` + a schema) so outputs parse
  deterministically. Add a `generate_structured(messages, schema)` method to the provider
  interface; fall back to plain text + best-effort JSON parse for providers without it.
- **Tool/function calling (optional, later)**: for richer agents, expose read-only tools
  (fetch controls/posture/policies). MVP keeps it prompt-based with RAG context to limit
  scope; note tool-calling as a follow-up.
- All of the above flows through the gateway, so Claude/OpenAI/local remain drop-in.

---

## 2. Work items

### WI-1 — Agent framework + audit trail (`AiRun`)
- **Goal:** a uniform way to run agents and record every run for audit.
- **Files:** new `libs/core/refle_core/models/ai_run.py` (`AiRun`: tenant-scoped;
  `agent_key`, `input` JSONB, `output` Text, `status` enum `running|succeeded|failed`,
  `model`, `error`, timestamps); register in `models/__init__.py`; new
  `libs/ai_core/refle_ai_core/agents/base.py` (`Agent` protocol: `key`, `name`,
  `description`, `run(context, params) -> AgentResult`).
- **Interface:** built-in agents register into `refle_extensions.agent_registry` via a
  `register_builtin_agents()` (mirror `register_builtin_connectors()`); call it from the
  API lifespan (`services/api/refle_api/main.py`) and the worker.
- **Acceptance:** running any agent writes an `AiRun` row (succeeded/failed); `/meta`
  `agents` list is populated.
- **Tests:** an `AiRun` is created with correct status on success and on a raised error.

### WI-2 — Gateway: agent model + structured generation
- **Goal:** agents use the Pro model and structured JSON output.
- **Files:** `libs/ai_core/refle_ai_core/config.py` (`agent_model`), `gateway.py`
  (`for_agent()`/model override), `providers/base.py` + `providers/gemini.py` +
  `providers/openai_compatible.py` (`generate_structured`).
- **Acceptance:** `AIGateway().for_agent().info.model` reflects `REFLE_AI_AGENT_MODEL`;
  structured calls return parsed dicts; offline/local provider still works for tests.
- **Tests:** model selection unit test; structured-parse unit test with a stub provider.

### WI-3 — `draft-policy` agent + draft/publish workflow
- **Goal:** AI drafts a policy; a human reviews and publishes. No auto-publish.
- **Files:** `libs/core/refle_core/models/policy.py` (add `PolicyVersion.status` enum
  `draft|published`, default `published` for back-compat of existing rows — migration
  must backfill existing versions to `published`); new agent
  `libs/ai_core/refle_ai_core/agents/draft_policy.py`; `routers/policies.py` (+ a new
  `routers/ai_agents.py` or extend `routers/ai.py`).
- **Behavior:** gather context — in-scope SOC 2 controls, related existing policies via
  `rag.retrieve()`, connected integrations + current posture — prompt the **agent model**
  with a policy-template system prompt, save the result as a **draft** `PolicyVersion`
  + an `AiRun`.
- **API:** `POST /ai/agents/draft-policy {name, instructions?}` (owner/admin) → draft;
  `POST /policies/{id}/versions/{version}/publish` (owner/admin) → mark published.
  Acceptance counts/posture only consider the latest **published** version.
- **Acceptance:** drafting creates `PolicyVersion(status=draft)` + `AiRun(succeeded)`;
  publishing flips it; `accept` targets the published version.
- **Tests:** offline gateway → draft created (status=draft); publish flow; acceptance
  ignores drafts.

### WI-4 — Posture-change detection + `Notification` model
- **Goal:** detect when a control flips passing↔failing and record a notification.
- **Files:** new `libs/core/refle_core/models/notification.py` (`Notification`:
  tenant-scoped; `type`, `title`, `body`, `level` enum `info|warning`, `read_at`);
  modify `libs/integrations/refle_integrations/engine.py` `run_connection()` to capture
  each control's **previous** status before applying results, diff, and create a
  `Notification` on a flip or a newly-opened remediation task.
- **Acceptance:** a sync that flips CC6.1 passing→failing creates one `Notification`.
- **Tests:** simulate two syncs (pass then fail via different connector data) → exactly
  one warning notification on the change.

### WI-5 — Notification dispatch (Slack + email) + settings
- **Goal:** deliver notifications out-of-band; configurable per org; secrets encrypted.
- **Files:** new `libs/core/refle_core/models/notification.py` (`NotificationSetting`:
  `slack_webhook_url` (Fernet-encrypted via `refle_core.crypto`), `email_to`,
  `channels`); new `services/api/refle_api/notify.py` (Slack incoming-webhook POST via
  httpx; email via stdlib `smtplib` or env SMTP); call dispatch from the engine + the
  Celery `sync_all_connections` task. Graceful no-op when unconfigured.
- **API:** `GET /notifications`, `POST /notifications/{id}/read`,
  `GET/PUT /ai/notification-settings` (owner/admin).
- **Acceptance:** with a Slack webhook set, a posture change posts to Slack (mock in
  tests); unset → no-op, no error.
- **Tests:** dispatch is invoked with the right payload (httpx mocked); unconfigured = no call.

### WI-6 — `posture-summary` agent
- **Goal:** turn a batch of posture deltas into a plain-language summary + suggested
  remediation, attached to the notification body.
- **Files:** `libs/ai_core/refle_ai_core/agents/posture_summary.py`; used by the engine
  hook (WI-4) before creating the notification. Uses the **agent model**.
- **Acceptance:** notification body contains the AI summary when the model is available;
  falls back to a templated summary when it isn't (mirror the `/ai/chat` fallback).
- **Tests:** offline → templated fallback summary present; `AiRun` recorded.

### WI-7 — Web
- **Files:** `apps/web/components/policies-panel.tsx` (a **"Draft with AI"** action →
  show the draft → **Publish**); a notifications surface (bell/list) — extend the
  dashboard nav or the Integrations tab; a notification-settings form; `apps/web/lib/api.ts`
  (new methods); regenerate the SDK with `make openapi`.
- **Acceptance:** owner/admin can draft → review → publish a policy from the UI; posture
  changes appear as notifications with their AI summary.

### WI-8 — Tests + verification
- **Offline-safe:** every AI test must pin the gateway/embeddings offline like
  `tests/test_ai.py` does (`monkeypatch.setenv("REFLE_AI_PROVIDER","local")` +
  `REFLE_AI_EMBEDDING_PROVIDER=hash` + `ai_config.get_ai_settings.cache_clear()`). Tests
  must never hit the real API even with a key in `.env`.
- **Browser:** draft a policy with AI → review → publish; trigger a posture change → see a
  notification with summary.
- **Live (manual, with a real key):** set `GEMINI_API_KEY` + `REFLE_AI_AGENT_MODEL`,
  reindex, draft a policy, confirm a real grounded draft.

---

## 3. Cross-cutting principles & guardrails

- **Human-in-the-loop / no autonomy in core:** no auto-publish, no auto-remediation.
  Agents *propose*; humans *approve*.
- **Auditability:** every agent execution → an `AiRun` (inputs, output, model, status).
- **Open-core boundary:** built-in agents register through `agent_registry`. The private
  `refle-enterprise` repo adds advanced agents (auto-remediation, full SSP/audit-package
  generation, advanced routing) the same way — core must not import enterprise.
- **Provider-agnostic + sovereign:** agents go through the gateway; a local model
  (Ollama/vLLM) must work end-to-end with no external calls.
- **Secrets:** Slack webhooks and any credentials encrypted at rest (`refle_core.crypto`);
  never log keys (Gemini already uses the `x-goog-api-key` header).
- **Durability:** keep **Celery** for scheduled/async; `AiRun` gives audit + checkpoints.
  **Defer Temporal** until agent chains are genuinely multi-step.

---

## 4. Definition of done (quality gates)

Run before considering Phase 4 complete:

```bash
make lint          # ruff + next lint, clean
make test          # pytest (offline; no real API calls)
make openapi       # regenerate the TS SDK after API changes
npm run build --workspace apps/web   # web typechecks/builds
make up && make migrate              # migrations apply cleanly
```

Migration gotchas seen in earlier phases (watch for them):
- Reusing an existing PG enum across tables → set `create_type=False` on the column.
- `pgvector` columns → the autogenerated migration needs
  `import pgvector.sqlalchemy.vector` added manually.

---

## 5. Open items to confirm

- **Exact model id for "Gemini Pro 3.1"** (set `REFLE_AI_AGENT_MODEL`); verify it resolves
  on the Generative Language API before depending on it.
- **Email transport** (SMTP env vs a provider) — pick during WI-5.
- **Notifications UI placement** — its own nav tab vs a bell in the header.
