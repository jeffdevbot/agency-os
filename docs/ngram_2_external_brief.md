# N-Gram 2.0 External Brief

_Last updated: 2026-03-28 (ET)_

Use this document as a self-contained context brief for discussing the future
of `N-Gram 2.0` with an AI that does **not** have access to the Agency OS
codebase.

## What N-Gram does today

The agency's current `N-Gram` workflow is a workbook-driven negative-keyword
process.

Current legacy flow:

1. Analyst exports a search-term report from Pacvue.
2. Analyst uploads that file into `N-Gram`.
3. The tool generates an Excel workbook organized by campaign with:
   - mono / bi / tri-gram tables
   - search-term rows
   - scratchpads / review columns
4. Analyst reviews the workbook manually.
5. A manager may review the workbook.
6. The reviewed workbook is uploaded back into the tool.
7. The tool returns a cleaner negatives summary output for publishing.
8. Analysts still publish negatives manually in Pacvue / Amazon.

Important point:

- The workbook is not a side artifact. It is the center of the current team
  workflow.

## What N-Gram 2.0 is trying to change

`N-Gram 2.0` is **not** trying to replace the entire workflow all at once.

The first goal is narrower:

1. remove the manual Pacvue export/upload dependency from Step 1
2. use native Agency OS search-term data instead
3. still generate the same practical workbook shape
4. leave the downstream review/export flow intact

In short:

- replace the **input source**
- preserve the **familiar workbook process**

## What is already true right now

Current shipped reality:

1. `N-Gram 2.0` lives at a separate route from legacy `N-Gram`.
2. Legacy `/ngram` is still live and untouched.
3. `Sponsored Products` (`SP`) is the trusted path.
4. `Sponsored Brands` (`SB`) has partial validation, but is still treated
   cautiously because at least one legacy SB campaign family appears in Amazon
   export/console but not in the native API payload.
5. `Sponsored Display` (`SD`) is out of scope for now.

Most important milestone already proven:

1. Native `SP` data can now generate a workbook in `N-Gram 2.0`.
2. That workbook can be uploaded into Step 2 of the legacy `N-Gram` tool.
3. The legacy downstream flow accepts it successfully.

That means native Agency OS data has already replaced the old Pacvue export
for the first step of the current `SP` workflow.

## Current N-Gram 2.0 user flow

The current `N-Gram 2.0` product shape is intentionally simple.

### Step 1: Select native search-term data

The user chooses:

1. client
2. marketplace
3. ad product
4. date range
5. whether to respect the current campaign exclusions

Current legacy exclusions that can still be applied:

1. campaigns containing `Ex.`
2. campaigns containing `SDI`
3. campaigns containing `SDV`

### Step 2: Quick trust check

For `SP`, the page now shows a summary of the selected imported window before
workbook generation.

It includes things like:

1. imported clicks / spend / orders / sales
2. eligible rows for workbook input
3. number of campaigns / search terms
4. coverage start / end
5. ASIN-only row removals
6. skipped campaigns from legacy exclusions
7. warnings when the selected window looks incomplete or filtered heavily

There is also a secondary row-inspection link for admin QA, but that is not
meant to be the normal analyst workflow every time.

### Step 3: Generate workbook

If the `SP` window looks healthy, the user generates the native workbook.

That workbook is meant to behave like the current workbook-centered process,
not replace it with a new dashboard-first experience.

## What data powers N-Gram 2.0

The system now uses native Amazon Ads search-term facts stored inside Agency
OS instead of asking the user to upload a Pacvue export for Step 1.

For the current trusted `SP` path, the important fields are effectively:

1. campaign name
2. search term
3. impressions
4. clicks
5. spend
6. orders
7. sales

The stored corpus also preserves additional Amazon-native dimensions such as:

1. keyword id
2. keyword text
3. keyword type
4. targeting
5. match type

Those dimensions are important for future AI reasoning even though the first
native workbook slice mainly needs campaign + term + performance metrics.

## Trust model

The team does **not** want a workflow that requires manual export-vs-DB
validation every single time someone uses the tool.

Current trust model direction:

1. the system should show a lightweight summary by default
2. the user should inspect raw rows only when something looks off
3. manual export comparison should be an onboarding / debugging / exception
   step, not a mandatory preflight on every run

This matters because the AI path should plug into a workflow that feels
operationally realistic for analysts.

## What N-Gram 2.0 is not

The product is **not** trying to become:

1. a Pacvue clone
2. a giant search-term table product
3. a general Amazon Ads dashboard
4. a fully autonomous negative-keyword system on day one

The differentiated value is:

1. native data is already there
2. the workbook can still be generated
3. the existing review process is preserved
4. AI can later assist inside that proven workflow

## Most likely next milestone

If the current native `SP` workbook flow passes review, the next likely
milestone is an **optional AI-assisted prefill path**.

Important framing:

1. AI should sit beside the manual workbook path, not replace it immediately
2. AI should produce recommendations, not auto-publish negatives
3. analyst review and override should remain first-class
4. direct Amazon writeback is a later milestone, not the next one

## Best next AI slice

The most sensible next AI slice is:

1. stay `SP` only
2. use the same selected native data window as the workbook path
3. produce structured recommendations, not free-form prose only
4. keep campaign-level and gram-level reasoning visible
5. let the analyst accept / edit / reject recommendations

Likely shape:

1. user selects the same native run inputs
2. system builds a structured recommendation payload
3. each recommendation includes:
   - entity being reviewed
   - recommendation type
   - explanation / reason tag
   - confidence
4. analyst reviews before anything becomes publishable

## Constraints the AI design should respect

Any proposed future design should respect these product constraints:

1. legacy `/ngram` remains the safety net for now
2. `SP` is the trusted scope
3. `SB` should be treated as nuanced / partial, not universally trusted
4. workbook compatibility still matters
5. analysts and managers already understand the workbook review pattern
6. the team is not looking for a mandatory row-QA workflow on every run
7. the first AI slice should be assistive, reviewable, and reversible

## Good design questions to discuss next

If you are using this brief with another AI, useful questions to explore are:

1. What should the AI recommendation unit be:
   - per search term
   - per gram
   - per campaign section
   - some combination
2. Should AI output first land in:
   - an internal review UI
   - an AI-prefilled workbook
   - both
3. What recommendation labels / reason tags would be most useful for analysts?
4. How should confidence be shown without encouraging blind approval?
5. What is the smallest useful AI slice that clearly saves time without
   changing the team's trust model too aggressively?

## Short summary

`N-Gram 2.0` is currently a native-data replacement for Step 1 of the existing
N-Gram workflow.

It already works for `SP`:

1. select native data
2. review a lightweight trust summary
3. generate the familiar workbook
4. continue using the current downstream review/export process

The likely next step is an **optional AI-assisted prefill and review path**
built on top of that trusted `SP` foundation.
