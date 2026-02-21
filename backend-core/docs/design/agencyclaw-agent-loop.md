# AgencyClaw Agent Loop Redesign

**Status:** Draft
**Author:** Jeff + Claude + Codex
**Date:** 2026-02-21

## Problem Statement

AgencyClaw currently works but doesn't feel like talking to an AI assistant. It feels like talking to a command router. The root cause: **the LLM is used as a classifier, not as a brain.**

When a user says *"create a coupon code for Garlic Press for Thorinox"*, the system should:
1. Recognize "Garlic Press" as a product mention and "Thorinox" as a brand mention
2. Load brand/client context, destination mapping, and relevant SOPs
3. Search KB for coupon-related procedures
4. Synthesize everything into a natural response with a grounded task draft

Instead, today it either:
- Regex-matches "create task" and enters a rigid state machine, or
- Asks the LLM to output a JSON classifier result, then fires a skill handler the LLM never sees the results of

The user gets canned Slack messages, not intelligent conversation.

## Current Architecture (What Exists)

### The Two-Brain Problem

The system has two independent routing brains that run in sequence:

```
User message
  → Pending state machine (if awaiting input)    # Brain 0: hardcoded
  → LLM orchestrator (single-shot JSON)          # Brain 1: classifier
  → Regex classifier fallback                     # Brain 2: pattern match
  → Help text fallback
```

**Brain 0** (`slack_pending_flow.py`, `slack_interaction_runtime.py`): A hand-coded state machine with states `brand → title → confirm_or_details → asin_or_pending`. Runs BEFORE the LLM even sees the message. ~500 lines of if/elif chains that duplicate logic the LLM should own.

**Brain 1** (`slack_orchestrator.py`): Single-shot LLM call to gpt-4o (via `OPENAI_MODEL_PRIMARY`; code default is gpt-4o-mini but prod uses 4o). Outputs JSON with `mode: reply|clarify|tool_call|plan_request`. The LLM never sees skill execution results — the conversation buffer only records summaries like `"[Ran task list for Distex]"`, not the actual data.

**Brain 2** (`slack_helpers._classify_message`): ~250 lines of regex patterns. Runs as fallback when the LLM returns `mode: fallback`. Duplicates the LLM's job.

### What the LLM Can't Do Today

1. **No tool results**: When the LLM dispatches `clickup_task_list`, it never sees the tasks. The handler formats them into a canned Slack message directly. The LLM can't summarize, filter, or respond naturally to what it found.

2. **No context loading**: The LLM gets a thin `client_context_pack` string, but can't request more. It can't look up a client, search KB, or resolve a brand name on demand. These functions exist (`command_center_lookup.py`, `kb_retrieval.py`, `brand_context_resolver.py`, `client_context_builder.py`) but are called by deterministic code, not by the LLM.

3. **No multi-turn reasoning**: The conversation buffer stores 5 exchange summaries in ~1500 tokens. The LLM sees these as context but can't use them to build on prior tool results or maintain a coherent plan.

4. **No response generation from data**: Every user-facing message is a hardcoded format string. The LLM generates responses only in `mode: reply` (conversational), never from tool output data.

### Module Inventory (26 files, ~4500 LOC)

