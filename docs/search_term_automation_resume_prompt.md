# Search Term Automation Resume Prompt

_Last updated: 2026-04-02 (ET)_

Use this prompt when returning specifically to the `STR / N-Gram 2.0`
workstream.

Continue work in `/Users/jeff/code/agency-os`.

Read first, in this order:

1. `docs/current_handoffs.md`
2. `docs/ngram_2_pure_prompt_pivot_plan.md`
3. `docs/ngram_2_ai_prefill_design.md`
4. `docs/search_term_automation_resume_prompt.md`
5. `docs/ngram_2_ui_cleanup_plan.md`
6. `docs/search_term_automation_plan.md`
7. `docs/ngram_native_replacement_plan.md`
8. `docs/wbr_v2_schema_plan.md`
9. `PROJECT_STATUS.md`
10. `AGENTS.md`

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
   - Step 4 workbook generation works on validated windows, but large-window
     reliability is still being hardened
   - Step 5 reviewed-workbook upload to negatives summary works
   - Step 6 is a greyed-out direct-Amazon placeholder
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
9. `/ngram-2` analyst UI cleanup is now effectively shipped:
   - Step 1 is simpler and contains the spend threshold
   - Step 3 is smaller and clearly optional
   - campaign selector supports multi-select
   - preview rows can expand beyond the default compact cap
   - Search Term Data now offers filtered CSV export
   - the synthetic activity terminal was removed
10. The current matching path now uses code-first retrieval before AI:
   - code ranks catalog candidates per campaign
   - the model receives a shortlist instead of the full catalog
   - the pure-model context pass gets one bounded expanded-shortlist retry
   - short-lived OpenAI `429` errors now retry with bounded backoff

## Prompt / model state

1. The current pure-model prompt version is:
   - `ngram_pure_model_two_step_v2026_04_01_family_match`
2. The current intended OpenAI model lane is:
   - `OPENAI_MODEL_NGRAM`
   - currently tested successfully on `gpt-5.4-2026-03-05`
3. The current live AI path is a two-step flow:
   - context pass locks the best product or product-family representative row
   - term-triage pass evaluates terms against that locked context
   - product-context matching now depends on a retrieval shortlist rather than
     the full catalog
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
2. The current pure-model triage path is shipped enough for real analyst
   testing.
3. The current UI cleanup pass is no longer the active blocker.
4. The earlier Whoosh US month-long Step 4 blocker was investigated:
   - the expensive AI pass completed and persisted
   - the visible failure was workbook generation after AI persistence
   - saved-run recovery and recent-run reuse are now shipped
5. The current focus is quality/cost validation on the latest prompt path plus
   SB controlled-validation enablement.

## Exact next-session goal

The next session should start from this concrete milestone:

1. validate the current SP full-run path on a real large run under the latest
   prompt versions
2. continue SB enablement / validation without changing the workbook contract
3. keep the current analyst-triage workbook contract intact
4. prefer persisted runs / logs / measured token impact over more prompt churn
5. do not reopen UI cleanup unless testing exposes a new specific usability
   issue

## Rules for the next session

1. Do not treat missing `SB` legacy parity as the blocking issue.
2. Do not spend the next session on Responses API migration or model-generated
   “thinking” summaries.
3. Prefer inspecting persisted `ngram_ai_preview_runs` and
   `ngram_ai_override_runs` rows over inferring behavior from screenshots.
4. Keep the legacy `/ngram` workbook format as the contract unless explicitly
   asked to redesign the review flow.
5. If model changes are considered, compare against real override data rather
   than intuition.
6. Treat saved-run recovery, recent-run reuse, and brand-portfolio handling as
   current shipped behavior, not experimental ideas.

## Restart prompt for the next session

Use this as the first message if the next session returns to this workstream:

```text
Continue the Agency OS STR / N-Gram 2.0 workstream.

Read first:
1. docs/current_handoffs.md
2. docs/ngram_2_pure_prompt_pivot_plan.md
3. docs/ngram_2_ai_prefill_design.md
4. docs/search_term_automation_resume_prompt.md
5. docs/ngram_2_ui_cleanup_plan.md
6. docs/search_term_automation_plan.md
7. docs/ngram_native_replacement_plan.md
8. docs/wbr_v2_schema_plan.md
9. PROJECT_STATUS.md
10. AGENTS.md

Current reality:
- SP native STR ingestion is validated and trusted
- SB works on validated modern accounts but still has a likely legacy-campaign
  gap on at least one older Whoosh US campaign family
- /ngram-2 Step 3 preview works
- /ngram-2 Step 4 workbook generation works on validated windows
- /ngram-2 Step 5 reviewed workbook upload works
- OpenAI Structured Outputs are now live for campaign evaluation
- saved runs persist in `ngram_ai_preview_runs`
- recent saved runs can now be reused/recovered instead of paying for AI again
- reviewed uploads now persist override diffs in `ngram_ai_override_runs`
- the current pure-model prompt version is
  `ngram_pure_model_two_step_v2026_04_02_sparse_keep_rationale`
- the current model lane is `OPENAI_MODEL_NGRAM`
- the workbook is now triage-oriented:
  - `SAFE KEEP`
  - `LIKELY NEGATE`
  - `REVIEW`
  - `AI Rationale`
  - blank `NE/NP`
  - blank mono/bi/tri scratchpad
- the `/ngram-2` UI cleanup pass is effectively shipped
- the current matching path uses code-first candidate retrieval before AI
- brand / mix / defensive campaigns now run as `brand_portfolio` scope instead
  of being skipped or treated as strict single-product lanes
- KEEP rationale is now sparse / usually null to reduce output-token spend
- SB is mechanically enabled in `/ngram-2` for native summary, AI preview, and
  workbook generation with caution messaging intact; SD remains blocked

Continue `/ngram-2` quality/cost hardening and SB validation without changing
the analyst-triage workbook contract. Use the existing docs for context,
prefer real persisted evidence over intuition, and do not migrate to
Responses API.
```
