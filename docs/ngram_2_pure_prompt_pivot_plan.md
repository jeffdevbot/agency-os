# N-Gram 2.0 Pure Prompt Pivot Plan

_Last updated: 2026-04-02 (ET)_

## Purpose

Define the current strategic conclusion for the `/ngram-2` pivot away from
deterministic gram synthesis.

This document explains what we learned after shipping the first pure-model
prototype, testing it across brands, and reframing the AI job around analyst
leverage instead of analyst replacement.

## Core goal

The goal is **not** to replace the analyst.

The goal is to save analyst time by letting AI handle:

1. product-context inference
2. first-pass semantic triage
3. obvious keep vs likely-negate vs needs-review separation

while keeping the analyst in control of the final workbook actions.

If AI can consistently remove a large amount of cold review work and leave a
fast edit pass for the analyst, that is an exceptional operational win.

Success means:

1. materially reducing cold manual review work
2. preserving the existing workbook-centered review flow
3. keeping analysts and managers in control of final judgment
4. generalizing across brands without growing a brittle rules engine

## Why we pivoted

The recent pure-prompt experiment on:

1. `Screen Shine - Duo | SPM | MKW | Br.M | 9 - laptop | Perf`

showed that frontier models could get much closer to analyst behavior than
the current deterministic synthesis layer.

Key finding:

1. combined frontier-model exact recall reached `12/14` analyst exact
   negatives on that campaign
2. that is `86%` exact recall with no deterministic phrase-synthesis layer
3. the remaining problem was mostly phrase overproduction and `NE` / `NP`
   expression choice, not inability to reason about relevance

This initially suggested:

1. the hard part of N-Gram AI prefill is semantic judgment and phrase
   compression
2. models are better at that than deterministic token heuristics
3. our current synthesis path in `aiPrefill.ts` is likely the wrong
   abstraction for this problem

Subsequent live testing on Whoosh, Ahimsa, and Distex clarified the stronger
conclusion:

1. the model is good at deciding what looks relevant vs wrong-fit
2. the model is not yet reliably strong at expressing analyst-style final
   negatives in the right exact-vs-phrase shape
3. the best current product direction is therefore **AI triage**, not AI-owned
   final negation encoding

## Strategic conclusion

Deterministic code should not be responsible for deciding analyst-style
mono/bi/tri phrase output.

However, the current product also should not force the model to own the final
`NE` / `NP` / gram decision just because deterministic code stepped back.

Code should remain responsible for:

1. input shaping
2. code-first catalog retrieval and shortlist construction
3. structured-output validation
4. persistence
5. workbook export
6. auditability
7. minimal malformed-output safety checks

Code should stop being responsible for:

1. deriving phrase negatives from exact negatives using token heuristics
2. compressing semantic judgment into mono/bi/tri with deterministic rules
3. encoding analyst taste as a growing list of content-word exceptions

The analyst should currently remain responsible for:

1. final `NE` / `NP` choice
2. mono/bi/tri abstraction
3. final workbook expression

## Product framing

This pivot should be communicated clearly:

1. we are not trying to automate away analyst judgment
2. we are trying to remove as much repetitive first-pass work as possible
3. a system that gets a strong triage draft and leaves the final workbook
   expression to the analyst is still a major win

Non-goals:

1. full autonomy
2. Amazon writeback
3. deterministic parity with every analyst phrase choice
4. Whoosh-only optimization
5. a growing client-specific rules engine

## Current target architecture

### 1. Inputs to the model

The model should continue to receive:

1. campaign name
2. campaign theme
3. compact catalog candidate context, not the full catalog
4. search terms with spend/performance metrics
5. spend threshold / scope boundaries for the run

Important implementation update:

1. the current path no longer sends the full profile catalog into every
   campaign context prompt
2. code now ranks candidate products per campaign and sends only a compact
   shortlist into the model
3. this is now the preferred scaling direction for large catalogs

### 2. Current preferred model-owned output

The current preferred model output is:

1. matched product or product-family representative row
2. match confidence
3. term-level recommendation:
   - `KEEP`
   - `NEGATE`
   - `REVIEW`
4. per-term confidence
5. reason tag
6. one-sentence rationale

The pure-model path can still produce exact and phrase negatives in preview for
research purposes, but that is no longer the preferred product contract.

Current preferred workbook expression:

1. the workbook shows triage guidance
2. the workbook does **not** prefill `NE/NP`
3. the workbook does **not** prefill mono/bi/tri scratchpad values

### 3. Code-owned responsibilities

Code should still handle:

1. deterministic candidate retrieval before AI matching
2. structured output contract enforcement
3. dedupe
4. empty / malformed output rejection
5. persistence in `ngram_ai_preview_runs`
6. workbook writing
7. override capture for analyst-reviewed uploads

