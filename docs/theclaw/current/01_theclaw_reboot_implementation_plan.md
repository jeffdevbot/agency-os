# 01 - The Claw Reboot Implementation Plan

Status: proposed
Owner: Jeff + Codex
Last updated: 2026-02-26

## 1) Goal

Reboot AgencyClaw into **The Claw** with a strict baby-step rollout:
- make Slack assistant reliable first,
- add capabilities one skill at a time,
- remove legacy AgencyClaw code only after each replacement is proven.

## 2) Scope

In scope:
- New Slack runtime path for The Claw.
- Minimal phase-1 behavior (plain assistant chat via OpenAI).
- Skill-by-skill rollout with test gates.
- Controlled removal of legacy AgencyClaw files/tests.
- Removal of identity sync for now.
- Regression protection for existing non-Slack routes.

Out of scope (for reboot start):
- SOP-grounded execution,
- deep client memory/context,
- complex multi-step autonomous planning,
- broad admin automation.

## 3) Principles

1. Ship smallest possible working slice.
2. One new skill at a time.
3. No silent behavior changes.
4. Keep rollback path until replacement is proven.
5. Delete only after replacement tests are green.

## 3A) Guiding Philosophy

The Claw is being built as a **Jarvis-like operator assistant** for the agency:
- long-term, it should understand clients, agency operations, and Amazon selling deeply;
- short-term, it earns that capability one proven slice at a time.

Execution philosophy:
1. **LLM-first orchestration**: use strong models for understanding, planning, and response generation.
2. **Skill-calling architecture**: let the model call skills and specialist subagents when action is needed.
3. **No regex determinism as core intelligence**: avoid brittle intent-routing trees as the main control plane.
4. **Determinism only for safety rails**: keep hard checks for auth, policy, confirmations, idempotency, and auditability.
5. **Progressive depth**: ship basic usefulness first, then add memory/context and multi-step execution after each layer proves reliable.

## 4) Architecture Direction

- Keep `backend-core/app/main.py` as app bootstrap and router mount point.
- Keep Slack route surface (`/api/slack/...`) stable.
- Replace internals behind Slack route with new The Claw runtime modules.
- Remove legacy AgencyClaw runtime paths as replacements land.

## 4A) Code Organization Guardrails

To avoid repeating the previous monolith pattern:

1. `backend-core/app/api/routes/slack.py` is an adapter only.
2. `slack.py` must only do request wiring, auth/signature validation handoff, and runtime dispatch.
3. No business logic, prompt logic, policy logic, skill logic, or session mutation logic lives in `slack.py`.
4. `slack.py` line budget target is <= 150 lines.
5. `slack.py` warning threshold is > 200 lines.
6. `slack.py` hard stop is > 250 lines; extraction is required before merge.

Required The Claw service topology (non-flat):
- `backend-core/app/services/theclaw/runtime/` for Slack/event runtime orchestration
- `backend-core/app/services/theclaw/memory/` for session memory and context state
- `backend-core/app/services/theclaw/skills/` one folder per skill
- `backend-core/app/services/theclaw/policy/` for allow/deny rails
- `backend-core/app/services/theclaw/prompts/` for prompt contracts/templates
- `backend-core/app/services/theclaw/integrations/` for external API adapters

Skill module rule:
- One skill = one folder with explicit entrypoint, prompt contract, output contract, tests.

PR guardrail:
- Any PR that adds behavior to Slack must include new/updated module placement under the topology above.
- If extraction is not yet possible, PR must include explicit rationale.

## 4B) Data Persistence Contract

Current memory persistence:
- Store location: Supabase `public.playbook_slack_sessions`
- Field: `context` JSONB
- The Claw key: `theclaw_history_v1`
- History cap: 25 turns (25 user + 25 assistant messages max)

Session behavior:
- Session is considered active for ~30 minutes based on `last_message_at`.
- `new session` command clears active session context and starts fresh memory.

Schema reference:
- Canonical DB reference: `docs/db/schema_master.md`
- Relevant table section: `public.playbook_slack_sessions`

## 4C) Skill Registry + Organization