| Layer | Module | Lines | Role | Keep/Rework/Remove |
|-------|--------|-------|------|---------------------|
| **Routing** | `slack_dm_runtime.py` | 255 | Main DM router | **Rework** — simplify to: pending → agent loop |
| | `slack_orchestrator.py` | 264 | LLM classifier | **Rework** → becomes the agent loop core |
| | `slack_orchestrator_runtime.py` | 304 | Handles LLM results | **Remove** — absorbed into agent loop |
| | `slack_helpers.py` | ~600 | Regex classifier + formatters | **Remove** classifier; **keep** utility fns |
| | `slack_planner_runtime.py` | 129 | Multi-step planner runtime | **Rework** — becomes planner sub-agent loop |
| **State** | `slack_pending_flow.py` | ~500 | Pending state machine | **Remove** legacy FSM; keep thin confirmation helpers |
| | `slack_interaction_runtime.py` | 274 | Slack button callbacks | **Keep** — buttons are Slack-native |
| | `conversation_buffer.py` | ~120 | Exchange history | **Rework** — backed by run/message/event tables |
| | `playbook_session.py` | ~200 | Session CRUD | **Keep** as-is |
| | `preference_memory.py` | 119 | User prefs | **Keep** as-is |
| **Planning** | `planner.py` | 241 | Constrained planner | **Rework** — planner sub-agent contract + step generation |
| | `plan_executor.py` | 186 | Step executor | **Rework** — planner sub-agent execution loop with policy rails |
| | `skill_registry.py` | 343 | Skill schemas | **Rework** → becomes function definitions |
| | `policy_gate.py` | ~100 | Authorization | **Keep** as-is |
| **Context** | `client_context_builder.py` | ~200 | Token-budgeted packing | **Rework** → becomes a skill |
| | `brand_context_resolver.py` | 242 | Brand resolution | **Rework** → becomes a skill |
| | `kb_retrieval.py` | ~250 | 3-tier KB cascade | **Rework** → becomes a skill |
| | `grounded_task_draft.py` | ~300 | Deterministic draft builder | **Keep** — called by create_task skill |
| **Skills** | `slack_task_runtime.py` | 362 | Task creation | **Rework** → skill that returns data |
| | `slack_task_list_runtime.py` | 152 | Task listing | **Rework** → skill that returns data |
| | `slack_cc_dispatch.py` | ~400 | CC skill dispatch | **Rework** → individual skills |
| | `command_center_lookup.py` | 302 | CC read-only queries | **Keep** — backing logic for skills |
| | `brand_mapping_remediation.py` | 253 | Remediation logic | **Keep** — backing logic for skills |
| **Infra** | `openai_client.py` | ~150 | OpenAI HTTP adapter | **Rework** → support function calling API |
| | `clickup_reliability.py` | 201 | Retry/idempotency | **Keep** as-is |
| | `slack_runtime_deps.py` | 118 | DI containers | **Rework** — simplify |
| | Other (identity, catalog, space reg.) | ~450 | Supporting modules | **Keep** as-is |

## Proposed Architecture

### Core Idea: LLM as Primary Brain with Skills

Replace the three-brain routing system with a single agent loop where the LLM:
1. Reads the user message + conversation history + session context
2. Decides what skills to invoke (if any)
3. Sees skill results
4. Generates a natural response from the data

```
User message
  → Slack button callback? → handle_interaction_runtime (unchanged)
  → Pending confirmation?  → thin guard (see below)
  → Agent Loop:
      LLM sees: system prompt + conversation history + user message
      LLM can: invoke skills, see results, invoke more skills, respond
      LLM outputs: natural text response to user
```

### Skill Categories

#### Context-Loading Skills (read-only, no confirmation needed)

These let the LLM gather information before acting:

| Skill | Backing Module | Returns |
|-------|---------------|---------|
| `lookup_client` | `command_center_lookup.lookup_clients` | Client list with IDs |
| `lookup_brand` | `command_center_lookup.list_brands` | Brand list with mappings |
| `get_client_context` | `client_context_builder.build_client_context_pack` | Assignments, KPIs, SOPs, tasks |
| `search_kb` | `kb_retrieval.retrieve_kb_context` | SOPs, docs, similar tasks |
| `resolve_brand` | `brand_context_resolver.resolve_brand_context` | Brand + destination resolution |
| `list_tasks` | ClickUp API via `slack_task_list_runtime` logic | Task list data (JSON, not formatted) |
| `audit_brand_mappings` | `command_center_lookup.audit_brand_mappings` | Missing mapping report |

#### Mutation Skills (require confirmation gate)

| Skill | Backing Module | Side Effect |
|-------|---------------|-------------|
| `create_task` | `slack_task_runtime.execute_task_create_runtime` | Creates ClickUp task |
| `assign_person` | `slack_cc_dispatch` → assignment upsert | Updates client_assignments |
| `remove_assignment` | `slack_cc_dispatch` → assignment remove | Removes assignment |
| `create_brand` | `slack_cc_dispatch` → brand create | Inserts brand row |
| `update_brand` | `slack_cc_dispatch` → brand update | Updates brand row |
| `apply_remediation` | `brand_mapping_remediation.apply_*` | Bulk brand updates |

### The Agent Loop

```python
async def run_agent_loop(
    *,
    text: str,
    session: Session,
    channel: str,
    slack: SlackClient,
    max_turns: int = 6,
) -> str:
    """Run the LLM agent loop. Returns final response text."""

    messages = build_initial_messages(session, text)
    skills = build_skill_definitions()  # from skill_registry, reworked

    for turn in range(max_turns):
        response = await call_llm(messages, tools=skills)

        if response.has_tool_calls:
            skill_results = []
            for call in response.tool_calls:
                # Policy gate for mutations
                if is_mutation(call.skill_id):
                    policy = evaluate_skill_policy(...)
                    if not policy["allowed"]:
                        skill_results.append(error_result(policy["user_message"]))
                        continue

                result = await execute_skill(call)
                skill_results.append(result)

            messages.append(response)
            messages.append(skill_results_message(skill_results))
            continue

        # LLM chose to respond with text
        return response.text

    return "I ran into a limit processing that. Could you simplify?"
```

