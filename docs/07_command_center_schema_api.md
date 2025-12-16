# Command Center — Schema & API Reference (Canonical)

Status (2025-12-15): draft for implementation. Source of truth for the engineering contract (tables + API routes) for `docs/07_command_center_prd.md`.

Scope: Command Center is **single-tenant** (Ecomlabs internal), **admin-only** for MVP. ClickUp sync is **deferred**; we store mappings manually.

---

## 1) Identity Model (Profiles + Ghost Profiles)

Command Center needs “team members” even when they have never logged in (“Ghost Profiles”).

**Compatibility requirement (important):**
Other tools currently assume `public.profiles.id == auth.uid()` and store `created_by = auth.uid()` in their tables (with FKs referencing `public.profiles(id)`).

To support Ghost Profiles *without breaking existing tools*:
- Keep the invariant: for logged-in users, **`profiles.id == auth.users.id`**.
- Allow Ghost Profiles with **independent UUIDs** (not present in `auth.users` yet).
- When a Ghost Profile logs in, **merge** it into the canonical logged-in profile:
  - ensure canonical row exists (`profiles.id = auth.users.id`)
  - remap any known foreign keys from ghost id → canonical id
  - delete the ghost profile row

Implementation note (Supabase): this merge is typically performed in the existing signup trigger function
`public.handle_new_auth_user()` which is executed by a trigger on `auth.users` insert.

**Canonical columns**
- `profiles.id` (uuid, pk) — “profile id”; equals `auth.users.id` for logged-in users.
- `profiles.auth_user_id` (uuid, nullable) — for logged-in users set to `auth.users.id`; for Ghost Profiles null.
- `profiles.email` (text, not null) — used to link ghost → auth on login (case-insensitive uniqueness via partial unique indexes on `lower(email)`).

---

## 2) Tables (Core)

### 2.1 `public.agency_roles`
Dynamic roles (replaces enums for assignments).

```sql
create table public.agency_roles (
  id uuid primary key default gen_random_uuid(),
  slug text unique not null, -- e.g. 'brand_manager'
  name text not null,        -- e.g. 'Brand Manager'
  created_at timestamptz default now()
);
```

Seed (MVP defaults):
- `strategy_director`
- `brand_manager`
- `catalog_strategist`
- `catalog_specialist`
- `ppc_strategist`
- `ppc_specialist`
- `report_specialist`

### 2.2 `public.profiles`
Team member directory + access flags (admin-only CRUD in Command Center).

Minimum fields Command Center needs:
- identity: `id`, `auth_user_id`, `email`, `display_name`, `full_name`, `avatar_url`
- access: `is_admin`, `allowed_tools`
- external mappings: `clickup_user_id`, `slack_user_id`
- status: `employment_status`, `bench_status`

Notes:
- `bench_status` is derived from `client_assignments` via trigger (see 2.5).

### 2.3 `public.agency_clients`
Agency clients (NOT Composer clients).

Minimum fields:
- `id`, `name`, `status` (`active|inactive|archived`), `notes?`, timestamps

### 2.4 `public.brands`
Brands that belong to agency clients.

Minimum fields:
- `id`, `client_id` (fk `agency_clients.id`)
- `name`
- `product_keywords` (text[]) — for Debrief brand detection
- `amazon_marketplaces` (text[]) — for tools like AdScope (optional)
- `clickup_space_id` (text) — mapping stored manually (ClickUp sync later)
- `clickup_list_id` (text, nullable) — preferred list for task creation (tasks are created in lists)
- timestamps

### 2.5 `public.client_assignments`
Core junction: role assignments for a team member at either the client scope or brand scope.

Minimum fields:
- `id`
- `client_id` (fk `agency_clients.id`)
- `brand_id` (nullable fk `brands.id`) — `NULL` means “whole client”
- `team_member_id` (fk `profiles.id` **ON DELETE CASCADE**)
- `role_id` (fk `agency_roles.id`)
- `assigned_at`, `assigned_by` (fk `profiles.id`)

Uniqueness rule:
- One assignee per role slot per scope.
  - Client scope: unique `(client_id, role_id)` where `brand_id is null`
  - Brand scope: unique `(client_id, brand_id, role_id)` where `brand_id is not null`

Derived rule:
- `profiles.bench_status` should flip to `assigned` if any assignments exist, else `available`.

---

## 3) Read Models (Recommended)

These aren’t required, but simplify the UI and reduce client-side joins.

### 3.1 `public.v_command_center_clients`
Clients with brand counts and “coverage” (how many of the default roles are filled).

### 3.2 `public.v_command_center_client_org_chart`
Rows shaped for org chart rendering:
- `client_id`, `brand_id?`, `role_slug`, `role_name`, `team_member_id`, `team_member_name`, `team_member_email`, `employment_status`, `bench_status`

