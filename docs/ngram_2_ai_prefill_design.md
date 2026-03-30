# N-Gram 2.0 AI Prefill Design

_Last updated: 2026-03-30 (ET)_

## Purpose

Define the first AI-assisted `N-Gram 2.0` workflow for Agency OS.

This design assumes:

1. `Sponsored Products` (`SP`) only for v1
2. native Agency OS search-term facts are already available and trusted enough
   for workbook generation
3. the output should remain the familiar N-Gram workbook shape
4. the manual path remains available in parallel

This document is intentionally about the **AI-prefill path**, not the broader
native-ingestion story.

## Product goal

The goal is to reduce cold manual review work without replacing the current
team process too aggressively.

The AI path should:

1. use the same selected native data window as the workbook path
2. understand campaign context, not just raw query metrics
3. make structured, reviewable recommendations
4. prefill only when evidence is strong enough
5. leave analysts and managers in control

The goal is **not**:

1. direct Amazon or Pacvue writeback
2. fully autonomous negation
3. replacing the workbook with a dashboard-only process
4. forcing every analyst into AI mode

## Summary of the proposed design

The proposed AI path is:

1. user selects native `SP` data in `N-Gram 2.0`
2. user sets a spend threshold
3. system provides campaign context plus Windsor catalog context to AI
4. AI evaluates qualifying search terms
5. system converts term-level judgments into **conservative gram prefills**
6. workbook is generated in the same practical shape as legacy N-Gram
7. analyst reviews, edits, and overrides
8. downstream upload / cleanup / publishing flow stays the same

Important nuance:

- The AI should not jump directly from one bad search term to one bad gram.
- It should judge search terms first, then only prefill grams when the
  evidence is sufficiently strong across multiple terms.

That is the main safety layer in this design.

## Inputs

### 1. Native SP search-term facts

Use the same selected native window already chosen in `N-Gram 2.0`.

Core metrics used in the current trusted path:

1. campaign name
2. search term
3. impressions
4. clicks
5. spend
6. orders
7. sales

Additional native dimensions already preserved by Agency OS and useful for AI:

1. keyword id
2. keyword text
3. keyword type
4. targeting
5. match type

### 2. WBR listing/product context

Use WBR listing data as the product context source.

Useful fields:

1. ASIN
2. title
3. description
4. category

This gives the AI a product anchor instead of forcing it to reason from search
terms alone.

### 3. User-defined spend threshold

Before running AI prefill, the user sets a spend threshold.

Rules:

1. search terms below threshold are excluded from AI evaluation
2. they remain in the workbook as normal rows
3. their AI-prefill cells stay blank
4. they are not marked negative automatically
5. they are not treated as positive evidence either

Why this matters:

1. reduces token usage
2. reduces low-signal AI calls
3. focuses review on terms that have actually spent enough to matter

This should be configured **per run** at AI-prefill time, not as a global
setting hidden elsewhere in the product.

## Step 1: Campaign-to-product mapping

### Primary idea

Use the campaign name plus Windsor child-ASIN catalog context to infer product
context and campaign theme.

The first segment before the first `|` is the product-family candidate.

Examples:

1. `Screen Shine - Pro | ...` -> `Screen Shine - Pro`
2. `Screen Shine - Go XL | ...` -> `Screen Shine - Go XL`
3. `Sport Shine - Go XL | ...` -> `Sport Shine - Go XL`

### Matching strategy

Current implemented direction:

1. skip clearly non-product-specific brand / mix / defensive lanes up front
2. for runnable campaigns, send the campaign name and compact Windsor catalog
   rows to the model in the **same call** as search-term evaluation
3. ask the model to return:
   - `matched_product`
   - `match_confidence`
   - `match_reason`
   - `term_recommendations[]`
4. if product confidence is low, mark the campaign as review/ambiguous rather
   than forcing prefills

If mapping is ambiguous or missing:

1. AI should not confidently prefill grams for that campaign
2. campaign can be flagged as `REVIEW`
3. search-term-level reasoning may still be shown, but conservative output
   should dominate

Important clarification:

1. `Brand` campaigns such as
   `Brand | SPM | MKW | Br. | Mix. | Def`
   are expected ambiguous cases
2. those campaigns often do not map cleanly to one product-family context
3. they should be treated as a normal `mixed / review` lane
4. they should **not** be treated as data-quality failures by default

### Why this matters

Product families in the same brand can be close enough that fuzzy-only mapping
will sometimes be wrong.

Wrong product context would poison the entire AI evaluation for the campaign.

### Guardrail now in code

The model output for product match + term recommendations should be treated as
an explicit contract, not a best-effort suggestion.

Current implementation validates that:

1. the AI response is valid JSON
2. the matched product references a real catalog row
3. high/medium confidence cannot be returned without a product
4. low confidence must not also claim a product
5. every input search term appears exactly once in the output
6. missing terms, duplicate terms, or bad enums hard-fail the preview

This was added specifically to prevent malformed model output from silently
polluting gram synthesis.

## Step 2: Campaign-theme parsing

Besides product mapping, parse the campaign's targeting theme from its naming
convention.

Example:

1. `2 - computer`
2. `7 - eyeglasses`
3. `17 - sunglass`

This theme is critical because the same search term may be correct for one
campaign and incorrect for another.

Example:

1. `eyeglass cleaner` may be reasonable in a sports/eyewear campaign
2. the same term may be wrong for a monitor/laptop cleaning campaign

The AI should receive both:

1. product context
2. campaign targeting theme

## Step 3: Spend-threshold filtering

For each campaign:

1. gather search terms in the selected date window
2. remove terms below the user-defined spend threshold from AI evaluation
3. keep them visible in the workbook with blank AI-prefill fields

This should happen before any LLM call.

## Step 4: AI relevance evaluation

### Unit of AI judgment

The first AI judgment unit should be the **search term**, not the gram.

That is safer and easier to reason about.

For each qualifying search term, the AI receives:

1. search term
2. performance metrics
3. matched product context
4. campaign targeting theme
5. keyword / targeting / match-type context when available

### Example context

For a campaign like:

`Screen Shine - Pro | SPM | MKW | Br.M | 2 - computer | Perf`

The AI context could look like:

1. Product:
   - `WHOOSH! Screen Shine Pro`
   - large refillable screen-cleaner spray
   - for TVs / monitors / laptops
   - not travel size
   - not eyeglass cleaner
2. Campaign theme:
   - computer / monitor / laptop
3. Search term:
   - `travel size screen cleaner`

### AI output contract

Per evaluated search term, the AI returns:

1. recommendation:
   - `KEEP`
   - `NEGATE`
   - `REVIEW`
2. confidence:
   - `HIGH`
   - `MEDIUM`
   - `LOW`
3. reason tag:
   - short controlled explanation
4. short rationale:
   - concise natural-language explanation for auditability

Presentation guidance:

1. keep both `reason_tag` and `rationale` in the structured AI output
2. the workbook should likely surface the compact `reason_tag` by default
3. the fuller `rationale` is still valuable for auditability and debugging,
   but should only be written into the workbook if there is a clear, low-noise
   place for it
4. if there is a tradeoff, keep the workbook compact and preserve the fuller
   rationale in the underlying structured output or a secondary review surface

Suggested reason-tag families:

1. core_use_case
2. wrong_category
3. wrong_product_form
4. wrong_size_variant
5. wrong_audience_theme
6. competitor_brand
7. cloth_primary_intent
8. accessory_only_intent
9. foreign_language
10. ambiguous_intent

## Step 5: Conservative gram synthesis

This is the most important safety layer.

### Why it exists

A single negative search term does **not** automatically prove that a mono,
bi, or tri-gram should be negated at campaign level.

Example:

1. Search term: `travel size screen cleaner`
2. AI judgment: `NEGATE`

That does **not** mean:

1. `travel` should always be negated
2. `size` should always be negated
3. `travel size` should always be negated

### Rule

The AI should judge **search terms first**.

Then a deterministic synthesis layer should decide whether any grams are safe
to prefill.

### Recommended synthesis logic

A gram becomes eligible for prefill only when:

1. it appears repeatedly across `NEGATE` search terms in the same campaign
2. the associated negative evidence is meaningful enough by spend / click
   share, not just count
3. it does not appear in strong `KEEP` terms for the same campaign context
4. the AI confidence on the underlying negative terms is strong enough

Possible conservative heuristic:

1. only consider grams appearing in at least `N` negative terms
2. require most supporting terms to be `NEGATE + HIGH`
3. block prefill if the gram appears in any `KEEP + HIGH` term with meaningful
   spend
4. otherwise downgrade to `REVIEW`

The exact thresholds can be tuned later, but the important point is:

- term judgments are AI-driven
- gram prefills are AI-informed but **gated by deterministic synthesis**

## Step 6: Workbook prefill

The output should remain the same practical workbook shape used by the current
team flow.

Important requirement:

- Do **not** hardcode specific spreadsheet column letters in the design.

The workbook generator owns the sheet structure.

The design requirement is:

1. prefill the existing negative/review fields in the workbook-compatible
   structure
2. keep the output aligned with the current downstream review/upload flow

### Prefill behavior

1. `NEGATE + strong synthesized gram evidence`
   - prefill the gram recommendation
