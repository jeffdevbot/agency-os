# AgencyClaw PRD And Build Plan

> AI operations assistant for Agency OS. Slack-first interaction, ClickUp action execution, Supabase-backed knowledge and routing.

## 1. Product Intent
AgencyClaw is the successor to Vara/Vora. It should:
- Let team members chat naturally in Slack about meeting notes, SOP questions, and task creation.
- Feel conversational and assistant-like in Slack (Jarvis-style), not command-syntax dependent.
- Route work to the right assignee using Command Center mappings.
- Create and track ClickUp tasks reliably.
- Reuse as much existing Agency OS infrastructure as possible.

Non-goals for v1:
- Full multi-agent architecture from day one.
- Full vector knowledge ingestion from external sources.
- New standalone "bot platform" separate from existing backend.

## 2. Current Reality (Codebase)
AgencyClaw is not greenfield. Existing assets:
- `public.playbook_sops` with seeded SOP registry and aliases.
- `public.client_assignments` + `public.agency_roles` for role-based routing.
- Slack integration already in backend FastAPI (`/api/slack/events`, `/api/slack/interactions`).
- Debrief extraction and ClickUp send flows in Next API routes.
- Operational skills already live as APIs: `/ngram`, `/npat`, `/adscope`, `/root`, `/api/scribe/*`, `/api/debrief/*`.

Decision: reuse current Slack integration path and evolve it. Do not introduce Slack Bolt in v1.

## 3. Naming And Role Standards
### 3.1 Bot Naming
- Product: `AgencyClaw`
- Slack app display: `AgencyClaw`
- Internal legacy references to Vara/Vora can remain temporarily during migration.

### 3.2 Role Naming
Current role slug `brand_manager` is being renamed to `customer_success_lead` (CSL).

Migration rule:
1. Add new role slug `customer_success_lead`.
2. Backfill assignments currently using `brand_manager` to `customer_success_lead`.
3. Update UI role slots and routing logic to use CSL.
4. Remove legacy `brand_manager` slug after safe migration window.

## 4. Architecture (v1)
### 4.1 Single Orchestrator First
AgencyClaw v1 uses one orchestrator service with typed tool adapters.

Components:
- `Orchestrator`: LLM-first intent parsing, policy checks, routing decisions.
- `ConversationalRouter`: produces either direct reply, clarification question, or tool-call plan.
- `KnowledgeService`: SOP lookup and answer assembly.
- `RoleResolutionService`: map client/brand + role -> assignee.
- `TaskExecutionService`: ClickUp task create/update + status tracking.
- `AuditService`: structured event logging.
- `SkillAdapters`: typed wrappers for existing tools.
- `DeterministicFallbackRouter`: existing pattern-matching handlers used when model/tool routing fails.

This design keeps a clean seam for future sub-agents without forcing early complexity.

### 4.4 Runtime Routing Priority (v1)
Slack DM runtime should follow this order:
1. Resolve identity + policy context.
2. Attempt LLM conversational routing (`reply`, `clarify`, or `tool_call`).
3. Execute tool call via typed adapter when selected.
4. If LLM/tool planning fails, fall back to deterministic intent handlers.

Rule:
- Existing deterministic routes are retained as resilience fallback, not the primary UX.

### 4.5 Runtime vs Skill Boundary (OpenClaw-style)
AgencyClaw should keep a hard boundary between conversation runtime and modular skills:

- Runtime layer responsibilities:
  - conversation state and memory windows,
  - actor/surface policy checks,
  - clarification and confirmation workflows,
  - plan/tool selection, retries, and fallback routing,
  - audit envelope and telemetry.
- Skill layer responsibilities:
  - typed input schema,
  - deterministic business operation execution,
  - structured result/error payloads.
- Runtime must not embed skill-specific business logic beyond safe routing/guards.
- Skills must not own global conversation behavior.
- “Add team member to client/brand role” is a skill-domain mutation (for example assignment upsert/remove), executed under runtime policy + confirmation gates.

### 4.6 Brand Context Resolution Policy
AgencyClaw must resolve **destination** and **brand context** separately.

- Destination resolution:
  - where the task is created (`clickup_space_id` / `clickup_list_id`).
- Brand context resolution:
  - which brand the request refers to (`brand_id`/brand name for task brief + metadata).

Rules:
- Never infer brand by “latest updated brand” or other hidden heuristics.
- For clients with one shared destination and multiple brands:
  - product-scoped requests require explicit brand disambiguation when ambiguous.
  - client-level requests may proceed with no brand context.
- For clients with multiple brand-specific destinations:
  - destination is selected from explicit brand context or an explicit clarify step.
- If brand cannot be resolved confidently, runtime must clarify (or explicitly mark brand pending), never silently guess.

### 4.2 Future Multi-Agent Upgrade Path
If needed later, split orchestrator responsibilities into:
- Librarian (knowledge)
- Inspector (analysis)
- Relay (output/action)

No schema rewrite should be required if service contracts are stable.

### 4.3 Orchestrator Instruction Source (SOUL/AGENTS-style)
AgencyClaw should support file-based orchestrator instructions so behavior can be tuned without redeploying application code.

v1:
- Keep baseline system behavior in a versioned file (for example: `docs/agent_runtime/orchestrator.md`).
- Load file content at process start and include a version/hash in logs for traceability.
- Allow safe reload via admin-only command or deploy restart.

Later:
- Optional DB-backed override layer for urgent hotfixes, with audit trail and rollback.

## 5. Slack Runtime Decision
### 5.1 Slack Bolt vs Existing FastAPI Slack Routes
- v1 choice: keep current FastAPI webhook handlers.
- Reason: already deployed, already signed request validation, lower migration risk.
- Bolt is optional later if interactive complexity grows substantially.

### 5.2 Rename Strategy
Reuse existing Slack integration and rename behavior/branding from Vara to AgencyClaw.

### 5.3 Conversational UX Decision
For Slack DM interactions, AgencyClaw is LLM-first:
- Users should not need strict command phrasing for common requests.
- Bot should ask natural clarifying questions when details are missing.
- Tool actions remain policy-gated and auditable through typed adapters.
- Deterministic classifier remains as fail-safe fallback path.

## 6. Debrief As Slack-Native Capability
### 6.1 Product Behavior
User can DM or mention AgencyClaw with:
- pasted meeting summary,
- copied client notes,
- plain-language follow-up request.

