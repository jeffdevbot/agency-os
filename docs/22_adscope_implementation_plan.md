# AdScope Implementation Plan (Micro Tasks)

Context: AdScope is a stateless audit tool for Amazon Ads. It ingests a Bulk Excel file and a Sponsored Products Search Term Report (STR), performs in-memory Pandas analysis, and returns a precomputed JSON used by a dark, IDE-style frontend with chat-driven view switching. Auth stays on Supabase JWT. Schemas and tab headers are captured in `docs/21_adscope_schema.md`; use them as the canonical reference.

---

## Backend (FastAPI / Pandas)

1) Router & Auth
- Add `POST /audit` (multipart: bulk_file, str_file, brand_keywords text), Supabase JWT guard, 40MB/file cap, memory guard (~512MB).
- Return JSON with all precomputed views; include `currency_code` and `date_range_mismatch` flags.

2) Ingest Service: STR Parsing
- Use schemas from `docs/21_adscope_schema.md`. Implement fuzzy matching for required fields (search_term, spend, sales, impressions, clicks, match_type, campaign, dates, currency).
- Clean numerics rigorously: strip $/commas; replace non-numeric (‘-’, ‘NaN’, ‘null’) with 0 before math; parse dates (start/end); classify branded vs generic (brand keywords).
- Add n-gram tokenizer (1-gram, 2-gram) over Customer Search Term for n_grams view.

3) Ingest Service: Bulk Parsing (Multi-tab Excel)
- Use tab selection heuristic: prefer “Sponsored Products Campaigns”/“Sponsored Products”, or first tab containing critical headers (Entity, Campaign ID, Spend, Sales); prefer explicitly named “Bulk Sheet”/“Search Terms” if present. Warn on fallback.
- Use schemas from `docs/21_adscope_schema.md` for Sponsored Products Campaigns. Apply fuzzy mapping for entity, product, campaign/ad group, match_type, keyword/targeting, spend, sales, clicks, impressions, bids, placement, state, ASIN/SKU, targeting type, dates, currency.
- Clean numerics rigorously: strip $/commas; replace non-numeric (‘-’, ‘NaN’, ‘null’) with 0 before math.
- Do not filter rows; preserve campaign/adgroup/keyword/product ad rows for later grouping.
- Detect currency_code from currency columns; default USD.

4) Date Range Validation
- Read Start/End from STR and Bulk; if ranges differ by >24h, set `date_range_mismatch: true` in overview JSON.

5) Metrics & Views (Pandas)
- Overview: spend, sales, acos, roas, impressions, clicks, orders, ad_type_mix, targeting_mix (manual/auto split by campaign targeting type).
- Money Pits: top 20% by spend (max 50), include asin, product_name (if available), spend, sales, acos, state; add thumbnail URL pattern (or let FE derive).
- Waste Bin: STR terms with spend > 50 and sales = 0 (max 100).
- Brand Analysis: branded vs generic aggregates.
- Match Types: group by Match Type with spend, sales, acos, cpc.
- Placements: group by placement with spend, acos, cpc.
- Keyword Leaderboard: winners (top 10 sales) and losers (top 10 spend with ROAS < 2), include state, campaign, match_type.
- Budget Cappers: CampaignID → daily budget; sum spend (non-campaign rows); avg_daily_spend = total_spend / days; utilization = avg_daily_spend / daily_budget; flag > 0.9, include roas, state.
- Campaign Scatter: per campaign spend, acos, ad_type.
- N-grams: 1-gram/2-gram aggregates from STR (spend, sales, acos, count).
- Duplicates: keywords used in multiple campaigns (count + list).
- Portfolios: group by portfolio name (spend, sales, acos).
- Price Sensitivity: per ASIN avg_price (sales/units) vs CVR.
- Zombies: active ad groups with zero impressions; counts + list.

6) Currency & Number Handling
- Backend emits raw numerics; include `currency_code`. Frontend formats with $, €, £. Keep percent as 0–1 floats.

7) Error Handling
- Clear messages: invalid type, missing critical columns, oversize, memory guard, unable to find tab. Include warnings in response (e.g., tab fallback).

8) Tests (Backend)
- Unit: fuzzy mapping (STR/Bulk), currency detection, date range mismatch flag, budget cap math, targeting mix splits, n-gram aggregation.
- Integration: sample files → full JSON; verify view keys/types; ensure warnings/flags set as expected.

---

## Frontend (Next.js + Tailwind + shadcn + Recharts + Framer Motion)

1) Testing/Contract First
- Create `mocks/audit_response.json` that mirrors the full schema (all views, empty states, flags, currency_code) to serve as the FE/BE contract. Use it to render UI before wiring the API.

2) Auth & Layout
- Keep Supabase auth guard; global layout with PostHog init/identify (already present). Dark IDE theme consistent with other tools’ gradient cards style adapted to dark.

3) Ingest Screen
- Two dropzones (Bulk .xlsx, STR .csv/.xlsx), brand keywords input. “Run Audit” disabled during upload; show spinner/status. Show errors in red alert. Pass both files + brand keywords to `/audit`.

4) State & Data
- Store audit JSON + `activeCanvasView`, `warnings` (e.g., date_range_mismatch), `currency_code`. Ensure initial view = overview; handle empty states per view.

5) Overview View
- KPI cards (Spend, Sales, ACOS with thresholds, ROAS). Donut for ad_type_mix with fixed colors (SP #3b82f6, SB #8b5cf6, SD #f97316, default gray). Funnel bars for impressions/clicks/orders. Targeting mix progress bar (manual vs auto). Date-range mismatch alert if flagged.

6) Deep Views (render on demand)
- money_pits: table with thumbnail (derive URL), ASIN/product, spend/sales/acos, state badge; sort enabled first then spend.
- waste_bin: table of terms spend>50 & sales=0.
- brand_analysis: stacked/side bars branded vs generic.
- match_types: grouped bars (spend/sales) + ACOS line.
- placements: grouped bars.
- keyword_leaderboard: winners/losers tables with state badges.
- budget_cappers: list of utilization>0.9, highlight high ROAS.
- campaign_scatter: scatter (spend log x, acos y, color by ad_type).
- n_grams: two tables (1-gram, 2-gram) highlighting value vs waste.
- duplicates: warning list of keywords in multiple campaigns.
- portfolios: horizontal bars by spend.
- price_sensitivity: scatter avg_price vs CVR.
- zombies: stat/list of zero-impression ad groups.

7) Tool Calling
- `change_canvas_view(view_id: string)` with allowed IDs from PRD. Guard invalid IDs (no-op + chat message).

8) Testing (Frontend)
- Validate render with mock JSON: overview, each view, empty states, currency formatting from `currency_code`, state badges, thumbnails fallback, warnings display.

---

## Ops & References
- Env: reuse existing Supabase/OpenAI/PostHog vars; ensure backend MAX_UPLOAD_MB=40.
- Schemas: Refer to `docs/21_adscope_schema.md` for tab names/headers. Keep PRD `docs/20_adscope_prd.md` in sync as new exports appear.
