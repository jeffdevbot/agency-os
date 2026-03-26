# Opportunity Backlog

_Created: 2026-03-23 (ET)_

Purpose:

1. Keep a lightweight record of promising product and platform opportunities.
2. Preserve prioritization and thin-slice thinking without turning ideas into
   premature implementation plans.
3. Avoid polluting shipped-state docs, handoff docs, or changelogs with
   speculative work.

How to use this file:

1. Keep entries short.
2. Update `Status` and `Priority` as reality changes.
3. Prefer documenting the product shape, thin slice, and risks over detailed
   technical plans.
4. If an item becomes active build work, move the implementation detail into a
   dedicated plan doc and keep this file as the short index.

Status meanings:

- `now`: strong candidate for the next build tranche
- `next`: likely soon, but not the very next thing
- `later`: worthwhile, but not close enough to plan yet
- `hold`: strategically interesting, but too broad or premature
- `maybe never`: possible, but high risk or weak ROI
- `shipped`: already live; keep here only to track obvious follow-on polish

## 1. Team Hours
- Status: `shipped`
- Priority: `1`
- Current reality: the baseline Team Hours surface is now live at
  `/command-center/hours`.
- Shipped scope:
  - admin-only Command Center surface for date-range reporting of ClickUp hours
    by team member and client/space
  - Team Members / Clients views
  - summary cards
  - stacked daily charting
  - unmapped user / space cleanup sections
  - CSV export
- Current product name: `Team Hours`
- UI home: `Command Center`
- Access: existing `is_admin` gate is sufficient for v1; do not introduce a
  separate `super_admin` concept yet.
- Ongoing drift reality:
  - some ClickUp spaces will not yet be linked to Command Center brands
  - some time entries may reference ClickUp users not yet linked to
    `profiles.clickup_user_id`
  - the current product surfaces those rows as unmapped / unlinked rather than
    dropping them
  - the intended operational fix remains adding the missing mappings later in
    Command Center
- Current implementation reference:
  - `docs/team_hours_plan.md`
- Nice to have later: tag slicing, richer filtering, utilization-style
  rollups, and profitability overlays.
- Not now: perfect task/tag attribution or a large analytics surface.
- Repo fit: good. There is already a real ClickUp service layer and task API
  path in:
  - `backend-core/app/services/clickup.py`
  - `backend-core/app/routers/clickup.py`
- Main risk: data quality depends on how consistently the team logs time.

## 2. Forecasting v1
- Status: `next`
- Priority: `2`
- Why it matters: clients ask for this often, and it is one of the clearest
  high-value strategist workflows for Agency OS.
- Thin slice: a deterministic forecast seed with editable scenario controls,
  not a heavyweight “AI forecasting engine.”
- Possible Agency OS / Claude tool shapes later:
  - `get_forecast_seed_dataset`
  - `export_forecast_workbook_seed`
- First inputs to support:
  - baseline run rate
  - simple growth assumption
  - event bump assumptions (for example Prime Day)
  - promotion lift assumptions
  - stockout / inventory-awareness where possible
- Product requirement: users should be able to “play” with assumptions rather
  than accept one locked forecast.
- Active plan doc:
  - `docs/forecasting_v1_plan.md`
- Nice to have later:
  - per-child-ASIN scenarios
  - inventory line overlays
  - separate assumptions by event window
  - scenario save/export
- Not now: claiming false precision, overfitting, or building a large ML stack.
- Repo fit: strong strategic fit with the existing Claude-first direction.
- Main risk: forecasts can look more authoritative than they really are if the
  assumptions are not made explicit.

## 3. Returns Health Report v1
- Status: `next`
- Priority: `3`
- Why it matters: return reasons and return-rate trends can drive product,
  listing, and ops decisions; this is useful reporting rather than speculative
  infrastructure.
- Thin slice:
  - return rate vs shipped units
  - top reason-code trends by month
  - basic financial impact framing
