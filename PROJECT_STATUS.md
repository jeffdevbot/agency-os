# Changelog — Ecomlabs Tools

_Last updated: 2026-03-30 (ET)_

> Development history for the project. For setup instructions and project overview, see [AGENTS.md](AGENTS.md).

---

## 2026-03-30 (ET)
- **`/ngram-2` preview now has a dedicated model lane and deterministic temperature:** Step 3 no longer has to inherit the generic frontend OpenAI primary model; the preview route now reads `OPENAI_MODEL_NGRAM` explicitly and runs at `temperature = 0` to reduce quality jitter between repeated runs on the same campaign/window.
- **The AI-prefilled workbook now writes negatives more like a human-filled N-Gram sheet:** `NEGATE` terms with 1/2/3 cleaned words now drop directly into the scratchpad `Monogram` / `Bigram` / `Trigram` columns, while longer `NEGATE` terms prefill the search-term row itself as exact `NE`; this uses the existing workbook formulas instead of inventing a separate AI-only marking pattern.
- **Saved Step 3 previews now feed the AI-prefilled workbook path directly:** The `/ngram-2` preview route now returns the persisted `preview_run_id`, the AI-prefilled workbook request can reuse that exact saved run instead of depending only on transient browser state, and the backend rejects mismatched saved runs rather than silently drifting to a different selection.
- **The AI-prefilled workbook now carries compact review context without breaking the familiar N-Gram layout:** Search-term tables keep their existing structure and now append `AI Recommendation`, `AI Confidence`, and `AI Reason` columns, summary metadata records the linked preview run id / model / threshold, and the scratchpad area shifts one extra spacer column right to preserve readability and workbook compatibility.
- **`/ngram-2` Step 3 is now in a good shipped-validation state for the current SP preview slice:** Whoosh CA now has Windsor child-ASIN catalog data, the GPT-5 frontend adapter path is fixed, live previews succeeded on `gpt-5.4-mini`, and successful preview payloads now persist in `ngram_ai_preview_runs` instead of existing only in the browser response.
- **N-Gram AI preview reason tags are now a strict enum instead of model-invented slugs:** The prompt and validator now require every `reason_tag` to be exactly one of `core_use_case`, `wrong_category`, `wrong_product_form`, `wrong_size_variant`, `wrong_audience_theme`, `competitor_brand`, `cloth_primary_intent`, `accessory_only_intent`, `foreign_language`, or `ambiguous_intent`; anything else hard-fails the preview contract.
- **`/ngram-2` AI preview now uses AI-first product identification instead of a deterministic match gate:** The Step 3 preview path in the Next.js frontend now sends the campaign name, Windsor child-ASIN catalog context, and above-threshold search terms in one AI call, and expects one structured response that contains both the matched product and the term-level recommendations.
- **N-Gram AI preview now fails loudly on malformed model output instead of silently degrading into bad synthesis:** Added strict validation of the AI response contract before gram synthesis so malformed JSON, catalog mismatches, missing term rows, duplicate term rows, or contradictory confidence/product states stop the preview rather than leaking bad data into workbook prefills.
- **The `/ngram-2` AI preview budget bug was fixed:** Intentionally skipped brand / mix / defensive campaigns no longer consume the top-6 preview slots; the route now walks past those lanes and uses the highest-spend runnable campaigns for the actual AI preview surface.
- **Today’s `/ngram-2` AI-preview work remained frontend-service-heavy by design:** The live preview endpoint still lives under `frontend-web/src/app/api/ngram-2/ai-prefill-preview/route.ts`, so the prompt/adapter/persistence changes redeploy through the `frontend-web` Render service.
- **Current next-session product target:** The trusted preview surface is now wired into workbook prefill; the next useful work should focus on reviewed-workbook override logging and calibration rather than reopening catalog/model plumbing that is now working.

## 2026-03-27 (ET)
- **Sponsored Brands now has a strong live counterexample showing the Whoosh mismatch is likely legacy-campaign-specific, not a general ingestion failure:** Ahimsa US `SB` for `2026-03-15` through `2026-03-21` was validated against a real Amazon `Sponsored Brands > Search term > Daily` export, and the DB matched exactly on rows (`567`), impressions (`69,544`), clicks (`809`), spend (`$805.81`), orders (`64`), and sales (`$3,048.50`), including a branded defensive `SB | PC-Store` campaign. This materially strengthens the theory that the repeated missing Whoosh US campaign is legacy Sponsored Brands inventory omitted by Amazon’s v3 reporting surface rather than a broad SB parser/storage bug.
- **Post-redeploy overnight STR health is now confirmed across multiple live profiles:** The latest completed overnight search-term runs for Whoosh US/CA (`SP` + `SB`), Ahimsa US (`SP` + `SB`), and Distex CA (`SP`) were checked against persisted `search_term_daily_facts`, and each successful run wrote the expected number of fact rows for its exact `sync_run_id`.
- **The earlier “run says success but no facts persisted” behavior now looks like a stale worker issue, not a standing code bug:** After redeploying `worker-sync`, the latest overnight runs finalized cleanly and the persisted fact counts matched `rows_loaded` on the run records.
- **N-Gram 2.0 has now completed the first real native replacement loop for Sponsored Products:** A native workbook was generated successfully from the new separate `/ngram-2` flow using Agency OS STR data, then uploaded into Step 2 of the existing `/ngram` tool, and the legacy downstream flow accepted it and returned the expected workbook output.
- **This proves the current Pacvue export is no longer required for Step 1 of the SP N-Gram workflow:** The team can now generate a workbook from native Agency OS data while preserving compatibility with the existing Step 2 review/export process, which materially lowers adoption risk for the first rollout of the native replacement path.
- **Native workbook generation is now aligned with the legacy workbook-construction path:** The native and upload-driven flows now share the same campaign/workbook builder, and the STR overwrite bug that previously allowed SB runs to wipe SP facts for the same profile/date window has been fixed by scoping fact replacement to `ad_product`.
- **Search Term Automation SP-only ingestion is now live-validated end to end:** A real post-worker-redeploy Sponsored Products backfill for Whoosh US completed successfully across three chunks covering `2026-03-01` through `2026-03-26`, and `search_term_daily_facts` now holds `10,436` stored SP rows for that account with the Amazon-native keyword dimensions preserved.
- **The new STR row shape is confirmed against a real Amazon export, not just internal expectations:** A Whoosh US Amazon Ads Sponsored Products search-term CSV for `2026-03-01` through `2026-03-10` matched the stored DB totals essentially exactly (`410,267` export impressions vs `410,261` in DB, with clicks / spend / orders / sales matching), validating both the ingestion contract and the new dedup key that preserves distinct `keyword_id` / `targeting` rows.
- **The remaining STR impression discrepancy was explained and is not a pipeline bug:** Broader Sponsored Products Campaign Manager totals can show materially higher impressions than the search-term export because Amazon’s search-term reporting surface appears limited to search terms that generated at least one click. Future STR validation should therefore compare against Amazon `Search term` exports, not broader SP console totals.

