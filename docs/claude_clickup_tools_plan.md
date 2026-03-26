# Claude ClickUp Tools Plan

_Drafted: 2026-03-25 (ET)_

Status: `implemented — Slice 0–4 complete as of 2026-03-25`

Slice 0–4 are merged and tested. All five MCP tools are live on the shared
Agency OS pilot surface: `list_clickup_tasks`, `get_clickup_task`,
`resolve_team_member`, `prepare_clickup_task`, `create_clickup_task`.
`get_clickup_task` now scopes fetches to mapped Agency OS brand destinations
(Slice 4 workspace guard). Remaining open items (task update/close/move,
idempotency persistence) are tracked in the opportunity backlog.

## Purpose

Define the implementation plan for making a safe, useful ClickUp tool belt
available to the shared Agency OS Claude / MCP surface.

This plan is intentionally narrower than "full ClickUp inside Claude."

The target is:

1. list tasks from the correct client/brand backlog destination
2. inspect an explicitly linked ClickUp task directly from a task URL or task
   id
3. resolve assignees from natural-language team-member references
4. prepare a new task in the correct destination
5. create the task safely
6. optionally assign a mapped team member

This is not a plan for broad ClickUp admin workflows, space management, or
replacing the app UI.

## Why this is a separate plan

Relevant foundations already exist, but they do not yet add up to a real
Claude-facing ClickUp tool surface:

1. shared ClickUp API client:
   - `backend-core/app/services/clickup.py`
2. admin-only Team Hours reporting:
   - `backend-core/app/services/clickup_team_hours.py`
   - `backend-core/app/routers/admin.py`
3. existing generic task-create backend route:
   - `backend-core/app/routers/clickup.py`
4. existing app-side ClickUp task creation from Debrief:
   - `frontend-web/src/app/api/debrief/tasks/[taskId]/send-to-clickup/route.ts`
   - `frontend-web/src/app/api/debrief/meetings/[meetingId]/send-to-clickup/route.ts`
5. existing MCP client discovery:
   - `backend-core/app/mcp/tools/clients.py`

Current constraint:

1. the MCP server currently exposes client tools, WBR tools, and Monthly P&L
   tools only
2. there is no real ClickUp MCP tool file or registration yet

## Current confirmed repo state

### Shared ClickUp client

The existing `ClickUpService` already supports:

1. listing spaces
2. fetching workspace time entries
3. listing tasks within a ClickUp list
4. creating tasks in a ClickUp list
5. creating tasks in a ClickUp space by resolving a default list

Important implementation caveats in the current code:

1. `resolve_default_list_id()` should not be treated as safe per-brand
   destination resolution when `CLICKUP_DEFAULT_LIST_ID` is set globally
2. assignee IDs are normalized as integers in the ClickUp service layer, so
   malformed `clickup_user_id` values can otherwise be silently dropped
3. the shared ClickUp API token is environment-backed and represents one
   service account / shared account, not the actual end user invoking Claude

### Command Center as source of truth

The durable local mappings already live in Command Center tables:

1. `brands.clickup_list_id`
2. `brands.clickup_space_id`
3. `profiles.clickup_user_id`
4. `client_assignments`

That means the right backend behavior is not "ask ClickUp where things should
go." The right behavior is:

1. resolve client / brand / team member from Agency OS data first
2. use ClickUp only as the execution system

### Team Hours relevance

Team Hours proves the shared ClickUp client and Command Center mapping model
are workable together, but it is a read-only reporting flow.

It does this:

1. fetch raw time entries from ClickUp
2. map them back onto local `profiles` and `brands`

Claude ClickUp tools need the inverse flow:

1. resolve local `client` / `brand` / `team member`
2. derive the correct ClickUp destination and assignee
3. call ClickUp for read or create actions

### Existing gaps

1. the generic `/clickup/tasks` route accepts raw `list_id` / `space_id`
   directly from the caller, which is too permissive for a Claude tool
2. there is no first-class MCP ClickUp tool module
3. the existing helper that picks a brand destination for a client is too
   permissive for general Claude use because it can silently choose one mapped
   brand when multiple exist

## Product decision

### Home

Put this on the shared Agency OS MCP surface, not in The Claw runtime and not
as a frontend-only feature.

### V1 framing

Treat this as a "client backlog ClickUp tool belt."

That means:

1. destination scope is the mapped brand backlog destination
2. task listing is about the resolved backlog destination, not arbitrary
   workspace-wide search
