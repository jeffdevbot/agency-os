# Product Requirement Document: AdScope (v0.1)

**Goal:** Upload Bulk .xlsx + Search Term Report .csv (+ brand keywords), run in-memory Python audit, return one JSON payload with precomputed views; render in a dark “VS Code”-style UI with chat-driven view switching. Ephemeral: no DB writes; data cleared after request. No database tables; JSON schemas only.

---

## 1) Core Workflow
- Ingest: Two files (Bulk .xlsx, STR .csv) + optional Brand Keywords.
- Process: FastAPI + Pandas load, clean, and compute 8 views; return a single JSON.
- Visualize: Initial Overview rendered in a dark IDE-like workspace.
- Interact: AI chat drives `change_canvas_view` tool calls to swap views.
- Forget: No persistence; data lives in RAM for the request/session only.

---

## 2) Tech Stack
- Frontend: React, Tailwind, shadcn/ui, Framer Motion, Recharts (charts).
- Backend: Python FastAPI, Pandas.
- AI: OpenAI (reuse existing Scribe integration; GPT-4o+ chat/tool-calling). Future: evaluate GPT-5.1 Responses API behind a feature flag.
- Hosting: Render (frontend + backend).
- Auth: Supabase JWT guard (match existing tools).

---

## 3) Backend (FastAPI/Pandas)
- Endpoint: `POST /audit` (multipart: bulk_file, str_file, brand_keywords text).
- Limits: 40MB per file; if `df.memory_usage().sum()` > ~512MB, return friendly error (“File too large…reduce date range to 30 days”).
- Ephemeral: No DB writes; clear data after request; temp files removed.
- Parsing: Clean numerics; branded vs generic via keyword contains (case-insensitive). Required columns derived from provided STR/Bulk samples; fuzzy matching handles header variants. Minimum required columns:
  - STR: Search Term, Match Type, Campaign, Impressions, Clicks, Cost/Spend, Conversions/Orders, Sales (7-day), Currency (if present).
  - Bulk (SP campaigns tab): Campaign Name/ID, Ad Group Name/ID, Entity, Match Type, Keyword/Targeting, Spend/Cost, Sales, Clicks, Impressions, Status/State, Max CPC/Default Bid, Product/Ad Type, Portfolio (optional), ASIN/SKU (optional).
- Output: JSON with raw numerics (frontend formats). Currency assumed USD v0.1.
  - Currency: detect from file column (e.g., Currency/Currency Code); include `currency_code` in JSON for frontend formatting ($/€/£).

### Precomputed Views (schemas)
- `overview`: `{ spend: float, sales: float, acos: float (0-1), roas: float, impressions: float, clicks: float, orders: float, ad_type_mix: [{ type, spend, percentage }] }`
- `money_pits`: top 20% by spend, max 50, sorted spend desc: `[{ asin, product_name, spend, sales, acos }]`
- `waste_bin`: spend > 50, sales = 0, max 100, sorted spend desc: `[{ search_term, spend, clicks }]`
- `brand_analysis`: `{ branded: { spend, sales, acos }, generic: { spend, sales, acos } }`
- `match_types`: sorted spend desc: `[{ type, spend, sales, acos, cpc }]`
- `placements`: standard 3 placements: `[{ placement, spend, acos, cpc }]`
- `keyword_leaderboard`: `{ winners: [{ text, match_type, campaign, spend, sales, roas }], losers: [{ text, match_type, campaign, spend, sales, roas }] }` (winners = top 10 by sales; losers = top 10 by spend with ROAS < 2)
- `budget_cappers`: list with utilization > 0.9: `[{ campaign_name, daily_budget, avg_daily_spend, utilization, roas }]`
- `campaign_scatter`: `[{ id, name, spend, acos, ad_type }]`
- `n_grams`: `[{ gram, type, spend, sales, acos, count }]` (type = 1-gram, 2-gram)
- `duplicates`: `[{ keyword, match_type, campaign_count, campaigns }]`
- `portfolios`: `[{ name, spend, sales, acos }]`
- `price_sensitivity`: `[{ asin, avg_price, cvr }]`
- `zombies`: `{ total_active_ad_groups: int, zombie_count: int, zombie_list: [str] }`

---

