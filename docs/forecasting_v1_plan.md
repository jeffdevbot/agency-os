# Forecasting v1 Plan

_Drafted: 2026-03-24 (ET)_

## Purpose

Define the first real implementation plan for `Forecasting v1`.

This should be a practical planning surface for client and internal strategy
work, not a vague “AI forecasting” toy and not a heavyweight statistical
platform.

The goal is to let operators answer:

1. where forecasted dollars come from
2. how those dollars change under explicit assumptions
3. what low / base / high scenarios look like
4. how spend, pricing, conversion, traffic, seasonality, and promotions alter
   the shape of the forecast

## Product decision

### Home

Put Forecasting under `Reports`, not `Command Center`.

Recommended route:

- `/reports/[clientSlug]/[marketplaceCode]/forecast`

Reason:

1. forecasting is client/report work, not admin data management
2. the current reports IA is already `client -> marketplace -> report surface`
3. forecasting should sit beside `WBR` and `Monthly P&L`, not under the admin
   control plane

### Scope

Forecasting v1 should be:

1. marketplace-scoped
2. weekly
3. bottom-up by `child ASIN`
4. driven primarily by Section 1 business facts
5. financially calibrated by Monthly P&L history

It should not start as:

1. a pure macro monthly finance forecast
2. a client-wide cross-marketplace rollup
3. a pure ads simulator
4. an “AI writes one number and trust it” workflow

## Why this shape

The core planning question is not just:

`What will top-line revenue be?`

It is:

`Where will those dollars come from, and what assumptions move them?`

That pushes the product toward:

1. `child ASIN x week` planning
2. explicit metric levers
3. scenario comparison
4. seasonality-aware time windows

This also aligns with the current analyst workflow direction documented in
`docs/claude_primary_surface_plan.md`, where forecasting is treated as a
multisource planning workflow rather than a Slack-style quick answer.

## Current repo/data fit

### Best current source for the forecast engine

Use WBR Section 1 as the core operational forecast dataset.

Current live WBR Section 1 source shape:

1. Windsor seller-business sync
2. daily child-ASIN facts in `wbr_business_asin_daily`
3. core metrics:
   - `page_views`
   - `unit_sales`
   - `sales`
4. current derived metric:
   - `conversion_rate = unit_sales / page_views`

Reference:

- `docs/windsor_wbr_ingestion_runbook.md`

### Financial calibration layer

Use Monthly P&L as a separate calibration and sanity-check layer.

Reason:

1. P&L history is currently deeper than WBR history for key live clients
2. P&L provides the financial reality check beyond traffic/sales mechanics
3. forecasting should not become detached from recent profitability and spend
   discipline

P&L should calibrate and contextualize the forecast, but should not be the
primary forecast grain in v1.

### Ads role in v1

Use WBR Section 2 / Amazon Ads as a recent overlay and scenario lever, not as
the primary forecast engine.

Important constraint:

1. do not pretend exact child-ASIN ad attribution exists if the data/model
   does not support it
2. keep the core engine at `child ASIN x week`
3. let the ads layer operate at `catalog`, `row`, or marketplace scope first

## Source-of-truth decisions

### Metric family

Use `Page Views`, not `Sessions`, for v1.

Reason:

1. current WBR Section 1 is already page-view based
2. current WBR-derived CVR logic is already:
   - `CVR = Unit Sales / Page Views`
3. switching to sessions only for Forecasting would create metric drift across
   tools without a strong enough reason

Core v1 math:

- `Revenue = Page Views x CVR x ASP`
- `CVR = Units Sold / Page Views`
- `ASP = Sales / Units Sold`

If the organization later decides to move the forecasting/reporting language to
sessions, that should be a deliberate cross-tool metric decision, not an
isolated Forecasting choice.

### Forecast grain

Use:

1. weekly periods
2. child ASIN rows
3. marketplace totals as the sum of child ASIN rows

Why weekly:

1. promo timing is easier to reason about weekly than monthly
2. seasonality shape is easier to inspect weekly
3. ad and traffic changes are more naturally planned in weekly tranches

Why child ASIN:

1. this answers where dollars come from
2. it makes the forecast explainable
3. it allows operators to reason about catalog mix, hero SKUs, and weak SKUs

## Verified source assumptions

### SP-API / Windsor business-data side

Verified:

1. Amazon SP-API analytics reporting supports child-ASIN sales/traffic style
   reporting through `GET_SALES_AND_TRAFFIC_REPORT`
2. the report start time may not be more than two years before the request
3. the current Windsor WBR path uses `get_sales_and_traffic_report_by_asin`
   with explicit `date_from` / `date_to`

Interpretation for Forecasting:

1. Section 1 should support a meaningful seasonality lookback window
2. one-year seasonality and two-year context are realistic targets
3. deep Section 1 backfill for target clients is worth doing before relying on
   seasonality-heavy forecasts

