# Admin Client Hub IA — Implementation Plan

Target information architecture: consolidate client admin under `/clients/[clientSlug]/{reports,data,team}`. Staged over small vertical slices. Jeff + Claude + Codex collaborate; see roles below.

---

## Scorecard

Tick each box as slices merge. Brief one-liner after each box can note PR / commit SHA once landed.

### Pass 1 — Shell

- [x] **Slice 1** — `/clients` list + `/clients/[slug]` overview with 3 tiles + admin-only root nav entry. Tiles link to existing routes. *(Merged 2026-04-23, Codex impl, reviewed by Claude.)*
- [x] **Slice 1.1** — Bonus polish: persistent "Ecomlabs Tools" top nav + reusable breadcrumbs scoped to `/clients/*` via layout; remove the "Active clients" stat card. Components live at `frontend-web/src/components/nav/` for cross-app reuse. *(Merged 2026-04-23, Codex impl, reviewed by Claude.)*
- [ ] **Slice 5 (post Pass 2)** — Roll the shared `AppTopNav` + `AppBreadcrumbs` out to remaining tools (`/ngram`, `/npat`, `/scribe`, `/root-keywords`, `/reports`, `/command-center`, `/adscope`, `/`). One layout wrap per tool; no logic changes. Sequenced after the `/clients/*` pattern is proven through Pass 2.

### Pass 2 — Re-parent existing screens

- [x] **Slice 2a** — `/clients/[slug]/reports` renders `ClientReportsHub`. 307 redirect from `/reports/[slug]`. *(Merged 2026-04-23, Codex impl, reviewed by Claude.)*
- [x] **Slice 2b-1** — Extract `ClientTeamWorkspace` from `/command-center/clients/[id]/page.tsx`. Scope widened after Codex pushback: extract the ENTIRE client detail body (header card + brand + org-chart + shared bootstrap/refresh/error state), not just brand/org-chart, because state is entangled. Command Center `page.tsx` becomes a thin wrapper. *(Merged 2026-04-23, Codex impl, reviewed by Claude.)*
- [x] **Slice 2b-2** — Mount `<ClientTeamWorkspace/>` at `/clients/[slug]/team`. Update Team tile href. *(Merged 2026-04-23, Codex impl, reviewed by Claude.)*
- [x] **Slice 2c** — `/clients/[slug]/data` renders `ReportApiAccessScreen` with provider-neutral copy. 307 redirects from `/reports/client-data-access/*`. *(Merged 2026-04-23, Codex impl, reviewed by Claude. Polish: `clientDataAccessHref` still points to old path via redirect — update when 307→308 flip happens.)*
- [x] **Slice 2d** — Data status dashboard on `/clients/[slug]/data`. Read-only display above `ReportApiAccessScreen` showing: per-connection status (connected / error / revoked, last validated, last error) from `report_api_connections`; per-WBR-profile cards with nightly sync flags (business, ads, STR SP/SB/SD) + inherited inventory/returns, and backfill coverage (min/max date per fact table). *(Merged 2026-04-23, Codex impl, reviewed by Claude. Codex correctly pushed back on one schema mismatch — `wbr_inventory_asin_snapshots` not `_daily` — during implementation.)*

Redirects ship as 307 (temporary) during migration. After Passes 1–2 soak for a week without rollback, a follow-up PR flips them to 308 (permanent) to let browsers/CDNs cache. **Do not ship 308s on first landing** — they cache aggressively and make rollback painful.

### Pass 3 — Rebuild Data against Option B schema + SP-API direct migration

- [x] **Slice 3a** — Schema migration: two partial unique indexes on `report_api_connections` — `(client_id, provider, external_account_id) WHERE external_account_id IS NOT NULL` plus `(client_id, provider) WHERE external_account_id IS NULL`. Preserves "one pending row per (client,provider)" invariant while enabling multi-account. Code adaptation to upsert paths is a follow-up slice. *(Applied 2026-04-23 via MCP, file at `supabase/migrations/20260423220000_*.sql`. Claude owned.)*
- [ ] **Slice 3b** — `/clients/[slug]/data/connections` management UI rebuild for multi-region / multi-account. *Partially redundant with Slice 2d's read-only status dashboard; only needed when managing (adding/removing) multiple accounts per (client, provider) becomes a real workflow. Defer until a client actually authorizes a second account for the same region.*
- [x] **Slice 3c** — `SpApiReportsClient` generic create/poll/download/decompress helper + tests. Async Python client at `backend-core/app/services/reports/sp_api_reports_client.py`; 8 passing tests; fixture-based, no live network. *(Merged 2026-04-23, Codex impl, reviewed by Claude. Note: I referred to this as "Slice 3b" in the Codex prompt by mistake — the client work is scorecard slot 3c.)*
- [x] **Slice 3d** — Section 1 (business data) direct SP-API service writing to `wbr_business_asin_daily__compare`; A/B-ready. Day-by-day `GET_SALES_AND_TRAFFIC_REPORT` loop (required because SP-API exposes date aggs + asin aggs as separate axes). Admin endpoint `POST /admin/reports/api-access/amazon-spapi/compare-business`. Compare table migration at `supabase/migrations/20260424032333_add_wbr_business_asin_daily_compare.sql` (Claude owned, applied 2026-04-24 via MCP). *(Merged 2026-04-23, Codex impl, reviewed by Claude. Operational note: admin endpoint blocks HTTP connection for full run — run in 7-15 day chunks, not full backfill at once.)*
  - **Hotfix 2026-04-24 (commit `42d1ef3`):** `SpApiReportsClient._parse_json` had a scalar-only filter (`if isinstance(value, (str, int, float)) or value is None`) that silently stripped nested fields from `GET_SALES_AND_TRAFFIC_REPORT` responses, surfacing as `[{}]` and zero-row compares. Filter removed; nested structures now preserved. Verified live against Distex CA (2026-04-15): 143 child-ASIN rows + real CAD sales/traffic. The "BA / draft-app gating" hypothesis we chased through Amazon SP-API support for ~16 hours was wrong — Amazon's data was healthy the whole time; our parser was the issue. See memory `project_spapi_draft_app_blocker.md` for the full debunk and lesson. Slice 3d's compare endpoint is now functional end-to-end.
  - **Known issue (open):** `GET_SALES_AND_TRAFFIC_REPORT` returns 2 days of data when given a single-day window (Amazon treats `dataStartTime` and `dataEndTime` as inclusive at date granularity, even with next-day-midnight ends). The day-by-day loop in `SpApiBusinessCompareService` will double-count `salesAndTrafficByAsin` aggregates if run as-is across multi-day backfills. Fix candidates: switch to `end_inclusive=True` (same-day 23:59:59.999Z) and verify Amazon honors it, OR post-filter `salesAndTrafficByDate` and re-aggregate. Track separately; not blocking 3.5b's UI work.
- [x] **Slice 3e** — Listings catalog direct SP-API. Preview endpoint + write path both landed; `wbr_listing_import_batches.source_provider` column added and backfilled. Distex CA live on SP-API listings (929 rows). *(Shipped as commits `a31c93e` (preview) + `0caf3fc` (write) on 2026-04-24. Codex impl, reviewed by Claude. Naming note: the write-path commit message labeled itself "Slice 3f" — same drift as the 3b/3c mixup; both commits belong to scorecard slot 3e.)*
- [ ] **Slice 3f** — Section 3 inventory + returns direct SP-API.
- [ ] **Slice 3g** — Delete Windsor services, env vars, and frontend references. Repoint nightly sync.
- [ ] **Slice 3h** — Delete P&L Windsor compare (`windsor_compare.py` + `PnlWindsorCompareCard` + hook).

### Pass 3.5 — Data page UX refactor

`/clients/[slug]/data` is currently a Windsor-era screen that mixes three concerns into one dense table: connection state, per-WBR-profile backfill coverage, and nightly-sync flags. It also has no notion of region or marketplace — a fiction that breaks the moment a client like Whoosh (CA + US + UK, with AU / JP on the roadmap) needs more than one region.

This pass restructures the page around the actual auth + data topology: **Region → (Connections + Marketplaces)**. Each region block holds its own region-scoped connections (Ads + SP-API) and the marketplaces inside that region (per-WBR-profile Backfill + Nightly-sync). Empty regions collapse to a "+ Add region" CTA so single-region clients (e.g., Distex NA / CA) aren't visually taxed by empty EU / FE blocks.

Layout sketch:

```
NA  ┌─────────────────────────────────────────────────┐
    │ Connections:  [Ads NA]  [SP-API NA]             │
    │ Marketplaces:                                   │
    │   CA → Backfill / Sync                          │
    │   US → Backfill / Sync                          │
    └─────────────────────────────────────────────────┘
EU  ┌─────────────────────────────────────────────────┐
    │ Connections:  [Ads EU]  [SP-API EU]             │
    │ Marketplaces:                                   │
    │   UK → Backfill / Sync                          │
    └─────────────────────────────────────────────────┘
FE  ┌─ Not connected. [+ Connect Ads] [+ Connect SP-API] ─┐
```

Why region-grouped instead of section-first:

- **Connections are regional, not per-marketplace.** One NA auth covers CA + US; one EU auth covers UK + DE + FR + etc. Showing them outside a region context misrepresents the auth topology.
- **Backfill + Sync are per-marketplace** (per WBR profile), and each marketplace lives inside exactly one region — so nesting matches the real data model.
- **Scales to multi-region clients** without duplicating connection UIs or confusing "which auth covers this market."
- **First-visit happy path still works:** a brand-new client sees empty region blocks with "Connect X" CTAs; connecting in a region unlocks its marketplaces; marketplaces show backfill + sync affordances.

