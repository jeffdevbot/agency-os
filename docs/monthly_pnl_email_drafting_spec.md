# Monthly P&L Email Drafting Spec

_Last updated: 2026-03-23 (ET)_

## Purpose

Define the first clean Claude-facing spec for Monthly P&L client email drafting
based on real Agency OS reporting data and the current manual email examples.

This document replaces the old screenshot/OCR mental model with a structured
data model:

1. Agency OS Monthly P&L data is the source of truth.
2. Claude should draft from canonical report data, not screenshots.
3. YoY should be used when comparable prior-year data exists.
4. If YoY is not available, the draft should degrade cleanly to MoM or explicit
   "comparison unavailable" language.

## Current status

1. This is a design/spec document, not a shipped tool contract.
2. The current live Monthly P&L MCP slice is still read-only:
   - `resolve_client`
   - `list_monthly_pnl_profiles`
   - `get_monthly_pnl_report`
   - `get_monthly_pnl_email_brief`
3. The structured brief layer is now implemented as a read-only backend/MCP
   slice.
4. A persisted Monthly P&L email draft tool is now implemented on top of the
   brief layer.
5. The next email-drafting slice should continue building on those foundations,
   but it should not reuse the legacy screenshot prompt shape.

## Extracted writing pattern

The supplied manual examples were consistent enough to define a stable pattern.

### Primary artifact

The standard deliverable is one client-facing monthly highlights email for one
client and one reporting month, optionally covering multiple marketplaces in the
same email.

The normal shape is:

1. subject line
2. greeting
3. short opening sentence referencing attached P&L statements/highlights
4. top-level executive summary across the included marketplaces
5. one section per marketplace
6. short closing CTA
7. sign-off

### Typical structure per marketplace

Each marketplace section should contain:

1. a short executive paragraph
2. a metrics snapshot table
3. top positive drivers
4. top risks / negative drivers
5. a one-sentence financial health verdict
6. prioritized recommendations

### Default table shape

The examples consistently use this snapshot table:

1. `Total Gross Revenue`
2. `Total Refunds`
3. `Total Net Revenue`
4. `Advertising`
5. `Advertising % of Net Revenue`
6. `Net Earnings`
7. `Net Earnings % of Net Revenue`

For each row, the comparison columns depend on data availability:

1. preferred: `Latest Month Value | Latest Month YoY | YTD Value | YTD YoY`
2. fallback: `Latest Month Value | MoM Change | YTD Value`

Do not force YoY labels when the prior-year comparable month is missing.

### Comparison rules

Comparison logic should be explicit and deterministic.

1. Prefer YoY when the latest month and the YTD window both have valid prior-year
   comparables.
2. If latest-month YoY is unavailable but the current-period sequence is still
   useful, fall back to MoM language for the latest month.
3. If YTD YoY is unavailable, omit YTD YoY rather than inferring it.
4. If comparison data is missing, say that clearly in internal validation notes;
   avoid cluttering the client-facing email body unless it materially changes
   interpretation.

### Executive-summary pattern

The top-level summary is usually 1-3 sentences and does three things:

1. states whether the portfolio is healthy, pressured, or mixed
2. identifies the main growth or profitability theme
3. names the largest current constraint or watchout

For single-marketplace emails, the top-level summary may be effectively the same
as the country-level summary.

### Marketplace summary pattern

The first paragraph for each marketplace usually explains:

1. the current phase of the account
   - examples: growth phase, investment phase, off-season resilience,
     margin-protection month
2. the most important top-line movement
3. the most important profitability or cost movement
4. whether the outcome is intentional, temporary, or a risk

### Positive-driver pattern

Positive drivers usually come from one of these themes:

1. strong revenue growth or product-sales growth
2. improved refund rate or stable refund control
3. improved ad efficiency
4. stable or improving gross margin / fee rate
5. strong net earnings margin or improving YTD profitability

Each driver should be one short evidence-backed line, not generic praise.

### Risk pattern

Negative drivers usually come from one of these themes:

1. advertising cost growth outpacing revenue growth
2. refund growth outpacing revenue growth
3. storage / removal / inbound fee spikes
4. margin compression despite growth
5. seasonal sales decline
6. one-time cleanup costs that should be monitored

Each risk should also be evidence-backed and should distinguish temporary issues
from structural concerns when the data supports that distinction.

### Verdict pattern

The financial health verdict is short and categorical. Common shapes:

1. `Excellent` / `Strong`
2. `Good`
3. `Warning`
4. `Mixed`

The verdict should reflect both margin quality and the intentionality of spend.
High-growth investment is not automatically bad if margins remain acceptable.

### Recommendation pattern

Recommendations are operational, not generic. They normally:

1. point to a specific driver or risk in the numbers
2. describe the action to review or take
3. imply the expected financial direction

Typical recommendation areas:

1. advertising bid/budget refinement
2. refund investigation or recovery workflow
3. inventory age and storage-fee mitigation
4. removal-fee validation
5. inbound/logistics review
6. selective reinvestment when margins have headroom

Default count: 3 recommendations.

### Tone rules

1. client-facing
2. concise
3. analytical but not technical
4. confident without overstating certainty
5. no invented operational claims
6. no "we already fixed this" language unless the user explicitly provided that
   context

## Recommended product shape

The cleanest path is a two-layer model.

### Layer 1: structured email brief

First build a canonical structured brief from Monthly P&L data. This should be
read-only and deterministic.

That brief should answer:

1. what is the latest reporting month
2. which marketplaces are included
3. whether each marketplace has YoY available
4. what the key latest-month, YTD, and comparison metrics are
5. what the leading positive and negative drivers are
6. what data-quality issues exist

### Layer 2: client email draft

Then generate the client-facing email draft from that structured brief.

This mirrors the successful WBR architecture more closely than asking Claude to
derive every metric and narrative decision directly from raw line items.

## Proposed Claude-facing contract

The long-term user-facing tool should be a monthly email drafting tool, but it
should be implemented on top of the structured brief described above.

### Recommended rollout

1. Phase A: read-only preview tool
   - `draft_monthly_pnl_email_preview`
2. Phase B: persisted draft tool
   - `draft_monthly_pnl_email`

This keeps the first release lower-risk and respects the current direction of
proving the P&L read path before adding write workflows.

### Proposed preview tool

`draft_monthly_pnl_email_preview`

Purpose:

Generate a copy/paste-ready Monthly P&L highlights email from canonical Agency
OS data without persisting anything.

Suggested input:

```json
{
  "client_id": "uuid",
  "report_month": "2026-02-01",
  "marketplace_codes": ["US", "CA", "UK"],
  "comparison_mode": "auto",
  "recipient_name": "Billy",
  "sender_name": "Anshuman",
  "sender_role": "Client Success Lead",
  "agency_name": "Ecomlabs"
}
```

Input rules:

1. `client_id` required
2. `report_month` required
3. `marketplace_codes` optional
   - default: all marketplaces with active Monthly P&L coverage for the client
     in the selected month
4. `comparison_mode` default: `auto`
   - `auto`: prefer YoY, fall back to MoM when YoY is unavailable
   - `yoy_only`: use YoY where possible and omit unsupported comparisons
   - `mom_only`: force MoM framing
5. `recipient_name`, `sender_name`, `sender_role`, `agency_name` optional but
   strongly recommended for a polished output

Suggested output:

```json
{
  "client": {
    "client_id": "uuid",
    "client_name": "Whoosh"
  },
  "report_month": "2026-02-01",
  "comparison_mode_requested": "auto",
  "comparison_mode_used": "yoy_preferred",
  "subject_options": [
    "Whoosh — Amazon P&L highlights | Feb 2026 results",
    "Whoosh — Monthly Amazon P&L highlights | Feb 2026"
  ],
  "preview_text": "Attached are the February 2026 Amazon P&L highlights across the active marketplaces.",
  "email_body": "full email body here",
  "sections": [
    {
      "marketplace_code": "US",
      "currency_code": "USD",
      "comparison_mode_used": "yoy",
      "latest_month_has_yoy": true,
      "ytd_has_yoy": true
    }
  ],
  "data_quality_notes": [],
  "report_refs": [
    {
      "profile_id": "uuid",
      "marketplace_code": "US",
      "months_used": ["2026-01-01", "2026-02-01"]
    }
  ]
}
```

### Proposed persisted tool

`draft_monthly_pnl_email`

Same input shape as preview, but mutating.

Additional output:

1. `draft_id`
2. `draft_kind`
3. `created_at`
4. prompt/model metadata as needed

## Prompt contract

The prompt contract should instruct the drafting layer to behave as a renderer
over a structured brief, not as a freeform analyst.

### Prompt rules

