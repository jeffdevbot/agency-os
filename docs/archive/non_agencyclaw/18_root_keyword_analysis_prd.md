# Product Requirement Document: Root Keyword Analysis

**Version:** 0.1 (Draft)  
**Product Area:** Agency OS → Tools → Root Keyword Analysis  
**Status:** Draft  
**Route:** `tools.ecomlabs.ca/root-keywords` (frontend) / `POST /root/process` (backend)

---

## 1) Executive Summary

Root Keyword Analysis ingests a Campaign Report and returns an Excel workbook grouped into hierarchical rows (Profile → Portfolio → Ad Type → Targeting → Sub-Type → Variant) with 4 weeks of metrics per metric group. It mirrors the N-GRAM/N-PAT upload-download pattern and reuses their UI styling (heading, cards, buttons, loading states). **Single-step tool:** only `/process` is required; no `/collect` step (there is nothing to collect from a filled workbook).

---

## 2) Inputs

- **File:** Campaign Report (.xlsx/.xls/.csv) with 8-row header; data starts on row 9.  
- **Required columns (row 9):** `Time`, `CampaignName`, `Campaign Tag`, `ProfileName`, `PortfolioName`, `Status`, `Impression`, `Click`, `Spend`, `CTR`, `CPC`, `CVR14d`, `ACOS14d`, `ROAS14d`, `Order14d`, `SaleUnits14d`, `Sales14d`.  
- **Status filter:** Include all values (no exclusion).  
- **File size:** Enforce `MAX_UPLOAD_MB = 40`.

---

## 3) Campaign Name Parsing & Hierarchy

- **Delimiter:** Split `CampaignName` by `" | "` (space-pipe-space). Trim whitespace around parts.  
- **Map (positional):** `[0]=Portfolio | [1]=Ad Type | [2]=Targeting | [3]=Sub-Type | [4]=Variant]`.  
- **Fewer parts / no delimiter:** If no pipe is present, treat the whole string as Portfolio; stop nesting at the last present part.  
- **Extra parts (>4):** Ignore beyond Variant (do not concatenate).  
- **Other separators:** Underscores/hyphens inside tokens are treated as part of the token (no split on `_` or `-`).  
- **Vocab:** Use provided Ad Type/Targeting/Sub-Type/Variant codes as current fixed list; unknowns pass through (no “Other”).  
- **Grouping order (alphabetical at each level):** ProfileName → PortfolioName → Ad Type → Targeting → Sub-Type → Variant.  
- **Row labels:** Concatenated path per level (Variant rows show full path).

---

## 4) Time Window & Metrics

- **Timezone:** Use UTC for all date math unless a future setting overrides it.  
- **Window definition:** Last 4 full weeks, Sunday 00:00:00 to Saturday 23:59:59 UTC. Anchor on the latest `Time` in the file:  
  1) Convert `Time` to datetime UTC.  
  2) Find the Saturday at or before `max(Time)`. This is week 1 end.  
  3) Week 1 start = that Saturday - 6 days. Weeks 2–4 back up in 7-day blocks.  
  4) Include rows where `Time` ∈ [week_start, week_end] for each of the 4 buckets.  
- **Partial data:** If the file has <7 days or gaps, still render all 4 weeks; buckets without data show 0/blank.  
- **Metrics (per week):** Clicks, Spend, $ CPC, Orders, Conversion Rate, Sales, ACoS.  
- **Aggregations (per group, per week):** Sum `Impression, Click, Spend, Order14d, SaleUnits14d, Sales14d`.  
- **Recomputed rates (per week):**  
  - CTR = Click / Impression  
  - CPC = Spend / Click  
  - CVR = Order / Click  
  - ACoS = Spend / Sales  
  - ROAS = Sales / Spend (not displayed but available if needed)  
- **Div-by-zero:** Return 0.

---

## 5) Workbook Layout & Styling (match screenshot)

- **Single sheet** with hierarchy in column A; metric blocks to the right.  
- **Header band:** Dark background `#3a3838`, white bold text. Each metric name is a merged cell over 4 columns; two date rows beneath (row 1 Sunday, row 2 Saturday) for each week.  
- **Column ordering:** Metric blocks in this order, each with 4 weekly columns (most recent leftmost): Clicks | Spend | $ CPC | Orders | Conversion Rate | Sales | ACoS.  
- **Column widths:**  
  - A (hierarchy): 60  
  - Each weekly numeric column: 9–10  
  - Optional thin spacer between metric blocks (width ~2)  
