# Ecomlabs Tools ClickUp MCP Playbook

This file is historical reference for the older Ecomlabs Tools ClickUp MCP
surface.

## Goal

Use Claude's native ClickUp connector for team task work. Keep this file only
as historical reference for the older MCP-based ClickUp flow.

Current scope:

1. list tasks from the correct mapped client/brand backlog destination
2. inspect a specific ClickUp task from a task URL or task id
3. update an existing mapped ClickUp task
4. resolve natural-language assignee references against Agency OS team members
5. preview a task create payload before mutation
6. create a task in the correct mapped backlog destination

## Live Tools

### `resolve_client`

Use when the user provides a client name but not a canonical `client_id` for a
ClickUp request.

Input:

```json
{
  "query": "Whoosh"
}
```

Returns:

1. canonical `client_id`
2. canonical client name
3. brand rows with `clickup_list_id` / `clickup_space_id`
4. team assignment metadata
5. team-member `clickup_user_id` hints

### `list_clickup_tasks`

Use when the user wants to review the client backlog for a brand.

Input:

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

1. resolves the brand backlog destination from Agency OS mappings
2. fails closed if multiple mapped brands exist and `brand_id` is omitted
3. returns structured task rows from the resolved backlog destination

### `get_clickup_task`

Use when the user pastes a ClickUp task URL or gives a ClickUp task id.

Input:

```json
{
  "task_url": "https://app.clickup.com/t/86dzr5nhe"
}
```

Or:

```json
{
  "task_id": "86dzr5nhe"
}
```

Behavior:

1. fetches the specific task from ClickUp
2. only returns tasks that belong to mapped Agency OS brand backlog destinations
3. returns structured task metadata including status, assignees, and list/space
   context

### `resolve_team_member`

Use when the user refers to an assignee conversationally, such as `assign this
to Susie`.

Input:

```json
{
  "query": "Susie",
  "client_id": "uuid | optional",
  "brand_id": "uuid | optional"
}
```

Returns matches with:

1. `profile_id`
2. team-member name and email
3. `clickup_user_id`
4. assignment scope hints
5. `resolution_status`

### `update_clickup_task`

Use when the user wants to edit an existing ClickUp task that already exists.

Input:

```json
{
  "task_url": "https://app.clickup.com/t/86dzr5nhe",
  "title": "Updated title | optional",
  "description_md": "Updated markdown | optional",
  "assignee_profile_id": "uuid | optional",
  "assignee_query": "Susie | optional",
  "clear_assignees": false,
  "client_id": "uuid | optional",
  "brand_id": "uuid | optional"
}
```

Behavior:

1. fetches and scopes the task to mapped Agency OS destinations first
2. updates title, description, or assignee
3. allows conversational assignee updates through local team-member resolution
4. fails closed if the task is outside mapped destinations or assignee
   resolution is ambiguous

This is a mutating tool.

### `prepare_clickup_task`

Use before creation when the user wants to preview the final task payload or
when Claude should confirm the resolved destination/assignee before mutating.

Input:

```json
{
  "client_id": "uuid",
  "brand_id": "uuid | optional",
  "title": "Review Q2 plan",
  "description_md": "string | optional",
  "assignee_profile_id": "uuid | optional",
  "assignee_query": "string | optional"
}
```

Returns:

1. resolved destination metadata
2. resolved assignee metadata
3. final task payload
4. warnings such as missing assignee mapping

This is read-only.

### `create_clickup_task`

Use when the user explicitly wants the task created in ClickUp.

Input:

```json
{
  "client_id": "uuid",
  "brand_id": "uuid | optional",
  "title": "Review Q2 plan",
  "description_md": "string | optional",
  "assignee_profile_id": "uuid | optional",
  "assignee_query": "Susie | optional"
}
```

Returns:

1. `task_id`
2. `task_url`
3. resolved destination metadata
4. resolved assignee metadata

This is a mutating tool.

## Canonical Workflow

### 1. Client name given

If the user says:

- "Show me Whoosh ClickUp tasks"
- "Create a task for Basari CA"
- "Assign a task to Susie for Lifestyle"

then:

1. call `resolve_client`
2. if multiple matches are returned, ask the user to choose the right client
3. if one match is returned, continue using the canonical `client_id`
4. use the returned brand metadata when a brand clarification is needed

### 2. Backlog review request

If the user wants the current backlog for a client/brand:

1. resolve the client if needed
2. call `list_clickup_tasks`
3. if multiple mapped brands exist, clarify the brand instead of guessing
4. summarize the task list cleanly without exposing raw internal ids unless
   explicitly useful

### 3. Direct task inspection

If the user pastes a ClickUp task link or gives a task id:

1. call `get_clickup_task`
2. summarize the returned task directly
3. if the task is outside mapped Agency OS destinations, say so clearly

### 4. Conversational assignee resolution

If the user says things like:

- "Assign this to Susie"
- "Put Jeff on it"
- "Make this Billy's task"

then:

1. call `resolve_team_member`
2. use `client_id` and `brand_id` hints when available
3. if exactly one concrete match exists, continue with that resolved person
4. if multiple plausible matches remain, ask for clarification
5. do not invent or guess raw ClickUp user ids

### 5. Task creation

If the user wants a new ClickUp task:

1. resolve the client
2. resolve the brand when needed
3. resolve the assignee when needed
4. use `prepare_clickup_task` when preview/confirmation is useful
5. use `create_clickup_task` only when the user actually wants the task created
6. if assignment is ambiguous, fail closed and ask for clarification
7. if the assignee has no valid ClickUp mapping, keep the task unassigned and
   explain that clearly

### 6. Task editing

If the user wants to revise an existing task:

1. call `get_clickup_task` when you need to inspect the task first
2. call `update_clickup_task` when the user clearly wants the task changed
3. use `resolve_team_member` first when assignee intent is ambiguous
4. do not imply the task was edited unless `update_clickup_task` succeeds

## Working Rules

1. Prefer Agency OS mappings over memory or guesses for ClickUp routing.
2. Treat `create_clickup_task` and `update_clickup_task` as mutating actions.
3. Treat `prepare_clickup_task` as read-only preview, not creation.
4. Use `resolve_client` before backlog-task work when a canonical `client_id`
   is not already known.
5. Do not expose raw internal UUIDs in normal user-facing answers unless the
   user explicitly asks for identifiers or they are required to resolve
   ambiguity.
6. If the user pastes a ClickUp task URL, prefer `get_clickup_task` over asking
   for client or brand first.
7. If a task lookup is blocked because it is outside mapped destinations, say
   that explicitly instead of implying the task does not exist.
8. For creates, prefer `prepare_clickup_task` before `create_clickup_task` when
   there is any ambiguity about brand or assignee.
9. Do not imply a task was created unless `create_clickup_task` succeeded.

## Recommended Pilot Prompts

1. "Show me Whoosh ClickUp backlog tasks"
2. "Open this ClickUp task: https://app.clickup.com/t/86dzr5nhe"
3. "Create a ClickUp task for Lifestyle CA to review ad spend anomaly"
4. "Assign this to Susie"
5. "Update this ClickUp task title to 'Review CA ad spend anomaly today'"
6. "Preview the ClickUp task before creating it"