## 2026-03-25 (ET)
- **Claude/Agency OS ClickUp MCP can now edit existing mapped tasks, not just inspect or create them:** Added `update_clickup_task` to the shared Claude tool belt so the pilot surface can safely fetch a mapped task by id/URL, scope-check it against allowed Agency OS backlog destinations, and update title, description, or assignee through the same local assignee-resolution rules already used for creates.
- **Claude/Agency OS ClickUp MCP is now live in the Jeff-only pilot and ready for user testing:** The shared Claude surface now includes `list_clickup_tasks`, `get_clickup_task`, `resolve_team_member`, `prepare_clickup_task`, and `create_clickup_task`, with destination routing owned by Command Center, fail-closed brand/assignee resolution, and task-link scoping limited to mapped Agency OS brand backlog destinations.
- **The Claude Project bundle now covers ClickUp alongside WBR and Monthly P&L:** Added a dedicated `docs/claude_project/clickup_mcp_playbook.md` plus refreshed Claude Project instructions/README guidance so the live shared Claude surface has operator-facing usage docs for task review, task inspection, assignee resolution, preview, and create flows.
- **ClickUp MCP moved out of planning and into live-testing status:** The ClickUp plan/handoff docs now describe the slice buildout as implemented, the next work is no longer “ship the tool belt,” and the immediate phase is real pilot usage plus follow-on hardening only if testing exposes pain.
- **Lifestyle CA WBR Amazon Ads validation now has a concrete day-level win:** Live Supabase facts for the Lifestyle CA WBR profile were checked against a fresh Amazon Ads campaign export for `2026-03-16`, and the DB matched the export exactly for both ad spend (`80.37 CAD`) and ad-attributed sales (`267.58 CAD`).
- **The old open CA triage question is no longer “does the DB match the export for the checked day?”** The checked March 16 campaign-level rows now line up exactly between `wbr_ads_campaign_daily` and the Amazon CSV export, including the three non-zero-sales campaigns and their spend / sales values.
- **The Lifestyle US/CA Amazon Ads profile triage docs were updated to reflect the resolved validation state:** The dedicated CA triage handoff/prompt are now historical reference rather than the primary active restart thread, while preserving the operational notes about the earlier US wrong-profile fix and the March 25 CA validation result.

## 2026-03-24 (ET)
- **Team Hours is now a real shipped Command Center surface, not just backlog planning:** The admin-only page at `/command-center/hours` is already wired end to end with a backend ClickUp time-entry report, Team Members / Clients views, stacked daily charting, unmapped cleanup sections, and deep links back into Command Center records.
- **Team Hours now exports CSV from the live page:** Added client-side export of the current Team Members or Clients view, including summary, nested series/daily breakdown rows, and unmapped user/space rows, plus focused Vitest coverage for the export shape.
- **Team Hours docs were updated to match reality:** The root `README`, `docs/team_hours_plan.md`, `docs/opportunity_backlog.md`, and `docs/current_handoffs.md` now describe Team Hours as shipped rather than as the next unbuilt feature.

## 2026-03-23 (ET)
- **Claude/Agency OS Monthly P&L is now live beyond read-only analysis:** The shared `resolve_client` workflow now routes cleanly into Monthly P&L, the first read-only P&L MCP slice (`list_monthly_pnl_profiles`, `get_monthly_pnl_report`) is working in Claude, and the shared Claude Project bundle now covers both WBR and Monthly P&L instead of staying WBR-only.
- **Monthly P&L client-email drafting is now live in Claude:** Added a structured read-only brief layer plus persisted `draft_monthly_pnl_email` support on top of canonical Monthly P&L report data, along with the supporting prompt contract, persistence migration, and Claude Project guidance.
- **Monthly P&L YoY is now shipped as a real product surface:** Added the shared backend comparison layer, the frontend `Standard` / `YoY` mode, `% of Revenue` support in YoY, dashed prior-year chart series, and YoY Excel export without creating a separate Claude-only comparison stack.
- **A real Render/runtime regression in the new P&L brief path was found and fixed immediately:** The first brief-builder version fanned out too many nested report builds in parallel, which surfaced in Claude as `[Errno 11] Resource temporarily unavailable`; the brief path now runs sequentially and the live Claude brief/draft flow recovered after deploy.
- **WBR snapshot freshness is now hardened end to end for the Claude/The Claw path:** `worker-sync` now refreshes snapshots as part of the WBR sync lifecycle, Windsor refreshes defer snapshot creation when Amazon Ads data is still pending, and successful Amazon Ads finalize runs now create the fresh snapshot automatically.
- **Amazon Ads WBR refreshes are more resilient under real throttling/duplicate conditions:** The Amazon Ads sync path now persists report-job state incrementally, treats `429 Throttled` as retryable, reuses Amazon's existing report id on `425 duplicate`, and keeps polling instead of losing partial progress and forcing manual reruns.
- **WBR snapshot reads now self-heal if sync freshness gets ahead of snapshot creation:** `WBRSnapshotService.get_or_create_snapshot(...)` now rebuilds a stale snapshot when a newer successful Windsor or Amazon Ads sync has already finished, so Claude does not stay pinned to an old digest if the background snapshot write is missed.
- **Live validation confirmed the repaired Distex CA WBR sync path:** A fresh Distex CA overnight cycle now shows Windsor `daily_refresh` success, Amazon Ads `daily_refresh` success, `ads_snapshot_refresh.status = success`, and a new latest snapshot with `week_ending = 2026-03-21`.
- **The Claude WBR hardening pass is effectively complete for now:** Real pilot usage showed the main remaining issues are response restraint and sequencing polish rather than hallucinated metrics or broken tool flows, so WBR is now stable enough to treat as the completed first Claude slice.
- **The next planned Claude/Agency OS expansion is no longer speculative Monthly P&L work:** That slice is now shipped in an initial production-ready form, so the next step should be refinement or the next adjacent reporting capability rather than re-litigating whether P&L belongs in Claude.

