# AgencyClaw Implementation Plan (Chunked)

## 1. Purpose
This document is the execution blueprint for AgencyClaw implementation.
It is separate from `docs/23_agencyclaw_prd.md`:
- PRD = product decisions and behavior.
- Implementation plan = execution order, prompts, and acceptance gates.

Status note (2026-02-20):
- Post-C12 runtime hardening/decomposition has completed through C16C.
- See `docs/25_agencyclaw_execution_tracker.md` for commit-by-commit evidence.

## 2. Working Rules
- Work one chunk at a time.
- No scope expansion inside a chunk.
- Every chunk ships with tests.
- Every mutation path must preserve idempotency, confirmation, and audit requirements from PRD v1.19.
- Unimplemented skills remain disabled in `skill_catalog`.
- Actor + surface context (`who` + `where`) must be available before mutation execution.
- Clarify loops for mutation workflows must persist pending slot state until confirm/cancel.
- Task drafts should be source-grounded where possible (SOP/internal docs/similar tasks).
- Task draft/body formatting should follow `docs/26_agencyclaw_task_brief_standard.md`, including generic fallback templates when classification is uncertain.
- Keep runtime-vs-skill separation strict:
  runtime owns conversation/policy/confirmation/fallback; skills own typed business execution.
- New capabilities should default to new modular skills, not new hardcoded intent branches.
- Brand-aware routing must follow explicit policy:
  resolve destination (`space/list`) separately from brand context (`brand_id`), and never guess ambiguous brands.

## 2.1 Scope Freeze (Near-Term)
- Committed for active delivery:
  - C1 through C12B shipped behavior.
  - C12C Path-1 runtime: fail-closed ASIN/SKU clarification and explicit identifier-pending path.
- Deferred indefinitely (not release blockers):
  - Distributed cross-worker lock (`C4D`) unless production contention demands it.
  - Queue lanes and async orchestration expansion.
  - Cross-user admin approval workflow beyond self-confirmation.
  - Inbound ClickUp webhook sync.
- Optional backlog (not near-term commitments):
  - Vector semantic retrieval.
  - External transcript/document ingestion.
  - Multi-agent decomposition.

## 3. Definition Of Done (Per Chunk)
- Behavior implemented end-to-end for chunk scope.
- Permission checks and policy gates enforced.
- Idempotency and concurrency requirements handled where applicable.
- Tests added for happy path and key failure/ambiguity paths.
- `skill_catalog` row updated to `implemented_in_code=true` and enabled only when ready.
- Tracker updated (`docs/25_agencyclaw_execution_tracker.md`).

## 4. Chunk Roadmap
1. C1: Task list read path (`clickup_task_list_weekly`, later canonicalized to `clickup_task_list`)
2. C2: Task create flow (`clickup_task_create`) with thin-task clarification
3. C3: Confirmation protocol + Slack dedupe hardening
4. C4: Concurrency guard + ClickUp reliability/idempotency
5. C5: Team identity sync + reconciliation (`needs_review` decisions)
6. C6: ClickUp space sync/classification + brand mapping controls
7. C7: Standalone `meeting_parser` + debrief review path hardening
8. C8: `client_context_builder` + token budget enforcement + metadata
9. C9: Slack conversational orchestrator (LLM-first skill calling)
10. C10B: Mutation clarify-state persistence + slot-fill loop hardening
11. C10B.5: Session conversation history buffer (last 5 exchanges)
12. C10A: Actor/surface context resolver + runtime policy gate
13. C10C: KB retrieval cascade + source-grounded draft composer
14. C10D: Reduce hardcoded intent paths into planner + capability skills (includes N-gram carve-out)
15. C10E: Lightweight durable preference memory (operator defaults)
16. C10F: Semantic pending-state resolver hardening
17. C11A: Command Center read-only lookup skills in chat (clients/brands/mapping audit)
18. C11B: LLM-first fallback cleanup (disable broad regex fallback by default)
19. C11D: Brand context resolver for shared-destination + multi-brand clients
20. C11E: Admin remediation skill for unmapped brands (dry-run -> confirm apply)
21. C11F-A: Conversational runtime cleanup (LLM-first, no command menus)
22. C12A: Assignment mutations in chat (`cc_assignment_upsert` / `cc_assignment_remove`)
23. C12B: Brand CRUD mutations in chat (`cc_brand_create` / `cc_brand_update`)
24. C12C: Product identifier guardrail (Path-1, no catalog dependency)
25. C13A: Strict LLM-first deterministic gating
26. C13B: Strict-gating helper extraction (no behavior change)
27. C13C: Tool->skill compatibility alias cleanup
28. C14A: Slack helper extraction
29. C14B: Pending-flow extraction
30. C14C: Command Center dispatch extraction
31. C14D: LLM orchestrator runtime extraction
32. C14E: DM event runtime extraction
33. C14F: Interaction runtime extraction
34. C14G: Task-create runtime extraction
35. C14I: Runtime dependency contract hardening
36. C15A: Orchestrator-first planner delegation
37. C15B: `plan_request` resilience + planner coverage expansion
38. C15C: Planner runtime extraction + control-reroute hardening
39. C16A: Flexible task-list windows + runtime extraction
40. C16B: Task-list canonicalization + `window_days` normalization hardening
41. C16C: Internal weekly-shim cleanup (canonical task-list routing)