AgencyClaw should propose/create routed tasks and report outcomes in-thread.

### 6.2 Contract Refactor (Important)
Current `/api/debrief/*` endpoints are Next route handlers, not ideal as core agent runtime contracts.

v1 adaptation:
1. Extract shared Debrief business logic into a backend service module.
2. Keep `/api/debrief/*` for web UI compatibility.
3. Let Slack Orchestrator call the shared service directly (not through UI route coupling).

Result: one logic core, multiple interfaces (web + Slack).

## 7. Permissions Model
Three tiers:
- `super_admin`: full control, override, forced actions, emergency tooling.
- `admin`: most operational actions, approval authority.
- `member`: routine usage, limited auto-action authority.

Additional role state:
- `viewer`: read-only access where allowed; no mutation skills.

Implementation note:
- Existing `profiles.is_admin` supports admin detection today.
- v1 super_admin resolution is application-layer allowlist, not a DB enum value.
- Super admin identities are resolved from `SUPER_ADMIN_PROFILE_IDS` (or equivalent config table in later phases).
- RLS remains `is_admin`-based for DB mutation boundaries.
- Application-layer policy gates enforce super_admin-only operations and viewer restrictions.

Tier resolution order (v1):
1. `super_admin`: `profiles.id` in `SUPER_ADMIN_PROFILE_IDS`.
2. `admin`: `profiles.is_admin = true` and not in super_admin set.
3. `viewer`: `profiles.team_role = 'viewer'` and not admin.
4. `member`: all remaining authenticated users.

### 7.1 Policy Matrix (initial)
- Viewer read operations: explicit allowlist only (for example, selected status/report reads); no mutation operations.
- SOP Q&A: `member+`
- Task draft generation: `member+`
- Task auto-create from ambiguous/low-confidence context: `admin+`
- Role/threshold policy changes: `admin+`
- Global/system overrides and emergency actions: `super_admin`
- Command Center profile/assignment mutations (including Slack ID / ClickUp ID): `admin+`

### 7.2 Slack Identity Resolution (required)
All Slack-initiated operations must resolve actor identity before policy evaluation.

Required flow:
1. Inbound Slack event contains `slack_user_id`.
2. Resolve `profiles.id` via `profiles.slack_user_id = slack_user_id`.
3. Load tier context from profile (`is_admin`, `team_role`) + super_admin allowlist.
4. If no matching profile, return actionable message: ask admin to map Slack user in Command Center.
5. If multiple matches ever occur, fail closed and alert admin (data integrity issue).

Runtime rule:
- Skill invocation and mutation paths must not execute without a resolved `profiles.id`.

### 7.3 Actor + Surface Context (required for policy)
AgencyClaw must evaluate permissions with both actor identity and conversation surface.

Required actor context:
- `profile_id`
- `slack_user_id`
- resolved tier (`super_admin` / `admin` / `member` / `viewer`)
- `is_admin`

Required surface context:
- `surface_type`: `dm`, `channel`, or `thread`
- `channel_id`
- `channel_scope`: `internal`, `client_scoped`, or `unknown`
- resolved `client_id` / `brand_id` when available

Policy rule:
- Mutation authorization is computed from `(actor_tier, surface_scope, requested_skill)`.
- Unknown channel scope must fail closed for mutations.
- DM scope can allow broader operations than client-scoped channels, but still tier-gated.
- Runtime must pass actor/surface context into orchestrator prompt + post-tool policy gate.

## 8. Data Model
### 8.1 Use Existing Tables
- `public.playbook_sops`
- `public.client_assignments`
- `public.agency_roles`
- `public.brands`
- `public.profiles`

### 8.2 Add New Tables (correct references)
```sql
create table public.agent_events (
  id uuid primary key default gen_random_uuid(),
  event_type text not null,
  client_id uuid references public.agency_clients(id),
  employee_id uuid references public.profiles(id),
  payload jsonb,
  confidence_level text,
  sop_id uuid references public.playbook_sops(id),
  created_at timestamptz default now()
);

create table public.agent_tasks (
  id uuid primary key default gen_random_uuid(),
  clickup_task_id text unique,
  client_id uuid references public.agency_clients(id),
  assignee_id uuid references public.profiles(id),
  source text not null,
  source_reference text,
  skill_invoked text,
  sprint_week date,
  status text not null default 'pending',
  last_error text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table public.threshold_rules (
  id uuid primary key default gen_random_uuid(),
  playbook text not null,
  client_id uuid references public.agency_clients(id),
  metric text not null,
  condition text not null,
  threshold_value numeric not null,
  task_type text not null,
  assignee_role_slug text not null,
  task_template text not null,
  active boolean default true,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table public.skill_catalog (
  id text primary key,
  name text not null,
  description text not null default '',
  owner_service text not null,
  input_schema jsonb not null default '{}'::jsonb,
  output_schema jsonb not null default '{}'::jsonb,
  implemented_in_code boolean not null default true,
  enabled_default boolean not null default true,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table public.skill_policy_overrides (
  id uuid primary key default gen_random_uuid(),
  skill_id text not null references public.skill_catalog(id) on delete cascade,
  scope_type text not null check (scope_type in ('global', 'client', 'team')),
  scope_id uuid,
  enabled boolean,
  min_role_tier text check (min_role_tier in ('member', 'admin', 'super_admin')),
  requires_confirmation boolean,
  allowed_channels text[] not null default '{}'::text[],
  max_calls_per_hour integer check (max_calls_per_hour is null or max_calls_per_hour >= 0),
  created_by uuid references public.profiles(id),
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table public.skill_invocation_log (
  id uuid primary key default gen_random_uuid(),
  idempotency_key text not null unique,
  skill_id text not null references public.skill_catalog(id) on delete restrict,
  actor_profile_id uuid references public.profiles(id),
  status text not null check (status in ('pending', 'success', 'failed', 'duplicate')),
  request_payload jsonb not null default '{}'::jsonb,
  response_payload jsonb not null default '{}'::jsonb,
  error_message text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
```

### 8.3 Skill Table Runtime Scope (v1 vs later)
v1 implementation scope:
- Use `skill_catalog` as the runtime source of enabled skills + metadata.
- Use `skill_invocation_log` for idempotency tracking and execution audit.
- Keep `skill_policy_overrides` as a seeded admin table, but do not make it a hard runtime dependency yet.