### What Changes

**Removed entirely:**
- `_classify_message` regex classifier — LLM handles all intent recognition
- most of `slack_pending_flow.py` state machine — replaced by natural conversation + thin confirmation guard
- `slack_orchestrator_runtime.py` — no separate "handle LLM result" layer
- Canned format strings for responses — LLM generates from data

**Kept as-is:**
- `slack_interaction_runtime.py` — Slack buttons are platform callbacks, not conversation
- `policy_gate.py` — authorization checks still gate mutations
- `clickup_reliability.py` — idempotency/retry/orphan detection unchanged
- `preference_memory.py` — user prefs still durable
- `playbook_session.py` — session CRUD unchanged
- `identity_reconciliation.py` / `identity_sync_runtime.py` — not in hot path
- `clickup_space_registry.py` — admin utility, unchanged

**Reworked:**
- `slack_orchestrator.py` → `agent_loop.py`: From single-shot classifier to multi-turn skill-use loop
- `planner.py` + `plan_executor.py` + `slack_planner_runtime.py`: Retained as planner sub-agent with its own loop and explicit report-back contract
- `openai_client.py`: Add function calling support (OpenAI tools API)
- `skill_registry.py`: Convert to OpenAI function definition format
- `conversation_buffer.py`: Rework to load from persistent conversation/event tables
- `slack_dm_runtime.py`: Simplify to: interaction callback → thin pending guard → agent loop → post response
- `slack_task_runtime.py` / `slack_task_list_runtime.py`: Refactor to return data (not post Slack messages)
- `slack_cc_dispatch.py`: Break into individual skill handlers that return data

### Thin Pending Guard (Not a State Machine)

The current pending flow is a 500-line state machine. Most of it goes away because the LLM naturally tracks multi-turn conversation. But two things remain as thin guards:

1. **Confirmation guard**: Mutations may be confirmed by either natural language (e.g. "yes, create it") or Slack buttons. Buttons remain optional UX accelerators. For either path, store a simple `pending_confirmation` payload with expiry and idempotency key.

2. **Idempotency**: The `clickup_reliability.py` duplicate check and inflight lock remain. These protect against double-creates regardless of whether the LLM or a button triggered the action.

The LLM handles everything else: asking for missing info, resolving ambiguity, and continuing naturally across turns.

### Conversation History & Storage

**Today:** `conversation_buffer.py` stores a list of `{user, assistant}` pairs in the session context JSONB column (`playbook_sessions.context → recent_exchanges`). 5 exchanges max, 1500 token budget. The "assistant" side is usually a summary string like `"[Ran task list for Distex]"` — not the actual response or skill results. No dedicated table, no queryability, no debugging visibility.

**Proposed — dedicated conversation + run/event tables (details in appendix):**

```sql
create table agent_runs (...);
create table agent_messages (...);
create table agent_skill_events (...);
```

Benefits:
- Full audit trail of every conversation turn, including skill invocations and their results
- Parent/child run visibility (main agent run + planner sub-agent runs)
- Queryable — "show me all conversations where create_task was called" is a simple SQL query
- Debuggable — when something goes wrong, look at the exact message history
- Eviction moves to a query: load last N rows by session_id, with a token budget cap
- Session context JSONB no longer grows unboundedly with conversation data

The agent loop loads recent history from these tables at the start of each turn, and appends new entries (user message, skill calls, skill results, final response) at the end. Token budget stays configurable (~8000 tokens for the main loop, with smaller sub-agent windows).

Eviction: FIFO with priority — skill results evict before user messages.

### ASIN Handling

Today: The pending flow has a special `asin_or_pending` state where it prompts the user for ASINs if the task text contains product keywords but no identifiers.

Proposed: The LLM handles this naturally. `_extract_product_identifiers` becomes a utility the `create_task` skill calls internally. If the task text mentions products but has no ASINs, the LLM can ask — because it sees the task context and KB results. No special state needed.

Note: There's no catalog lookup data source yet (`catalog_lookup_contract.py` defines types but no implementation). ASINs come from user input only.

### KB/SOP Integration

Today: `kb_retrieval.py` runs before task creation, results feed into `grounded_task_draft.py` which builds a structured description. The LLM never sees any of this.

Proposed: `search_kb` is a skill the LLM invokes when it recognizes a task might benefit from SOP context. The LLM sees the retrieval results (SOP content, similar tasks, internal docs) and can:
- Incorporate SOP steps into a task description
- Reference specific procedures in its response
- Ask the user if a particular SOP applies