- [x] **Slice 3.5a-region** — First-class region support for Amazon Ads. Shipped: backfill migration + NOT NULL on `region_code`; OAuth initiate/state/callback + `upsert_amazon_ads_connection` + Ads API helper + nightly sync + search-term sync all carry region end-to-end; NA/EU/FE → API host map; frontend `createAmazonAdsAuthorizationUrl` accepts optional region. Backend tests cover NA default, EU round-trip, host mapping, and invalid-region rejection. *(Codex impl 2026-04-24, reviewed by Claude, pending commit. Migrations `20260424170334_amazon_ads_region_backfill.sql` and follow-up `20260424174837_report_api_connections_null_account_include_region.sql` — the latter widens the null-external-account partial unique index to include `region_code` so multi-region Ads rows for the same client can coexist. Open items: LWA authorization host and token refresh host remain global (`www.amazon.com/ap/oa` / `api.amazon.com/auth/o2/token`) — needs a live EU or FE OAuth round-trip before 3.5a UI ships non-NA connects to users.)*
- [x] **Slice 3.5a-api** — Backend + API wrapper prep shipped. Three admin endpoints: `POST /admin/reports/api-access/amazon-ads/validate`, `POST /amazon-ads/disconnect`, `POST /amazon-spapi/disconnect`. Disconnect is soft-revoke (`connection_status='revoked'` + `refresh_token=null`, row preserved, idempotent). Ads validate refreshes token + calls `/v2/profiles` via the region-aware helper from 3.5a-region. Frontend wrappers `validateAmazonAdsConnection`, `disconnectAmazonAdsConnection`, `disconnectSpApiConnection` landed in `reportApiAccessApi.ts`. Tests cover happy path + error path + validating-a-revoked-row + idempotent re-call + nonexistent-tuple + reconnect-after-revoke (important: verifies the soft-revoke → OAuth → upsert loop doesn't collide on the partial index). *(Codex impl 2026-04-24, reviewed by Claude, pending commit.)*
- [x] **Slice 3.5a** — Region blocks + Connections UI shipped. `/clients/[slug]/data` now renders three `RegionBlock`s (NA / EU / FE) at the top, each with a `ConnectionsStrip` holding Ads + SP-API `ProviderConnectionCard`s. State-first visual treatment (Not connected / Connected / Error / Revoked) via accent color + border. Empty regions collapse to outline `+ Connect` CTAs with marketplace-unlock subheads. Legacy `ReportApiAccessScreen` now inside a closed-by-default `<details>` disclosure labeled "Advanced connection details (legacy)". Slice 2d dashboard unchanged below. Components live at `frontend-web/src/app/clients/_components/data-connections/` (Orchestrator + RegionBlock + ConnectionsStrip + ProviderConnectionCard). *(Codex impl 2026-04-24, reviewed by Claude. Scope creep accepted: Codex filled a gap in 3.5a-api — `validateSpApiConnection` + backend SpApiValidateRequest now accept optional `region`; `get_spapi_connection` accepts optional region filter; `upsert_spapi_connection` now considers region when external_account_id is absent; list endpoints (Ads + SP-API) return new `shared_connections` / `connections` arrays alongside existing singles. All changes backward-compat via optional params / additive fields.)*
- [x] **Slice 3.5b** — Marketplaces + Backfill UI shipped. ACTIVE `RegionBlock`s now render nested `MarketplaceCard`s per WBR profile in that region. Each card has 5 `DomainBackfillRow`s in order: Business / Ads / Listings / Inventory / Returns. Business + Listings active when region's SP-API is Connected (variant `active`); disabled with "Connect SP-API to enable" otherwise. Ads is read-only "Managed by nightly sync." Inventory + Returns disabled "Coming soon — Slice 3f." Business helper copy: "A/B compare against Windsor. Production data still flows through nightly sync." Date-range picker defaults to L3D (today_utc - 5 → today_utc - 3). Business wires to `/api/admin/spapi-compare-business` (writes `wbr_business_asin_daily__compare`); Listings wires to `/api/admin/spapi-import-listings` (writes production via Slice 3f). Backend scope creep (backward-compat): `runSpApiBusinessCompareBackfill` wrapper has 15-min `AbortController` timeout with "Backfill timed out — try a smaller date range" surfaced. Listings coverage reads `wbr_profile_child_asins.updated_at`; Business coverage reads compare-table dates. *(Codex impl 2026-04-24, reviewed by Claude. Live walkthrough deferred — Codex couldn't auth as admin in its local session; Jeff verified post-deploy.)*
- [ ] **Slice 3.5c** — Nightly sync within marketplace cards. Per-domain toggles wired to the `wbr_profiles.*_enabled` columns already surfaced by Slice 2d, living inside each marketplace card below the backfill row. Last-run timestamps next to each toggle. Decoupled from one-time backfill actions by visual grouping.
- [ ] **Slice 3.5d** — Remove the old mixed UI block from `ReportApiAccessScreen`, strip remaining Windsor references on this page, final copy pass, and tighten Ads OAuth initiate to require region (was optional post-3.5a-region to avoid breaking the legacy UI during transition).

**Sequencing notes:** 3.5a-region ships first (backend Ads region parity, no UI). Then 3.5a-api (validate + disconnect endpoints + frontend wrappers). Then 3.5a ships the Region-grouped UI + Connections strip. 3.5b (marketplace cards + per-domain Backfill) and 3.5c (nightly sync toggles inside marketplace cards) can ship in either order; 3.5b is higher value since it unblocks the manual onboarding flow Jeff runs today. 3.5d is cleanup, last.

**Open design questions (resolved at slice-prompt time):**
- "Last backfilled: X" — derive from each fact table's min/max date (Slice 2d approach, no new table) vs. a dedicated `data_backfill_runs` audit table. Leaning derive-from-facts to avoid a migration.
- Synchronous vs. enqueued backfills — Slice 3d's admin endpoint blocks HTTP for full runs, so 3.5b's UI must frame backfill in chunks (e.g., 7–15 day picker defaults) rather than a single "backfill all" button. Proper job queue is out of scope for this pass.
- Amazon Ads backfill path — no direct replacement endpoint exists yet (Ads data still flows through the existing Windsor/Ads pipeline). Slice 3.5b may render the Ads row as read-only ("Managed by nightly sync") until that's clarified.

### Pass 3.6 — Imports section on Data page

Under the revised IA boundary (see Decisions), CSV/file uploads and third-party data imports are ingestion channels and live on Data, not Reports. This pass adds an **Imports** section to `/clients/[slug]/data` alongside the Connections / Backfill / Nightly sync sections from Pass 3.5, and migrates existing upload UIs out of the WBR and P&L setup screens.

- [ ] **Slice 3.6a** — Imports section scaffolding on `/clients/[slug]/data`. Per-report-profile cards rendering upload history (last uploaded timestamp, row count, import status). No new upload UI yet — just the surface and read-only history.
- [ ] **Slice 3.6b** — Move Pacvue CSV import for WBR profiles into the Imports section. Per-WBR-profile "Upload Pacvue CSV" action (drag-drop + file picker) wired to the existing backend endpoint. Leave the old upload UI in WBR setup in place temporarily for rollback.
- [ ] **Slice 3.6c** — Move P&L CSV upload for PnL profiles into the Imports section. Per-PnL-profile upload action. Same rollback pattern as 3.6b.
- [ ] **Slice 3.6d** — Remove the old upload UIs from `WbrProfileWorkspace` and the PnL setup screen once 3.6b + 3.6c have soaked.

**Sequencing notes:** 3.6a first (scaffolding, no behavior change — low risk). 3.6b and 3.6c are independent and can ship in either order. 3.6d is cleanup after both have soaked.