## 5. Chunk Details
## C1: Task List Read Path
- Scope:
  - Slack query: "what's being worked on this week for client X"
  - Slack query: "show tasks for client X" (default `this_week`; optional broader windows added later).
  - Resolve client/brand.
  - Read ClickUp tasks with pagination and Slack-friendly formatting.
  - Cap response at 200 tasks with truncation notice.
- Acceptance:
  - Handles ambiguous client/brand with clarification.
  - Handles missing ClickUp mapping fail-closed.
  - Returns useful "no tasks" response.
- Skill target:
  - Initial: `clickup_task_list_weekly`
  - Canonicalized later to: `clickup_task_list` (weekly alias retained for compatibility)

## C2: Task Create Flow
- Scope:
  - `clickup_task_create` to brand backlog default destination.
  - Thin-task clarification workflow.
  - "Create anyway as draft" workflow.
  - Return ClickUp URL after success.
- Acceptance:
  - Confirmation required in channel contexts.
  - Missing mapping fails closed with actionable message.
  - Task URL is always returned on success.

## C3: Confirmation + Dedupe
- Scope:
  - Ephemeral Block Kit self-confirmation.
  - 10-minute expiry handling.
  - `slack_event_receipts` idempotent handling for interactions.
- Acceptance:
  - Duplicate interaction deliveries are no-ops.
  - Expired confirms do not mutate state.

## C4: Concurrency + Reliability
- Scope:
  - Advisory lock pattern for mutation skills.
  - ClickUp retry/backoff for transient failures.
  - ClickUp create idempotency key and orphan handling.
- Acceptance:
  - Concurrent writes to same entity do not race.
  - ClickUp 429/timeout behavior is deterministic and user-visible.
- Status note:
  - C4A-C4C shipped.
  - `C4D` (distributed cross-worker lock via Redis/DB advisory lock) is pinned as a future hardening feature.

## C5: Team Identity Sync
- Scope:
  - Sync Slack users + ClickUp users (read-only source ingestion).
  - Deterministic matching to `profiles`.
  - `needs_review` decision in Slack for ambiguous mappings.
- Acceptance:
  - Auto-match, new-profile, and needs-review outcomes all supported.
  - Admin decision path is audited and idempotent.

## C6: ClickUp Space Sync + Classification
- Scope:
  - Ingest spaces and maintain classification:
    `brand_scoped`, `shared_service`, `unknown`.
  - Admin classification and brand map/unmap via chat skills.
- Acceptance:
  - Brand routing uses only `brand_scoped` by default.
  - `unknown` spaces block routing until classified.

## C7: Meeting Parser Hardening
- Scope:
  - Implement and test standalone `meeting_parser`.
  - Integrate with debrief ingest/review path.
- Acceptance:
  - Parser is testable independently from ClickUp send.
  - Quality and ambiguity handling are explicit.

## C8: Client Context Builder
- Scope:
  - Build 4,000-token context pack with deterministic truncation.
  - Emit metadata (`included_sources`, `omitted_sources`, token estimate, freshness).
- Acceptance:
  - Deterministic output for same inputs.
  - Budget guardrails enforced and tested.

## C9: Slack Conversational Orchestrator (LLM-First)
- Scope:
  - Route Slack DM messages through an LLM orchestrator before deterministic intent handlers.
  - Use tool-calling to invoke implemented skills (`clickup_task_list`/weekly alias, `clickup_task_create`) instead of pattern-only dispatch.
  - Inject client context pack from `client_context_builder` with strict budget metadata.
  - Preserve existing safety rails (confirmation, permission checks, idempotency hooks).
- Acceptance:
  - Natural-language queries and requests are handled without strict command phrasing.
  - Clarifying questions are generated when required fields are missing.
  - Tool results are returned in conversational responses, with task links preserved.
  - Existing deterministic fallback path remains available if model/tool call fails.
  - LLM token usage is logged to `ai_token_usage` using AgencyClaw stage labels.