`grounded_task_draft.py` remains available as a utility the `create_task` skill can call to build structured descriptions from KB results.

## Migration Strategy

### Phase 1: Skill-Use Foundation
- Add function calling support to `openai_client.py`
- Convert `skill_registry.py` to OpenAI function definition format
- Build `agent_loop.py` with basic skill dispatch
- Create `agent_runs` + `agent_messages` + `agent_skill_events` tables
- Create skill wrappers that return data (not post to Slack)

### Phase 2: Context Skills
- Wire up read-only skills: `lookup_client`, `lookup_brand`, `search_kb`, `get_client_context`, `list_tasks`
- Read policy can run in permissive mode initially (single-user dev), then enforced in a hardening pass
- Agent loop handles all read-only queries

### Phase 3: Planner Sub-Agent Loop
- Rework planner as internal sub-agent:
  - planner can run multi-step skill loops
  - planner writes its own run/messages/events
  - planner returns structured report to main agent
- Main agent can iterate (feedback → another planner run) before user-facing response

### Phase 4: Mutation Skills + Confirmation
- Wire up mutation skills with policy gate
- Implement natural-language + button confirmation path for mutations
- Keep thin pending guard only for confirmation payload + expiry + replay safety

### Phase 5: Remove Legacy
- Remove regex classifier
- Remove legacy pending state machine
- Remove orchestrator runtime
- Simplify DM runtime to: buttons → agent loop

### Feature Flag

Each phase is gated by `AGENCYCLAW_AGENT_LOOP_ENABLED` (default off). The existing `AGENCYCLAW_LLM_DM_ORCHESTRATOR` flag continues to control the current system. When the agent loop flag is on, it takes priority. Both paths coexist until Phase 5.

## Model Choice

Current: `gpt-4o` (via `OPENAI_MODEL_PRIMARY` env var).

Continue with `gpt-4o` for the agent loop. Already wired up via `openai_client.py`. The agent loop makes more calls per conversation but don't worry about cost optimization yet — get it working first, optimize later. Token budget is generous during development.

Model is swappable later — the agent loop design is model-agnostic as long as the provider supports function calling. The current token telemetry infrastructure (`log_ai_token_usage`) carries over unchanged.

## Decisions

1. **Max turns per message**:
   - Main agent loop: 6
   - Planner sub-agent loop: 6 (independent budget)

2. **Streaming**: Yes — post an initial "thinking" message, then `chat.update` with the final response. This shows the bot as actively typing in Slack. Implement in Phase 1 as part of the agent loop response posting.

3. **Skill call visibility**: No. Users don't need to see which skills were invoked. The agent just responds naturally.

4. **Confirmation UX**: Natural-language confirmation can execute mutations. Buttons are optional accelerators, not required.

5. **Create-task grounding**: `create_task` uses SOP/KB grounding (`grounded_task_draft.py`) by default when relevant.

6. **Fallback policy**: On agent-loop failure, prefer full conversational fallback (LLM-generated), not deterministic regex routing for business intents.

7. **Planner position**: Planner is retained as an internal sub-agent (not user-facing). Main agent remains the sole direct user interface.

8. **Sequential execution (lane queue)**: Process events serially per session/lane to prevent race conditions (e.g., double-pings causing duplicate creates). Different sessions can still run concurrently.

9. **History retention policy**: Do not blindly evict all skill results from model context. Keep compact summaries in-window, store full payloads in DB, and allow explicit rehydration when users ask follow-ups.

10. **Client memory**: Add client-scoped durable notes so important client facts can be recalled across conversations and loaded with client context.

## Appendix A: Runtime Contract (Main Agent + Planner Sub-Agent)

### Main Agent Contract

**Input**
- `session_id`
- `user_message`
- `channel_id`
- `active_client_id` (optional)

**Behavior**
1. Acquire per-session lane lock (serial execution in that lane)
2. Load recent conversation context
3. Call LLM with skill definitions
4. If LLM emits skill calls:
   - execute skills
   - append skill results
   - continue loop
5. If LLM emits `delegate_planner`:
   - invoke planner sub-agent run
   - append planner report
   - continue loop
6. Return final natural-language assistant response
7. Release lane lock

**Output**
- `assistant_text`
- `run_id`
- `status` (`completed|needs_clarification|failed`)

### Planner Sub-Agent Contract

**Input**
- `parent_run_id`
- `planner_request_text`
- scoped context snapshot from main agent

