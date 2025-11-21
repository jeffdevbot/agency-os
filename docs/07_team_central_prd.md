# Product Requirement Document: Team Central

**Version:** 1.3 (Shared ClickUp Service architecture documented)
**Product Area:** Agency OS → Tools → Team Central
**Status:** Ready for Engineering
**Route:** `tools.ecomlabs.ca/team-central`

**Architecture:** Single-tenant (Ecomlabs internal only)

---

## 1. Executive Summary

**Team Central** is the organizational control panel for Agency OS. It provides a visual interface to manage the relationship between team members, clients, and their roles—replacing manual spreadsheets and SQL editing with drag-and-drop org charts.

### Primary Goals

1. **Visualize team structure** across all clients using hierarchical org charts
2. **Manage role assignments** with intuitive drag-and-drop from "The Bench"
3. **Map external tools** (ClickUp user IDs, Slack handles) to enable automation
4. **Enable The Operator** to intelligently assign tasks based on client team structure
5. **Streamline onboarding** for new clients and team members

### The Core Problem

Currently, understanding "who works on what client in what capacity" requires:
- Asking around
- Checking ClickUp manually
- Tribal knowledge
- Hope and prayer

Team Central makes this **instantly visible** and **easily configurable**.

---

## 2. User Roles & Personas

### Admin Users
**Who:** Agency owners, operations managers
**Needs:** Full CRUD access to all clients, team members, and assignments
**Access:** Everything in Team Central

### Non-Admin Users (Future)
**Who:** Team members (Brand Managers, Specialists, etc.)
**Needs:** View-only access to their own assignments and team structure
**Access:** Limited to their profile and assigned clients (Phase 3+)

**Note:** For MVP (Phases 1-2), Team Central is **Admin-only**.

---

## 3. The Agency Team Structure

Team Central supports a 7-role hierarchy with flexible assignment:

```
Strategy Director (floating advisor across clients)
    ↓
Brand Manager (client lead)
    ↓
├─ Catalog Strategist          ├─ PPC Strategist
    ↓                               ↓
├─ Catalog Specialist          ├─ PPC Specialist

Report Specialist (supports Brand Manager)
```

### Role Definitions

| Role | Responsibilities | Typical Reporting |
|------|------------------|-------------------|
| **Strategy Director** | Subject matter expert, unblocks team, advises on complex strategy | Reports to leadership; supports all roles |
| **Brand Manager** | Client-facing lead, requirements gathering, overall account strategy | Reports to Strategy Director or leadership |
| **Catalog Strategist** | Executes catalog work, assigns to Specialists, interfaces with Brand Manager or client | Reports to Brand Manager |
| **Catalog Specialist** | Executes assigned catalog tasks (listings, optimization, etc.) | Reports to Catalog Strategist |
| **PPC Strategist** | Executes PPC work, assigns to Specialists, interfaces with Brand Manager or client | Reports to Brand Manager |
| **PPC Specialist** | Executes assigned PPC tasks (campaigns, bidding, reporting) | Reports to PPC Strategist |
| **Report Specialist** | Assembles weekly/monthly reports, supports Brand Manager with analytics | Reports to Brand Manager |

### Key Flexibility Rules

- ✅ **One person can hold multiple roles** (e.g., Sarah is both Strategy Director and Brand Manager for Client A)
- ✅ **Roles are per-client** (Sarah is Brand Manager for Client A but Catalog Strategist for Client B)
- ✅ **All roles can be assigned to multiple clients** (Mike is PPC Strategist for 5 clients)
- ✅ **Roles are contextual, not identity** (roles stored on assignments, not on the person)

---

## 4. Core Workflows

### Workflow 1: Onboarding a New Client

**Actor:** Admin
**Steps:**
1. Navigate to Team Central → Clients → "+ New Client"
2. Enter client name, select ClickUp Space from dropdown
3. System creates client record
4. Navigate to individual client page
5. See empty org chart with 7 role slots (all show "+ Add")
6. Drag team members from "The Bench" into role slots
7. For each drop: system creates assignment with specified role
8. Client is now fully staffed and visible to The Operator

**Success:** Client has all critical roles filled (at minimum: Brand Manager)

---

### Workflow 2: Onboarding a New Team Member

**Actor:** Admin
**Steps:**
1. (Optional) New hire logs in via Google SSO → `auth.users` and `profiles` auto-created
2. Admin navigates to Team Central → Team → "+ New Team Member"
3. Enter name, email, ClickUp User ID, Slack handle
4. Toggle "Admin" if applicable
5. Team member appears in "The Bench" (unassigned)
6. Admin navigates to client pages and drags them into assignments
7. If team member logs in later, email auto-matches existing profile

**Success:** Team member is in the system, assigned to clients, ready to receive tasks from The Operator

---

### Workflow 3: Reassigning Team Members (Staffing Changes)

**Actor:** Admin
**Steps:**
1. Navigate to individual client page
2. See current org chart
3. Click "Remove" on existing team member in a role
4. Member returns to "The Bench"
5. Drag replacement team member from bench into that role
6. System updates assignment, logs change
7. The Operator now assigns tasks to the new person

**Success:** Client team structure reflects current reality, no manual ClickUp updates needed

---

### Workflow 4: Mapping ClickUp Spaces & Users

**Actor:** Admin
**Steps:**
1. Navigate to Team Central → Clients → Individual Client
2. Click "Sync ClickUp" button
3. Backend fetches all ClickUp Spaces for the team
4. Admin selects correct Space from dropdown
5. System stores `clickup_space_id` on client record
6. Navigate to Team Central → Team → Individual Member
7. Enter ClickUp User ID (or select from fetched list)
8. System stores `clickup_user_id` on profile

**Success:** Every client has a ClickUp Space ID, every active team member has a ClickUp User ID, The Operator can assign tasks programmatically

---

## 5. Screen-by-Screen Requirements

### 5.1 Main Dashboard ("Team Central Home")

**Route:** `/team-central`

**Layout:**
```
┌─────────────────────────────────────────────────────┐
│  Team Central                                       │
│  Your agency's organizational command center        │
└─────────────────────────────────────────────────────┘

┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│   Clients     │  │     Team      │  │     Roles     │
│               │  │               │  │               │
│   12 Active   │  │  18 Members   │  │  By Function  │
│   2 Paused    │  │  3 On Bench   │  │               │
│               │  │               │  │               │
│  [View All]   │  │  [View All]   │  │  [View All]   │
└───────────────┘  └───────────────┘  └───────────────┘
```

