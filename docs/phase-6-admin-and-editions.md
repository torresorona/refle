# Phase 6 — Admin surfaces & the Core ↔ Enterprise boundary

This doc does two things: records the **Tier 1 open-core admin wrap-up** (delivered) and lays out
the **enterprise admin roadmap** (Tiers 2–3) so the Core ↔ Enterprise split stays clean as work
moves into the private `refle-enterprise` repo.

## Guiding principle — three admin tiers, not one

A business may run refle for itself **or as a service for many orgs** (GitLab-style). That implies
three *distinct* admin surfaces, each mapped to an edition:

| Tier | Admin | Scope | Edition |
| --- | --- | --- | --- |
| 1 | **Org admin** (owner/admin) | one org: controls, people, policies, integrations | **Core** |
| 2 | **Account/Group admin** | a business's many child orgs: create/suspend, cross-org roles, roll-up reporting | **Enterprise** (Hosted Enterprise / On-Prem Enterprise) |
| 3 | **Instance/operator admin** | the whole deployment: all orgs, *global* framework catalog, instance settings | **On-Prem Enterprise** + the Hosted operator console |

**Frameworks "outside the code":** per-org customization (scoping controls in/out; org-owned custom
controls) is **Core**; editing the **shared global** catalog or authoring new frameworks for
everyone is **operator/enterprise** — one tenant must never mutate the catalog all tenants share.

**Audit-log-first:** any runtime admin change must be recorded in a generic human-action audit log
(`AiRun` only covered agent actions). This was built first, as a dependency for everything here.

---

## Tier 1 — Open-core admin wrap-up  ✅ DELIVERED (2026-06-21)

Shipped on branch `phase-5-readiness-monitoring-people` (committed alongside the Phase 5 close-out;
verified live in the browser). Closes the open-core admin gap so focus can shift to Enterprise.

### WI-1 — Generic audit log
- `libs/core/refle_core/models/audit.py` (`AuditLog`: tenant-scoped; `actor_id`, `action`,
  `target_type`, `target_id`, `summary`); `refle_core/audit.py::record_audit` helper (adds to the
  caller's transaction); `routers/audit.py` `GET /audit-log` (owner/admin). Wired into
  control status/scope changes, policy publish, and person termination.
- **Done:** mutations land an `AuditLog` row; owner/admin can read it; members get 403.

### WI-2 — Per-org control scoping
- `OrgControl.in_scope` (default true). `PATCH /controls/{id}` accepts `in_scope`; out-of-scope
  controls are excluded from posture (`refle_core.posture.posture_counts`) and from readiness gaps,
  and the change is audited (`control.scope`).
- **Done:** scoping a control out drops the posture denominator and removes its gaps.

### WI-3 — Org switcher
- `POST /auth/switch-org` (verify membership → re-issue the org-scoped session cookie). Web header
  shows a switcher when the user has >1 membership (multi-org membership already existed in data).
- **Done:** a multi-org user switches context; switching to a non-member org is 403.

### Migration & tests
- Migration `b4538924eeda` (audit_logs + `org_controls.in_scope`, backfilled true).
- `tests/test_phase6_admin.py`: scoping excludes from posture/gaps; scope+status audited;
  switch-org happy path + 403; audit-log requires owner/admin.

### Deferred to a follow-on **core** slice (not yet built)
- **Custom control / framework *authoring*** (org-owned `Control` via the nullable-`organization_id`
  pattern). Held back because it touches the audit-sensitive catalog uniqueness/tenancy
  (`controls (framework_id, code)` → needs per-org scoping) and deserves its own careful slice with
  full tests, rather than being rushed into the Tier 1 wrap-up. Control **scoping** (WI-2) already
  delivers the high-value "change the framework's applicability without editing YAML."

---

## Tier 2 — Account/Group admin (ENTERPRISE, private repo)

Goal: a business managing many orgs, like GitLab Groups. **Lives in `refle-enterprise`, gated by
`has_feature`; core only exposes the seam.**

- **Model:** an `Account`/`Group` entity that owns child `organizations` (`parent`/hierarchy);
  cross-org roles; roll-up readiness across child orgs.
- **Admin dashboard:** create/suspend child orgs, manage cross-org membership, account-wide reports.
- **Identity:** rides **WorkOS Organizations + Admin Portal** (per-org SSO/SAML self-setup + SCIM
  directory sync), which memory already slates for the enterprise repo — same seam, not a separate
  build.
- **Editions:** **Hosted Enterprise** (Coming Soon — gated on Refle's own SOC 2 + FedRAMP) and
  **On-Prem Enterprise** (white-glove). Hosted Core explicitly excludes this.

## Tier 3 — Instance/operator admin (ON-PREM ENTERPRISE + Hosted operator)

Goal: whoever runs the deployment. GitLab `/admin`.

- Manage **all** orgs/users on the instance; edit the **global framework catalog** and author new
  frameworks (with audit trail); instance-wide settings, license, and feature flags.
- A guarded `/admin` behind an instance-admin flag for self-managed; the Hosted operator console for
  SaaS (run by Refle staff, not customers).

---

## Cross-cutting (carries forward)
- Open-core features must keep working with **no Refle-managed AI** (BYO key / local). AI is additive
  with templated fallbacks.
- Core never imports enterprise; enterprise registers via `libs/extensions` (license + registries).
- Every runtime admin action is audited (`AuditLog`); agent actions stay in `AiRun`.

## Definition of done (quality gates)
```bash
make lint && make test && make openapi
npm run build --workspace apps/web
make up && make migrate
```
