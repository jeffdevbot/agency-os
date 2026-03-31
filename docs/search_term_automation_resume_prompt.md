# Search Term Automation Resume Prompt

_Last updated: 2026-03-30 (ET)_

Use this prompt when returning specifically to the `STR / N-Gram 2.0`
workstream.

Continue work in `/Users/jeff/code/agency-os`.

Read first, in this order:

1. `docs/current_handoffs.md`
2. `docs/search_term_automation_plan.md`
3. `docs/ngram_native_replacement_plan.md`
4. `docs/ngram_2_ai_prefill_design.md`
5. `docs/wbr_v2_schema_plan.md`
6. `PROJECT_STATUS.md`
7. `AGENTS.md`

## Current shipped reality

1. `SP` native STR ingestion is live and validated against real Amazon
   `Search term` exports.
2. `SB` ingestion works on validated modern accounts, but is still not assumed
   complete for older legacy Sponsored Brands campaign families.
3. `SD` remains out of scope for the current native N-Gram replacement path.
4. `/ngram-2` exists as a separate route and does **not** modify the legacy
   `/ngram` surface.
5. `N-Gram 2.0` has already completed the first real native replacement loop
   for `SP`:
   - generate native workbook from `/ngram-2`
   - upload that workbook into Step 2 of legacy `/ngram`
   - legacy Step 2 accepts it and returns the expected workbook output
6. `/ngram-2` AI workflow is now materially beyond preview-only status:
   - Step 3 bounded preview works
   - Step 4 full AI-prefilled workbook generation works
   - campaign evaluation now uses OpenAI Structured Outputs with strict JSON
     schema enforcement
   - the model lane is tool-specific through `OPENAI_MODEL_NGRAM`
   - saved runs persist in `ngram_ai_preview_runs`
   - saved runs persist explicit `prompt_version`
   - workbook summary metadata writes:
     - `AI Preview Run`
     - `AI Model`
     - `AI Prompt Version`
     - `AI Threshold`
   - AI-prefilled workbook output now mirrors human workflow more closely:
     - 1/2/3-word `NEGATE` terms land in scratchpad
       `Monogram` / `Bigram` / `Trigram`
     - longer `NEGATE` terms prefill exact `NE` on the search-term row
   - reviewed workbook uploads through legacy `/ngram/collect` now persist
     best-effort AI-vs-analyst diffs in `ngram_ai_override_runs`

## Prompt / model state

1. The current prompt version is:
   - `ngram_step3_calibrated_v2026_03_30`
2. The current intended OpenAI model lane is:
   - `OPENAI_MODEL_NGRAM`
   - currently tested successfully on `gpt-5.4-2026-03-05`
3. The current prompt calibration intentionally does all of the following:
   - tightens `REVIEW` vs `NEGATE`
   - explicitly handles cloth-only / accessory-only intent
   - treats CA French as marketplace-aware relevance rather than generic
     foreign-language noise
4. `reason_tag` is now a strict 10-value enum:
   - `core_use_case`
   - `wrong_category`
   - `wrong_product_form`
   - `wrong_size_variant`
   - `wrong_audience_theme`
   - `competitor_brand`
   - `cloth_primary_intent`
   - `accessory_only_intent`
   - `foreign_language`
   - `ambiguous_intent`

## Important validation findings

### Sponsored Products

1. Whoosh US `SP` was validated end to end against a real Amazon export.
2. Validation should compare against Amazon `Search term` exports, not broad
   Campaign Manager totals.
3. Search-term impression totals can differ from broader console totals
   because Amazon search-term exports appear limited to terms with at least one
   click.

### Sponsored Brands

1. Native `SB` is not generically broken.
2. Ahimsa US provides the clean live counterexample where Amazon export and DB
   matched exactly.
3. The repeated Whoosh US mismatch is still best explained as a likely legacy
   Sponsored Brands campaign-family gap, not a broad parser/storage bug.
4. Practical rule:
   - do not block `SP` product progress on full legacy `SB` parity

## Current live checkpoint

1. The first override-capture layer is live:
   - reviewed workbook uploads now persist AI-vs-analyst diffs in
     `ngram_ai_override_runs`
2. A limited Whoosh CA full AI workbook run for `2026-03-27` through
   `2026-03-29` completed successfully:
   - run id: `a63530e2-9d1a-42c1-a0d4-563bf931e6b1`
   - `43` runnable campaigns
   - `145` evaluated terms
   - `477,233` total tokens
   - approx cost: `$1.42` on `gpt-5.4`
3. The current pipeline is now good enough to stop iterating on plumbing and
   move into analyst-verified quality comparison.

## Exact next-session goal

The next session should start from this concrete milestone:

1. take a full 7-day Whoosh US worksheet that an analyst already reviewed
2. run the equivalent `/ngram-2` full AI-prefilled workbook for the same
   window/profile/settings
3. compare:
   - campaign coverage
   - exact negatives
   - mono/bi/tri scratchpad grams
   - analyst overrides vs AI recommendations
4. decide whether the current prompt/model/workbook behavior is good enough or
   whether a targeted correction is needed

This is now a quality-comparison problem, not a schema/plumbing problem.

## Rules for the next session

1. Do not reopen OpenAI API integration debates unless a fresh run shows a new
   real failure.
2. Do not treat missing `SB` legacy parity as the blocking issue.
3. Prefer inspecting persisted `ngram_ai_preview_runs` and
   `ngram_ai_override_runs` rows over inferring behavior from screenshots.
4. Keep the legacy `/ngram` workbook format as the contract unless explicitly
   asked to redesign the review flow.
5. If model changes are considered, compare against real override data rather
   than intuition.

## Restart prompt for the next session

Use this as the first message if the next session returns to this workstream:

```text
Continue the Agency OS STR / N-Gram 2.0 workstream.

Read first:
1. docs/current_handoffs.md
2. docs/search_term_automation_resume_prompt.md
3. docs/search_term_automation_plan.md
4. docs/ngram_native_replacement_plan.md
5. docs/ngram_2_ai_prefill_design.md
6. docs/wbr_v2_schema_plan.md
7. PROJECT_STATUS.md
8. AGENTS.md

Current reality:
- SP native STR ingestion is validated and trusted
- SB works on validated modern accounts but still has a likely legacy-campaign
  gap on at least one older Whoosh US campaign family
- /ngram-2 Step 3 preview works
- /ngram-2 Step 4 full AI-prefilled workbook generation works
- OpenAI Structured Outputs are now live for campaign evaluation
- saved runs persist in `ngram_ai_preview_runs`
- reviewed uploads now persist override diffs in `ngram_ai_override_runs`
- the current prompt version is `ngram_step3_calibrated_v2026_03_30`
- the current model lane is `OPENAI_MODEL_NGRAM`
- the next exact milestone is a full 7-day Whoosh US analyst-reviewed
  worksheet comparison against the `/ngram-2` full AI workbook output

Start by checking Supabase MCP auth in the fresh session, then inspect the
latest Whoosh US manual-vs-AI comparison inputs/outputs and identify the
highest-signal diffs by campaign, search term, and gram.
```
