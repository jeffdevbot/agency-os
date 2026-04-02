# N-Gram 2.0 Sponsored Brands Enablement Plan

_Created: 2026-04-02 (ET)_

## Purpose

Enable `Sponsored Brands` (`SB`) in the native `/ngram-2` workflow so it works
the same way `Sponsored Products` (`SP`) already works mechanically:

1. native summary
2. Step 3 AI preview
3. Step 4 AI workbook generation
4. Step 5 reviewed workbook upload / override capture

This plan is intended as a direct implementation handoff for another coding
agent.

## Decision already made

The remaining legacy SB parity gap is **not** a blocker.

Accepted product stance:

1. Some older SB campaign families, likely pre-2019-era legacy inventory, do
   not appear in the native `sbSearchTerm` API feed.
2. That limitation is acceptable for this implementation slice.
3. The goal is to enable SB where native data already exists and keep the UI
   copy honest about the caveat.
4. Do **not** spend implementation time trying to solve Amazon-side historical
   SB parity before enabling the workflow.

## Non-goals

Do not expand scope into:

1. Sponsored Display support
2. Responses API migration
3. more `/ngram-2` UI cleanup unrelated to SB enablement
4. redesigning the analyst workbook contract
5. proving total export parity for all historical SB campaign families

## Current live reality

As of 2026-04-02, live Supabase already contains usable SB STR data:

1. `SPONSORED_BRANDS`: `8,672` rows across `209` campaigns
2. `SPONSORED_PRODUCTS`: `44,425` rows across `654` campaigns

Largest live SB profile coverage:

1. `Whoosh` `US`: `4,546` rows / `137` campaigns
2. `Ahimsa` `US`: `2,648` rows / `6` campaigns
3. `Whoosh` `CA`: `1,461` rows / `110` campaigns
4. `Distex` `CA`: `17` rows / `6` campaigns

Live field coverage in `search_term_daily_facts`:

1. SB rows have `keyword`, `keyword_type`, and `match_type`
2. SB rows currently have null `targeting`
3. SP rows have all four populated

That means the missing work is mostly enablement and QA, not schema
invention or ingestion from scratch.

## How SP works today

This section describes the current end-to-end SP path, because SB should be
enabled by following the same architecture rather than inventing a parallel
path.

### 1. Native ingestion

Search-term ingestion is defined in
[amazon_ads_search_terms.py](/Users/jeff/code/agency-os/backend-core/app/services/wbr/amazon_ads_search_terms.py).

SP uses:

1. `ad_product = "SPONSORED_PRODUCTS"`
2. `report_type_id = "spSearchTerm"`
3. `campaign_type = "sponsored_products"`
4. `group_by = ["searchTerm"]`

The sync writes normalized rows into
[search_term_daily_facts](/Users/jeff/code/agency-os/docs/wbr_v2_schema_plan.md).

### 2. Search Term Data verification

The operator-facing verification surface is
`/reports/search-term-data/[clientSlug]`.

It reads from
[search_term_facts.py](/Users/jeff/code/agency-os/backend-core/app/services/wbr/search_term_facts.py),
which already supports filtering by `ad_product`.

This matters because `/ngram-2` already uses Search Term Data as the
trust-building inspection step before workbook generation.

### 3. `/ngram-2` Step 1 native summary

The main page is
[page.tsx](/Users/jeff/code/agency-os/frontend-web/src/app/ngram-2/page.tsx).

For SP today it:

1. loads client/profile options
2. loads a native summary from backend `POST /ngram/native-summary`
3. shows coverage, campaign counts, totals, and warnings
4. offers a direct link into Search Term Data for the same filters

The backend endpoint lives in
[ngram.py](/Users/jeff/code/agency-os/backend-core/app/routers/ngram.py)
and delegates to
[native.py](/Users/jeff/code/agency-os/backend-core/app/services/ngram/native.py).

### 4. `/ngram-2` Step 3 preview and Step 4 full workbook generation

The AI route is
[route.ts](/Users/jeff/code/agency-os/frontend-web/src/app/api/ngram-2/ai-prefill-preview/route.ts).

