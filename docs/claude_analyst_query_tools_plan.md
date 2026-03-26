# Claude Analyst Query Tools Plan

_Drafted: 2026-03-26 (ET)_

## Purpose

Define the next MCP expansion tranche that lets Claude answer ad hoc internal
business questions from Agency OS data in a Jarvis-like way without exposing a
raw unrestricted database client.

This plan is intentionally narrower than:

1. "full SQL in Claude"
2. "one tool for every possible reporting question"
3. "let the model improvise directly on production tables"

The target is:

1. natural-language analyst questions from Claude web
2. compact, business-shaped read-only tools
3. a guarded analyst-query layer for flexible drill-down
4. safe rollout that matches how WBR, Monthly P&L, and ClickUp tools were
   introduced

## Product framing

This is a direct extension of the current Agency OS Claude philosophy:

1. the user speaks naturally
2. Claude chooses the right tools
3. backend services enforce business logic and safety
4. Claude synthesizes the answer in business language

This is consistent with the current "Jarvis-like" direction.

It is **not** a form-driven reporting surface and **not** a raw SQL console.

## Why this needs a separate plan

Current Agency OS MCP tools are strong for:

1. WBR summary retrieval
2. Monthly P&L analysis and drafting
3. ClickUp task workflows

But they are still weak for ad hoc analyst questions like:

1. "Did these promo ASINs sell well yesterday?"
2. "What products make up this WBR row?"
3. "Which campaigns spent the most last week?"
4. "Is this data even fresh yet?"
5. "What was our best keyword last week for Whoosh?" (later, after STR ingest)

Today those questions often require:

1. manual SQL
2. backend engineer lookup
3. a one-off Supabase query outside Claude

That is exactly the gap this plan is meant to close.

## Core product decision

Do **not** make the first version a raw SQL tool.

Do **not** add dozens of tiny one-off tools either.

The right shape is a hybrid:

1. domain tools for common high-value questions
2. a few guarded analyst-query tools for flexible drill-down
3. backend services that own validation, allowlists, limits, and logging

## Architecture stance

### Avoid

1. a backend LLM that translates English to SQL for Claude
2. a raw unrestricted SQL tool on the MCP surface
3. direct model access to arbitrary production tables
4. table-shaped tool names like `query_wbr_business_asin_daily`

### Prefer

1. business-shaped tool names
2. read-only backend service orchestration
3. parameterized query construction in backend code
4. curated reporting views or explicitly allowed fact tables only
5. shaped outputs with row/time/result limits

## Current data surfaces that are most useful

These are the first-class domains worth surfacing.

### 1. WBR business facts

Useful for:

1. ASIN performance windows
2. unit sales and sales breakdowns
3. row composition / row membership
4. freshness and source availability questions

Primary inputs:

1. `wbr_business_asin_daily`
2. `wbr_profile_child_asins`
3. `wbr_asin_row_map`
4. `wbr_rows`
5. `wbr_sync_runs`

### 2. WBR ads facts

Useful for:

1. campaign performance windows
2. spend / sales / orders drivers
3. mapped vs unmapped campaign QA
4. ad-type breakdowns

Primary inputs:

1. `wbr_ads_campaign_daily`
2. `wbr_pacvue_campaign_map`
3. `wbr_campaign_exclusions`
4. `wbr_sync_runs`

### 3. Monthly P&L

Useful for:

1. month/detail drill-down
2. why-margin-changed questions
3. category / ledger detail explanations

Primary inputs:

1. existing Monthly P&L report builder
2. import-month coverage metadata
3. ledger detail tables already used by the report layer

### 4. Catalog context

Useful for:

1. product/title/category lookup
2. row composition
3. later AI recommendation work

Primary inputs:

1. `wbr_profile_child_asins`
2. later richer catalog context layer from the search-term automation plan

### 5. Search-term data later

Useful for:

1. keyword ranking
2. wasted-spend questions
3. negative candidate analysis

This belongs in a later wave, after STR ingestion exists.

## Core safety rules

### Rule 1: read-only only

