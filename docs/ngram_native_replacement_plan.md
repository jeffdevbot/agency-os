# N-Gram Native Replacement Plan

_Created: 2026-03-27 (ET)_

## Purpose

Define the product plan for replacing the current Pacvue-export-driven
`/ngram` workflow with a native Agency OS workflow while preserving the parts
of the existing operator process that already work well.

This document is intentionally narrower than
[search_term_automation_plan.md](/Users/jeff/code/agency-os/docs/search_term_automation_plan.md).

That STR plan covers the ingestion/data foundation.

This document covers the operator-facing N-Gram replacement concept:

1. what the current workflow actually is
2. what should stay the same
3. what should improve
4. how the manual and AI-assisted paths should coexist
5. how to prove time-saving value without forcing a brand-new workflow too
   early

## Product framing

The product goal is **not**:

1. clone Pacvue
2. clone the Amazon Ads console
3. build a generic search-term dashboard
4. build a fancy filter table that already exists elsewhere

The product goal **is**:

1. replace the brittle Pacvue export/upload dependency with native data
2. preserve the proven human workflow where it is still useful
3. offer an AI-assisted path beside the manual path, not in place of it
4. keep the output compatible with the team's current review and publishing
   habits
5. demonstrate clear time savings and operational trust before pushing toward
   direct Amazon writeback

## Current workflow

Today the N-Gram flow is roughly:

1. analyst exports a Pacvue search-term report
2. analyst uploads the file into `/ngram`
3. Agency OS generates an Excel workbook with grams organized by campaign
4. analyst manually reviews/fills the workbook campaign by campaign
5. analyst optionally sends the workbook to a manager for review
6. analyst uploads the reviewed workbook back into Agency OS
7. Agency OS returns a cleaned/export-oriented workbook for easier copy/paste
8. analyst copies negatives campaign by campaign into Pacvue

This is slow, but it has useful qualities that should not be discarded
lightly:

1. analysts understand it
2. managers understand the review step
3. the workbook acts as a familiar approval artifact
4. the final output is aligned with how the team actually publishes today

## Replacement principle

The replacement should preserve the old flow's strengths while removing the
worst friction.

The first-generation native replacement should therefore feel like:

1. the same N-Gram job
2. with native data already available
3. with less export/import friction
4. with optional AI assistance
5. with the current manual review path still fully available

It should **not** require analysts to abandon the workbook process just to
prove that native ingestion works.

## Milestone status

### 2026-03-27 (ET): Step 1 native replacement is now proven for SP

The first real native replacement loop is now working for the current
Sponsored Products N-Gram workflow:

1. native SP search-term data was ingested into Agency OS
2. `/ngram-2` generated a native workbook for a selected client/marketplace
   and date range
3. that workbook was then uploaded into **Step 2 of the existing `/ngram`
   tool**
4. the legacy Step 2 flow accepted the file successfully and returned the
   expected workbook output

This is an important milestone because it proves:

1. native data can now replace the Pacvue export for the first step of the
   workflow
2. the generated workbook is compatible with the team's current downstream
   N-Gram review/export flow
3. team adoption does not require abandoning the legacy process immediately

Current scope of this milestone:

1. validated for `SP` only
2. `SB` remains not yet validated because the native `sbSearchTerm` API
   surface still does not fully match the Amazon console/export surface
3. `SD` remains out of scope for the current N-Gram 2.0 replacement path

### Recommended next slice

The next build slice should stay narrow and operator-facing:

1. keep the current `/ngram-2` route separate from legacy `/ngram`
2. improve the native `SP` path before expanding the AI workflow:
   - stronger pre-generation validation summary
   - clearer Step 1 replacement messaging
   - cleaner operator guidance around date range / client / marketplace
3. treat `SB` as visible but nuanced:
   - validated on at least one modern live account
   - not guaranteed complete for legacy Sponsored Brands campaign families
4. do **not** let unresolved legacy `SB` parity block incremental `SP`
   productization

## Old vs new

### Step 1: getting the data

Old:

1. export Pacvue STR
2. upload Pacvue STR into `/ngram`

New:

1. Agency OS ingests STR data automatically
2. analyst selects the client, marketplace, ad product, and date range
3. no manual Pacvue export is required for the normal case

Immediate value:

1. less manual prep
2. fewer stale files
3. lower risk of uploading the wrong date range or wrong marketplace

### Step 2: getting the n-gram workbook

Old:

1. the tool returns an Excel workbook with the grams organized

New:

1. the tool should still generate the workbook
2. workbook generation remains a first-class output, not a fallback
3. the user may then choose one of two next steps:
   - download workbook for manual review
   - continue into AI-assisted review

Important product point:

1. the native replacement should still be able to produce the familiar
   workbook shape because that is what the current workflow runs on
2. a new UI-only experience should not block the replacement effort

### Step 3: analyst review

Old:

1. analyst manually fills out the workbook campaign by campaign

New:

1. Manual path:
   - same basic workbook review process as today
2. AI-assisted path:
   - Agency OS pre-fills recommendations into the same conceptual structure
   - the user reviews, edits, and overrides those recommendations

Important product point:

1. the AI path should be optional
2. the manual path should remain available until the AI path earns trust
3. the output structure should stay close enough to current workbooks that the
   team can compare old and new directly

### Step 4: manager review

Old:

1. analyst may send the workbook to a manager
2. reviewed workbook is uploaded back to Agency OS for organization/cleanup

New:

1. preserve the same manager review path
2. if AI pre-filled the workbook, the manager still sees a familiar artifact
3. if the analyst stayed fully manual, the process should feel essentially the
   same as today

Important product point:

1. the native replacement should not force a brand-new approval model before
   the team wants one

### Step 5: publishing negatives

Old:

1. analyst copy/pastes negatives campaign by campaign into Pacvue