Skill model (OpenClaw-style, markdown-first):
- Each skill lives under `backend-core/app/services/theclaw/skills/<category>/<skill_id>/SKILL.md`.
- `SKILL.md` is the source of truth for:
  - metadata (`id`, `name`, `category`, optional `categories`, trigger hints),
  - the skill prompt contract,
  - output contract notes.
- Runtime loads skills via a registry module, not hardcoded prompt blocks in `slack_minimal_runtime.py`.

Folder taxonomy (human organization, not deterministic pre-filtering):
1. `core`
2. `ppc`
3. `catalog`
4. `p&l`
5. `replenishment`
6. `wbr`

Routing strategy (multi-level to prevent skill explosion):
1. Build a compact `<available_skills>` XML menu (id, name, description, when_to_use, trigger_hints, location) and inject it into a skill-router prompt.
2. Let the model choose `skill_id` (or `none`) for the turn in strict JSON.
3. Runtime loads only the selected `SKILL.md` contract and augments the response prompt with that skill.
4. Invoke one skill by default unless explicit multi-skill orchestration is required.
5. Deterministic checks remain only for safety rails (auth, policy, confirmations, idempotency, auditability).

Guardrail:
- Do not append large per-skill prompt logic directly in runtime code; add/modify `SKILL.md` contracts and registry metadata instead.
- Skill registry cache should auto-refresh with TTL (`THECLAW_SKILL_CACHE_TTL_SECONDS`) so skill edits do not require restart.

## 5) Phase Plan (Baby Steps)

## Phase 0 - Baseline and Freeze

Deliverables:
- Capture passing backend baseline and route smoke checks.
- Freeze legacy behavior for reference.

Gate:
- `pytest -q backend-core` passes at baseline.
- Non-Slack product-route smoke checks (ngram/npat/root/adscope/clickup endpoints) unchanged.

## Phase 1 - Minimal Slack Assistant (No Skills)

Deliverables:
- Gut `backend-core/app/api/routes/slack.py` internals to minimal runtime path.
- Keep event verification and DM handling only.
- Single OpenAI call with a high-level Amazon agency assistant system prompt.
- No mutations, no SOP lookup, no planner, no pending state machine.
- No legacy fallback path in runtime.

Gate:
- Slack DM round-trip works manually.
- Assistant handles basic Q&A without crashes.
- Existing non-Slack route tests still pass.

## Phase 2 - Meeting Notes -> Task Suggestions (Draft Only)

Deliverables:
- Add first real skill: `Task Extraction` (parse meeting notes and output structured draft tasks).
- Strictly draft mode only (no ClickUp writes).
- Response format contract:
  - `The Claw: Task Extraction`
  - `Internal ClickUp Tasks (Agency)` with `Task N` + `Context`
  - `Client-Side Requirements (Recap)` with `Action Item`

Gate:
- Unit tests for parser/formatter + manual Slack transcript check.
- False positives reduced (no unrelated SOP references).

## Phase 3 - Task Creation Skill (One-by-One Confirmed Writes)

Deliverables:
- Add ClickUp create skill with explicit confirmation per task.
- Enforce one-by-one task creation, not bulk firehose.
- Idempotency and duplicate guard for retries.

Gate:
- Integration tests for successful create, duplicate prevention, and reject paths.
- Manual test in Test space with controlled fixtures.

## Phase 4 - Follow-up Email Draft Skill

Deliverables:
- Add email drafting skill from meeting notes + created tasks context.
- Draft-only output (no send).

Gate:
- Formatting and content quality checks pass against fixture cases.

## Phase 5 - Legacy Deletion

Deliverables:
- Remove unused AgencyClaw modules and tests.
- Remove identity sync endpoints/runtime.
- Remove legacy env flags not used by The Claw.

Deletion rules:
- Delete only when replacement tests exist and are passing.
- Delete in chunks with grep proof of no live imports.
- Keep rollback tag before each delete chunk.

Gate:
- Full backend suite green.
- `rg "services\.agencyclaw|AGENCYCLAW_" backend-core/app backend-core/tests` only shows intentional survivors (or none).

## Phase 6 - Hardening and Docs

Deliverables:
- Consolidated architecture doc for new contributors.
- Runbook for local and Render testing.
- Matrix tests for The Claw gauntlets.

