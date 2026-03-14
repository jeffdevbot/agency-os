# WBR v2 Resume Prompt

You are continuing WBR v2 work in `/Users/jeff/code/agency-os`.

Start by reading, in this order:

1. `docs/wbr_v2_handoff.md`
2. `PROJECT_STATUS.md`
3. `docs/wbr_v2_schema_plan.md`
4. `docs/wbr_v2_prototype_plan.md`
5. `backend-core/app/routers/wbr.py`
6. `backend-core/app/services/wbr/windsor_business_sync.py`
7. `backend-core/app/services/wbr/section1_report.py`
8. `frontend-web/src/app/reports/_components/WbrSection1ReportScreen.tsx`
9. `frontend-web/src/app/reports/_components/WbrSection1MetricTable.tsx`
10. `frontend-web/src/app/reports/_components/WbrSyncScreen.tsx`
11. `frontend-web/src/app/reports/_lib/useResolvedWbrProfile.ts`
12. `frontend-web/src/app/reports/_lib/useWbrSection1Report.ts`
13. `frontend-web/src/app/reports/_lib/useWbrSync.ts`
14. `frontend-web/src/app/reports/wbr/[profileId]/WbrProfileWorkspace.tsx`

Context you should assume:

1. WBR v2 schema migrations 1-6 are already applied live.
2. Pacvue import, listings import, ASIN mapping, Windsor listings import, Section 1 Windsor sync/report, Amazon Ads sync/report, and nightly worker automation are already shipped.
3. Primary user routes are client-first:
   - `/reports/[clientSlug]`
   - `/reports/[clientSlug]/[marketplaceCode]/wbr`
   - `/reports/[clientSlug]/[marketplaceCode]/wbr/settings`
   - `/reports/[clientSlug]/[marketplaceCode]/wbr/sync`
   - `/reports/[clientSlug]/[marketplaceCode]/wbr/sync/sp-api`
   - `/reports/[clientSlug]/[marketplaceCode]/wbr/sync/ads-api`
4. The old `/admin/wbr/section1/*` backend still exists but is legacy.
5. `worker-sync` exists in-repo and runs nightly `daily_refresh` jobs for `active` profiles.
6. Enabling either nightly sync toggle auto-promotes a `draft` profile to `active`.

Immediate goal for the next session:

1. Start from the current issue or request, assuming both Section 1 and Section 2 are live.
2. Avoid god-file bloat.
3. Keep the route structure and backend contract intact unless a concrete bug requires a change.
4. Preserve current admin/settings/sync functionality, including nightly worker behavior.

Constraints:

1. Leave unrelated dirty files alone:
   - `docs/db/schema_master.md`
   - `scripts/db/generate-schema-master.sh`
   - `supabase/.temp/cli-latest`
2. Prefer focused components and hooks over growing existing large files.
3. Keep changes pragmatic and easy to test manually on Render.
