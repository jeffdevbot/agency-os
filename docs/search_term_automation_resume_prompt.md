# Search Term Automation Resume Prompt

_Last updated: 2026-04-01 (ET)_

Use this prompt when returning specifically to the `STR / N-Gram 2.0`
workstream.

Continue work in `/Users/jeff/code/agency-os`.

Read first, in this order:

1. `docs/current_handoffs.md`
2. `docs/ngram_2_ui_cleanup_plan.md`
3. `docs/ngram_2_pure_prompt_pivot_plan.md`
4. `docs/search_term_automation_plan.md`
5. `docs/ngram_native_replacement_plan.md`
6. `docs/ngram_2_ai_prefill_design.md`
7. `docs/wbr_v2_schema_plan.md`
8. `PROJECT_STATUS.md`
9. `AGENTS.md`

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
6. `/ngram-2` AI workflow is now materially beyond preview-only plumbing work:
   - Step 3 bounded preview works
   - Step 4 workbook generation works
   - campaign evaluation uses OpenAI Structured Outputs with strict JSON
     schema enforcement
   - the model lane is tool-specific through `OPENAI_MODEL_NGRAM`
   - saved runs persist in `ngram_ai_preview_runs`
   - saved runs persist explicit `prompt_version`
   - reviewed workbook uploads through legacy `/ngram/collect` persist
     best-effort AI-vs-analyst diffs in `ngram_ai_override_runs`
7. The preferred AI product direction is now **triage for analyst leverage**:
   - AI is good at product-context inference and search-term triage
   - AI is weaker at analyst-style `NE` / `NP` and mono/bi/tri abstraction
   - the workbook should help the analyst review faster, not decide the final
     negation expression automatically
8. The current workbook behavior reflects that direction:
   - `AI Recommendation` now displays:
     - `SAFE KEEP`
     - `LIKELY NEGATE`
     - `REVIEW`
   - `AI Confidence`, `AI Reason`, and `AI Rationale` are populated
   - `NE/NP` stays blank
   - mono/bi/tri scratchpad stays blank

## Prompt / model state

1. The current pure-model prompt version is:
   - `ngram_pure_model_two_step_v2026_04_01_family_match`
2. The current intended OpenAI model lane is:
   - `OPENAI_MODEL_NGRAM`
   - currently tested successfully on `gpt-5.4-2026-03-05`
3. The current live AI path is a two-step flow:
   - context pass locks the best product or product-family representative row
   - term-triage pass evaluates terms against that locked context
4. The current prompt calibration intentionally does all of the following:
   - tightens `REVIEW` vs `NEGATE`
   - adds a KEEP-side forcing rule
   - handles Apple-in-tech-context disambiguation
   - supports family-level product matching at `MEDIUM` confidence when the
     product family is clear but the exact variant is not
   - treats CA French as marketplace-aware relevance rather than generic
     foreign-language noise
5. `reason_tag` is now a strict enum:
   - `core_use_case`
   - `wrong_category`
   - `wrong_product_form`
   - `wrong_size_variant`
   - `wrong_audience_theme`
   - `competitor_brand`
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

### Pure-model cross-brand triage

1. Whoosh US single-campaign testing showed strong product matching and useful
   first-pass triage, but too much forced exact/phrase output when the model
   was asked to own final negation expression.
2. Ahimsa campaign testing was a strong positive signal:
   - the system identified the product cleanly from campaign naming
   - it flagged obvious wrong-fit sibling-product traffic such as bowls and
     spoons effectively
3. Distex `New Air - NGR | SPA | Los. | Rsrch` initially failed because the
   campaign identifier implied a product family rather than one exact SKU.
4. After the family-match prompt change, Distex improved materially:
   - the model could treat `NGR` as a product-family cue
   - family-level ambiguity now yields `MEDIUM` confidence instead of
     collapsing to `LOW` / null / all-`REVIEW`

## Current live checkpoint

1. The first override-capture layer is live:
   - reviewed workbook uploads persist AI-vs-analyst diffs in
     `ngram_ai_override_runs`
2. The current pure-model triage path is shipped enough to move out of prompt
   debugging and into analyst-usage cleanup.
3. The current page still contains too much migration/debug copy and too much
   vertical sprawl for day-to-day analyst use.

## Exact next-session goal

The next session should start from this concrete milestone:

1. simplify the `/ngram-2` page for analyst use
2. remove obsolete migration/debug language and the old shipped-preview button
3. move spend threshold into Step 1 and simplify the page structure
4. make Step 3 clearly optional and much smaller on screen
5. keep the current AI triage logic intact while improving usability
6. plan an inline terminal-style progress surface using app-generated status
   lines only, with **no Responses API migration and no extra model-output
   tokens** in the first version

## Rules for the next session

1. Do not reopen OpenAI API integration debates unless a fresh run shows a new
   real failure.
2. Do not treat missing `SB` legacy parity as the blocking issue.
3. Do not spend the next session on Responses API migration or model-generated
   “thinking” summaries.
4. Prefer inspecting persisted `ngram_ai_preview_runs` and
   `ngram_ai_override_runs` rows over inferring behavior from screenshots.
5. Keep the legacy `/ngram` workbook format as the contract unless explicitly
   asked to redesign the review flow.
6. If model changes are considered, compare against real override data rather
   than intuition.

## Restart prompt for the next session

Use this as the first message if the next session returns to this workstream:

```text
Continue the Agency OS STR / N-Gram 2.0 workstream.

Read first:
1. docs/current_handoffs.md
2. docs/ngram_2_ui_cleanup_plan.md
3. docs/ngram_2_pure_prompt_pivot_plan.md
4. docs/search_term_automation_resume_prompt.md
5. docs/search_term_automation_plan.md
6. docs/ngram_native_replacement_plan.md
7. docs/ngram_2_ai_prefill_design.md
8. docs/wbr_v2_schema_plan.md
9. PROJECT_STATUS.md
10. AGENTS.md

Current reality:
- SP native STR ingestion is validated and trusted
- SB works on validated modern accounts but still has a likely legacy-campaign
  gap on at least one older Whoosh US campaign family
- /ngram-2 Step 3 preview works
- /ngram-2 Step 4 workbook generation works
- OpenAI Structured Outputs are now live for campaign evaluation
- saved runs persist in `ngram_ai_preview_runs`
- reviewed uploads now persist override diffs in `ngram_ai_override_runs`
- the current pure-model prompt version is
  `ngram_pure_model_two_step_v2026_04_01_family_match`
- the current model lane is `OPENAI_MODEL_NGRAM`
- the workbook is now triage-oriented:
  - `SAFE KEEP`
  - `LIKELY NEGATE`
  - `REVIEW`
  - `AI Rationale`
  - blank `NE/NP`
  - blank mono/bi/tri scratchpad
- the next exact milestone is UI simplification and analyst usability on
  `/ngram-2`, not more prompt plumbing

Implement the UI cleanup described in `docs/ngram_2_ui_cleanup_plan.md`.
Keep the current AI triage logic intact. Do not migrate to Responses API.
If you add an inline activity panel, make it app-generated only so it adds no
meaningful token cost.
```
