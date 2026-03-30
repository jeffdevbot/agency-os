# Current Handoffs

_Last updated: 2026-03-30 (ET)_

Use this file to decide which restart/handoff docs are current versus merely
historical reference.

## Active next-session entrypoints

1. [Claude primary surface plan](/Users/jeff/code/agency-os/docs/claude_primary_surface_plan.md)
   - Current strategy doc for Claude vs The Claw and future MCP expansion.
2. [Agency OS MCP implementation plan](/Users/jeff/code/agency-os/docs/agency_os_mcp_implementation_plan.md)
   - Current implementation-planning reference for the shared Claude/MCP tool
     surface after WBR + Monthly P&L shipped.
3. [Reports API access and SP-API plan](/Users/jeff/code/agency-os/docs/reports_api_access_and_spapi_plan.md)
   - Current shared reporting auth/source-of-truth planning reference.
4. [PROJECT_STATUS.md](/Users/jeff/code/agency-os/PROJECT_STATUS.md)
   - Fastest high-level snapshot of what is already shipped.
5. [Search term automation resume prompt](/Users/jeff/code/agency-os/docs/search_term_automation_resume_prompt.md)
   - Current restart prompt if the next session returns specifically to the
     STR / N-Gram 2.0 workstream.

## Current operational/reference docs

1. [WBR schema plan](/Users/jeff/code/agency-os/docs/wbr_v2_schema_plan.md)
   - Current schema/reference document for WBR v2.
2. [Windsor WBR ingestion runbook](/Users/jeff/code/agency-os/docs/windsor_wbr_ingestion_runbook.md)
   - Narrow operational runbook for Windsor Section 1 ingestion.
3. [Claude Project bundle](/Users/jeff/code/agency-os/docs/claude_project/README.md)
   - Current project instructions/files bundle for the live shared WBR +
     Monthly P&L + ClickUp Claude surface.
4. [Monthly P&L handoff](/Users/jeff/code/agency-os/docs/monthly_pnl_handoff.md)
   - Current shipped-state reference for Monthly P&L, Claude P&L, and YoY.
5. [Monthly P&L resume prompt](/Users/jeff/code/agency-os/docs/monthly_pnl_resume_prompt.md)
   - Current restart prompt if a future session returns specifically to
     Monthly P&L.
6. [Team Hours plan / current state](/Users/jeff/code/agency-os/docs/team_hours_plan.md)
   - Current implementation reference for the shipped Team Hours surface under
     Command Center.
7. [Forecasting v1 plan](/Users/jeff/code/agency-os/docs/forecasting_v1_plan.md)
   - Current planning document for the next forecasting surface under Reports.
8. [Claude ClickUp tools plan](/Users/jeff/code/agency-os/docs/claude_clickup_tools_plan.md)
   - Slice 0–4 implemented and live, plus follow-on `update_clickup_task`.
     Current shipped ClickUp MCP tools: `list_clickup_tasks`,
     `get_clickup_task`, `update_clickup_task`, `resolve_team_member`,
     `prepare_clickup_task`, `create_clickup_task`. `get_clickup_task` now
     scopes fetches to mapped Agency OS brand destinations (workspace guard).
     Open follow-ups: broader task update/close/move flows, idempotency.
9. [Opportunity backlog](/Users/jeff/code/agency-os/docs/opportunity_backlog.md)
   - Lightweight priority list for next product/platform opportunities.
10. [Supabase Python client upgrade plan](/Users/jeff/code/agency-os/docs/supabase_python_client_upgrade_plan.md)
   - Tonight-review reference for the backend Supabase dependency warning,
     upgrade scope, and the explicit non-goal of forcing Amazon Ads or Windsor
     re-auth.
11. [Search term automation plan](/Users/jeff/code/agency-os/docs/search_term_automation_plan.md)
   - Current phased planning doc for richer catalog context expansion plus the
     current STR implementation / AI review / direct Amazon writeback roadmap
     for the current N-Gram / N-PAT workflow.
