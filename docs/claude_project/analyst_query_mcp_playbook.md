# Ecomlabs Tools Analyst Query MCP Playbook

This file is the compact reference Claude should use for the live Ecomlabs Tools
analyst-query tool surface.

## Goal

Use Ecomlabs Tools as the source of truth for ad hoc internal reporting questions
inside Claude.

Current scope:

1. answer narrow ASIN sales-window questions
2. explain what products make up a WBR row
3. explain whether WBR business / ads data is current
4. drill into business facts with bounded grouping
5. drill into ads facts with bounded grouping
6. answer bounded STR keyword and search-term ranking questions
7. return compact catalog context for ASINs or WBR rows
8. drill into Monthly P&L detail for a bounded period

## Live Tools

### `get_asin_sales_window`

Use for narrow ASIN performance questions such as:

1. "How much of this ASIN did we sell last Tuesday?"
2. "How many units did these three ASINs sell last week?"

Input:

```json
{
  "profile_id": "uuid",
  "child_asins": ["B07BVZ4TN7"],
  "date_from": "2026-03-10",
  "date_to": "2026-03-16"
}
```

Returns:

1. per-ASIN units, sales, and page views for the requested window
2. freshness metadata
3. per-ASIN latest available snapshots when the requested end date exceeds
   landed data

Use this before `query_business_facts` when the user is asking for a direct
ASIN-window answer rather than a breakdown.

### `list_child_asins_for_row`

Use when the user asks what products make up a WBR row.

Input:

```json
{
  "profile_id": "uuid",
  "row_id": "uuid"
}
```

Returns:

1. mapped child ASINs
2. title / SKU / category
3. `scope_status`
4. exclusion reason when applicable
5. whether the row was resolved directly or through descendant leaves

### `get_sync_freshness_status`

Use when the user asks whether WBR business or ads data is current, or why a
date appears missing.

Input:

```json
{
  "profile_id": "uuid"
}
```

Returns:

1. latest successful Windsor business sync
2. latest successful Amazon Ads sync
3. latest landed business and ads fact dates
4. marketplace code
5. warnings when data may be incomplete or stale

### `query_business_facts`

Use for bounded WBR business drill-down when the user wants a breakdown rather
than a single ASIN-window answer.

Input:

```json
{
  "profile_id": "uuid",
  "date_from": "2026-03-10",
  "date_to": "2026-03-16",
  "group_by": "child_asin",
  "row_id": "uuid",
  "metrics": ["unit_sales", "sales"]
}
```

Allowed `group_by` values:

1. `day`
2. `child_asin`
3. `row`

Use for questions like:

1. "Show me units and sales by day for this row"
2. "Break out these ASINs by child ASIN last week"

### `query_ads_facts`

Use for bounded Amazon Ads drill-down.

Input:

```json
{
  "profile_id": "uuid",
  "date_from": "2026-03-10",
  "date_to": "2026-03-16",
  "group_by": "campaign"
}
```

Allowed `group_by` values:

1. `day`
2. `campaign`
3. `campaign_type`
4. `row`

Use for questions like:

1. "Which campaigns spent the most last week?"
2. "Show campaign spend and sales for this row"

### `query_search_term_facts`

Use for bounded STR keyword or search-term ranking questions.

Input:

```json
{
  "profile_id": "uuid",
  "date_from": "2026-03-01",
  "date_to": "2026-03-31",
  "group_by": "keyword",
  "sort_by": "spend",
  "limit": 10,
  "ad_product": "SPONSORED_PRODUCTS"
}
```

Allowed `group_by` values:

1. `day`
2. `search_term`
3. `keyword`
4. `campaign`
5. `keyword_type`

Allowed `sort_by` values:

1. `spend`
2. `sales`
3. `orders`
4. `clicks`
5. `impressions`
6. `acos`
7. `roas`
8. `ctr`
9. `cvr`
10. `cpc`

Use for questions like:

1. "What were Whoosh's top 10 keywords last month?"
2. "What search terms spent the most for this profile?"
3. "Show the best Sponsored Brands search terms by ROAS"

Important:

1. `keyword` means the Amazon targeting keyword, not the customer search term
2. `search_term` means the customer query that actually triggered the ad
3. prefer `group_by="keyword"` only when the user explicitly asks about keywords
4. prefer `group_by="search_term"` when the user asks what customers searched

### `query_catalog_context`

Use for compact product context questions.

Input:

```json
{
  "profile_id": "uuid",
  "row_id": "uuid"
}
```

Returns:

1. `child_asin`
2. `parent_asin`
3. SKU
4. product / parent title
5. category
6. size
7. style
8. fulfillment method

### `query_monthly_pnl_detail`

Use for bounded Monthly P&L detail questions.

Input:

```json
{
  "profile_id": "uuid",
  "month_from": "2026-01",
  "month_to": "2026-02",
  "group_by": "line_item",
  "section": "expenses"
}
```

Allowed `group_by` values:

1. `line_item`
2. `month`

Use for questions like:

1. "What were the biggest expense lines this month?"
2. "Show me net revenue, gross profit, expenses, and net earnings by month"

Important:

1. `section` is only meaningful with `group_by="line_item"`
2. when `group_by="month"`, the tool returns canonical summary lines by month

## Canonical Workflow

### 1. Narrow lookup first

If the user asks for one ASIN and one date window:

1. resolve the client if needed
2. resolve the WBR profile if needed
3. prefer `get_asin_sales_window`

### 2. Flexible breakdown second

If the user asks for a grouping, comparison, or row-level drill-down:

1. use `query_business_facts` for Windsor/WBR business facts
2. use `query_ads_facts` for campaign-level ad facts
3. use `query_search_term_facts` for bounded keyword or search-term rankings
4. use `query_catalog_context` for product metadata

### 3. Row composition questions

If the user asks what products make up a WBR row:

1. prefer `list_child_asins_for_row`
2. if deeper product context is needed after that, use `query_catalog_context`

### 4. Freshness questions

If the user asks whether a date is missing because data has not landed yet:

1. use `get_sync_freshness_status`
2. mention the latest landed fact dates explicitly
3. do not guess whether same-day data should exist

### 5. Search-term ranking questions

If the user asks for top keywords, top search terms, or STR-based rankings:

1. use `query_search_term_facts`
2. default to bounded windows like last week or last month
3. prefer ranking by `spend` unless the user clearly asks for another metric
4. state explicitly whether the result is about `keyword` or `search_term`

### 6. Monthly P&L detail questions

If the user wants line-item or month-level P&L drill-down:

1. use `query_monthly_pnl_detail`
2. keep the explanation focused on the selected month window
3. surface warnings when they materially affect interpretation

## Working Rules

1. Prefer the narrowest analyst tool that cleanly answers the question.
2. Use `get_asin_sales_window` before `query_business_facts` for simple
   ASIN-window questions.
3. Use `list_child_asins_for_row` before `query_catalog_context` when the user
   is asking specifically about WBR row composition.
4. Treat all analyst-query tools as read-only.
5. If the requested period exceeds landed data, say that explicitly and use the
   returned freshness notes.
6. Do not invent conversion rates, rankings, or conclusions that are not
   clearly supported by the returned metrics.
7. Do not expose raw internal UUIDs in normal user-facing answers unless the
   user explicitly asks for them or they are required to resolve ambiguity.
8. For STR questions, do not conflate `keyword` and `search_term`; name which
   dimension you are ranking in the answer.

## Recommended Prompts

1. "How much of ASIN B07BVZ4TN7 did we sell from 2026-03-10 to 2026-03-16?"
2. "What products make up this WBR row?"
3. "Is the data current for this WBR profile?"
4. "Show me campaign spend and sales by campaign for last week."
5. "What were the biggest expense lines for January 2026?"