Gate:
- New coder can run and validate flows from docs in under 30 minutes.

## 6) Skill Rollout Contract

Every skill must include:
- explicit trigger contract,
- explicit output schema,
- policy for allowed/disallowed actions,
- unit tests,
- one manual transcript test,
- rollback strategy.

No new skill ships without all six.

## 7) Test Strategy

Required on each chunk:
1. Targeted tests for touched modules.
2. Slack route runtime tests.
3. Full backend run before merge.
4. Manual Slack validation when behavior changes.

Minimum manual checks after each Slack change:
- DM greeting and plain question,
- meeting-notes to draft task suggestions,
- reject unsafe or ambiguous mutation attempts,
- confirm non-Slack routes still respond.

## 8) Cutover + Rollback

Cutover:
- Keep route path stable and cut internals directly to The Claw runtime.
- Do not maintain dual-path runtime flags.

Rollback:
- Preserve pre-cutover tag/branch.
- Roll back by git commit/tag, not runtime fallback toggles.

## 9) Immediate Execution Backlog

1. Create The Claw architecture doc skeleton.
2. Implement Phase 1 minimal Slack handler behind guarded switch.
3. Add tests for Phase 1 DM round-trip and error handling.
4. Run full backend suite and manual Slack smoke.
5. Then start Phase 2 (meeting notes -> draft tasks).

## 10) Definition of Done for Reboot

The reboot is done when:
- Slack assistant is stable for real daily use,
- meeting-notes -> draft tasks -> confirmed task creation works reliably,
- follow-up draft email works reliably,
- legacy AgencyClaw and identity sync are removed,
- docs and tests are simple enough for fast onboarding.

## 11) Skill Catalog (Organized Backlog)

This section catalogs proposed skills so we can add them one-by-one without losing architecture clarity.

### 11A) Identity Model: Client, Brand, ClickUp Space

Canonical fields every execution-oriented skill should receive or resolve:
1. `client_name` (human-facing)
2. `brand_name` (human-facing)
3. `clickup_space_name` (human-facing)
4. `clickup_space_id` (system id, resolved before mutations)
5. `brand_key` (stable internal slug/id to avoid name collisions)
6. `market_scope` (optional, e.g. `CA`, `US`, `UK`, `MX`)

Real-world mapping patterns to support:
1. Client and Brand not the same:
- `Client = Lifestyle`
- `Brand = Home Gifts USA`
- `ClickUp Space = Home Gifts USA`

2. Client and Brand not the same, brand exists elsewhere:
- `Client = Basari World`
- `Brand = Whoosh`
- `ClickUp Space = Basari World [Whoosh]`
- Note: Basari is Whoosh's distributor in Mexico; this scope matters for routing.

3. Client and Brand the same, but brand exists elsewhere:
- `Client = Whoosh`
- `Brand = Whoosh`
- `ClickUp Space = Whoosh`
- Note: this client context can span multiple markets (CA, US, UK), so market disambiguation may still be needed.

4. Client with multiple brands:
- `Client = Distex`
- `Brands = Thorinox, New Air, Brika, Distex`
- `ClickUp Space = Distex`

Rule:
- Skills must resolve to `clickup_space_id` before create/update calls.
- If multiple matches exist, ask one clarification question instead of guessing.

### 11B) Command Center Status (Keep or Deprecate)

Current recommendation: keep Command Center as source of truth for now; do not deprecate in this phase.

What Command Center already handles:
1. `agency_clients` with nested `brands` in bootstrap payload.
2. Per-brand ClickUp destination fields (`clickup_space_id`, `clickup_list_id`).
3. ClickUp Space Registry with admin mapping/classification.
4. Duplicate brand names across different clients are structurally possible because brand names are not globally unique.

Current gaps to address via skills/runtime:
1. Natural-language disambiguation ("which Whoosh?") is not handled end-to-end yet.
2. Resolver behavior for multi-brand clients sharing one space needs explicit contract.
3. Market-level context (CA/US/UK/MX) is not first-class in resolver flow yet.
4. Existing helper destination picker can choose "first mapped brand"; this is not safe for ambiguous cases.