## C10B: Clarify-State Persistence (No Looping)
- Scope:
  - Persist pending state when orchestrator returns `clarify` for mutation workflows.
  - While pending mutation state exists, route follow-up text into slot-fill/confirm path (not generic reply).
  - Support explicit cancel/resume transitions.
- Acceptance:
  - Transcript tests for locked regression fixtures pass (`R1`, `R2` below).
  - No repeated “ask for title” loops after title has already been provided.
  - Existing deterministic task-create confirmations still work.

Locked regression fixtures for C10B:
- `R1_distex_coupon_drift`
  - U: `create task for Distex`
  - A: asks for task title
  - U: `Sell stuff`
  - U: `it's a task to turn on 20% coupon codes for all products`
  - U: `coupon code for thorinox`
  - Expected:
    - stays in same pending mutation workflow
    - does not switch to generic coupon/support reply
    - reaches confirmation-ready draft or explicit missing-slot clarification
- `R2_roger_loop_title`
  - U: `can you create tasks for roger`
  - A: asks for task title
  - U: `setup coupons`
  - U: `setup coupons` (repeat)
  - U: `jsut create it`
  - U: `make one up for me?`
  - Expected:
    - no infinite title prompt loop
    - pending state remains coherent
    - action converges to confirm/cancel or explicit blocked reason

## C10B.5: Conversation History Buffer
- Scope:
  - Add bounded recent-message history buffer to session context (last 5 user+assistant exchanges / 10 messages).
  - Inject buffer into orchestrator prompt context.
  - Enforce strict size limit: max 1,500 estimated tokens for history buffer.
  - Use deterministic eviction: drop oldest full exchange first.
- Acceptance:
  - Orchestrator sees recent turns and resolves follow-up references correctly.
  - History buffer respects both caps (`<=5 exchanges`, `<=1,500 tokens`) with deterministic tested eviction.
  - No regression to existing pending-state flow behavior.

## C10A: Actor/Surface Context + Policy Gate
- Scope:
  - Build context resolver for `who` (profile/tier) and `where` (dm/channel/thread + scope).
  - Enforce pre-skill and post-skill policy checks using actor/surface context.
  - Fail closed for unknown channel scope on mutations.
- Acceptance:
  - Mutation denied when actor/surface policy disallows it.
  - Policy decisions include actionable user-facing reasons.
  - Tests cover DM vs client-channel scope + tier combinations.

## C10C: KB Retrieval Cascade + Source-Grounded Drafts
- Scope:
  - Implement retrieval cascade:
    SOP -> internal docs/playbooks -> similar historical tasks -> external docs.
  - Compose task drafts with citations + confidence tier.
  - Emit task descriptions using task-type templates from `docs/26_agencyclaw_task_brief_standard.md` with generic fallback support.
  - If no high-quality source found, ask focused clarify questions instead of inventing.
- Acceptance:
  - “Coupon code task” style prompt produces source-cited draft when data exists.
  - Fallback to similar-task retrieval works when SOP is missing.
  - Tests verify citation metadata and confidence behavior.
  - Tests verify non-bucket requests get generic fallback brief output (not empty/looping clarify behavior).
  - Tests verify ambiguous product mentions (no ASIN/SKU) trigger clarification or explicit "ASIN pending" draft fields; no identifier guessing.

## C10D: Planner + Capability Skills (De-hardcode)
- Scope:
  - Replace rigid intent branches with planner-driven execution using reusable capabilities.
  - Explicitly carve out hardcoded N-gram deterministic task-create path into planner + capability skills.
  - Keep existing behavior parity for n-gram and task flows while moving logic into shared adapters.
  - Preserve all policy/idempotency/confirmation guardrails.
- Acceptance:
  - Hardcoded intent-specific mutation path count is reduced.
  - Planner definition for this chunk is locked:
    constrained plan schema + deterministic skill execution (not open-ended ReAct loop).
  - Planner path covers N-gram flow end-to-end without hardcoded intent branch.
  - Regression tests confirm no behavior loss for shipped chunks.

## C10E: Lightweight Durable Preference Memory
- Scope:
  - Add durable key/value preference store for operator defaults (for example assignee, cadence, default client hints).
  - Load preferences into orchestrator context and drafting flows where relevant.
  - Keep explicit user override behavior (request text can override stored defaults).
  - Enforce multi-user isolation semantics for channel surfaces:
    actor-scoped preferences, requester-bound pending state, and separate `requested_by` vs `confirmed_by` audit metadata.
