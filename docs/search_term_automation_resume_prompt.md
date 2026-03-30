# Search Term Automation Resume Prompt

_Last updated: 2026-03-30 (ET)_

Use this prompt when returning specifically to the STR / N-Gram 2.0 workstream.

Continue work in `/Users/jeff/code/agency-os`.

Read first, in this order:

1. `docs/current_handoffs.md`
2. `docs/search_term_automation_plan.md`
3. `docs/ngram_native_replacement_plan.md`
4. `PROJECT_STATUS.md`
5. `AGENTS.md`

## Current shipped reality

1. `SP` native STR ingestion is live and validated against a real Amazon
   `Search term` export.
2. `SB` ingestion is live and works on modern accounts we have validated, but
   is not guaranteed complete for legacy Sponsored Brands campaign families.
3. `SD` is still out of scope for the current native N-Gram replacement path.
4. `/ngram-2` exists as a separate route and does **not** modify the legacy
   `/ngram` tool.
5. `N-Gram 2.0` has already completed the first real native replacement loop
   for `SP`:
   - generate native workbook from `/ngram-2`
   - upload that workbook into Step 2 of the existing `/ngram`
   - legacy Step 2 accepts it and returns the expected workbook output
6. `/ngram-2` AI preview is now live behind the new Step 3 path:
   - native SP preflight summary is already in place
   - AI preview now performs **AI-first product identification + term
     evaluation in one call** using Windsor child-ASIN catalog context
   - preview responses are validated strictly before gram synthesis
   - successful preview payloads now persist in `ngram_ai_preview_runs`
   - preview responses now return `preview_run_id`, and the AI-prefilled
     workbook path can reuse that exact saved run
   - `reason_tag` is now a strict enum and must be exactly one of:
     - `core_use_case`
     - `wrong_category`
     - `wrong_product_form`
     - `wrong_size_variant`
     - `wrong_audience_theme`
     - `competitor_brand`
     - `cloth_primary_intent`
     - `accessory_only_intent`
     - `foreign_language`
     - `ambiguous_intent`
   - intentionally skipped brand/mix/defensive campaigns no longer consume the
     top-6 preview budget
   - AI-prefilled workbook sheets now keep the legacy workbook layout while
     appending compact `AI Recommendation`, `AI Confidence`, and `AI Reason`
     columns to the search-term table

## Important validation findings

### Sponsored Products

1. Whoosh US `SP` was validated end to end against a real Amazon export.
2. Validation should compare against Amazon `Search term` exports, not broad
   Campaign Manager totals.
3. Impressions can differ from broader console totals because Amazon search-
   term reporting appears limited to search terms that generated at least one
   click.

### Sponsored Brands

1. Native `SB` contract probing on Whoosh US established:
   - `adProduct = SPONSORED_BRANDS`
   - `reportTypeId = sbSearchTerm`
   - `groupBy = ["searchTerm"]`
2. A repeated Whoosh US mismatch was isolated to one campaign family:
   - `Screen Shine - Pro | Brand | SB | PC-Store | MKW | Br.M | Mix. | Def`
3. That campaign was absent from the raw native `sbSearchTerm` API payload,
   not just missing after parsing/storage.
4. Screenshot evidence shows the campaign was created on `2019-12-04`.
5. Current leading hypothesis:
   - this is a legacy Sponsored Brands campaign family omitted by Amazon's v3
     reporting surface while still present in console/export views
6. Ahimsa US now provides the clean counterexample:
   - Amazon `Sponsored Brands > Search term > Daily` export for
     `2026-03-15` through `2026-03-21` matched the DB exactly
   - exact matched totals:
     - `567` rows
     - `69,544` impressions
     - `809` clicks
     - `$805.81` spend
     - `64` orders
     - `$3,048.50` sales
   - campaign-level matches included a branded defensive
     `SB | PC-Store` campaign
7. Practical current read:
   - `SB` is not generically broken
   - `SB` is partly validated
   - legacy SB campaign families remain the main gap/risk

## Operational notes to preserve

1. The earlier “run says success but no facts persisted” incident now looks
   like a stale `worker-sync` deployment problem, not a standing code bug.
2. Post-redeploy overnight runs were checked against persisted facts, not just
   UI cards, and were healthy for:
   - Whoosh US `SP`
   - Whoosh US `SB`
   - Whoosh CA `SP`
   - Whoosh CA `SB`
   - Ahimsa US `SP`
   - Ahimsa US `SB`
   - Distex CA `SP`
3. For those completed runs, `rows_loaded` matched persisted
   `search_term_daily_facts` rows by exact `sync_run_id`.

## Current product position

1. The immediate value is not a Pacvue clone.
2. The current win is a safer Step 1 replacement for the existing N-Gram flow.
3. Workbook compatibility matters more than inventing a new analyst workflow
   too early.
4. `SP` is the trusted production path for N-Gram 2.0 right now.
5. `SB` should stay visible but nuanced:
   - works on validated modern accounts
   - not guaranteed complete for legacy campaign families

## Recommended next-session target

The current `SP` Step 3 validation slice is in a good state. Focus next on
turning the trusted `/ngram-2` preview output into a better workbook-prefill /
analyst-review loop rather than trying to “solve” legacy `SB` immediately.

Recommended order:

1. start a **fresh Codex session** after:
   - `codex mcp logout supabase`
   - `codex mcp login supabase`
   - `codex mcp list`
2. use the fresh session to inspect the persisted `/ngram-2` preview outputs
   and identify the next smallest useful SP-focused implementation slice:
   - workbook-prefill tuning
   - analyst-review ergonomics
   - override logging / calibration
3. keep validating `SB` opportunistically on additional modern accounts, but
   do not block `SP` product progress on full legacy SB parity
4. avoid touching the legacy `/ngram` route unless explicitly asked

## Restart prompt for the next session

Use this as the first message if the next session returns to this thread:

```text
Continue the Agency OS STR / N-Gram 2.0 workstream.

Read first:
1. docs/current_handoffs.md
2. docs/search_term_automation_resume_prompt.md
3. docs/search_term_automation_plan.md
4. docs/ngram_native_replacement_plan.md
5. PROJECT_STATUS.md
6. AGENTS.md

Current reality:
- SP native STR ingestion is validated and trusted
- SB works on at least one modern live account (Ahimsa US) but has a likely
  legacy Sponsored Brands gap on at least one older Whoosh US campaign family
- /ngram-2 already proved the first real native Step 1 replacement loop for SP
  by generating a workbook that Step 2 of legacy /ngram accepted
- /ngram-2 Step 3 AI preview now uses AI-first product identification from the
  Windsor child-ASIN catalog in the same call as term evaluation
- AI preview responses are now validated strictly before gram synthesis
- successful preview payloads now persist in `ngram_ai_preview_runs`
- `reason_tag` is now a strict 10-value enum:
  core_use_case, wrong_category, wrong_product_form, wrong_size_variant,
  wrong_audience_theme, competitor_brand, cloth_primary_intent,
  accessory_only_intent, foreign_language, ambiguous_intent
- skipped brand/mix/defensive campaigns no longer burn the top-6 preview slots
- the current Step 3 validation slice is a pass; the next priority is turning
  the trusted SP preview path into a stronger workbook-prefill / review loop,
  not blocking on full legacy SB parity

Start by checking that Supabase MCP auth works in this fresh session, then
review the latest persisted /ngram-2 preview outputs and identify the next
smallest useful SP-focused implementation slice based on those real results.
```