**Components:**
- Page header with title + description
- Three navigation cards with basic stats
- Admin-only route guard (redirect to `/` if `is_admin = false`)

---

### 5.2 Clients — All

**Route:** `/team-central/clients`

**Purpose:** Browse all clients, see team coverage at a glance

**Layout:**
```
┌─────────────────────────────────────────────────────┐
│  Clients                           [+ New Client]   │
│  [Search: _______________]  [Filter: Active ▼]      │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  Grid of Client Cards:                              │
│                                                     │
│  ┌─────────────────┐  ┌─────────────────┐          │
│  │ [Logo]          │  │ [Logo]          │          │
│  │ Brand X         │  │ Brand Y         │          │
│  │ Active          │  │ Paused          │          │
│  │                 │  │                 │          │
│  │ Team: 5 roles   │  │ Team: 3 roles   │          │
│  │ BM: Sarah J.    │  │ BM: Mike C.     │          │
│  │                 │  │                 │          │
│  │ [View Team →]   │  │ [View Team →]   │          │
│  └─────────────────┘  └─────────────────┘          │
└─────────────────────────────────────────────────────┘
```

**Data Displayed Per Client:**
- Client name
- Logo (if available)
- Status badge (Active / Paused / Churned)
- Team size (count of assigned roles)
- Brand Manager name (if assigned)
- ClickUp mapping status (icon: ✅ mapped / ⚠️ not mapped)

**Actions:**
- Search by client name
- Filter by status
- Sort by: Name, Date Added, Team Size
- Click card → Navigate to individual client page

**Empty State:**
- "No clients yet. Add your first client to get started."
- "+ New Client" CTA

---

### 5.3 Clients — Individual (⭐ Core Feature)

**Route:** `/team-central/clients/[clientId]`

**Purpose:** Visualize client's team as org chart, manage assignments via drag-and-drop

**Layout:**
```
┌─────────────────────────────────────────────────────┐
│  ← Back to Clients                                  │
│                                                     │
│  Brand X                           [Edit Client]   │
│  Status: Active ▼                                   │
│  ClickUp Space: [Dropdown: Brand X Space ▼] [Sync] │
│  Slack: #client-brandx                              │
└─────────────────────────────────────────────────────┘

┌─────────────── CLIENT ORG CHART ────────────────────┐
│                                                     │
│              [Strategy Director]                    │
│              Sarah Johnson                          │
│              [Remove]                               │
│                      ↓                              │
│              [Brand Manager]                        │
│              Sarah Johnson                          │
│              [Remove]                               │
│                   ↙     ↘                           │
│      [Catalog Strategist]    [PPC Strategist]       │
│      Mike Chen              Lisa Park               │
│      [Remove]               [Remove]                │
│          ↓                      ↓                   │
│   [Catalog Specialist]     [PPC Specialist]         │
│   + Add role               Tom Wilson               │
│                            [Remove]                 │
│                                                     │
│              [Report Specialist]                    │
│              + Add role                             │
│                                                     │
└─────────────────────────────────────────────────────┘

┌─────────────────── THE BENCH ───────────────────────┐
│  Unassigned Team Members (drag to assign):          │
│                                                     │
│  [Jane Smith]  [Alex Wong]  [Chris Lee]             │
│                                                     │
└─────────────────────────────────────────────────────┘

┌─────────────── ASSIGNMENT HISTORY ──────────────────┐
│  3 days ago: Sarah Johnson assigned as Brand Mgr    │
│  1 week ago: ClickUp Space mapped                   │
│  2 weeks ago: Client created by Jeff                │
└─────────────────────────────────────────────────────┘
```

**Org Chart Interaction:**
- **Empty slot:** Shows "+ Add [Role Name]" as drop zone
- **Filled slot:** Shows team member name + "Remove" button
- **Drag from bench:** Hover over role slot → slot highlights → drop → assignment created
- **Visual hierarchy:** Lines/arrows showing reporting structure
- **Dual roles:** Same person can appear in multiple slots (e.g., Sarah as both Strategy Director AND Brand Manager)

**ClickUp Integration:**
- Dropdown populated by API call to ClickUp (`GET /team/{team_id}/space`)
- Manual "Sync" button refreshes list
- Visual indicator if not mapped (⚠️ warning)

**Assignment History:**
- Shows last 10 changes to this client's team
- Displays: timestamp, action, actor
- Stored in `client_assignments` via `assigned_at`, `assigned_by`

**Actions:**
- Edit client metadata (name, status, Slack channels)
- Sync ClickUp
- Assign/unassign team members via drag-and-drop
- Navigate to team member profiles (click name)

---

### 5.4 Team — All

**Route:** `/team-central/team`

**Purpose:** Browse all team members, see assignment load, manage admin access

**Layout:**
```
┌─────────────────────────────────────────────────────┐
│  Team                            [+ New Team Member]│
│  [Search: _______________]  [Filter: All ▼]         │
└─────────────────────────────────────────────────────┘

┌──────────────────── THE BENCH (3) ──────────────────┐
│  Unassigned:  [Jane Smith]  [Alex Wong]  [Chris Lee]│
└─────────────────────────────────────────────────────┘

┌──────────────────── ALL TEAM (18) ──────────────────┐
│                                                     │
│  Name        | Roles | Clients | Admin | ClickUp   │
│  ──────────────────────────────────────────────────│
│  Sarah J.    | BM,SD |    3    |  ✓    | 123456    │
│  Mike C.     | CS    |    2    |       | 789012    │
│  Lisa P.     | PPCS  |    5    |       | 345678    │
│  ...                                                │
│                                                     │
│  [View] [Edit] per row                              │
└─────────────────────────────────────────────────────┘
```

**The Bench Section:**
- Shows team members with zero client assignments
- Draggable items (can drag from here to client pages)
- Count badge in section header

**Team Table Columns:**
- **Name:** Full name (click → individual page)
- **Roles:** List of unique roles held across all clients (abbreviated)
  - BM = Brand Manager, SD = Strategy Director, CS = Catalog Strategist, CSp = Catalog Specialist, PPCS = PPC Strategist, PPCSp = PPC Specialist, RS = Report Specialist