## 2026-03-21 (ET)
- **Claude Pro remote MCP pilot is now live end to end for Jeff:** The private `Agency OS` connector can now authenticate through Supabase OAuth, connect from Claude web, and successfully run the first WBR tool belt (`resolve_client`, `list_wbr_profiles`, `get_wbr_summary`, `draft_wbr_email`) against live Agency OS data.
- **Agency OS now has its first LLM-native primary surface in production-like use:** Claude Project setup was narrowed to a compact WBR-focused knowledge bundle under `docs/claude_project/`, giving the pilot a durable instruction layer without uploading large product strategy docs into Claude.
- **Supabase OAuth server setup was completed for Claude remote MCP:** Added the custom consent page at `frontend-web/src/app/oauth/consent/`, enabled dynamic OAuth app registration, and verified the real auth flow through Claude and Supabase.
- **MCP auth hardening landed before JWT key rotation:** `backend-core/app/auth.py` now supports asymmetric Supabase JWT verification via cached JWKS with legacy `HS256` fallback, so normal backend-protected routes remain compatible while Supabase signs new OAuth/OIDC tokens with ECC keys.
- **Supabase JWT signing was rotated safely to asymmetric keys:** The project now uses an ECC (`P-256`) current signing key while the legacy `HS256` key remains in the previous-key set for verification of non-expired older tokens.
- **OAuth state signing was decoupled from Supabase JWT mode:** Amazon Ads and SP-API state signing now prefer `OAUTH_STATE_SIGNING_SECRET` with fallback to `SUPABASE_JWT_SECRET`, reducing accidental coupling between internal OAuth state protection and Supabase JWT signing strategy.
- **Claude pilot smoke tests succeeded on real workflows:** Jeff validated client resolution, WBR marketplace lookup, MX WBR summary retrieval for Basari, and persisted WBR email draft creation for Whoosh from inside Claude web.

## 2026-03-19 (ET)
- **The Claw now delivers live WBR summaries in Slack:** The rebooted `backend-core/app/services/theclaw/` runtime can resolve WBR clients semantically, use bounded multi-step tool loops, and return compact Slack-friendly weekly summaries from stored WBR digests instead of deterministic bridge formatting.
- **The Claw now drafts weekly WBR emails across marketplaces:** Added `wbr_weekly_email_draft` as a Claw skill plus backend `wbr_email_drafts` persistence. Draft generation now gathers all active WBR marketplaces for a client, builds one combined email, stores the draft for traceability, and returns a copy-paste-ready Slack response.
- **WBR email drafts now behave more like real operator drafts:** The Slack output no longer uses code blocks, the prompt now pushes for normal copy/paste-friendly email formatting with headings and bullets, and follow-up instructions like `don't mention inventory` or `add this business context` are now treated as revision constraints rather than ignored style notes.
- **WBR email draft persistence is live in schema and code:** Added migration `20260319000001_add_wbr_email_drafts.sql` with admin-only RLS and idempotent index/policy creation. The production table was created manually after initial migration drift (`team_role` vs `is_admin`) was discovered.
- **The Claw operational visibility improved materially:** Added structured-but-sanitized turn/tool logs plus shared `ai_token_usage` logging for both skill selection and skill execution calls. This made live debugging of WBR client resolution and model fallback practical.
- **GPT-5 mini is now working as The Claw primary model:** The Claw OpenAI adapter now handles GPT-5-family request differences (`max_completion_tokens`, no `temperature`, `reasoning_effort=low`) and newer content-part response shapes. Live `ai_token_usage` rows now show `gpt-5-mini-2025-08-07` for both skill-selection and skill-execution phases instead of silent fallback to `gpt-4o`.
- **The Claw WBR fuzzy-name resolution improved enough for live use:** The current prompt/tool-contract path can now infer canonical WBR client names such as `Basari` → `Basari World` through `list_wbr_profiles` rather than requiring rigid exact-name input.
- **Slack scope remains intentionally narrow:** The currently shipped `theclaw/` Slack runtime only processes DM events (`channel_type == "im"`). Channel messages and `app_mention` flows are not implemented yet.

## 2026-03-18 (ET)
- **Shared Reports/API Access shipped as the new auth surface:** Added shared `report_api_connections` storage, launched admin `/reports/api-access`, and moved Amazon Ads connection visibility/launch into that shared reporting surface without removing WBR-owned advertiser profile selection.
- **Amazon Seller API auth scaffolding is now live end to end:** Added signed state, public callback handling, shared connection persistence, Seller API validation via `getMarketplaceParticipations`, and a P&L-first finances smoke test via `listFinancialEventGroups` plus `listTransactions`.
- **SP-API hardening landed before live testing:** Seller auth/validation now route by explicit region (`NA` / `EU` / `FE`), redirect errors are surfaced back into the UI, and shared connection health is no longer inferred from row existence alone.
- **WBR safety was preserved during the shared-auth migration:** WBR Amazon Ads now prefers healthy shared credentials but falls back to legacy `wbr_amazon_ads_connections` when the shared row is absent or unhealthy. Windsor-backed WBR behavior and manual Monthly P&L CSV upload mode remain intact.
- **Production schema gap was fixed live:** The initial `/reports/api-access` failure was traced to a missing `report_api_connections` migration in production; the additive migration was then applied to Supabase so the page could load real clients.
- **Frontend deploy stability was hardened on Render:** A Render build failure caused by a broken default Node `22.16.0` image was resolved by pinning the frontend runtime to `20.19.0` via `frontend-web/package.json` and `frontend-web/.node-version`.
- **Current SP-API blocker is Amazon-side approval/configuration:** Live seller auth reached Amazon but hit app-side errors (`MD1000`, then `MD9100`). Draft testing now uses `AMAZON_SPAPI_DRAFT_APP=true`, and the remaining blocker is public-app approval plus correct Amazon app Login URI / Redirect URI configuration.

