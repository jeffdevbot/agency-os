# N-Gram 2.0 SB Enablement Execution Checklist

_Created: 2026-04-02 (ET)_

Companion doc to
[ngram_2_sb_enablement_plan.md](/Users/jeff/code/agency-os/docs/ngram_2_sb_enablement_plan.md).

Use this as the execution checklist and progress-report template for the AI
coder implementing Sponsored Brands support in `/ngram-2`.

## Working rules

1. Keep the workbook contract unchanged.
2. Do not block on legacy SB parity gaps.
3. Do not add Sponsored Display support.
4. Do not spend time on unrelated `/ngram-2` UI cleanup.
5. Prefer small, reviewable commits grouped by implementation phase.

## Definition of done

The work is done when all boxes below are complete:

- [ ] `/ngram-2` can load an SB native summary
- [ ] `/ngram-2` can run SB Step 3 preview
- [ ] `/ngram-2` can run SB Step 4 workbook generation
- [ ] backend native summary/workbook endpoints accept `SPONSORED_BRANDS`
- [ ] SB preview/full runs persist in `ngram_ai_preview_runs`
- [ ] reviewed SB workbook uploads can still flow through Step 5
- [ ] workbook contract is unchanged
- [ ] SB remains caution/beta in messaging
- [ ] SD remains blocked

## Reporting format

Every status update back to the user should use this structure:

### Progress

1. `Completed:` list the checklist items completed in this work block
2. `In progress:` name the single active item
3. `Blocked:` list blockers, or say `none`
4. `Verified:` list tests, local checks, or Supabase checks actually run
5. `Open risks:` list only current real risks, not generic caveats

Example:

```text
Progress
1. Completed: backend allowlist for SB in native summary/workbook
2. In progress: frontend /ngram-2 gating changes
3. Blocked: none
4. Verified: pytest backend-core/tests/test_ngram_native.py
5. Open risks: SB targeting is null live; preview route still needs coverage
```

## Execution checklist

## Phase 0: Reconfirm context

- [ ] Read [ngram_2_sb_enablement_plan.md](/Users/jeff/code/agency-os/docs/ngram_2_sb_enablement_plan.md)
- [ ] Confirm no schema migration is required
- [ ] Confirm live SB rows exist in `search_term_daily_facts`
- [ ] Confirm current SP-only gates still exist in code before editing

Report when done:

1. which files contain the active SP-only gates
2. whether live SB data is still present
3. whether any unexpected drift was found

## Phase 1: Backend native service allowlist

Primary file:
[native.py](/Users/jeff/code/agency-os/backend-core/app/services/ngram/native.py)

Tasks:

- [ ] Replace SP-only validation in `build_workbook_from_search_term_facts`
- [ ] Replace SP-only validation in `build_summary_from_search_term_facts`
- [ ] Allow:
  - `SPONSORED_PRODUCTS`
  - `SPONSORED_BRANDS`
- [ ] Keep rejecting unsupported products like `SPONSORED_DISPLAY`
- [ ] Keep workbook output shape unchanged

Minimum report back:

1. exact validation rule before
2. exact validation rule after
3. whether any downstream code needed adjustment beyond the allowlist

## Phase 2: Frontend API route allowlist

Primary file:
[route.ts](/Users/jeff/code/agency-os/frontend-web/src/app/api/ngram-2/ai-prefill-preview/route.ts)

Tasks:

- [ ] Replace the single-product request guard with an allowlist
- [ ] Accept `SPONSORED_BRANDS`
- [ ] Keep rejecting `SPONSORED_DISPLAY`
- [ ] Preserve response payload shape
- [ ] Preserve persistence into `ngram_ai_preview_runs`
- [ ] Add or retain honest SB caution warning text in route warnings

Minimum report back:

1. exact request validation change
2. whether SB required any runtime logic changes beyond request coercion
3. whether nullable `targeting` caused any code changes

## Phase 3: Frontend `/ngram-2` gating

Primary file:
[page.tsx](/Users/jeff/code/agency-os/frontend-web/src/app/ngram-2/page.tsx)

Tasks:

- [ ] Remove SP-only gate from `inspectRowsHref`
- [ ] Remove SP-only gate from summary loading
- [ ] Remove SP-only gate from workbook-generation eligibility
- [ ] Remove SP-only gate from preview eligibility
- [ ] Keep SD blocked
- [ ] Keep SB caution-state messaging intact

Minimum report back:

1. which gating expressions changed
2. how SB is allowed now
3. how SD remains blocked

## Phase 4: Tests

Tasks:

- [ ] Add or update backend tests for SB acceptance in native summary/workbook
- [ ] Add or update route tests for SB acceptance in preview/full run path
- [ ] Add coverage for unsupported products still being rejected
- [ ] Add coverage for nullable SB `targeting` if practical

Minimum report back:

1. exact test files changed
2. exact commands run
3. whether any expected test coverage was skipped

## Phase 5: Local verification

Tasks:

- [ ] Run targeted backend tests
- [ ] Run targeted frontend tests
- [ ] Run frontend typecheck
- [ ] Run any necessary lint/build checks if the touched files require it

Minimum report back:

1. commands run
2. pass/fail result
3. anything not run and why

## Phase 6: Live validation

Preferred first validation profiles:

1. `Ahimsa US`
2. `Whoosh CA`

Tasks:

- [ ] Load SB native summary in `/ngram-2`
- [ ] Confirm Search Term Data deep link uses SB filters
- [ ] Run Step 3 SB preview on a bounded campaign subset
- [ ] Confirm SB preview row persisted in `ngram_ai_preview_runs`
- [ ] Run Step 4 SB workbook generation
- [ ] Confirm workbook downloads and preserves current triage columns
- [ ] If possible, run reviewed workbook upload and confirm override capture

Minimum report back:

1. exact profile and date range used
2. whether summary worked
3. whether preview worked
4. whether workbook generation worked
5. whether persistence checks passed

## Phase 7: Final wrap-up

Tasks:

- [ ] Summarize implementation outcome
- [ ] List any remaining known risks
- [ ] State whether follow-up docs were updated or intentionally deferred
- [ ] Provide commit hash if committed

Final handoff report should include:

1. what shipped
2. what was verified
3. what remains risky but acceptable
4. any recommended next task

## Suggested progress milestones

Use these milestone labels in updates so the user can scan progress quickly:

1. `Milestone 1`: backend allowlist complete
2. `Milestone 2`: frontend route allowlist complete
3. `Milestone 3`: `/ngram-2` UI gating complete
4. `Milestone 4`: tests green
5. `Milestone 5`: live SB validation complete

## Suggested final status summary format

```text
Status
1. Scope: Sponsored Brands enablement for /ngram-2 native summary, AI preview, and workbook generation
2. Outcome: shipped / partial / blocked
3. Verified: <tests and live checks>
4. Persistence: <whether ngram_ai_preview_runs and ngram_ai_override_runs behaved correctly>
5. Workbook contract: unchanged / changed
6. Remaining risks: <short list>
7. Next recommendation: <single next step>
```
