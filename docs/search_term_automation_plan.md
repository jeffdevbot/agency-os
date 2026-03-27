# Search Term Automation Plan

_Created: 2026-03-26 (ET)_

## Purpose

Define the phased replacement path for the current Pacvue-export-driven
N-Gram / N-PAT workflow while keeping the legacy tool untouched during rollout.

This plan covers:

1. richer catalog context ingestion needed for AI-quality recommendations
2. Amazon Ads-native STR and adjacent report ingestion
3. a staged operator-facing rollout:
   - setup controls
   - Search Term Data inspection
   - later action tools
4. eventual direct writeback to Amazon with explicit approval and audit

For the operator-facing N-Gram replacement concept built on top of this data
foundation, see:

- [N-Gram native replacement plan](/Users/jeff/code/agency-os/docs/ngram_native_replacement_plan.md)

It does **not** assume the existing `/ngram` and `/npat` routes should be
rewired in place. The preferred product direction is a new surface that can
ship alongside the legacy upload flow until the replacement is trusted.

It also does **not** assume every STR-related surface is a "tool".

The rollout should distinguish clearly between:

1. operational setup/control surfaces
2. data inspection surfaces
3. true action/workflow tools

## Current state

### What the current tools do

The existing file-based tools already have a clean processing split:

1. N-Gram reads a search-term report, keeps the fields:
   - `Query`
   - `Impression`
   - `Click`
   - `Spend`
   - `Order 14d`
   - `Sales 14d`
   - `Campaign Name`
2. N-Gram excludes ASIN queries and builds 1/2/3-gram analysis.
3. N-PAT uses the same input family but keeps only ASIN queries.
4. Both tools group by campaign and skip campaign names containing:
   - `Ex.`
   - `SDI`
   - `SDV`

Important clarification about the legacy file source:

1. the current Pacvue-export workflow is a unified analyst-facing report shape,
   not proof of one-to-one Amazon-native report-family parity
2. a Pacvue "search term report" can contain mixed `SP`, `SB`, and `SD` rows
   in one file
3. this does **not** prove that Amazon exposes `SP`, `SB`, and `SD` through
   the same native report family or contract
4. future native ingestion should therefore validate each ad product against
   Amazon's own report contracts, not infer support from the Pacvue export

### What is missing today

The manual workflow still depends on:

1. exporting a search-term report from Pacvue
2. uploading that file into N-Gram / N-PAT
3. using human judgment to decide negatives
4. copying approved negatives back into Pacvue / Amazon manually

### Existing WBR data that is relevant

WBR already maintains a child-ASIN catalog in `wbr_profile_child_asins`.

Current structured fields include:

1. `child_asin`
2. `parent_asin`
3. `child_sku`
4. `parent_title`
5. `child_product_name`
6. `category`
7. `source_item_style`
8. `size`
9. `fulfillment_method`

So today we already have usable product/title context through:

1. `child_product_name`
2. `parent_title`
3. `child_sku`
4. `category`

The Windsor listing import also fetches more raw fields than it promotes,
including items such as:

1. `item_description`
2. `item_note`
3. `image_url`
4. `status`
5. `price`
6. `quantity`
7. `merchant_shipping_group`
8. `item_condition`
9. `browse_path`

Those richer fields are currently available only in `raw_payload`, not as a
clean catalog context layer for AI or review workflows.

### Live raw-payload audit

We audited live active `wbr_profile_child_asins.raw_payload` coverage across
real profiles before locking the expansion plan.

What we found:

1. `status`, `price`, `quantity`, `merchant_shipping_group`, and
   `item_condition` are generally strong promotion candidates.
2. `item_description` is useful and often populated, but not universally
   reliable enough to be treated as guaranteed on the compact active index.
3. `image_url`, `item_note`, and `browse_path` currently look effectively
   empty in the live data and should not be treated as near-term first-class
   fields.
4. `child_product_name` / title context already exists and is usable today.
5. A fresh Distex CA Listings Import confirmed that the earlier odd payload
   shape was an import-lineage issue, not a Canada-specific issue.

Representative profile audit:

1. Basari World MX
   - `item_description`: 19.4%
   - `status`: 100%
   - `price`: 98.0%
   - `quantity`: 96.2%
   - `merchant_shipping_group`: 100%
   - `item_condition`: ~100%