12. [N-Gram native replacement plan](/Users/jeff/code/agency-os/docs/ngram_native_replacement_plan.md)
   - Current product framing for replacing the legacy Pacvue-export-driven
     N-Gram workflow with native data selection, workbook generation, and
     side-by-side manual vs AI-assisted paths.
13. [Claude tool budget plan](/Users/jeff/code/agency-os/docs/claude_tool_budget_plan.md)
   - Current sizing reference for the live MCP tool surface, Claude Project
     file bundle, and the recommended safe expansion budget for future analyst
     query tools.
14. [Claude analyst query tools plan](/Users/jeff/code/agency-os/docs/claude_analyst_query_tools_plan.md)
   - Current implementation-planning doc for the next read-only analyst-query
     MCP expansion beyond WBR / Monthly P&L / ClickUp.

## Current operational notes

1. Supabase MCP auth was re-established locally on 2026-03-23 (ET):
   - `codex mcp logout supabase`
   - `codex mcp login supabase`
   - `codex mcp list` recovered and now shows `supabase` with `Auth = OAuth`
   - if an existing Codex session still reports `Auth required` when using the
     Supabase MCP, treat that as stale session state and start a fresh Codex
     session before concluding the MCP is broken
2. Supabase MCP re-auth reminder as of 2026-03-30 (ET):
   - the current thread ended in the same stale-session pattern again
   - the intended recovery remains:
     - `codex mcp logout supabase`
     - `codex mcp login supabase`
     - `codex mcp list`
   - after that, start a **fresh Codex session** rather than trying to reuse
     the old one
3. Monthly P&L active debugging focus as of 2026-03-24 (ET):
   - next session should start with the remaining **US P&L unmapped
     transactions**
   - the current Monthly P&L handoff/prompt have been updated to reflect the
     recent Lifestyle CA inbound-carrier rule gap and the exact Supabase MCP
     caveat above
4. WBR Amazon Ads Lifestyle triage update as of 2026-03-25 (ET):
   - Lifestyle US remains the confirmed wrong-profile case that was fixed by
     re-selecting the correct advertiser profile
   - Lifestyle CA was rechecked against a March 16 Amazon campaign export, and
     the live DB matched the export exactly for both spend (`80.37 CAD`) and
     sales (`267.58 CAD`)
   - that dedicated triage thread is now historical/reference rather than the
     primary active WBR restart path
5. Supabase Python client warning follow-up as of 2026-03-26 (ET):
   - the current backend warning is from the older `supabase==2.6.0` Python
     dependency chain still pulling `gotrue`
   - the Claude MCP auth work this week was OAuth/JWKS compatibility, not a
     Python client migration
   - the tracked upgrade follow-up should not require mass re-auth of Amazon
     Ads or Windsor accounts because those credentials are stored in database
     rows