### Amazon Ads side

Verified:

1. current app Section 2 is sourced from the Amazon Ads API, not Windsor

Not fully verified yet from primary docs:

1. the exact hard historical backfill ceiling behind the user’s “90 days”
   assumption

Planning implication:

1. do not make v1 depend on deep historical ads retention
2. treat ads as a recent overlay and scenario lever
3. if later source verification confirms a stable retention ceiling, document
   it explicitly in the implementation pass

Current live observed limitation:

1. Amazon Ads report creation is currently behaving like an approximately
   `60` calendar day inclusive retention window in live backfill attempts
2. the app should warn earlier instead of letting the worker fail after the
   request is queued
3. Forecasting v1 should treat this as a real Section 2 history limitation
   unless and until primary Amazon Ads docs or newer live behavior prove
   otherwise

## Product layers

### Layer 1: Recent-run-rate baseline

Purpose:

Build the base forecast from recent observed child-ASIN behavior.

Recommended defaults:

1. baseline lookback window: `12 weeks`
2. default forecast horizon: `26 weeks`
3. optional extended horizon: `52 weeks`

Output:

1. weekly forecast rows per child ASIN
2. marketplace rollup totals

This is the:

`If nothing special changes, what happens next?`

layer.

### Layer 2: Seasonality and trend

Purpose:

Apply longer historical context so the forecast reflects pattern, not just
recent run rate.

Recommended historical windows:

1. preferred seasonality window: `52 weeks`
2. optional trend context: up to `104 weeks` where available

Recommended blend:

1. recent `8-12` week momentum
2. same-week-last-year seasonality shape
3. optional YoY lift/decline factor

Important rule:

Do not simply project “last 6 months grew X%, so the future grows X%.”

Prefer:

1. recent behavior for momentum
2. last-year analog weeks for shape
3. explicit operator control over trend tilt

### Layer 3: Core metric controls

Purpose:

Let operators change the forecast by manipulating the metrics that actually
drive revenue.

Required controls:

1. `Traffic % change`
2. `ASP % change`
3. `CVR percentage-point change`

Controls must be:

1. time-bound
2. scope-bound
3. stackable

Scope options:

1. full catalog
2. selected child ASINs
3. future row-group scope if the row model proves useful

Example control:

1. Weeks `2026-03-23` through `2026-04-13`
2. Scope: full catalog
3. `ASP -8%`
4. `Traffic +15%`
5. `CVR +0.7 pts`

### Layer 4: Promotions and events

Purpose:

Model planned interventions such as promotions, sales events, or merchandising
windows.

Important product rule:

Do not model promotions as a raw:

`Sales +20%`

override.

Model them through metric changes:

1. ASP
2. Traffic
3. CVR
4. optionally Ad Spend

Why:

1. it keeps the model explainable
2. it forces assumptions to be explicit
3. it makes the event logic compatible with the baseline forecast engine

V1 event shape:

1. manual event/promo overlays
2. date-bounded
3. catalog or child-ASIN scoped

Later possibilities:

1. suggest analogous historical weeks
2. prefill known marketplace events
3. detect candidate prior promos from unusual metric shifts

But those should be hints, not implied ground truth.

### Layer 5: Ad spend and TACoS

Purpose:

Reflect one of the main real planning levers used by the agency.

Important modeling rule:

`TACoS` is a derived outcome, not a raw causal metric.

So v1 should not let the model pretend:

`Spend +20% and TACoS automatically improves by 5 points`

without an explicit efficiency assumption.

Recommended v1 shape:

1. user changes ad spend by date window and scope
2. user optionally adds an efficiency assumption
3. that assumption affects traffic and/or CVR
4. forecast revenue updates
5. TACoS is recomputed from forecasted spend and forecasted revenue

This keeps the UI honest while still supporting the real agency workflow.

## Scenario model

Forecasting v1 should support:

1. `Low`
2. `Base`
3. `High`

These scenarios should not be separate disconnected models.

They should share:

1. the same historical dataset
2. the same baseline generation logic

And differ through:

1. baseline trend assumptions
2. overlay controls
3. event assumptions
4. ad efficiency assumptions

Operators should be able to:

1. switch between scenarios quickly
2. compare summary outputs
3. export the currently viewed scenario

## Scenario state

Scenario state should remain session-local in v1.

Reason:

1. it keeps the first build simpler
2. it avoids prematurely committing to a persistence model
3. it encourages fast play/testing without adding save-state complexity up
   front

Recommended v1 behavior:

1. scenario edits live in browser/session state
2. switching scenarios should be fast and reversible
3. export should capture the currently active scenario and assumptions

Later possibility:

1. save a forecast snapshot and reopen it later

That is worth keeping in mind, but it should not be added to v1 unless the
implementation turns out to be unusually cheap. It adds product questions about
ownership, naming, comparison, stale-data handling, and whether reopened
scenarios should rebase onto newer source history or stay frozen.