2. Lifestyle US
   - `item_description`: 94.8%
   - `status`: 100%
   - `price`: 92.2%
   - `quantity`: 90.9%
   - `merchant_shipping_group`: 100%
   - `item_condition`: 100%
3. Distex CA after fresh import
   - `item_description`: 93.1%
   - `status`: 100%
   - `price`: 86.3%
   - `quantity`: 98.0%
   - `merchant_shipping_group`: 100%
   - `item_condition`: 100%
4. Ahimsa US
   - `item_description`: 98.6%
   - `status`: 100%
   - `price`: 86.5%
   - `quantity`: 74.3%
   - `merchant_shipping_group`: 100%
   - `item_condition`: 100%

Global active-row audit:

1. `item_description`: 42.8%
2. `status`: 88.3%
3. `price`: 83.2%
4. `quantity`: 81.3%
5. `merchant_shipping_group`: 88.3%
6. `item_condition`: 88.2%
7. `image_url`: 0%
8. `item_note`: 0%
9. `browse_path`: 0%

### Important architecture gap

Raw search-term facts alone are not enough for automated negation.

The system still needs a way to understand campaign intent:

1. what product or product family the campaign is meant to represent
2. whether a query is irrelevant versus merely low performing
3. whether a mismatch is a product mismatch, a targeting mismatch, or a
   campaign-structure problem

For MVP, the fastest context path should come from campaign-name parsing and
existing naming conventions, not from coupling this workflow to WBR rollups.

### Important implementation correction

The first shipped STR ingestion slice reused too much of the existing WBR
Amazon Ads sync abstraction.

That was the wrong boundary.

Why:

1. Amazon Ads report creation is report-type-specific:
   - `reportTypeId`
   - `adProduct`
   - `groupBy`
   - allowed `columns`
   - allowed `filters`
   - `timeUnit`
   - max window / retention
2. search-term reporting is **not** just "campaign sync with different columns"
3. the generic WBR Amazon Ads sync path hardcoded campaign-report assumptions
   that do not apply to search-term reports

Concrete failure we already observed:

1. the initial STR implementation inherited `groupBy: ["campaign"]`
2. Amazon rejected the request for `spSearchTerm`
3. the official v3 search-term contract requires `groupBy: ["searchTerm"]`

This plan should therefore treat STR ingestion as a separate Amazon Ads
reporting subsystem, not as a small extension of WBR campaign sync.

## Recommended architecture

Treat this as a new workflow with four layers:

1. catalog context layer
2. Amazon Ads report-ingestion layer
3. recommendation + review layer
4. execution layer

The Amazon Ads report-ingestion layer must be driven by the Amazon Ads report
spec, not by WBR sync conventions.

The catalog context layer is still an important dependency for later review
quality, but it should not dictate how Amazon report ingestion is modeled.

### Amazon Ads-native ingestion principles

The ingestion layer should follow these principles:

1. define report contracts per report type, not per legacy sync family
2. make `groupBy` explicit in the contract
3. make allowed columns explicit in the contract
4. make allowed filters explicit in the contract
5. make retention and max date window explicit in the contract
6. preserve Amazon-native row semantics first
7. derive app-specific interpretations later

In practice this means:

1. no inherited hardcoded `groupBy`
2. no assumption that SP / SB / SD all expose the same report family
3. no assumption that campaign-level WBR sync patterns map cleanly to
   search-term or adjacent report ingestion
4. no schema design driven first by legacy N-Gram or WBR convenience

## Product staging plan

### Stage 1: Setup + sync controls

Purpose:

1. let an operator enable and control STR ingestion per client
2. keep setup close to the existing ingestion/admin surfaces
3. make backfill and nightly behavior explicit and user-controlled

Recommended location:

1. `Client Data Access`
2. specifically the per-client surface, not a global all-client status page

Recommended Stage 1 responsibilities:

1. show STR connection/readiness state for the client
2. allow manual backfill by date range
3. allow "run daily refresh now"
4. allow enabling/disabling nightly STR sync
5. show latest STR sync run status
6. link forward to the Search Term Data surface

Important note:

1. this is not the eventual replacement for N-Gram / N-PAT
2. this is an operational setup/control surface

### Stage 2: Search Term Data

Purpose:

1. give operators a place to verify that STR ingestion worked
2. inspect the imported data before any action tools depend on it
3. provide coverage/status confidence during rollout