- **Clients:** Count of unique clients assigned to
- **Admin:** Checkbox/toggle (admin can toggle inline)
- **ClickUp:** ClickUp User ID (or "Not mapped" warning)
- **Actions:** [View] [Edit] buttons

**Filters:**
- All / Assigned / On Bench
- By role (any role they hold)
- Admin / Non-Admin

**Search:** By name or email

---

### 5.5 Team — Individual (⭐ Reverse Org Chart)

**Route:** `/team-central/team/[memberId]`

**Purpose:** See all assignments for one team member, manage their metadata

**Layout:**
```
┌─────────────────────────────────────────────────────┐
│  ← Back to Team                                     │
│                                                     │
│  Sarah Johnson                      [Edit Profile]  │
│  sarah@ecomlabs.ca                                  │
│                                                     │
│  Admin Access: ✓                                    │
│  ClickUp User ID: 123456                            │
│  Slack: @sarah                                      │
└─────────────────────────────────────────────────────┘

┌────────────────── ASSIGNMENTS ──────────────────────┐
│                                                     │
│  Brand Manager for:                                 │
│    • Client A                        [Remove]       │
│    • Client B                        [Remove]       │
│                                                     │
│  Strategy Director for:                             │
│    • Client A                        [Remove]       │
│                                                     │
│  Catalog Strategist for:                            │
│    • Client C                        [Remove]       │
│                                                     │
│  Total: 4 roles across 3 clients                    │
│                                                     │
└─────────────────────────────────────────────────────┘

┌──────────────── RECENT ACTIVITY ────────────────────┐
│  2 days ago: Assigned to Client A as Brand Manager  │
│  1 week ago: ClickUp ID updated                     │
│  2 weeks ago: Profile created                       │
└─────────────────────────────────────────────────────┘
```

**Assignments Section:**
- Grouped by role
- Each group lists clients where they hold that role
- Inline "Remove" button per assignment
- Summary stats at bottom

**Edit Profile Modal/Form:**
- Display name
- Email (read-only if from Google auth)
- Admin toggle (with confirmation dialog)
- ClickUp User ID (text input or dropdown from synced list)
- Slack User ID / handle

**Actions:**
- Edit metadata
- Remove from specific client assignments
- Toggle admin access
- Navigate to client pages (click client name)

---

### 5.6 Roles — All Functions

**Route:** `/team-central/roles`

**Purpose:** Bird's-eye view of team organized by function

**Layout:**
```
┌─────────────────────────────────────────────────────┐
│  Roles by Function                                  │
│  View your team organized by their responsibilities │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│                                                     │
│  ┌──────────────────┐  ┌──────────────────┐        │
│  │ Strategy Directors│  │ Brand Managers   │        │
│  │                  │  │                  │        │
│  │  2 members       │  │  5 members       │        │
│  │  Sarah, Mike     │  │  Sarah, Lisa...  │        │
│  │                  │  │                  │        │
│  │  [View →]        │  │  [View →]        │        │
│  └──────────────────┘  └──────────────────┘        │
│                                                     │
│  ┌──────────────────┐  ┌──────────────────┐        │
│  │ Catalog Team     │  │ PPC Team         │        │
│  │                  │  │                  │        │
│  │  8 members       │  │  7 members       │        │
│  │  3 Strategists   │  │  2 Strategists   │        │
│  │  5 Specialists   │  │  5 Specialists   │        │
│  │                  │  │                  │        │
│  │  [View →]        │  │  [View →]        │        │
│  └──────────────────┘  └──────────────────┘        │
│                                                     │
│  ┌──────────────────┐                              │
│  │ Report Specialists│                             │
│  │                  │                              │
│  │  2 members       │                              │
│  │  Jane, Alex      │                              │
│  │                  │                              │
│  │  [View →]        │                              │
│  └──────────────────┘                              │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Function Cards:**
- Count of team members with that role (across all clients)
- Preview of names (up to 3-4, then "...")
- For teams (Catalog, PPC): breakdown by Strategist vs. Specialist
- Click → Navigate to function detail page

---

### 5.7 Roles — By Function

**Route:** `/team-central/roles/[function]` (e.g., `/catalog`, `/ppc`, `/brand-managers`)

**Purpose:** Deep dive into one function, see assignment distribution

**Example: Catalog Team**

**Layout:**
```
┌─────────────────────────────────────────────────────┐
│  ← Back to Roles                                    │
│                                                     │
│  Catalog Team                                       │
│  All Catalog Strategists and Specialists            │
└─────────────────────────────────────────────────────┘

┌────────────── CATALOG STRATEGISTS (3) ──────────────┐
│                                                     │
│  Name      | Clients | Assignments                  │
│  ───────────────────────────────────────────────────│
│  Sarah J.  |    2    | Client A, Client C           │
│  Mike C.   |    1    | Client B                     │
│  Lisa P.   |    3    | Client D, Client E, Client F │
│                                                     │
└─────────────────────────────────────────────────────┘

┌────────────── CATALOG SPECIALISTS (5) ──────────────┐
│                                                     │
│  Name      | Clients | Assignments                  │
│  ───────────────────────────────────────────────────│
│  Tom W.    |    4    | Client A, B, C, D            │
│  Jane S.   |    2    | Client E, Client F           │
│  ...                                                │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Data Displayed:**
- Separate sections for Strategists vs. Specialists (where applicable)
- Name (link to individual team member page)
- Client count
- List of client names (truncated if >5, show "...and 3 more")

**Actions:**
- Click name → Team member page
- Click client → Client page
- Sort by: Name, Client count

**Future Enhancement Placeholder:**
- Utilization % (when ClickUp hours integrated)
- "Overloaded" / "Available" badges

---

## 6. Data Model

### 6.1 Tables & Schema

#### **`public.profiles` (enhanced)**

Extends Supabase `auth.users` with agency-specific fields.

**Enhancement Strategy:** Add new columns to existing `profiles` table (non-breaking, additive changes only).

```sql
-- Existing columns (already in live DB):
-- id uuid primary key references auth.users on delete cascade
-- email text unique
-- full_name text
-- avatar_url text
-- created_at timestamptz default now()
-- updated_at timestamptz default now()

-- NEW columns to add via migration:
alter table public.profiles
  add column if not exists display_name text,
  add column if not exists is_admin boolean default false,
  add column if not exists clickup_user_id text unique,
  add column if not exists slack_user_id text unique,
  add column if not exists employment_status text
    default 'active'
    check (employment_status in ('active', 'inactive', 'contractor')),
  add column if not exists bench_status text
    default 'available'
    check (bench_status in ('available', 'assigned', 'unavailable'));
```