## 2026-03-17 (ET)
- **WBR Section 2 ad-type drilldowns shipped:** Section 2 Advertising rows can now expand inline under parent or leaf rows to show `Sponsored Products`, `Sponsored Brands`, and `Sponsored Display` breakdown rows with chevron controls. The breakdowns reuse the existing report payload, keep `TACoS` blank at the subtype level to avoid implying unavailable total-sales attribution, and passed the backend WBR suite plus frontend type/test coverage before push.
- **Monthly P&L Excel export is now live:** The report header now exports an XLSX workbook that mirrors the selected report window and totals setting, with a `Dollars` tab and a `% of Revenue` tab, WBR-style workbook formatting, marketplace-derived currency labels, accounting-style negative number formatting, and range-aware filenames such as `distex-ca-pnl-jan2025-dec2025.xlsx`.
- **Monthly P&L reporting polish continued across UI and workbook output:** New P&L profiles now default currency by marketplace, the shared reports shell/table spacing was tightened for wider month visibility, P&L values now use accounting parentheses and whole-number display, the refund band in `% of Revenue` now uses `Total Gross Revenue` while lower expense rows continue to use `Total Net Revenue`, and the report now appends `Payout ($)` / `Payout (%)` rows from the existing `non_pnl_transfer` bucket.
- **Amazon P&L SKU-based COGS is now live end to end:** Applied `20260317023402_add_monthly_pnl_sku_cogs_and_unit_summaries.sql`, finished the SKU-unit summary import path, and shipped the settings workflow for one fixed unit cost per sold SKU. User validation confirmed that entered SKU costs now flow through to visible COGS on the report.
- **Amazon P&L v2 UX/reporting controls shipped:** Added `Dollars` vs `% of Revenue`, a totals toggle, a larger header month-range picker, `Amazon P&L` naming, more prominent account/marketplace context, and import-history cleanup with source-type labels plus `See more`.
- **Monthly P&L importer was decomposed out of god-file territory:** Split CSV parsing, ledger expansion, model types, SKU-unit aggregation, and persistence into focused modules and reduced `transaction_import.py` from roughly `1430` lines to about `529` while keeping the Monthly P&L backend suite green.
- **Whoosh US 2025 Monthly P&L coverage is now complete on the validation profile:** Jan-Mar and Apr-Jun multi-month uploads completed successfully, joining the already validated Jul-Dec coverage. The active/validated profile now spans Jan-Dec 2025 for Whoosh US.
- **WBR hardening continued across sync/admin/report flows:** Added future-date validation for Windsor business and Amazon Ads backfills, improved Pacvue upload messaging, allowed deletion of Pacvue-only mapped leaf rows, batched large ASIN mapping CSV imports, paginated WBR business fact reads in Sections 1 and 3, and added a Section 2-only `Unmapped / Legacy Campaigns` row so advertising totals stay truthful even when legacy campaigns are untagged.
- **Monthly P&L first-pass CA ingest compatibility landed:** Updated the transaction parser for CA `a.m./p.m.` timestamps and extra amount columns, made exact-field mapping rules case-insensitive for CA label drift like `Cost of advertising` / `Amazon fees`, added focused CA backend coverage, and pushed the code on `main` in commit `d4f4874`.
- **CA global Monthly P&L mapping rules are now seeded live:** Applied live migration `20260317150607_seed_monthly_pnl_ca_mapping_rules`, which copied the shipped global US transaction-upload mapping rules into `CA` without changing the validated US imports.
- **Monthly P&L async import UX is now hardened end to end:** The worker path now records progress/heartbeat metadata in `raw_meta`, marks failed background imports as `error` instead of leaving them stranded in `running`, and the frontend settings/upload UI now shows queued/running detail instead of silently waiting.
- **Whoosh CA Monthly P&L is now live and manually validated:** A real Jan 2026 CA month was reconciled successfully, Feb 2026 imported cleanly, and the active Whoosh CA profile now covers `2026-01-01` through `2026-02-01`.
- **Distex CA Monthly P&L backfill is now live from Jan 2024 through Feb 2026:** Multi-range CA uploads were imported successfully into the live Distex CA profile, providing active backfill coverage from `2024-01-01` through `2026-02-01`.
- **Observed CA unmapped transaction variants were closed out live:** Applied `20260317154748_add_monthly_pnl_fulfilment_removal_prefix_rule` and `20260317161435_add_monthly_pnl_ca_label_variants` to map real CA labels such as removal-order disposal fees, coupon redemption fees, Vine enrolment fees, and FBA prep fees. Active CA months on Whoosh and Distex now sit at `unmapped_amount = 0`.
- **Monthly P&L COGS settings got the first bulk-edit ergonomics pass:** The COGS card now collapses long SKU lists, supports `See more`, and adds CSV export/import round-trips so operators can bulk-edit SKU unit costs without manual row-by-row web entry.
- **Monthly P&L other expenses are now live:** Applied `20260317165228_add_monthly_pnl_other_expenses`, adding manual monthly `FBM Fulfillment Fees` and `Agency Fees` rows with per-profile show/hide toggles plus CSV export/import in the settings panel. Enabled rows now flow into `Total Expenses` and `Net Earnings` without affecting Amazon ingest.
- **Monthly P&L presentation polish continued:** Removed the misleading hardcoded currency label from the `/reports` hub P&L card and fixed the totals-column contrast bug on the `Contribution Profit` row so the summary cell styling stays readable.

