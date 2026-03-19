# WBR Snapshot and The Claw Weekly Email Plan

_Drafted: 2026-03-18 (ET)_

## Implementation status (2026-03-19)

This plan is now **partially implemented**.

What is live:

1. `wbr_digest_v1` is the canonical prompt-friendly WBR summary contract.
2. `wbr_report_snapshots` exists and The Claw uses a get-or-create snapshot path for WBR summary retrieval.
3. The Claw skill `wbr_summary` is live and working in Slack.
4. The Claw skill `wbr_weekly_email_draft` is implemented and drafts one combined weekly email across all active marketplaces for a client.
5. `wbr_email_drafts` now exists for persisted draft history / traceability.

Important current-shape notes:

1. The shipped email draft path is **client-level across marketplaces**, not one draft per single profile.
2. Draft generation now fails fast if included marketplace snapshots do not share the same `week_ending`.
3. Email-draft client resolution only considers clients with active WBR profiles and requires unique partial matches.
4. Email drafts now render as normal Slack text rather than code blocks, making copy/paste into Gmail or Outlook more practical.
5. Follow-up instructions such as `make it shorter`, `don't mention inventory`, or `include this commentary` are now treated as draft-revision constraints in the skill contract.
6. Slack remains the MVP operator surface; there is still no browser draft editor or automated sending path.

## Goal

Use the live WBR data model as the source for weekly client-email drafting,
without screenshots, while keeping Slack as the operator surface.

This should support flows like:

1. `Show me Whoosh US WBR summary`
2. `Draft this week's client email for Whoosh US`

The output should be copy/paste-ready in Slack. Final editing can happen in the
user's normal email client. No separate browser review UI is required for the
first version.

## Claw philosophy constraints

This plan must follow the current AgencyClaw direction:

1. Do not build strict regex-first routing for WBR/email drafting.
2. Do not build a brittle command grammar like
   `draft_wbr_email(client=whoosh, market=us)`.
3. Use semantic skill selection, consistent with the current Claw skill model:
   - flat skill menu
   - model chooses skill by intent/context
   - category folders are organizational only
4. Keep the Claw feeling conversational and lifelike:
   - it should infer likely intent from natural phrasing
   - it should ask one focused clarification if client/market/week scope is
     ambiguous
   - it should not force a rigid command syntax
5. Slack is the delivery surface for the MVP.
6. The WBR and email output should be generated from structured stored data,
   not browser screenshots.

## Current reality

The WBR report is already machine-readable enough to support this direction, and the first end-to-end Slack path is now live.

Important clarification:

1. WBR is rebuilt on each report request.
2. It is not reparsed from Windsor/Amazon raw inputs on each page load.
3. The report services already read persisted fact tables, including:
   - `wbr_business_asin_daily`
   - `wbr_ads_campaign_daily`
   - `wbr_inventory_asin_snapshots`
   - `wbr_returns_asin_daily`
4. That means the missing layer was never "put WBR into tables."
5. The layers that were added in this tranche are:
   - stable AI-friendly digest generation
   - snapshot persistence for reproducibility
   - Claw skills that retrieve summary + email-draft output from those snapshots

## Product shape

### What the operator should experience

In Slack:

1. ask for a client WBR summary
2. receive a compact summary
3. ask for a weekly client email draft
4. receive a copy/paste-ready draft
5. optionally ask follow-ups like:
   - `make it more concise`
   - `focus more on ads`
   - `mention returns risk less strongly`

The Claw should be able to use the same underlying snapshot/digest for these
follow-ups.

Current implementation note:

1. Follow-up revisions currently rely on normal Claw conversation history plus explicit revision guidance in the `wbr_weekly_email_draft` skill contract.
2. There is not yet a separate deterministic "edit prior draft" backend mode.

### What not to do in MVP

1. Do not dump the full WBR workbook into Slack as giant ASCII output.
2. Do not build a browser draft editor first.
3. Do not automate sending emails yet.
4. Do not attempt a generic cross-report snapshot framework before WBR proves
   the pattern.

## Build order

## Phase 1: canonical WBR digest

Build one backend formatter that converts the current WBR report payload into a
stable, compact, prompt-friendly digest.

This is the real foundation.

Why first:

1. it keeps AI prompts stable
2. it avoids sending huge raw report payloads to Slack/LLMs
3. it gives one contract for:
   - snapshots
   - Slack summaries
   - email drafts
   - future audit/history

Recommended output shape:

1. profile metadata
   - client
   - marketplace
   - profile_id
   - report week labels
   - snapshot date
2. executive summary metrics
   - sales
   - spend
   - TACoS / ACoS where relevant
   - page views / unit sales
   - weeks of stock / return rate