Later (v1.5+):
- Turn on full policy resolution precedence (`global` -> `team` -> `client`) once core flows are stable.
- Enforce `allowed_channels`, `requires_confirmation`, and `max_calls_per_hour` from DB policy rows.

### 8.4 Operational State Tables (recommended)
Add lightweight runtime tables to support durable dedupe and run/session isolation.

Recommended:
- `slack_event_receipts`: one row per processed Slack event/interaction key (`event_key`, `event_type`, `received_at`, `status`, `error_message`).
- `agent_runs`: one row per orchestrator run (`run_id`, `run_type`, `run_key`, `actor_profile_id`, `channel_id`, `thread_ts`, `status`, `started_at`, `completed_at`, `parent_run_id`).

Purpose:
- Prevent duplicate Slack side effects across retries/restarts.
- Isolate interactive chat context from scheduled/background work.
- Provide parent/child run lineage without requiring full multi-agent runtime.

### 8.5 Client/Brand Context + KPI Targets
AgencyClaw supports structured profile context and time-scoped KPI targets.

Recommended additions:
- Add context fields on `agency_clients`/`brands` (for example `context_summary`, `target_audience`, `positioning_notes`).
- Add `brand_market_kpi_targets` for period-scoped targets (monthly/annual) including optional TACOS, ACOS, and sales targets.

Clarification guardrail:
- If user provides any KPI target without marketplace, AgencyClaw must ask follow-up clarification before writing.
- Example: `Set TACOS target to 15%` -> `Which marketplace (US, CA, etc.)?`
- Example: `Set monthly sales target to 200k` -> `Which marketplace (US, CA, etc.)?`

### 8.6 Migration Manifest Requirements
The PRD table contracts must map to concrete migration files.

Required migration set before Phase 1 implementation:
- `20260217000001_agencyclaw_skill_catalog_and_csl_role.sql`
- `20260217000002_agencyclaw_runtime_isolation.sql`
- `20260217000003_client_brand_context_and_kpi_targets.sql`
- `20260217000004_agent_core_tables.sql` for `agent_events`, `agent_tasks`, and `threshold_rules` (including indexes, RLS, and updated_at triggers).

Rule:
- Phase work cannot start against tables that exist only in PRD prose/SQL snippets but not in applied migrations.

## 9. Knowledge Base Strategy
v1:
- Keep `playbook_sops` as curated internal knowledge source.
- Keep alias lookup + category lookup.
- Do not block v1 on vector search.
- Use retrieval cascade with trust ordering:
  1) curated SOPs (`playbook_sops`)
  2) approved internal docs/playbooks
  3) similar historical ClickUp tasks (client-first)
  4) external materials (lowest trust)

Behavior rule:
- Task drafts must be source-grounded when knowledge is available.
- If no strong source match exists, agent must say so explicitly and ask targeted clarifying questions.
- Do not silently invent SOP-backed procedures.

v2:
- Add vector semantics and external ingestion.
- Prefer separate `knowledge_documents` table for external/transcript materials to avoid mixing trust semantics with curated SOP cache.
- Add ingestion/approval flow for non-SOP documents (playbooks, transcripts, notes) before high-trust use in task drafting.

## 10. Idempotency And Concurrency (must-have)
### 10.1 Idempotency (Slack retries)
Problem:
- Slack can retry the same event delivery.

Requirement:
- Store processed event keys and skip duplicates safely.

Suggested key:
- Slack `event_id` for event callbacks.
- Deterministic interaction key for button/action payloads.

Implementation note:
- Do not rely only on `X-Slack-Retry-Num` headers.
- Persist dedupe keys in DB so dedupe survives process restarts.
- Use atomic insert pattern:
  `INSERT ... ON CONFLICT (event_key) DO NOTHING RETURNING id`.
- If row is returned: process event.
- If no row is returned: event is duplicate; return HTTP 200 with no side effects.
- Do not use SELECT-then-INSERT for dedupe.
- Retention is handled by scheduled cleanup jobs (default 30 days for `slack_event_receipts`).

### 10.2 Concurrency (race prevention)
Problem:
- Two users may trigger edits/actions for same task/client concurrently.

v1 safeguard:
- Add per-entity advisory lock strategy around critical mutation paths.
- Use idempotency key on outbound task creation.

Required lock pattern:
- Before mutation skill execution, acquire transaction-scoped advisory lock keyed by:
  `hashtext(skill_id || ':' || target_entity_type || ':' || target_entity_id)`.
- If lock cannot be acquired immediately, fail fast with user-visible conflict message.
- Do not silently queue behind lock in v1.

Implementation status note (as of February 18, 2026):
- C4C shipped with an in-memory per-worker guard for task-create mutation paths.
- Cross-worker distributed lock (`C4D`) is intentionally deferred as a future hardening feature.
- Duplicate suppression + idempotency key checks remain active in current runtime.

v2 enhancement:
- Move to queued lane execution once volume warrants.

### 10.3 Execution Context Isolation (must-have)
Problem:
- Scheduled/background runs can pollute interactive user conversation state if they share the same session key.

Requirement:
- Every run has explicit `run_type` and `run_key`, and context is isolated by these fields.

Suggested model:
- `run_type = 'interactive'`: key by Slack conversation scope (for example `workspace_id:channel_id:thread_ts_or_dm`).
- `run_type = 'heartbeat'`: key by deterministic schedule scope (for example `heartbeat:client_id:rule_id:YYYY-MM-DD`).
- `run_type = 'ingestion'`: key by source document/job identity.

Rule:
- Interactive context never reads/writes heartbeat context directly.
- Background outputs are posted as summaries/events, not injected as hidden chat history.

## 11. Queue Strategy
### 11.1 v1
No Celery requirement for first release.
- Use synchronous + bounded background tasks.
- Keep queue abstraction interface in code (`enqueue_job(...)`) so queue backend can be swapped later.
- Use `agent_runs` envelope for all async work so runtime behavior is consistent when queue backend is introduced.

### 11.2 v1.5 / v2
Introduce Redis + Celery lane queues if needed:
- `client.{client_id}` serial lane
- `background.thresholds`
- `background.ingestion`
- `realtime.staff`