2. `KEEP`
   - leave blank
3. `REVIEW`
   - flag for analyst attention, but do not prefill as a negative
4. below spend threshold
   - leave blank
5. ambiguous product mapping / mixed campaign context
   - bias toward blank or review, not negative prefill

## Analyst experience

The analyst should not feel like the AI replaced their job.

The analyst experience should become:

1. review prefilled suggestions
2. check flagged `REVIEW` areas
3. override where needed
4. continue with the same general manager-review and downstream upload flow

That is a much safer product story than asking analysts to trust an automated
negative list outright.

## Manual path remains first-class

This AI path must remain optional.

Users should still be able to:

1. generate the native workbook without AI
2. review manually as they do today

The AI path is an acceleration lane, not a replacement mandate.

## AI token usage logging

The existing Agency OS pattern should be reused here.

Current tools such as Scribe, Debrief, AdScope chat, and The Claw already log
AI token usage to the shared `ai_token_usage` table using a best-effort
logging path.

That pattern should be followed for `N-Gram 2.0` AI prefill rather than
inventing a new telemetry model.

### Logging model to follow

Use the shared token-usage shape:

1. `tool`
2. `user_id`
3. optional `stage`
4. `prompt_tokens`
5. `completion_tokens`
6. `total_tokens`
7. `model`
8. `meta`

Important behavior:

1. logging should be best-effort
2. logging failures must never block the user workflow
3. token telemetry should land in `ai_token_usage`, consistent with the rest
   of Agency OS

### Recommended tool / stage naming

Recommended `tool` value:

1. `ngram`

Recommended `stage` values for the AI-prefill path:

1. `ai_prefill_term_eval`
2. `ai_prefill_synthesis`

If synthesis is fully deterministic and does not call an LLM, only the first
stage needs token logging.

If the product later adds a separate AI review or AI workbook-explanation
step, that should log as its own stage rather than being mixed into the same
row.

### Recommended meta payload

The `meta` field should stay compact and operationally useful.

Suggested fields:

1. `profile_id`
2. `marketplace_code`
3. `date_from`
4. `date_to`
5. `ad_product`
6. `spend_threshold`
7. `campaign_count`
8. `search_term_count_considered`
9. `search_term_count_sent_to_ai`
10. `ambiguous_campaign_count`
11. `prefill_mode`
    - for example `workbook_prefill`

If helpful, later follow-ups could also log:

1. `negate_count`
2. `review_count`
3. `keep_count`

Those are not token metrics, but they can be useful operational metadata if
kept small.

### Why this matters

Using the shared token-logging model gives:

1. consistent internal attribution in Command Center token reporting
2. comparable cost visibility across tools
3. stage-level observability if prompts or thresholds are tuned later
4. lower implementation risk because the logging pattern already exists

### Practical implementation note

If the AI-prefill execution lives in a frontend route / server action, follow
the existing `logUsage(...)` pattern used by Scribe and Debrief.

If the execution lives deeper in the backend async/runtime path, follow the
best-effort `log_ai_token_usage(...)` pattern used by The Claw.

## Empirical model evaluation

On `2026-03-28`, the team ran a head-to-head evaluation on the core
`N-Gram 2.0` AI-prefill task using one real campaign and `285` search terms.

Test setup summary:

1. campaign:
   - `Screen Shine - Pro | SPM | MKW | Br.M | 2 - computer | Perf`
2. inputs:
   - campaign name
   - All Listings Report
   - `285` search terms
3. required output:
   - structured JSON
   - `KEEP / NEGATE / REVIEW`
   - confidence
   - controlled reason tag
4. important nuance:
   - models were **not** given product context directly
   - they had to infer product context from the listing data and campaign name

Models evaluated:

1. Claude Sonnet 4.6
2. Claude Haiku 4.5
3. ChatGPT fast
4. ChatGPT thinking
5. Gemini fast
6. Gemini thinking

### Main result

`Claude Sonnet 4.6` was the strongest model by a meaningful margin.

Observed strengths:

1. correctly inferred product context from listing data
2. correctly parsed campaign theme
3. strong competitor-brand detection
4. strong foreign-language negation
5. strong wrong-category / wrong-size detection
6. clean structured JSON
7. strong confidence calibration

### Observed model ranking

Best overall quality in the experiment:

1. `Claude Sonnet 4.6`
2. `ChatGPT thinking`
3. `Claude Haiku 4.5` and `Gemini fast` as cheaper but weaker bulk evaluators

Explicit non-recommendation from the experiment:

1. `Gemini thinking` is not suitable for first production use because it
   silently degrades when output length is exceeded