## UI shape

### Recommended route

- `/reports/[clientSlug]/[marketplaceCode]/forecast`

### Recommended page sections

1. header
   - client
   - marketplace
   - scenario selector
   - lookback window
   - horizon
   - export
2. forecast summary
   - total forecast revenue
   - total forecast units
   - blended ASP
   - blended CVR
   - ad spend
   - TACoS
3. weekly chart
   - low / base / high optional comparison
4. child-ASIN table
   - forecast by week or collapsed totals
5. controls panel
   - baseline settings
   - metric overlays
   - events / promos
   - ad spend overlays
6. assumptions log
   - readable explanation of active assumptions

### Interaction style

The surface should feel:

1. simple
2. interactive
3. a little playful
4. but clearly grounded in visible assumptions and historical context

Avoid:

1. overly dense quant UI
2. invisible model logic
3. claiming false precision

## Export requirement

Forecasting v1 must support export, following the same product principle used
by WBR and Monthly P&L:

`Export what the user is currently looking at.`

V1 export expectation:

1. export the active scenario
2. export the active lookback/horizon context
3. export the active child-ASIN forecast rows visible in the UI
4. export the active weekly summary view
5. export the active assumptions/overlays that produced that view

Recommended first export target:

1. Excel workbook

Recommended workbook tabs:

1. `Summary`
2. `Weekly Forecast`
3. `Child ASIN Forecast`
4. `Assumptions`

V1 export decision:

1. Excel only

## Data prerequisites for rollout

### Required for a serious pilot

1. deep Section 1 backfill for target clients
2. stable child-ASIN mapping coverage
3. enough recent P&L history to calibrate financial reasonableness

### Nice to have but not blocking

1. deeper Section 2 ads history
2. richer inventory overlays
3. automated historical event detection

### Practical rollout recommendation

Start with:

1. `Whoosh US`
2. `Distex CA`

Reason:

1. both are already live in the reporting stack
2. both are already familiar validation clients
3. they give different seasonal/commercial shapes

Important operational note:

If the user is backfilling Whoosh US Section 1 history now, that work should be
treated as directly relevant to Forecasting v1 readiness.

## Shallow-history behavior

If the available Section 1 backfill is too shallow for the selected forecasting
mode, the UI should say so clearly instead of pretending the model is fully
grounded.

Recommended behavior:

1. detect when the available lookback is below the threshold needed for the
   current view
2. show a direct warning on the page
3. recommend a deeper backfill window

Recommended tone:

`Forecast history is too shallow for seasonality-aware forecasting here. Backfill some more. Recommended: at least 52 weeks of Section 1 business history.`

If the user has enough data for Layer 1 but not Layer 2:

1. allow the simple recent-run-rate forecast
2. disable or clearly degrade the seasonality layer
3. explain the limitation in plain language

## Suggested backend architecture

Add a dedicated forecasting service rather than hiding this logic inside WBR or
P&L report builders.

Suggested modules:

1. `backend-core/app/services/forecasting/seed.py`
2. `backend-core/app/services/forecasting/scenarios.py`
3. `backend-core/app/services/forecasting/export.py`

Responsibilities:

1. load historical Section 1 business data
2. load optional Section 2 and P&L calibration context
3. generate baseline weekly child-ASIN forecast rows
4. apply layered scenario controls
5. build UI-friendly response payloads
6. export the current view

Keep this separate from:

1. `section1_report.py`
2. `section2_report.py`
3. Monthly P&L report services

Those should remain data/report sources, not become forecasting engines.

## Suggested frontend architecture

Suggested modules:

1. `frontend-web/src/app/reports/[clientSlug]/[marketplaceCode]/forecast/page.tsx`
2. `frontend-web/src/app/reports/forecast/_lib/*`
3. `frontend-web/src/app/reports/_components/*` for shared chart/export UI as
   needed

The client marketplace hub should eventually add a third card beside:

1. `WBR`
2. `Monthly P&L`
3. `Forecast`

## Not in v1

1. exact child-ASIN ad attribution
2. probabilistic/statistical confidence intervals
3. black-box ML forecasts
4. fully automated promo/event inference
5. multi-marketplace client rollup planning
6. direct writeback to planning systems

## Open questions

1. What is the cleanest operator-facing label for row-group scopes if we later
   expose WBR row groups inside Forecasting?
2. What exact minimum-history thresholds should gate:
   - recent-run-rate only
   - seasonality-aware mode
   - longer-horizon mode
3. What exact Amazon Ads historical-retention ceiling should be documented once
   confirmed from primary Amazon Ads docs?

## Recommended next step

Before implementation starts:

1. deepen Section 1 backfill on the first pilot marketplace(s)
2. confirm the minimum history threshold for calling a forecast
   “seasonality-aware”
3. convert this plan into a thin implementation checklist once the first pilot
   data windows are confirmed