### 11C) Foundation Skills (Cross-Category)

1. `entity_context_resolver`:
- Resolve client/brand/space mapping.
- Output canonical identity packet for downstream skills.
- Understand mentions of client name, brand name, or ClickUp space name.

2. `entity_disambiguation_clarifier`:
- Ask focused clarification when multiple matches exist (example: "Which Whoosh: Basari World [Whoosh] or Whoosh?").
- Capture selected entity for session context.

3. `clickup_destination_resolver`:
- Resolve final `clickup_space_id` and optional `clickup_list_id`.
- Respect one-space/multi-brand and multi-space/one-brand edge cases.

4. `task_creation_guard`:
- Validate required fields before task creation.
- Enforce one-by-one confirmed writes.

5. `session_context_manager`:
- Maintain active client/brand context for current session.
- Support explicit reset (`new session`).

### 11D) Client Memory Skills

1. `client_memory_capture`:
- Detect important durable facts in conversation (goals, constraints, ownership rules, market scope).
- Propose a memory entry before writing.

2. `client_memory_write`:
- Explicit write path when the user's intent is to persist memory.
- Skill selection remains LLM-led from the available skills menu (no regex command router for memory).
- Requires clear scope (`client`, optional `brand`, optional `market_scope`) and concise memory text.

3. `client_memory_retrieve`:
- Pull top relevant stored memory for current entity context.
- Return compact memory blocks to keep token usage bounded.

4. `client_memory_admin`:
- List/edit/archive memory records for cleanup.
- Keep memory quality high and prevent stale clutter.

Suggested storage model:
- Keep memory as database records keyed by `client_id` (+ optional `brand_id`, optional `market_scope`), not as local markdown files.
- Keep skill contracts in markdown; keep mutable memory in database.
- Keep intent routing model-led; deterministic logic is limited to policy/auth/idempotency rails.

### 11E) Task Creation Skills (Near-Term Focus)

1. `task_extraction` (implemented):
- Meeting notes -> internal task drafts + client action recap.

2. `task_draft_refiner`:
- Tighten task titles, owners, due dates, and acceptance criteria.

3. `task_confirmation_to_create`:
- Convert approved draft task into mutation-ready payload for ClickUp create.

4. `clickup_task_create_one_by_one`:
- Create one ClickUp task at a time only after explicit confirmation.
- Use resolved client/brand/space context from resolver skills.

### 11F) Sub-Agent Use Cases (Near-Term)

Use sub-agents only when decomposition is needed; keep simple requests in orchestrator + skill flow.

1. `identity_resolution_subagent`:
- For complex ambiguous mentions across client/brand/space/market.
- Returns one resolved context packet plus clarification question if unresolved.

### 11G) Rollout Order Recommendation (Focused)

1. Lock context resolution:
- `entity_context_resolver` + `entity_disambiguation_clarifier` + `clickup_destination_resolver`
2. Add explicit memory writes:
- `client_memory_capture` + `client_memory_write` + `client_memory_retrieve` + `client_memory_admin`
3. Complete one-by-one task flow:
- `task_extraction` hardening -> `task_draft_refiner` -> `task_confirmation_to_create` -> `clickup_task_create_one_by_one`

## 12) Ice Box (Explicitly Deferred)

These are valid ideas but intentionally parked. They are not part of the current execution focus.

Deferred meeting extension:
1. `followup_email_draft`

Deferred domain skill lanes:
- PPC:
1. `ppc_task_planner`
2. `ppc_weekly_diagnostics`
3. `ppc_budget_shift_recommendation`

- Catalog:
1. `catalog_listing_audit`
2. `catalog_content_brief`
3. `variation_cleanup_plan`

- P&L:
1. `pnl_snapshot_explainer`
2. `margin_risk_detector`
3. `contribution_lever_planner`

- Replenishment:
1. `restock_risk_assessor`
2. `po_recommendation_draft`
3. `stockout_impact_brief`

- WBR:
1. `wbr_kpi_summary`
2. `wbr_anomaly_detector`
3. `wbr_action_plan_draft`

Deferred sub-agent expansion:
1. `meeting_execution_subagent`