Current SP flow:

1. frontend calls `/api/ngram-2/ai-prefill-preview`
2. route loads search-term rows from `search_term_daily_facts`
3. route loads catalog rows from `wbr_profile_child_asins`
4. route runs retrieval-first campaign evaluation
5. route persists the exact run in `ngram_ai_preview_runs`
6. frontend calls backend `POST /ngram/native-workbook-prefilled`
7. backend rebuilds the familiar workbook using the saved preview payload

Current model path:

1. Step 3 preview works
2. Step 4 full workbook now uses the pure-model path too
3. saved runs persist `prompt_version`, token counts, and full preview payload

### 5. Step 5 reviewed workbook upload

The reviewed workbook upload still goes through backend `/ngram/collect`.

That path captures analyst-vs-AI differences in
`ngram_ai_override_runs` when the workbook still carries `AI Preview Run`
metadata from `/ngram-2`.

The important point for SB enablement:

1. Step 5 is not SP-specific in concept
2. it should continue to work as long as the generated workbook shape stays
   unchanged

## Current SB implementation status

### Already implemented

SB ingestion is already configured in
[amazon_ads_search_terms.py](/Users/jeff/code/agency-os/backend-core/app/services/wbr/amazon_ads_search_terms.py).

SB uses:

1. `ad_product = "SPONSORED_BRANDS"`
2. `report_type_id = "sbSearchTerm"`
3. `campaign_type = "sponsored_brands"`
4. `group_by = ["searchTerm"]`
5. SB-native columns like `keywordText`, `keywordType`, `matchType`,
   `searchTerm`, `purchases`, `sales`

Product metadata is already exposed in
[searchTermProducts.ts](/Users/jeff/code/agency-os/frontend-web/src/app/reports/_lib/searchTermProducts.ts):

1. key `sb`
2. `amazonAdsAdProduct = "SPONSORED_BRANDS"`
3. `campaignType = "sponsored_brands"`
4. `reportTypeId = "sbSearchTerm"`
5. `status = "beta"`

Presentation-layer caution messaging already exists in
[ngram2Presentation.ts](/Users/jeff/code/agency-os/frontend-web/src/app/ngram-2/ngram2Presentation.ts).

### Not yet implemented

The remaining blockers are explicit SP-only gates:

1. `/ngram-2` frontend only enables preview/workbook actions when
   `selectedProduct === "sp"`
2. the `/api/ngram-2/ai-prefill-preview` route only allows
   `SPONSORED_PRODUCTS`
3. backend native summary/workbook services reject any non-SP ad product

## Relevant schema

No new tables are required for this slice.

### 1. `public.wbr_profiles`

Reference:
[wbr_v2_schema_plan.md](/Users/jeff/code/agency-os/docs/wbr_v2_schema_plan.md)

Relevant columns:

1. `id`
2. `client_id`
3. `display_name`
4. `marketplace_code`
5. `amazon_ads_profile_id`
6. `amazon_ads_currency_code`
7. `search_term_auto_sync_enabled`
8. `search_term_sb_auto_sync_enabled`
9. `search_term_sd_auto_sync_enabled`

Why it matters:

1. `/ngram-2` profile availability comes from this table
2. SB readiness is already modeled by `search_term_sb_auto_sync_enabled`

### 2. `public.search_term_daily_facts`

Reference:
[wbr_v2_schema_plan.md](/Users/jeff/code/agency-os/docs/wbr_v2_schema_plan.md)

Relevant columns:

1. `profile_id`
2. `report_date`
3. `ad_product`
4. `report_type_id`
5. `campaign_type`
6. `campaign_id`
7. `campaign_name`
8. `search_term`
9. `match_type`
10. `impressions`
11. `clicks`
12. `spend`
13. `orders`
14. `sales`
15. `keyword_id`
16. `keyword`
17. `keyword_type`
18. `targeting`
19. `source_payload`

Why it matters:

1. native summary reads from this table
2. AI preview/full workbook runs read from this table
3. SB rows already exist here, so no migration is required