**Important Notes:**
- ⚠️ `id` is **non-nullable** (PRIMARY KEY referencing `auth.users`)
- Users must log in via Google SSO before they can be assigned to clients
- `employment_status`:
  - `'active'`: Current employee, shows in "The Bench" and assignment interfaces
  - `'inactive'`: Former employee or on leave, excluded from "The Bench" (soft delete)
  - `'contractor'`: Temporary/contract worker, shows in interfaces but marked distinctly
- `bench_status` is derived: 'assigned' if user has any client assignments, else 'available'
- `is_admin` controls access to Team Central admin features

---

#### **`public.team_role` (enum type)**

```sql
create type team_role as enum (
  'strategy_director',
  'brand_manager',
  'catalog_strategist',
  'catalog_specialist',
  'ppc_strategist',
  'ppc_specialist',
  'report_specialist'
);
```

---

#### **`public.team_members_pending` (NEW - Pre-Login Support)**

Stores team members who have been added to the system but haven't logged in yet.

```sql
create table public.team_members_pending (
  id uuid primary key default gen_random_uuid(),
  email text unique not null,
  full_name text not null,
  display_name text,
  clickup_user_id text,
  slack_user_id text,
  invited_by uuid references public.profiles(id),
  invited_at timestamptz default now(),
  linked_profile_id uuid unique references public.profiles(id),
  linked_at timestamptz,
  expires_at timestamptz default (now() + interval '30 days')
);

-- Trigger: Auto-link when user signs up with matching email
create or replace function link_pending_team_member()
returns trigger as $$
begin
  update public.team_members_pending
  set linked_profile_id = NEW.id,
      linked_at = now()
  where email = NEW.email
    and linked_profile_id is null;
  return NEW;
end;
$$ language plpgsql security definer;

create trigger on_profile_created
  after insert on public.profiles
  for each row
  execute function link_pending_team_member();
```

**Purpose:**
- Admins can add team members before they log in (e.g., during onboarding)
- Once user logs in via Google SSO, system auto-links by email
- Pending members can be pre-configured with ClickUp/Slack IDs
- After linking, admin can drag them into client assignments

**Workflow:**
1. Admin adds "sarah@ecomlabs.ca" with name and IDs
2. Row created in `team_members_pending`
3. Sarah logs in via Google SSO → `profiles` row created
4. Trigger auto-links: `pending.linked_profile_id = sarah's profiles.id`
5. Admin sees Sarah is now "active" and can assign her to clients

---

#### **`public.agency_clients`** (⚠️ Renamed to avoid conflict with `client_profiles`)

Represents Ecomlabs' client accounts (e.g., Brand X, Brand Y). Distinct from `client_profiles` which represents external users of Composer/Ngram.

```sql
create table public.agency_clients (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  logo_url text,
  clickup_space_id text unique,
  clickup_space_name text,
  slack_channel_internal text,
  slack_channel_external text,
  status text default 'active' check (status in ('active', 'paused', 'churned')),
  archived_at timestamptz,
  created_at timestamptz default now(),
  created_by uuid references public.profiles(id),
  updated_at timestamptz default now()
);

-- Indexes
create index idx_agency_clients_status on public.agency_clients(status) where status = 'active';
create index idx_agency_clients_clickup on public.agency_clients(clickup_space_id) where clickup_space_id is not null;
create index idx_agency_clients_archived on public.agency_clients(archived_at) where archived_at is not null;
```

**Why "agency_clients"?**
- Live DB already has `public.client_profiles` for Composer/Ngram end-users
- This table is for **Ecomlabs' internal client accounts** (the brands you serve)
- Naming avoids confusion and future conflicts

**Archiving Strategy:**
- Clients are **never hard-deleted** (preservation of audit trail and historical data)
- Set `archived_at` to mark client as archived
- Archived clients excluded from default views (filter `WHERE archived_at IS NULL`)
- Archived clients retain all assignments for historical reference
- Can be unarchived by setting `archived_at = NULL` if client returns

---

#### **`public.client_assignments` (⭐ Core Junction Table)**

```sql
create table public.client_assignments (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.agency_clients(id) on delete cascade,
  team_member_id uuid not null references public.profiles(id) on delete cascade,
  role team_role not null,
  assigned_at timestamptz default now(),
  assigned_by uuid references public.profiles(id),

  -- One person can have multiple roles for the same client
  unique (client_id, team_member_id, role)
);

-- Indexes for common query patterns
create index idx_assignments_client on public.client_assignments(client_id);
create index idx_assignments_member on public.client_assignments(team_member_id);
create index idx_assignments_role on public.client_assignments(role);
create index idx_assignments_member_client on public.client_assignments(team_member_id, client_id);
create index idx_assignments_client_role on public.client_assignments(client_id, role);
```

**Key Design Decision:**
`role` is stored **on the assignment**, not on the person. This allows:
- Sarah to be Brand Manager for Client A
- Sarah to be Catalog Strategist for Client B
- Sarah to be BOTH Strategy Director AND Brand Manager for Client C

**Example Rows:**
```
id | client_id | team_member_id | role                | assigned_at
---+-----------+----------------+---------------------+------------
1  | client-a  | sarah-123      | brand_manager       | 2025-11-20
2  | client-a  | sarah-123      | strategy_director   | 2025-11-20
3  | client-b  | sarah-123      | catalog_strategist  | 2025-11-21
4  | client-a  | mike-456       | catalog_strategist  | 2025-11-20
```

---

### 6.2 Derived Queries

**Get Client Org Chart:**
```sql
select
  ca.role,
  p.id,
  p.display_name,
  p.email,
  ca.assigned_at,
  assigned_by_profile.display_name as assigned_by_name
from client_assignments ca
join profiles p on ca.team_member_id = p.id
left join profiles assigned_by_profile on ca.assigned_by = assigned_by_profile.id
where ca.client_id = :clientId
order by ca.role, ca.assigned_at;
```

**Get Team Member's Assignments (Reverse Org Chart):**
```sql
select
  ca.role,
  c.id as client_id,
  c.name as client_name,
  c.status,
  ca.assigned_at
from client_assignments ca
join agency_clients c on ca.client_id = c.id
where ca.team_member_id = :memberId
order by ca.role, c.name;
```

