# Command Center — Implementation Plan (Micro Tasks)

Purpose: ship Command Center per `docs/07_command_center_prd.md`, using the engineering contract in `docs/07_command_center_schema_api.md`.

Scope (MVP):
- Single-tenant (internal Ecomlabs only)
- Admin-only access
- ClickUp sync deferred (manual mapping fields only)

---

## Phase 0 — Preflight (Decisions + Baselines)

1) Lock contracts
- Confirm `docs/07_command_center_prd.md` is the UX reference.
- Confirm `docs/07_command_center_schema_api.md` is the canonical schema/API contract.
- Freeze role slugs ordering (used for org chart slots).

2) Confirm “Ghost Profile” compatibility strategy
- Goal: Ghost Profiles without breaking existing tools that assume `profiles.id == auth.uid()`.
- Adopt invariant: logged-in users have `profiles.id == auth.users.id`; Ghost Profiles start with random UUID and are merged into the canonical profile on first login (explicit FK remap + ghost row deletion).

3) Inventory existing Supabase schema
- Inspect `supabase/migrations/*team_central*`, `*operator*`, `*scribe*` for:
  - `public.profiles` shape and constraints
  - existing `agency_clients` + `client_assignments` tables
  - any existing triggers touching `profiles`
- Identify whether `team_members_pending` exists in the deployed DB.

Deliverable: short note in PRD Engineering Notes (or a checklist comment) confirming the above.

---

## Phase 1 — Database (Supabase) Migrations

Create one forward-only migration (do NOT edit existing migrations).

1) Migration scaffold
- Add `supabase/migrations/<timestamp>_command_center_v2.sql`.
- Ensure it is idempotent where possible (`if exists` / `if not exists`) but prefer explicit forward moves.

2) Roles table (replace enums)
- Create `public.agency_roles` (+ seed default roles).
- Enable RLS + policies (admin-only write, authenticated read) consistent with PRD.

3) Brands table
- Create `public.brands` with required fields:
  - `client_id`, `name`, `product_keywords text[]`, `clickup_space_id`, `amazon_marketplaces text[]`, timestamps
- Add `updated_at` trigger and indexes.
- Enable RLS + policies (authenticated read; admin-only write).

4) Client assignments v2
- Alter `public.client_assignments` to match PRD:
  - Rename `profile_id` → `team_member_id` (if column exists).
  - Add `brand_id` (nullable fk `brands.id`).
  - Add `role_id` (fk `agency_roles.id`).
  - Add `assigned_by` (fk `profiles.id`), keep `assigned_at`.
  - Drop/replace the old uniqueness constraint `unique(client_id, profile_id)` with:
    - partial unique index for brand scope
    - partial unique index for client scope (brand null)
- Ensure FK `team_member_id → profiles.id` is `ON DELETE CASCADE` (no `ON UPDATE CASCADE` required; we remap explicitly during ghost merge).
- Add indexes used by the UI (`client_id`, `brand_id`, `team_member_id`, `role_id`).
- Add trigger `sync_bench_status()` that updates `profiles.bench_status` on insert/delete.
  - Add test cases: first assignment, many assignments, delete last, delete one-of-many, and ensure reassignment is modeled as delete+insert (or add an update-trigger if using in-place updates).

5) Profiles updates (Ghost Profiles support)
- Update `public.profiles` with the PRD fields if missing:
  - `email` (NOT NULL), `display_name`, `full_name`, `avatar_url`
  - `is_admin`, `allowed_tools`
  - `employment_status`, `bench_status`
  - `clickup_user_id`, `slack_user_id`
- Remove the FK constraint that ties `profiles.id` to `auth.users(id)` (required for Ghost Profiles).
  - Keep existing `id` values as-is (they should already equal auth uid for existing users).
- Add `auth_user_id uuid references auth.users(id) on delete set null` (nullable).
- Add case-insensitive email uniqueness via partial unique indexes on `lower(email)`:
  - one for Ghost Profiles (`auth_user_id is null`)
  - one for canonical users (`auth_user_id is not null`)
- Add partial unique index on `auth_user_id`.

6) Link-on-login trigger (Ghost merge)
- Update the existing `auth.users` trigger function (`public.handle_new_auth_user()`) to merge Ghost Profiles by email (or add the trigger if it doesn’t exist):
  - Find existing profile by `lower(email)`.
  - Always insert/ensure the canonical profile row exists (`id = new.id`, `auth_user_id = new.id`).
  - If a Ghost Profile exists (`auth_user_id is null`):
    - copy missing metadata from ghost → canonical profile
    - remap known foreign keys from ghost id → canonical id (current schema: `client_assignments.profile_id` + `client_assignments.assigned_by`; later schema: `client_assignments.team_member_id`)
    - delete the ghost profile row (preserves email uniqueness)
  - Else if not found:
    - insert a new profile with `id = new.id`, `auth_user_id = new.id`, `email = new.email`, `full_name/avatar_url` from metadata if present.

7) Remove pending table (if present)
- Drop `public.team_members_pending` (and any obsolete invite-link triggers) if it exists in DB.
- Decide what to do with `team_role` enum + `profiles.role` column:
  - MVP recommendation: leave in place if it’s not harmful, but stop using it.
  - If removing: drop `profiles.role` first, then drop enum type.

8) Optional: Read views
- Add `v_command_center_client_org_chart` and `v_command_center_bench` if the UI would otherwise do too many joins.