Recommended location:

1. under `reports`
2. recommended name: `Search Term Data`

Recommended Stage 2 responsibilities:

1. show ingestion status
2. show coverage window
3. show latest sync runs / failures
4. show row counts and simple health checks
5. allow filters by:
   - profile / marketplace
   - date range
   - campaign type
   - campaign name
   - search term
6. show lightweight row inspection for QA

Important note:

1. this is not a classic dashboard like WBR or PnL
2. this is a data inspection / verification surface
3. it is also not yet a decisioning tool

### Stage 3: Action tools

Purpose:

1. turn the ingested/searchable STR corpus into workflows that produce decisions
2. replace or supersede legacy N-Gram / N-PAT behaviors with better tooling

Recommended location:

1. separate routes/tools
2. not inside `reports`

Examples:

1. a new N-Gram successor
2. a new N-PAT successor
3. future search-term recommendation / review tools

Important note:

1. these are true product tools
2. they should have their own names and workflow identity
3. they should consume Stage 1/2 data plumbing, not be mixed into setup pages

## Dependency Phase: Higher-value catalog context expansion

### Goal

Expand the existing WBR listing ingestion into a richer, review-friendly
catalog context source that can support automated negative recommendations.

### Recommendation

Do **not** rely only on widening `wbr_profile_child_asins`.

Instead:

1. keep `wbr_profile_child_asins` as the profile’s canonical active child-ASIN
   index
2. promote a few missing operationally useful fields into first-class columns
3. add a richer content snapshot table for AI/review use

### Why not keep everything in `wbr_profile_child_asins`

Because the table currently serves as a compact active catalog index for WBR
rollups and ASIN mapping. It should stay cheap to query and easy to reason
about.

Large or semi-structured listing content belongs in a separate snapshot table.

### Proposed data model

#### 1. Extend `wbr_profile_child_asins` modestly

Promote the strongest operational Windsor fields into first-class columns:

1. `status`
2. `price`
3. `quantity`
4. `merchant_shipping_group`
5. `item_condition`

Treat `item_description` as optional:

1. it is often valuable and often populated
2. but it is not reliable enough across all profiles to be treated as a
   required compact-index field
3. it may still be promoted, but should be nullable and not assumed to exist

Do **not** promote these yet:

1. `image_url`
2. `item_note`
3. `browse_path`

Those three currently look effectively empty in live data.

#### 2. Add a richer content snapshot table

Suggested working name:

- `wbr_profile_catalog_content`

Suggested purpose:

1. store richer per-child-ASIN content context used by AI and analyst review
2. preserve historical refreshes without bloating the active ASIN index
3. allow future enrichment from non-Windsor sources if needed

Suggested columns:

1. `id`
2. `profile_id`
3. `child_asin`
4. `source_type`
5. `listing_batch_id`
6. `title`
7. `description`
8. `bullet_points jsonb`
9. `brand`
10. `category`
11. `image_url`
12. `attributes jsonb`
13. `raw_payload jsonb`
14. `content_hash`
15. `active`
16. `created_at`
17. `updated_at`

Important note:

1. `bullet_points jsonb` is an aspirational field, not a confirmed near-term
   Windsor field
2. the live Windsor audit did not confirm bullet-point availability through the
   current Amazon SP listing source
3. this richer content table should therefore allow partial population and be
   designed to accept later enrichment sources cleanly

### What may still be missing after Windsor expansion

The Windsor merchant listings feed may still not be enough for:

1. normalized bullet points
2. backend keywords
3. reliable brand field
4. precise variation-attribute structure

So the dependency phase should be designed to allow a later second source if
needed, not to assume Windsor is perfect.

Important clarification:

1. we do already have title/name context today
2. we do **not** have evidence yet that Windsor exposes bullet points through
   the current Amazon SP listing source
3. the public Windsor field-reference page did not confirm bullet fields in a
   way we could verify from static page content
4. bullets should therefore be treated as an unverified enrichment target, not
   as a guaranteed field we simply forgot to request

### Campaign-intent context dependency

The AI layer still needs a way to know what a campaign is for, but the MVP
should not depend on WBR/Pacvue-derived scope.

Recommended order of precedence:

1. campaign-name parsing from existing naming conventions
2. Amazon-native context from:
   - `Advertised product`
   - `Targeting`
   - `Purchased product`
3. optional fallback/manual overrides later if real accounts need them

Important decision:

1. do **not** treat WBR row mappings or Pacvue tags as a required dependency
   for the MVP STR path
2. do **not** treat `search_term_campaign_scope` as a required MVP table
3. if campaign-scope tables are revisited later, they should be additive
   fallback context, not the primary source of truth

## Phase 1: STR ingestion

### Goal

Replace the manual Pacvue export dependency with programmatic STR ingestion
while keeping the legacy file upload flow untouched.

### Phase 1 reset

The first attempt at Phase 1 proved that the implementation boundary was wrong.

Going forward:

1. Phase 1 must be rebuilt around official Amazon Ads report contracts
2. the initial verified path should be **Sponsored Products search-term v3**
3. any SB / SD support must be added only after the exact official contract is
   verified
4. Stage 1 and Stage 2 UI can remain, but the ingestion underneath them should
   be treated as an Amazon-native reporting system, not a WBR sync variant

### Amazon report priority

For this project, not every Amazon Ads console report matters equally.

Recommended priority:

1. `Search term`
   - core fact source for N-Gram / N-PAT replacement
   - start with documented SP support
   - do not assume SB / SD parity until verified in the official docs/API
2. `Advertised product`
   - high-value product-context source for understanding what was actually being
     promoted
3. `Targeting`
   - high-value intent/context source for understanding keyword vs ASIN target
     setup
4. `Purchased product`
   - high-value conversion-context source for understanding what actually sold

Useful next, but not core to the first automation slice:

1. `Campaign`
   - helpful summary context and likely worth adding once the core four are
     stable
2. `Placement`
   - useful diagnostic context, but not required for first-pass negation logic

Lower priority for this roadmap:

1. `Budget`
2. `Audience`
3. `Performance Over Time`
4. `Search Term Impression Share`
5. `Gross and Invalid Traffic`
6. `Prompts`
7. `Video`

### Product shape

Do **not** start by building a single monolithic "search-term workspace".

Instead, stage the rollout by surface type.

Current recommendation:

1. keep `/ngram` and `/npat` working exactly as they are
2. build Stage 1 setup/sync controls in `Client Data Access`
3. build Stage 2 `Search Term Data` under `reports`
4. build Stage 3 action tools separately from `reports`
5. allow fallback to legacy file upload during rollout

### Phase 1 outputs

1. programmatic Amazon Ads report fetch/storage driven by explicit report contracts
2. profile / marketplace scoping
3. date-window selection
4. report-type / ad-product source tagging
5. campaign-name-derived intent parsing for MVP context
6. parity checks against current Pacvue-based tool inputs
7. preservation of Amazon-native dimensions needed for later tools

### Ad-type coverage requirement

The product goal should not silently collapse into Sponsored Products only.

But the engineering path must be evidence-driven.

Immediate rule:

1. do **not** implement or claim support for an ad product unless the exact
   report contract has been verified from the official Amazon Ads docs/API

Desired eventual coverage:

1. Sponsored Products (`SP`)
2. Sponsored Brands (`SB`), including patterns such as `SBV`
3. Sponsored Display (`SD`)

Important note:

1. the exact report surface and fact grain may differ by ad type
2. the implementation should start with the verified SP path
3. SB / SD should be marked unsupported / unverified until the real report
   contracts are confirmed
4. if one ad type requires an adjacent report instead of the exact same
   search-term grain, that should still count toward eventual product scope
5. unsupported ad products should fail clearly, not masquerade as supported
6. the current Pacvue mixed export should be treated as a legacy convenience
   layer, not as evidence that Amazon-native `SB` and `SD` support can be
   implemented by copying the `SP` contract

### Suggested data model

Suggested working tables:

1. `amazon_ads_report_batches`
2. `search_term_daily_facts`
3. later adjacent Amazon-native context tables:
   - advertised product facts
   - targeting facts
   - purchased product facts

Suggested daily-fact grain:

1. `profile_id`
2. `report_date`
3. `campaign_type`
4. `campaign_id`
5. `campaign_name`
6. `ad_group_id`
7. `ad_group_name`
8. `search_term`
9. `keyword_type`
10. `keyword`
11. `keyword_id`
12. `targeting`
13. `match_type`
14. `impressions`
15. `clicks`
16. `spend`
17. `orders`
18. `sales`
19. `currency_code`
20. `source_payload`