- Acceptance:
  - Preferences can be set/read/applied in runtime with tests.
  - Preference application is visible in draft output metadata.
  - Incorrect/stale preferences fail safe and trigger clarification.
  - Tests prove one user's preferences are not applied to another user in the same channel/thread.

## C11D: Brand Context Resolver (Shared-Destination Aware)
- Scope:
  - Add deterministic resolver service that outputs:
    destination (`clickup_space_id`/`clickup_list_id`) and brand context (`brand_id`/name) independently.
  - Use client/brand metadata from Supabase (`brands`, `agency_clients`) as source of truth.
  - For shared-destination clients with multiple brands:
    ask clarify question when product-scoped request is ambiguous.
  - For client-level requests:
    allow `brand_id=None` while still routing to valid destination.
  - Persist brand context in pending state and include in task brief metadata.
- Acceptance:
  - No hidden brand selection heuristics (for example “latest updated brand”) remain in mutation path.
  - Distex-style case (shared destination + many brands) prompts for brand only when needed.
  - Multi-destination clients continue to route correctly with explicit disambiguation.
  - Regression tests cover:
    explicit brand,
    ambiguous brand/product request,
    client-level request,
    multi-destination mapping path.

## C11E: Brand Mapping Remediation (Admin, Safe-Apply)
- Scope:
  - Add deterministic remediation planner for brands missing `clickup_space_id` and/or `clickup_list_id`.
  - Planner must evaluate per-client defaults and only mark items safe when each missing field has exactly one client-level candidate value.
  - Support dry-run summary and explicit apply execution path.
  - Keep apply path admin-gated and auditable; no implicit auto-apply.
- Acceptance:
  - Dry-run returns deterministic plan with per-brand reason (`safe_to_apply` vs blocked reason).
  - Ambiguous defaults (multiple candidate mappings per client) are blocked with explicit reason.
  - Apply updates only missing fields on safe items; unsafe items are skipped.
  - Tests cover dry-run, ambiguity block, apply success, and apply failure reporting.

## C12C: Product Identifier Guardrail (Path-1)
- Scope:
  - Enforce fail-closed product identifier behavior without a live product catalog integration.
  - For product-scoped task mutations with missing identifier:
    require explicit ASIN/SKU or explicit "identifier pending" confirmation.
  - Preserve deterministic no-guessing behavior for ambiguous/unknown product references.
  - Keep `docs/29_catalog_lookup_contract.md` and `catalog_lookup_contract.py` as optional future integration contract.
- Acceptance:
  - Product-scoped requests without ASIN/SKU do not auto-create as fully resolved tasks.
  - Runtime asks focused clarify prompt for ASIN/SKU or explicit pending flow.
  - "Identifier pending" creates draft with unresolved block and explicit first-step resolution note.
  - No silent identifier guessing in any path.
  - Regression tests cover happy path (identifier supplied), clarify path (missing), and pending path (explicit deferral).

## 6. C9 Runtime Env Prerequisites
Source of truth for deployed values:
- Render env group: `agency-os-env-var`

Required for Slack + LLM + ClickUp orchestration:
- `OPENAI_API_KEY`
- `OPENAI_MODEL_PRIMARY`
- `OPENAI_MODEL_FALLBACK`
- `SLACK_BOT_TOKEN`
- `SLACK_SIGNING_SECRET`
- `CLICKUP_API_TOKEN`
- `CLICKUP_TEAM_ID`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_JWT_SECRET`
- `ENABLE_USAGE_LOGGING=1`

Optional (recommended for spend visibility):
- `OPENAI_ADMIN_API_KEY`
- `OPENAI_ORG_ID`

Notes:
- Do not store secret values in repo docs; only document key names.
- Backend service must inherit the env group used by Slack runtime routes.

## 7. C9 Token Telemetry Contract
For every successful AgencyClaw LLM call in Slack orchestration:
- Write usage row to `public.ai_token_usage`.
- Use `tool='agencyclaw'`.
- Include stage labels (for example: `intent_parse`, `client_context_builder`, `response_compose`).
- Include contextual metadata when available:
  `run_id`, `run_type`, `skill_id`, `client_id`, `channel_id`, `thread_ts`.

Logging is best-effort and must not block user response paths.

## 8. Prompt Template (For Coding Agent)
```text
Implement Chunk <ID> in repo `agency-os`.

Rules:
- Work only within this chunk scope.
- Use PRD `docs/23_agencyclaw_prd.md` (v1.19) as source of truth.
- No extra features.
- Add/update tests.
- Keep migration changes separate unless this chunk requires schema.

Deliverables:
1) Files changed + rationale
2) Tests added/updated
3) Commands run and outcomes
4) Risks/TODOs
```