**Behavior**
1. Planner runs its own LLM loop with planner-specific system prompt
2. Planner may call skills repeatedly (policy-gated)
3. Planner produces structured report:
   - `summary`
   - `actions_taken[]`
   - `evidence[]`
   - `open_questions[]`
   - `confidence`
4. Report is returned to main agent (not directly to end user)
5. Main agent may provide feedback and launch a subsequent planner run (new child run) before responding to user

**Output**
- `planner_report` JSON
- `planner_run_id`
- `status` (`completed|blocked|failed`)

## Appendix B: Proposed Storage Schema

```sql
create table if not exists public.agent_runs (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.playbook_sessions(id) on delete cascade,
  parent_run_id uuid references public.agent_runs(id) on delete cascade,
  trace_id uuid not null default gen_random_uuid(),
  run_type text not null check (run_type in ('main', 'planner')),
  status text not null check (status in ('running', 'completed', 'blocked', 'failed')),
  started_at timestamptz not null default now(),
  completed_at timestamptz
);

create index if not exists idx_agent_runs_session_started
  on public.agent_runs(session_id, started_at desc);
create index if not exists idx_agent_runs_trace
  on public.agent_runs(trace_id);

create table if not exists public.agent_messages (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references public.agent_runs(id) on delete cascade,
  role text not null check (role in ('user', 'assistant', 'system', 'planner_report')),
  content jsonb not null,
  summary text,
  created_at timestamptz not null default now()
);

create index if not exists idx_agent_messages_run_created
  on public.agent_messages(run_id, created_at);

create table if not exists public.agent_skill_events (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references public.agent_runs(id) on delete cascade,
  event_type text not null check (event_type in ('skill_call', 'skill_result')),
  skill_id text not null,
  payload jsonb not null,
  payload_summary text,
  created_at timestamptz not null default now()
);

create index if not exists idx_agent_skill_events_run_created
  on public.agent_skill_events(run_id, created_at);
```

### Storage Notes
- `content` and `payload` use JSONB so structured tool IO can be preserved exactly.
- Keep `playbook_sessions.context` for lightweight runtime state only (active client, pending confirmation token, etc.).
- Read/retention/RLS hardening can be applied in follow-up once multi-user rollout begins.
- For large skill results, store full `payload` in DB but keep concise `payload_summary` in prompt context.
- Add a small rehydration skill (e.g., `load_prior_skill_result`) so the agent can reload full prior evidence on demand.

## Appendix C: Confirmation Payload Contract

Store a lightweight `pending_confirmation` object in `playbook_sessions.context`:

```json
{
  "run_id": "uuid",
  "trace_id": "uuid",
  "skill_id": "create_task",
  "args": {"client_id": "...", "task_title": "..."},
  "proposal_fingerprint": "sha256(skill_id + normalized_args + actor_id + created_at)",
  "expires_at": "2026-02-21T23:59:59Z",
  "actor_profile_id": "uuid"
}
```

Rules:
- Natural-language confirmation and button confirmation both must match `proposal_fingerprint`.
- Reject stale/mismatched confirmations with a natural re-prompt.
- Keep deterministic idempotency checks for mutation execution.

## Appendix D: Safety Rails That Stay Deterministic

- Policy checks for all mutation skills
- Idempotency/replay protection for task mutations
- Slack signature verification + interaction dedupe
- Pending confirmation token validation (expiry + actor match)
- Per-session lane queue serialization

Everything else (intent recognition, clarification language, response phrasing, multi-turn steering) is owned by the LLM loops.

## Appendix E: Client Memory (Durable Notes)

Client memory is a scoped, durable note system loaded with client context.

Use cases:
- Key client preferences ("Distex prefers concise task titles")
- Stable operational facts ("Reporting Specials space is shared-service")
- Meeting-derived facts worth remembering beyond one chat

Proposed schema:

```sql
create table if not exists public.client_memory_notes (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.agency_clients(id) on delete cascade,
  author_profile_id uuid references public.profiles(id) on delete set null,
  source text not null check (source in ('chat', 'meeting', 'manual')),
  note text not null,
  confidence numeric(3,2) not null default 0.70,
  tags text[] not null default '{}',
  created_at timestamptz not null default now(),
  archived_at timestamptz
);

create index if not exists idx_client_memory_client_created
  on public.client_memory_notes(client_id, created_at desc);
```

Memory policy:
- Load top recent/high-confidence notes as part of `get_client_context`.
- Only persist notes when confidence threshold is met and note is client-relevant.
- Avoid auto-persisting volatile or speculative statements.
- Allow explicit user correction ("forget that", "update memory for client X...").
