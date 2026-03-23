# Agency OS Monthly P&L MCP Playbook

This file is the compact reference Claude should use for the first Monthly P&L
tool slice.

## Goal

Use Agency OS as the source of truth for read-only Monthly P&L workflows inside
Claude.

## Live Tools

### `resolve_client`

Use when the user provides a client name but not a canonical `client_id` for a
Monthly P&L request.

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

### `list_monthly_pnl_profiles`

Use after client resolution when the correct marketplace/profile is not yet
known.

Input:

```json
{
  "client_id": "uuid"
}
```

Returns reportable Monthly P&L profiles with:

1. `profile_id`
2. `marketplace_code`
3. `currency_code`
4. first and last active month
5. active month count

### `get_monthly_pnl_report`

Use when the user asks for Monthly P&L performance, profitability analysis, or
month-window report summaries.

Input:

```json
{
  "profile_id": "uuid",
  "filter_mode": "last_3"
}
```

Optional `filter_mode` values:

1. `ytd`
2. `last_3`
3. `last_6`
4. `last_12`
5. `last_year`
6. `range` with `start_month` and `end_month` as `YYYY-MM-01`

Returns:

1. profile metadata
2. month list
3. line items
4. warnings

This is a read-only tool.

## Canonical Workflow

### 1. Client name given

If the user says:

- "Show me Whoosh US Monthly P&L"
- "How profitable was Distex CA over the last 6 months?"
- "Summarize Whoosh Canada P&L for Jan-Feb 2026"

then:

1. call `resolve_client`
2. if multiple matches are returned, ask the user to choose the right client
3. if one match is returned, continue using the canonical `client_id`

### 2. Client resolved, marketplace not yet resolved

If the user asks a marketplace-specific P&L question and the correct profile is
not already known:

1. call `list_monthly_pnl_profiles`
2. choose the matching `marketplace_code`
3. use the returned canonical `profile_id`

### 3. Monthly P&L analysis request

For read-only P&L questions:

1. call `get_monthly_pnl_report`
2. summarize the returned line items in business language
3. do not invent numbers not present in the tool output
4. surface warnings when they materially affect interpretation
5. do not expose raw internal UUIDs in normal user-facing answers unless the
   user explicitly asks for them

## Working Rules

1. Prefer Agency OS data over memory or guesses for Monthly P&L questions.
2. Ask for the smallest possible clarification when ambiguity remains.
3. Use canonical IDs after resolution is complete.
4. If no client, no profile, or no reportable data is found, say so explicitly.
5. Treat warnings as decision-relevant context, not footnotes to ignore.
6. This tool slice is read-only. Do not imply Claude can edit P&L settings,
   upload imports, or trigger write workflows unless new tools are added later.
