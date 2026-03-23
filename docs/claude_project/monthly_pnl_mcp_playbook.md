# Agency OS Monthly P&L MCP Playbook

This file is the compact reference Claude should use for the live Monthly P&L
tool surface.

## Goal

Use Agency OS as the source of truth for Monthly P&L workflows inside Claude.

Current scope:

1. inspect Monthly P&L by client, marketplace, and month window
2. summarize profitability and key cost drivers
3. surface missing-data or quality warnings
4. build a structured, read-only Monthly P&L email brief for a client/month
5. generate a persisted Monthly P&L client email draft when explicitly asked

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

### `get_monthly_pnl_email_brief`

Use when the user wants a structured Monthly P&L highlights brief for a
specific client and report month, especially as preparation for future
client-facing drafting.

Input:

```json
{
  "client_id": "uuid",
  "report_month": "2026-02-01",
  "marketplace_codes": ["US", "CA"],
  "comparison_mode": "auto"
}
```

Optional `comparison_mode` values:

1. `auto`
2. `yoy_only`
3. `mom_only`

Returns:

1. client metadata
2. selected marketplace sections
3. snapshot metrics
4. broader component metrics
5. positive and negative driver candidates
6. financial health verdict
7. data quality notes

This is a read-only tool.

### `draft_monthly_pnl_email`

Use when the user explicitly wants a Monthly P&L client email draft for a given
client and report month.

Input:

```json
{
  "client_id": "uuid",
  "report_month": "2026-02-01",
  "marketplace_codes": ["US", "CA"],
  "comparison_mode": "auto",
  "recipient_name": "Billy"
}
```

Optional fields:

1. `marketplace_codes`
2. `comparison_mode`
3. `recipient_name`
4. `sender_name`
5. `sender_role`
6. `agency_name`

Returns:

1. `draft_id`
2. draft metadata
3. subject
4. body

This is a mutating tool.

## Important note about YoY

There is not currently a dedicated Monthly P&L YoY MCP tool.

That is expected.

1. The web app has a true YoY mode backed by shared backend comparison logic.
2. Claude currently does YoY reasoning by using existing P&L tool output.
3. If a dedicated YoY MCP tool is added later, it should be a thin wrapper over
   the same shared comparison layer rather than a separate logic path.

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
3. lead with the most material profitability outcome in the selected month
   window
4. if the data clearly supports a same-period prior-year comparison, use YoY
   framing
5. if YoY is not clearly available, fall back cleanly to sequential or
   descriptive analysis instead of forcing a YoY claim
6. surface warnings when they materially affect interpretation
7. do not invent numbers not present in the tool output
8. do not expose raw internal UUIDs in normal user-facing answers unless the
   user explicitly asks for them

### 4. Normal P&L inspection flow

If the user wants to inspect the P&L before asking for any client-facing draft:

1. stay in the read-only flow
2. answer directly from `get_monthly_pnl_report`
3. do not redirect the user toward an email workflow unless they ask for it

### 5. Structured P&L email-prep flow

If the user asks for monthly highlights prep, a structured email brief, or the
best data-backed setup for later drafting:

1. resolve the client
2. confirm the report month
3. call `get_monthly_pnl_email_brief`
4. present the structured takeaways cleanly
5. do not imply a persisted P&L draft was created

### 6. Monthly P&L email draft request

If the user explicitly wants the client-facing Monthly P&L email:

1. resolve the client
2. confirm the report month
3. call `draft_monthly_pnl_email`
4. present the returned draft cleanly
5. if the user wants revisions, revise in chat while staying faithful to the
   Agency OS data and the returned draft

## Working Rules

1. Prefer Agency OS data over memory or guesses for Monthly P&L questions.
2. Ask for the smallest possible clarification when ambiguity remains.
3. Use canonical IDs after resolution is complete.
4. If no client, no profile, or no reportable data is found, say so explicitly.
5. Treat warnings as decision-relevant context, not footnotes to ignore.
6. Do not imply Claude can edit P&L settings, upload imports, or trigger other
   write workflows unless new tools are added later. Exception:
   `draft_monthly_pnl_email` is a supported mutating draft tool.
7. If the user asks for last month, a specific month, or a recent month window,
   treat that as a normal analysis request, not an email-drafting request.
8. When summarizing P&L, prioritize:
   - net revenue direction
   - net earnings / margin quality
   - material cost drivers
   - material warnings

## Recommended Pilot Prompts

1. "Show me Whoosh US Monthly P&L for last month."
2. "Summarize Whoosh Canada P&L for Jan-Feb 2026."
3. "Draft the Monthly P&L highlights email for Whoosh for February 2026."
3. "What were the main profitability drivers for Distex CA over the last 6 months?"
4. "Do we have Monthly P&L coverage for Whoosh in the UK?"
5. "Build a structured Monthly P&L email brief for Whoosh for February 2026."
6. "Draft the Monthly P&L highlights email for Whoosh for February 2026."