If any post-processing remains, it should be extremely thin:

1. remove exact duplicates
2. reject blank strings / malformed rows
3. reject obviously broken values

It should not attempt semantic phrase correction.

## Current retrieval architecture

The current matching architecture should now be thought of as:

1. code ranks catalog candidates from the full catalog using:
   - campaign identifier
   - SKU overlap
   - title overlap
   - family-token overlap
   - category/description overlap as weaker signals
2. AI sees only the top shortlist for context locking
3. pure-model preview is allowed one bounded expanded-shortlist retry if the
   first context pass returns `LOW` / no confident match
4. term-triage then runs only after product context is locked

Why this is the right direction:

1. the full catalog should not be treated as prompt input
2. large profiles can eventually contain tens of thousands of SKUs
3. code can search/rank large catalogs cheaply; the model should only be the
   final chooser over a compact candidate set

## Evaluation framework

We should evaluate the pivot on analyst leverage, not theoretical perfection.

Primary question:

1. how much manual review time does the AI remove?

Secondary metrics:

1. percentage of clear `SAFE KEEP` rows the analyst can ignore
2. percentage of clearly useful `LIKELY NEGATE` flags
3. false-positive `REVIEW` rate
4. analyst edit volume after triage
5. cross-brand stability of product-context matching

Working success threshold:

1. `70%+` useful first-pass coverage is a strong win
2. `80%+` on some accounts/campaigns is excellent
3. if the AI output is directionally right and easy to edit, it is valuable

## Validation path that already happened

### Phase 1: pure-model campaign prototype

A pure-model campaign path was implemented for:

1. one Whoosh campaign with known analyst output

It was then expanded to additional campaigns and brands.

### Phase 2: cross-brand check

The path was tested on:

1. Whoosh campaigns
2. one Ahimsa campaign
3. one Distex campaign

Key outcome:

1. Ahimsa showed that the prompt was not purely Whoosh-shaped
2. Distex exposed a family-level context-matching gap
3. the generalized family-match prompt rule improved Distex materially

### Phase 3: architecture decision

The first architecture decision has already been made:

1. pure-model triage is better than more deterministic synthesis work
2. analyst-owned final negation expression is the safer product contract for
   now
3. the next focus is analyst usability, not another immediate attempt to force
   AI-owned mono/bi/tri output

Future question, not current milestone:

1. whether a later version should reintroduce a tightly constrained AI-owned
   negative-expression layer after more evidence

## Implementation order from here

1. freeze further deterministic synthesis tuning in `aiPrefill.ts`
2. keep the bounded pure-model preview path in `/ngram-2`
3. keep the two-step context-plus-triage flow
4. keep workbook behavior triage-only
5. keep the retrieval-first shortlist architecture in front of AI matching
6. harden full-run reliability on large real-account windows before doing more
   product polish

## Current blocker after retrieval hardening

The current active issue is no longer UI cleanup.

The current active issue is a real full-run failure on a Whoosh US month-long
Step 4 workbook generation:

1. failing campaign:
   - `Screen Shine - Pro | SPM | MKW | Br.M | 2 - computer | Perf`
2. failing error:
   - `AI response validation failed after 3 attempts: Invalid confidence:`

What this means:

1. malformed or blank `confidence` still surfaced on a real large run
2. that happened despite Structured Outputs plus local validation/retry
3. the next session should investigate raw invalid payload shape, retry
   behavior, and per-campaign prompt sizing before making more UI changes

## Practical design constraints

### Keep

1. Step 3 bounded/subset preview flow
2. saved-run persistence
3. workbook export path
4. override capture and audit trail
5. structured outputs

### Replace

1. heuristic gram synthesis as the preferred product direction

### Preserve as fallback

1. manual workbook path
2. analyst review path

## Guiding principle

Let frontier models do what they are good at:

1. semantic judgment
2. product-family inference
3. first-pass triage

Let code do what code is good at:

1. contracts
2. storage
3. validation
4. exports
5. auditability

Let analysts do what analysts are good at:

1. final negation expression
2. abstraction into reusable negatives
3. judgment on borderline business-context cases

If we feel pressure to keep adding content-word rules or client-specific reason
tags to make the system work, that should be treated as evidence that the old
deterministic layer and overfit taxonomy are the wrong tools for this problem.

## Immediate next-session brief

Start the next session with this assumption:

1. deterministic phrase synthesis is no longer the preferred direction
2. AI-owned final `NE` / `NP` output is also not the current product target
3. the benchmark is analyst time saved, not exact rule-based parity
4. success is a strong triage workbook, not autonomous perfection
5. the next milestone is UI simplification and analyst usability on `/ngram-2`