This keeps OpenClaw-style lane advantages without forcing day-one infra overhead.

### 11.3 Proactive Heartbeat (MVP)
AgencyClaw should not be purely reactive long-term.

v1 MVP:
- Add one scheduled proactive scan with isolated heartbeat runs.
- Initial use case: flag client sprint/task risk (for example: sprint ending soon with open tasks) or stale playbook cadence (for example: no recent N-Gram run).
- Post concise alerts to a defined channel/DM target with links and suggested action.
- Respect permission policy and per-client/channel opt-in controls.

Success criteria:
- Alerts are useful (low noise), deduplicated, and auditable.

### 11.4 Child-Run Pattern (before sub-agents)
For long-running operations, use child runs instead of blocking orchestrator requests.

Pattern:
- Parent run records intent and enqueues child run(s).
- Child run executes with its own timeout/context and reports structured result.
- Parent run posts incremental status and final outcome.

Use for:
- Debrief batch extraction/send.
- Large analysis jobs (for example AdScope-heavy requests).
- Future ingestion workflows.

## 12. Google Meeting Notes Inputs
Current limitation is user-account-specific sourcing. AgencyClaw input model should support:
1. Paste summary text directly in Slack (fastest, universal).
2. Provide Google Doc link and fetch content using approved integration path.
3. Future: Workspace-level delegated access where appropriate.

Do not require global crawl access to all docs for v1.

## 13. Skill Registry (typed adapters)
Each skill definition should include:
- `id`, `description`
- `input_schema`
- `output_schema`
- `auth_policy`
- `idempotency_key_builder`
- `owner_service`

Initial skill set:
- `ngram_process`
- `ngram_collect`
- `npat_process`
- `npat_collect`
- `adscope_audit`
- `root_process`
- `scribe_generate`
- `debrief_extract`
- `debrief_send_to_clickup`
- `cc_org_chart_ascii`
- `kpi_target_upsert`
- `kpi_target_lookup`
- `clickup_task_list_weekly`
- `clickup_task_create`
- `clickup_task_update`
- `meeting_parser`
- `debrief_meeting_ingest`
- `debrief_task_review`
- `client_context_builder`
- `client_brief`
- `sop_lookup`
- `sop_sync_run`
- `clickup_task_quality_gate`
- `clickup_task_duplicate_check`
- `run_status_lookup`
- `run_retry`
- `event_dedupe_audit`
- `error_digest`
- `usage_cost_report`
- `cc_assignment_matrix`
- `cc_role_capacity_snapshot`
- `cc_policy_explain`
- `cc_clickup_space_sync`
- `cc_clickup_space_list`
- `cc_clickup_space_classify`
- `cc_clickup_space_brand_map`

Command Center skill family (required for Slack org/assignment changes):
- `cc_client_lookup` (`member+`): list/search clients and brands.
- `cc_role_lookup` (`member+`): list/search assignable role slugs.
- `cc_resolve_scope` (`member+`): resolve natural language client/brand references to IDs.
- `cc_org_chart_ascii` (`member+`): render current client/brand staffing as an ASCII org chart for Slack.
- `cc_assignment_upsert` (`admin+`): assign or replace assignee for a client/brand role slot.
- `cc_assignment_remove` (`admin+`): clear assignee from a client/brand role slot.
- `cc_assignment_audit_log` (`admin+`): write assignment-change audit event with actor and before/after values.

Command Center team/profile parity skills (required for web parity via chat):
- `cc_team_member_lookup` (`member+`): lookup employee by email/name/Slack ID/ClickUp ID.
- `cc_team_member_create` (`admin+`): create ghost profile/team member.
- `cc_team_member_update` (`admin+`): update profile fields (display name, employment status, allowed tools, role flags).
- `cc_team_member_update_slack_id` (`admin+`): set/replace `profiles.slack_user_id`.
- `cc_team_member_update_clickup_id` (`admin+`): set/replace `profiles.clickup_user_id`.
- `cc_team_member_archive` (`admin+`): archive/deactivate team member.

Command Center client/brand parity skills (required for web parity via chat):
- `cc_client_update` (`admin+`): update client fields (name/status/notes/context fields).
- `cc_brand_list_all` (`member+`): list all brands with mapped ClickUp destination fields.
- `cc_brand_create` (`admin+`): create brand for client.
- `cc_brand_update` (`admin+`): update brand fields (name, marketplaces, keywords, ClickUp routing, context fields).
- `cc_brand_clickup_mapping_audit` (`admin+`): identify brands missing `clickup_space_id` and/or `clickup_list_id`.
- `cc_brand_clickup_space_set` (`admin+`): set/replace `brands.clickup_space_id`.
- `cc_brand_clickup_list_set` (`admin+`): set/replace `brands.clickup_list_id`.
- `cc_brand_delete` (`admin+`): delete archived/unused brand when permitted by policy.

Example command path:
- User asks: `Make me the Customer Success Lead on Distex`.
- Orchestrator runs: `cc_resolve_scope` -> `cc_role_lookup` -> `cc_assignment_upsert` -> `cc_assignment_audit_log`.
- Require explicit confirmation before mutation in channel contexts.

### 13.1 OpenClaw Skills Alignment
AgencyClaw adopts the useful parts of OpenClaw's skills model while keeping typed backend adapters as the execution contract.

Adopt now:
- Skill identity + metadata (name, description, auth policy, idempotency strategy, owner service).
- Per-skill enable/disable controls in config.
- LLM-first tool routing for user-invocable operations, with deterministic command routing fallback.
- Security posture: treat third-party/community skill packages as untrusted by default.

Adopt later (optional):
- Filesystem skill package format (`SKILL.md` frontmatter + instructions) for portability.
- Skill load precedence model (`workspace` > `managed` > `bundled`).
- Load-time capability gating (required env vars, binaries, config flags, OS).

Do not adopt in v1:
- Automatic installation from public skill marketplaces.
- Direct execution of unreviewed community skill bundles.

### 13.2 KPI Target Interaction Rules
- `kpi_target_upsert` is `admin+`.
- All KPI target commands require explicit `marketplace_code` (TACOS, ACOS, sales targets).
- When missing, orchestrator asks a blocking clarification and performs no mutation.
- `kpi_target_lookup` is `member+`.