## 2026-03-16 (ET)
- **Monthly P&L wide-range report root cause was identified and fixed at the DB layer:** Live investigation showed the validation profile had about `1.5M` ledger rows and the report RPC had been regressed by a later migration back to an `EXISTS` shape that still scanned the raw ledger, taking about `7.3s` for `2025-01-01` through `2026-02-01`. Added and applied `20260316182035_add_monthly_pnl_import_month_bucket_totals.sql`, which backfills per-import-month bucket totals and rewires `pnl_report_bucket_totals(...)` to read those summaries instead. The same wide range now executes at about `4.5ms` at the SQL function boundary.
- **Monthly P&L imports are now queued/background-ready in code:** Refactored the transaction upload path to stage source files into the existing private `monthly-pnl-imports` bucket, create pending async imports, and let `worker-sync` process them later via the new `PNLImportWorkerService`. Import execution now persists `monthly_pnl_import_month_bucket_totals` as part of the pipeline, and the upload UI now tells operators the file was queued for background processing.
- **Monthly P&L backfill exposed the next scale blockers clearly:** Single-month backfills now work for the current validation client across July through December 2025, with November and December explicitly validated to the penny. But the first multi-month backfill attempts (`jan-mar2025-whoosh-us.csv` and `apr-june2025-whoosh-us.csv`) stranded partial active/error/pending month state because the import still runs inside one long blocking request.
- **Monthly P&L still needs one more operational pass after the code change:** The DB bottleneck is fixed live, but `backend-core` and `worker-sync` still need deployment for the queued import path and summary-table-first fallback logic. After that deploy, re-check the full `/admin/pnl/.../report` HTTP route and the `/reports/.../pnl` page load against the validation profile.
- **Reporting surface separation cleanup landed:** Clarified the `/reports` UX so WBR and Monthly P&L are presented as sibling reporting products rather than one surface inheriting the other. The top-level `/reports` page now stays client-first, each client marketplace page presents WBR and Monthly P&L as separate cards, and the shared reports header exposes a marketplace-level WBR/P&L switcher.
- **Monthly P&L UX was productized further:** Split the P&L screen out of god-file territory, moved upload/provenance into a subtle settings panel, moved the month-range picker into the header actions, fixed its z-index layering bug, and defaulted the report to the last `3` completed months instead of including the current in-progress month.
- **Monthly P&L now adapts profit framing when COGS is absent:** Removed the noisy missing-COGS warning from the main report surface. When no COGS exists in the selected months, the UI now labels the bottom-line row as `Contribution Profit` and adds `Contribution Margin (%)`; when COGS is present, it adds `Net Margin (%)`.
- **Monthly P&L provenance surfaced in UI:** Added active-import provenance to the Monthly P&L settings panel so operators can see the active source filename, import timestamps, import ID, and covered months for the report period currently in view. Added lightweight source-drift guidance in the upload area to clarify that Amazon download dates can shift settlement coverage.
- **Monthly P&L December 2025 live reconciliation completed:** Applied the pending P&L follow-up migrations live, pushed backend fixes through `main`, and reconciled the validation profile (`c8e854cf-b989-4e3f-8cf4-58a43507c67a`) to the agency manual December workbook using the older source export that the workbook was based on. The active December import is now `c84cade9-6633-427f-b4b0-2371d0aca344`, and live report totals now sit at `total_gross_revenue=339770.20`, `total_refunds=-11314.14`, `total_net_revenue=328456.06`, and `total_expenses=-173735.13`.
- **Monthly P&L November 2025 backfill was unblocked and validated:** Fixed a real importer bug where a single raw row could emit duplicate ledger rows into the same bucket and trip the unique constraint on `(import_id, source_row_index, ledger_bucket)`. The importer now coalesces same-bucket entries per raw row, the November upload succeeds, and the user validated November to the penny.
- **Monthly P&L source-drift root cause confirmed:** The newer Amazon December export (`2025DecMonthlyUnifiedTransaction.csv`) and the older workbook source do not represent the same settlement coverage. The major remaining delta after earlier mapping fixes was therefore not a report bug but a source-artifact mismatch caused by Amazon shifting transactions across settlement periods between download dates.
- **Monthly P&L report performance issue fixed at the DB layer:** The first RPC aggregation version removed Python-side paging, but the RPC still scanned all historical ledger rows for a profile and could take `10s` to `40s` or time out. Added `20260316194500_optimize_monthly_pnl_report_rpc_active_months.sql` to index `monthly_pnl_ledger_entries(import_month_id, entry_month, ledger_bucket)` and rewrite the RPC to resolve active month IDs first. The same profile/report query dropped to sub-`100ms` at the function boundary.
- **Monthly P&L workbook edge cases now covered:** Added workbook-aligned handling for blank-type promo rows (for example `Price Discount - ...`), broader manual-model rule coverage, `Order / other`, `Refund / other`, and `FBA Removal Order: Disposal Fee`. Final related commits on `main`: `fcd0f9e`, `676851d`, and `586c5a9`. Focused backend P&L tests now pass at `74 passed`.

## 2026-03-15 (ET)
- **Monthly P&L Phase 1 foundation shipped:** Added the backfill-first Monthly P&L system for US marketplace. Includes 7 new tables (`monthly_pnl_profiles`, `monthly_pnl_imports`, `monthly_pnl_import_months`, `monthly_pnl_raw_rows`, `monthly_pnl_ledger_entries`, `monthly_pnl_mapping_rules`, `monthly_pnl_cogs_monthly`), a private Supabase Storage bucket for file preservation, RLS + `updated_at` triggers on all tables, seeded US default mapping rules, admin upload endpoint for Amazon Monthly Unified Transaction Report CSVs, CSV parsing with canonical month assignment (`Transaction Release Date` first, `date/time` fallback), ledger expansion with column-based + rule-based bucket mapping, month-slice activation for atomic replacement, duplicate-upload guard via `source_file_sha256`, and 32 new backend tests covering parsing, mapping, expansion, and router behavior (320 total passed).
- **WBR Section 3 inventory + returns is now live on the main report:** Added Windsor-backed inventory snapshots and returns facts, Section 3 report rendering on the primary WBR route, sync-run visibility for `windsor_inventory` and `windsor_returns`, and end-to-end manual validation that Section 3 is now showing real data for the validation account.
- **WBR hardening follow-up added in repo:** Extracted generic WBR sync-run listing into a dedicated service so the router no longer routes all source types through `WindsorBusinessSyncService`, and added a follow-up migration `20260315113000_harden_wbr_section3_sync_constraints.sql` to dynamically replace the `wbr_sync_runs.source_type` CHECK plus enforce Section 3 `sync_run_id` source-type validation.
- **WBR Section 3 schema follow-up applied:** Added and applied `20260314000001_wbr_inventory_and_returns_tables.sql` plus the follow-up `20260315100000_expand_wbr_sync_run_source_types_for_section3.sql` so Section 3 sync runs can be recorded in `wbr_sync_runs`.
- **WBR report UX upgraded significantly:** Replaced stacked sections with report tabs (`Traffic + Sales`, `Advertising`, `Inventory + Returns`), added Excel export of the current WBR as a 3-sheet workbook, and shipped inline trend charts for Sections 1 and 2 with row overlays and toggleable total series.
- **WBR docs and planning artifacts updated:** Refreshed the WBR handoff/docs to match the shipped tabs/export/chart state and added `docs/monthly_pnl_implementation_plan.md` to capture the backfill-first Monthly P&L roadmap.

