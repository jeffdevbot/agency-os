Continue Monthly P&L work in `/Users/jeff/code/agency-os`.

Read first, in this order:

1. `docs/monthly_pnl_handoff.md`
2. `README.md`
3. `PROJECT_STATUS.md`
4. `docs/monthly_pnl_implementation_plan.md`
5. `AGENTS.md`

Current reality as of March 16, 2026:

1. December 2025 Monthly P&L validation is complete on the validation profile.
2. Validation/backfill profile:
   - `c8e854cf-b989-4e3f-8cf4-58a43507c67a`
3. Active validated December import:
   - import `c84cade9-6633-427f-b4b0-2371d0aca344`
   - source filename `dec2025data-olderfile.csv`
4. November 2025 is also validated and should be preserved:
   - active import `0626222a-dc9c-4be5-a2ba-9de27b093494`
   - source filename `nov-2025.csv`
5. WBR is a separate shipped reporting product. Do not treat Monthly P&L as
   WBR follow-on scope.
6. The user upgraded Supabase to Pro, but the P&L page is still too slow and
   wide report ranges can still fail.

Important live state to preserve:

1. Do not redo December 2025 from scratch unless explicitly asked.
2. Do not replace the active validated December import unless explicitly asked.
3. Preserve the validated November and December state.
4. Leave unrelated dirty files alone:
   - `docs/db/schema_master.md`
   - `scripts/db/generate-schema-master.sh`
   - `supabase/.temp/*`

Current open problems:

1. The Monthly P&L page still loads very slowly.
2. The report request for
   `filter_mode=range&start_month=2025-01-01&end_month=2026-02-01`
   still returns `500` after the earlier RPC optimization and Render redeploy.
3. Multi-month uploads are not reliable yet because the import still runs in a
   long synchronous HTTP request.
4. Earlier failed multi-month uploads left mixed active/error/pending state in
   early 2025 months:
   - Jan 2025 active from failed `jan-mar2025-whoosh-us.csv`
     import `65d24015-7602-49f2-8c7f-2b9f29bab56a`
   - Feb 2025 errored/inactive on that same import
   - Apr 2025 active from retry import `0fe50885-fce4-48ec-afa6-a9dce5cef716`
     which still shows `running`
   - May 2025 active from older failed import
     `37b0af74-0e7f-411a-b6aa-1c82b5cd827a`, while the newer retry has a second
     May slice still `pending`
   - Jun 2025 errored/inactive

Primary goal for the next session:

1. Debug the remaining wide-range report failure and identify the real
   bottleneck for page-load speed.
2. Then productize Monthly P&L imports so multi-month backfills can run as
   async/background work instead of timing out in one blocking request.

Suggested task order:

1. Reproduce and trace the exact `2025-01-01` through `2026-02-01` report
   failure in live logs and code.
2. Confirm whether the mixed active/pending early-2025 import state is part of
   the failure.
3. Decide whether the stranded retry import
   `0fe50885-fce4-48ec-afa6-a9dce5cef716` should be cleaned up before further
   report debugging.
4. Design and implement async/background Monthly P&L imports using the existing
   `worker-sync` service or an equivalent durable job path.
5. Keep the current client-facing `/reports/.../pnl` UX intact while improving
   reliability and speed.

Deliverable expectation:

1. Leave a clear explanation of the remaining report failure.
2. Preserve the validated November/December Monthly P&L state.
3. Move Monthly P&L toward reliable multi-month backfill without regressing the
   shipped reporting surface.