Resolution rules for `(brand_id, marketplace_code)`:
- Resolve current period by calendar date (today in UTC).
- Monthly pass: find active monthly row for current month (`period_start = first day of current month`).
- Annual pass: find active annual row for current year (`period_start = Jan 1 of current year`).
- Merge behavior when both exist:
  monthly metric values win where present; missing monthly metrics fall back to annual.
- If no current-period row exists, return no active target for that metric.
- Response should include per-metric source attribution (`monthly`, `annual`, or `none`).

### 13.3 Command Center Chat Parity Rules
- Goal: anything available in Command Center web should be invocable in chat via explicit skills.
- All mutation operations require confirmation in channel contexts before commit.
- Identity updates (`slack_user_id`, `clickup_user_id`) must include before/after values in audit logs.
- When a requested mutation is ambiguous (multiple matching people/clients/brands), orchestrator must ask clarifying disambiguation before mutation.
- Read operations (`member+`) should be fast-path and return concise structured responses.

Confirmation modes:
- `self_confirmation`: requesting user confirms intent before execution.
- `admin_approval`: separate admin confirms execution for actions above requester tier.

v1 decision:
- Implement `self_confirmation` only.
- Defer `admin_approval` workflow until dedicated approval schema + UX is defined.

### 13.4 ClickUp Task Interaction Rules
- `clickup_task_list_weekly` is `member+` and supports prompts like `what's being worked on this week for client X`.
- `clickup_task_create` is `member+` with policy gate; default destination is the resolved brand backlog:
  `brands.clickup_list_id` when present, otherwise the brand `clickup_space_id` default backlog path.
- If no ClickUp mapping exists for the resolved brand, do not create task; ask admin to map space/list first (or run mapping update skill if authorized).
- For thin task requests (e.g., vague title only), orchestrator must ask for missing details (owner, due date, success criteria, scope) before create.
- If user explicitly says `create anyway`, create task as draft and return a follow-up checklist of fields to edit in ClickUp.
- `clickup_task_update` is `admin+` by default; support later relaxation via policy overrides.
- All create/update operations in channels require explicit confirmation before mutation.
- Every successful create/update response must include direct ClickUp task URL(s) for one-click follow-up.
- `clickup_task_create` idempotency key:
  `sha256(brand_id + ':' + normalized_title + ':' + yyyy_mm_dd)` with 24h duplicate suppression window.
- All outbound ClickUp create/update calls should include `agent_runs.id` trace tag in description or task metadata where supported.
- ClickUp API rate-limit/timeout handling: exponential backoff, max 3 retries, then fail with explicit retry guidance.
- Orphan handling: if ClickUp create succeeds but AgencyClaw persistence fails, emit `agent_events.event_type = 'clickup_orphan'`, store payload, and alert admin.
- `clickup_task_list_weekly` must paginate ClickUp responses and cap Slack payload to 200 tasks with truncation notice.

Scope note:
- v1 does not require inbound ClickUp webhook sync.
- `agent_tasks.status` is source-of-truth for AgencyClaw-created operations and explicit refresh actions only.

### 13.5 Brand ClickUp Mapping Integrity Rules
- Users can ask for `all brands` in chat via `cc_brand_list_all`.
- Admin can ask for mapping audit via `cc_brand_clickup_mapping_audit`; response must include:
  total brand count, mapped count, unmapped count, and explicit list of missing mappings.
- Admin can fix gaps in-chat using `cc_brand_clickup_space_set` / `cc_brand_clickup_list_set`.
- Task creation flows must call mapping integrity checks and fail closed when destination mapping is missing.
- Mapping integrity checks should validate space classification first:
  brand backlog routing must use spaces classified as `brand_scoped`.

### 13.6 Client Context And Parsing Rules
- `meeting_parser` is a standalone skill and must be testable independently from ingest/send workflows.
- `client_context_builder` is a first-class foundational skill:
  builds a fixed-budget context pack for orchestrator calls (assignments, KPI targets, active tasks, relevant SOP slices, recent events).
- `client_context_builder` output should include metadata for observability:
  token estimate, included sources, omitted sources, and freshness timestamps.
- Context pack generation should be deterministic for a given `(client, time window, scope)` input unless source data changed.

Token budget contract:
- Default context budget: 4,000 tokens.
- Initial allocation targets:
  assignments 500, KPI targets 500, active tasks 1,500, SOP slices 1,000, recent events 500.
- If budget is exceeded, truncation priority is deterministic:
  drop oldest events first, then lowest-priority SOP slices, then completed/lowest-priority tasks.
- Budget is tunable via `CONTEXT_BUILDER_MAX_TOKENS`.

### 13.7 Proactive Briefing Rules (without sprint planner for now)
- `client_brief` is `member+` for on-demand usage and `admin+` for scheduled channel push.
- `client_brief` should produce pre-call context summaries:
  current priorities, open tasks, KPI status, risks, blockers, and recommended talking points.
- `sprint_planner` is intentionally deferred; do not include in active skill roster yet.

### 13.8 Reliability And Operations Skills
- `run_status_lookup` (`member+`): retrieve run status and outputs from `agent_runs`.
- `run_retry` (`admin+`): retry failed runs with explicit idempotency strategy.
- `event_dedupe_audit` (`admin+`): inspect duplicate/failed Slack receipts.
- `error_digest` (`admin+`): summarize recent application failures by tool/severity.
- `usage_cost_report` (`admin+`): summarize model usage/cost by tool/user/client.

Deferred:
- `approval_request_create` remains deferred until dedicated approval schema and UX are implemented.

### 13.9 Slack Confirmation Protocol
All mutation operations in channel contexts require interactive confirmation before commit.

Mechanism:
- Post ephemeral Block Kit confirmation to requesting user with change summary and `Confirm` / `Cancel` actions.
- Track pending confirmation in `agent_runs` (`status = 'awaiting_confirmation'`).

Timeout:
- Confirmation expires after 10 minutes.
- Expired confirmations transition run to `cancelled`.
- Expiry must not execute pending mutation.

Idempotency:
- Interaction dedupe key is deterministic action identity:
  `workspace_id + user_id + channel_id + message_ts + action_id + selected_value`.
- Persist this key in `slack_event_receipts`.
- Duplicate deliveries of same confirmation action are safe no-ops.

