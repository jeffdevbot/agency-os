# AgencyClaw Parallel Runbook (Non-Conflicting Work)

## Purpose
This doc captures two parallel tracks that can move after C11E/C11F-A landed:
1) client/brand/ClickUp onboarding model (including shared destination patterns), and
2) remaining legacy deterministic branch cleanup plan.

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

## 3) Remaining Legacy Branches To Retire (Post-C11E)

These are still in `backend-core/app/api/routes/slack.py` and should be removed in a controlled pass after C11E lands.

### A) Regex/classifier deterministic fallback path
- `_classify_message(...)` and intent switch inside `_handle_dm_event(...)` (around deterministic create/list/switch/default branches).
- Current behavior is feature-flagged by:
  - `_is_llm_orchestrator_enabled()`
  - `_is_legacy_intent_fallback_enabled()`

### B) Command-style help fallback
- `_help_text()` and "Try: ..." style guidance should be replaced with natural conversational fallback text.

### C) Partial deterministic "control intents"
- `switch_client`, `set_default_client`, `clear_defaults` currently bypass skill invocation.
- Long-term: expose as explicit skills so orchestrator decides when to invoke them.

### Cleanup sequence (safe order)
1. Keep policy gate + deterministic skill execution functions (safety rails).
2. Remove broad regex routing fallback for non-control requests.
3. Migrate control intents to skills.
4. Remove command-style help text.
5. Keep fail-closed behavior and all policy checks unchanged.

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
After C11E merges, take a focused cleanup chunk:
- "C11F: LLM-first runtime cleanup"
- Scope: remove broad deterministic classifier fallback, keep deterministic skill execution/policy rails.
- Deliverables: code cleanup + regression tests + updated tracker evidence.