6. Search Term Automation current state as of 2026-03-30 (ET):
   - Stage 1 `Search Term Automation` controls are live on
     `/reports/client-data-access/[clientSlug]`
   - Stage 2 `Search Term Data` is live on
     `/reports/search-term-data/[clientSlug]`
   - STR ingestion was refactored away from inherited WBR campaign-sync
     assumptions and now uses an Amazon Ads-native contract for the verified
     `spSearchTerm` path
   - current supported scope is **Sponsored Products only**; SB / SD remain
     intentionally unverified / unsupported until their exact report contracts
     are confirmed
   - `search_term_daily_facts` now preserves `keyword_id`, `keyword`,
     `keyword_type`, and `targeting`
   - STR UI now auto-refreshes every 15 seconds while runs are in `running`
     state, mirroring the WBR Ads sync experience
   - post-worker-redeploy live validation is now confirmed on a real Whoosh US
     Sponsored Products backfill:
     - three successful chunks covering `2026-03-01` through `2026-03-26`
     - `search_term_daily_facts` loaded `10,436` SP rows with the expected
       keyword/targeting shape
     - a real Amazon Ads Sponsored Products search-term CSV for
       `2026-03-01` through `2026-03-10` matched the stored DB totals
       essentially exactly (`410,267` export impressions vs `410,261` in DB;
       clicks / spend / orders / sales matched)
   - do not compare STR facts to broader Sponsored Products Campaign Manager
     totals when validating impressions:
     - Amazon search-term exports appear to include only search terms that
       generated at least one click
     - broader SP console totals can therefore show materially higher
       impressions than STR facts while clicks / spend / sales still line up
   - legacy Pacvue "search term report" files can contain mixed `SP`, `SB`,
     and `SD` rows in one export:
     - that mixed Pacvue shape is useful for understanding the old workflow
     - it is **not** evidence that Amazon-native `SP`, `SB`, and `SD` use the
       same report family or should share one implementation contract
   - the first live backend-only SB contract probe has now been run on Whoosh
     US (March 27, 2026):
     - Amazon accepted `adProduct = SPONSORED_BRANDS`
     - Amazon accepted `reportTypeId = sbSearchTerm`
     - Amazon accepted `groupBy = ["searchTerm"]`
     - Amazon rejected `groupBy = ["campaign"]` for `sbSearchTerm`
     - Amazon rejected guessed SP-style columns such as `keyword` and
       `targeting`
     - Amazon accepted this candidate SB column set:
       - `date`
       - `campaignId`
       - `campaignName`
       - `adGroupId`
       - `adGroupName`
       - `keywordId`
       - `keywordText`
       - `keywordType`
       - `matchType`
       - `searchTerm`
       - `impressions`
       - `clicks`
       - `cost`
       - `purchases`
       - `sales`
       - `adKeywordStatus`
     - accepted live SB probe report ids:
       - `e1389546-cf24-4f62-8e1f-c0b01986ed6d`
       - `946b80e9-98b9-4216-a60e-2cc9c0c6a891`
     - both accepted reports later completed successfully with `283` rows each
     - observed minimal payload keys:
       - `date`
       - `campaignId`
       - `campaignName`
       - `searchTerm`
       - `impressions`
       - `clicks`
       - `cost`
       - `purchases`
       - `sales`
     - observed richer payload keys:
       - `date`
       - `campaignId`
       - `campaignName`
       - `adGroupId`
       - `adGroupName`
       - `keywordId`
       - `keywordText`
       - `keywordType`
       - `matchType`
       - `searchTerm`
       - `impressions`
       - `clicks`
       - `cost`
       - `purchases`
       - `sales`
       - `adKeywordStatus`
   - the first productized live SB backfill also ran on Whoosh US for
     `2026-03-25` through `2026-03-26`:
     - run id: `7d7c5a55-538a-4d6c-a959-5d08ce314af4`
     - DB totals landed as:
       - `283` rows
       - `28,829` impressions
       - `474` clicks
       - `$989.97` spend
       - `128` orders
       - `$2,158.26` sales
   - manual Amazon `Sponsored Brands > Search term > Daily` export for the
     same Whoosh US window did **not** fully match the DB:
     - export totals:
       - `305` rows
       - `29,433` impressions
       - `550` clicks
       - `$1,066.07` spend
       - `176` orders
       - `$2,985.96` sales
     - exact delta versus DB:
       - `+22` rows
       - `+604` impressions
       - `+76` clicks
       - `+$76.10` spend
       - `+48` orders
       - `+$827.70` sales
   - that delta localizes exactly to one missing campaign:
     - `Screen Shine - Pro | Brand | SB | PC-Store | MKW | Br.M | Mix. | Def`
   - raw Amazon `sbSearchTerm` payload was checked directly for the successful
     Whoosh US run and the campaign was absent there too:
     - raw row count: `283`
     - matching raw rows for that campaign: `0`
   - conclusion as of March 27, 2026:
     - this is **not** currently an ingest/parser bug in our SB path
     - the native `sbSearchTerm` API payload appears narrower than the Amazon
       console/export surface for at least one SB campaign family
     - SB should remain **not yet validated**
   - current best hypothesis:
     - the missing campaign is a branded defensive SB family
     - likely manual-keyword-targeted, store-destination / product-collection-
       style creative (`PC-Store` in internal naming)
     - stronger current read: this may be a **legacy Sponsored Brands**
       campaign family rather than a general SB parser issue
     - screenshot evidence shows the campaign was created on `2019-12-04`
     - multiple third-party Amazon Ads integrators document that Amazon v3
       Sponsored Brands reporting does not fully support legacy /
       single-ad-group SB campaigns
   - current best interpretation is that this specific campaign family may
   - `/ngram-2` current state:
     - native SP preflight summary is live
     - page was simplified to a single-column Step 1 / 2 / 3 flow
     - AI preview now uses **AI-first product matching** from the Windsor child
       ASIN catalog inside the same call as term evaluation rather than a
       deterministic pre-match gate
     - AI preview output is now validated strictly before synthesis:
       malformed JSON, bad ASINs, missing term rows, duplicate term rows, or
       contradictory confidence/product states hard-fail instead of silently
       degrading
     - the preview-budget bug was fixed:
       intentionally skipped brand/mix/defensive campaigns no longer consume
       the top-6 preview slots; the route now walks past them to the next
       runnable campaigns
     - both recent `/ngram-2` changes are frontend-service-only because the
       preview route lives under Next.js at
       `frontend-web/src/app/api/ngram-2/ai-prefill-preview/route.ts`
     - immediate next-session goal:
       after fresh Supabase MCP auth and a fresh Codex session, inspect live
       `/ngram-2` AI preview behavior on real profiles and decide whether the
       next issue is prompt/model quality, skip taxonomy, or workbook-prefill
       tuning
       be omitted from the native `sbSearchTerm` API while still appearing in
       Amazon console/export surfaces
   - screenshots/export inspection confirmed:
     - campaign type is `Sponsored Brands`
     - campaign targeting is `MANUAL`
     - campaign is not video
     - search-term export rows for the missing campaign show:
       - `Targeting = whoosh`
       - `Match Type = EXACT`
       - `Customer Search Term = whoosh`
   - overnight follow-up plan:
     - Whoosh US and CA now have nightly sync enabled for both `SP` and `SB`
     - re-check tomorrow whether the same SB campaign remains absent from the
       native API while still present in the Amazon export
     - if still absent, treat this as a real Amazon-side contract/surface gap,
       not a one-day freshness lag
   - post-redeploy overnight sync health check on March 28, 2026:
     - the latest completed overnight STR runs for the requested profiles all
       persisted facts correctly by `sync_run_id`
     - verified healthy:
       - Whoosh US `SP`
       - Whoosh US `SB`
       - Whoosh CA `SP`
       - Whoosh CA `SB`
       - Ahimsa US `SP`
       - Ahimsa US `SB`
       - Distex CA `SP`
     - for each of those completed runs:
       - `wbr_sync_runs.status = success`
       - `rows_loaded` matched the number of persisted
         `search_term_daily_facts` rows for that exact `sync_run_id`
       - fact windows currently span the requested overnight date range and
         land through `2026-03-27` (expected for an early-morning March 28
         refresh)
     - this strongly suggests the earlier “run says success but no facts
       persisted” issue was a stale `worker-sync` deployment problem rather
       than a continuing storage bug in the current code
   - Ahimsa US now provides a clean SB counterexample to the Whoosh mismatch:
     - Amazon `Sponsored Brands > Search term > Daily` export for
       `2026-03-15` through `2026-03-21` matched the stored DB totals exactly
     - exact matched totals:
       - `567` rows
       - `69,544` impressions
       - `809` clicks
       - `$805.81` spend
       - `64` orders
       - `$3,048.50` sales
     - campaign-level spot checks matched too, including a branded defensive
       `SB | PC-Store` campaign:
       - `Mealtime Sets - Balanced Bites-$P | Brand | SB | PC-Store | MKW | Ph. | Mix. | Def`
       - `22` rows / `7,140` impressions / `39` clicks / `$31.64` spend /
         `11` orders / `$593.66` sales
   - implication after the Ahimsa validation:
     - `SB` ingestion is not failing generically
     - the repeated Whoosh US gap is now more likely a campaign-specific
       Amazon reporting limitation than a broad SB parser/storage issue
     - this materially strengthens the current hypothesis that the missing
       Whoosh campaign is legacy Sponsored Brands inventory
   - current recommended next-session priority:
     - keep productizing the trusted `SP` path in `/ngram-2`
     - do not block the operator rollout on full legacy `SB` parity
     - continue `SB` validation opportunistically on modern accounts while
       messaging legacy caveats clearly
   - product framing update:
     - the next operator-facing milestone should not be a generic search-term
     dashboard or Pacvue clone
     - the preferred direction is a native replacement of the current N-Gram
       workflow:
       - native data selection instead of Pacvue export/upload
       - same practical workbook generation path
       - optional AI-assisted path beside the manual path
       - current manager review/export habits preserved until trust is earned
     - detailed operator-flow framing now lives in:
       [N-Gram native replacement plan](/Users/jeff/code/agency-os/docs/ngram_native_replacement_plan.md)
   - pre-worker-redeploy STR runs remain untrustworthy validation evidence