### 3. `public.wbr_profile_child_asins`

Reference:
[wbr_v2_schema_plan.md](/Users/jeff/code/agency-os/docs/wbr_v2_schema_plan.md)

Relevant columns:

1. `profile_id`
2. `child_asin`
3. `child_sku`
4. `parent_title`
5. `child_product_name`
6. `category`
7. `item_description`
8. `active`

Why it matters:

1. catalog retrieval for AI matching reads from this table
2. the same listing catalog path is used for SP and SB

### 4. `public.ngram_ai_preview_runs`

Reference:
[wbr_v2_schema_plan.md](/Users/jeff/code/agency-os/docs/wbr_v2_schema_plan.md)

Relevant columns:

1. `profile_id`
2. `ad_product`
3. `date_from`
4. `date_to`
5. `spend_threshold`
6. `respect_legacy_exclusions`
7. `model`
8. `prompt_version`
9. `prompt_tokens`
10. `completion_tokens`
11. `total_tokens`
12. `preview_payload`
13. `created_at`

Why it matters:

1. Step 3 and Step 4 persistence already work here
2. SB runs should write here exactly the same way as SP runs

### 5. `public.ngram_ai_override_runs`

Reference:
[wbr_v2_schema_plan.md](/Users/jeff/code/agency-os/docs/wbr_v2_schema_plan.md)

Relevant columns:

1. `preview_run_id`
2. `profile_id`
3. `model`
4. `prompt_version`
5. `override_payload`
6. `created_at`

Why it matters:

1. reviewed uploads should continue to capture SB AI-vs-analyst override data

### Schema conclusion

Expected schema work for this slice:

1. **none required**

Optional later cleanup, not part of this slice:

1. add `run_mode` as a top-level column on `ngram_ai_preview_runs`
2. add `prefill_strategy` as a top-level column on `ngram_ai_preview_runs`

## Endpoints and services involved

### Frontend

1. `/ngram-2`
   - file:
     [page.tsx](/Users/jeff/code/agency-os/frontend-web/src/app/ngram-2/page.tsx)
2. presentation helpers
   - file:
     [ngram2Presentation.ts](/Users/jeff/code/agency-os/frontend-web/src/app/ngram-2/ngram2Presentation.ts)
3. ad-product config
   - file:
     [searchTermProducts.ts](/Users/jeff/code/agency-os/frontend-web/src/app/reports/_lib/searchTermProducts.ts)

### Frontend server route

1. `POST /api/ngram-2/ai-prefill-preview`
   - file:
     [route.ts](/Users/jeff/code/agency-os/frontend-web/src/app/api/ngram-2/ai-prefill-preview/route.ts)

### Backend API

1. `POST /ngram/native-summary`
2. `POST /ngram/native-workbook`
3. `POST /ngram/native-workbook-prefilled`
4. `POST /ngram/collect`

Router file:
[ngram.py](/Users/jeff/code/agency-os/backend-core/app/routers/ngram.py)

### Backend services

1. native workbook/summary builder
   - [native.py](/Users/jeff/code/agency-os/backend-core/app/services/ngram/native.py)
2. campaign grouping/workbook generation
   - [campaigns.py](/Users/jeff/code/agency-os/backend-core/app/services/ngram/campaigns.py)
3. search-term ingestion
   - [amazon_ads_search_terms.py](/Users/jeff/code/agency-os/backend-core/app/services/wbr/amazon_ads_search_terms.py)
4. Search Term Data read/export service
   - [search_term_facts.py](/Users/jeff/code/agency-os/backend-core/app/services/wbr/search_term_facts.py)

## What actually needs to change

## Phase 1: Remove SP-only product gates in `/ngram-2`

Primary file:
[page.tsx](/Users/jeff/code/agency-os/frontend-web/src/app/ngram-2/page.tsx)

Required changes:

1. allow `sb` to build `inspectRowsHref`
2. allow `sb` to load the native summary
3. allow `sb` to enable preview/workbook actions
4. keep `sd` blocked
5. keep SB caution copy intact

Current SP-only gates to remove or generalize:

1. `selectedProduct === "sp"` in `inspectRowsHref`
2. `selectedProduct === "sp"` in `canGenerateWorkbook`
3. `selectedProduct === "sp"` in `canRunPreviewBase`
4. `if (selectedProduct !== "sp") { ... return; }` in the summary-loading effect

Target behavior:

1. `sp` remains `ready`
2. `sb` becomes runnable when the selected profile is connected and summary
   data exists
3. `sd` remains blocked

Recommended rule:

1. permit actions when `selectedProduct` is `sp` or `sb`
2. require `runState.tone !== "blocked"` rather than hardcoding SP

## Phase 2: Allow SB through the AI preview/full-run route

Primary file:
[route.ts](/Users/jeff/code/agency-os/frontend-web/src/app/api/ngram-2/ai-prefill-preview/route.ts)

Required changes:

1. replace the single `SUPPORTED_AD_PRODUCT = "SPONSORED_PRODUCTS"` guard
   with an allowlist:
   - `SPONSORED_PRODUCTS`
   - `SPONSORED_BRANDS`
2. keep `SPONSORED_DISPLAY` rejected
3. keep the response payload contract unchanged
4. keep persisted `ad_product` exactly as provided

Why this route should work for SB with limited changes:

1. it loads generic search-term fact rows
2. it already passes `ad_product` through to persistence
3. it already tolerates nullable `targeting`
4. campaign evaluation logic is term-driven, not SP-only by design

Recommended small addition:

1. append an SB-specific warning when `ad_product === "SPONSORED_BRANDS"`:
   - make clear this remains a controlled-validation/beta path
   - explicitly mention the accepted legacy parity gap

This warning should be informational only. It should not block execution.

## Phase 3: Allow SB through native summary and workbook generation

Primary file:
[native.py](/Users/jeff/code/agency-os/backend-core/app/services/ngram/native.py)

Current blockers:

1. `build_workbook_from_search_term_facts` rejects non-SP
2. `build_summary_from_search_term_facts` rejects non-SP

Required changes:

1. replace the current SP-only validation with an allowlist:
   - `SPONSORED_PRODUCTS`
   - `SPONSORED_BRANDS`
2. keep `SPONSORED_DISPLAY` rejected
3. keep the workbook output contract unchanged

Important observation:

The workbook builder is already mostly ad-product-agnostic because
`_prepare_rows`, `build_campaign_items`, and `build_workbook` only need the
normalized campaign/query/metric shape.

That means SB should reuse the same builder rather than branching to a
special-case workbook implementation.

## Phase 4: Preserve the existing workbook contract

Do **not** change the workbook contract while enabling SB.

Current expected workbook behavior:

1. `AI Recommendation`
   - `SAFE KEEP`
   - `LIKELY NEGATE`
   - `REVIEW`
2. `AI Rationale` remains populated
3. `NE/NP` cells stay blank for analyst review
4. mono/bi/tri scratchpad remains the same

This matters because Step 5 reviewed workbook upload depends on the current
shape and the team’s adoption path is workbook-centered.

## Phase 5: Keep the trust messaging honest

Files:

1. [searchTermProducts.ts](/Users/jeff/code/agency-os/frontend-web/src/app/reports/_lib/searchTermProducts.ts)
2. [ngram2Presentation.ts](/Users/jeff/code/agency-os/frontend-web/src/app/ngram-2/ngram2Presentation.ts)

Current messaging is directionally correct and should stay cautious.

Recommended product posture after enablement:

1. `SP`: ready now
2. `SB`: controlled validation / beta, but runnable
3. `SD`: blocked

The implementation should not rewrite history and claim universal SB parity.

## Tests to add or update

### Backend

Add or update tests for:

1. `NativeNgramWorkbookService.build_summary_from_search_term_facts`
   accepts `SPONSORED_BRANDS`
2. `NativeNgramWorkbookService.build_workbook_from_search_term_facts`
   accepts `SPONSORED_BRANDS`
3. both methods still reject unsupported products like `SPONSORED_DISPLAY`

### Frontend route

Add or update tests for:

