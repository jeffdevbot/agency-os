# Admin Client Hub IA — Implementation Plan

Target information architecture: consolidate client admin under `/clients/[clientSlug]/{reports,data,team}`. Staged over small vertical slices. Jeff + Claude + Codex collaborate; see roles below.

---

## Scorecard

Tick each box as slices merge. Brief one-liner after each box can note PR / commit SHA once landed.

### Pass 1 — Shell

- [x] **Slice 1** — `/clients` list + `/clients/[slug]` overview with 3 tiles + admin-only root nav entry. Tiles link to existing routes. *(Merged 2026-04-23, Codex impl, reviewed by Claude.)*

### Pass 2 — Re-parent existing screens

- [ ] **Slice 2a** — `/clients/[slug]/reports` renders `ClientReportsHub`. 307 redirect from `/reports/[slug]`.
- [ ] **Slice 2b-1** — Extract `ClientTeamWorkspace` reusable component from `/command-center/clients/[id]/page.tsx`. Command Center renders the extracted component. No new routes.
- [ ] **Slice 2b-2** — Mount `<ClientTeamWorkspace/>` at `/clients/[slug]/team`. Update Team tile href.
- [ ] **Slice 2c** — `/clients/[slug]/data` renders `ReportApiAccessScreen` with provider-neutral copy. 307 redirects from `/reports/client-data-access/*`.

Redirects ship as 307 (temporary) during migration. After Passes 1–2 soak for a week without rollback, a follow-up PR flips them to 308 (permanent) to let browsers/CDNs cache. **Do not ship 308s on first landing** — they cache aggressively and make rollback painful.

### Pass 3 — Rebuild Data against Option B schema (deferred, bundled with SP-API direct migration)

- [ ] **Slice 3a** — Schema migration: change `report_api_connections` uniqueness to `(client_id, provider, external_account_id)`. Backfill existing rows. (Claude owns.)
- [ ] **Slice 3b** — `/clients/[slug]/data/connections` rebuilt as one-row-per-connection table supporting multi-region / multi-account.
- [ ] **Slice 3c** — `SpApiReportsClient` generic create/poll/download/decompress helper + tests.
- [ ] **Slice 3d** — Section 1 (business data) direct SP-API service; A/B against Windsor.
- [ ] **Slice 3e** — Listings catalog direct SP-API.
- [ ] **Slice 3f** — Section 3 inventory + returns direct SP-API.
- [ ] **Slice 3g** — Delete Windsor services, env vars, and frontend references. Repoint nightly sync.
- [ ] **Slice 3h** — Delete P&L Windsor compare (`windsor_compare.py` + `PnlWindsorCompareCard` + hook).

### Pass 4 — Independent UI refactor

- [ ] **Slice 4** — Split `WbrProfileWorkspace.tsx` kitchen sink into Sync / Imports / Mapping / Profile tabs under `/clients/[slug]/reports/[mkt]/wbr/setup/*`.

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

- **IA boundary:** Data = credentials/connections (provider-neutral). Reports = report products + report-specific setup (WBR row tree, ASIN mapping, Pacvue import, campaign exclusions). Team = brands + org-chart. This differs from an earlier draft that put WBR setup under Data — replaced by Codex's (correct) argument that report-specific config belongs with the report.
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

## Pass 3 and Pass 4 — planning deferred

Pass 3 (rebuild `/data` against Option B schema + SP-API direct migration) is a multi-slice track planned separately once Passes 1–2 land. Pass 4 (`WbrProfileWorkspace` split) is a straight UI refactor that can happen independently.

This doc will be expanded with detailed slice prompts for Pass 3 when we're ready to start it. Scorecard entries above are placeholders so the overall progress is visible.