Recommended natural key at this grain:

1. `profile_id`
2. `report_date`
3. `campaign_id`
4. `search_term`
5. `keyword_type`
6. `match_type`

Important note:

1. if Amazon returns both keyword-backed and targeting-expression-backed rows,
   `keyword_type` is part of the business meaning and should not be discarded
2. preserve Amazon-native row identity first; only collapse rows later if a
   downstream tool explicitly wants that
3. deduplicate at the persisted fact grain, not by heuristic text cleanup

Important implementation note:

1. the current WBR Amazon Ads sync is campaign-level and should not be treated
   as the base abstraction for STR or adjacent report ingestion
2. each Amazon Ads report family should carry its own:
   - `reportTypeId`
   - `adProduct`
   - `groupBy`
   - `columns`
   - `filters`
   - `timeUnit`
   - retention/window rules
3. the ingestion service should be organized around those report contracts
4. ad-group-level population should come from the actual report payload, not
   from assumption
5. if ad-group context is absent for a supported report, the schema should
   tolerate nulls rather than inventing structure

Recommended MVP decision:

1. MVP should start with documented SP search-term reporting only
2. the stored grain should preserve the Amazon dimensions returned by that
   report, including keyword/targeting context
3. later tool views can still project to campaign + search term where useful
4. do not throw away dimensions at ingest time just because the legacy tools
   did not use them

### Phase 1 grain decision

Legacy parity still matters, but ingestion should not be flattened down to
legacy tool grain at write time.

Decision:

1. MVP ingest should preserve documented Amazon row dimensions
2. MVP tooling may still read that data at campaign + search term grain when
   helpful for parity
3. `ad_group_id` and `ad_group_name` should remain nullable, populated only
   when the report actually provides them
4. `keyword_type`, `keyword`, `keyword_id`, and `targeting` should not be
   treated as optional luxury fields; they are part of the source semantics

### Rules

1. keep campaign names exactly as sourced
2. preserve raw payload for QA
3. preserve Amazon-native dimensions even if the first tools do not render all
   of them
4. dedupe at the persisted fact grain, not by heuristic text cleanup
5. support backfill plus trailing daily refresh
6. treat Pacvue upload as fallback until parity is proven
7. assume API backfill is retention-limited
8. keep unsupported/unverified report families explicitly out of scope until
   confirmed

### Retention / backfill note

Do not let the WBR Ads sync retention constant define STR behavior.

Phase 1 retention assumptions should come from the report contract for the
specific Amazon report family.

Current documented assumption:

1. `spSearchTerm` v3 retention is 95 days

So Phase 1 should assume:

1. live API backfill for documented SP search-term should use the documented
   retention window, not the older WBR sync constant
2. if a deeper historical corpus is needed initially, Pacvue exports may still
   be required as bootstrap input

### Acceptance criteria

1. same search-term family can power both N-Gram-like and N-PAT-like views
2. parity sample checks against Pacvue export are within agreed tolerance
3. import pipeline is stable enough to run without analyst file export

## Phase 2: Search Term Data surface

### Goal

Provide a lightweight operational/data inspection surface that proves the STR
pipeline is healthy before action tooling depends on it.

### Surface shape

This should be a `reports` surface, not a standalone workflow tool.

Recommended name:

1. `Search Term Data`

Recommended responsibilities:

1. display latest sync state
2. display sync coverage
3. display row counts and sample rows
4. display filterable imported search-term facts
5. make it easy to spot obvious ingestion/report-shape issues
6. make it obvious which report families / ad products are actually supported
7. make the currently supported ad product explicit in the setup/sync surface:
   - the existing live controls should be labeled as `Sponsored Products`
   - future `Sponsored Brands` / `Sponsored Display` controls should appear as
     separate ad-product sections, not as silent behavior hidden behind the
     same generic STR label

Recommended non-goals:

1. do not turn this into an AI recommendation workspace yet
2. do not turn this into a WBR/PnL-style dashboard
3. do not add publish/writeback actions here

### Acceptance criteria

1. an operator can confirm data landed correctly without using SQL
2. sync failures and coverage gaps are visible
3. the surface is useful for QA during rollout without pretending to be a full tool

