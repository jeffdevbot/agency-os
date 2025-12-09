# Root Keyword Analysis — Implementation Plan (Micro Tasks)

Purpose: bite-size steps to ship the Root Keyword Analysis tool per `docs/18_root_keyword_analysis_prd.md`. Parallelize backend/frontend; mirror N-GRAM/N-PAT patterns.

## Backend (FastAPI)
1) Router scaffold `app/routers/root.py`: healthz, process; auth (require_user); MAX_UPLOAD_MB enforcement; return Excel file; logging with fields in PRD.
2) Parser `app/services/root/parser.py`: load row-9 header (Excel/CSV), normalize required columns, keep raw currency symbols, convert to numeric after symbol pass-through; expose CampaignName parsed parts (Portfolio/AdType/Targeting/SubType/Variant) using `" | "` split rules and no-pipe fallback.
3) Week bucketing utility `app/services/root/weeks.py`: UTC-based 4 full weeks, Sunday–Saturday, anchored to latest date; returns week boundaries and labels (Sun/Sat strings) most-recent-first.
4) Aggregator `app/services/root/aggregate.py`: per-row week assignment; hierarchical grouping (Profile→Portfolio→AdType→Targeting→SubType→Variant); per-week sums of Impression/Click/Spend/Order/SaleUnits/Sales; recompute CTR/CPC/CVR/ACoS/ROAS with zero guards.
5) Workbook builder `app/services/root/workbook.py`: single sheet with hierarchy column, metric blocks (Clicks, Spend, $CPC, Orders, Conversion Rate, Sales, ACoS), 4 weeks each, merged headers + date rows, formatting (colors, widths, borders, freeze panes), currency symbol applied.
6) Currency detector helper: inspect raw Spend strings pre-clean; pick most frequent of {€, £, $}; default €.
7) Wiring: `/root/process` endpoint composes parser → week buckets → aggregate → workbook; clean temp files; return `{original}_root_keywords.xlsx`.
8) Logging: log user_id/email, file_name, size_bytes, rows_processed, profiles_count, portfolios_count, campaigns_parsed, duration_ms, app_version, status, weeks_covered, generated_at.

## Frontend (Next.js)
1) Page scaffold `frontend-web/src/app/root-keywords/page.tsx`: auth guard via Supabase; reuse N-GRAM/N-PAT layout (heading, gradient, cards, buttons, dropzone, loading phrases).
2) Upload flow: file input (.xlsx/.xls/.csv), optional 40MB precheck; fetch POST `${BACKEND_URL}/root/process` with bearer JWT; download `{original}_root_keywords.xlsx`; toast states/errors.
3) UI polish: match typography/colors/buttons from N-GRAM/N-PAT; show filename; disabled states; error banners; toasts.

## Testing
1) Unit: parser column normalization and delimiter logic; week bucketing (Sunday–Saturday, latest-date anchor); currency detection; rate zero-guard calculations.
2) Integration: end-to-end `/root/process` on sample report → validate sheet structure (headers, date rows, banding, widths), data buckets (4 weeks), hierarchy labels, aggregates, rates, currency format.
3) Edge: no pipe CampaignName; extra parts; unknown tokens; <4 weeks data; mixed currency symbols; file too large; missing columns.

## Ops/Config
1) Add router import to backend app; env `MAX_UPLOAD_MB` (40) honored; ensure CORS allows frontend.
2) Frontend envs: `NEXT_PUBLIC_BACKEND_URL`, Supabase keys already present.
3) Filename convention: `{original}_root_keywords.xlsx`.
