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
- Parsing: Clean numerics; branded vs generic via keyword contains (case-insensitive). Required columns TBD upon sample files.
- Output: JSON with raw numerics (frontend formats). Currency assumed USD v0.1.

### Precomputed Views (schemas)
- `overview`: `{ spend: float, sales: float, acos: float (0-1), roas: float, ad_type_mix: [{ type, spend, percentage }] }`
- `money_pits`: top 20% by spend, max 50, sorted spend desc: `[{ asin, product_name, spend, sales, acos }]`
- `waste_bin`: spend > 50, sales = 0, max 100, sorted spend desc: `[{ search_term, spend, clicks }]`
- `brand_analysis`: `{ branded: { spend, sales, acos }, generic: { spend, sales, acos } }`
- `match_types`: sorted spend desc: `[{ type, spend, acos }]`
- `placements`: standard 3 placements: `[{ placement, spend, acos, cpc }]`
- `keyword_leaderboard`: `{ best: [{ keyword, match_type, spend, sales }], worst: [{ keyword, match_type, spend, clicks }] }` (best = top 50 by sales; worst = top 50 by spend with 0 sales)
- `budget_cappers`: max 50: `[{ campaign_name, frequency_score (0-1) }]`

---

## 4) Frontend (React)
- Screen 1 (Ingest): Two distinct dropzones (Bulk .xlsx, STR .csv), Brand Keywords input, “Run Audit” disabled during processing with spinner/status. Errors shown in red alert under dropzones (invalid type, missing columns, >40MB, memory).
- Screen 2 (IDE workspace): Dark “VS Code” style. Left chat (messages, input, quick chips), right canvas swaps views with Framer Motion. Global state holds audit JSON + `activeCanvasView`.
- Views: Overview cards/pie; Reusable TableView for money_pits/waste_bin/leaderboard; BrandAnalysis stacked bar; GroupedChart for match_types/placements; Budget cappers list.
- Empty state: Keep tab, render “No data” message inside the canvas.

### Formatting (frontend)
- Currency: `$1,234.56` (2 dp), Percent: `12.5%` (1–2 dp), Large ints with thousands/compact for charts.

---

## 5) AI Tooling
- Persona: “Senior Ad Auditor” — direct, data-driven.
- Tool: `change_canvas_view(view_id: str)`; allowed: `['overview','money_pits','waste_bin','brand_analysis','match_types','placements','keyword_leaderboard','budget_cappers']`.
- Guardrail: If user asks for a non-existent view, do NOT call tool; explain it’s unavailable and suggest closest existing view.

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
- **Selection heuristic:** Scan visible sheets; pick the sheet containing critical headers (at minimum `Entity`, `Campaign ID`, `Spend`, `Sales`). If multiple qualify, prefer sheet named “Sponsored Products Campaigns” or “Sponsored Products”. If none, error: “Could not find a sheet with Entity, Spend, and Sales columns.”
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

---

## Currency Handling
- Detect currency symbols/headers for USD ($), EUR (€), GBP (£); default to USD if undetectable. Send raw numerics; frontend formats with symbol.

---

## UX/Patterns
- Two-file upload pattern is intentional (Bulk + STR) with two distinct dropzones.
- Response is JSON (precomputed views) to support chat-driven canvas swapping (distinct from Excel exporters in other tools).
- Theme is dark/IDE-style (intentional departure from light themes).

---

## Testing (to add)
- Schema validation: fuzzy matching maps required columns for STR and Bulk; errors on missing criticals.
- Currency detection: selects $, €, £ correctly when present.
- View JSON shape: all view keys present; numeric fields populated; empty states handled.
- Memory guard: oversize files ( >40MB) and memory cap (~512MB) return friendly errors (adjust after perf tests).
- Tool-calling: AI requests invalid view_id → no tool call; responds with guidance.

---

## Open Items
- Budget cap detection logic (columns/thresholds from Bulk).
- STR/Bulk column mapping finalized from provided samples (update required-list if needed).
- Branded vs generic matching rules refinement (exact word boundaries vs contains).
- Optional future: GPT-5.1 Responses API pilot behind a flag; current default stays on the existing OpenAI chat integration used by Scribe.