## Phase 3: Recommendation + review tools

### Goal

Turn the current “analyst reads workbook and decides negatives” step into
dedicated action tools where AI and deterministic logic propose candidates and
the human approves them.

### Product shape

These should be separate tools, not `reports` pages.

Examples:

1. a new N-Gram successor
2. a new N-PAT successor
3. other targeted search-term action tools as the corpus matures

### Inputs to the model/recommendation layer

1. STR facts from Phase 1
2. catalog context from the dependency phase
3. campaign-name-derived intent context
4. Amazon-native context from:
   - `Advertised product`
   - `Targeting`
   - `Purchased product`
5. historical exclusions / prior negatives when available
6. performance heuristics

### Recommendation model

Do not start with a single opaque LLM step.

Use a hybrid pipeline:

1. deterministic candidate generation
2. structured relevance classification
3. confidence scoring
4. human review UI

### Deterministic candidate generation

Examples:

1. spend with zero orders
2. high clicks with low conversion
3. ASIN targets that clearly point to competitors for N-PAT
4. search terms that do not semantically match the intended product set

### AI classification tasks

Examples:

1. relevant vs irrelevant to promoted product
2. branded competitor vs generic research vs off-topic
3. low-confidence ambiguity flag
4. recommendation type:
   - negative exact
   - negative phrase
   - review only
   - do not negate

### Review workspace requirements

1. show why a term was recommended
2. show linked campaign / ad group / promoted product context
3. show matching child ASIN(s), titles, and catalog snippets
4. allow approval, rejection, and uncertainty handling
5. keep a full decision trail

### Review workspace outputs

1. approved negative candidates
2. rejected candidates
3. deferred / unsure queue
4. exportable change set

### Acceptance criteria

1. an analyst can review recommendations faster than the workbook process
2. low-confidence cases are obvious, not hidden
3. the review surface is trusted enough to replace most manual triage

## Phase 4: Direct Amazon writeback with approval/audit

### Goal

Allow approved negatives to be pushed directly into Amazon only after explicit
review and with a strong audit trail.

### Principles

1. no silent writeback
2. no writeback from raw model output
3. explicit approval required
4. full audit log required
5. fail closed on ambiguity

### Required controls

1. diff preview before execution
2. campaign/ad-group target destination preview
3. approval record with actor and timestamp
4. execution log with request/response payloads
5. clear error handling and retry state
6. rollback strategy where technically possible

### Suggested data model

Suggested working tables:

1. `search_term_negative_recommendations`
2. `search_term_negative_review_actions`
3. `search_term_publish_runs`
4. `search_term_publish_items`

### Acceptance criteria

1. a reviewer can approve a batch confidently
2. every writeback is attributable
3. failed writes are isolated and retryable
4. no direct publish happens without review-state validation

## Build order

Recommended order:

1. dependency phase: richer catalog context expansion
2. Stage 1 setup/sync controls in `Client Data Access`
3. refactor STR ingestion into an Amazon Ads-native report-contract system
4. rebuild Phase 1 on documented SP search-term support
5. Stage 2 `Search Term Data` under `reports`
6. validate and add `Sponsored Brands` support only after the real report
   contract is proven
7. validate and add `Sponsored Display` support only after the real report
   contract is proven
8. Phase 1 adjacent Amazon-native context ingestion:
   - `Advertised product`
   - `Targeting`
   - `Purchased product`
9. Stage 3 recommendation/action tools
10. Phase 4 direct Amazon writeback

## What should stay untouched for now

1. current `/ngram` upload flow
2. current `/npat` upload flow
3. current Pacvue-dependent analyst workflow

Those are the safety net during rollout.

## Biggest risks

1. over-reusing WBR campaign-sync abstractions may keep distorting Amazon Ads
   ingestion unless we explicitly separate the boundaries now
2. Amazon Ads report families may differ more sharply by ad product than the
   product vision assumes, requiring staged support instead of one uniform path
3. Amazon Ads report shape may not match Pacvue exports exactly enough on day
   one
4. Windsor listing data may be too shallow for high-confidence relevance
   decisions without enrichment
5. campaign-name-derived intent context may be noisier across clients than it
   first appears, pushing more value into Amazon-native context reports sooner
   than expected
6. direct writeback has the highest trust and safety burden

## Recommended next implementation slice

