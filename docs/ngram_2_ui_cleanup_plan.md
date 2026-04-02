# N-Gram 2.0 UI Cleanup Plan

_Last updated: 2026-04-02 (ET)_

## Purpose

This document now serves as the shipped-state reference for the `/ngram-2`
productization pass that was completed on `2026-04-01` through `2026-04-02`.

The current AI workflow is directionally strong enough to move out of
prompt-plumbing mode and into analyst-usage cleanup mode.

The next session should not treat this file as the primary implementation
brief. The current active milestone has moved back to full-run reliability and
model-output hardening.

## Current product reality

The current shipped direction is:

1. `/ngram-2` is a native Agency OS workbook-generation surface for search-term
   review.
2. The current AI goal is **analyst leverage**, not analyst replacement.
3. The AI workbook is now a **triage workbook**, not an auto-negation workbook.
4. The active pure-model preview path is:
   - single-campaign
   - two-step
   - context-pass first
   - term-triage second
5. The full workbook still preserves the analyst-centered workbook review flow.

Current triage workbook behavior:

1. `AI Recommendation` shows:
   - `SAFE KEEP`
   - `LIKELY NEGATE`
   - `REVIEW`
2. `AI Confidence`, `AI Reason`, and `AI Rationale` are populated.
3. `NE/NP` is intentionally left blank.
4. Mono/bi/tri scratchpad columns are intentionally left blank.
5. Analysts still decide the final negation expression.

## Product conclusion from testing

Recent testing across Whoosh, Ahimsa, and Distex suggests:

1. AI is strong at:
   - product-context inference
   - search-term triage
   - spotting likely wrong-fit traffic
2. AI is weaker at:
   - analyst-style `NE` vs `NP` choice
   - compact mono/bi/tri abstraction
   - safely compressing negatives without collateral risk
3. The current best product framing is:
   - AI reduces cold review work
   - analysts keep final control over workbook actions

## Shipped UI state

The following cleanup items are now implemented on `/ngram-2`:

1. obsolete migration/debug copy is gone
2. spend threshold moved into Step 1
3. Step 1 status copy is simpler
4. Step 3 is visually smaller and clearly optional
5. the old legacy/manual `Generate Workbook` button is removed
6. preview rows now default to a compact slice with `Show 10 more`, `Show all`,
   and `Show less`
7. campaign selector now supports multi-select
8. Step 5 reviewed-workbook upload now mirrors the legacy `/ngram` collect
   flow
9. Step 6 is a greyed-out “coming soon” direct-to-Amazon push card
10. Search Term Data now offers filtered CSV export

## V1 UI cleanup goals

The next implementation pass should optimize for:

1. clarity
2. speed
3. analyst confidence
4. less vertical sprawl
5. less migration/debug language

It should not reopen:

1. Responses API migration
2. extra model-generated summaries
3. deterministic gram tuning
4. another round of heuristic phrase synthesis

## Copy and structure changes

### Global

1. Remove the top migration/comparison box entirely.
2. Remove the words `native` and `experiment` from the page.
3. Rewrite the top copy so it simply explains that the page builds an N-Gram
   workbook from Agency OS search-term data.

### Step 1

Rename to:

1. `Choose Account, Marketplace, Date Range, and Ad Type`

Changes:

1. Replace first-load empty states like `No connected clients found` with a
   simple loading state.
2. Rename `Ad product` to `Ad type`.
3. Remove `BETA`.
4. Mark `SB` as `LIVE`.
5. Remove the extra explanatory copy under the ad-type cards.
6. Rename `Respect legacy exclusions` to `Campaign exclusions`.
7. Rewrite the exclusions helper copy in plain language.
8. Move spend threshold here.
9. Rename spend threshold to `Minimum Spend per Search Term`.
10. Default it to `0.00`.
11. Remove the run-readiness section.

### Step 2

Rename to:

1. `Data Summary`

Changes:

1. Keep only the `Imported Totals` and `Workbook Input` summary boxes.
2. Move the exclusions note into quieter helper text.
3. Remove the word `legacy`.
4. Reword the row-inspection section to a friendly spot-check instruction.
5. Open the spot-check destination in a new tab so analysts do not lose their
   selections.

### Step 3

Rename to something like:

1. `Optional: Preview AI Analysis on a Few Campaigns`

Changes:

1. Remove `Run Shipped AI Preview`.
2. Keep only the current pure-model preview action.
3. Rewrite the helper copy in plain analyst language.
4. Keep the campaign subset selector.
5. Make it visually obvious that this step is optional.
6. Collapse campaign results by default.
7. Sort or pin `LIKELY NEGATE` rows first inside each campaign preview.
8. Truncate or cap long result lists so the page does not become enormous.

### Step 4

Rename to:

1. `Generate Workbook`

Changes:

1. Rename the button to `Generate Workbook`.
2. Rewrite the description in plain language.
3. Remove `native` wording here too.

## Progress panel decision

The UI cleanup pass briefly added an inline activity panel, then removed it.

Why it was removed:

1. the displayed progress was mostly synthetic client-side copy
2. it did not communicate truthful backend progress
3. it was visually interesting but operationally low-value

The retained design rule is still the same:

1. do not use the Responses API
2. do not add extra model output just to make the UI feel alive
3. if a future progress surface returns, it should be fed by real backend
   milestones or not exist at all

Reason:

1. the current goal is no extra token cost
2. streaming alone is not the priority
3. app-generated progress lines are sufficient for v1

### Historical first version

Add an inline terminal-style activity panel that shows app-generated status
lines such as:

1. `Loading search-term data`
2. `Preparing campaign set`
3. `Running AI context pass`
4. `Running AI term analysis: chunk 2 of 6`
5. `Saving preview run`
6. `Preparing workbook`
7. `Done`

Important constraint:

1. this should be driven by application state and backend orchestration events
2. it should **not** ask the model for extra reasoning summaries
3. it should **not** require the Responses API in this first version

## Likely implementation files

Primary UI work will likely touch:

1. `frontend-web/src/app/ngram-2/page.tsx`

Potential supporting files:

1. `frontend-web/src/app/api/ngram-2/ai-prefill-preview/route.ts`
2. `frontend-web/src/lib/ngram2/aiPrefill.ts`
3. `frontend-web/src/lib/ngram2/aiCampaignEvaluator.ts`

Only touch backend or workbook files if the activity/progress panel needs a
small contract change later.

## Status of the original implementation order

1. obsolete copy, labels, and migration/debug sections were removed
2. spend threshold was moved and renamed into Step 1
3. Step 1 and Step 2 were simplified
4. `Run Shipped AI Preview` was removed
5. Step 3 became smaller and clearly optional
6. Step 4 naming/copy was simplified into one AI generate path
7. the spot-check view opens in a new tab
8. the temporary app-generated terminal/progress panel was later removed

## What is still relevant from this doc

1. the page should stay simple and analyst-centered
2. the workbook should stay triage-oriented
3. synthetic activity UI should not come back

## Restart checklist for the next session

1. read `docs/current_handoffs.md`
2. read `docs/search_term_automation_resume_prompt.md`
3. read `docs/ngram_2_pure_prompt_pivot_plan.md`
4. use this file only as shipped-state reference for the page cleanup
5. inspect `frontend-web/src/app/ngram-2/page.tsx`
6. treat full-run reliability, not UI cleanup, as the current open problem
