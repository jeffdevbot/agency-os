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
6. Phase 1 adjacent Amazon-native context ingestion:
   - `Advertised product`
   - `Targeting`
   - `Purchased product`
7. expand ad-product support only where the official report contracts are
   verified
8. Stage 3 recommendation/action tools
9. Phase 4 direct Amazon writeback

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

Stage 1 UI is shipped (2026-03-27) and Stage 2 `Search Term Data` is now
shipped as well.

Current shipped surfaces:

1. `Client Data Access` / `Search Term Automation`
   - per-marketplace WBR profile cards with:
   - latest STR sync run status
   - backfill date-range controls + Run Backfill button
   - Run Daily Refresh Now button
   - Enable/Disable Nightly Sync toggle (bound to `search_term_auto_sync_enabled`)
2. `Search Term Data`
   - latest sync state
   - coverage
   - profile/date/type/text filters
   - raw fact inspection without SQL

However, the current ingestion implementation needs a refactor before it should
be treated as trusted.

Reason:

1. the initial STR ingestion path reused campaign-sync assumptions from WBR
2. the first live run failed because `spSearchTerm` requires
   `groupBy=["searchTerm"]`, while the inherited implementation sent
   `groupBy=["campaign"]`
3. SB / SD support was also assumed before the official contract was verified

The next active build slice should therefore be:

1. refactor STR ingestion away from WBR campaign-sync abstractions
2. introduce explicit per-report Amazon Ads contracts:
   - `reportTypeId`
   - `adProduct`
   - `groupBy`
   - `columns`
   - `filters`
   - `timeUnit`
   - retention/window rules
3. rebuild the Phase 1 path around documented `spSearchTerm` support first
4. update the schema/model to preserve:
   - `keyword_type`
   - `keyword`
   - `keyword_id`
   - `targeting`
5. update Stage 1/2 UI copy so support scope and retention claims match the
   real Amazon contract
6. treat SB / SD as unverified / unsupported until the exact official contract
   is confirmed

That sequence keeps the rollout understandable:

1. first control the ingestion ✓
2. then inspect the data ✓
3. then correct the ingestion boundary so the data is truly trustworthy
4. then build action tools on top of trusted data