Current shipped state as of 2026-03-27 (ET):

1. Stage 1 `Search Term Automation` is live in `Client Data Access`
2. Stage 2 `Search Term Data` is live under `reports`
3. the STR ingestion layer has been refactored away from inherited WBR
   campaign-sync assumptions
4. the current verified implementation target is Sponsored Products
   `spSearchTerm`
5. persisted STR facts now preserve:
   - `keyword_id`
   - `keyword`
   - `keyword_type`
   - `targeting`
6. STR sync UI now auto-refreshes every 15 seconds while jobs are still
   running and surfaces worker polling progress

Live validation result:

1. a real Sponsored Products STR backfill completed successfully after the
   worker-sync redeploy
2. `Search Term Data` now shows real SP coverage for Whoosh US across
   `2026-03-01` through `2026-03-26`
3. the stored row shape is now validated as trustworthy enough to support
   Stage 3 tools
4. live stored facts matched a real Amazon Ads Sponsored Products search-term
   CSV for `2026-03-01` through `2026-03-10` at effectively exact totals:
   - export: `410,267` impressions, `5,382` clicks, `$7,395.89` spend,
     `1,701` orders, `$31,347.02` sales
   - DB: `410,261` impressions, `5,382` clicks, `$7,395.89` spend,
     `1,701` purchases, `$31,347.02` sales
5. the remaining broader-console impression discrepancy was resolved as a
   validation-surface mismatch, not an ingestion bug:
   - compare STR facts to Amazon `Search term` exports
   - do not compare STR facts to broader Sponsored Products Campaign Manager
     totals
   - impression-only queries can exist in broader SP totals without appearing
     in the search-term export, while clicks / spend / sales remain aligned

Important note:

1. do not treat STR runs queued before the worker-sync redeploy as valid
   evidence for the refactored implementation
2. current supported scope remains **Sponsored Products only**
3. SB / SD remain intentionally unverified / unsupported until their exact
   report contracts are confirmed
4. live SB contract probing has now started on Whoosh US:
   - a backend-only Amazon Ads probe on March 27, 2026 confirmed that
     `SPONSORED_BRANDS` accepts `reportTypeId = sbSearchTerm`
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
   - accepted live report ids from the probe:
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
5. the first productized SB backfill/export comparison did **not** yet fully
   validate `SB`:
   - Whoosh US live SB backfill for `2026-03-25` through `2026-03-26` loaded:
     - `283` rows
     - `28,829` impressions
     - `474` clicks
     - `$989.97` spend
     - `128` orders
     - `$2,158.26` sales
   - matching Amazon `Sponsored Brands > Search term > Daily` export for the
     same window showed:
     - `305` rows
     - `29,433` impressions
     - `550` clicks
     - `$1,066.07` spend
     - `176` orders
     - `$2,985.96` sales
   - the entire delta localizes to one missing campaign:
     - `Screen Shine - Pro | Brand | SB | PC-Store | MKW | Br.M | Mix. | Def`
   - raw Amazon `sbSearchTerm` payload for the successful Whoosh US run was
     checked directly and that campaign was absent from the raw API rows too
   - therefore:
     - current SB ingest logic is behaving consistently with the native
       `sbSearchTerm` API response
     - the mismatch appears to be between Amazon's native API surface and the
       Amazon console/export surface for at least one SB campaign family
     - SB remains **unvalidated**
6. current working hypothesis for the SB gap:
   - the missing campaign is a branded defensive SB family
   - campaign screenshots/export inspection show it is:
     - `Sponsored Brands`
     - `MANUAL` targeting
     - not video
     - likely a store-destination / product-collection-style campaign
       (`PC-Store` in internal naming)
   - either:
     - Amazon's `sbSearchTerm` API omits this SB family, or
     - Amazon has a freshness/reporting inconsistency between API and export
       surfaces
7. immediate follow-up:
   - Whoosh US and CA nightly sync is now enabled for both `SP` and `SB`
   - re-check the next nightly cycle before concluding the gap is permanent
   - if the same branded-defensive SB campaign is still absent from API while
     present in export, treat the issue as an Amazon-side contract/surface gap
     rather than an ingest bug

If live validation succeeds, the next active build slice should be:

1. keep the current validated SP path stable and clearly label it as
   `Sponsored Products` in the setup/sync surface
