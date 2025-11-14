# Product Requirement Document: The Agency Configurator (Admin Settings)

## 1. Executive Summary
**The Agency Configurator** is the "Control Panel" for the Agency OS. It is a restricted, Admin-only interface that manages the relationships between **People**, **Clients**, and **External Tools** (ClickUp).

Instead of manually editing SQL rows in Supabase to onboard a new client or employee, the Admin uses a visual "Drag-and-Drop" interface to configure the agency's operating structure.

## 2. User Experience (UX)

### 2.1 The Interface
Located at `tools.ecomlabs.ca/admin` (Protected Route: Role = 'Admin' only).

The UI consists of three main tabs:
1.  **Team & Roles:** Manage users and their permission levels.
2.  **Client Map:** Configure Client $\leftrightarrow$ ClickUp Space bindings.
3.  **The Assignment Board:** A visual matrix to assign Team Members to Clients.

### 2.2 Core Workflows
1.  **Onboarding a New Hire:**
    * *Action:* Admin invites a user (via Supabase Auth email). User logs in.
    * *Admin Task:* Admin sees the new user in the "Unassigned" list. Assigns them a Role (e.g., "Advertising Specialist").
2.  **Onboarding a New Client:**
    * *Action:* Admin clicks "Add Client." Enters "Brand X."
    * *Mapping:* Admin selects the corresponding ClickUp Space from a dropdown (fetched via ClickUp API).
    * *Result:* The system links `Brand X` (Internal ID) to `Space 123` (ClickUp ID).
3.  **Staffing a Project (The "Matrix" Drag-and-Drop):**
    * *Action:* Admin drags "Jane (PPC)" onto the "Brand X" card.
    * *Result:* Jane now has access to Brand X in her dashboard. "The Operator" knows to assign Brand X tasks to Jane.

---

## 3. Technical Architecture

### 3.1 Frontend (`frontend-web`)
* **Framework:** Next.js + ShadcnUI (Data Table & Drag-and-Drop primitives).
* **State:** React Query (for fetching the latest assignments).
* **Auth Guard:** Strict middleware check. If `user.role !== 'Admin'`, redirect to `/`.

### 3.2 Backend (`backend-core`)
The Python backend provides "Management Endpoints" that write to the Supabase `public` schema.

* `GET /api/admin/users`: Returns all users + roles.
* `PATCH /api/admin/users/{id}`: Update role.
* `GET /api/admin/clients`: Returns clients + ClickUp mapping status.
* `POST /api/admin/clients`: Create new client.
* `POST /api/admin/assignments`: Link `{user_id}` to `{client_id}`.
* `POST /api/admin/sync-clickup`: Trigger the "Nightly Sync" manually to refresh Space lists.

---

## 4. Data Model (Supabase)

This tool creates the "Knowledge Graph" that the rest of the OS relies on.

### 4.1 Extended User Profiles

```sql
alter table public.profiles
add column role text check (role in (
  'Admin',
  'Brand Manager',
  'Catalog Specialist',
  'Advertising Specialist'
));

-- Stores the user's specific ClickUp Member ID for task assignment
alter table public.profiles
add column clickup_user_id text;
```

### 4.2 Client Registry

```sql
create table public.clients (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  logo_url text,
  clickup_space_id text unique, -- Critical Link
  clickup_space_name text, -- Cached for UI speed
  status text default 'active' -- active, churned, paused
);
```

### 4.3 The Assignment Junction

This is the source of truth for "Who works on what."

```sql
create table public.client_assignments (
  client_id uuid references public.clients on delete cascade,
  user_id uuid references public.profiles on delete cascade,
  assigned_at timestamptz default now(),
  primary key (client_id, user_id)
);
```

## 5. Integration Logic (ClickUp)

The Configurator needs to "know" about ClickUp Spaces to let you map them.

* **Fetch:** On page load (or via manual sync button), backend-core hits `https://api.clickup.com/api/v2/team/{team_id}/space`.
* **Display:** The dropdown for "ClickUp Space" in the "Add Client" modal is populated by this live (or cached) list.
* **User Mapping:** The tool also fetches ClickUp Members so you can map "John Smith (Agency OS)" to "John Smith (ClickUp User ID 998877)".

## 6. Success Criteria (MVP)

* **RBAC Enforcement:** Non-admins cannot access `/admin`.
* **Client Creation:** Admin can create "Client Y" and link it to "ClickUp Space Y".
* **Team Assignment:** Admin can assign "User A" to "Client Y".
* **Verification:** When "User A" logs in, they only see "Client Y" in their dashboard selector (filtering works).