- Current constraint: do not design MVP around AI analysis of customer comments
  until those fields are confirmed in real Windsor/SP-API exports.
- Nice to have later:
  - AI-assisted root-cause clustering on customer comments
  - severity flags
  - sellable vs unsellable inventory framing
- Repo fit: decent. Windsor returns sync already exists, but current ingestion
  is still narrow and centered on quantity/date/ASIN.
- Main risk: noisy Amazon reason-code quality and uncertain comment-field
  availability.

## 4. Claude ClickUp Tools
- Status: `shipped`
- Priority: `4`
- Why it matters: useful extension of the shared Agency OS Claude surface for
  operational work.
- Thin slice:
  - list tasks
  - create backlog task in the right destination
  - assign team members
- Current reality:
  - this is now a real Claude/MCP tool belt
  - the live surface includes:
    - `list_clickup_tasks`
    - `get_clickup_task`
    - `resolve_team_member`
    - `prepare_clickup_task`
    - `create_clickup_task`
  - the ClickUp Claude surface is now live and in pilot testing
- Active plan doc:
  - `docs/claude_clickup_tools_plan.md`
- Remaining follow-on work:
  - idempotency persistence for create
  - task update / close / move flows
  - any pilot-driven polish that only becomes obvious through live usage
- Not now: broad ClickUp admin workflows or replacing the app UI.
- Main risk now: operator ergonomics and retry safety rather than whether the
  core MCP surface exists.

## 5. Shared AI Service / Model Lanes
- Status: `later`
- Priority: `5`
- Why it matters: real technical debt exists around duplicated model/provider
  handling and mismatched parameter support across features.
- Thin slice:
  - lane-based model routing (`fast`, `writing`, `extraction`, `agent`)
  - shared backend completion wrapper
  - centralized token logging / fallback behavior
- Important distinction:
  - lane-based routing is the real short-term need
  - broad multi-provider abstraction is not yet proven necessary
- Repo fit: good, but this is enabling infrastructure rather than direct
  user-facing product value.
- Not now: full provider plug-and-play architecture unless a second provider
  is truly needed in production.

## 6. N-Gram API Automation
- Status: `later`
- Priority: `6`
- Why it matters: removing the STR export/upload step would reduce friction on
  a tool the team already uses.
- Thin slice:
  - pull report inputs automatically from Amazon Ads-connected data
  - generate the same workbook without manual STR upload
- Nice to have later:
  - scheduled refreshes
  - readiness notifications
  - AI-assisted negative suggestions for review
- Not now: direct publish back to Amazon.
- Main risk: this is not a small extension of the current file-based N-Gram
  tool; it becomes a new ingestion/reporting pipeline.

## 7. Client Context Layer
- Status: `hold`
- Priority: `7`
- Why it matters: a unified client context would materially improve meeting
  prep, reporting synthesis, and smarter drafts.
- Inputs that could matter:
  - WBR emails
  - Monthly P&L emails
  - meeting agendas and notes
  - post-meeting recaps
  - ClickUp work
  - targets
  - client communications
- Why this is on hold: this is a platform, not a feature. It is large enough
  to distort the roadmap if started too early.
- Better framing: use narrow, workflow-specific context improvements first
  instead of building “all client context” in one move.

## 8. Multi-Provider AI Plug-and-Play
- Status: `hold`
- Priority: `8`
- Why it matters: optional future flexibility across OpenAI, Claude, and
  others.
- Current view: desirable in theory, but weaker than the case for shared AI
  lanes and runtime cleanup.
- Not now: provider abstraction for its own sake.
- Main risk: architecture tax before real demand exists.

## 9. N-Gram Direct Publish to Amazon
- Status: `maybe never`
- Priority: `9`
- Why it matters: could remove a manual step after human review.
- Why it is low priority: no undo path, real campaign risk, and heavy trust /
  safety requirements.
- If ever pursued later:
  - require explicit review
  - require diff preview
  - require audit trail
  - fail closed by default
- Current view: not a near-term roadmap item.