- **Number formats:**  
  - Clicks/Orders: integer (0).  
  - Spend/CPC/Sales: currency with detected symbol (€, £, $), two decimals; fallback to € if undetectable.  
  - Conversion Rate/ACoS: percent, two decimals.  
- **Row styling:**  
  - Band colors: `#d9e1f2`, `#fce4d6`, `#ffffff` (alternate by grouping blocks, e.g., Ad Type blocks).  
  - Profile/Portfolio rows bold; Ad Type italic bold; Targeting/Sub-Type/Variant normal (top of a block may be bold per sample).  
  - Indentation: leading indent/space or Excel indent level to show hierarchy depth.  
- **Borders:** Thin vertical separators between metric blocks; minimal horizontal borders (banding provides contrast).  
- **Freeze panes:** Freeze top header band (rows 1–3) and first column A.
- **Filename:** `{original}_root_keywords.xlsx`.

---

## 6) Frontend (Next.js, reuse N-GRAM/N-PAT styling)

- Single-page, auth-guarded (Supabase).  
- Same heading, gradient background, white cards, button styles, dropzone, and rotating loading phrases as N-GRAM/N-PAT.  
- Flow: Upload Campaign Report → call `/root/process` with bearer JWT → trigger download (`{original}_root_keywords.xlsx`).  
- Env vars: `NEXT_PUBLIC_BACKEND_URL`, Supabase URL/anon key.

---

## 7) Backend (FastAPI)

- Routes:  
  - `GET /root/healthz` → `{ok: true}`.  
  - `POST /root/process`: multipart `file`, auth required. Single-step tool; **no `/collect` endpoint** needed.  
- Behavior: Parse header at row 9; determine last 4 Sunday–Saturday weeks ending on/latest before file’s max date (UTC); filter to those weeks; parse hierarchy; aggregate per node/week; recompute rates; build styled workbook; return file.  
- Limits: `MAX_UPLOAD_MB=40`; returns 413 if exceeded.  
- Currency detection: inspect raw Spend (and other currency fields) before numeric cleaning for leading symbols; if one or more of {€, £, $} found, pick the most frequent symbol; otherwise default to €. Apply the chosen symbol to Spend/CPC/Sales/ACoS formats.  
- Logging (mirror N-GRAM/N-PAT shape): `user_id`, `user_email`, `file_name`, `file_size_bytes`, `rows_processed`, `profiles_count`, `portfolios_count`, `campaigns_parsed`, `duration_ms`, `app_version`, `status` (success/error), optional `weeks_covered`, `generated_at`.

---

## 8) Errors & Responses

- Missing required columns → 400 with missing list.  
- No data in last 4 weeks → 400 (“No data in last 4 weeks”).  
- File too large → 413.  
- Parse error → 400 with detail.

---

## 9) Testing Plan

- **Unit:** CampaignName parsing (truncated/extra parts), week bucketing (Sunday–Saturday), rate calc div-zero guards, alphabetical sort.  
- **Integration:** Sample report → verify 4-week headers (most recent left), hierarchy labels, aggregated sums, recomputed rates, multiple profiles/portfolios/ad types/sub-variants.  
- **Formatting smoke:** Open in Excel/Sheets; confirm header band color/merge, date rows, banding (#3a3838/#d9e1f2/#fce4d6/#ffffff), indentation, currency/percent formats, column widths.  
- **Edge:** <4 weeks data, missing sub-levels, unknown tokens, extra chunks ignored.

---

## 10) Notes & Sample Aids

- **Hierarchy sample (parsed):**
```json
{
  "ProfileName": "Framelane [DE]",
  "PortfolioName": "50x70 - Oak Frames",
  "AdType": "SPM",
  "Targeting": "MKW",
  "SubType": "Br.M",
  "Variant": "0 - gen"
}
```
- **Week selection example:** If latest `Time` is Wed Aug 13, 2025 → nearest Saturday is Aug 16 → weeks:  
  - Week 1: Sun Aug 10 – Sat Aug 16 (most recent, leftmost)  
  - Week 2: Sun Aug 3 – Sat Aug 9  
  - Week 3: Sun Jul 27 – Sat Aug 2  
  - Week 4: Sun Jul 20 – Sat Jul 26

---

## 11) Open Items

- Currency detection beyond symbol (e.g., currency codes or locale inference) if future reports omit symbols.  
- Exact bold/italic/indent rules for each level can be tuned to match the provided screenshot pixel-perfectly during implementation.