## 2026-03-14 (ET)
- **WBR Amazon Ads source is live for Section 2:** Added Amazon Ads OAuth connection storage, advertiser-profile selection, sync-run wiring, and Section 2 report rendering on the main WBR route. The current Ads sync supports Sponsored Products, Sponsored Brands, and Sponsored Display ingestion into `wbr_ads_campaign_daily` with `campaign_type` preserved for future split reporting.
- **WBR Section 2 hardening landed:** Added TACoS, admin mapping QA on the Ads sync screen, parser/report-shape hardening, unpaginated fact-query fix, and frontend fetch `no-store` behavior so older week rollups render correctly across the full 4-week window.
- **WBR nightly automation is now implemented:** Added `worker-sync/` background worker, per-profile nightly SP-API and Ads API toggles, and worker-driven `daily_refresh` execution using `wbr_sync_runs` as the operational log.
- **WBR sync ergonomics improved:** Amazon Ads polling now defaults to a 15-minute report wait window, Brand/Display report column definitions were corrected, and enabling either nightly sync toggle on a `draft` profile now auto-promotes it to `active` so the worker will pick it up.
- **WBR Amazon Ads sync now runs as queued background work:** Manual Ads backfills and manual Ads refreshes now enqueue report jobs immediately, persist queued-report progress in `wbr_sync_runs.request_meta`, and let `worker-sync` poll/download/finalize in the background. The Ads sync UI now shows queued/polling/completed progress instead of a long blocking request.

## 2026-03-13 (EST)
- **WBR client-first routing now serves real report/sync pages:** The new client/marketplace paths are live as the primary navigation shape:
  - `/reports/[clientSlug]/[marketplaceCode]/wbr`
  - `/reports/[clientSlug]/[marketplaceCode]/wbr/settings`
  - `/reports/[clientSlug]/[marketplaceCode]/wbr/sync`
  The legacy UUID route remains a compatibility redirect into settings.
- **WBR Windsor Section 1 sync engine landed:** Added `WindsorBusinessSyncService` plus admin endpoints for Windsor business backfill, daily refresh, and sync-run history. Sync writes normalized child-ASIN daily facts into `wbr_business_asin_daily` and logs runs in `wbr_sync_runs`.
- **WBR Section 1 report renderer landed:** Added `Section1ReportService` and the first live report UI on the primary WBR route. The page now renders rolling 4-week Page Views, Unit Sales, Sales, and Conversion Rate rollups using the configured row tree and ASIN mappings, plus QA counters for mapped/unmapped activity.
- **WBR sync UI replaced the placeholder:** The `/sync` route now has real controls for chunked backfill and daily refresh, with Windsor account visibility and recent-run history.

## 2026-03-12 (EST)
- **WBR v2 schema foundation applied:** Added and applied the new WBR migrations for profile/row modeling, Pacvue/listings mappings, and source fact tables:
  - `20260312000001_wbr_profiles_and_rows.sql`
  - `20260312000002_wbr_imports_and_mappings.sql`
  - `20260312000003_wbr_sync_runs_and_fact_tables.sql`
- **WBR v2 backend profile/row admin API shipped:** Added dedicated `/admin/wbr/*` management endpoints backed by `wbr_profiles` and `wbr_rows`, including admin auth, `404` vs `400` semantics, marketplace normalization, inactive-parent guards, and service-layer tests (`33 passed`).
- **WBR frontend replaced with profile-based flow:** Replaced the old `/reports/wbr/[clientId]` Section 1 scaffold with a profile-centric flow:
  - `/reports/wbr`
  - `/reports/wbr/setup`
  - `/reports/wbr/[profileId]`
- **WBR workspace modularized before next feature tranche:** Split the new profile workspace into a thin orchestrator, dedicated hook, typed workspace module, and focused components for summary, create-row, parent rows, and leaf rows. The stale empty `[clientId]` WBR route directory was removed.
- **Legacy WBR Section 1 backend retained temporarily:** The old Windsor-only `/admin/wbr/section1/*` endpoints and `windsor_section1_ingest.py` remain in place for now because they do not conflict with the new v2 profile-based routes.

## 2026-03-03 (EST)
- **The Claw Phase 3 pause/handoff packaged:** Added resume artifacts for clean context recovery after switching focus to N-Gram:
  - `docs/theclaw/current/03_theclaw_phase3_handoff.md`
  - `docs/theclaw/current/04_theclaw_phase3_resume_prompt.md`
- **Phase 3 runtime/test modularization checkpoint recorded:** Latest relevant The Claw commits captured in handoff (`cb9d6d8`, `74c7efe`) with current baseline (`144 passed, 1 warning`) and next-tranche acceptance criteria.

## 2026-02-26 (EST)
- **Reports/WBR frontend scaffold shipped:** Added `/reports` hub, `/reports/wbr`, `/reports/wbr/setup`, and `/reports/wbr/[clientId]` client workspace using existing Ecomlabs Tools UI language.
- **WBR Section 1 backfill wiring live:** Client workspace now runs backend `backfill-last-full-weeks` and refreshes Section 1 data directly from Supabase.
- **Weekly totals validation mode:** Main WBR table now shows Section 1 weekly totals across all groups (mapping-independent), excludes current in-progress week, and zero-fills missing full weeks so requested week count is always rendered (for example 4 rows for 4 weeks).

## 2026-02-25 (EST)
- **AgencyClaw C17H/C17H+ stabilization:** Landed follow-up hardening for planner delegation and agent-loop reliability, including delegated planner API contract propagation (`tool_executor` + explicit turn budgets) and stricter legacy prompt isolation so `delegate_planner` remains agent-loop-only.
- **Agent-loop runtime decomposition:** Extracted intent-recovery and skill-validation logic into dedicated service modules and split oversized runtime tests into focused suites to reduce drift risk while preserving behavior.
- **Debug chat operator harness:** Added gated `/api/slack/debug/chat` path and CLI flow for rapid non-Slack testing, with token verification, optional fixed user override, payload size cap, and mutation toggle controls.

## 2026-02-24 (EST)
- **AgencyClaw C17H complete:** Main agent now runs bounded multi-turn tool loops and can delegate complex requests via first-class `delegate_planner`, persisting parent/child run linkage and shared trace IDs.
- **AgencyClaw C17H+ complete:** Planner delegation upgraded to bounded iterative re-plan loop with explicit stop-state reporting (`completed`, `blocked`, `failed`, `budget_exhausted`, `needs_clarification`) while keeping DB run status on storage enum values.
- **Slack runtime modularization progress:** Continued extraction of route-layer glue from `slack.py` into bridge/runtime modules while preserving compatibility seams and full test parity.