**Get "The Bench" (Unassigned Team Members):**
```sql
select p.*
from profiles p
where not exists (
  select 1 from client_assignments ca
  where ca.team_member_id = p.id
)
and p.bench_status = 'available'
and p.employment_status = 'active'  -- Only show active employees
order by p.display_name;
```

---

### 6.3 Row-Level Security (RLS) Policies

**Security Model:** Single-tenant (Ecomlabs internal). All authenticated Ecomlabs employees can view data; only admins can modify.

#### **`public.agency_clients`**

```sql
-- Enable RLS
alter table public.agency_clients enable row level security;

-- Policy: All authenticated users can view clients
create policy "Authenticated users can view agency clients"
  on public.agency_clients
  for select
  to authenticated
  using (true);

-- Policy: Only admins can insert/update/delete clients
create policy "Only admins can manage agency clients"
  on public.agency_clients
  for all
  to authenticated
  using (
    exists (
      select 1 from public.profiles
      where id = auth.uid() and is_admin = true
    )
  )
  with check (
    exists (
      select 1 from public.profiles
      where id = auth.uid() and is_admin = true
    )
  );
```

#### **`public.client_assignments`**

```sql
alter table public.client_assignments enable row level security;

-- Policy: All authenticated users can view assignments (for org charts)
create policy "Authenticated users can view assignments"
  on public.client_assignments
  for select
  to authenticated
  using (true);

-- Policy: Only admins can manage assignments
create policy "Only admins can manage assignments"
  on public.client_assignments
  for all
  to authenticated
  using (
    exists (
      select 1 from public.profiles
      where id = auth.uid() and is_admin = true
    )
  )
  with check (
    exists (
      select 1 from public.profiles
      where id = auth.uid() and is_admin = true
    )
  );
```

#### **`public.team_members_pending`**

```sql
alter table public.team_members_pending enable row level security;

-- Policy: Only admins can view/manage pending members
create policy "Only admins can manage pending members"
  on public.team_members_pending
  for all
  to authenticated
  using (
    exists (
      select 1 from public.profiles
      where id = auth.uid() and is_admin = true
    )
  );
```

#### **`public.profiles` (Enhanced Policies)**

```sql
-- Existing: Users can view all profiles (team directory)
-- Existing: Users can update their own profile

-- NEW: Only admins can toggle is_admin flag
create policy "Only admins can grant admin access"
  on public.profiles
  for update
  to authenticated
  using (
    -- Current user must be admin
    exists (
      select 1 from public.profiles
      where id = auth.uid() and is_admin = true
    )
  )
  with check (
    -- Can only modify is_admin if updater is admin
    exists (
      select 1 from public.profiles
      where id = auth.uid() and is_admin = true
    )
  );
```

**Notes:**
- All policies check `is_admin` flag via subquery (not a stored function)
- Authenticated users = anyone logged in via Google SSO
- Admin-only operations: Create/update/delete clients, manage assignments, toggle admin access
- Read access is open to all authenticated Ecomlabs employees (team directory visibility)

---

## 7. API Surface

All routes are **admin-only** (enforce `is_admin = true` middleware).

### Clients

- `GET /api/team-central/clients` — List all clients
  - Query params: `status`, `search`, `page`, `pageSize`
  - Returns: `{ clients: Client[], total, page, pageSize }`

- `POST /api/team-central/clients` — Create new client
  - Body: `{ name, clickup_space_id?, slack_channel_internal?, slack_channel_external?, status? }`
  - Returns: `{ client: Client }`

- `GET /api/team-central/clients/:id` — Get client detail + org chart
  - Returns: `{ client: Client, assignments: Assignment[], history: ActivityLog[] }`

- `PATCH /api/team-central/clients/:id` — Update client metadata
  - Body: `{ name?, logo_url?, clickup_space_id?, slack_*, status? }`
  - Returns: `{ client: Client }`

- `PATCH /api/team-central/clients/:id/archive` — Archive client (soft delete)
  - Body: `{ archived: boolean }` (set to false to unarchive)
  - Sets `archived_at` timestamp or nullifies it
  - Returns: `{ client: Client }`

---

### Team Members

- `GET /api/team-central/team` — List all team members
  - Query params: `bench_status`, `role`, `is_admin`, `search`, `page`, `pageSize`
  - Returns: `{ members: TeamMember[], bench: TeamMember[], total }`

- `POST /api/team-central/team` — Create new team member
  - Body: `{ email, display_name, is_admin?, clickup_user_id?, slack_user_id? }`
  - Returns: `{ member: TeamMember }`

- `GET /api/team-central/team/:id` — Get team member detail + assignments
  - Returns: `{ member: TeamMember, assignments: GroupedAssignment[], history: ActivityLog[] }`

- `PATCH /api/team-central/team/:id` — Update team member metadata
  - Body: `{ display_name?, is_admin?, clickup_user_id?, slack_user_id?, bench_status?, employment_status? }`
  - Returns: `{ member: TeamMember }`

- `PATCH /api/team-central/team/:id/employment-status` — Update employment status (soft delete)
  - Body: `{ employment_status: 'active' | 'inactive' | 'contractor' }`
  - Sets status to 'inactive' for offboarding (preserves all assignment history)
  - Inactive members excluded from "The Bench" and assignment interfaces
  - Returns: `{ member: TeamMember }`

---

### Assignments

- `POST /api/team-central/assignments` — Create assignment (drag-and-drop)
  - Body: `{ client_id, team_member_id, role }`
  - Returns: `{ assignment: Assignment }`

- `DELETE /api/team-central/assignments/:id` — Remove assignment
  - Returns: `{ success: boolean }`

- `GET /api/team-central/assignments/client/:clientId` — Get all assignments for client
  - Returns: `{ assignments: Assignment[] }`

- `GET /api/team-central/assignments/member/:memberId` — Get all assignments for member
  - Returns: `{ assignments: Assignment[] }`

---

### ClickUp Integration

- `POST /api/team-central/clickup/sync-spaces` — Manual sync of ClickUp Spaces
  - Hits ClickUp API: `GET /team/{team_id}/space`
  - Returns: `{ spaces: ClickUpSpace[] }`

- `POST /api/team-central/clickup/sync-users` — Manual sync of ClickUp Users
  - Hits ClickUp API: `GET /team/{team_id}/member`
  - Returns: `{ users: ClickUpUser[] }`