## 4) Frontend (React)
- Screen 1 (Ingest): Two distinct dropzones (Bulk .xlsx, STR .csv), Brand Keywords input, “Run Audit” disabled during processing with spinner/status. Errors shown in red alert under dropzones (invalid type, missing columns, >40MB, memory).
- Screen 2 (IDE workspace): Dark “VS Code” style. Left chat (messages, input, quick chips), right canvas swaps views with Framer Motion. Global state holds audit JSON + `activeCanvasView`.
- Views: Overview cards/pie/funnel (initial). Additional views summoned via AI/tool calls: money_pits, waste_bin, keyword_leaderboard, brand_analysis, match_types, placements, budget_cappers, campaign_scatter, n_grams, duplicates, portfolios, price_sensitivity, zombies. Recharts components: pie/donut, funnel bars, grouped bars, scatter, and tables.
- Empty state: Keep tab, render “No data” message inside the canvas.

### Formatting (frontend)
- Currency: `$1,234.56` (2 dp), Percent: `12.5%` (1–2 dp), Large ints with thousands/compact for charts.
- Overview visuals: KPI cards (Spend, Sales, ACOS with thresholds: <15% blue/good; 15–30% yellow/ok; >30% red/high), ROAS neutral; ad type donut with fixed palette (e.g., SP #3b82f6, SB #8b5cf6, SD #f97316, default gray); funnel bars for impressions/clicks/orders (render even when zero; show labels).

---

## 5) AI Tooling
- Persona: “Senior Ad Auditor” — direct, data-driven.
- Tool: `change_canvas_view(view_id: str)`; allowed: `['overview','money_pits','waste_bin','brand_analysis','match_types','placements','keyword_leaderboard','budget_cappers','campaign_scatter','n_grams','duplicates','portfolios','price_sensitivity','zombies']`.
- Guardrail: If user asks for a non-existent view, do NOT call tool; explain it’s unavailable and suggest closest existing view.
- Guardrail decision tree: If question can be answered by existing view + filter, use that. Else if it matches a common hidden view, compute once and cache for the session. Else if estimated cost < limits (max 500 rows, max 3 grouping dimensions, ~5s budget), compute ad hoc; otherwise, offer alternative guidance.

---

## 6) Errors & UX
- Auth required (Supabase JWT).
- Clear error messages: invalid file type, missing columns, oversize (>40MB), memory cap (>512MB RAM).
- Button disabled + loading state during processing.

---

## 7) Open Items (pending sample files)
- Bulk/STR required columns, header rows, tab names, and parsing rules.
- Budget cap detection logic based on available columns.
- Branded vs generic matching rules refinement (exact word boundaries vs contains).
- Optional future: GPT-5.1 Responses API pilot behind a flag; current default stays on the existing OpenAI chat integration used by Scribe.

---

## Addendum: Schema Validation (Fuzzy Matching)

- **Strategy:** Map columns via internal_key → candidate headers list; if no exact match, use keyword/fuzzy matching (e.g., contains "Sales" AND "7 Day"). If a critical column is missing, raise a clear `ReportValidationError`.
- **Search Term Report (STR):** Required fields
  - `search_term`: ["Customer Search Term", "Query", "Search Term"]
  - `spend`: ["Spend", "Cost"]
  - `sales`: fuzzy (contains "Sales" and "7 Day"; fallback any "Sales")
  - Clean numerics (strip $ ,), fillna(0).
- **Bulk Operations File:** Required fields
  - `entity`: ["Entity", "Record Type"]
  - `product`: ["Product", "Ad Product"]
  - `campaign_name`: ["Campaign Name", "Campaign"]
  - `match_type`: ["Match Type"]
  - `spend`: ["Spend", "Cost"]
  - `sales`: ["Sales", "7 Day Total Sales", "14 Day Total Sales"]; fallback fuzzy contains "Sales"
  - `clicks`: ["Clicks"]
  - `impressions`: ["Impressions"]
  - Optional/blank if missing: `asin` ["ASIN (Informational only)", "ASIN", "Ad ID"], `sku` ["SKU"], `keyword` ["Keyword Text", "Targeting Expression"]
  - Clean numerics (spend, sales, clicks, impressions).
  - Raise on missing criticals; keep optional as blank.

---

## Addendum: Bulk Excel Ingestion (Multi-Tab)

- **Sheets:** Bulk file may have multiple tabs (e.g., “Portfolios”, “Sponsored Products Campaigns”, “RAS Campaigns”). Do not assume “Sheet1”.
- **Selection heuristic:** Scan visible sheets; pick the sheet containing critical headers (at minimum `Entity`, `Campaign ID`, `Spend`, `Sales`). If multiple qualify, prefer sheet named “Sponsored Products Campaigns” or “Sponsored Products”. If none, error: “Could not find a sheet with Entity, Spend, and Sales columns.” If a tab explicitly named “Bulk Sheet”/“Search Terms” exists, prefer it; otherwise use first matching tab and surface a warning.
- **Schema (Sponsored Products Campaigns tab):** Apply fuzzy matching:
  - `entity`: ['Entity']
  - `product`: ['Product']
  - `campaign_name`: ['Campaign Name']
  - `ad_group_name`: ['Ad Group Name']
  - `match_type`: ['Match Type']
  - `spend`: ['Spend']
  - `sales`: ['Sales', '7 Day Total Sales'] (keep fuzzy “Sales” contains)
  - `clicks`: ['Clicks']
  - `impressions`: ['Impressions']
  - `asin`: ['ASIN (Informational only)', 'ASIN']
  - `sku`: ['SKU']
  - `keyword`: ['Keyword Text', 'Targeting Expression']
- **Cleaning:** Convert spend/sales/clicks/impressions to numeric (strip $, commas; treat non-numeric like “-” as 0). Keep rows unfiltered initially (Campaign rows for budget; Ad Group rows for spend/sales; Product Ad rows for ASIN; Keyword rows for match/keyword).
- **RAS tab:** Present but not primary; prioritize Sponsored Products tab by heuristic. If future logic needs RAS, add a specific mapper.
- **Schema reference:** Tab names and observed headers captured in `docs/21_adscope_schema.md`; update as new exports appear.

---

## Currency Handling
- Detect currency symbols/headers for USD ($), EUR (€), GBP (£); default to USD if undetectable. Send raw numerics; frontend formats with symbol. For bulk/STR with Currency/Currency Code, pass `currency_code` in JSON metadata.

---

## Budget Utilization Logic (Budget Cappers)
- Build CampaignID → Daily Budget map from Entity='Campaign' rows.
- Sum Spend for non-Campaign rows per CampaignID (avoid double counting).
- Assume 60-day bulk span unless date parsing indicates otherwise; compute `avg_daily_spend = total_spend / days_in_range`. Utilization = avg_daily_spend / daily_budget.
- Flag campaigns with utilization > 0.9; include roas if available; output only flagged rows.

---

## Date Range Validation
- Read Start/End dates from STR and Bulk. If date ranges differ by >24h, set `date_range_mismatch: true` in overview JSON and surface a yellow alert in the frontend (“Warning: File date ranges do not match. Analysis may be skewed.”)

---

## UX/Patterns
- Two-file upload pattern is intentional (Bulk + STR) with two distinct dropzones.
- Response is JSON (precomputed views) to support chat-driven canvas swapping (distinct from Excel exporters in other tools).
- Theme is dark/IDE-style (intentional departure from light themes).
- Hidden views: precompute Tier 1 (core views listed above). Tier 2 common hidden views (match_types, keyword_leaderboard, budget_cappers, campaign_scatter, n_grams, duplicates, portfolios, price_sensitivity, zombies) available on demand and cached for session. Ad-hoc requests must respect limits (max 500 rows, max 3 grouping dimensions, ~5s).

---

## Testing (to add)
- Schema validation: fuzzy matching maps required columns for STR and Bulk; errors on missing criticals.
- Currency detection: selects $, €, £ correctly when present; currency_code passed through for formatting.
- View JSON shape: all view keys present; numeric fields populated; empty states handled.
- Memory guard: oversize files ( >40MB) and memory cap (~512MB) return friendly errors (adjust after perf tests).
- Tool-calling: AI requests invalid view_id → no tool call; responds with guidance.
- Budget cappers: budget/utilization computed correctly and filtered.
- Date-range mismatch: warn when Bulk/STR ranges differ by >24h.

---

## Open Items
- Budget cap detection logic (columns/thresholds from Bulk).
- STR/Bulk column mapping finalized from provided samples (update required-list if needed).
- Branded vs generic matching rules refinement (exact word boundaries vs contains).
- Optional future: GPT-5.1 Responses API pilot behind a flag; current default stays on the existing OpenAI chat integration used by Scribe.
- Date-range validation: Read Start/End dates from STR and Bulk; if ranges differ by >24h, set `date_range_mismatch: true` in overview JSON and surface a yellow alert in the frontend.
