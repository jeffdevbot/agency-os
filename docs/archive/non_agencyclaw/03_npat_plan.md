# N-PAT Build Plan (Micro Tasks)

Purpose: bite-size tasks to implement N-PAT per `docs/03_npat_prd.md`. Keep parity with N-Gram where possible.

## Backend
- [ ] Router scaffold `app/routers/npat.py`: healthz, process, collect; Supabase auth; MAX_UPLOAD_MB enforcement.
- [ ] Parser `app/services/npat/parser.py`: normalize STR columns (match N-Gram mappings), filter ONLY ASINs with `^[A-Z0-9]{10}$` (case-insensitive), uppercase ASINs, exclude campaigns containing “Ex.”/“SDI”/“SDV”.
- [ ] Analytics `app/services/npat/analytics.py`: compute CTR, CPC, CVR, ACOS with div-by-zero guards; reuse N-Gram category derivation.
- [ ] Workbook generator `app/services/npat/workbook.py`: summary sheet + per-campaign sheets with helper rows (B2 TEXTJOIN pipe uppercase), main metrics table (Impression, Click, Spend, Order 14d, Sales 14d, CTR, CVR, CPC, ACOS), H10 paste zone (M-V per H10 schema), VLOOKUP columns (W-AA), NE/NP + Comments (AB/AC); formatting like N-Gram.
- [ ] Collect endpoint: read filled workbook, pull ASINs marked NE in column AB + enrichment (W-AA) + all metrics (Impression…ACOS), emit formatted Excel (header, zebra with borders), skip empty campaigns, enforce auth.
- [ ] Usage logging: mirror N-Gram fields plus total_asins; ensure errors surface as HTTP 400/413/500.

## Frontend
- [ ] Page scaffold `frontend-web/src/app/npat/page.tsx`: two cards (Step 1 generate, Step 2 collect), drag/drop + browse, Supabase auth, env check for `NEXT_PUBLIC_BACKEND_URL`.
- [ ] Step 1 UX: CTA with loading phrases (reuse N-Gram list), pulse effect; show filename; handle errors/toast.
- [ ] Step 2 UX: CTA text “Download Negatives Summary”, accepts `.xlsx`, shows filename, errors/toast.
- [ ] Wire API calls: Step 1 → `/npat/process` (JWT bearer) download `_npat.xlsx`; Step 2 → `/npat/collect` download `_negatives.xlsx`.
- [ ] Add simple frontend file-size precheck (40MB) to align with backend.

## Testing
- [ ] Parser unit tests: ASIN regex, normalization, campaign exclusion.
- [ ] Analytics unit tests: CTR/CPC/CVR/ACOS with zero guards.
- [ ] Workbook smoke test: generate from sample STR, open with openpyxl, verify sheet names, formulas (TEXTJOIN, VLOOKUP ranges), no repair.
- [ ] Collect smoke test: craft filled workbook with NE marks, run collect, verify rows/columns/metrics populate and borders/zebra applied.
- [ ] Integration: end-to-end upload/process/download and collect on sample STR (~6k rows) within timeout (<=180s) locally.

## Ops/Config
- [ ] Env vars: `SUPABASE_URL`, `SUPABASE_JWT_SECRET`, `MAX_UPLOAD_MB` (40), `APP_VERSION`, `NEXT_PUBLIC_*`.
- [ ] Start command: gunicorn with increased timeout (e.g., `--timeout 180 --graceful-timeout 30`), match N-Gram service.
- [ ] File naming: `{original}_npat.xlsx` for process; `{original}_negatives.xlsx` for collect.

## Nice-to-have (post-MVP)
- [ ] Add Amazon product URL column in output summary if helpful.
- [ ] Dedup ASINs per campaign in summary (optional toggle).
- [ ] Add frontend link from dashboard to N-PAT route.