6. N-Gram 2.0 native Step 1 replacement milestone as of 2026-03-27 (ET):
   - `/ngram-2` now exists as a separate experimental route and does **not**
     modify the legacy `/ngram` surface
   - current native workbook generation is intentionally `SP` only
   - the native workbook path now shares the same campaign/workbook builder as
     the legacy `/ngram` upload flow, so workbook construction behavior stays
     aligned
   - live operator validation has now happened end to end:
     - a native workbook was generated successfully from `/ngram-2`
     - that workbook was then uploaded into Step 2 of the existing `/ngram`
       tool
     - the legacy Step 2 flow accepted the workbook and returned the expected
       output
   - practical conclusion:
     - native Agency OS data can now replace the Pacvue export for the first
       step of the current SP N-Gram workflow without forcing a new downstream
       review/publishing process
7. Supabase MCP local auth restart note:
   - if Supabase MCP tools are unavailable in a Codex session, run:
     `codex mcp logout supabase`
   - then:
     `codex mcp login supabase`
   - confirm with:
     `codex mcp list`
   - then start a fresh Codex session if the current one still behaves as if
     Supabase auth is missing

## Historical/reference docs

1. [WBR v2 handoff](/Users/jeff/code/agency-os/docs/wbr_v2_handoff.md)
   - Historical shipped-state/debug reference for WBR.
   - WBR is stable for now; this is no longer the primary restart doc.
