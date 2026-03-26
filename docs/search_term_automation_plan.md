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

Promote the most useful already-fetched Windsor fields into first-class
columns:

1. `item_description`
2. `item_note`
3. `image_url`
4. `status`
5. `price`
6. `quantity`
7. `merchant_shipping_group`
8. `item_condition`
9. `browse_path`

These are high-value and low-risk because Windsor already returns them.

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

### What may still be missing after Windsor expansion

The Windsor merchant listings feed may still not be enough for:

1. normalized bullet points
2. backend keywords
3. reliable brand field
4. precise variation-attribute structure

So the dependency phase should be designed to allow a later second source if
needed, not to assume Windsor is perfect.

### Campaign-product context dependency

The AI layer also needs a way to know what a campaign is for.

Recommended addition:

1. create a small campaign-product context layer that links campaigns or ad
   groups to intended child ASINs / row scope
2. do not overload `wbr_pacvue_campaign_map` for this

Possible inputs:

1. existing WBR row mappings
2. Amazon Ads entity data / bulk data
3. manual override when a campaign intentionally spans multiple products

## Phase 1: STR ingestion

### Goal

Replace the manual Pacvue export dependency with programmatic STR ingestion
while keeping the legacy file upload flow untouched.

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

### Rules

1. keep campaign names exactly as sourced
2. preserve raw payload for QA
3. dedupe at the persisted fact grain, not by heuristic text cleanup
4. support backfill plus trailing daily refresh
5. treat Pacvue upload as fallback until parity is proven

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

1. expand WBR listing ingestion into richer structured catalog context
2. design the campaign-product context layer
3. only then lock the final STR storage schema

That sequence reduces rework in the later AI recommendation phase.