3. task creation is about the resolved backlog destination, not arbitrary
   raw list IDs

### V1 non-goals

1. no space classification management from Claude
2. no broad task update / close / move flows yet
3. no ClickUp doc search
4. no cross-workspace admin tooling
5. no replacing Command Center setup flows

## Core safety rules

These are the most important design rules for the implementation.

### Rule 1: Command Center owns routing

Claude-facing task tools must never accept raw ClickUp `space_id` or `list_id`
as user-controlled inputs.

Instead:

1. resolve the target client and brand from local data
2. read `brands.clickup_list_id` and `brands.clickup_space_id`
3. derive the ClickUp destination internally

### Rule 2: fail closed on ambiguity

Do not silently choose a destination when:

1. multiple mapped brands match the request
2. a client has multiple candidate brand destinations and the user did not
   specify which one they want
3. the brand has no mapped destination

Return a structured clarification/error instead.

### Rule 3: assignees must map locally

Assignment should only be allowed when the selected team member has a unique,
mapped `profiles.clickup_user_id`.

If not:

1. keep the task unassigned, or
2. fail with explicit guidance, depending on the tool mode

Do not let Claude guess raw ClickUp assignee IDs.

However, because the target product shape is a Jarvis-like conversational
assistant rather than a form-driven tool belt:

1. v1 should support natural-language assignee references such as `assign this
   to Susie` or `put Jeff on it`
2. the agent should understand those references in context and call the right
   resolution tools rather than depending on regex-style command parsing
3. those references must be resolved against Agency OS team-member data first
4. ambiguity should fail closed with a clarification prompt
5. the conversational input can be natural language, but the execution path
   must still resolve to one concrete local profile before any ClickUp
   mutation happens

Before passing any assignee value into the ClickUp client:

1. validate that `clickup_user_id` is a non-empty integer string
2. if not, treat it as `missing_mapping`
3. do not rely on the lower ClickUp client layer to silently coerce or drop
   invalid values

### Rule 4: prepare before create

For mutation safety, the first implementation should expose a read-only
"prepare" step before creation.

That step should:

1. resolve the destination
2. resolve the assignee
3. show the final payload that would be sent
4. surface warnings before any mutation happens

Important:

1. in v1 this is a prompt-layer and tool-usage convention, not a hard
   server-side constraint
2. `create_clickup_task` should still be safe when called directly without a
   prior `prepare_clickup_task`

### Rule 5: log every mutation

All successful or failed mutation attempts should log:

1. MCP tool name
2. Agency OS user id
3. client / brand / destination ids
4. assignee resolution outcome
5. success / failure
6. returned ClickUp task id and URL when successful

Use the same named `key=value` logging style already established in MCP tools
such as `_log_tool_outcome` so mutation logs are grep-able by:

1. tool name
2. client / brand ids
3. destination ids
4. ClickUp task id
5. invoking user id

Normal structured backend logging is enough for v1 unless a stronger mutation
audit table is clearly needed.

## V1 tool inventory

## Existing tool reused as-is

### `resolve_client`

Keep using the existing MCP `resolve_client` tool as the first resolver.

Why:

1. it already returns brand rows with `clickup_space_id` / `clickup_list_id`
2. it already returns team assignment hints and `clickup_user_id` metadata
3. it already fits the shared Claude surface

## New ClickUp MCP tools

### 1. `list_clickup_tasks`

Purpose:

1. list tasks from the resolved brand backlog destination

Input shape:

```json
{
  "client_id": "uuid",
  "brand_id": "uuid | optional",
  "updated_since_days": 14,
  "include_closed": false,
  "limit": 50
}
```

Behavior:

1. if `brand_id` is provided, use that brand only
2. if `brand_id` is omitted:
   - use the sole mapped brand if exactly one exists
   - otherwise fail closed and require brand clarification
3. prefer `clickup_list_id`
4. if only `clickup_space_id` exists:
   - resolve the default list from the live lists in that specific space
   - clearly label the returned destination as a resolved fallback list
5. read tasks from that resolved list only
6. return structured task data plus destination metadata
7. interpret `updated_since_days` relative to `now` in UTC and convert to
   `date_updated_gt` in Unix milliseconds
8. treat `limit` as a hard maximum number of tasks returned and a hard cap on
   how far pagination will continue

Explicit v1 scope note:

1. subtasks are out of scope for this tool
2. the initial implementation should keep `subtasks=false`

Output shape:

```json
{
  "client_id": "uuid",
  "brand_id": "uuid",
  "brand_name": "string",
  "destination": {
    "space_id": "string | null",
    "list_id": "string",
    "resolution_basis": "mapped_list | mapped_space_default_list"
  },
  "tasks": [
    {
      "id": "string",
      "name": "string",
      "status": "string | null",
      "url": "string | null",
      "assignees": ["string"],
      "date_updated": "string | null",
      "date_created": "string | null"
    }
  ]
}
```

### 2. `get_clickup_task`

Purpose:

1. inspect one specific ClickUp task when the user provides a task URL or task
   id

Why this should be explicit in the plan:

1. it is one of the most natural real-world Claude workflows
2. it avoids forcing users to resolve a client and list backlog tasks when
   they already have the exact task link
3. it is read-only, so it is a high-value low-risk part of the ClickUp MCP
   expansion

Input shape:

```json
{
  "task_id": "string | optional",
  "task_url": "string | optional"
}
```

Behavior:

1. require exactly one of `task_id` or `task_url`
2. if `task_url` is provided, parse the ClickUp task id from the URL first
3. fetch the task from ClickUp using a backend read helper
4. return structured task data, including destination/location metadata when
   available
5. if the URL is malformed or the task cannot be found, return a structured
   error

Accepted v1 inputs:

1. bare task ids
2. `https://app.clickup.com/t/{task_id}`

Do not attempt to parse broader ClickUp URL shapes in the first slice.

Explicit scope note:

1. this tool has no workspace scope guard in the Jeff-only pilot
2. before broader team rollout, add a guard that verifies the returned task's
   list or space maps to an allowed Command Center destination

Output shape:

```json
{
  "task": {
    "id": "string",
    "name": "string",
    "url": "string | null",
    "description_md": "string | null",
    "status": "string | null",
    "assignees": ["string"],
    "date_created": "string | null",
    "date_updated": "string | null",
    "list_id": "string | null",
    "list_name": "string | null",
    "space_id": "string | null",
    "space_name": "string | null"
  }
}
```

Implementation note:

1. the shared ClickUp service does not currently expose a task-by-id read
   helper, so this plan includes adding one
2. URL parsing should live in the backend helper layer, not in the MCP tool
   wrapper
3. missing ClickUp configuration should return a structured
   `configuration_error` response rather than an opaque 500

### 3. `resolve_team_member`

Purpose:

1. resolve a natural-language assignee reference to one concrete Agency OS
   team member before task creation

Why this belongs in v1:

1. the intended product shape is conversational, not form-driven
2. forcing users to provide `assignee_profile_id` manually would be the wrong
   UX for the shared Claude surface
3. a read-only assignee resolver preserves conversational feel without giving
   up safety
4. this supports the broader Agency OS / The Claw philosophy that the model
   should understand the request and call the right tool, not rely on brittle
   command syntax

Input shape:

```json
{
  "query": "string",
  "client_id": "uuid | optional",
  "brand_id": "uuid | optional"
}
```

Behavior:

1. the agent may call this tool after interpreting natural conversational
   language such as `assign this to Susie on the CA side`
2. resolve the query against Command Center team-member records
3. use client / brand assignment hints when available to improve ranking and
   reduce ambiguity
4. return one concrete match when confidence is sufficient
5. fail closed when multiple candidates remain plausible
6. return `clickup_user_id` status so Claude can tell whether assignment is
   actually possible

Output shape:

```json
{
  "matches": [
    {
      "profile_id": "uuid",
      "team_member_name": "string",
      "team_member_email": "string | null",
      "clickup_user_id": "string | null",
      "assignment_scope": "client | brand | none | mixed",
      "resolution_status": "resolved | ambiguous | missing_mapping"
    }
  ]
}
```

### 4. `prepare_clickup_task`

Purpose:

1. dry-run task creation without mutating ClickUp

Input shape:

```json
{
  "client_id": "uuid",
  "brand_id": "uuid | optional",
  "title": "string",
  "description_md": "string | optional",
  "assignee_profile_id": "uuid | optional",
  "assignee_query": "string | optional"
}
```

Behavior:

1. resolve the exact destination using the same rules as `list_clickup_tasks`
2. resolve the assignee from either:
   - `assignee_profile_id` when already known, or
   - `assignee_query` via team-member resolution