2. fast / lightweight models without prompt reinforcement are weak on the two
   most important negative categories:
   - competitor brands
   - foreign-language terms

### Consistent blind spots outside Sonnet

Across non-Sonnet models, two failure patterns repeated:

1. competitor-brand detection
   - examples: `Invisible Glass`, `Monoprice`, `AudioQuest`, `Staples`,
     `Screen Doctor`, `E-Cloth`
2. foreign-language negation
   - especially Spanish search terms

This means general instruction alone is not enough. If a cheaper or faster
model is used, the prompt should include concrete few-shot examples for these
cases.

### Recommended production architecture from the experiment

The experiment's recommended operating model was:

1. `Haiku-first` bulk pass
2. escalate `REVIEW` or `LOW` confidence terms to `Sonnet`
3. add explicit few-shot examples for:
   - competitor brands
   - foreign-language terms

Why this architecture is attractive:

1. lower cost than `Sonnet-only`
2. materially better quality than `Haiku-only`
3. preserves a high-quality escalation path for the tricky terms

Alternative if the stack remains OpenAI-only for now:

1. use a stronger reasoning-tier OpenAI model as the initial production
   fallback
2. do **not** rely on a nano-class general default for this workflow
3. still add few-shot reinforcement for competitor-brand and foreign-language
   cases

### Product implication

`N-Gram 2.0` AI prefill is unusually sensitive to model quality.

This is **not** a good place to reuse a generic global “cheap default” model
lane without explicit validation.

The current implementation path inherits the shared frontend OpenAI adapter
default behavior. In practice that means:

1. if no explicit model is set for `N-Gram 2.0`, it uses whatever
   `OPENAI_MODEL_PRIMARY` is set to for the environment
2. if that env var is absent, the frontend adapter falls back to
   `gpt-5.1-nano`

That is an implementation convenience, not a product recommendation.

### Design recommendation

For `N-Gram 2.0`, model selection should become tool-specific rather than
implicitly inherited from the global default.

Recommended direction:

1. add an explicit `N-Gram` model lane or route-level override
2. keep the chosen model configurable per environment
3. treat Sonnet-quality behavior as the quality bar
4. do not assume that the same model used for cheaper chat / routing / prose
   tasks is suitable for PPC negation judgment

### Immediate practical takeaway

If the active environment is currently using a nano-class or otherwise
lightweight default model for this workflow, that is likely the wrong primary
model choice for launch.

At minimum before broader rollout:

1. pin `N-Gram 2.0` to a stronger model than the generic default
2. add few-shot examples for competitor-brand and foreign-language terms
3. validate on more campaign types:
   - `MKW`
   - `SKW`
   - `PT`
4. validate on more products where the same query should flip by campaign
   context

## What this design is not

This design does **not** include:

1. direct Amazon writeback
2. Pacvue writeback automation
3. removing the manager review step
4. mandatory validation of raw rows on every run
5. `SB` or `SD` AI support in the first slice

## Override tracking and tuning

When the reviewed workbook comes back through the downstream flow, the system
should eventually compare:

1. AI-prefilled output
2. final analyst-reviewed output

That diff can be logged silently for later tuning.

Use cases:

1. identify recurring false positives
2. identify reason tags the team keeps overriding
3. improve mapping heuristics
4. improve synthesis thresholds
5. improve prompt wording

This should be passive and low-friction.

## Implementation recommendation

If the team wants to “jump to v2,” the safest interpretation is:

1. ship an AI-prefilled workbook path
2. but keep the internal pipeline split into:
   - search-term evaluation
   - conservative gram synthesis

That gives the team the workbook-prefill experience they want, without making
unsafe direct gram leaps from single search terms.

## Suggested phased build order

Even if the product surface jumps straight to workbook prefill, the internal
implementation should still be built in layers:

1. campaign/product/theme mapping layer
2. spend-threshold filtering
3. search-term AI judgment contract
4. deterministic gram synthesis layer
5. workbook-prefill writer
6. optional override logging after reviewed-workbook upload

## Open questions

1. What exact alias map or normalization strategy should be used for campaign
   family -> product mapping?
2. What minimum evidence threshold should grams need before prefill?
3. Should `REVIEW` terms be visible only in the workbook, or also in an
   intermediate UI?
4. How much term-level rationale should be written into the workbook versus
   kept internal?

## Short conclusion

The best version of `N-Gram 2.0` AI prefill is:

1. native `SP` data only
2. product-aware
3. campaign-theme-aware
4. threshold-gated
5. term-judgment-first
6. conservative in gram prefill
7. workbook-compatible
8. fully reviewable by analysts

That preserves the current team's workflow while still delivering real AI
time savings.