2. run a narrow `Sponsored Brands` report-contract validation slice:
   - confirm the exact Amazon report family / `reportTypeId`
   - confirm allowed `groupBy`
   - confirm allowed columns
   - confirm download payload field names and row grain
   - validate a real SB export against stored DB totals on one live account
3. only after SB is proven, run the same validation slice for
   `Sponsored Display`
4. add each ad product as its own operational sync area:
   - separate latest run state
   - separate backfill action
   - separate daily refresh action
   - separate nightly toggle
5. keep unsupported ad products visibly disabled / unverified rather than
   pretending the generic STR controls cover all ad products
6. only once SP + desired additional ad products are validated, define the
   first Stage 3 action tool on top of the trusted corpus

That sequence keeps the rollout understandable:

1. control the ingestion ✓
2. inspect the data ✓
3. validate the live Amazon-native pipeline in a real account ✓
4. validate additional ad products one by one ⏳
5. then build action tools on top of trusted data

Important product framing note:

1. the next true operator-facing workflow should not be treated as a generic
   filter/dashboard replacement for Pacvue or Amazon
2. the preferred product direction is to replace the current N-Gram flow in a
   minimally disruptive way:
   - native data already ingested
   - same practical workbook output
   - manual and AI-assisted paths side by side
   - existing review/export habits preserved until trust is earned
3. the detailed workflow framing for that replacement now lives in:
   - [N-Gram native replacement plan](/Users/jeff/code/agency-os/docs/ngram_native_replacement_plan.md)

## SB / SD validation plan

### Goal

Expand beyond Sponsored Products without repeating the original mistake of
assuming ad-product parity.

### Principles

1. treat `SB` and `SD` as separate Amazon report-contract projects
2. do not infer their contract from `SP`
3. do not enable their sync controls just because the UI already exists
4. validate each one against a real export before claiming support

### Sponsored Brands plan

1. identify the exact Amazon Ads report family intended to represent SB search
   term performance for this workflow
   - current live probe result: `reportTypeId = sbSearchTerm`
2. confirm the live request contract:
   - `adProduct`
   - `reportTypeId`
   - `groupBy`
   - allowed `columns`
   - retention/window behavior
   - current live probe result from Whoosh US on March 27, 2026:
     - `adProduct = SPONSORED_BRANDS`
     - `reportTypeId = sbSearchTerm`
     - `groupBy = ["searchTerm"]`
     - `groupBy = ["campaign"]` is rejected by Amazon for this report type
     - `keyword` and `targeting` are invalid SB columns
     - `keywordText` is valid
     - accepted candidate columns:
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
3. run a minimal API smoke test against one live profile with real SB activity
4. inspect the raw payload and confirm whether the returned grain matches the
   planned fact model or requires ad-product-specific handling
5. if the payload is compatible, add SB ingestion as a separate report
   definition and sync path
6. backfill one narrow live date window and validate against an Amazon SB
   search-term export
7. only then mark SB as supported and enable its controls

### Sponsored Display plan

1. repeat the same contract-validation path independently for SD
2. assume the highest chance of shape/semantic drift:
   - target semantics may differ
   - the closest useful report may not map 1:1 to SP/SB search-term grain
3. if SD requires adjacent-but-not-identical facts, model that explicitly
   instead of forcing it into the SP mental model
4. validate one live SD export against stored results before enabling support

### Pacvue parity note

The legacy Pacvue export can still be a useful parity target, but only with
careful interpretation:

1. a mixed Pacvue "search term report" may contain `SP`, `SB`, and `SD` rows
   in one file
2. for `SP` and likely `SB`, native Amazon search-term reporting is the
   intended replacement path
3. for `SD`, parity may require a reconstruction from different Amazon-native
   report families such as `matched target` and/or `targeting`
4. therefore "match the Pacvue file eventually" is still a valid product goal,
   but it should not collapse the implementation plan into a false assumption
   of identical native report contracts

### UI/ops implication after validation

Once an ad product is validated, the sync surface should expose it separately
under each marketplace:

1. `Sponsored Products`
2. `Sponsored Brands`
3. `Sponsored Display`

Each section should own:

1. its own latest run card
2. its own backfill controls
3. its own run-daily-refresh action
4. its own nightly sync toggle

This keeps operational truth aligned with the actual Amazon report contracts.