1. `/api/ngram-2/ai-prefill-preview` request coercion accepts
   `SPONSORED_BRANDS`
2. preview/full persistence still writes `ad_product = SPONSORED_BRANDS`
3. nullable `targeting` does not break SB payload generation

### Frontend page

If page-level tests exist or are practical, cover:

1. SB can request summary/workbook/preview
2. SD remains blocked

## Recommended validation sequence

Use a validated modern SB profile first. Best candidates from live data:

1. `Ahimsa US`
2. `Whoosh CA`

Avoid starting with the legacy-gap profile family for first validation.

### Validation checklist

1. In `Search Term Data`, confirm SB rows load for the selected profile/date
   range.
2. In `/ngram-2`, load native summary for SB.
3. Confirm the Search Term Data deep link opens with the same SB filters.
4. Run Step 3 preview on a bounded campaign subset.
5. Confirm a row is written to `ngram_ai_preview_runs` with
   `ad_product = 'SPONSORED_BRANDS'`.
6. Generate a Step 4 full workbook.
7. Confirm workbook downloads and preserves the current triage columns.
8. Upload the reviewed workbook through Step 5.
9. Confirm override capture still lands in `ngram_ai_override_runs`.

### SQL checks for QA

Use read-only checks similar to:

```sql
select count(*)
from public.ngram_ai_preview_runs
where ad_product = 'SPONSORED_BRANDS';
```

```sql
select count(*)
from public.ngram_ai_override_runs o
join public.ngram_ai_preview_runs p on p.id = o.preview_run_id
where p.ad_product = 'SPONSORED_BRANDS';
```

## Unknowns and risks

### 1. SB `targeting` is null

Live SB rows currently do not populate `targeting`. This is probably fine,
because the AI and workbook paths already tolerate nullable fields, but it
should be explicitly tested.

### 2. Catalog matching quality may differ from SP

SB campaigns can be more brand/creative-oriented than SP campaigns. The
mechanical enablement should still work, but match quality may need later
prompt tuning.

That is not a blocker for this slice unless it causes obvious runtime breakage.

### 3. Legacy exclusion rules may be imperfect for SB naming

The existing legacy exclusions around `Ex.`, `SDI`, and `SDV` were inherited
from the old N-Gram workflow and are not SB-specific. They should remain
unchanged for this slice, but if a modern SB account shows obviously bad
campaign skipping, capture that as a follow-up.

### 4. Large-window AI reliability is still a separate issue

The current SP Step 4 reliability hardening work remains relevant to SB too.
Do not treat an AI size/reliability issue as proof that SB enablement itself
is wrong.

### 5. Historical SB export parity remains incomplete by design

This should remain visible in product copy and docs. It is an accepted known
gap, not a blocker for shipping the SB path.

## Acceptance criteria

This implementation is done when all of the following are true:

1. `/ngram-2` can load a native SB summary without SP-only gating errors
2. `/ngram-2` can run SB Step 3 preview
3. `/ngram-2` can run SB Step 4 workbook generation
4. backend native summary/workbook endpoints accept `SPONSORED_BRANDS`
5. `ngram_ai_preview_runs` persists SB runs
6. reviewed workbook upload still works and can persist SB override capture
7. the workbook contract remains unchanged
8. SB still appears as caution/beta rather than universally trusted
9. SD remains blocked

## Suggested implementation order

1. update backend `native.py` allowlist
2. update frontend API route allowlist in `route.ts`
3. update `/ngram-2` page gating in `page.tsx`
4. run targeted tests
5. validate on one modern SB account
6. only then update handoff/status docs if desired

## Nice-to-have follow-up docs after shipping

If the implementation lands cleanly, update:

1. [current_handoffs.md](/Users/jeff/code/agency-os/docs/current_handoffs.md)
2. [search_term_automation_resume_prompt.md](/Users/jeff/code/agency-os/docs/search_term_automation_resume_prompt.md)
3. [PROJECT_STATUS.md](/Users/jeff/code/agency-os/PROJECT_STATUS.md)

Those doc updates are secondary to the actual enablement work.