3. return warnings for:
   - missing brand clarification
   - unmapped destination
   - unmapped assignee
   - ambiguous assignment
4. return the final mutation-ready payload without creating anything

Output shape:

```json
{
  "client_id": "uuid",
  "brand_id": "uuid",
  "brand_name": "string",
  "destination": {
    "space_id": "string | null",
    "list_id": "string",
    "resolution_basis": "mapped_list | mapped_space_default_list"
  },
  "assignee": {
    "profile_id": "uuid | null",
    "clickup_user_id": "string | null",
    "resolution_status": "resolved | unassigned | ambiguous | missing_mapping"
  },
  "task_payload": {
    "name": "string",
    "description_md": "string | null",
    "assignee_ids": ["string"]
  },
  "warnings": ["string"]
}
```

### 5. `create_clickup_task`

Purpose:

1. create a task in the resolved destination

Input shape:

```json
{
  "client_id": "uuid",
  "brand_id": "uuid | optional",
  "title": "string",
  "description_md": "string | optional",
  "assignee_profile_id": "uuid | optional",
  "assignee_query": "string | optional"
}
```

Behavior:

1. use the same destination and assignee resolution rules as
   `prepare_clickup_task`
2. fail closed on missing or ambiguous destination
3. allow unassigned creates only when the destination is fully resolved
4. return ClickUp task id and URL
5. emit mutation logs

Explicit v1 mutation stance:

1. v1 does not guarantee idempotent task creation
2. if Claude or the operator retries a successful create call, duplicate
   ClickUp tasks may be created
3. this is acceptable for the initial pilot only if it is documented clearly
4. revisit with a real idempotency key or persistence guard if duplicate-task
   pain appears in practice

Output shape:

```json
{
  "task_id": "string",
  "task_url": "string | null",
  "client_id": "uuid",
  "brand_id": "uuid",
  "destination": {
    "space_id": "string | null",
    "list_id": "string"
  },
  "assignee": {
    "profile_id": "uuid | null",
    "clickup_user_id": "string | null",
    "resolution_status": "resolved | unassigned"
  }
}
```

## Destination resolution rules

Implement destination resolution in one shared backend service, not separately
inside each MCP tool.

### Resolution order

1. explicit `brand_id` if provided
2. otherwise, sole mapped brand under the client if exactly one exists
3. otherwise, fail closed

### ClickUp destination order

1. if `brands.clickup_list_id` exists, use it directly
2. else if `brands.clickup_space_id` exists, resolve the default list from the
   actual lists in that specific space
3. else fail with a mapping error

Important implementation note:

1. do not delegate per-brand fallback resolution to
   `ClickUpService.resolve_default_list_id()`
2. that method currently has a global `default_list_id` shortcut and is not a
   safe source of truth for per-space brand routing when a global default list
   is configured
3. the new resolver should call the space-lists lookup path directly

Operational warning:

1. `clickup_space_id`-only routing is inherently dependent on live ClickUp
   workspace state
2. if the expected fallback list is renamed, reordered, or removed, the
   resolved destination can drift
3. long term, explicit `clickup_list_id` is safer than `clickup_space_id`-only
   routing

### Why not accept client-only silent fallback

Because a client can have:

1. multiple brands
2. multiple ClickUp backlog destinations
3. shared-service spaces that should not be used as a brand backlog

The safe behavior is explicitness, not convenience-by-guessing.

## Assignee resolution rules

Implement assignee resolution in one shared backend helper.

### V1 input rule

The mutating tools should accept conversational assignee intent while still
resolving to one concrete local profile before mutation.

Reason:

1. the target assistant experience is natural-language-first
2. the agent should infer intent from normal conversation and then call
   explicit resolution tools
3. deterministic local resolution still preserves safety after that
4. Command Center remains the source of truth for team-member mappings
5. raw ClickUp user IDs should still never be user inputs

Recommended v1 contract:

1. support `assignee_query` for conversational usage
2. let the agent decide when to call `resolve_team_member` based on natural
   language in the conversation
3. also allow `assignee_profile_id` when a prior tool call has already
   resolved the person explicitly

### V1 assignee behavior

1. if both `assignee_query` and `assignee_profile_id` are omitted, create
   unassigned
2. if `assignee_profile_id` is provided, use it directly after validation
3. if `assignee_query` is provided, resolve it against team-member records
4. if the resolved profile has a unique integer-shaped `clickup_user_id`,
   assign it