**Note:** These syncs also run nightly via `worker-sync` service.

---

### Roles

- `GET /api/team-central/roles` — Get all roles with counts
  - Returns: `{ roles: { role: string, count: number, members: string[] }[] }`

- `GET /api/team-central/roles/:role` — Get team members with specific role
  - Example: `GET /roles/catalog_strategist`
  - Returns: `{ role, members: TeamMember[], assignments: Assignment[] }`

---

## 8. Integration Strategy

### 8.1 ClickUp Integration

**Purpose:** Enable The Operator to assign tasks to the right person for each client

**ClickUp Team ID:** `42600885` (Ecomlabs workspace)

**How to Find Your Team ID:**
If you need to verify or retrieve your ClickUp Team ID in the future, run this command:
```bash
curl -H "Authorization: YOUR_CLICKUP_API_TOKEN" https://api.clickup.com/api/v2/team
```
Look for the `id` field in the response. You'll need this ID for all Space and User sync operations.

**What We Store:**
- Client → ClickUp Space ID
- Team Member → ClickUp User ID

**Sync Flow:**
1. Admin clicks "Sync ClickUp" button
2. Backend calls ClickUp API (requires `CLICKUP_API_TOKEN` env var):
   - `GET /team/42600885/space` → Returns all Spaces
   - `GET /team/42600885/member` → Returns all Users
3. Frontend displays dropdowns populated with synced data
4. Admin selects correct mapping
5. System stores IDs in DB

**Nightly Worker Job:**
- Runs at 2 AM daily
- Re-syncs Spaces and Users
- Updates cached names (`clickup_space_name`)
- Logs changes (new Spaces, removed Users, etc.)

**The Operator Usage:**
```python
# When assigning a task for Client X to their Brand Manager
client = get_client(client_id)
assignment = get_assignment(client_id, role='brand_manager')
team_member = get_team_member(assignment.team_member_id)

# Create task in client's ClickUp Space, assigned to team member's ClickUp User ID
clickup.create_task(
  space_id=client.clickup_space_id,      # e.g., "90123456"
  assignee=team_member.clickup_user_id,  # e.g., "12345678"
  title="Weekly report for Brand X",
  ...
)
```

---

#### 8.1.1 ClickUp Service Architecture

**Design Decision:** Team Central will consume a **shared ClickUp service** rather than calling the ClickUp API directly.

**Rationale:**
- Multiple tools will need ClickUp integration (Team Central, The Operator, future reporting tools)
- Centralized service provides single source of truth for API interactions
- Easier to implement rate limiting, caching, error handling in one place
- When ClickUp API changes, only one service needs updates
- Consistent authentication and logging across all ClickUp operations

**Service Location:** `backend-core/services/clickup_service.py` (FastAPI) or `/api/integrations/clickup/*` (Next.js API routes)

**Team Central Requirements (MVP):**
The ClickUp service must provide these methods for Team Central:

```python
class ClickUpService:
    """Shared ClickUp API service for all Agency OS tools"""

    def __init__(self, api_token: str, team_id: str = "42600885"):
        self.api_token = api_token
        self.team_id = team_id

    # Team Central uses these for mapping UI
    def get_spaces(self) -> List[ClickUpSpace]:
        """Fetch all Spaces for the team

        Returns:
            List of spaces with id, name, private, multiple_assignees fields
        API: GET /team/{team_id}/space
        """

    def get_team_members(self) -> List[ClickUpUser]:
        """Fetch all Users/Members for the team

        Returns:
            List of users with id, username, email, initials fields
        API: GET /team/{team_id}/member
        """
```

**The Operator Requirements (Future):**
When The Operator is built, the service will be extended with task management methods:

```python
    # The Operator will use these (add in Phase 2)
    def create_task(self, space_id: str, task_data: dict) -> ClickUpTask:
        """Create a task in a Space"""

    def update_task(self, task_id: str, updates: dict) -> ClickUpTask:
        """Update an existing task"""

    def get_tasks(self, space_id: str, filters: dict = None) -> List[ClickUpTask]:
        """Fetch tasks for a Space with optional filters"""
```

**Implementation Notes:**
- Service handles authentication (reads `CLICKUP_API_TOKEN` from env)
- Service implements exponential backoff retry for rate limits (ClickUp: 100 req/min)
- Optional: Service can cache `get_spaces()` and `get_team_members()` for 1 hour (refreshed nightly)
- All ClickUp API calls go through this service (no direct `fetch()` calls from frontend/other services)

**Team Central API Routes:**
Team Central's API routes will call the ClickUp service:

```typescript
// /api/team-central/clickup/sync-spaces.ts
import { ClickUpService } from '@/services/clickup'

export async function POST(req: Request) {
  const clickup = new ClickUpService(process.env.CLICKUP_API_TOKEN!)
  const spaces = await clickup.get_spaces()
  return Response.json({ spaces })
}
```

---

### 8.2 Google Auth Integration

**Current State:**
- `auth.users` managed by Supabase
- Users log in via Google SSO (Google Workspace restricted to `@ecomlabs.ca`)

**Team Central Strategy:**

**Scenario A: Team Member Logs In First**
1. User clicks "Sign in with Google"
2. Supabase creates `auth.users` entry
3. Trigger auto-creates `profiles` entry with `email`, `display_name` from Google
4. `is_admin = false` by default
5. Admin navigates to Team Central, sees new profile, can assign to clients

**Scenario B: Admin Adds Team Member First (Not Logged In Yet)** ⭐ **Common during onboarding**
1. Admin clicks "+ New Team Member" (pre-login)
2. Enters: `sarah@ecomlabs.ca`, "Sarah Johnson", ClickUp ID, Slack handle
3. System creates `team_members_pending` entry (not yet in `profiles`)
4. Admin can configure Sarah's ClickUp/Slack mappings, but **cannot yet assign to clients**
5. Admin sends Google Workspace invite to sarah@ecomlabs.ca
6. When Sarah logs in with Google:
   - Supabase creates `auth.users` + `profiles` entries
   - Trigger auto-links: `team_members_pending.linked_profile_id = sarah's profile.id`
   - ClickUp/Slack IDs copied from pending record to `profiles`
7. Sarah now appears in "The Bench" and can be assigned to clients