## 2025-12-17 (EST)
- **Command Center UI polish:** Redesigned Clients list into a searchable, filterable table with brand chips/counts and a collapsed archived section. Refreshed Manage Client → Brands to use an "Add New Brand" modal (marketplace pill multiselect) and a visual org-chart tree with dashed support line + optimistic assignment updates for faster UX.
- **Command Center Tokens page:** Added `/command-center/tokens` with official OpenAI daily costs vs internal `ai_token_usage` attribution (range selector, rounded charts, fast-loading sections, CSV export of full selected range).
- **Debrief UX upgrades:** Added per-meeting "Draft Email" (modal editor + copy + Gmail compose link) and meeting dismissal ("Remove" on `/debrief`, stored as `status='dismissed'`). Added meeting list pagination (10 at a time with "Show 10 more").

## 2025-12-18 (EST)
- **Scribe Stage C Title Blueprint shipped:** Added a project-level blueprint to enforce deterministic Amazon title structure across all SKUs (ordered blocks + single separator), with a single AI block that fills the remaining character budget.
- **Title blueprint parsing + tests:** Added safe `unknown` parsing/validation, a single source of truth for valid separators, and expanded Vitest coverage for join rules, budget math, and integration scenarios.
- **Copy generation updated for blueprint mode:** Stage C generation now produces an AI `feature_phrase` (instead of a full title) when a blueprint is present, then assembles the final title deterministically; adds “fill the budget” targeting for longer phrases when remaining room is large.
- **Stage C UI/UX polish:** Made “Copy Formatting”, “Title Blueprint”, and “Attribute Preferences” consistent collapsible sections; added SKU title previews with fixed-length + AI budget indicators.
- **API hardening:** PATCH project updates now merge `format_preferences` instead of clobbering between sections; regenerate-copy gates on `scribe_topics.selected` (not `approved`) to match Stage B workflow.

## 2025-12-16 (EST)
- **Command Center MVP shipped:** Implemented Ghost Profiles + merge-on-login, core schema (clients, brands, roles, assignments), admin-only UI (`/command-center`) with org-chart role slots, team roster, per-member assignment view, brand marketplaces, and safe archive/delete actions for test data. Added Debrief helper endpoints for brand+role routing.
- **Debrief Stage 1–3 shipped (manual extraction):** Set up Google Workspace domain-wide delegation + impersonation, Drive folder ingestion, and Debrief MVP routes (`/debrief`) to sync "Notes by Gemini" into Supabase, view meetings, and manually run extraction per meeting (no ClickUp yet).
- **Debrief token usage logging:** Generalized `ai_token_usage.stage` constraint to allow non-Scribe stages (migration `20251216000001_ai_token_usage_stage_check_generalize.sql`) and wired Debrief extraction to log OpenAI usage via `frontend-web/src/lib/ai/usageLogger.ts`.
- **Auth hardening:** Updated Command Center route handlers to use `supabase.auth.getUser()` (verified identity) rather than trusting `getSession()` payloads, removing noisy warnings and improving server-side correctness.

## 2025-12-12 (EST)
- **AdScope Sponsored Brands Views + Data Accuracy Fixes:** Added SB analytics to AdScope (match/targeting types and ad formats) sourced from Bulk SB tabs. Implemented stable Bulk mappings for SB fields (`ad_format`, targeting expressions), new backend `views.sponsored_brands` payload, and corresponding frontend canvas/tab. Tightened SB targeting breakdown to use target-level SB entities only (Keyword + Product Targeting), removed negative keyword types from SB view, and added a spend-alignment warning when Bulk exports are campaign-rolled-up.
- **AdScope Bidding Strategy Mapping Bug Fix:** Diagnosed incorrect bidding-strategy buckets (numeric values) to fuzzy matching falsely mapping `Bid` → `Bidding Strategy` due to substring logic. Added exclusion in `bulk_parser.py` so bid-like headers cannot match `Bidding Strategy`, restoring correct strategy names (e.g., Dynamic bids / Fixed bid) in Bidding & Placements view.
- **AdScope UI Polish:** Fixed Explorer nav alignment/classes, added SB section in Explorer, and removed the hardcoded "Target: 30%" label from ACoS overview cards for cleaner presentation.

## 2025-12-11 (EST)
- **Supabase Auth Deadlock Fix:** Fixed critical auth bug causing homepage to hang on "Checking session..." indefinitely. Root cause: `async getUser()` inside `onAuthStateChange` callback triggered Supabase internal locking deadlock. Fix: (1) Changed initial auth check from `getUser()` to `getSession()`. (2) Removed async from `onAuthStateChange` callback. (3) Added `.catch()` handler to clear corrupted sessions. Commits: `b754d01`, `d143d4d`.
- **Scribe Stage C Prompt Improvements:** Enhanced copy generation prompt in `copyGenerator.ts` to fix attribute override mode, SKU code leakage, and product name rephrasing issues.

## 2025-12-10 (EST)
- **AdScope Backend/Frontend Landing (testable):** Added FastAPI router `/adscope/audit` with memory/file caps, fuzzy bulk/STR parsing (header-row scan), date-range mismatch warning, and all 13 precomputed views; hardened optional-column handling (placements/price sensitivity/zombies) and inclusive budget cap date span. Frontend `/adscope` now has ingest UI, dark workspace with all view tabs, mock JSON contract, and server-side chat proxy (no client key leakage). Bulk tab selection prioritizes SP Campaigns per schema.

## 2025-12-09 (EST)
- **AdScope Parser & Metrics Fixes:** Resolved critical data accuracy issues. Multi-tab parsing for SP/SB/SD campaigns. Switched overview metrics source from STR to Bulk file. Added backfill logic for missing columns.
- **Token Usage Tracking Refactor:** Generalized logging to support Scribe and AdScope. Migrated `scribe_usage_logs` to `ai_token_usage`. Consolidated logging into `frontend-web/src/lib/ai/usageLogger.ts`.
- **Root Keyword Analysis Tool Shipped:** Backend `/root/process` with parsing, week bucketing, hierarchical aggregation, and formatted Excel workbook. Frontend `/root-keywords` with drag/drop upload.