v1 approval scope:
- v1 uses self-confirmation only.
- Cross-user admin approval workflow is deferred.

DM rule:
- Destructive mutations still require confirmation in DM.
- Non-destructive additive mutations may skip confirmation only when policy explicitly sets `requires_confirmation = false`.

### 13.10 Token Usage Telemetry (AgencyClaw)
- AgencyClaw must log LLM token usage to existing `public.ai_token_usage` (same pattern used by Scribe/Debrief).
- Use `tool = 'agencyclaw'` with stage labels per operation (for example: `intent_parse`, `meeting_parser`, `client_context_builder`, `response_compose`).
- Include model + token counts (`prompt_tokens`, `completion_tokens`, `total_tokens`) for every successful LLM call.
- Include structured `meta` context where available: `run_id`, `run_type`, `skill_id`, `client_id`, `channel_id`, `thread_ts`.
- Logging is best-effort and must never block user-facing responses.
- `usage_cost_report` should include AgencyClaw rows from this table by default.

### 13.11 Skill Catalog Seeding Rules
- `skill_catalog` must include all skill IDs planned through Phase 2.6, even if not yet implemented.
- Not-yet-implemented skills should be seeded with:
  `implemented_in_code = false` and `enabled_default = false`.
- Skills planned for Phase 3+ may be deferred from seed until their phase starts.
- Build validation must compare PRD skill IDs against `skill_catalog` and fail on missing required rows.

### 13.12 Identity Sync And Reconciliation Rules
AgencyClaw supports periodic team identity sync from Slack and ClickUp to reduce manual profile maintenance.

Sync model:
- Pull Slack users and ClickUp users in read-only mode.
- Reconcile against existing `profiles` using deterministic matching:
  1. exact email (case-insensitive),
  2. exact `slack_user_id`,
  3. exact `clickup_user_id`.
- Name-only or fuzzy matches must never auto-merge.

Resolution outcomes:
- `auto_match`: safe deterministic match; apply mapping automatically and audit.
- `new_profile`: no match; create ghost profile when policy allows.
- `needs_review`: ambiguous or conflicting mapping; no auto-merge.

`needs_review` workflow:
- Bot notifies requesting admin in Slack (DM or thread context) with proposed candidates and rationale.
- Bot provides explicit actions: `Confirm match`, `Reject / keep separate`, `Pick different profile`.
- Decision is admin-only, expires in 10 minutes, and uses idempotent interaction key handling.
- Every decision writes audit trail with actor, chosen action, and before/after identity mapping.

Safety rules:
- Conflicting identity claims (same Slack/ClickUp ID tied to different profiles) fail closed and require manual decision.
- Reconciliation never mutates third-party systems; only AgencyClaw profile mappings are updated.

### 13.13 ClickUp Space Sync And Classification Rules
AgencyClaw should ingest ClickUp spaces and keep a local classification registry.

Space classification states:
- `brand_scoped`: space is tied to one brand (default target for brand backlog tasks).
- `shared_service`: space is cross-brand/shared (for example reporting specials).
- `unknown`: discovered but not yet reviewed.

Required behavior:
- Regular sync ingests all accessible ClickUp spaces with IDs and names.
- Bot can list spaces and current classification state in chat.
- Admin can explicitly classify spaces in chat (for example: `Mark Reporting Specials as shared_service`).
- Admin can explicitly map/unmap a `brand_scoped` space to a brand when inference is wrong or missing.

Routing safety:
- Brand task auto-routing must not use `shared_service` or `unknown` spaces by default.
- If target space is `unknown`, bot asks admin to classify before using it for brand backlog routing.
- Explicit admin override can route to `shared_service` for exceptional workflows, with confirmation and audit trail.

Suggested skills:
- `cc_clickup_space_sync` (`admin+`): refresh space registry from ClickUp.
- `cc_clickup_space_list` (`member+`): list spaces + classification + mapping status.
- `cc_clickup_space_classify` (`admin+`): set classification state for a space.
- `cc_clickup_space_brand_map` (`admin+`): map/unmap a space to a brand.

### 13.14 Conversational Orchestrator Rules (Slack DM)
- Slack DM is LLM-first for conversational interaction quality.
- Orchestrator response modes are:
  - `reply`: answer directly without tool invocation.
  - `clarify`: ask blocking follow-up for missing required fields.
  - `tool_call`: invoke typed skill adapter with validated arguments.
- `tool_call` is limited to enabled skills in `skill_catalog`.
- For v1 scope, required tool-call coverage includes:
  - `clickup_task_list_weekly`
  - `clickup_task_create`
- If model routing fails, times out, or returns invalid schema, runtime must transparently fall back to deterministic handlers.
- Conversational mode must preserve all existing safeguards:
  confirmation requirements, permission checks, idempotency, and audit logging.
- Clarify mode for mutation workflows must persist pending slot state (`pending_*`) so follow-up user messages continue the same workflow.
- While pending mutation state exists, generic conversational `reply` is disallowed; runtime must either:
  continue slot-fill/confirmation flow or explicitly cancel it.
- Orchestrator prompt context must include actor + surface context (who + where).
- Orchestrator prompt context must include a bounded recent conversation window
  (locked at last 5 user+assistant exchanges) to reduce stateless per-message behavior.

### 13.17 Conversation Memory And Preferences (v1.5 bridge)
- Keep lightweight session conversation buffer for orchestrator context:
  store last 5 user+assistant exchanges (10 messages) in session context (rolling window).
- History buffer hard cap: 1,500 tokens estimated.
- Eviction rule: remove oldest full exchange first until both limits are satisfied
  (<= 5 exchanges and <= 1,500 tokens).
- Buffer is short-term/ephemeral (session-scoped), not long-term memory.
- Add lightweight durable user preferences for operator defaults
  (for example default assignee, preferred cadence, default client hints).
- Preference memory is explicit key/value state with auditability; full semantic memory remains Phase 4.
- Multi-user surface rules (channels/threads):
  - Preferences are actor-scoped (per `profile_id`), never shared globally across channel participants.
  - Pending mutation state is thread/request scoped and should remain bound to requester by default.
  - Runtime must record and distinguish `requested_by` and `confirmed_by` for mutation actions.
  - Preference resolution precedence:
    1) explicit message content
    2) active pending thread state
    3) actor-scoped preferences
    4) optional channel defaults (if configured)
    5) org/client defaults
  - One user's preferences must never be applied to another user implicitly.