**Why this approach?**
- `profiles.id` must reference `auth.users.id` (non-nullable FK)
- Can't create profiles without login
- Separate table allows pre-configuration before first login
- Auto-linking happens transparently via trigger (see Section 6.1)

**UI Indicator:**
- Pending members show with badge: "⏳ Pending Login"
- Once linked, badge changes to: "✅ Active"

---

### 8.3 Slack Integration (Future)

**Phase 4+ Feature**

**What We'd Store:**
- Client → Internal Slack Channel (`#client-brandx`)
- Client → External Slack Channel (shared Slack Connect)
- Team Member → Slack User ID

**The Operator Usage:**
- Post task notifications to client's internal channel
- DM team member when assigned a task
- Post status updates to external client channel (weekly reports, etc.)

**Implementation:**
- Add Slack fields to `clients` table (already in schema above)
- Add Slack User ID to `profiles` (already in schema above)
- Build Slack OAuth flow for workspace connection
- Store workspace token in env vars

---

## 9. User Experience Details

### 9.1 Drag-and-Drop Interaction

**Library:** `dnd-kit` (same as Composer keyword grouping)

**Draggable Items:**
- Team member cards in "The Bench"
- Team member cards in role slots (for reassignment)

**Drop Zones:**
- Each role slot in client org chart
- "The Bench" (for removal)

**Visual Feedback:**
- Drag start: Item lifts with shadow
- Drag over valid drop zone: Zone highlights with border/background
- Drag over invalid zone: Cursor shows "not allowed"
- Drop success: Animated placement, toast notification "Sarah assigned as Brand Manager"
- Drop failure: Item snaps back to origin, error toast

**Behavior:**
- Dropping team member onto empty role slot → Creates assignment
- Dropping team member onto filled role slot → Replaces existing assignment (confirmation dialog)
- Dropping team member back to bench → Removes assignment

---

### 9.2 Admin Access Toggle

**UI:** Large toggle switch on team member profile

**Interaction:**
1. Admin clicks toggle to grant admin access
2. Confirmation dialog appears:
   ```
   Grant Sarah Johnson admin access?

   Admin users can:
   • Access Team Central and manage all clients/team
   • View all tools in Agency OS (future)
   • Assign roles and manage assignments

   [Cancel] [Grant Access]
   ```
3. On confirm: `is_admin = true` saved, toast notification
4. Sarah can now access `/team-central` on next login

**Security:**
- Middleware on all Team Central routes checks `is_admin = true`
- Non-admins redirected to home with message: "This page is restricted to administrators."

---

### 9.3 Empty States

**No Clients Yet:**
- Illustration + message: "No clients yet. Add your first client to get started."
- CTA: "+ New Client"

**No Team Members Yet:**
- Illustration + message: "Your team is empty. Add team members to start assigning them to clients."
- CTA: "+ New Team Member"

**Client with No Assignments:**
- Empty org chart with all slots showing "+ Add [Role]"
- Helper text: "Drag team members from The Bench below to assign roles."

**The Bench is Empty:**
- Message: "All team members are assigned! 🎉"

---

### 9.4 Responsive Design

**Desktop (Primary):**
- Org charts display in full hierarchy with visual lines
- Tables show all columns
- Drag-and-drop works smoothly

**Tablet:**
- Org charts collapse to vertical list (no visual lines)
- Tables hide non-essential columns (e.g., ClickUp ID)
- Drag-and-drop still functional

**Mobile (Future):**
- Org charts become accordion list
- Tables become cards
- Drag-and-drop replaced with tap-to-assign modal

**MVP:** Desktop + Tablet. Mobile deferred to Phase 3.

---

## 10. Success Criteria (MVP)

### Functional Requirements

✅ **Client Management**
- Admin can create clients
- Admin can map ClickUp Space to client
- Admin can see all clients in grid/list view
- Admin can archive/pause clients

✅ **Team Member Management**
- Admin can create team members (with or without prior login)
- Admin can edit team member metadata (name, ClickUp ID, Slack handle)
- Admin can toggle admin access
- Team members auto-link to auth when they log in

✅ **Role Assignment**
- Admin can assign team member to client with specific role via drag-and-drop
- Admin can assign same person to multiple clients
- Admin can assign same person to multiple roles for same client
- Admin can remove assignments

✅ **Visualization**
- Client page shows org chart with 7 role types in hierarchy
- Team member page shows reverse org chart (grouped by role)
- "The Bench" shows unassigned team members
- Roles pages show team organized by function

✅ **ClickUp Integration**
- Manual sync button fetches Spaces and Users
- Nightly worker auto-syncs ClickUp data
- All clients have ClickUp Space ID (or warning if missing)
- All active team members have ClickUp User ID (or warning if missing)

✅ **The Operator Enablement**
- Database has all data needed for The Operator to:
  - Find client's ClickUp Space
  - Find team member's ClickUp User ID
  - Determine who to assign tasks to based on role
  - Query "Who is the Brand Manager for Client X?"

---

### Non-Functional Requirements

✅ **Performance**
- Client list loads in <500ms
- Org chart renders in <200ms
- Drag-and-drop has <100ms response time

✅ **Security**
- All Team Central routes enforce admin-only access
- Non-admins cannot view or modify data
- Assignment changes are logged with `assigned_by` for audit trail

✅ **Usability**
- Drag-and-drop works on first try
- Empty states are helpful, not frustrating
- Error messages are actionable ("Map ClickUp Space to enable task assignment")

---

## 11. Future Enhancements (Post-MVP)

### Phase 3: Non-Admin Access
- Team members can view their own profile
- Team members can see their assigned clients
- Team members can view client org charts (read-only)
- Dashboard filter: "My Clients Only"

---

### Phase 4: Time Tracking & Analytics

**ClickUp Hours Integration:**
- Pull time entries from ClickUp API
- Display on team member profile: "Last 30 days: 120 hours"
- Display on client page: "Team spent 80 hours this month"

**New Screens:**
- **Time Dashboard:** `/team-central/analytics/time`
  - Time by [Period] × [Function] × [Employee] × [Client]
  - Filters: Last 7/30/90 days
  - Export to CSV

**Smart Features (enabled by time data):**
- Team Capacity Grid (progress bars showing utilization)
- "Overloaded" / "Available" badges
- Suggested assignments based on workload
- Client profitability analysis (hours × rate)

---