### 3.3 `public.v_command_center_bench`
All team members that are `employment_status = 'active'` plus their assignment count.

---

## 4) API Endpoints (Next.js Route Handlers)

Command Center **management routes** are **admin-only** (MVP). Enforce:
1) authenticated session exists
2) current user is admin (`public.profiles.is_admin = true`)

Exception:
- Debrief helper routes are **authenticated-only** (not admin), because Debrief will be used by non-admins.

Endpoint design goals:
- CRUD primitives for tables
- one “bootstrap” endpoint for the Command Center UI
- small helper endpoints needed by Debrief

Base: `frontend-web/src/app/api/command-center/*`

### 4.1 Bootstrap
`GET /api/command-center/bootstrap`

Returns everything needed to render Command Center without waterfalls:
```ts
type BootstrapResponse = {
  roles: { id: string; slug: string; name: string }[];
  clients: {
    id: string;
    name: string;
	    status: "active" | "inactive" | "archived";
	    brands: {
	      id: string;
	      name: string;
	      clickupSpaceId: string | null;
	      clickupListId: string | null;
	      productKeywords: string[];
	      amazonMarketplaces: string[];
	    }[];
	  }[];
	  teamMembers: {
	    id: string;
	    email: string;
	    displayName: string | null;
	    fullName: string | null;
	    avatarUrl: string | null;
	    isAdmin: boolean;
	    allowedTools: string[];
	    employmentStatus: "active" | "inactive" | "contractor";
	    benchStatus: "available" | "assigned" | "unavailable";
	    clickupUserId: string | null;
	    slackUserId: string | null;
	  }[];
  assignments: {
    id: string;
    clientId: string;
    brandId: string | null;
    teamMemberId: string;
    roleId: string;
    assignedAt: string;
    assignedBy: string | null;
  }[];
};
```

### 4.2 Clients
- `GET /api/command-center/clients`
- `POST /api/command-center/clients`
- `GET /api/command-center/clients/:clientId`
- `PATCH /api/command-center/clients/:clientId`
- `POST /api/command-center/clients/:clientId/archive` (soft archive)
- `DELETE /api/command-center/clients/:clientId` (test helper; archives first in UI; removes brands + assignments)

### 4.3 Brands
- `POST /api/command-center/clients/:clientId/brands`
- `PATCH /api/command-center/brands/:brandId`
- `DELETE /api/command-center/brands/:brandId` (test helper; removes brand-scoped assignments first)

### 4.4 Team Members
- `GET /api/command-center/team`
- `POST /api/command-center/team` (creates Ghost Profile)
- `PATCH /api/command-center/team/:teamMemberId`
- `POST /api/command-center/team/:teamMemberId/archive` (sets `employment_status = inactive`)
- `DELETE /api/command-center/team/:teamMemberId` (test helper; only for unlinked ghost + inactive + no assignments)

### 4.5 Roles
- `GET /api/command-center/roles`
- `POST /api/command-center/roles` (Phase 3+, optional)
- `PATCH /api/command-center/roles/:roleId` (Phase 3+, optional)

### 4.6 Assignments (Drag & Drop)
Prefer idempotent upserts.

- `POST /api/command-center/assignments/upsert`
  - creates or replaces a role assignment at a given scope
  - request:
    ```ts
    type UpsertAssignmentRequest = {
      clientId: string;
      brandId?: string | null;
      teamMemberId: string;
      roleId: string;
    };
    ```
  - response: `{ assignment: AssignmentRow }`

- `POST /api/command-center/assignments/remove`
  - request: `{ assignmentId: string }`

### 4.7 Debrief Helpers (Read-only)
Debrief needs brand + keywords and role routing.

- `GET /api/command-center/debrief/brands`
  - auth: authenticated-only
  - response: brands with `clientId`, `brandId`, `name`, `productKeywords`, `amazonMarketplaces`, `clickupSpaceId`, `clickupListId`

- `GET /api/command-center/debrief/routing?brandId=<uuid>`
  - returns role→assignee mapping (client scope + brand overrides)
  - auth: authenticated-only
  - response:
    ```ts
    type DebriefRoutingResponse = {
      clientId: string;
      brandId: string;
      roles: { roleSlug: string; roleName: string; teamMemberId: string; teamMemberName: string | null; teamMemberEmail: string }[];
    };
    ```

---

## 5) Non-Goals (MVP)
- Multi-tenancy for Command Center tables (`organization_id`)
- ClickUp sync/caching tables (ClickUp service can be added later)
- Non-admin access model / per-user visibility rules (Phase 3+)