9) Migration verification checklist
- Run local Supabase migration apply.
- Manually verify:
  - creating a Ghost Profile row works (no auth FK constraint failures)
  - inserting into `client_assignments` works and updates `bench_status`
  - creating a new auth user triggers a `profiles` row insert/link (in staging)

---

## Phase 2 — Backend (Next.js API Routes)

Pattern reference: `frontend-web/src/app/api/scribe/*` route handlers using `createSupabaseRouteClient()`.

Shared utilities:
- Add `frontend-web/src/lib/command-center/auth.ts`:
  - `requireSession()` (401 if no session)
  - `requireAdmin()` (403 if `profiles.is_admin` false)
- Add `frontend-web/src/lib/command-center/validators.ts` (zod schemas for payloads).

Endpoints (create route handlers; see `docs/07_command_center_schema_api.md`):

1) `GET /api/command-center/bootstrap`
- Fetch roles, clients+brands, team members, assignments.
- Return in one payload to avoid waterfalls.

2) Clients
- `GET /api/command-center/clients`
- `POST /api/command-center/clients`
- `PATCH /api/command-center/clients/:clientId`
- `POST /api/command-center/clients/:clientId/archive`

3) Brands
- `POST /api/command-center/clients/:clientId/brands`
- `PATCH /api/command-center/brands/:brandId`

4) Team members
- `GET /api/command-center/team`
- `POST /api/command-center/team` (Ghost Profile create)
- `PATCH /api/command-center/team/:teamMemberId`
- `POST /api/command-center/team/:teamMemberId/archive`

5) Assignments
- `POST /api/command-center/assignments/upsert`
  - Upsert semantics: if the unique scope exists, update; else insert.
- `POST /api/command-center/assignments/remove`

6) Debrief helpers (read-only)
- `GET /api/command-center/debrief/brands`
- `GET /api/command-center/debrief/routing?brandId=<uuid>`

Error handling contract:
- Use consistent `{ error: { code, message } }` responses.
- Validate UUID params and payload shape; return 400 on validation errors.

---

## Phase 3 — Frontend (Command Center UI)

Create a new tool route group under `frontend-web/src/app/command-center/*`.

1) Route + guard
- `frontend-web/src/app/command-center/layout.tsx`:
  - server-side session check
  - admin check (redirect non-admins)

2) Data loading model
- On first load, call `GET /api/command-center/bootstrap`.
- Store as a single normalized client-side store (e.g., Zustand):
  - `clientsById`, `brandsById`, `rolesById`, `teamMembersById`, `assignmentsById`
  - derived selectors for org chart slots + bench list

3) Screens (MVP)
- `/command-center` — dashboard links + basic stats
- `/command-center/clients` — clients grid/list + “New Client”
- `/command-center/clients/:clientId` — org chart + brands panel + bench sidebar
- `/command-center/team` — roster list + “New Team Member”
- `/command-center/team/:teamMemberId` — member detail + assignments list

4) Org chart UI (drag & drop)
- Use `@dnd-kit/core` (or equivalent) with:
  - draggable bench cards (`team_member_id`)
  - droppable role slots (`client_id`, `brand_id?`, `role_id`)
- On drop, call `POST /api/command-center/assignments/upsert`.
- Provide “remove from role” action that calls `POST /api/command-center/assignments/remove`.

5) Brand configuration UI
- Brand editor form for:
  - name
  - product keywords (chip input)
  - clickup space id (text input; sync later)
  - marketplaces (multi-select)

6) Team member configuration UI
- Create/edit:
  - name, email
  - clickup_user_id, slack_user_id
  - is_admin toggle (danger-guarded)
  - allowed_tools checkboxes (optional; can ship later if unused)
  - employment_status toggle

7) Empty states + UX polish
- Empty client: “Add brands” + “Assign Brand Manager”
- Empty bench: explain that inactive/assigned members don’t show
- Ghost Profile badge (not linked yet)
- Toasts for saves + errors

---

## Phase 4 — Debrief Integration (Thin Slice)

Goal: unblock Debrief’s routing logic without ClickUp.

1) Ensure Debrief can read brand keywords + assignments
- Use the Debrief helper endpoints from Phase 2.
- Debrief can:
  - detect brand by `brands.product_keywords`
  - map task type → role slug
  - resolve role slug → assignee via `client_assignments` (brand overrides + client scope)

2) Add a small contract test fixture
- Create a JSON fixture that includes:
  - one client with 2 brands
  - at least 3 roles assigned
  - brand keywords
- Use it to validate routing edge cases:
  - brand-specific override exists
  - client-level fallback
  - role unfilled → no assignee

---

## Phase 5 — QA / Release Checklist

1) RLS sanity
- Non-admin cannot hit any `/api/command-center/*` routes (403).
- Admin can CRUD clients/brands/team/assignments.

2) Ghost Profile lifecycle
- Admin creates Ghost Profile and assigns to a role.
- User logs in for the first time:
  - canonical profile row exists (`profiles.id = auth.uid()`)
  - ghost row is merged (assignments remapped; ghost row deleted)
  - user can now use other tools that store `created_by = auth.uid()` with no changes.

3) Performance
- `bootstrap` endpoint returns in < 1s for ~50 clients / ~200 staff / ~3k assignments.
- Add indexes if any query is slow.

4) Deploy notes
- Apply DB migrations first (Supabase).
- Deploy Next.js UI + API routes next.