## 2025-12-08 (EST)
- **N-Gram Special Character Preservation Fix:** Fixed token cleaning in `analytics.py` to preserve measurement symbols (`"`, `'`, `°`), brand symbols (`™`, `®`, `©`), and common characters (`&`, `+`, `#`). Added 23-test suite in `test_ngram_analytics.py`.

## 2025-12-04 (EST)
- **Scribe Stage C CSV Export & Dirty Regenerate:** Implemented `/api/scribe/projects/[projectId]/export-copy` with dynamic attribute columns. Dirty-state now forces full regenerate-all when stale.
- **Scribe Test Coverage Expanded:** Added API tests for export-copy, generate-copy, generated-content. Composer tests quarantined via `describe.skip`.
- **N-Gram Two-Step Negatives Flow:** Refreshed `/ngram` UI into two clear cards, added new collector for formatted NE summary (Excel).
- **N-PAT PRD & Plan Ready:** Authored `docs/03_npat_prd.md` and `docs/03_npat_plan.md`.

## 2025-12-03 (EST)
- **Scribe Stage B Topic Selection Bug Fixed:** Resolved React state closure issue in `handleToggleTopic` causing selections not to persist.
- **Scribe Stage C Attribute Preferences Specification Complete:** Documented feature allowing control of which attributes appear in title/bullets/description.

## 2025-12-02 (EST)
- **Scribe Stage B (Topics) Shipped:** Complete UI with topic generation workflow, 5-topic selection limit, dirty state detection, and Previous/Next navigation. Added `PATCH /api/scribe/projects/{projectId}/topics/{topicId}` endpoint.
- **Scribe Stage A Polish:** Fixed EditSkuPanel save button, custom attributes persistence, keyword limits. Optimized with `Promise.all()` for parallel API calls.
- **Scribe CSV Upload Bug Fixes:** Auto-detect delimiter, fixed field name mismatch, added duplicate handling.
- **Scribe Lite Foundation Components:** Built `ScribeHeader` and `ScribeProgressTracker`. Replaced approval/locking with "Dirty State" model.
- **Scribe Lite Restart:** Archived legacy Scribe frontend (`_legacy_v1`) and docs (`docs/archive/scribe_legacy`).

## 2025-11-29 (EST)
- **Scribe Stage navigation/approval guard fixes:** Normalized status handling so refreshes land on correct stage.

## 2025-11-28 (EST)
- **Scribe Stage C shipped (backend + UI):** Generate/regenerate/approve/edit routes, job runner, Stage C fields in CSV export, per-SKU editor.
- **Scribe CSV export fixes:** RFC 4180 formatting with proper quoting and UTF-8 BOM.
- **Scribe variant attribute values persistence fixed:** Replaced `upsert()` with manual check-then-update-or-insert.

## 2025-11-27
- **Scribe Stage C spec ready (docs):** PRD, implementation plan, schema, prompt/orchestration, and test plan updated.
- **Scribe Stage B tests passing:** Gate, job, CSV edge, RLS/limits telemetry tests (Vitest).
- **Scribe Stage B refinements:** Topics prompt updated to 3-bullet descriptions, token usage logging wired.
- **Scribe Stage A polished & CSV upsert:** Per-SKU blocks, CSV import upserts by `sku_code`.

## 2025-11-26
- **Scribe per-SKU migration and docs aligned:** Applied Supabase migration to drop shared/default columns, enforce `sku_id` NOT NULL.

## 2025-11-25
- **Scribe Slice 1 (Projects Shell) Complete:** Projects API with owner scoping, frontend dashboard at `/scribe`.
- **Scribe Stage A Grid In Progress:** Grid-centric layout with sticky SKU column, dynamic variant attribute columns.

## 2025-11-22
- **Composer Deprecated, Scribe Announced:** Paused Composer work. Initiated Scribe replacement.
- **Fixed Keyword Grouping Generation:** Resolved three critical issues with the "GENERATE GROUPING PLAN" button.

## 2025-11-21
- **Database Migrations for Team Central, The Operator, and ClickUp Service:** Created 3 production-ready Supabase migrations.
- **Composer Slice 2 Stage 7 (Keyword Grouping UI):** Full drag-and-drop interface, approval workflow, override tracking.

## 2025-11-20
- **Composer Slice 2 Stage 6 (Keyword Grouping APIs & AI Integration):** AI-powered keyword grouping with OpenAI integration, 4 grouping basis types, merge utility.
- **Composer Slice 2 Stage 5 (Keyword Cleanup UI):** Tab-based navigation, collapsible keyword lists, grouped removed keywords by reason.
- **Composer Slice 2 Stage 4 (Keyword Upload UI):** Scope-aware tabs, CSV/paste/manual inputs, dedupe/validation.
- **Composer Slice 2 Stage 3 (Keyword Cleanup APIs & Logic):** Deterministic cleaning service, approval gating.
- **Composer Slice 2 Stage 2 (Keyword Pool APIs):** Upload/merge endpoints, CSV parsing helpers.
- **Composer Slice 2 Stage 1 (Schema & Backend Foundation):** Created keyword pipeline tables with RLS policies.

## 2025-11-19
- **Composer Slice 2 planning:** Aligned schema/types with keyword pool state machine.
- **Composer Slice 1 polish:** Key-attribute highlight grid, keyword grouping override spec.
- **Composer Slice 1 Surface 4 (Content Strategy):** StrategyToggle, SkuGroupsBuilder, GroupCard, full SKU groups API.

## 2025-11-18
- **Frontend migration to `@supabase/ssr`:** Fixed async cookies regression, aligned Composer fallback org.

## 2025-11-17
- **Composer Slice 1 Surface 3 (Product Info):** Autosave meta forms, FAQ editor, SKU intake with CSV import.

## 2025-11-16
- **Composer Slice 1 Surface 1+2:** Dashboard list/create, wizard frame with autosave shell.

## 2025-11-15
- **Composer schema + tenancy:** Created all `composer_*` tables, RLS policies, canonical TypeScript types.

## 2025-11-14
- **Composer PRD rebuild (v1.6):** End-to-end implementation plan.

## 2025-11-13
- **N-Gram Processor migration:** FastAPI backend + refreshed Next.js page.
- **Supabase-aware middleware:** Guards `/ngram` for logged-out users.