5. if no `clickup_user_id` exists, fail with a mapping error in prepare/create
6. if local data implies ambiguity, fail closed and require clarification

Initial stance on assignment scope:

1. v1 does not require the assignee to already be assigned to the target brand
   in Command Center
2. if that constraint becomes operationally important later, add it as a
   stricter policy rather than assuming it now

Implementation note:

1. the read-only `resolve_team_member` tool should ship early enough that
   Claude can preserve conversational behavior while still using explicit
   local resolution under the hood

## Backend organization rules

The MCP layer should stay thin, matching the current MCP architecture.

### New files

1. `backend-core/app/mcp/tools/clickup.py`
   - MCP tool definitions only
2. `backend-core/app/services/clickup_task_tools.py`
   - shared read/create orchestration for Claude-facing ClickUp tools
3. optional:
   - `backend-core/app/services/clickup_destination_resolver.py`
   - `backend-core/app/services/clickup_assignee_resolver.py`
   if the orchestration file starts getting too large

### Files to reuse

1. `backend-core/app/services/clickup.py`
2. `backend-core/app/mcp/tools/clients.py`
3. `backend-core/app/services/playbook_session.py`
   - as a reference only, not as the final silent-selection policy
4. `frontend-web/src/app/api/debrief/tasks/[taskId]/send-to-clickup/route.ts`
   - as a reference for destination and assignee lookup flow

Reuse caveat:

1. do not blindly inherit every behavior from the current ClickUp service
   helpers
2. the new MCP-facing orchestration layer must explicitly correct for
   per-space list-resolution and assignee-validation gaps

### Avoid

1. calling the backend HTTP `/clickup/tasks` route from MCP
2. duplicating resolution logic in multiple tool wrappers
3. exposing raw ClickUp ids as Claude-facing tool inputs

## Recommended implementation slices

## Slice 0: backend helper foundation

Goal:

1. build destination and assignee resolution helpers that support
   conversational tool-calling safely

Why this is split from Slice 1:

1. it isolates the policy decisions and edge-case tests before any new MCP
   tools are registered
2. the read-only MCP tools should sit on top of already-proven resolver logic,
   not define that logic implicitly as they are built

Work:

1. add a shared resolver for brand destination lookup
2. add a shared resolver for assignee profile lookup
3. encode fail-closed ambiguity rules
4. add task-id / task-URL parsing helpers
5. add unit tests for the resolver layer

Done when:

1. one helper can resolve a brand destination safely
2. one helper can resolve an assignee safely
3. ambiguous and unmapped cases are explicitly covered by tests

## Slice 1: read-only task list MCP tool

Goal:

1. ship the first safe read-only ClickUp tools first

Work:

1. add `backend-core/app/mcp/tools/clickup.py`
2. register it in `backend-core/app/mcp/server.py`
3. implement `list_clickup_tasks`
4. implement `get_clickup_task`
5. implement `resolve_team_member`
6. add structured result formatting
7. add Claude manual smoke test coverage

Done when:

1. Claude can resolve a client, then list tasks from the correct mapped
   backlog destination
2. Claude can inspect a directly linked ClickUp task from a task URL or task
   id
3. Claude can resolve a natural-language assignee reference to one concrete
   team member or fail closed on ambiguity
4. ambiguous client/brand cases fail with clear guidance

## Slice 2: prepare-create mutation flow

Goal:

1. ship safe task creation with explicit preview behavior

Work:

1. implement `prepare_clickup_task`
2. implement `create_clickup_task`
3. add mutation logging
4. ensure response always includes direct ClickUp URL after success

Done when:

1. Claude can preview a task payload without mutation
2. Claude can create a task in the correct destination
3. wrong or missing mappings fail closed

## Slice 3: polish and rollout hardening

Goal:

1. make the tool belt reliable enough for regular use

Work:

1. tighten error text for operator clarity
2. add more explicit destination metadata in outputs
3. document prompt usage in the Claude project bundle
4. decide whether a `resolve_team_member` tool is still needed

## Test plan

### Unit tests

1. destination resolution:
   - single mapped brand
   - multiple mapped brands
   - no mapped brands
   - mapped list id
   - mapped space with default-list fallback
   - mapped space resolution bypasses any global default-list shortcut
   - missing lists in a mapped space fail cleanly