### Phase 5: Slack Integration
- Map Slack channels to clients
- Map Slack User IDs to team members
- The Operator sends Slack notifications on task assignment
- Weekly digest to client channels

---

### Phase 6: "Wow Factor" Features

Based on earlier brainstorming, these could be added later:

- **Client Health Score:** 🟢🟡🔴 traffic light based on role coverage
- **Suggested Assignments:** AI-like logic (not AI) to recommend best team member for a role
- **Client Onboarding Checklist:** Progress bar + missing items
- **Org Chart PDF Export:** Generate client-facing PDF of team structure
- **Role Coverage Heatmap:** Executive dashboard showing gaps across all clients
- **Client Comparison View:** Side-by-side org charts for standardization
- **Client "At-Risk" Indicator:** Flag clients with team instability

**Decision:** Defer all "wow factor" features to later phases to keep MVP focused and shippable.

---

## 12. Out of Scope (Explicitly NOT in MVP)

❌ **Permissions beyond Admin/Non-Admin** (e.g., "Brand Managers can only edit their own clients")
❌ **Client budgets or financial tracking**
❌ **Task management** (that's The Operator's job)
❌ **Time tracking** (Phase 4+)
❌ **Slack integration** (Phase 5+)
❌ **Mobile app** (responsive web only)
❌ **Real-time collaboration** (no presence indicators, no live cursors)
❌ **Client portal** (external client access to their team)
❌ **Automated role suggestions** (manual assignment only)
❌ **Historical assignment analytics** ("How many times has Sarah been reassigned this year?")

---

## 13. Technical Stack

**Frontend:**
- Next.js 14 (App Router)
- ShadCN UI components
- `dnd-kit` for drag-and-drop
- React Query for data fetching
- TypeScript

**Backend:**
- Next.js API routes (for Team Central CRUD operations)
- Supabase Postgres (data layer)
- RLS policies (enforce org-level access in future multi-tenant mode)

**Shared Services:**
- **ClickUp Service** (`backend-core/services/clickup_service.py` or `/api/integrations/clickup/*`)
  - Centralized ClickUp API wrapper used by Team Central, The Operator, and future tools
  - Handles authentication, rate limiting, caching, error retry logic
  - MVP methods: `get_spaces()`, `get_team_members()`
  - Future methods: `create_task()`, `update_task()`, `get_tasks()`
  - See Section 8.1.1 for detailed architecture

**External APIs:**
- ClickUp API v2 (`https://api.clickup.com/api/v2/`) - **accessed exclusively via ClickUp Service**
- Google OAuth (via Supabase Auth)
- Slack API (Phase 5+)

**Workers:**
- Python `worker-sync` service (nightly ClickUp sync via ClickUp Service)

---

## 14. Migration & Rollout Plan

### Existing Data
**Current state:**
- Some team members exist in `profiles` (logged in before)
- No conflicts: `client_profiles` is for Composer/Ngram external users (different entity)
- Team Central uses new `agency_clients` table

**Migration Steps:**
1. Run schema migration:
   - Create enum types: `team_role`, `bench_status` (if using enum)
   - Enhance `profiles` with new columns (additive only)
   - Create `team_members_pending` table + trigger
   - Create `agency_clients` table
   - Create `client_assignments` table
   - Add indexes (Section 6.1)
   - Enable RLS policies (Section 6.3)
2. Backfill `is_admin = true` for known admins (manually or via script)
3. No data loss (all changes are additive)

### Rollout
1. **Week 1:** Schema + API development
2. **Week 2:** UI development (clients + team modules)
3. **Week 3:** Drag-and-drop + ClickUp integration
4. **Week 4:** Testing + bug fixes
5. **Week 5:** Admin training session (show Jeff & team how to use it)
6. **Week 6:** Production launch (admin-only initially)
7. **Week 8+:** Gather feedback, iterate

---

## 15. Appendix: Screens Checklist

- [ ] Main Dashboard (Team Central Home)
- [ ] Clients — All (grid view)
- [ ] Clients — Individual (org chart + bench)
- [ ] Team — All (table + bench section)
- [ ] Team — Individual (reverse org chart)
- [ ] Roles — All Functions (grid of function cards)
- [ ] Roles — By Function (e.g., Catalog Team detail)
- [ ] Modals/Forms:
  - [ ] New Client Modal
  - [ ] Edit Client Modal
  - [ ] New Team Member Modal
  - [ ] Edit Team Member Modal
  - [ ] ClickUp Sync Modal (showing fetched spaces/users)
  - [ ] Confirmation Dialogs (remove assignment, toggle admin, etc.)

---

## 16. Decisions Made (Post-Review)

**Resolved after Red Team & Supabase Consultant review (2025-11-21):**

1. ✅ **Multi-Tenancy:** Single-tenant (Ecomlabs internal only). No `organization_id` needed in Team Central tables.
2. ✅ **Pre-Login Team Members:** Use `team_members_pending` table with auto-linking trigger (not nullable `profiles.id`).
3. ✅ **Admin Model:** `profiles.is_admin` boolean flag (not role enum).
4. ✅ **Table Naming:** `public.agency_clients` (avoids conflict with existing `client_profiles`).
5. ✅ **RLS Policies:** Defined in Section 6.3 (all authenticated can view, only admins can modify).
6. ✅ **Indexes:** Composite indexes added for common query patterns (org charts, reverse charts, role filtering).
7. ✅ **Client Archiving:** Soft delete using `archived_at` column. Archived clients excluded from default views, preserves all historical data and assignments.
8. ✅ **Team Member Offboarding:** Soft delete using `employment_status = 'inactive'`. Inactive members excluded from "The Bench" and assignment interfaces, preserves assignment history.
9. ✅ **ClickUp Team ID:** `42600885` (Ecomlabs workspace). Documented in Section 8.1 with "how to find it" instructions.
10. ✅ **ClickUp Service Architecture:** Team Central will consume a shared ClickUp service (not call API directly). Service will be used by Team Central, The Operator, and future tools. Documented in Section 8.1.1 and Section 13.

**Still Open (Require Product Decision):**

1. **Default Max Clients Per Role:** Should we enforce limits? (e.g., "Brand Managers can't exceed 6 clients") **Recommendation:** No limits in MVP, add Phase 4 with hours data.
2. **Assignment Change Notifications:** Should team members receive email/Slack when assigned to new client? **Recommendation:** Deferred to Phase 5 (Slack integration).

---

**End of PRD**