2. [WBR Ads profile triage handoff](/Users/jeff/code/agency-os/docs/wbr_ads_profile_triage_handoff.md)
   - Historical/reference record for the resolved Lifestyle US/CA Amazon Ads
     triage thread, including the March 25 CA export-vs-DB validation.
3. [WBR Ads profile triage resume prompt](/Users/jeff/code/agency-os/docs/wbr_ads_profile_triage_resume_prompt.md)
   - Historical restart prompt for that resolved triage thread if a new
     discrepancy appears later.
4. [PnL YoY implementation plan](/Users/jeff/code/agency-os/docs/pnl_yoy_implementation_plan.md)
   - Historical implementation record for the now-shipped YoY architecture.
5. [Archived session prompts](/Users/jeff/code/agency-os/docs/archive/session_prompts)
   - Historical prompts from active build/debug phases.
6. [Older archived non-The-Claw docs](/Users/jeff/code/agency-os/docs/archive/non_agencyclaw/README.md)
   - Historical product/build docs no longer meant to be the active entrypoint.

## Rule of thumb

1. Treat code as the canonical current state.
2. Use handoff docs only when they add operational context, validation notes,
   or restart guidance that code alone does not show.
3. When a workstream becomes stable, demote its handoff docs into historical or
   reference status instead of treating them as evergreen restart docs.
