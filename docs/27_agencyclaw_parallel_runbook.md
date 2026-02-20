# AgencyClaw Parallel Runbook (Non-Conflicting Work)

## Purpose
This doc captures two parallel tracks:
1) client/brand/ClickUp onboarding model (including shared destination patterns), and
2) runtime cleanup/decomposition status and remaining optional hardening.

---

## 1) Onboarding Model (What To Configure)

### Canonical entities
- `agency_clients`: business account (for example `Distex`).
- `brands`: work units under a client (can be multiple per client; same brand name can exist under different clients).
- `clickup_space_registry`: discovered ClickUp spaces with classification (`brand_scoped`, `shared_service`, `unknown`).

### Key runtime rule
Task routing uses `brands.clickup_space_id` + `brands.clickup_list_id` as source of truth.
This supports many brands mapping to the same destination (many-to-one), which is required for clients that operate multiple brands in one ClickUp space.

### Classification guidance
- `brand_scoped`: space dedicated to one client operating area where normal brand task routing can land.
- `shared_service`: cross-client/shared operations space (for example reporting specials).
- `unknown`: not trusted for routing until reviewed.

### Distex-style setup (one client space, multiple brands)
If one client space contains work for multiple brands:
1. Classify the space as `brand_scoped` if it is a normal execution destination for that client.
2. Keep/create all brand rows under the same client.
3. Set each brand's `clickup_space_id`/`clickup_list_id` to the same destination.
4. Let runtime disambiguate brand context when request is product-scoped.

This avoids misclassifying true client execution spaces as `shared_service`.

---

## 2) Current Gap: Why "List Brands" and "List Clients" Feel Uneven

`cc_client_lookup` is intentionally assignment-scoped for non-admin members, while `cc_brand_list_all` can be broader depending on query path and role.
So "I only see 2 clients" can be expected when your profile is assigned to 2.

Action:
- Keep this behavior for now (policy-safe).
- Add explicit wording in responses when results are assignment-scoped.

---

## 3) Runtime Cleanup Status (As Of C16C)

Completed:
1. Strict LLM-first gating is in place (`C13A`), with non-control deterministic fallback blocked in strict mode.
2. Command-style fallback cleanup landed (`C11F-A`).
3. Slack route decomposition landed through C14A/C14B/C14C/C14D/C14E/C14F/C14G.
4. Typed runtime dependency contracts landed (`C14I`) to reduce signature-drift risk.
5. Runtime-focused unit suites landed (`C14X`) and full backend suite is currently green.
6. Orchestrator-first planner delegation + resilience landed (`C15A`-`C15C`).
7. Canonical task-list routing landed with weekly alias compatibility (`C16A`-`C16C`).

Still optional (not release blockers):
1. Convert deterministic control intents (`switch_client`, `set_default_client`, `clear_defaults`) into first-class skills.
2. Consolidate or trim compatibility wrappers once patch points are no longer needed.
3. Extend policy coverage beyond DM/default surfaces as channel use expands.

---

## 4) Slack Smoke Prompts (Manual)

### Brand-context / routing
- `create task for Distex: Set up 20% coupon for Thorinox`
- `create with ASIN pending`
- Expect: unresolved block + explicit pending note, no silent brand guess.

### Shared destination disambiguation
- `create task for Distex`
- (provide product-scoped title)
- Expect: brand picker when ambiguous.

### Lookup/audit
- `list brands`
- `brands missing clickup mapping?`
- Expect: clear missing field output per brand.

---

## 5) Next Non-Conflicting Follow-up
- Keep this runbook focused on onboarding model and optional runtime hardening only.
- Source of truth for chunk-level delivery and commits: `docs/25_agencyclaw_execution_tracker.md`.
- Recommended next product-focused work should be planned as new chunks (not added to this historical cleanup runbook).