1. Use only metrics and comparisons present in the structured brief.
2. Prefer YoY framing when the brief marks YoY as available.
3. Fall back to MoM framing only when the brief says YoY is unavailable.
4. Keep the top-level summary short.
5. Keep each marketplace paragraph to 2-4 sentences.
6. Use the standard snapshot table shape.
7. Keep recommendations evidence-backed and financially directional.
8. Do not invent operational actions already taken.
9. If the brief contains warnings or missing-data notes, incorporate them only
   when they materially affect interpretation.

## Exact data requirements

This is the minimum data the drafting stack needs to write these emails well.

### 1. Shared client context

Source:

1. `resolve_client`

Needed fields:

1. `client_id`
2. `client_name`
3. `primary_email`
4. team assignments
5. brand list
6. context notes

Why:

1. supports greeting quality
2. supports future routing to ClickUp or other client-context tools
3. avoids fragmented client resolution logic

### 2. Marketplace/profile selection

Source:

1. `list_monthly_pnl_profiles`

Needed fields:

1. `profile_id`
2. `marketplace_code`
3. `currency_code`
4. `first_active_month`
5. `last_active_month`
6. `active_month_count`

Why:

1. determines which marketplaces can be included
2. constrains the valid report month
3. allows the tool to skip marketplaces with no active data

### 3. Raw financial lines

Source:

1. `get_monthly_pnl_report`

Needed line-item keys:

1. `total_gross_revenue`
2. `total_refunds`
3. `total_net_revenue`
4. `gross_profit`
5. `advertising`
6. `net_earnings`
7. all major refund component rows
8. all major expense component rows
9. `cogs`
10. `payout`

Why:

1. the snapshot table needs the headline metrics
2. driver selection depends on the component rows
3. gross profit / COGS context helps avoid shallow recommendations
4. payout context may matter later even if it is not yet core email copy

### 4. Coverage and validation state

Source:

1. `get_monthly_pnl_report.warnings`
2. profile active-month ranges

Needed fields:

1. requested month window
2. actual months used
3. missing-month warnings
4. missing-COGS warnings
5. unmapped-row warnings

Why:

1. prevents Claude from writing confidently over incomplete data
2. allows clean fallback when YoY cannot be trusted

### 5. Derived comparison metrics

These are required even if they are computed in a helper layer rather than
returned directly by `get_monthly_pnl_report`.

Needed per marketplace:

1. latest reporting month
2. latest prior-year comparable month, if present
3. YTD current-period start and end
4. YTD prior-year comparable window, if present
5. booleans:
   - `latest_month_has_yoy`
   - `ytd_has_yoy`
   - `has_previous_month`
6. for each snapshot metric:
   - latest month value
   - latest month percent of revenue where applicable
   - latest month YoY delta %
   - latest month YoY margin delta in p.p. where applicable
   - latest month MoM delta % where applicable
   - YTD value
   - YTD percent of revenue where applicable
   - YTD YoY delta %
   - YTD YoY margin delta in p.p. where applicable

Why:

1. this is the core numerical substrate behind the email examples
2. making Claude derive all of this ad hoc from raw line items is avoidable
   risk

### 6. Driver candidates

This should be a helper-layer output, not a freeform prompt responsibility.

Needed per marketplace:

1. ranked positive driver candidates with evidence
2. ranked risk candidates with evidence
3. optional tags such as:
   - `revenue_growth`
   - `refund_improvement`
   - `ad_efficiency`
   - `storage_spike`
   - `removal_fee_spike`
   - `margin_compression`
   - `seasonality`

Why:

1. improves consistency of recommendations
2. reduces generic or repetitive commentary
3. gives Claude a stable set of facts to verbalize

## What current tools already support well

The current read-only P&L MCP slice already supports:

1. canonical client resolution
2. marketplace/profile discovery
3. month-window P&L retrieval
4. warnings for missing data, missing COGS, and unmapped rows

## What is still missing for high-quality email drafting

The current slice does not yet provide:

1. a client/month multi-marketplace email envelope
2. deterministic YoY availability detection
3. derived latest-month and YTD comparison metrics
4. ranked driver candidates
5. recipient/sign-off handling
6. a preview or persisted P&L email draft tool

## Recommended next implementation step

Do not jump straight from `get_monthly_pnl_report` to a mutating draft tool.

The next backend/product step should be:

1. design or implement a structured Monthly P&L email brief builder
2. let Claude draft from that brief in preview mode first
3. add persistence only after the preview outputs are consistently good
