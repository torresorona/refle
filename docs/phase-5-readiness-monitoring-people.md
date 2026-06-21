# Phase 5 — Audit-readiness, Continuous Monitoring & People/Access Reviews

> **STATUS: ✅ DELIVERED (2026-06-21) — 100% open-core (Apache community core).**
> Everything below shipped in the community core; **none of it is enterprise-gated.** It works
> with no Refle-managed AI (BYO key or local/sovereign). Branch
> `phase-5-readiness-monitoring-people` → [PR #3](https://github.com/torresorona/refle/pull/3).
> Verification: ruff clean, full pytest green, `next build` passes, migrations apply, and the
> Readiness/People surfaces were browser-verified.
>
> **What was deliberately NOT in Phase 5 (it's Enterprise / later):** multi-org "Account/Group"
> admin, instance/operator admin, global-catalog editing, SSO/SAML + SCIM, Refle-managed AI
> models. See `docs/phase-6-admin-and-editions.md` for the open-core admin wrap-up (Tier 1,
> delivered) and the enterprise roadmap.

In-repo, execution-ready plan. Written to be picked up cold by a coding agent. Each work
item lists the files to touch, the interface, acceptance criteria, and tests — same format as
`docs/phase-4-agentic-ai.md`.

**Phase 5 turns the data from Phases 1–4 into an audit-grade product.** It has three
workstreams, all in the **Apache community core**:

- **5A — Audit-readiness & reporting:** coverage/gap analysis, framework progress, and an
  exportable audit package (the auditor-facing payoff).
- **5B — Connector depth & continuous monitoring:** real AWS/GitHub/Okta tests, a bigger SOC 2
  catalog, posture trend history, and per-connection monitoring schedules.
- **5C — People & access reviews:** employees, on/offboarding, periodic access reviews, and
  security-training tracking (covers the SOC 2 CC1 / access-management domain we don't have yet).

---

## 0. Cross-cutting principles (read first)

- **Open-core, no Refle-managed AI assumed.** Every Phase 5 feature must work with **no AI**, a
  **BYO provider key**, or a **local/sovereign** model. AI is *additive* (e.g. an SSP narrative),
  never required, and always has a templated fallback (mirror the Phase 4 `draft-policy` pattern).
  "Refle-offered AI models" are an **edition** differentiator, not a core dependency. See the
  editions split below.
- **Editions (packaging).** Three offerings — **Hosted Core** (now; BYO AI, no enterprise
  features), **Hosted Enterprise** (Coming Soon, gated on Refle attaining SOC 2 + FedRAMP),
  **On-Prem Enterprise** (white-glove, in customer infra, with support). Anything enterprise
  (advanced agents, auto-remediation, WorkOS SSO/SCIM, Refle-managed models) stays behind the
  `libs/extensions` license/`has_feature` seam and lives in the private `refle-enterprise` repo.
- **Auditability & human-in-the-loop carry over.** Every agent run → an `AiRun`
  (`refle_core.ai_runs.record_agent_run`). Nothing auto-publishes or auto-remediates in core.
- **Tenant scoping.** Every new table uses `TenantMixin`; every query filters by
  `organization_id`. Register new models in `libs/core/refle_core/models/__init__.py`.
- **Durability.** Keep **Celery** for scheduled work; defer Temporal.

## 0.1 Where you're building (current state)

| Area | Path | Notes |
| --- | --- | --- |
| Frameworks/controls | `libs/core/.../models/compliance.py` | `Framework`, `Control`, `OrgControl` (has `status`, `owner_id`); crosswalk-ready |
| Catalog seed | `content/` + `refle_api/seed.py` (`make seed`) | 10 SOC 2 controls today |
| Posture | `routers/controls.py` `GET /controls/posture` | counts by status |
| Evidence | `models/evidence.py`, `routers/evidence.py` | `Evidence` + `EvidenceControl` (→ `org_controls`) |
| Policies | `models/policy.py`, `routers/policies.py` | versioning, draft/published, acceptance |
| Connectors | `libs/integrations/` (`engine.py`, `connectors/`) | demo (full) + aws/github/okta (best-effort collect, pure test fns) |
| Sync engine | `engine.py::run_connection` / `_apply_to_controls` | results → posture → remediation → notification |
| Worker | `services/worker/refle_worker/celery_app.py` | `sync_all_connections` beat (hourly) |
| Notifications | `models/notification.py`, `routers/notifications.py`, `notify.py` | from Phase 4 |
| Agents/audit | `libs/ai_core/.../agents/`, `refle_core/ai_runs.py` | `record_agent_run`, `agent_registry` seam |
| RBAC | `models/user.py` (`Role`: owner/admin/member/**auditor**), `refle_api/deps.py` | `require_role`, `OwnerOrAdmin`, `Members` |

> Note: `Role.auditor` already exists but isn't wired to a read-only scope yet — 5A WI-A4 does that.

---

## Workstream 5A — Audit-readiness & reporting

### WI-A1 — Readiness/coverage service
- **Goal:** one place that computes, per in-scope control, everything an auditor cares about.
- **Files:** new `services/api/refle_api/readiness.py`.
- **Interface:** `async def control_coverage(session, org_id) -> list[ControlCoverage]` where each
  row aggregates: control `code`/`title`/`category`, `OrgControl.status`, `owner_id`,
  `evidence_count` (via `EvidenceControl`), `last_test_result` (latest `ControlTestResult` for the
  code) + `last_tested_at`, `open_remediation_count`, and `related_policies` (published policies
  whose mapping touches the control — for MVP, all published policies; refine later).
  Plus `async def framework_progress(session, org_id) -> list[FrameworkProgress]`
  (passing / failing / not_assessed counts + `percent_ready`).
- **Acceptance:** for a fresh org after a demo sync, coverage shows CC6.1 failing with an open
  remediation task and the others passing; progress ≈ 75% ready.
- **Tests:** offline; assert counts and a known gap.

### WI-A2 — Readiness API + gap list
- **Files:** new `routers/reports.py`; schemas in `schemas.py`; include router in `main.py`.
- **API:**
  - `GET /reports/readiness` → `{ framework_progress, controls: [ControlCoverage] }`.
  - `GET /reports/gaps` → derived gaps: controls `failing`/`not_assessed`, controls with
    **0 evidence**, controls with **no owner**, policies **unpublished** or **0 acceptances**.
    Each gap has `severity` + a human `recommendation`.
- **Acceptance:** gaps endpoint lists CC6.1 (failing) and any control with no evidence/owner.
- **Tests:** seed a gap (control with no evidence) → it appears; resolve → it disappears.

### WI-A3 — Audit-package export
- **Goal:** a single download that hands an auditor the whole story. **No heavy deps.**
- **Files:** `routers/reports.py` (`GET /reports/audit-package`); a builder in `readiness.py`.
- **Behavior:** build a **ZIP** (stdlib `zipfile`, in-memory `BytesIO`) containing:
  `manifest.json` (org, framework, generated_at, edition), `controls.json` + `controls.md`
  (status/owner/evidence/test/policies per control), `policies.md` (published bodies +
  acceptance counts), `evidence_index.csv` (name, control codes, sha256, **presigned URL** via
  `storage.py`), and `readiness_summary.md` (framework progress + gaps). Stream with
  `StreamingResponse`, `Content-Disposition: attachment`.
- **Optional AI (additive):** an `ssp-narrative` agent (`libs/ai_core/.../agents/ssp_narrative.py`,
  registered like the others) writes a plain-language System Security Plan section from the
  readiness summary. **Templated fallback when no LLM** (so Hosted Core works). Recorded via
  `record_agent_run`.
- **Acceptance:** endpoint returns a valid ZIP; manifest + controls + evidence index present;
  works with AI off.
- **Tests:** offline; open the returned ZIP, assert the expected members exist and `controls.json`
  is valid JSON; assert the narrative falls back to templated text with AI off.

### WI-A4 — Read-only auditor scope
- **Goal:** an `auditor` member can view everything (controls, evidence, policies, reports,
  people) but mutate nothing.
- **Files:** `refle_api/deps.py` (a `ReadOnlyForAuditor` / ensure all mutating routes use
  `OwnerOrAdmin` or `Members` that exclude `auditor`); audit the routers.
- **Acceptance:** an `auditor` token gets 200 on GET reports/evidence/controls and 403 on any
  POST/PUT/PATCH/DELETE.
- **Tests:** create an auditor membership; assert read OK + write 403 across a sample of routes.

### WI-A5 — Web: Readiness dashboard + export
- **Files:** new `apps/web/components/readiness-panel.tsx` (a dashboard tab): framework progress
  bar/%, a gap list (severity + recommendation), a per-control coverage table (status • owner •
  evidence count • last tested • policies), and an **“Export audit package”** button hitting
  `/reports/audit-package`. `apps/web/lib/api.ts` methods; `make openapi`.
- **Acceptance:** the tab renders progress + gaps; export downloads a ZIP.

---

## Workstream 5B — Connector depth & continuous monitoring

### WI-B1 — Real AWS/GitHub/Okta coverage
- **Goal:** move aws/github/okta from best-effort to genuinely useful, mapped to more controls.
- **Files:** `libs/integrations/refle_integrations/connectors/{aws,github,okta}.py` — flesh out
  `collect()` (real API calls, defensive) and add **pure** `ControlTest` functions (unit-testable
  like the existing `iam_mfa`/`s3_public`). Examples: AWS — CloudTrail enabled, password policy,
  root MFA, EBS encryption; GitHub — branch protection, 2FA org requirement, secret scanning; Okta
  — MFA policy, password policy, deprovisioning lag. Map each test to control codes.
- **Acceptance:** each connector exposes ≥3 pure tests with passing/failing unit cases.
- **Tests:** pure-function tests per check (no network), mirroring `test_integrations.py`.

### WI-B2 — Expand the SOC 2 catalog
- **Goal:** grow from 10 controls toward fuller Common Criteria coverage (CC1–CC9) so readiness
  and tests have somewhere to land.
- **Files:** `content/` seed data + `refle_api/seed.py`; ensure `make seed` is idempotent and that
  new orgs bootstrap the expanded `OrgControl` set. Keep crosswalk-ready (`framework_id`+`code`).
- **Acceptance:** `make seed` loads the expanded catalog; new control tests map to real codes.
- **Tests:** seed count assertion; a connector test maps to a newly added code.

### WI-B3 — Posture trend history
- **Goal:** show posture over time, not just a snapshot.
- **Files:** new `models/posture_snapshot.py` (`PostureSnapshot`: tenant-scoped; `passing`,
  `failing`, `not_assessed`, `percent_ready`, `taken_at`); register in `models/__init__.py`;
  migration. Write a snapshot at the end of `engine.run_connection` (and/or a daily beat task).
  API `GET /controls/posture/history?days=30`.
- **Acceptance:** two syncs produce ≥2 snapshots; history endpoint returns them ordered.
- **Tests:** run `_apply_to_controls`/sync twice → history has entries with sane counts.

### WI-B4 — Per-connection monitoring schedule
- **Goal:** continuous monitoring that's configurable per connection.
- **Files:** `models/integration.py` (`Connection.monitoring_enabled: bool`,
  `sync_interval_minutes: int | None`); migration; `routers/integrations.py` (PATCH to toggle);
  worker `celery_app.py` — keep the global hourly beat but have `sync_all_connections` **skip
  disabled connections** and respect `sync_interval_minutes` (compare `last_synced_at`).
- **Acceptance:** a disabled connection is skipped by the scheduled task; an interval is honored.
- **Tests:** unit-test the “is this connection due?” predicate; integration test that a disabled
  connection isn't synced.

### WI-B5 — Web: monitoring controls + trend chart
- **Files:** `apps/web/components/integrations` (toggle monitoring, set interval) and a small
  posture **trend sparkline/line chart** on the dashboard (lightweight SVG; no chart lib needed).
- **Acceptance:** toggling monitoring persists; trend renders from `/controls/posture/history`.

---

## Workstream 5C — People & access reviews

> New SOC 2 domain (CC1 “control environment / personnel”, CC6 access management). These records
> become **evidence** for the corresponding controls and feed readiness (5A) + notifications (P4).

### WI-C1 — People (employees)
- **Goal:** track personnel who may or may not be platform users.
- **Files:** new `models/people.py` (`Person`: tenant-scoped; `full_name`, `email`, `title`,
  `status` enum `active|terminated`, `start_date`, `end_date`, `manager_id` self-FK,
  `user_id` FK→users nullable to link a platform account); register + migration; new
  `routers/people.py` (CRUD, owner/admin write, auditor/member read).
- **Acceptance:** create/list/update a person; terminate sets `status` + `end_date`.
- **Tests:** CRUD + termination; auditor read-only.

### WI-C2 — On/offboarding checklists
- **Goal:** standardized joiner/leaver steps that produce evidence for access controls.
- **Files:** `models/people.py` (`OnboardingTemplateItem` per org; `PersonChecklistItem`:
  `person_id`, `kind` enum `onboarding|offboarding`, `label`, `done_at`, `done_by_id`); migration;
  `routers/people.py` endpoints to instantiate a checklist for a person and check items off.
- **Behavior:** terminating a person auto-creates the offboarding checklist (e.g. revoke access,
  disable MFA, collect devices). Overdue/incomplete offboarding → a `Notification` (reuse P4).
- **Acceptance:** terminating a person creates offboarding items; completing all clears the alert.
- **Tests:** termination → checklist created; overdue → one warning notification.

### WI-C3 — Access reviews
- **Goal:** periodic attestation of who has access to what.
- **Files:** new `models/access_review.py` (`AccessReview`: campaign — `name`, `period`,
  `status` enum `open|completed`, `due_at`; `AccessReviewItem`: `review_id`, `person_id`,
  `system` (free-text or connection ref), `access_detail`, `decision` enum
  `pending|keep|revoke`, `reviewed_by_id`, `reviewed_at`); migration; new
  `routers/access_reviews.py` (create campaign, list items, record decisions, complete).
- **Behavior:** seed items from connection resources where available (e.g. Okta users); a
  `revoke` decision opens a `RemediationTask`. Completing a campaign is evidence for CC6.x.
- **Acceptance:** create a campaign with items → record decisions → complete; `revoke` creates a
  remediation task.
- **Tests:** decision flow; revoke → remediation task; auditor read-only.

### WI-C4 — Security-training tracking
- **Files:** `models/people.py` (`TrainingRecord`: `person_id`, `course`, `completed_at`,
  `expires_at`); migration; endpoints in `routers/people.py`. Expiring/missing training →
  notification + a readiness gap (feeds 5A) for CC1.
- **Acceptance:** record training; an expired record surfaces as a gap.
- **Tests:** expiry detection; gap surfaces in `/reports/gaps`.

### WI-C5 — Web: People hub
- **Files:** new `apps/web/components/people-panel.tsx` (or sub-tabs): people list + on/offboarding
  checklists, an access-review screen (campaign → items → decisions), training status. `api.ts` +
  `make openapi`.
- **Acceptance:** run an access-review campaign end-to-end and complete an offboarding from the UI.

---

## Sequencing (recommended)

1. **5B-WI-B2** (expand catalog) + **5B-WI-B1** (real tests) — gives readiness real coverage.
2. **5A** (readiness service → API → export → auditor scope → web) — the headline payoff.
3. **5B-WI-B3/B4/B5** (trend history + monitoring schedules + charts).
4. **5C** (people / access reviews / training) — largest new domain; its records then flow back
   into 5A readiness and P4 notifications.

Each workstream is independently shippable; do them as separate branches/PRs.

---

## Definition of done (quality gates — run before calling Phase 5 done)

```bash
make lint                              # ruff + next lint, clean
make test                              # pytest, offline (no real API/AI calls)
make openapi                           # regenerate the TS SDK after API changes
npm run build --workspace apps/web     # web typechecks/builds
make up && make migrate                # migrations apply cleanly
```

Migration gotchas seen in earlier phases (watch for them):
- Reusing an existing PG enum across tables → set `create_type=False` on the column.
- `pgvector` columns → add `import pgvector.sqlalchemy.vector` to the autogenerated migration.
- New enums (`person_status`, `checklist_kind`, `access_decision`, …) — name them explicitly and
  backfill defaults for added non-null columns.

## Open items to confirm

- **Audit-package format:** ZIP-of-Markdown/JSON/CSV for MVP (chosen for zero new deps). PDF
  rendering is a fast-follow if auditors want it — likely an enterprise/hosted enhancement.
- **Access-review item seeding:** how much to auto-pull from connectors (Okta/GitHub) vs manual in
  the first cut.
- **Editions surfacing:** add `REFLE_EDITION` (core|enterprise) to settings + expose on `/meta`,
  and mark Hosted-Enterprise-only surfaces “Coming Soon” in the web — confirm copy/placement.
