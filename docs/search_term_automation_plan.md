# Search Term Automation Plan

_Created: 2026-03-26 (ET)_

## Purpose

Define the phased replacement path for the current Pacvue-export-driven
N-Gram / N-PAT workflow while keeping the legacy tool untouched during rollout.

This plan covers:

1. richer catalog context ingestion needed for AI-quality recommendations
2. STR ingestion from Amazon Ads-connected data
3. AI-assisted recommendation and review
4. eventual direct writeback to Amazon with explicit approval and audit

It does **not** assume the existing `/ngram` and `/npat` routes should be
rewired in place. The preferred product direction is a new surface that can
ship alongside the legacy upload flow until the replacement is trusted.

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

The existing WBR campaign mapping is **not** enough for automated negation.

Today `wbr_pacvue_campaign_map` maps:

1. `campaign_name -> WBR row_id`

That is enough for WBR rollups, but not enough to answer:

1. which child ASINs a campaign is really promoting
2. which queries are irrelevant versus merely low performing
3. whether a search term mismatch is a catalog mismatch or a campaign-structure
   problem

## Recommended architecture

Treat this as a new workflow with four layers:

1. catalog context layer
2. STR fact layer
3. recommendation + review layer
4. execution layer

The catalog context layer is the dependency for the rest of the roadmap.

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

### Campaign-product context dependency

The AI layer also needs a way to know what a campaign is for.

Recommended addition:

1. create a small campaign-product context layer that links campaigns or ad
   groups to intended child ASINs / row scope
2. do not overload `wbr_pacvue_campaign_map` for this
3. treat this as distinct from campaign filtering / exclusion policy

Possible inputs:

1. existing WBR row mappings
2. Amazon Ads entity data / bulk data
3. manual override when a campaign intentionally spans multiple products

Suggested purpose of `search_term_campaign_scope`:

1. represent the intended promoted product scope of a campaign or ad group
2. support recommendation relevance decisions
3. support later review UI explanations
4. not act as a generic exclusion table for legacy campaign-name filters

## Phase 1: STR ingestion

### Goal

Replace the manual Pacvue export dependency with programmatic STR ingestion
while keeping the legacy file upload flow untouched.

### Amazon report priority

For this project, not every Amazon Ads console report matters equally.

Recommended priority:

1. `Search term`
   - core fact source for N-Gram / N-PAT replacement
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

Build a new search-term workspace entrypoint rather than mutating the current
legacy `/ngram` and `/npat` flow.

Current recommendation:

1. keep `/ngram` and `/npat` working exactly as they are
2. build a new reports/automation surface for imported STR data
3. allow fallback to legacy file upload during rollout

### Phase 1 outputs

1. programmatic STR fetch and storage
2. profile / marketplace scoping
3. date-window selection
4. campaign/ad-product source tagging
5. parity checks against current Pacvue-based tool inputs

### Suggested data model

Suggested working tables:

1. `search_term_import_batches`
2. `search_term_daily_facts`
3. `search_term_campaign_scope`

Suggested daily-fact grain:

1. `profile_id`
2. `report_date`
3. `campaign_type`
4. `campaign_id`
5. `campaign_name`
6. `ad_group_id`
7. `ad_group_name`
8. `search_term`
9. `match_type`
10. `impressions`
11. `clicks`
12. `spend`
13. `orders`
14. `sales`
15. `source_payload`

Recommended natural key at this grain:

1. `profile_id`
2. `report_date`
3. `campaign_id`
4. `search_term`
5. `match_type`

Deduplicate at that persisted fact grain, not by heuristic text cleanup.

Important implementation note:

1. the current WBR Amazon Ads sync is campaign-level only with
   `groupBy: ["campaign"]`
2. search-term ingestion will require a separate report definition / request
   path
3. ad-group-level STR support should be treated as an explicit design choice,
   not assumed "for free"
4. ad-group-aware ingestion should be treated as an explicit upgrade decision,
   not bundled implicitly into the first STR sync
5. if ad-group grain is required for review quality, that should be called out
   as added implementation complexity rather than an incidental extension of
   the current ads sync

Recommended MVP decision:

1. campaign + search term grain is sufficient for Phase 1 parity with the
   current Pacvue-driven N-Gram / N-PAT workflow
2. ad-group-aware grain becomes important when a single campaign contains
   materially different ad groups targeting different products
3. treat ad-group-aware ingestion as a Phase 2 enhancement unless Phase 1
   source testing shows that campaign-level grain is too coarse for reliable
   recommendation review

### Phase 1 grain decision

Campaign + search-term grain is sufficient for MVP parity with the current
N-Gram / N-PAT tools:

1. the existing Pacvue export format is campaign + search-term with no
   ad-group column
2. the current N-Gram and N-PAT tools do not use ad-group identity
3. ad-group grain adds implementation complexity without parity benefit at this
   stage

Decision:

1. MVP `search_term_daily_facts` grain is: `(profile_id, report_date,
   campaign_id, search_term, match_type)`
2. `ad_group_id` and `ad_group_name` columns should still exist in the schema
   as nullable, populated when the report source provides them
3. making them nullable from day one preserves the upgrade path without
   requiring a schema migration when Phase 2 relevance classification needs
   ad-group context
4. do not lock `ad_group_id` into the natural key until ad-group-aware MVP is
   an explicit requirement

### Rules

1. keep campaign names exactly as sourced
2. preserve raw payload for QA
3. dedupe at the persisted fact grain, not by heuristic text cleanup
4. support backfill plus trailing daily refresh
5. treat Pacvue upload as fallback until parity is proven
6. assume API backfill is retention-limited
7. keep `ad_group_id` and `ad_group_name` nullable until ad-group-aware grain is
   an explicit requirement

### Retention / backfill note

The current Amazon Ads WBR sync already documents an observed retention window
of about 60 days:

1. `OBSERVED_REPORT_RETENTION_DAYS = 60` in `amazon_ads_sync.py`

So Phase 1 should assume:

1. live API backfill will likely be capped to roughly 60 days
2. if a deeper historical STR corpus is needed initially, Pacvue exports may
   still be required as bootstrap input

### Acceptance criteria

1. same search-term family can power both N-Gram-like and N-PAT-like views
2. parity sample checks against Pacvue export are within agreed tolerance
3. import pipeline is stable enough to run without analyst file export

## Phase 2: AI recommendation + review workspace

### Goal

Turn the current “analyst reads workbook and decides negatives” step into a
review-first workflow where AI proposes candidates and the human approves them.

### Inputs to the model/recommendation layer

1. STR facts from Phase 1
2. catalog context from the dependency phase
3. campaign-product scope context
4. historical exclusions / prior negatives when available
5. performance heuristics

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

## Phase 3: Direct Amazon writeback with approval/audit

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
2. dependency phase: campaign-product context layer
3. Phase 1 STR ingestion
4. Phase 2 recommendation + review workspace
5. Phase 3 direct Amazon writeback

## What should stay untouched for now

1. current `/ngram` upload flow
2. current `/npat` upload flow
3. current Pacvue-dependent analyst workflow

Those are the safety net during rollout.

## Biggest risks

1. Amazon Ads report shape may not match Pacvue exports exactly enough on day
   one
2. Windsor listing data may be too shallow for high-confidence relevance
   decisions without enrichment
3. campaign-to-product context may be harder than STR ingestion itself
4. direct writeback has the highest trust and safety burden

## Recommended next implementation slice

The next active build slice should be the dependency phase, not direct STR
ingestion by itself.

Specifically:

1. use the completed live `raw_payload` audit to finalize promoted catalog
   fields:
   - promote `status`, `price`, `quantity`, `merchant_shipping_group`, and
     `item_condition`
   - keep `item_description` optional / nullable
   - do not promote `image_url`, `item_note`, or `browse_path` yet
2. expand WBR listing ingestion into richer structured catalog context
3. design the campaign-product context layer with a sharper definition of
   `search_term_campaign_scope`
4. lock the Phase 1 STR schema around the decided MVP grain:
   - campaign + search term natural key
   - nullable `ad_group_id` / `ad_group_name` columns for forward compatibility
5. only then build the first STR ingestion slice

That sequence reduces rework in the later AI recommendation phase.
