# N-Gram 2.0 Pure Prompt Pivot Plan

_Last updated: 2026-03-31 (ET)_

## Purpose

Define the pivot away from deterministic gram-synthesis logic in `/ngram-2`
toward a frontier-model-led exact + phrase negative workflow.

This document is intended to be the operating brief for the next session.

## Core goal

The goal is **not** to replace the analyst.

The goal is to save analyst time by letting AI do as much high-quality
prework as possible while keeping the analyst in control of the final result.

If AI can consistently get us `70%` to `86%` of the way there on exact and
phrase negatives, that is an exceptional operational win.

Success means:

1. materially reducing cold manual review work
2. preserving the existing workbook-centered review flow
3. keeping analysts and managers in control of final judgment
4. generalizing across brands without growing a brittle rules engine

## Why we are pivoting

The recent pure-prompt experiment on:

1. `Screen Shine - Duo | SPM | MKW | Br.M | 9 - laptop | Perf`

showed that frontier models could get much closer to analyst behavior than
the current deterministic synthesis layer.

Key finding:

1. combined frontier-model exact recall reached `12/14` analyst exact
   negatives on that campaign
2. that is `86%` exact recall with no deterministic phrase-synthesis layer
3. the remaining problem was mostly phrase overproduction, not inability to
   reason about relevance

This strongly suggests:

1. the hard part of N-Gram AI prefill is semantic judgment and phrase
   compression
2. models are better at that than deterministic token heuristics
3. our current synthesis path in `aiPrefill.ts` is likely the wrong
   abstraction for this problem

## Strategic conclusion

Deterministic code should not be responsible for deciding the analyst-style
mono/bi/tri phrase output.

That part should be model-owned.

Code should remain responsible for:

1. input shaping
2. structured-output validation
3. persistence
4. workbook export
5. auditability
6. minimal malformed-output safety checks

Code should stop being responsible for:

1. deriving phrase negatives from exact negatives using token heuristics
2. compressing semantic judgment into mono/bi/tri with deterministic rules
3. encoding analyst taste as a growing list of content-word exceptions

## Product framing

This pivot should be communicated clearly:

1. we are not trying to automate away analyst judgment
2. we are trying to remove as much repetitive first-pass work as possible
3. a system that gets a strong first draft and leaves the last 15% to 30% for
   analyst review is still a major win

Non-goals:

1. full autonomy
2. Amazon writeback
3. deterministic parity with every analyst phrase choice
4. Whoosh-only optimization

## New target architecture

### 1. Inputs to the model

The model should continue to receive:

1. campaign name
2. campaign theme
3. matched product/catalog context
4. search terms with spend/performance metrics
5. spend threshold / scope boundaries for the run

### 2. Model-owned output

The model should directly return:

1. matched product
2. match confidence
3. term-level judgments
4. exact negatives
5. phrase negatives
6. optional rationale / reason tags
7. optional confidence fields where helpful

Important change:

1. the model should decide the minimum meaningful phrase negative directly
2. the system should not synthesize phrase negatives afterward with code

### 3. Code-owned responsibilities

Code should still handle:

1. structured output contract enforcement
2. dedupe
3. empty / malformed output rejection
4. persistence in `ngram_ai_preview_runs`
5. workbook writing
6. override capture for analyst-reviewed uploads

If any post-processing remains, it should be extremely thin:

1. remove exact duplicates
2. reject blank strings / malformed rows
3. possibly reject obviously broken values

It should not attempt semantic phrase correction.

## Evaluation framework

We should evaluate the pivot on analyst leverage, not theoretical perfection.

Primary question:

1. how much manual review time does the AI remove?

Secondary metrics:

1. exact recall vs analyst
2. phrase recall vs analyst
3. junk phrase rate
4. overbroad phrase rate
5. analyst edit volume after prefill

Working success threshold:

1. `70%+` useful first-pass coverage is a strong win
2. `80%+` on some accounts/campaigns is excellent
3. if the AI output is directionally right and easy to edit, it is valuable

## Validation plan

### Phase 1: rebuild one campaign end-to-end

Implement a pure-model campaign path for:

1. one Whoosh campaign with known analyst output

Run:

1. same input window
2. same campaign
3. same analyst benchmark
4. no deterministic phrase synthesis

Compare:

1. exact negatives
2. phrase negatives
3. junk phrases
4. missing analyst signals

### Phase 2: cross-brand check

Do not stop at Whoosh.

Run the same pure-model pattern on:

1. one additional Whoosh campaign
2. one Ahimsa campaign
3. one Distex campaign

This is the key anti-overfitting check.

### Phase 3: architecture decision

If the pure-model workflow consistently outperforms the heuristic synthesis
layer, move to:

1. model-generated exact negatives
2. model-generated phrase negatives
3. thin validation only

If it fails badly cross-brand, revisit the contract and prompting before
reintroducing deterministic synthesis.

## Implementation order

1. freeze further deterministic synthesis tuning in `aiPrefill.ts`
2. define a new strict structured-output schema for:
   - exact negatives
   - phrase negatives
   - optional review bucket
3. build a bounded single-campaign pure-model path in `/ngram-2`
4. export the result into the existing workbook shape
5. compare against analyst-reviewed outputs
6. validate on at least one non-Whoosh brand before concluding the pivot works

## Practical design constraints

### Keep

1. Step 3 bounded/subset preview flow
2. saved-run persistence
3. workbook export path
4. override capture and audit trail
5. structured outputs

### Replace

1. heuristic gram synthesis for mono/bi/tri prefills

### Preserve as fallback

1. manual workbook path
2. analyst review path

## Guiding principle

Let frontier models do what they are good at:

1. semantic judgment
2. phrase compression
3. minimum meaningful negative selection

Let code do what code is good at:

1. contracts
2. storage
3. validation
4. exports
5. auditability

If we feel pressure to keep adding content-word rules to make the system work,
that should be treated as evidence that the deterministic layer is the wrong
tool for the job.

## Immediate next-session brief

Start the next session with this assumption:

1. deterministic phrase synthesis is no longer the preferred direction
2. the next milestone is a pure-model single-campaign prototype in `/ngram-2`
3. the benchmark is analyst time saved, not exact rule-based parity
4. success is a strong editable first draft, not autonomous perfection