### 13.15 Actor + Surface Policy Gate Rules
- Pre-tool policy gate:
  - Resolve actor + surface context before orchestrator tool execution.
  - Reject skills not allowed for current tier/surface with explicit reason.
- Post-tool policy gate:
  - Validate final mutation intent again before execution (defense in depth).
- Scope defaulting:
  - In `client_scoped` channels, prefer channel client scope over free-text client guesses.
  - In DM, use active client + clarification when ambiguous.
- Confirmation policy:
  - Use self-confirmation for v1 mutation paths.
  - Keep admin-approval flow deferred.

### 13.16 Knowledge Retrieval And Drafting Rules
- Retrieval cascade for mutation drafting:
  1) SOP lookup
  2) internal docs/playbooks
  3) similar historical tasks
  4) external documents/transcripts
- Draft response contract:
  - include concise draft title/description/checklist
  - include source citations (for example: SOP category/title, historical task links)
  - include confidence tier (`high`, `medium`, `low`)
- Confidence behavior:
  - `high`: proceed to confirmation-ready draft
  - `medium`: ask focused clarification before confirmation
  - `low`: do not execute; ask user to choose/confirm source direction

### 13.16.1 Task Brief Composition Standard
- For recurring operations, AgencyClaw should produce a concise Task Brief and link the canonical SOP, rather than pasting the full SOP body by default.
- Task Brief generation should follow `docs/26_agencyclaw_task_brief_standard.md`.
- Preferred task-type buckets:
  - `ppc_optimization`
  - `promotions`
  - `catalog_account_health`
  - `generic_operations` (fallback)
- If a request does not cleanly map to a bucket, runtime must use the generic unclassified fallback contract and ask targeted clarification before mutation when needed.
- Silent invention is prohibited: when evidence is weak, the assistant must ask for missing variables instead of fabricating execution details.

### 13.18 Entity Disambiguation Guardrails (v1)
- AgencyClaw must not guess product entities (for example ASIN/SKU) when user language is ambiguous.
- If entity-level precision is required for execution and identifiers are missing, runtime must ask focused clarification (for example: "Please provide ASIN(s), or confirm create with ASIN pending.").
- If user chooses to proceed without identifiers, task draft/body must include explicit unresolved fields:
  - `open_questions` (missing ASIN/SKU list),
  - `needs_clarification=true`,
  - first-step instruction to resolve identifiers before execution.
- While catalog lookup skill is not implemented, this clarify/pending pattern is mandatory for product-scoped mutations.

### 13.18.1 Catalog Lookup Contract Acceptance (C12C)
- C12C introduces a deterministic `catalog_lookup` skill contract for ASIN/SKU candidate resolution.
- Input contract requires `client_id` + `query`; supports optional `brand_id` and bounded `limit`.
- Output contract returns ranked `candidates[]` with:
  `asin`, `sku`, `title`, `confidence`, `match_reason`, plus `resolution_status`.
- `resolution_status` must be one of:
  - `exact`: one unambiguous exact identifier match,
  - `ambiguous`: candidates exist but no single unambiguous exact match,
  - `none`: no candidates.
- Matching/ranking order is locked:
  exact ASIN/SKU -> prefix ASIN/SKU -> token-contains title.
- Runtime acceptance rule:
  - no silent identifier guessing under any status,
  - `ambiguous` must force explicit user clarification before mutation,
  - `none` must force explicit ASIN/SKU input or explicit "identifier pending" confirmation path.

## 14. Failure And Compensation Design
For all multi-step actions:
- Return per-step status to requesting user in Slack.
- On partial failure, report what succeeded and what failed.
- Send escalation alert to super_admin on high-severity failure.
- Persist failure state in `agent_events` and `agent_tasks.last_error`.
- Slack error responses should include:
  concise failure summary, actionable next step, and `run_id` for audit/support lookup.

## 15. Phased Delivery Plan
### Phase 0: Core Foundations
- Add CSL role migration (`brand_manager` -> `customer_success_lead`).
- Add `agent_events`, `agent_tasks`, `threshold_rules`.
- Land `20260217000004_agent_core_tables.sql` for `agent_events`, `agent_tasks`, `threshold_rules`.
- Add idempotency store for Slack events.
- Define typed skill adapter interfaces.
- Wire runtime to `skill_catalog` + `skill_invocation_log`.
- Keep `skill_policy_overrides` available but non-blocking in v1 runtime path.
- Seed `skill_catalog` for all skills through Phase 2.6 (unimplemented rows disabled by default).
- Add durable Slack event/interactions dedupe store (`slack_event_receipts` or equivalent).
- Add `agent_runs` with `run_type` + `run_key` + optional `parent_run_id`.
- Enforce context isolation rules between interactive and heartbeat/ingestion runs.
- Implement atomic dedupe flow (`INSERT ... ON CONFLICT DO NOTHING RETURNING`) for Slack events/interactions.
- Implement Slack identity resolution path (`slack_user_id` -> `profiles.id`) before policy checks.
- Implement super_admin allowlist resolution and viewer restrictions in policy layer.
- Implement advisory-lock concurrency guard for mutation skills.
- Implement v1 self-confirmation protocol for channel mutations.
- Externalize orchestrator baseline instructions to a versioned file.
- Require AgencyClaw token telemetry writes to `ai_token_usage` for all LLM paths.
- Extract/centralize Debrief business logic for reuse.

### Phase 1: End-to-End Win (Slack Debrief)
- Slack message with meeting summary -> parsed tasks.
- Role resolution from Command Center mapping.
- Human self-confirmation where required by policy/confidence.
- ClickUp task creation + success/failure status in-thread.
- Add ClickUp idempotency key checks, retry/backoff policy, and orphan detection flow.
- Child-run execution path for multi-step debrief actions (non-blocking status updates).

### Phase 2: SOP Q&A
- OpenAI-based Q&A over curated SOP cache.
- Confidence-tiered responses and source citation.
- Gap flagging to admin workflow.
- Add `sop_lookup` + `sop_sync_run` skill paths.
- Land `meeting_parser` and `debrief_task_review` as testable standalone capabilities.

### Phase 2.4: Client Context Foundation
- Implement `client_context_builder` with fixed-budget context packs and observability metadata.
- Add deterministic context assembly tests and token-budget guardrails.