3. key movers
   - top positive changes
   - top negative changes
4. flagged risks
   - unmapped campaigns
   - low stock / high return pressure
   - data-quality warnings
5. section summaries
   - Section 1 compact row summary
   - Section 2 compact row summary
   - Section 3 compact row summary

Important design rule:

1. the digest should be opinionated and compact
2. the digest should not try to preserve the full screen payload
3. the full raw report can still be fetched separately when needed

## Phase 2: WBR snapshots

Add a table that stores the exact digest used for downstream drafting.

Recommended table:

1. `wbr_report_snapshots`

Recommended columns:

1. `id uuid primary key default gen_random_uuid()`
2. `profile_id uuid not null references public.wbr_profiles(id) on delete restrict`
3. `snapshot_kind text not null`
   - initial value:
     - `weekly_email`
4. `week_count integer not null`
5. `week_ending date`
6. `window_start date not null`
7. `window_end date not null`
8. `source_run_at timestamptz not null default now()`
9. `digest_version text not null`
10. `digest jsonb not null`
11. `raw_report jsonb`
12. `created_by uuid references public.profiles(id)`
13. `created_at timestamptz not null default now()`

Recommended indexes:

1. `(profile_id, created_at desc)`
2. `(profile_id, week_ending desc)`
3. optional uniqueness guard on
   `(profile_id, snapshot_kind, week_ending, digest_version)` if duplicate
   generation becomes noisy

Why snapshots matter:

1. reproducibility
2. traceability
3. easier Slack follow-up prompts
4. easier future history / approval / resend flows

## Phase 3: weekly email draft generation

Generate client-facing draft email text from a stored WBR snapshot digest.

Original recommendation:

1. `wbr_email_drafts`

Recommended columns:

1. `id uuid primary key default gen_random_uuid()`
2. `snapshot_id uuid not null references public.wbr_report_snapshots(id) on delete cascade`
3. `profile_id uuid not null references public.wbr_profiles(id) on delete restrict`
4. `draft_kind text not null`
   - initial value:
     - `weekly_client_email`
5. `prompt_version text not null`
6. `tone_profile text`
7. `model text`
8. `draft_subject text`
9. `draft_body text not null`
10. `meta jsonb not null default '{}'::jsonb`
11. `created_by uuid references public.profiles(id)`
12. `created_at timestamptz not null default now()`

Current implementation note:

1. The shipped `wbr_email_drafts` table is client-level and stores:
   - `client_id`
   - `snapshot_group_key`
   - `marketplace_scope`
   - `snapshot_ids`
   - `subject`
   - `body`
   - `model`
2. This matches the multi-marketplace email shape more closely than the original single-snapshot recommendation.

This is still not for in-app editing first.

Purpose:

1. preserve what was generated
2. support regeneration/version comparison later
3. support future auditability

## Phase 4: The Claw skill integration

After digest + snapshots exist, add Claw-facing WBR skills.

Recommended MVP skills:

1. `wbr_summary`
2. `wbr_weekly_email_draft`

Possible future skill:

1. `wbr_snapshot_history`

Important philosophy point:

1. these should be skills selected semantically from natural conversation
2. not hardcoded command handlers
3. not regex-only dispatch

### Skill: `wbr_summary`

Purpose:

1. resolve target client/profile/market scope
2. fetch latest relevant WBR snapshot or build one if needed
3. return a concise Slack-friendly summary

Expected user prompts:

1. `Show me Whoosh US WBR`
2. `How did Distex CA look this week?`
3. `Give me a quick WBR summary for Whoosh`

Output shape in Slack:

1. resolved context
2. week ending / report window
3. compact KPI table or Slack-formatted summary block
4. key wins
5. key concerns
6. optional note if ambiguity/data gaps exist

### Skill: `wbr_weekly_email_draft`

Purpose:

1. resolve target client scope
2. gather the active WBR marketplaces for that client
3. fetch or create marketplace snapshots
4. use the stored digests plus the house prompt
5. produce one copy/paste-ready client email draft
6. store generated draft for traceability

Expected user prompts:

1. `Draft this week's client email for Whoosh US`
2. `Write the weekly update for Distex CA`
3. `Draft a client-facing WBR recap for Whoosh`

Output shape in Slack:

1. one-line context header
2. `Subject:` line
3. email body in a copyable fenced block
4. note such as
   `Drafted from WBR snapshots ending 2026-03-15 · Marketplaces: US,CA,UK`

## Entity resolution and ambiguity handling

This should reuse the Claw's semantic skill model rather than creating a new
WBR-specific parser.

Recommended flow:

