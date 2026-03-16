# WBR v2 Resume Prompt

Use this prompt only if the user is explicitly reopening WBR-specific work.

Current default assumption as of March 16, 2026:

1. The current WBR version is effectively done and live.
2. Monthly P&L is a separate reporting track and should be resumed from
   `docs/monthly_pnl_handoff.md`, not from this prompt.
3. If the next session is about clarifying reporting surfaces, route language,
   or navigation between WBR and Monthly P&L, treat that as cross-cutting
   product cleanup rather than core WBR feature development.

You are continuing WBR v2 work in `/Users/jeff/code/agency-os`.

Start by reading, in this order:

1. `docs/wbr_v2_handoff.md`
2. `PROJECT_STATUS.md`
3. `docs/wbr_v2_schema_plan.md`
4. `docs/archive/session_prompts/wbr_v2_prototype_plan.md`
5. `backend-core/app/routers/wbr.py`
6. `backend-core/app/services/wbr/windsor_business_sync.py`
7. `backend-core/app/services/wbr/windsor_inventory_sync.py`
8. `backend-core/app/services/wbr/windsor_returns_sync.py`
9. `backend-core/app/services/wbr/amazon_ads_sync.py`
10. `backend-core/app/services/wbr/nightly_sync.py`
11. `backend-core/app/services/wbr/section1_report.py`
12. `backend-core/app/services/wbr/section3_report.py`
13. `frontend-web/src/app/reports/_components/WbrSection1ReportScreen.tsx`
14. `frontend-web/src/app/reports/_components/WbrTrafficSalesPane.tsx`
15. `frontend-web/src/app/reports/_components/WbrAdvertisingPane.tsx`
16. `frontend-web/src/app/reports/_components/WbrTrendChart.tsx`
17. `frontend-web/src/app/reports/_components/WbrAdsSyncScreen.tsx`
18. `frontend-web/src/app/reports/_components/WbrSyncScreen.tsx`
19. `frontend-web/src/app/reports/_lib/useResolvedWbrProfile.ts`
20. `frontend-web/src/app/reports/_lib/useWbrSection1Report.ts`
21. `frontend-web/src/app/reports/_lib/useWbrSection3Report.ts`
22. `frontend-web/src/app/reports/_lib/useWbrWorkbookExport.ts`
23. `frontend-web/src/app/reports/_lib/useWbrAdsSync.ts`
24. `frontend-web/src/app/reports/_lib/useWbrSync.ts`
25. `frontend-web/src/app/reports/wbr/[profileId]/WbrProfileWorkspace.tsx`

Context you should assume:

1. WBR v2 schema migrations 1-8 are already applied live.
2. Pacvue import, listings import, ASIN mapping, Windsor listings import, Section 1 Windsor sync/report, Amazon Ads sync/report, Section 3 inventory + returns sync/report, and nightly worker automation are already shipped.
3. The main WBR page is now tabbed by section, supports Excel export, and includes inline trend charts for Sections 1 and 2.
4. Primary user routes are client-first:
   - `/reports/[clientSlug]`
   - `/reports/[clientSlug]/[marketplaceCode]/wbr`
   - `/reports/[clientSlug]/[marketplaceCode]/wbr/settings`
   - `/reports/[clientSlug]/[marketplaceCode]/wbr/sync`
   - `/reports/[clientSlug]/[marketplaceCode]/wbr/sync/sp-api`
   - `/reports/[clientSlug]/[marketplaceCode]/wbr/sync/ads-api`
5. The old `/admin/wbr/section1/*` backend still exists but is legacy.
6. `worker-sync` exists in-repo, runs nightly `daily_refresh` jobs for `active` profiles, and now also advances queued Amazon Ads report jobs outside the nightly schedule window.
7. Enabling either nightly sync toggle auto-promotes a `draft` profile to `active`.
8. Amazon Ads backfills/manual refreshes are now enqueue-first: the HTTP request returns quickly, while `worker-sync` polls Amazon, downloads finished reports, and finalizes the run later.
9. Windsor manual/nightly refreshes now also run Section 3 inventory and returns ingestion, and Section 3 is showing live data on the validation account.
10. Section 3 does not have charts yet because the current payload is snapshot-based, not a true multi-week inventory trend series.

Immediate goal for the next session:

1. Start from the current issue or request, assuming Sections 1, 2, and 3 are live and Amazon Ads sync uses the queued/background report flow.
2. Treat this as a bugfix or targeted enhancement path, not an open-ended prototype buildout.
3. Avoid god-file bloat.
4. Keep the route structure and backend contract intact unless a concrete bug requires a change.
5. Preserve current admin/settings/sync functionality, including nightly worker behavior.
6. Prefer extending the current modular report components rather than re-consolidating them into the old report screen.

Constraints:

1. Leave unrelated dirty files alone:
   - `docs/db/schema_master.md`
   - `scripts/db/generate-schema-master.sh`
   - `supabase/.temp/cli-latest`
2. Prefer focused components and hooks over growing existing large files.
3. Keep changes pragmatic and easy to test manually on Render.