2. assignee resolution:
   - mapped profile
   - natural-language query resolves to one profile
   - natural-language query remains ambiguous and fails closed
   - missing `clickup_user_id`
   - malformed non-integer `clickup_user_id`
   - invalid profile id
3. ClickUp task listing service:
   - query params passed correctly
   - `updated_since_days` converts from UTC-relative days into epoch ms
   - limit handling
   - include/exclude closed tasks
4. ClickUp task creation service:
   - create in explicit list
   - create via resolved default list
   - invalid assignee mapping fails before the ClickUp client call
5. direct task lookup:
   - bare task id accepted
   - `https://app.clickup.com/t/{task_id}` accepted
   - valid task URL parsing
   - invalid task URL rejection
   - task fetch by id
   - task fetch by parsed URL id

### MCP / integration tests

1. MCP server registration includes new ClickUp tools
2. `list_clickup_tasks` returns structured task rows
3. `get_clickup_task` returns structured task data from id or URL input
4. `resolve_team_member` returns a concrete team-member match or a structured
   ambiguity result
5. `prepare_clickup_task` returns preview payload and warnings
6. `create_clickup_task` returns task id and URL
7. ambiguous destination cases fail closed

### Manual smoke tests

1. resolve client -> list tasks for a mapped brand
2. paste a ClickUp task URL -> inspect the exact task
3. ask naturally for an assignee such as `assign this to Susie` and verify
   Claude resolves the correct team member or asks a clarifying question
4. resolve client -> prepare task for a mapped brand
5. resolve client -> create task for a mapped brand
6. create task with mapped assignee
7. create task for a client with multiple brands and verify Claude must
   clarify rather than guessing

## Acceptance criteria

This plan is complete when:

1. Agency OS MCP exposes a real ClickUp tool file and registration
2. Claude can list backlog tasks for a correctly resolved brand
3. Claude can inspect a specific ClickUp task from a direct task URL or task
   id
4. Claude can resolve natural-language assignee references into one concrete
   local team member or fail closed on ambiguity
5. Claude can preview a task creation payload safely
6. Claude can create a task in the correct destination
7. assignment works only through mapped `profiles.clickup_user_id`
8. no tool accepts raw destination ids from the user
9. ambiguous destination selection fails closed
10. invalid assignee mappings fail explicitly instead of silently dropping
    assignment

## Open questions

### 1. Read semantics when only `clickup_space_id` exists

Recommended v1 behavior:

1. resolve a fallback list from the live lists in that specific space and make
   that basis explicit in the result

Reason:

1. it matches the intended brand-level fallback behavior
2. it keeps the tool focused on the backlog destination, not all lists in a
   space

If that proves confusing in practice, tighten the rule later so read tools
require explicit `clickup_list_id`.

### 2. Should natural-language assignee lookup be in v1?

Recommended answer:

1. yes

Reason:

1. the target product shape is a Jarvis-like conversational assistant, not a
   rigid form flow
2. requiring users to provide `assignee_profile_id` manually would break that
   interaction model
3. the correct compromise is conversational input plus explicit local tool
   resolution after the model understands intent

Implementation stance:

1. ship a read-only `resolve_team_member` tool in v1
2. allow mutation tools to accept either `assignee_query` or an already
   resolved `assignee_profile_id`
3. let the agent infer when team-member resolution is needed from normal
   conversation, not from regex-style control syntax
4. fail closed when multiple candidates remain plausible

### 3. Should task update / close ship in the same tranche?

Recommended answer:

1. no

Create the smallest safe read + create surface first.

### 4. What identity will ClickUp show as the task creator?

Recommended answer:

1. the shared ClickUp token owner / service account, not the Claude end user

Implication:

1. operator-facing logs in Agency OS must carry the real invoking user id
2. do not expect native ClickUp "created by" metadata to act as the primary
   audit trail for Claude actions

### 5. Should team rollout keep `get_clickup_task` workspace-wide?

Recommended answer:

1. no

For the Jeff-only pilot, any valid task URL may be readable. Before team
rollout, restrict task lookup to spaces or lists that map to allowed Agency OS
destinations.

## Suggested next step

Build Slice 0 and Slice 1 first:

1. shared destination / assignee resolver
2. `list_clickup_tasks`
3. `get_clickup_task`
4. `resolve_team_member`

That gives a real Claude ClickUp foothold without taking mutation risk on the
first commit.