1. user asks naturally
2. Claw routes to `entity_resolver` first when client/market scope is unclear
3. if resolved, Claw routes to `wbr_summary` or `wbr_weekly_email_draft`
4. if not resolved, ask exactly one focused clarification

Examples:

1. `Draft the weekly email for Whoosh`
   - if multiple Whoosh scopes exist, ask which one
2. `Show me the CA one`
   - resolve against current session context if possible
3. `Draft this week's client note`
   - if active context exists, use it
   - otherwise ask which client/market

## API / service shape

Keep the first implementation backend-first and simple.

Recommended service additions:

1. `backend-core/app/services/wbr/report_digest.py`
   - builds canonical digest from section report payloads
2. `backend-core/app/services/wbr/report_snapshots.py`
   - create/list/load snapshots
3. `backend-core/app/services/wbr/email_drafts.py`
   - generate/store weekly email drafts

Recommended initial endpoints:

1. `POST /admin/wbr/profiles/{profile_id}/snapshots`
   - build and persist a snapshot
2. `GET /admin/wbr/profiles/{profile_id}/snapshots`
   - list snapshots
3. `POST /admin/wbr/profiles/{profile_id}/weekly-email-draft`
   - generate/store a draft from latest or new snapshot

These endpoints are for internal product use and debugging. The Claw can call
the same service layer rather than depending on browser pages.

## Suggested digest contract

Recommended top-level JSON:

```json
{
  "digest_version": "wbr_digest_v1",
  "profile": {
    "profile_id": "uuid",
    "client_name": "Whoosh",
    "marketplace_code": "US",
    "display_name": "Whoosh US"
  },
  "window": {
    "week_count": 4,
    "window_start": "2026-02-16",
    "window_end": "2026-03-15",
    "week_labels": ["16-Feb to 22-Feb", "23-Feb to 01-Mar", "02-Mar to 08-Mar", "09-Mar to 15-Mar"],
    "week_ending": "2026-03-15"
  },
  "headline_metrics": {
    "section1": {},
    "section2": {},
    "section3": {}
  },
  "wins": [],
  "concerns": [],
  "data_quality_notes": [],
  "section_summaries": {
    "section1": [],
    "section2": [],
    "section3": []
  }
}
```

Design rule:

1. store enough detail for grounded drafting
2. avoid overloading the digest with every row/field in the raw report

## Slack output design

### Summary response

Good:

1. compact KPI block
2. short wins / risks bullets
3. maybe one tiny code block if ASCII formatting helps readability

Bad:

1. dumping the entire WBR row tree into Slack
2. turning Slack into a spreadsheet viewer

### Email draft response

Recommended Slack format:

1. `Drafted from WBR snapshot ending <date>`
2. `Subject: ...`
3. fenced code block with email body

This keeps copy/paste easy.

## Non-goals for MVP

1. full autonomous email sending
2. browser draft editor
3. generic "AI for every report type" framework
4. broad new orchestration layer only for WBR
5. huge ASCII rendering of the full WBR in Slack

## Risks

1. Digest quality risk:
   - if the digest is too thin, drafts will feel generic
   - if too thick, prompts become noisy and expensive
2. Entity resolution risk:
   - client/market ambiguity can create wrong drafts if resolution is weak
3. Tone risk:
   - client-facing email wording must match internal expectations and avoid
     overclaiming
4. Snapshot freshness risk:
   - if a snapshot is stale, the user may unknowingly draft from old data

## Mitigations

1. Start with one digest version and test on a small client set.
2. Always include snapshot week ending in Slack output.
3. Reuse session/entity context instead of new WBR-specific heuristics.
4. Keep draft generation auditable by storing prompt/draft metadata.

## Recommended first implementation slice

The first slice should be:

1. implement `wbr_digest_v1`
2. add `wbr_report_snapshots`
3. add one internal endpoint to create/load latest snapshot
4. add one WBR Claw skill:
   - `wbr_summary`

Why this slice first:

1. it proves the data plane
2. it proves the Slack presentation shape
3. it avoids mixing prompt-writing and snapshot/debugging problems together
4. once the summary skill is good, weekly email drafting becomes much easier

## Second slice

1. add `wbr_weekly_email_draft`
2. add `wbr_email_drafts`
3. wire the house prompt for client-facing weekly email generation
4. return copy/paste-ready draft in Slack

## Acceptance criteria for MVP

1. A user can ask naturally for a WBR summary in Slack without using a rigid
   command grammar.
2. The Claw can resolve or clarify client/market scope with one focused
   question when needed.
3. A WBR snapshot is created from current persisted report data and stored in
   Supabase.
4. The Claw can generate a client-facing weekly email draft from that snapshot.
5. The Slack output is concise and copy/paste-friendly.
6. No screenshot-based workflow is required for the supported clients.