### Phase 2.5: Proactive Heartbeat MVP
- Introduce first scheduled proactive alert flow with isolated heartbeat runs.
- Add alert dedupe window + noise controls.
- Measure alert engagement and false-positive rate.
- Add `client_brief` generation as first proactive context artifact.

### Phase 2.6: Command Center Chat Parity
- Implement `cc_team_member_*` skills for employee lifecycle and identity mapping updates.
- Implement `cc_client_*` / `cc_brand_*` skills for client/brand CRUD parity.
- Implement `clickup_task_*` skills for weekly retrieval + task create/update in chat.
- Enforce brand backlog default routing and thin-task clarification workflow.
- Add brand ClickUp mapping audit + in-chat remediation skills.
- Add ClickUp space sync + classification flows (`brand_scoped` / `shared_service` / `unknown`).
- Add admin chat controls to classify spaces and map/unmap brand-scoped spaces.
- Add Slack/ClickUp user sync + reconciliation flows with `auto_match`, `new_profile`, and `needs_review` outcomes.
- Route `needs_review` cases to admin Slack confirmations with explicit in-chat decisions.
- Add audit coverage and channel confirmation rules for all admin mutations.
- Ship targeted prompts/playbooks for common ops commands (e.g., set Slack ID, set ClickUp ID, reassign role slot).
- Add brand-context resolution policy enforcement for shared-destination clients (destination routing vs brand disambiguation).

### Phase 2.7: Slack Conversational Orchestrator
- Add LLM-first DM routing that chooses `reply`, `clarify`, or `tool_call`.
- Integrate `client_context_builder` output into orchestrator prompts.
- Keep deterministic classifier as runtime fallback.
- Add integration tests for:
  natural-language weekly task retrieval,
  thin task creation clarification,
  fallback behavior on LLM/tool-plan failure.

### Phase 2.8: Jarvis Runtime Hardening
Execution order (locked):
1. Clarify-state continuity first:
   enforce pending-state continuity for mutation clarifications (no context-dropping loops).
2. Conversation buffer:
   add bounded recent-message context for orchestrator prompt input.
3. Actor/surface safety:
   add actor + surface context resolver and policy gate pipeline.
4. KB grounding:
   add retrieval cascade (SOP -> internal docs -> similar tasks -> external materials).
5. Planner de-hardcoding:
   reduce hardcoded intent branches by shifting to reusable capability skills + planner execution.
6. Preference memory:
   add lightweight durable user preference memory for defaults.
7. Brand-context hardening:
   enforce destination-vs-brand split with explicit disambiguation for ambiguous product-scoped requests.

Specific carve-out:
- Replace the hardcoded N-gram deterministic task creation branch with planner + capability-skill execution.
- Preserve behavior parity while removing intent-specific coupling from runtime routing.

### Phase 3: Threshold Automation
- Metric ingest.
- Rule evaluation.
- Task creation with duplicate suppression.

### Phase 4: Advanced Memory And External Knowledge
- Vector retrieval.
- External source ingestion (e.g. YouTube transcripts).
- Optional multi-agent decomposition.

## 16. Immediate Decisions Locked
- OpenAI-centric stack.
- Reuse existing FastAPI Slack integration.
- One orchestrator in v1, with extensible seams.
- Slack DM runtime is LLM-first conversational, with deterministic fallback retained for resilience.
- Slack-native Debrief is the first flagship workflow.
- Queue lanes are planned, but not mandatory for first release.
- v1 skill runtime depends on `skill_catalog` + `skill_invocation_log`; policy override enforcement is deferred.
- Session/run isolation is mandatory (`run_type` + `run_key`) before enabling proactive jobs.
- Durable Slack idempotency storage is mandatory (header-only dedupe is insufficient).
- Slack dedupe implementation is atomic insert-based (`ON CONFLICT DO NOTHING`), never select-then-insert.
- File-based orchestrator instruction source is adopted for tunability.
- Child runs are the first async scaling pattern; full sub-agents remain optional later.
- Command Center web parity via chat is a product requirement, not optional backlog.
- ClickUp task operations in chat must default to brand backlog routing and enforce mapping integrity checks.
- ClickUp create/update flows require idempotency keys, retry/backoff, and orphan detection.
- `client_context_builder` and `meeting_parser` are first-class skills and must not be implicit hidden logic.
- `client_context_builder` default budget is 4,000 tokens with deterministic truncation policy.
- `sprint_planner` is deferred until after context-builder + client-brief quality targets are met.
- AgencyClaw LLM token usage is logged to `ai_token_usage` with `tool='agencyclaw'` and stage-level attribution.
- Super-admin in v1 is resolved via allowlist config (`SUPER_ADMIN_PROFILE_IDS`), not DB enum.
- Viewer is a supported read-only role state for AgencyClaw policy checks.
- v1 confirmation model is self-confirmation only; admin-approval workflow is deferred.
- Required core table migration (`20260217000004_agent_core_tables.sql`) must exist before Phase 1.
- Inbound ClickUp webhook sync is out of scope for v1.
- Identity reconciliation supports `needs_review` admin confirmations in Slack with expiration + audit trail.
- ClickUp space registry/classification is required for safe brand backlog routing.
- Distributed cross-worker mutation lock (`C4D`) is deferred; current runtime uses per-worker in-memory guard + idempotency checks.
- Actor + surface context is mandatory for orchestrator policy decisions.
- Brand context is mandatory metadata for brand-scoped requests, but destination routing is resolved independently.
- Runtime must not silently guess a brand when multiple brand candidates exist for the same client.
- Mutation drafts should be source-grounded via KB retrieval cascade; silent invention is prohibited.
- Hardcoded single-intent branches are transitional; planner + capability-skill routing is the target runtime shape.
- C10 sequencing is impact-first: clarify continuity -> conversation buffer -> policy gate -> KB grounding -> de-hardcode -> preferences.
- Hardcoded N-gram deterministic branch is explicitly targeted for carve-out under planner de-hardcoding.
- Lightweight durable preference memory is in-scope before Phase 4 semantic memory.
- Runtime-vs-skill boundary is locked: runtime governs conversation/policy/confirmation, skills govern typed business execution.

---
Document version: 1.18
Last updated: 2026-02-20