**Open design questions:**
- Imports section placement — above or below Backfill in the visual stack? Uploads arguably come before API backfills in the mental model (they're the manual equivalent of ingestion), so lean above.
- One Imports card per profile accepting multiple file types, vs. per-source cards (a Pacvue card, a P&L card, etc.)? Lean per-source so status/history is obvious and empty states are unambiguous.
- Interaction with Pass 4 — see that pass's updated scope.

### Pass 4 — Independent UI refactor

- [ ] **Slice 4** — Reorganize `WbrProfileWorkspace.tsx` kitchen sink under `/clients/[slug]/reports/[mkt]/wbr/setup/*`. Original plan had four tabs (Sync / Imports / Mapping / Profile); once Pass 3.5c moves Sync and Pass 3.6b moves Imports onto the Data page, this pass is left with Mapping / Profile only — revisit at that point whether a tab split is still worth doing or if a single-page layout is simpler.

---

## How we work

### Roles

- **Jeff:** Owner, triggers Codex with each slice prompt, runs the app to spot-check. Final merge authority.
- **Claude (PM + reviewer + schema):** Writes prompts, owns all Supabase migrations (has MCP access; Codex does not), reviews diffs against acceptance criteria, distinguishes blockers from polish, updates this scorecard.
- **Codex (implementer):** Implements one slice per prompt. Reads migration SQL but does not invent schema changes. Pushes back if a prompt is risky or underspecified.

### DB schema is an external contract

Any slice that needs a schema change is blocked until Claude lands the migration first. Codex treats schema as read-only: reads SQL, codes against it, never writes DDL. Each slice's "Migration status" field says explicitly whether DB work is applied, pending, or not needed.

### Slice discipline

Every slice:
- Targets specific files/routes.
- Lists compatibility constraints (which old routes must keep working, which redirect, what can break).
- Has acceptance criteria concrete enough to verify in < 5 minutes.
- States migration status.
- Is small enough to land as one PR.

### Review rubric — blockers vs polish

Reviews call out **blockers** that must be fixed before merge, and **polish** noted for future cleanup. Anything not on the blocker list ships.

**Blocker criteria:**
- Fails acceptance test listed in the slice.
- Breaks a compatibility constraint (something old that must still work, doesn't).
- Security / auth regression.
- Type errors or test failures.
- Schema drift from current migrations.

**Not blockers (noted as polish, shipped anyway unless Codex asks):**
- Style / naming nits.
- Micro-optimizations.
- Missing tests where none were required by the slice.
- Documentation / comment suggestions.
- Refactoring opportunities in untouched neighboring code.

If a review adds new requirements that weren't in the original prompt, those do not block — they go on the scorecard as a follow-up slice.

### Pushback protocol

Codex is expected to push back on ambiguous or technically risky prompts instead of guessing. Preferred format: stop, state the ambiguity or risk, propose 1–2 options, wait. Not overruling — just catching problems before they're encoded.

---

## Constraints that apply to every slice in Passes 1–2

- **Slug resolution:** no new column on `agency_clients`. Slugs computed from `name` via `slugifyClientName()` in `frontend-web/src/app/reports/_lib/reportClientData.ts:45`. Unchanged.
- **Admin check:** every server page uses the exact auth pattern from `frontend-web/src/app/reports/client-data-access/page.tsx:5-23` (Supabase session → `profiles.is_admin` lookup → redirect if not admin).
- **No schema changes** in Pass 1 or Pass 2. If Codex believes one is required, it stops and flags it.
- **No UI redesign** of components being re-parented. Copy tweaks to de-Windsorize `ReportApiAccessScreen` in 2c are explicitly allowed; everything else is carry-over.
- **URLs slug-based** in every new route. The only `client_id` uuid in a URL is the Team-tile fallback during Slice 1 (because Command Center still uses uuid). Removed in Slice 2b.
- **Redirects are 307** (temporary) via Next.js `next.config.*` redirects array (`permanent: false`), not client-side `router.push`. Upgraded to 308 in a later follow-up PR after the new routes have soaked.
- **Package manager:** `npm`. Codex runs `npm -C frontend-web run typecheck` and `npm -C frontend-web run test:run` before claiming done.
- **Client-component auth:** existing pattern in `frontend-web/src/app/page.tsx` deliberately avoids async Supabase calls inside `onAuthStateChange` (see the explicit comment at line 30). New client-component logic that needs `profiles.is_admin` fetches it in a **separate `useEffect` keyed on `user`**, never inside the auth-change callback.
- **Shared server helpers** (introduced in Slice 1): every server page under `/clients/**` uses `requireAdminUser()` and `resolveClientBySlug()` from `frontend-web/src/app/clients/_lib/`. Do not duplicate the auth-check or slug-resolution inline.

---

## Decisions captured so far

- **IA boundary (revised during Pass 3.5 / 3.6 planning):** Data = the full **data ingestion pipeline** for a client — OAuth connections, API backfills, nightly sync state, CSV/file uploads, external-account ids. Reports = **report structure and presentation** — WBR row tree, ASIN → row mapping, campaign exclusions, visualization settings. Team = brands + org-chart. Rule of thumb: *if it's an ingestion channel it's Data; if it's a semantic/structural choice about how data is displayed it's Reports.* An earlier draft held Data = credentials-only with uploads living under Reports; that held for the Windsor era but didn't survive the SP-API migration, which made clear that a CSV upload is just a manual ingestion channel and belongs next to OAuth/API ingestion. Codex's original argument ("report-specific structural config belongs with the report") is still respected — row tree + ASIN mapping + campaign exclusions stay with Reports.
- **Connection uniqueness (Option B):** future schema is `(client_id, provider, external_account_id)`. Supports multiple seller accounts per client in same region (two current prospects have this).
- **P&L Windsor compare: killed outright**, not migrated. Wrong data source, didn't work.
- **Direct SP-API migration sequencing:** domain-by-domain (business → listings → inventory → returns), each with A/B against Windsor in a separate endpoint during cutover.

---

## Slices

Each slice below has: Goal, Compatibility constraints, Migration status, Files, Acceptance criteria, and a self-contained Codex prompt.

---

### Slice 1 — `/clients` shell with tiles

**Goal:** Admin-only `/clients` list page, `/clients/[slug]` overview with 3 tiles (Reports / Data / Team). One new admin-only tile on root `page.tsx`. Tiles link to **existing** routes.

**Compatibility constraints:**
- Must-keep-working: `/reports/[slug]`, `/reports/client-data-access/[slug]`, `/command-center/clients/[id]` — all unchanged.
- Can redirect: nothing yet.
- Can temporarily break: nothing.

**Migration status:** N/A — no DB changes.

**Files:**
- Create: `frontend-web/src/app/clients/_lib/adminGuard.ts` (server-only `requireAdminUser()`)
- Create: `frontend-web/src/app/clients/_lib/resolveClientBySlug.ts` (server-only slug → client record)
- Create: `frontend-web/src/app/clients/page.tsx`
- Create: `frontend-web/src/app/clients/[clientSlug]/page.tsx`
- Create: `frontend-web/src/app/clients/_components/ClientOverviewTiles.tsx`
- Edit: `frontend-web/src/app/page.tsx` (add 6th tile, admin-only conditional rendered via separate `useEffect`)

**Acceptance criteria:**
1. Non-admin visiting `/clients` or `/clients/[slug]` → redirected to `/`.
2. `/clients` lists all active clients (`status='active'`), alphabetical, clickable to `/clients/[slug]`.
3. `/clients/[slug]` resolves slug via `slugifyClientName` (redirect to `/clients` on miss) and renders 3 tiles.
4. Tile hrefs: Reports → `/reports/${slug}`, Data → `/reports/client-data-access/${slug}`, Team → `/command-center/clients/${client.id}` (uuid).
5. Root `/` shows "Clients" tile (🏢) for admins, hides for non-admins. The `is_admin` fetch runs in a separate `useEffect` keyed on `user`, **not** inside `onAuthStateChange`.
6. `_lib/adminGuard.ts` and `_lib/resolveClientBySlug.ts` are the only places where the admin check and slug resolution are implemented — both new server pages import them.
7. `npm -C frontend-web run typecheck` + `npm -C frontend-web run test:run` pass.

**Codex prompt:**

```
TASK: Add admin-only /clients hub that surfaces existing per-client setup pages. Introduce two shared server helpers to avoid repeating auth + slug logic.

CONTEXT:
- Next.js App Router repo at /Users/jeff/code/agency-os/frontend-web.
- Package manager: npm. Run `npm -C frontend-web run typecheck` and `npm -C frontend-web run test:run` before claiming done.
- This is the first of several passes adding a consolidated client admin hub. This pass ONLY adds the shell; it does not move any existing functionality. Existing routes keep working unchanged.
- The root page frontend-web/src/app/page.tsx is a CLIENT component ("use client" at line 1). Line 30 has a deliberate comment: "use session parameter directly (no async/getUser)" — the repo has a known auth-deadlock risk when async Supabase calls are made inside onAuthStateChange. Respect this: any new async fetch (e.g., is_admin lookup) must live in a SEPARATE useEffect keyed on `user`, never inside the onAuthStateChange callback.
- Do NOT run any Supabase migrations. If you think you need a schema change, STOP and ask.

WHAT TO BUILD:

1. New helper: frontend-web/src/app/clients/_lib/adminGuard.ts
   - Server-only (no "use client").
   - Exports `requireAdminUser()`: creates a route client via createSupabaseRouteClient, fetches user + profiles.is_admin. If not signed in -> redirect("/"). If not admin -> redirect("/"). Returns { user, supabase } on success.
   - Pattern reference: frontend-web/src/app/reports/client-data-access/page.tsx lines 5-23. Consolidate that pattern here.

2. New helper: frontend-web/src/app/clients/_lib/resolveClientBySlug.ts
   - Server-only.
   - Exports `resolveClientBySlug(supabase, slug)`: loads active clients, finds the one whose slugifyClientName(name) === slug. If no match -> redirect("/clients"). Returns { id, name } on success.
   - Import slugifyClientName from frontend-web/src/app/reports/_lib/reportClientData.ts.

3. New page: frontend-web/src/app/clients/page.tsx
   - Server component. First line of body: `const { supabase } = await requireAdminUser();`.
   - Lists active clients from agency_clients (filter status='active'), ordered alphabetically by name.
   - Each row shows client name + a link to /clients/[clientSlug] where clientSlug = slugifyClientName(client.name).
   - Visual style: mirror the grid/card look of frontend-web/src/app/command-center/clients/page.tsx. Read-only — no create form in this pass.

4. New page: frontend-web/src/app/clients/[clientSlug]/page.tsx
   - Server component. First lines:
       const { supabase } = await requireAdminUser();
       const { clientSlug } = await params;
       const client = await resolveClientBySlug(supabase, clientSlug);
   - Renders: client name as H1, then <ClientOverviewTiles clientSlug={clientSlug} clientId={client.id} />.

5. New component: frontend-web/src/app/clients/_components/ClientOverviewTiles.tsx
   - Accepts `{ clientSlug: string; clientId: string }` and renders the three tiles.
   - Tile hrefs (this pass only, will change in later passes):
       Reports -> `/reports/${clientSlug}`
       Data    -> `/reports/client-data-access/${clientSlug}`
       Team    -> `/command-center/clients/${clientId}`   (uuid, NOT slug)
   - Visual language matches the tiles on frontend-web/src/app/page.tsx lines 114-203 (white rounded card, emoji, title, description, launch link).
   - No client-side state; pure render.

6. Edit: frontend-web/src/app/page.tsx
   - Add a conditional 6th tile "Clients" (emoji 🏢) in the existing grid (currently has 5 tiles: N-Gram, N-PAT, Scribe, Root Keywords, Reports — add Clients as the 6th).
   - Add a separate useEffect keyed on `user` that fetches profiles.is_admin and stores it in state (e.g., `const [isAdmin, setIsAdmin] = useState(false);`). Include a cancellation flag so unmounts don't setState.
   - Do NOT add an await or .then() inside the onAuthStateChange callback. The auth callback only updates user/session state as it does today.
   - Render the Clients tile only when isAdmin is true.
   - Link target: `/clients`.

CONSTRAINTS:
- No migrations. No schema changes.
- Do not alter existing routes, components, or copy (outside the explicit root page.tsx edit above).
- URLs are slug-based; the Team tile's link is the only place a client_id uuid appears in a URL (because /command-center still uses uuid).
- Use existing helpers: slugifyClientName, createSupabaseRouteClient, getBrowserSupabaseClient.
- Do not add new npm dependencies.

PUSH BACK IF:
- Any part of this prompt feels ambiguous about async-in-auth-callback behavior.
- You discover that _lib helpers as specified would collide with existing code in a way not covered above.
- You think a migration is needed.

ACCEPTANCE TESTS YOU MUST VERIFY BEFORE CLAIMING DONE:
1. `npm -C frontend-web run typecheck` passes.
2. `npm -C frontend-web run test:run` passes (no new tests required unless a helper you touched already has tests).
3. Hit /clients as a non-admin (simulate by temporarily flipping is_admin false in DB or a local override) — redirected.
4. Hit /clients as an admin — list renders with clickable rows.
5. Hit /clients/[some-real-slug] — 3 tiles render; clicking each lands on the expected existing URL.
6. Root page (/) shows the Clients tile for admins, hides it for non-admins.
7. No new async work inside onAuthStateChange. Confirmed by grepping your own diff.

Report back with: list of files changed, any deviations from this spec with reasoning, and the output of typecheck + test:run.
```

---

### Slice 2a — Re-parent Reports

**Goal:** `/clients/[slug]/reports` renders `ClientReportsHub`. 307 redirect from `/reports/[slug]` to new URL. Update Slice 1 tile href.

**Compatibility constraints:**
- Must-keep-working: `/reports/[slug]/[mkt]/wbr/*` and everything deeper — these keep their current paths (moved in Pass 4).
- Can redirect: `/reports/[slug]` only (exact match, not prefix).
- Can temporarily break: nothing.

**Migration status:** N/A.

**Files:**
- Create: `frontend-web/src/app/clients/[clientSlug]/reports/page.tsx` (uses Slice 1 helpers)
- Edit: `frontend-web/src/app/clients/_components/ClientOverviewTiles.tsx` (Reports tile href)
- Edit: `frontend-web/next.config.*` (add scoped 307 redirect with `permanent: false`)
- Possibly edit: `frontend-web/src/app/reports/_lib/reportsHeaderState.ts` (add a clause for `/clients/*/reports` breadcrumbs if needed)

**Acceptance criteria:**
1. `/clients/[slug]/reports` renders visually identical UI to the old `/reports/[slug]`.
2. `/reports/[slug]` 307-redirects to `/clients/[slug]/reports`.
3. `/reports/[slug]/[mkt]/wbr/anything` still works — no redirect loop, no 404.
4. Breadcrumbs on new route are correct.
5. `npm -C frontend-web run typecheck` + `npm -C frontend-web run test:run` pass.

**Codex prompt:**

```
TASK: Re-parent the client-level Reports hub to /clients/[clientSlug]/reports and add a temporary redirect from the old URL.

CONTEXT:
- Previous pass landed /clients/[clientSlug] with 3 tiles, plus server helpers requireAdminUser() and resolveClientBySlug() in frontend-web/src/app/clients/_lib/.
- This pass moves the TOP-LEVEL per-client reports page under the new /clients shell, but leaves all DEEPER routes (e.g., /reports/[clientSlug]/[marketplaceCode]/wbr/*) alone.
- Package manager: npm. Run `npm -C frontend-web run typecheck` and `npm -C frontend-web run test:run` before claiming done.
- Use 307 (temporary) redirects during Pass 1-2 migration. They'll be upgraded to 308 in a separate follow-up PR after the new routes have soaked. DO NOT use permanent: true.

WHAT TO BUILD:
1. New page: frontend-web/src/app/clients/[clientSlug]/reports/page.tsx
   - Server component. First lines:
       const { supabase } = await requireAdminUser();
       const { clientSlug } = await params;
       const client = await resolveClientBySlug(supabase, clientSlug);
   - Renders the SAME component that /reports/[clientSlug]/page.tsx renders today (likely ClientReportsHub). Find that page's render tree and duplicate its server-side logic here verbatim, adjusted only for the new route.
   - If ClientReportsHub reads clientSlug from props, pass the same value through. Do NOT modify the ClientReportsHub component itself.

2. Edit: frontend-web/src/app/clients/_components/ClientOverviewTiles.tsx
   - Change the Reports tile href from `/reports/${clientSlug}` to `/clients/${clientSlug}/reports`.

3. Edit: frontend-web/next.config.(ts|js|mjs) — whichever exists
   - Add a temporary (307) redirect rule: source '/reports/:clientSlug', destination '/clients/:clientSlug/reports', permanent: false.
   - IMPORTANT: this redirect must only match a single slug segment. Deeper paths like /reports/:clientSlug/:marketplaceCode/wbr/anything MUST continue to work unchanged. If the Next.js redirect syntax would swallow deeper paths, use a more specific source pattern (e.g., explicit param matcher `(?!.*/.+)` won't work in Next's path-to-regexp; prefer testing with a real deeper URL) or scope via `has`/`missing` conditions.
   - Verify empirically that /reports/foo/US/wbr still resolves without redirect.

4. Check: frontend-web/src/app/reports/_lib/reportsHeaderState.ts
   - Review how it builds breadcrumbs for the reports hub at the top level. If the header currently reads segment[1]=clientSlug to build the title on /reports/:clientSlug, add a parallel clause for /clients/:clientSlug/reports so the new route has correct breadcrumbs. Keep the existing /reports clause intact for deeper paths.

CONSTRAINTS:
- Do NOT modify ClientReportsHub.tsx or any component it renders.
- Do NOT touch /reports/[clientSlug]/[marketplaceCode]/wbr/** — those stay on their current path.
- Do NOT introduce a new slug column. Slug resolution stays name-based.
- No Supabase migrations.
- Redirects must be 307, not 308.

ACCEPTANCE TESTS:
1. Visiting /clients/[slug]/reports renders the same UI as /reports/[slug] did before.
2. Visiting /reports/[slug] redirects to /clients/[slug]/reports with status 307.
3. Visiting /reports/[slug]/[mkt]/wbr continues to work (no redirect loop, no 404).
4. `npm -C frontend-web run typecheck` passes.
5. `npm -C frontend-web run test:run` passes.

Report files changed, any deviations with reasoning, and typecheck + test:run output.
```

---

### Slice 2b-1 — Extract `ClientTeamWorkspace`

**Goal:** Pure refactor. Move the brand + org-chart UI out of `/command-center/clients/[id]/page.tsx` into a reusable client component. Command Center renders the extracted component. No new routes.

**Compatibility constraints:**
- Must-keep-working: `/command-center/clients/[id]` — pixel-identical, all interactions preserved (brand add/edit, role assignment, role delete).
- Can redirect: nothing.
- Can temporarily break: nothing.

**Migration status:** N/A.

**Files:**
- Create: `frontend-web/src/app/clients/_components/ClientTeamWorkspace.tsx`
- Edit: `frontend-web/src/app/command-center/clients/[clientId]/page.tsx` (replace inline JSX with the new component)

**Acceptance criteria:**
1. `/command-center/clients/[id]` is pixel-identical pre/post.
2. Brand create, role assignment, role delete all still work.
3. No new routes.
4. `npm -C frontend-web run typecheck` + `npm -C frontend-web run test:run` pass.

**Codex prompt:**

```
TASK: Pure refactor. Extract the brand + org-chart UI from the command-center client-detail page into a reusable component. No new routes in this slice.

CONTEXT:
- Current brand + org-chart UI is inline in frontend-web/src/app/command-center/clients/[clientId]/page.tsx (roughly lines 304-1006: brand modal, brands list, per-brand org chart with role assignments, team-member dropdowns, delete actions).
- This slice ONLY extracts the component so it can be reused later. No route changes. Zero behavior change on /command-center/clients/[id] is the acceptance bar.
- Package manager: npm. Run `npm -C frontend-web run typecheck` and `npm -C frontend-web run test:run` before claiming done.

WHAT TO BUILD:
1. New component: frontend-web/src/app/clients/_components/ClientTeamWorkspace.tsx
   - Client component ("use client").
   - Props: `{ clientId: string }`.
   - Contains the full brand + org-chart UI block currently inline in the command-center page: brand list, "add brand" modal, per-brand org chart, role assignments, team-member dropdowns, role-delete/brand-delete actions.
   - Move any hooks, state, and fetch calls that are used only by this block INTO the component. Leave state/hooks that are used by surrounding command-center UI in their current place.
   - Do not introduce new backend APIs. Reuse existing fetch calls as-is.

2. Edit: frontend-web/src/app/command-center/clients/[clientId]/page.tsx
   - Delete the inline brand + org-chart JSX.
   - Replace with <ClientTeamWorkspace clientId={clientId} />.
   - Keep every surrounding piece of the page (header, layout, nav, anything not brand/org-chart) EXACTLY as-is.

PUSH BACK IF:
- You find that brand/org-chart state is tangled with surrounding state in a way that a clean extraction isn't possible. Stop and explain what's entangled before proceeding.

CONSTRAINTS:
- Zero visual or behavior change on /command-center/clients/[id]. Any regression is a blocker.
- Do NOT create any new pages or routes.
- Do NOT modify the supabase schema.
- No new npm dependencies.

ACCEPTANCE TESTS:
1. Load /command-center/clients/[id] before and after — pixel-identical. Describe in the report how you verified this (before/after screenshots preferred; or detailed interactive walkthrough).
2. Brand create, role assign, role delete all work.
3. `npm -C frontend-web run typecheck` passes.
4. `npm -C frontend-web run test:run` passes.

Report files changed, regression-check evidence, and typecheck + test:run output.
```

---

### Slice 2b-2 — Mount `ClientTeamWorkspace` at `/clients/[slug]/team`

**Goal:** Create the new route; update Team tile href. Depends on Slice 2b-1 having landed.

**Compatibility constraints:**
- Must-keep-working: `/command-center/clients/[id]` keeps its own URL for now (no redirect in this slice).
- Can redirect: nothing yet.
- Can temporarily break: nothing.

**Migration status:** N/A.

**Files:**
- Create: `frontend-web/src/app/clients/[clientSlug]/team/page.tsx`
- Edit: `frontend-web/src/app/clients/_components/ClientOverviewTiles.tsx` (Team tile href)

**Acceptance criteria:**
1. `/clients/[slug]/team` renders the same brand + org-chart UI as `/command-center/clients/[id]`, scoped to the right client.
2. Team tile on `/clients/[slug]` navigates to the new route.
3. Brand add/edit, role assignment, role delete all work on the new route.
4. `npm -C frontend-web run typecheck` + `npm -C frontend-web run test:run` pass.

**Codex prompt:**

```
TASK: Mount the extracted ClientTeamWorkspace at /clients/[clientSlug]/team. Update the Team tile href.

CONTEXT:
- Slice 2b-1 already landed ClientTeamWorkspace in frontend-web/src/app/clients/_components/ClientTeamWorkspace.tsx and refactored command-center to render it. Zero behavior change verified on command-center.
- This slice creates the new route and updates the tile href. /command-center/clients/[id] keeps its own URL in this slice (no redirect yet).
- Package manager: npm.

WHAT TO BUILD:
1. New page: frontend-web/src/app/clients/[clientSlug]/team/page.tsx
   - Server component. First lines:
       const { supabase } = await requireAdminUser();
       const { clientSlug } = await params;
       const client = await resolveClientBySlug(supabase, clientSlug);
   - Renders: H1 "<client.name> — Team", then <ClientTeamWorkspace clientId={client.id} />.

2. Edit: frontend-web/src/app/clients/_components/ClientOverviewTiles.tsx
   - Team tile href changes from `/command-center/clients/${clientId}` to `/clients/${clientSlug}/team`.

CONSTRAINTS:
- Do NOT redirect /command-center/clients/[id] to /clients/[slug]/team in this slice.
- Do NOT modify ClientTeamWorkspace itself.
- Do NOT modify the supabase schema.
- No new npm dependencies.

ACCEPTANCE TESTS:
1. /clients/[slug]/team renders the same brand + org-chart UI as /command-center/clients/[id] for the same client.
2. Brand create, role assign, role delete all work on the new route.
3. /command-center/clients/[id] still works identically (no regression).
4. `npm -C frontend-web run typecheck` passes.
5. `npm -C frontend-web run test:run` passes.

Report files changed, a brief walkthrough of the new route, and typecheck + test:run output.
```

---

### Slice 2c — Re-parent Data

**Goal:** `/clients/[slug]/data` renders `ReportApiAccessScreen` with provider-neutral copy. 308 redirects from `/reports/client-data-access/*`.

**Compatibility constraints:**
- Must-keep-working: all Amazon Ads + SP-API OAuth flows (connect, validate, smoke-test) unchanged — backend endpoint URLs untouched.
- Can redirect: `/reports/client-data-access` → `/clients`; `/reports/client-data-access/:slug` → `/clients/:slug/data`.
- Can temporarily break: nothing.

**Migration status:** N/A — connection schema is not touched in this slice. Schema change comes in Slice 3a.

**Files:**
- Create: `frontend-web/src/app/clients/[clientSlug]/data/page.tsx` (uses Slice 1 helpers)
- Edit: `frontend-web/src/app/reports/_components/ReportApiAccessScreen.tsx` (copy tweaks only — no logic changes)
- Edit: `frontend-web/src/app/clients/_components/ClientOverviewTiles.tsx` (Data tile href)
- Edit: `frontend-web/next.config.*` (2 redirects, `permanent: false`)

**Acceptance criteria:**
1. `/clients/[slug]/data` renders identical connection UI to before.
2. Old URLs 307-redirect correctly.
3. OAuth Connect / Validate buttons fire the same backend URLs (verify Network tab).
4. Copy no longer mentions "Windsor" or "WBR Settings" on the Data screen.
5. `npm -C frontend-web run typecheck` + `npm -C frontend-web run test:run` pass.

**Codex prompt:**

```
TASK: Re-parent the client data-access screen to /clients/[clientSlug]/data, strip Windsor-specific copy, add temporary redirects from old URLs.

CONTEXT:
- The current admin-only data-access UI lives at /reports/client-data-access/[clientSlug] and renders <ReportApiAccessScreen/>.
- It handles Amazon Ads + SP-API OAuth connections. The OAuth code and backend endpoints are untouched by this slice; only the frontend mount point and copy change.
- Previous passes landed server helpers requireAdminUser() and resolveClientBySlug() under frontend-web/src/app/clients/_lib/.
- Package manager: npm.
- Use 307 redirects (permanent: false). They'll be upgraded to 308 in a separate follow-up PR.

WHAT TO BUILD:
1. New page: frontend-web/src/app/clients/[clientSlug]/data/page.tsx
   - Server component. First lines:
       const { supabase } = await requireAdminUser();
       const { clientSlug } = await params;
       await resolveClientBySlug(supabase, clientSlug);
   - Render <ReportApiAccessScreen clientSlug={clientSlug} /> (same prop as the old mount).

2. Edit: frontend-web/src/app/reports/_components/ReportApiAccessScreen.tsx
   - Remove or rewrite any copy that assumes Windsor is part of the flow. Specifically hunt for strings like "Windsor", "WBR Settings to enter Windsor account id", "import listings", etc.
   - Replace with provider-neutral framing: this page manages API connections (Amazon Seller API, Amazon Advertising API, plus future providers). Report-specific configuration (including any remaining listing imports) lives on the Reports side.
   - Do NOT delete or alter the OAuth buttons, connection table rendering, or any network calls. Copy changes only.
   - If there are localized strings in a separate file, update them there.

3. Edit: frontend-web/src/app/clients/_components/ClientOverviewTiles.tsx
   - Data tile href changes from `/reports/client-data-access/${clientSlug}` to `/clients/${clientSlug}/data`.

4. Edit: frontend-web/next.config.(ts|js|mjs)
   - Add 307 redirects:
       source: '/reports/client-data-access', destination: '/clients', permanent: false
       source: '/reports/client-data-access/:clientSlug', destination: '/clients/:clientSlug/data', permanent: false
   - Ensure existing /reports redirects (if any) don't conflict.

CONSTRAINTS:
- DO NOT modify the Amazon Ads or SP-API OAuth flow. No changes to authorize URLs, callback handlers, token storage, or connection validation calls.
- DO NOT change the report_api_connections schema.
- Redirects must be 307 (permanent: false), not 308.
- No new npm dependencies.

ACCEPTANCE TESTS:
1. /clients/[slug]/data renders the same connection-management UI that /reports/client-data-access/[slug] rendered before.
2. /reports/client-data-access/[slug] redirects to /clients/[slug]/data with status 307.
3. /reports/client-data-access redirects to /clients with status 307.
4. Connect / Validate buttons still trigger the same backend endpoints (look at Network tab — URLs to backend-core unchanged).
5. Copy no longer mentions "Windsor" or "WBR Settings" on this screen.
6. `npm -C frontend-web run typecheck` passes.
7. `npm -C frontend-web run test:run` passes.

Report files changed, a diff of copy removed vs added on ReportApiAccessScreen, and typecheck + test:run output.
```

---

### Slice 3.5a-region — First-class region support for Amazon Ads

**Goal:** Bring Amazon Ads connections to feature parity with SP-API on region modeling. Backfill existing Ads rows to `region_code='NA'` + add `NOT NULL`; teach OAuth initiate / state / callback + upsert + API helper + nightly sync to carry region end-to-end; map region to the correct Amazon Ads API host (NA / EU / FE). No UI changes in this slice — the region selector on the Ads card arrives with Slice 3.5a.

**Why this slice exists:** Codex hit this during 3.5a-api prep. Today's Ads flow has no region awareness: OAuth state doesn't carry region, `upsert_amazon_ads_connection` doesn't write `region_code`, and the Ads API helper is hardcoded to `advertising-api.amazon.com`. Keying the new validate/disconnect endpoints on `(client, provider, region)` — the symmetric design with SP-API — requires Ads to be region-aware first. Treating `null` as "NA by default" works for Distex today but would block every future EU / FE Ads onboarding and bake in permanent tech debt.

**Compatibility constraints:**
- Must-keep-working: existing NA Ads connections after backfill. Nightly sync still runs against the correct endpoint; validate + any API helper callers continue to work.
- Must-keep-working: Amazon Ads OAuth initiate path. During this slice, `region` is an **optional** param that defaults to `'NA'` server-side — Slice 3.5d will tighten this to required once 3.5a's region selector UI ships.
- Must-keep-working: Slice 3a's partial unique indexes on `report_api_connections`. Backfill updates existing rows in place; no index disruption.
- Must-keep-working: legacy `wbr_amazon_ads_connections` fallback that nightly sync still reads from. Do not touch this table.
- Must-keep-working: SP-API flow is entirely untouched.

**Migration status:** **Applied 2026-04-24 via MCP.** File at `supabase/migrations/20260424170334_amazon_ads_region_backfill.sql`. Backfilled 6 Ads rows to `region_code='NA'`; SP-API's single row was already `'NA'`; `NOT NULL` on `region_code` now enforced. Slice 3a's partial unique indexes are keyed on `external_account_id` / `(client, provider)` and not `region_code`, so their semantics are unchanged.

**Files (predicted, Codex confirms on exploration):**
- `supabase/migrations/<timestamp>_amazon_ads_region_backfill.sql` — Claude owns.
- Backend Amazon Ads OAuth initiate handler — accept optional `region` param (default `'NA'`).
- Backend Amazon Ads OAuth state encoder/decoder — carry `region`.
- Backend Amazon Ads OAuth callback handler — extract `region`, pass to upsert.
- `upsert_amazon_ads_connection(...)` — accept + write `region_code`.
- Amazon Ads API helper — region → host mapping (`NA` → `advertising-api.amazon.com`, `EU` → `advertising-api-eu.amazon.com`, `FE` → `advertising-api-fe.amazon.com`).
- Nightly Ads sync — read `region_code` from each connection row, pass into the helper.
- Any remaining Ads helper callers updated to pass region.
- Frontend: `createAmazonAdsAuthorizationUrl` wrapper — accept optional `region` param (forwarded to backend).

**Acceptance criteria:**
1. Migration applied; all existing `amazon_ads` rows in `report_api_connections` have `region_code='NA'`; `NOT NULL` enforced on the column.
2. Ads OAuth initiate with no `region` → defaults to NA, behaves identically to today. With `region='EU'` or `region='FE'` → routes through the correct Amazon auth flow and persists the right `region_code` on callback.
3. Ads API helper, given a connection with `region_code='EU'`, hits `advertising-api-eu.amazon.com`. Same for FE. NA unchanged.
4. Nightly Ads sync picks the correct endpoint per connection's `region_code`. No regression against existing NA clients.
5. Legacy `wbr_amazon_ads_connections` fallback still functions.
6. Backend tests cover: NA backfill verification, EU/FE initiate round-trip, API helper endpoint selection, nightly sync endpoint selection.
7. `npm -C frontend-web run typecheck` passes. Backend test suite passes.

**Codex prompt:**

```
TASK: Bring Amazon Ads connections to region-awareness parity with SP-API. Teach the Ads OAuth flow + upsert + API helper + nightly sync to carry region end-to-end. Map region to the correct Ads API host (NA / EU / FE). NO UI changes in this slice — the Ads region selector is added by the next UI slice. The backfill + NOT-NULL migration on report_api_connections.region_code has ALREADY been applied by Claude before you start; verify this as step 1.

CONTEXT:
- Repo: /Users/jeff/code/agency-os. Frontend at /frontend-web (npm). Backend at /backend-core (Python; use the existing test runner).
- SP-API is already region-aware and is the reference implementation for this slice. Read the SP-API OAuth initiate / state / callback / helper code paths and mirror that shape for Amazon Ads. When in doubt, match SP-API's choices (error shapes, logging, state encoding).
- Amazon Ads API has three regional hosts:
    NA → https://advertising-api.amazon.com
    EU → https://advertising-api-eu.amazon.com
    FE → https://advertising-api-fe.amazon.com
  (LWA token exchange remains global; only the Ads API host differs.)
- Slice 3a's partial unique indexes on report_api_connections are keyed on external_account_id / (client, provider), NOT region_code. Adding NOT NULL on region_code doesn't affect them.
- Legacy wbr_amazon_ads_connections fallback is still in use by nightly sync as a pre-report_api_connections safety net. DO NOT touch that table or its code path.

STEP 1 — VERIFY MIGRATION PRE-CONDITION (do not skip):
- Query report_api_connections and confirm:
    (a) Zero rows with provider='amazon_ads' AND region_code IS NULL.
    (b) region_code has NOT NULL enforced.
- If either check fails, STOP and report — the migration hasn't landed or is incomplete.

WHAT TO BUILD (after verification passes):

1. Amazon Ads OAuth initiate handler
   - Accept an OPTIONAL `region` param; default to 'NA' when absent.
   - Validate region is one of { 'NA', 'EU', 'FE' }; reject anything else.
   - Pass region through to the OAuth state payload.
   - Backward compat: existing callers with no region continue to work and behave exactly as today (NA).

2. OAuth state encoder/decoder
   - Add `region` to whatever state payload shape Ads uses today. Preserve backward compat for any in-flight OAuth round-trips: if a returning state has no region field (staged before this slice shipped), treat as NA.

3. OAuth callback handler
   - Extract region from state and pass to `upsert_amazon_ads_connection(...)`.

4. upsert_amazon_ads_connection(...)
   - Accept `region_code` as a new param; write it to the row.
   - Upsert key must now consider region (matches the partial-index semantics for multi-region-same-client): prefer explicit (client_id, provider='amazon_ads', external_account_id) when external_account_id is present, else (client_id, provider='amazon_ads', region_code). Match the SP-API upsert's handling.

5. Amazon Ads API helper
   - Replace the hardcoded `https://advertising-api.amazon.com` with a function that maps `region_code` → host using the table above.
   - Every call site that hits the Ads API must now pass the connection's region_code (or resolve it from a loaded connection row).

6. Nightly Ads sync path
   - For each connection being processed, read region_code from the row and pass to the helper so the right host is used.
   - Verify that connection_status filter remains `'connected'` (unchanged). No other behavior change.

7. Any remaining Ads helper callers (one-off scripts, admin endpoints, debug tooling)
   - Audit. Update each to pass region_code.

8. Frontend wrapper: createAmazonAdsAuthorizationUrl
   - Accept an optional `region: 'NA' | 'EU' | 'FE'` param; forward to backend query/body.
   - No UI changes — leave the existing Ads Connect button behavior unchanged (it'll continue to hit the backend with no region, which defaults to NA).

PUSH BACK IF:
- The migration verification in Step 1 fails. Stop and report what you see.
- SP-API's region handling is structurally different enough that "mirror SP-API" doesn't produce a clean symmetric implementation. Describe the difference and propose a path.
- Amazon Ads OAuth (LWA) actually requires region-specific authorization URLs / scopes as well, not just API hosts. If so, report which piece changes per region and wait for confirmation before encoding.
- Token refresh for Ads uses a regional LWA host (rather than a global one). Flag and confirm behavior before coding.
- Legacy wbr_amazon_ads_connections still drives primary ingestion for any active client — in which case region parity there matters too. Describe what you find.

CONSTRAINTS:
- NO UI changes in this slice (other than the tiny wrapper-signature tweak). The Ads Connect button remains region-less from the user's POV until Slice 3.5a lands the selector.
- DO NOT touch SP-API code paths unless a shared utility is being generalized (in which case describe the generalization before making it).
- DO NOT touch wbr_amazon_ads_connections or its fallback path.
- NO schema changes — Claude already landed the migration. If you believe further schema changes are needed, stop and report.
- Admin gating, logging, error envelope — match existing Ads endpoints' conventions.

ACCEPTANCE TESTS YOU MUST VERIFY BEFORE CLAIMING DONE:
1. Step 1 migration verification passes against the live DB.
2. Ads OAuth initiate with no region: works exactly as today (NA round-trip, row persisted with region_code='NA').
3. Ads OAuth initiate with region='EU': full round-trip persists a row with region_code='EU'. (Testable by hand against a test client + EU Ads sandbox if available; otherwise document the code path end-to-end with screenshots / logs.)
4. Ads API helper, given region_code='EU', hits advertising-api-eu.amazon.com. Confirmed via unit test or request capture.
5. Nightly Ads sync over existing NA connections produces identical results to pre-slice baseline (no regression). Walk through one run against a known-good client (e.g., Distex) and compare row counts / durations.
6. Legacy wbr_amazon_ads_connections-backed clients still work.
7. `npm -C frontend-web run typecheck` passes.
8. Backend test suite passes.

Report: files changed, pre-condition verification output, walkthrough of the NA-unchanged test + the EU initiate test, test suite output, and anything that surprised you.
```

---

### Slice 3.5a-api — Disconnect + Ads validate endpoints (backend prep)

**Goal:** Add the three admin endpoints Slice 3.5a needs but that don't exist yet: Amazon Ads validate, Amazon Ads disconnect, SP-API disconnect. Plus matching frontend API client wrappers in `reportApiAccessApi.ts`. Disconnect is **soft-revoke**: `connection_status='revoked'`, tokens nulled, row preserved. No UI changes in this slice.

**Why this is split from 3.5a:** the UI slice hit Codex pushback because `reportApiAccessApi.ts` has `listAmazonAdsApiAccess`, `listSpApiConnections`, both `create*AuthorizationUrl`, and `validateSpApiConnection` — but no Ads validate, no disconnect for either provider. Rather than widen 3.5a, isolate the backend work in a reviewable chunk.

**Compatibility constraints:**
- Must-keep-working: existing Connect flows (Ads + SP-API OAuth initiate → callback → token storage).
- Must-keep-working: existing SP-API validate endpoint — do NOT refactor its shape; the new endpoints mirror it.
- Must-keep-working: nightly sync jobs. Soft-revoke relies on those jobs skipping rows where `connection_status='revoked'`. If they don't already, we need to handle that (see pushback clause).
- Must-keep-working: Slice 3a's partial unique indexes on `report_api_connections`. Soft-revoke preserves the row, so reconnect upserts on the same key without collision.
- Can temporarily break: nothing.

**Migration status:** Likely none. `report_api_connections.connection_status` must accept the value `'revoked'`. If a CHECK constraint or enum blocks that value, Codex stops and Claude lands the migration.

**Files (predicted, Codex confirms on exploration):**
- Edit: backend admin router under `backend-core/app/...` — three new endpoints alongside the existing SP-API validate + connect handlers.
- Edit: backend service layer for Amazon Ads (validate impl) and both providers (disconnect impl).
- Edit: `frontend-web/src/app/reports/_lib/reportApiAccessApi.ts` — three new wrappers + TypeScript types.
- New: backend tests for the three endpoints.

**Acceptance criteria:**
1. `POST /admin/reports/api-access/amazon-ads/validate` with `{ client_id, region }` calls Amazon Ads `/v2/profiles`, updates `connection_status` + `last_validated_at`, returns a shape mirroring the existing SP-API validate response.
2. `POST /admin/reports/api-access/amazon-ads/disconnect` with `{ client_id, region }` sets `connection_status='revoked'` and nulls refresh + access tokens across all matching rows. Idempotent.
3. `POST /admin/reports/api-access/amazon-spapi/disconnect` same shape + semantics for SP-API.
4. All three admin-gated per existing pattern.
5. Frontend wrappers `validateAmazonAdsConnection`, `disconnectAmazonAdsConnection`, `disconnectSpApiConnection` exist with TS types matching the existing wrappers' style.
6. Soft-revoke verified: post-disconnect DB inspection shows row intact with null tokens; re-Connect via OAuth flips the row back to `connected` with fresh tokens (no partial-index collision).
7. Backend tests cover happy path + error path + idempotent re-call for each endpoint.
8. Backend tests pass. `npm -C frontend-web run typecheck` passes.

**Codex prompt:**

```
TASK: Backend + API wrapper prep for Slice 3.5a. Add three missing admin endpoints — Amazon Ads validate, Amazon Ads disconnect, SP-API disconnect — plus matching frontend API client wrappers in reportApiAccessApi.ts. Disconnect is soft-revoke (update connection_status + null tokens, preserve row). This slice has NO UI changes.

CONTEXT:
- Repo: /Users/jeff/code/agency-os. Frontend at /frontend-web (npm). Backend at /backend-core (Python; find and use the existing test runner).
- Slice 3.5a-region has already shipped: Amazon Ads is now region-aware end-to-end (OAuth initiate/state/callback, upsert, API helper, nightly sync). Use the region-aware helpers: normalize_ads_region_code(), get_ads_api_base_url(region_code), and the Ads helper pattern from amazon_ads_auth.py. All live Ads rows have region_code='NA' and NOT NULL is enforced. The partial unique index on null-external-account rows is now (client_id, provider, region_code), so multi-region Ads rows coexist cleanly.
- Existing admin endpoints in the API-access space: POST /admin/reports/api-access/amazon-spapi/validate (takes client_id + region), Amazon Ads + SP-API OAuth connect/callback paths, plus domain endpoints like compare-business and import-listings. Find them; match their admin-gating pattern, error shape, and logging style.
- Existing frontend API client: frontend-web/src/app/reports/_lib/reportApiAccessApi.ts. Today it has createAmazonAdsAuthorizationUrl (now region-aware), createSpApiAuthorizationUrl, validateSpApiConnection, listAmazonAdsApiAccess, listSpApiConnections. Add the new wrappers alongside these, matching their fetch + error-handling pattern.
- report_api_connections: one row per (client, provider, external_account_id) when external_account_id is present, else one per (client, provider, region_code). This slice scopes validate/disconnect to (client_id, provider, region) — if multiple rows match that tuple (multi-account same region), operate on ALL of them. Connection-id-scoped variants are deferred to Slice 3b.
- Do NOT run Supabase migrations. If report_api_connections.connection_status has a CHECK / enum constraint blocking the value 'revoked', STOP and report — Claude owns migrations.

WHAT TO BUILD:

1. Backend endpoint: POST /admin/reports/api-access/amazon-ads/validate
   - Body: { client_id: uuid, region: 'NA' | 'EU' | 'FE' }
   - Loads the connection row(s) for (client_id, provider='amazon_ads', region_code=region). Calls Amazon Ads /v2/profiles on the region-correct host (use get_ads_api_base_url(region) from amazon_ads_auth.py) with the stored access token — refresh via the existing Ads refresh path if needed.
   - On success: update connection_status='connected', last_validated_at=now(), clear last_error. Return { status: 'connected', last_validated_at, profile_count }.
   - On failure: update connection_status='error', last_error=<msg>. Return { status: 'error', error: <msg> }. HTTP status and shape mirror the existing SP-API validate endpoint — inspect and align.
   - Admin-gated via the same pattern used by SP-API validate.

2. Backend endpoint: POST /admin/reports/api-access/amazon-ads/disconnect
   - Body: { client_id: uuid, region: 'NA' | 'EU' | 'FE' }
   - For each matching row (keyed by client_id + provider + region_code): set connection_status='revoked', null the refresh_token (and any cached access-token / token metadata fields — follow wherever the connect flow writes them). DO NOT delete rows.
   - Return { status: 'revoked', affected: <n> }.
   - Idempotent: calling against an already-revoked row returns 200 with affected=0.

3. Backend endpoint: POST /admin/reports/api-access/amazon-spapi/disconnect
   - Same shape + semantics as the Ads disconnect, for provider='amazon_spapi'.

4. Frontend wrappers in reportApiAccessApi.ts:
   - validateAmazonAdsConnection({ clientId, region }): Promise<ValidateResult>  — shape mirrors validateSpApiConnection.
   - disconnectAmazonAdsConnection({ clientId, region }): Promise<{ status: 'revoked'; affected: number }>
   - disconnectSpApiConnection({ clientId, region }): Promise<{ status: 'revoked'; affected: number }>
   - Match existing fetch + error-handling convention of sibling functions.

5. Backend tests (in the existing backend suite — find the location):
   - Ads validate: happy path; error path (e.g., Amazon returns 401 → row flips to connection_status='error'); validate against a row that was previously disconnected/revoked should surface a clean error rather than crash; correct regional host is used (spy on the API base URL resolved for NA vs EU).
   - Ads disconnect: happy path (rows flip to revoked, tokens null); idempotent re-call (affected=0); nonexistent (client, provider, region) tuple is graceful — 200 with affected=0 OR 404, match existing conventions.
   - SP-API disconnect: happy path + idempotent.

PUSH BACK IF:
- report_api_connections.connection_status has a CHECK / enum constraint blocking 'revoked'. STOP, report the constraint, wait for Claude to land a migration.
- Tokens for Ads / SP-API are stored in a separate table (tokens / credentials) rather than on report_api_connections. Follow wherever the existing connect flow writes them and null them there consistently — describe what you find before coding if the separation is non-obvious.
- Nightly sync jobs read from report_api_connections WITHOUT filtering out connection_status='revoked'. Soft-revoking an active client would break those jobs. If you find this, stop and describe so we decide (include the filter in this slice, or stage separately). (From 3.5a-region review we know nightly Ads sync already filters to 'connected', but double-check for other sync paths touched here.)
- The existing SP-API validate endpoint's shape differs materially from what's specified above, such that mirroring it would create inconsistency. Describe the existing shape and propose alignment.

CONSTRAINTS:
- NO UI changes. NO schema migrations. NO new npm packages. No new Python deps unless there's an existing SDK already in the repo you need to wire up.
- Soft-revoke semantics: preserve the row, null tokens, flip status. Do NOT hard-delete.
- Admin gating via existing pattern — do not reinvent.
- Endpoint shapes mirror the existing SP-API validate endpoint for consistency.
- Use the region-aware helpers shipped in 3.5a-region — do NOT hardcode Amazon Ads API hosts.

ACCEPTANCE TESTS YOU MUST VERIFY BEFORE CLAIMING DONE:
1. Three endpoints respond correctly to curl / httpie against a local backend. Walk through one Ads validate, one Ads disconnect, one SP-API disconnect and paste request + response.
2. After disconnect, the row still exists with connection_status='revoked' and tokens nulled — verify by direct DB query against report_api_connections.
3. After disconnect, a subsequent Connect OAuth round-trip succeeds and the row is back to connection_status='connected' with fresh tokens — i.e., no partial-index collision.
4. Frontend wrappers typecheck and are importable.
5. Backend tests pass. `npm -C frontend-web run typecheck` passes. `npm -C frontend-web run test:run` passes.

Report files changed, any deviations from spec with reasoning, test output, and the local-backend walkthrough from Acceptance Test 1.
```

---

### Slice 3.5a — Region blocks + Connections UI

**Goal:** First UI slice of Pass 3.5. Replaces `/clients/[slug]/data`'s top-level content with the Region → (Connections + Marketplaces) IA. Ships the three `RegionBlock`s (NA / EU / FE) and the `ConnectionsStrip` inside each (Ads + SP-API cards, state-first per-state treatment, region-scoped Connect / Validate / Disconnect calling 3.5a-api wrappers). Marketplace cards + their Backfill / Nightly-sync actions arrive in 3.5b / 3.5c. Empty regions render as a collapsed "+ Connect" CTA card. Legacy `ReportApiAccessScreen` moves into a closed-by-default `<details>` disclosure at the bottom — kept as a rollback safety net and multi-account overflow ("+N more") path until Slice 3.5d removes it.

**Compatibility constraints:**
- Must-keep-working: Ads + SP-API OAuth round-trips (Connect → Amazon → callback → Connected state) across all three regions.
- Must-keep-working: 307 redirect from `/reports/client-data-access/:slug` (Slice 2c) lands on the new layout.
- Must-keep-working: Slice 2d read-only per-WBR-profile status dashboard — in this slice it renders unchanged below the RegionBlocks. Slices 3.5b and 3.5c move its content into marketplace cards inside each region block; 3.5d cleans up.
- Must-keep-working: nightly sync jobs (consume `report_api_connections`; UI-agnostic).
- Must-keep-working: validate + disconnect endpoints shipped by 3.5a-api.
- Depends on: 3.5a-region (region-aware Ads OAuth) + 3.5a-api (validate + disconnect endpoints + frontend wrappers). Both shipped.

**Migration status:** N/A — no schema changes in this slice.

**Files:**
- Create: `frontend-web/src/app/clients/[clientSlug]/data/_components/RegionBlock.tsx` (empty-state + active-state variants, region label + subhead)
- Create: `frontend-web/src/app/clients/[clientSlug]/data/_components/ConnectionsStrip.tsx` (holds two `ProviderConnectionCard`s for a region)
- Create: `frontend-web/src/app/clients/[clientSlug]/data/_components/ProviderConnectionCard.tsx` (state-first card keyed off connection state)
- Create: orchestrator component (name Codex's choice — match Slice 2d's data-fetch pattern) that loads per-region connection state for the client and owns Connect / Validate / Disconnect handlers
- Edit: `frontend-web/src/app/clients/[clientSlug]/data/page.tsx` — replace top-level content with RegionBlocks stack → Slice 2d dashboard (unchanged) → `<details>` disclosure wrapping `<ReportApiAccessScreen/>`

**Design direction:**

Aesthetic: **"confident utility"** — opinionated clarity for an internal admin tool. First-visit obviousness is the primary design metric.

**Region subheads (copy):**
- NA: "Unlocks CA, US, MX"
- EU: "Unlocks UK, DE, FR, IT, ES, NL, SE, PL, TR, BE, EG, SA, ZA, AE"
- FE: "Unlocks AU, JP, SG, IN"

**RegionBlock container:**
- Region label prominent but not shouty (e.g., `NA`, not `North America` — match Amazon's own convention) with the subhead right underneath.
- Two variants, determined by whether any connection exists for that region:
  - *Empty:* collapsed low-height card with two outline `+ Connect Amazon Ads` / `+ Connect SP-API` CTAs and one-line helper copy ("No connections in `<region>` yet. Authorize to unlock `<markets>`."). Default for FE on most clients.
  - *Active:* expanded card containing `ConnectionsStrip`. A reserved space below the strip holds future marketplace cards (populated by 3.5b). Placeholder comment only — no visible "Marketplaces" label until 3.5b ships.

**ConnectionsStrip:** two cards side-by-side on `md+`, stacked on `sm`. Order: Amazon Ads, then SP-API. Region inherited from parent — cards don't render a region chip (avoids redundancy with the RegionBlock label).

**ProviderConnectionCard:** state-first; dominant visual cue (left accent bar / border / header band) communicates state at a glance. Never pill-only.
- *Not connected:* neutral/muted; large primary `Connect` button dominates; one-line helper copy.
- *Connected:* positive accent (repo's existing success token — not a saturated green); account identifier (seller id / Ads profile id) prominent; last-validated timestamp; secondary `Validate` + `Disconnect`.
- *Error:* amber accent; error reason visible; primary action `Reconnect`.
- *Revoked:* red accent; "Access revoked at Amazon" copy; primary action `Reconnect`.

**Other design rules:**
- Primary-action dominance on disconnected cards; status-as-hero on connected cards.
- Provider identity via a small accent only (thin left border or icon tint). Amazon orange (`#FF9900`) for Ads; calm contrasting tone (deep teal or slate) for SP-API. No Amazon logos.
- Reuse existing repo tokens + type scale. No new fonts or tokens.
- ~200ms crossfade on state transitions. No page-load animations.
- Copy: direct, imperative. Error messages name problem + fix.
- Accessibility: state distinguishable without hue (border weight, icon, shape). Verify with grayscale devtools rendering.
- Empty RegionBlocks should be visually quiet — low-contrast, minimal height.

**Legacy disclosure:** `<details>` at page bottom, summary "Advanced connection details (legacy)", closed by default. Contents: `<ReportApiAccessScreen clientSlug=.../>` rendered untouched.

**EU / FE OAuth caveat (open item from 3.5a-region):** LWA authorization host (`www.amazon.com/ap/oa`) + token refresh host (`api.amazon.com/auth/o2/token`) are still global. A live EU/FE OAuth round-trip has not been validated. For this slice render all three RegionBlocks as normal — if EU or FE Connect surfaces an Amazon-side error we'll diagnose separately. Do not gate EU/FE as "coming soon" unless a specific UI regression appears in the live flow.

**Acceptance criteria:**
1. `/clients/[slug]/data` renders three `RegionBlock`s (NA, EU, FE) at the top. Slice 2d dashboard renders below, unchanged. Closed-by-default `<details>` disclosure wrapping `<ReportApiAccessScreen/>` at the bottom.
2. Empty region: collapsed card with two `+ Connect` CTAs + subhead naming unlocked marketplaces.
3. Active region: ConnectionsStrip visible with Ads + SP-API cards reflecting real state from `report_api_connections`.
4. Connect in a region → OAuth round-trip → on return, card reads Connected with account id + last-validated; row in DB has `region_code` matching the region block.
5. Validate on a connected card → calls `validateAmazonAdsConnection` / `validateSpApiConnection` from 3.5a-api → updates last-validated or surfaces error inline.
6. Disconnect on a connected card → confirm step → calls `disconnectAmazonAdsConnection` / `disconnectSpApiConnection` from 3.5a-api → card returns to Not connected; row in DB has `connection_status='revoked'` with `refresh_token=null`.
7. Reconnect-after-revoke: connecting again in the same region upserts the existing row back to `connected` with no partial-index collision (3.5a-region's follow-up migration enables this).
8. Error and Revoked states render with distinct visual treatments per design direction.
9. No Windsor card / copy / icon inside any RegionBlock.
10. Slice 2d dashboard unchanged below. ReportApiAccessScreen fully functional when the disclosure is opened.
11. Grayscale rendering check passes — states distinguishable without hue.
12. `npm -C frontend-web run typecheck` and `npm -C frontend-web run test:run` pass.

**Codex prompt:**

```
TASK: Rebuild /clients/[clientSlug]/data around the Region → (Connections + Marketplaces) IA. In this slice ship the three RegionBlocks (NA / EU / FE) and the ConnectionsStrip inside each (Ads + SP-API cards, state-first per-state visual treatment, region-scoped Connect / Validate / Disconnect). Marketplace-level content arrives in Slices 3.5b (Backfill) and 3.5c (Nightly sync). Slice 2d's read-only dashboard stays BELOW the new blocks, untouched. Legacy ReportApiAccessScreen moves into a closed-by-default <details> disclosure at the bottom of the page.

CONTEXT:
- Repo: Next.js App Router at /Users/jeff/code/agency-os/frontend-web. Package manager: npm. Run `npm -C frontend-web run typecheck` and `npm -C frontend-web run test:run` before claiming done.
- /clients/[clientSlug]/data/page.tsx is admin-only (requireAdminUser() + resolveClientBySlug() from frontend-web/src/app/clients/_lib/). It currently renders: (1) Slice 2d read-only status dashboard at the top, (2) <ReportApiAccessScreen clientSlug=...> below. This slice puts three RegionBlocks at the TOP of the page, moves 2d dashboard BELOW them (unchanged), and moves ReportApiAccessScreen into a closed-by-default <details> disclosure at the very bottom.
- Slice 3.5a-region (prereq, SHIPPED): Amazon Ads is region-aware end-to-end. Frontend wrapper `createAmazonAdsAuthorizationUrl(token, profileId, returnPath, region?)` accepts an optional region param — use it.
- Slice 3.5a-api (prereq, SHIPPED): these wrappers live in `reportApiAccessApi.ts` — use them, do NOT add new backend endpoints:
    validateSpApiConnection(token, clientId, region)
    validateAmazonAdsConnection(token, { clientId, region })
    disconnectSpApiConnection(token, { clientId, region })
    disconnectAmazonAdsConnection(token, { clientId, region })
- report_api_connections: two partial unique indexes — one for `external_account_id IS NOT NULL`, one for `(client, provider, region_code) WHERE external_account_id IS NULL`. For this slice render a SINGLE card per (region, provider) representing the primary connection in that region (most recently validated). If additional rows exist for the same tuple, show a small "+N more" footer link pointing to the Advanced disclosure. Multi-account management is deferred to Slice 3b.

LAYOUT (top-to-bottom on /clients/[slug]/data):

1. Three stacked RegionBlocks, order: NA → EU → FE.

   Each RegionBlock shows:
   - Region label (`NA` / `EU` / `FE`) — prominent but not shouty.
   - Subhead naming the marketplaces that region unlocks:
       NA: "Unlocks CA, US, MX"
       EU: "Unlocks UK, DE, FR, IT, ES, NL, SE, PL, TR, BE, EG, SA, ZA, AE"
       FE: "Unlocks AU, JP, SG, IN"
   - Two visual variants based on whether any connection exists for that region:
     a) EMPTY (zero connections): collapsed, low-height card. Two outline CTAs `+ Connect Amazon Ads` / `+ Connect SP-API`. One-line copy ("No connections in <Region> yet. Authorize to unlock <markets>.").
     b) ACTIVE (>= 1 connection): expanded card containing ConnectionsStrip. Reserve space AFTER the strip for future marketplace cards (3.5b) — an empty div or HTML comment is enough; no visible "Marketplaces" label in this slice.

2. Slice 2d read-only status dashboard — UNCHANGED, renders below the three RegionBlocks.

3. <details> disclosure at the very bottom:
   - summary text: "Advanced connection details (legacy)"
   - Closed by default
   - Contents: <ReportApiAccessScreen clientSlug={...}/> — rendered exactly as before. DO NOT modify it.

WHAT TO BUILD:

1. Orchestrator component (match Slice 2d's data-fetch pattern — server component with pre-fetched data, OR client component that fetches on mount).
   - Loads connection state for this client across all three regions and both providers.
   - Owns Connect / Validate / Disconnect handlers:
     - Connect → calls createAmazonAdsAuthorizationUrl(..., region) or createSpApiAuthorizationUrl(..., region), follows the existing redirect pattern.
     - Validate → calls the right wrapper from 3.5a-api, refreshes local state.
     - Disconnect → confirm step (browser `confirm()` is acceptable) + calls the right 3.5a-api wrapper, refreshes local state.
   - Passes per-region + per-provider state down to each RegionBlock.

2. RegionBlock.tsx
   - Props: `{ region: 'NA' | 'EU' | 'FE'; adsConnection?: ConnectionState; spApiConnection?: ConnectionState; onConnect; onValidate; onDisconnect; }`
   - Renders EMPTY or ACTIVE variant per the layout spec above.

3. ConnectionsStrip.tsx
   - Two <ProviderConnectionCard/> side-by-side on md+, stacked on sm. Order: Ads first, SP-API second.
   - Passes through state + handlers.

4. ProviderConnectionCard.tsx
   - Pure presentation, keyed off `state`: 'not_connected' | 'connected' | 'error' | 'revoked'.
   - Approximate props:
       {
         provider: 'amazon-ads' | 'sp-api';
         region: 'NA' | 'EU' | 'FE';
         state: 'not_connected' | 'connected' | 'error' | 'revoked';
         accountId?: string;
         lastValidatedAt?: Date;
         errorMessage?: string;
         additionalAccountCount?: number;   // ">+N more" footer linking to the Advanced disclosure
         onConnect(): void;
         onValidate(): void;
         onDisconnect(): void;
       }
   - Region lives at the RegionBlock level — do NOT render a region chip on the card itself.

5. Edit page.tsx — replace the current top-level content with: orchestrator → 3 RegionBlocks → 2d dashboard (unchanged) → <details> disclosure wrapping <ReportApiAccessScreen/>.

DESIGN DIRECTION (full spec in docs/client_hub_ia_plan.md under "Slice 3.5a — Design direction"; follow it precisely):

- Aesthetic: "confident utility." Opinionated clarity, state-first visual hierarchy, no marketing fluff.
- State-first cards. Dominant visual cue (left accent bar / border color / header band) communicates state at a glance. NOT a pill-only indicator.
  - Not connected: neutral/muted; large primary Connect button dominates; one-line helper copy.
  - Connected: positive accent (repo's existing success token); account id + last-validated prominent; secondary Validate + Disconnect actions.
  - Error: amber accent; error reason visible; primary action Reconnect.
  - Revoked: red accent; "Access revoked at Amazon" copy; primary action Reconnect.
- Primary-action dominance on disconnected cards. Status-as-hero on connected.
- Provider identity via a SMALL accent only (thin left border or icon tint). Amazon orange (#FF9900) for Ads, calm contrasting tone (deep teal or slate) for SP-API. NO Amazon logos.
- Reuse existing repo tokens + type scale — NO new fonts or tokens.
- Two cards side-by-side on md+, stacked on sm. Generous vertical padding.
- Motion: restrained — ~200ms state crossfade. No page-load animations.
- Copy voice: direct, imperative. Error messages name problem + fix.
- Accessibility: state distinguishable without hue. Verify with devtools grayscale rendering.
- Empty RegionBlocks should be visually quiet — low-contrast, minimal height.

EU / FE OAuth caveat:
- LWA authorization and token refresh hosts are still global (open item from 3.5a-region). EU + FE Connect buttons fire the same OAuth endpoints as NA. A live EU/FE round-trip is not yet validated. Render all three RegionBlocks as normal — if EU or FE Connect surfaces an Amazon-side error we'll diagnose separately. Do NOT gate EU/FE as "coming soon" unless you find a specific UI regression in the live flow.

PUSH BACK IF:
- Any of the 3.5a-api wrappers (validateAmazonAdsConnection, disconnectAmazonAdsConnection, disconnectSpApiConnection) are missing from reportApiAccessApi.ts. Stop and report.
- The OAuth callback for Ads or SP-API redirects the user to a route other than /clients/[slug]/data in a way that blocks the Connected-on-return UX. Describe what you find.
- Slice 2d's dashboard renders per-connection status in a way that visibly duplicates the new ProviderConnectionCards enough to confuse users during the transition. Propose hiding or demoting that subsection and WAIT for confirmation — do not delete in this slice.

CONSTRAINTS:
- NO new backend endpoints; NO schema changes.
- Do NOT modify ReportApiAccessScreen or Slice 2d dashboard.
- NO new fonts, design tokens, or npm packages.
- requireAdminUser() is applied at the page level — do not re-implement inside components.
- Do NOT hardcode Amazon Ads API hosts — region-aware helpers already exist from 3.5a-region.

ACCEPTANCE TESTS YOU MUST VERIFY:
1. /clients/[slug]/data renders three RegionBlocks (NA, EU, FE) at the top. 2d dashboard below, unchanged. Closed <details> disclosure wrapping ReportApiAccessScreen at the bottom.
2. With zero connections: all three blocks are EMPTY variant; both `+ Connect` CTAs visible per region.
3. Connect Amazon Ads in the NA block → OAuth round-trip → NA block flips to ACTIVE with the Ads card Connected (account id + last-validated); SP-API still empty CTA; EU + FE unchanged. Row in DB has region_code='NA'.
4. Validate on a connected card → last-validated updates or error surfaces inline.
5. Disconnect on a connected card → confirm → card returns to Not connected; row has connection_status='revoked' with refresh_token null.
6. Reconnect in the same region after disconnect → row upserts back to 'connected' (no partial-index collision).
7. Grayscale devtools render check passes.
8. No Windsor references in any RegionBlock.
9. `npm -C frontend-web run typecheck` passes.
10. `npm -C frontend-web run test:run` passes.

Report: files changed, before/after screenshots of /clients/[slug]/data (empty, partially connected, fully connected), any deviations from spec with reasoning, and typecheck + test:run output.
```

---

### Slice 3.5b — Marketplace cards + per-domain Backfill

**Goal:** Inside each ACTIVE `RegionBlock`, render one `MarketplaceCard` per WBR profile whose `marketplace_code` belongs to that region. Each card exposes per-domain backfill actions (Business, Ads, Listings, Inventory, Returns) with "Last backfilled" status per domain and a `Run backfill` date-range picker. Wires to existing admin endpoints where they exist; the rest render as disabled placeholders. Connects directly to Slice 3.5a's reserved post-ConnectionsStrip slot. Empty regions (no connections) keep their collapsed `+ Connect` variant unchanged. No new backend endpoints.

**Compatibility constraints:**
- Must-keep-working: existing admin endpoints at current shapes — `POST /admin/reports/api-access/amazon-spapi/compare-business` and `POST /admin/reports/api-access/amazon-spapi/import-listings` (plus their Next.js proxy routes under `/api/admin/spapi-*`).
- Must-keep-working: Slice 3.5a RegionBlocks + ConnectionsStrip + ProviderConnectionCards — extended, not replaced.
- Must-keep-working: Slice 2d read-only dashboard below — unchanged.
- Must-keep-working: nightly sync (this slice doesn't touch it).
- Depends on: 3.5a shipped (✓).

**Migration status:** N/A — no schema changes.

**Files:**
- Create: `frontend-web/src/app/clients/_components/data-connections/MarketplaceCard.tsx`
- Create: `frontend-web/src/app/clients/_components/data-connections/DomainBackfillRow.tsx`
- Create: `frontend-web/src/app/clients/_components/data-connections/BackfillDateRangeDialog.tsx` (or inline picker inside the row — Codex's choice)
- Edit: `frontend-web/src/app/clients/_components/data-connections/RegionBlock.tsx` — inject `MarketplaceCard` list into the reserved post-strip slot
- Edit: `frontend-web/src/app/clients/_components/data-connections/ClientDataConnectionsOrchestrator.tsx` — fetch WBR profiles for this client + per-profile backfill coverage; handle backfill trigger + in-flight state
- Edit: `frontend-web/src/app/reports/_lib/reportApiAccessApi.ts` — add wrappers `runSpApiBusinessCompareBackfill`, `runSpApiListingsImport` (reusing existing `/api/admin/spapi-compare-business` + `/api/admin/spapi-import-listings` proxy routes — do NOT hit backend directly; proxy routes already handle admin auth)

**Per-domain wiring:**

| Domain    | Status this slice | Endpoint / behavior |
|-----------|------------------|---------------------|
| Business  | Live backfill    | `POST /admin/reports/api-access/amazon-spapi/compare-business` via proxy `/api/admin/spapi-compare-business`. Note: this writes to `wbr_business_asin_daily__compare`, NOT the production `wbr_business_asin_daily` table. That's correct for Pass 3's A/B-compare era; Slice 3g cutover flips production to SP-API. Last-backfilled reflects compare-table coverage. Copy below the button: "A/B compare against Windsor. Production data still flows through nightly sync." |
| Ads       | Read-only        | "Managed by nightly sync" — no direct backfill endpoint exists (open item in plan). No button. |
| Listings  | Live backfill    | `POST /admin/reports/api-access/amazon-spapi/import-listings` via proxy `/api/admin/spapi-import-listings`. Writes production via Slice 3f. Last-backfilled reflects `wbr_listing_import_batches.finished_at` (or equivalent). |
| Inventory | Disabled         | "Coming soon — Slice 3f." No button. |
| Returns   | Disabled         | "Coming soon — Slice 3f." No button. |

**Gating:**
- If the region's SP-API card is NOT in `connected` state, Business + Listings backfill rows render disabled with inline copy "Connect SP-API to enable".
- Ads / Inventory / Returns rows always render as described above regardless of connection state.
- Connection state is already available to the orchestrator — pass the region's `spApiConnection.state` down to each MarketplaceCard.

**Last-backfilled data source:**
- Derive from fact tables' MAX date per (profile_id, domain). Reuse the query shape Slice 2d's `ClientDataStatusDashboard` already uses — don't duplicate.
- Pattern: orchestrator fetches all needed coverage data once on mount, passes per-marketplace slices to each MarketplaceCard.
- If "Never" (no rows), show literally "Never".

**Date-range picker:**
- Default window: **L3D — 3 days of data ending 3 days ago** (UTC). So `date_to = today - 3`, `date_from = today - 5` (inclusive, yielding 3 days: today-5, today-4, today-3). Yesterday is too fresh — Amazon's validation window means recent days often come back empty, and our Distex empty-{} symptom has been observed even further back during investigation.
- No hard min-date limit.
- User can override both inputs to diagnose older ranges or widen the window.
- Submit closes the picker and fires the backfill. UI shows in-flight (spinner + "Running backfill…") with button disabled. On completion: refresh Last-backfilled and show brief success toast. On error: show error message inline below the row with the failing payload summary if possible.

**Blocking-HTTP caveat:**
- `compare-business` blocks the HTTP connection for the duration of its run (per Slice 3d's operational note). 7-day default keeps this to a reasonable wait.
- If a request times out at the proxy layer (Render timeout varies), surface that clearly: "Backfill timed out — try a smaller date range".

**Design direction:**

- **Nested visual hierarchy.** MarketplaceCards feel subordinate to their parent RegionBlock — slightly lower contrast, indented or shadowed inset, smaller headers. Carry over the "confident utility" aesthetic: state-forward, no marketing fluff.
- **MarketplaceCard header:** country code (e.g., `CA`) as prominent label, plus the profile `display_name` as secondary, plus a small tag like `Marketplace A2EUQ1WTGCTBG2` for disambiguation. Optional flag emoji only if the repo already uses them elsewhere — don't invent.
- **DomainBackfillRow:** tight 3-column layout — domain name left, last-backfilled middle, action right. Disabled rows grey out the entire row (not just the button) and show the reason inline.
- **Date-range picker:** keep it small. An inline popover with two date inputs (from / to) and a Run button. No calendar widget unless the repo already uses `react-day-picker` or similar. If it does, reuse.
- **In-flight state:** button becomes spinner + "Running…"; other rows on the same card remain actionable (independent).
- **Success feedback:** brief inline success state on the row ("Backfilled 7 days ✓"), auto-dismiss after a few seconds, then re-render with new Last-backfilled.
- **Failure feedback:** inline error below the row with short message + "Retry" action (same date range).
- Accessibility: disabled rows still readable, reasons explicit. Button labels describe what happens ("Run backfill", not "Go").

**Acceptance criteria:**
1. Active RegionBlocks now show a `MarketplaceCard` per WBR profile in that region, below the ConnectionsStrip.
2. Each card has 5 DomainBackfillRows: Business, Ads, Listings, Inventory, Returns (in this order).
3. Business row active when SP-API is Connected in that region, shows Last-backfilled from the compare table, has Run-backfill + date picker, below-button copy explains compare vs production. Disabled with "Connect SP-API" copy otherwise.
4. Listings row same shape, writes production via import-listings.
5. Ads row always shows "Managed by nightly sync" with no action button.
6. Inventory + Returns rows always disabled with "Coming soon — Slice 3f" copy.
7. Running a backfill shows in-flight state, handles success / error / timeout cases with clear messaging, refreshes Last-backfilled on success.
8. Empty regions (EMPTY variant from 3.5a) unchanged.
9. Active regions with connections but zero WBR profiles for that region: placeholder copy "No marketplaces in <Region> yet. Add a WBR profile to start pulling data." + link to wherever profiles are created (or a note to create via Command Center until Pass 4 ships).
10. Slice 2d dashboard, Slice 3.5a RegionBlocks + ConnectionsStrip, and the `<details>` legacy disclosure all render unchanged aside from the Marketplace cards being injected into their reserved slot.
11. `npm -C frontend-web run typecheck` passes.
12. `npm -C frontend-web run test:run` passes.

**Codex prompt:** (paste below)

---

## Pass 3, 3.5, 3.6, and 4 — remaining planning

Pass 3 (rebuild `/data` against Option B schema + SP-API direct migration) is a multi-slice track; slices 3a, 3c, 3d, and 3e have shipped. Pass 3.5 (Data UX — Region blocks → Connections + Marketplaces) is in flight — 3.5a-region and 3.5a-api have shipped (Codex impl, pending commit); 3.5a (UI) is prompt-ready above; 3.5b/c/d follow. Pass 3.6 (Imports section on Data) is orthogonal to Pass 3.5 and can run in parallel since it touches different UI surfaces; one-after-the-other sequencing keeps each review small. Pass 4 (`WbrProfileWorkspace` reorganization) is a UI refactor whose scope shrinks once 3.5c moves Sync and 3.6 moves Imports out of WBR setup.

Detailed slice prompts for 3.5a-region, 3.5a-api, and 3.5a are inlined above. Prompts for 3.5b, 3.5c, 3.5d, 3f, 3g, 3h, 3.6a–d, and 4 will follow at execution time.
