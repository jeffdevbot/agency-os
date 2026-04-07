# Ecomlabs Tools WBR MCP Playbook

This file is the compact reference Claude should use for the current Ecomlabs Tools
pilot.

## Goal

Use Ecomlabs Tools as the source of truth for WBR workflows inside Claude.

## Live Tools

### `resolve_client`

Use when the user provides a client name but not a canonical `client_id`.

Input:

```json
{
  "query": "Whoosh"
}
```

Returns:

1. canonical `client_id`
2. canonical client name
3. active WBR marketplaces
4. active Monthly P&L marketplaces
5. brand / ClickUp setup hints
6. team assignment metadata
7. client context fields

### `list_wbr_profiles`

Use after client resolution when the correct marketplace/profile is not yet
known.

Input:

```json
{
  "client_id": "uuid"
}
```

Returns active WBR profiles with:

1. `profile_id`
2. `display_name`
3. `marketplace_code`

### `get_wbr_summary`

Use when the user asks how a client/profile performed in a marketplace or asks
for a WBR analysis.

Input:

```json
{
  "profile_id": "uuid"
}
```

Returns:

1. profile metadata
2. snapshot metadata
3. WBR digest payload

### `draft_wbr_email`

Use only when the user wants a weekly client email draft.

Input:

```json
{
  "client_id": "uuid"
}
```

Returns a persisted draft object with:

1. `draft_id`
2. `subject`
3. `body`
4. snapshot references

This is a mutating tool.

## Canonical Workflow

### 1. Client name given

If the user says:

- "Find the client Whoosh"
- "How did Basari do in MX last week?"
- "Draft the weekly WBR email for Whoosh"

then:

1. call `resolve_client`
2. if multiple matches are returned, ask the user to choose the right client
3. if one match is returned, continue using the canonical `client_id`
4. use the returned WBR and Monthly P&L coverage metadata when it helps route
   follow-up questions

### 2. Client resolved, marketplace not yet resolved

If the user asks a marketplace-specific WBR question and the correct profile is
not already known:

1. call `list_wbr_profiles`
2. choose the matching `marketplace_code`
3. use the returned canonical `profile_id`

### 3. WBR analysis request

For performance questions:

1. call `get_wbr_summary`
2. summarize the returned digest in business language
3. do not invent numbers not present in the tool output
4. do not expose raw internal UUIDs in the normal user-facing answer unless the
   user explicitly asks for them

### 4. Weekly email draft request

For weekly email drafting:

1. ensure the client is canonically resolved
2. call `draft_wbr_email`
3. present the returned draft cleanly
4. if the user wants revisions, revise in chat but stay faithful to the draft
   and Ecomlabs Tools data
5. do not surface the persisted `draft_id` unless the user explicitly asks for
   it

## Working Rules

1. Prefer Ecomlabs Tools data over memory or guesses.
2. Ask for the smallest possible clarification when ambiguity remains.
3. Use canonical IDs after resolution is complete.
4. If no client, no profile, or no data is found, say so explicitly.
5. Treat uploaded external files as supplementary context, not a replacement
   for Ecomlabs Tools internal WBR data.
6. In normal user-facing answers, prefer client names and marketplace labels
   over internal IDs.

## Recommended Pilot Prompts

1. "Find the client Whoosh"
2. "What WBR marketplaces exist for Whoosh?"
3. "How did Basari do in MX last week?"
4. "Draft the weekly WBR email for Whoosh"