New:

1. default path should still support Pacvue-oriented export/upload
2. later path may optionally publish directly to Amazon
3. early direct-publish rollout should be deliberately narrow:
   - one selected campaign first
   - explicit user confirmation
   - encourage the user to validate results in Pacvue/Amazon before pushing
     broader scope

Important product point:

1. direct publish is a later trust milestone, not the first milestone

## Stage 2: data trust layer

Before the N-Gram replacement can be trusted, the user needs a clear way to
verify that the imported data is correct.

This is what the current `Search Term Data` surface is for.

The purpose of Stage 2 is:

1. allow basic inspection of imported native data
2. let the user choose a date range and compare totals against Amazon
3. build confidence in the ingestion before analysts depend on it

Stage 2 is **not** the end product.

It is the trust layer underneath the real workflow.

### What the user should validate

For a chosen date range and marketplace/ad product:

1. clicks
2. spend / total cost
3. orders / purchases
4. sales

Impressions need a specific warning:

1. compare STR facts to Amazon `Search term` exports, not broad Campaign
   Manager totals
2. broader console totals may show materially higher impressions
3. that difference is expected because impression-only queries can exist in
   broader totals without appearing in the search-term export

So yes: the Stage 2 screen should explicitly instruct the user to compare
native Agency OS totals to the matching Amazon `Search term` export.

## What should differentiate Agency OS from Pacvue/Amazon

The differentiated value is **not** raw filtering alone.

Amazon and Pacvue already let users filter by:

1. spend
2. clicks
3. sales
4. orders
5. campaign
6. query

So Agency OS should not pitch itself as "a better filter table."

The differentiation should come from:

1. native data already being present in the workflow
2. N-Gram-ready output generation
3. campaign-aware exclusions/defaults aligned with the agency's naming
   conventions
4. AI-assisted triage layered on top of the existing workbook logic
5. a smoother review-to-export path than the current Pacvue export/import loop

## First shippable replacement milestone

The first real milestone after the data foundation should be:

1. select imported native STR data
2. generate the same practical N-Gram workbook shape the team already uses
3. allow the analyst to choose:
   - download workbook
   - continue to AI-assisted review

This is the clearest old-to-new replacement story:

1. no Pacvue export required
2. same familiar workbook output
3. optional AI path beside it

## Recommended v1 product shape

### Entry point

A new N-Gram-native surface should start with:

1. client
2. marketplace
3. ad product
4. date range
5. campaign-scope toggles / exclusions

The existing campaign exclusions used by current N-Gram should be represented
explicitly, likely as preselected toggles/default filters rather than hidden
magic.

Examples:

1. exclude `Ex.`
2. exclude `SDI`
3. exclude `SDV`

This keeps the native workflow aligned with the existing analyst expectations.

### Output choices

After the user selects scope, the UI should present two clear next steps:

1. `Generate Workbook`
2. `Run AI Prefill`

These should be parallel paths, not one forcing the other.

### Manual path

Manual path should closely replicate the old workflow:

1. generate workbook
2. analyst reviews/fills it out
3. analyst/manager review happens externally if desired
4. reviewed workbook comes back for cleanup/export
5. user uploads into Pacvue or later Amazon

### AI-assisted path

AI path should use the same underlying data but not promise magic.

V1 AI path should:

1. prefill likely decisions
2. leave the user in control
3. produce something that can still be reviewed like the manual output

V1 AI path should **not** depend on solving every possible context problem
before shipping.

The early AI input context should likely include:

1. campaign naming conventions
2. campaign/ad-group/search-term context
3. marketplace
4. product/catalog context already available in WBR
5. agency review rules / reason tags

It is reasonable to add richer ASIN-level or listing-level intelligence later,
but v1 should not be blocked on perfect enrichment if the workflow can already
save time.

## Suggested side-by-side product story

The product should make the comparison to the old process easy to understand.

Example framing:

Old:

1. export Pacvue STR
2. upload into N-Gram
3. generate workbook
4. fill it manually
5. reupload for cleanup
6. copy into Pacvue

New:

1. data already ingested automatically
2. generate workbook from native data
3. choose manual or AI-assisted review
4. keep the same review/approval pattern if desired
5. export for Pacvue or later publish directly to Amazon

This is a better product story than "we built a search-term dashboard."

## Non-goals for the first replacement phase

Do not overreach too early.

Non-goals for the first native N-Gram replacement phase:

1. full direct publish by default
2. replacing every manager review habit with a brand-new UI process
3. building a massive Pacvue clone
4. forcing all analysts into AI mode
5. waiting for perfect SB/SD parity before proving the core SP replacement

## Rollout sequence

Recommended order:

1. trust the data
   - Stage 2 validation surface
   - explicit Amazon export comparison
2. replace the first painful workflow step
   - native data selection instead of Pacvue export/upload
3. preserve the current useful artifact
   - workbook generation
4. offer optional acceleration
   - AI prefill beside manual review
5. preserve the current review and export path
6. only then experiment with direct publish

## Open design questions

These should remain open until the data foundation is further along:

1. how closely should the new workbook mirror the existing workbook tabs and
   formatting?
2. should the AI path prefill directly into a workbook, or into an internal
   review UI that can also export a workbook?
3. what campaign exclusions should be default-on vs optional?
4. when should SB join the same replacement flow versus remaining SP-first?
5. when should direct Amazon publishing be exposed to users beyond a
   campaign-limited safety rollout?

## Immediate recommendation

Once SP plus desired additional ad-product ingestion is trustworthy enough, the
next workflow milestone should be:

1. native data selection
2. native workbook generation
3. side-by-side manual vs AI-assisted path

That is the clearest, least disruptive replacement of the current N-Gram
workflow and the easiest place to prove real time savings.
