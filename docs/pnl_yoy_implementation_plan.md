# PnL Year-over-Year Implementation Plan

## Recommendation

Keep the frontend product idea exactly as proposed:

- add a `Standard` / `YoY` view toggle to the existing Monthly P&L page
- replace the month-range picker with a simple year selector in YoY mode
- render a YoY table plus a dual-series chart in YoY mode

Do **not** build that on top of a standalone UI-only YoY stack.

Instead, introduce a shared backend comparison layer that owns Monthly P&L
comparison logic once, then let multiple surfaces depend on it:

1. Claude Monthly P&L email brief
2. Claude Monthly P&L draft generation
3. future frontend YoY view
4. future MCP/Claude YoY-specific tooling if real usage justifies it

That is the cleanest way to prevent drift between:

- what the UI calls "YoY"
- what Claude uses in its brief/draft logic
- what future reporting APIs return

---

## Why This Plan Is Better

We already shipped deterministic P&L comparison logic inside the Claude-facing
brief flow:

- latest-month YoY availability detection
- YTD YoY availability detection
- previous-month fallback
- report-window construction
- warning carry-through
- comparison-mode selection (`yoy_preferred`, `mom_fallback`, etc.)

That logic works, but it currently lives in a Claude-oriented service. If we
build a second YoY implementation just for the frontend, we will end up with
two definitions of the same thing.

So the goal is:

- move shared comparison logic down
- keep presentation logic separate
- let each surface format the data its own way

---

## Scope

### In scope

- shared backend P&L comparison service
- refactor Claude P&L brief/draft path to use it
- backend/frontend support for a YoY page mode built on that shared layer

### Out of scope for the first shared-layer pass

- Excel export for YoY mode
- persisting YoY view state in URL params
- a brand-new Claude/MCP YoY tool unless real usage demands it

---

## Target Architecture

### 1. Canonical report layer

Existing:

- `PNLReportService`

Responsibility:

- build a standard P&L report for one profile and one requested window

### 2. Shared comparison layer

New:

- `backend-core/app/services/pnl/comparison.py`

Responsibility:

- decide what comparison windows exist for a given profile/month
- determine whether YoY is available
- determine whether MoM fallback is available
- fetch the needed underlying reports
- index and normalize those reports into a reusable comparison bundle

This layer should be read-only and presentation-agnostic.

### 3. Surface-specific adapters

Uses of the shared comparison layer:

- `PNLEmailBriefService`
  - builds snapshot metrics, drivers, verdicts, and data-quality notes
- future frontend YoY route/endpoint
  - builds a month-aligned current/prior/delta response for the table and chart
- future MCP/Claude YoY tool, if needed
  - can expose comparison data directly without re-implementing rules

---

## Shared Comparison Layer Contract

The shared comparison layer should return a reusable comparison bundle for one
profile and one selected report month.

Suggested shape:

```python
{
  "comparison_mode_requested": "auto",
  "comparison_mode_used": "yoy_preferred",
  "latest_month_has_yoy": True,
  "ytd_has_yoy": True,
  "has_previous_month": True,
  "current_ytd_complete": True,
  "periods": {
    "latest_month": "2026-02-01",
    "previous_month": "2026-01-01",
    "latest_month_prior_year": "2025-02-01",
    "ytd_start": "2026-01-01",
    "ytd_end": "2026-02-01",
    "ytd_prior_year_start": "2025-01-01",
    "ytd_prior_year_end": "2025-02-01",
  },
  "reports": {
    "latest": {...},
    "previous": {...} | None,
    "latest_prior_year": {...} | None,
    "ytd": {...},
    "ytd_prior_year": {...} | None,
  },
  "indexes": {
    "latest": {...},
    "previous": {...},
    "latest_prior_year": {...},
    "ytd": {...},
    "ytd_prior_year": {...},
  },
  "warnings": [...],
}
```

Important:

- this is not a UI response
- this is not an MCP response
- it is an internal shared data contract

---

## Implementation Phases

## Phase 1 — Shared backend extraction

### Goal

Move the working YoY/comparison logic out of the Claude-specific brief service
and into a shared backend service.

### Files

Create:

- `backend-core/app/services/pnl/comparison.py`

Modify:

- `backend-core/app/services/pnl/email_brief.py`
- related backend tests

### Notes

- keep report fetching conservative; do not reintroduce broad nested
  concurrency around `PNLReportService.build_report_async(...)`
- the comparison layer should stay read-only and not know about email wording

### Validation

- existing P&L brief tests still pass
- existing P&L draft tests still pass
- add targeted tests for the new comparison service

---

## Phase 2 — Frontend YoY mode on top of shared comparison logic

### Goal

Implement the YoY page mode the frontend wants without creating a second set of
comparison rules.

### Backend shape

Add a lightweight route for the frontend, but build it from the shared
comparison layer.

Suggested file:

- `backend-core/app/services/pnl/yoy_report.py`

This service should be thin. Its job is only to reshape the shared comparison
bundle into a UI-friendly YoY response.

That means:

- no duplicate YoY-availability rules
- no duplicate prior-year window logic
- no duplicate warning logic

### Frontend shape

The frontend plan still makes sense with small adjustments:

- add `Standard` / `YoY` toggle in
  `frontend-web/src/app/reports/_components/PnlReportHeader.tsx`
- add a YoY hook under
  `frontend-web/src/app/reports/pnl/_lib/`
- add a new `PnlYoYTable.tsx`
- add dashed-series support to
  `frontend-web/src/app/reports/_components/WbrTrendChart.tsx`
- wire it in
  `frontend-web/src/app/reports/_components/PnlReportScreen.tsx`

### Required corrections to the original frontend plan

- do not hardcode `USD` in YoY formatting
- use the selected profile currency
- clear chart selection when switching between Standard and YoY modes
- keep export and `% of Revenue` hidden in YoY mode for v1

---

## Phase 3 — Claude / MCP downstream options

We do **not** need a new Claude-facing YoY tool immediately.

Current Claude support already benefits from the shared comparison layer
indirectly through:

- `get_monthly_pnl_email_brief`
- `draft_monthly_pnl_email`

### Recommended short-term path

- keep the shared comparison layer internal
- keep existing Claude tools unchanged
- let the brief/draft path consume the new shared layer

### Recommended later path

If real Claude usage shows repeated requests like:

- "show me Whoosh US YoY P&L"
- "compare 2026 to 2025 month by month"
- "give me a YoY P&L view without drafting an email"

then add one of these:

1. extend `get_monthly_pnl_report` with a comparison mode
2. add a dedicated `get_monthly_pnl_yoy_report`

Either option should be powered by the same backend comparison layer, not by a
new Claude-specific implementation.

---

## Why This Matters For Claude

If we leave YoY logic buried only inside the email brief path:

- Claude can draft better emails
- but the UI and future MCP tools will duplicate comparison logic

If we extract it into a shared backend layer:

- Claude and the UI use the same comparison windows
- YoY availability rules stay consistent
- fallback behavior stays consistent
- future skills/tools can reuse the same service

That is the right ownership boundary.

---

## Recommended Next Move

1. Extract the shared comparison layer now.
2. Refactor the existing P&L brief/draft logic to depend on it.
3. Only then build the frontend YoY mode.

That sequence preserves the working Claude behavior while setting up the YoY UI
the right way.