The analyst-query tranche is read-only.

No writes, no DDL, no mutation side effects.

### Rule 2: business-shaped first

If a common question can be answered by a narrow business tool, build that
instead of forcing everything through one generic query tool.

### Rule 3: no raw unrestricted SQL

Claude should not receive a top-level tool that accepts arbitrary SQL text
against the production database.

### Rule 4: backend owns query safety

The backend layer must enforce:

1. allowed data surfaces
2. parameter validation
3. max date window
4. max row count
5. timeout behavior
6. logging

### Rule 5: explain freshness

Analyst tools must surface enough freshness metadata that Claude can explain
when the answer might be incomplete because of source/report lag.

### Rule 6: prefer deterministic construction

For v1, the backend should construct the query plan deterministically from
validated parameters.

Do not add a second LLM in the backend just to convert English into SQL.

## Proposed tool model

The first implementation should have two layers:

### Layer A: narrow high-value tools

These answer common strategist questions cleanly.

Suggested v1 tools:

1. `get_asin_sales_window`
2. `get_campaign_performance_window`
3. `list_child_asins_for_row`
4. `get_sync_freshness_status`

### Layer B: guarded analyst-query tools

These handle ad hoc drill-down without exploding the top-level tool count.

Suggested v1 tools:

1. `query_business_facts`
2. `query_ads_facts`
3. `query_catalog_context`
4. `query_monthly_pnl_detail`

## Proposed v1 tool set

### 1. `get_asin_sales_window`

Purpose:

1. answer questions about one or more child ASINs over a date window

Typical asks:

1. "Did these ASINs sell well yesterday?"
2. "How did these promo ASINs do in the last 14 days?"

Suggested input:

```json
{
  "profile_id": "uuid",
  "child_asins": ["B07...", "B08..."],
  "date_from": "YYYY-MM-DD",
  "date_to": "YYYY-MM-DD",
  "include_latest_available": true
}
```

Suggested output:

1. per-ASIN totals
2. latest available date
3. optional latest daily row
4. freshness note when the requested end date has no landed source row

### 2. `get_campaign_performance_window`

Purpose:

1. answer questions about campaign performance over a date window

Typical asks:

1. "Which campaigns spent the most last week?"
2. "How did this group of campaigns perform?"

Suggested input:

```json
{
  "profile_id": "uuid",
  "campaign_names": ["optional"],
  "date_from": "YYYY-MM-DD",
  "date_to": "YYYY-MM-DD",
  "campaign_types": ["optional"]
}
```

Suggested output:

1. campaign totals
2. spend / sales / orders / clicks / impressions
3. mapping status if relevant
4. latest ads sync freshness

### 3. `list_child_asins_for_row`

Purpose:

1. answer row-composition questions

Typical asks:

1. "What child ASINs make up this WBR row?"
2. "Which products are counted in this line?"

Suggested input:

```json
{
  "profile_id": "uuid",
  "row_id": "uuid"
}
```

Suggested output:

1. mapped child ASINs
2. titles / SKU / category
3. exclusion status if relevant

### 4. `get_sync_freshness_status`

Purpose:

1. answer whether a profile’s data is up to date enough for analysis

Typical asks:

1. "Is this data current?"
2. "Why is yesterday missing?"

Suggested input:

```json
{
  "profile_id": "uuid"
}
```

Suggested output:

1. latest business source date
2. latest ads source date
3. latest successful sync times
4. warnings about expected source lag

### 5. `query_business_facts`

Purpose:

1. flexible but bounded business-fact drill-down

Suggested input shape:

```json
{
  "profile_id": "uuid",
  "group_by": "day|child_asin|row",
  "date_from": "YYYY-MM-DD",
  "date_to": "YYYY-MM-DD",
  "child_asins": ["optional"],
  "row_ids": ["optional"],
  "limit": 100
}
```

Suggested output:

1. grouped metric rows
2. totals
3. freshness metadata

### 6. `query_ads_facts`

Purpose:

1. flexible but bounded ads drill-down

Suggested input shape:

```json
{
  "profile_id": "uuid",
  "group_by": "day|campaign|campaign_type",
  "date_from": "YYYY-MM-DD",
  "date_to": "YYYY-MM-DD",
  "campaign_names": ["optional"],
  "campaign_types": ["optional"],
  "limit": 100
}
```

### 7. `query_catalog_context`

Purpose:

1. answer product/title/catalog questions for mapped child ASINs

Typical asks:

1. "What products are in this client’s MX catalog?"
2. "Show me the titles for these ASINs."

### 8. `query_monthly_pnl_detail`

Purpose:

1. bounded P&L drill-down for analyst questions that exceed the current report
   tools

Typical asks:

1. "What were the biggest non-COGS expenses last month?"
2. "Why is margin down?"

## Output design rules

Outputs should stay structured and compact.

Each tool should return:

1. requested data rows
2. a small summary block
3. freshness metadata when relevant
4. warnings when relevant

Avoid:

1. dumping raw database rows when a shaped response will do
2. very wide tables
3. huge payloads without limits

## Tool budget fit

This plan is intentionally aligned with the current tool-budget analysis.

Recommended additions from this plan:

1. 4 narrow tools
2. 4 guarded analyst tools

Estimated added budget:

1. about `1.4K` tokens across the tool belt

That keeps Agency OS in the currently recommended safe expansion range.

## Code organization rules

Follow the same MCP organization pattern already used in the repo.

### Required structure

1. `backend-core/app/mcp/tools/analyst.py`
   - tool definitions only
2. `backend-core/app/services/analyst_query_tools.py`
   - orchestration, validation, query construction
3. optional small helper module for shared freshness/status logic if needed

### Avoid

1. embedding business logic in MCP wrappers
2. copying report logic into the tool file
3. querying arbitrary tables directly from wrapper functions

## Rollout slices

### Slice 0: foundation

Goal:

1. create the shared analyst-query service layer
2. define common validation, limits, and logging
3. build freshness helpers

Scope:

1. backend service module
2. shared result envelope
3. shared error model
4. unit tests

### Slice 1: narrow high-value tools

Goal:

1. ship the highest-ROI read tools first

Scope:

1. `get_asin_sales_window`
2. `list_child_asins_for_row`
3. `get_sync_freshness_status`
4. MCP registration
5. focused tests

### Slice 2: flexible analyst layer

Goal:

1. ship bounded drill-down without exploding tool count

Scope:

1. `query_business_facts`
2. `query_ads_facts`
3. `query_catalog_context`
4. `query_monthly_pnl_detail`
5. focused tests

### Slice 3: polish and project guidance

Goal:

1. make the tools easy for Claude to use correctly

Scope:

1. refine tool descriptions
2. add Claude Project playbook guidance
3. add smoke-test prompts
4. update docs/handoffs

### Later slice: STR extension

Only after STR ingestion ships.

Scope:

1. `query_search_term_facts`
2. optional `rank_search_terms`

## Testing expectations

At minimum:

1. service-layer validation tests
2. grouped-query tests
3. freshness/lag explanation tests
4. MCP wrapper tests for structured success and structured error
5. smoke tests using real-like profile inputs where practical

## Acceptance criteria

This plan is successful when:

1. Claude can answer common analyst questions without a human writing SQL
2. the top-level tool count remains compact
3. answers include freshness caveats when source data is incomplete
4. the tool layer stays read-only and auditable
5. the surface feels Jarvis-like, not form-like

## Explicit non-goals

1. raw SQL tool for Claude
2. mutation workflows in the analyst-query tranche
3. replacing existing WBR/P&L summary tools
4. adding STR tools before STR ingestion exists
5. one tool per every imaginable question

## Recommended next move

The first concrete implementation should be:

1. Slice 0
2. Slice 1

That means:

1. shared analyst-query service
2. `get_asin_sales_window`
3. `list_child_asins_for_row`
4. `get_sync_freshness_status`

Those three tools alone would already cover a meaningful percentage of the ad
hoc questions Jeff is currently checking manually.
