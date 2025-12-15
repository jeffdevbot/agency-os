# Product Requirement Document: Command Center

**Version:** 2.0 (Merged Command Center + Client Registry)
**Product Area:** Agency OS → Tools → Command Center
**Status:** Ready for Engineering
**Route:** `tools.ecomlabs.ca/command-center`

**Architecture:** Single-tenant (Ecomlabs internal only)

**Subsystems:**
- **Team Management** — Team members, roles, assignments
- **Client & Brand Management** — Clients, brands, ClickUp spaces, product keywords

---

## 1. Executive Summary

**Command Center** is the organizational control panel for Agency OS. It provides a unified interface to manage clients, brands, team members, and role assignments—replacing manual spreadsheets and SQL editing with intuitive drag-and-drop org charts.

### Primary Goals

1. **Manage clients and brands** with ClickUp space mappings and product keywords
2. **Visualize team structure** across all clients using hierarchical org charts
3. **Manage role assignments** with intuitive drag-and-drop from "The Bench"
4. **Map external tools** (ClickUp user IDs, Slack handles) to enable automation
5. **Enable Debrief** to route work intelligently (brand detection + role-based assignment)
6. **Streamline onboarding** for new clients, brands, and team members

### The Core Problem

**Team Structure:** Understanding "who works on what client in what capacity" requires asking around, checking ClickUp manually, and tribal knowledge.

**Client Routing:** Different tools need different client information:
- **Debrief:** Which brand ClickUp Space should tasks go to? What keywords identify which brand?
- **AdScope:** Which Amazon marketplace is this client on?

Command Center makes this **instantly visible** and **easily configurable**.

---

## 2. User Roles & Personas

### Admin Users
**Who:** Agency owners, operations managers
**Needs:** Full CRUD access to all clients, team members, and assignments
**Access:** Everything in Command Center

### Non-Admin Users (Future)
**Who:** Team members (Brand Managers, Specialists, etc.)
**Needs:** View-only access to their own assignments and team structure
**Access:** Limited to their profile and assigned clients (Phase 3+)

**Note:** For MVP (Phases 1-2), Command Center is **Admin-only**.

---

## 3. The Agency Team Structure

Command Center supports a 7-role hierarchy with flexible assignment:

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
1. Navigate to Command Center → Clients → "+ New Client"
2. Enter client name (and optional metadata like marketplaces, notes)
3. System creates client record
4. Navigate to individual client page
5. Add one or more brands (name + product keywords)
6. See empty org chart with 7 role slots (all show "+ Add")
7. Drag team members from "The Bench" into role slots
8. For each drop: system creates assignment with specified role
9. Client is now fully staffed and ready for Debrief role-based routing

**Success:** Client has all critical roles filled (at minimum: Brand Manager)

---

### Workflow 2: Onboarding a New Team Member

**Actor:** Admin
**Steps:**
1. Admin navigates to Command Center → Team → "+ New Team Member"
2. Create a profile (can be a Ghost Profile if the user hasn’t logged in yet): name, email, ClickUp User ID, Slack handle
3. Toggle "Admin" if applicable
4. Team member appears in "The Bench" (unassigned)
5. Admin navigates to client pages and drags them into assignments
6. If the team member logs in later, the system links `auth.users` to the existing profile by email (`profiles.auth_user_id`)

**Success:** Team member is in the system, assigned to clients, ready to be pre-selected as an assignee in Debrief

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
7. Debrief will pre-select/assign tasks to the new person for that role

**Success:** Client team structure reflects current reality, no manual ClickUp updates needed

---

### Workflow 4: Mapping ClickUp Spaces & Users

**Actor:** Admin
**Steps:**
1. Navigate to Command Center → Clients → Individual Client
2. Click "Sync ClickUp" button
3. Backend fetches all ClickUp Spaces for the team
4. Admin opens a brand and selects the correct ClickUp Space from dropdown
5. System stores `clickup_space_id` on the brand record
6. Navigate to Command Center → Team → Individual Member
7. Enter ClickUp User ID (or select from fetched list)
8. System stores `clickup_user_id` on profile

**Success:** Every brand has a ClickUp Space ID, every active team member has a ClickUp User ID, Debrief can create tasks programmatically

---

## 5. Screen-by-Screen Requirements

### 5.1 Main Dashboard ("Command Center Home")

**Route:** `/command-center`

**Layout:**
```
┌─────────────────────────────────────────────────────┐
│  Command Center                                       │
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

**Route:** `/command-center/clients`

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
- ClickUp mapping status for brands (icon: ✅ mapped / ⚠️ not mapped)

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

**Route:** `/command-center/clients/[clientId]`

**Purpose:** Manage client brands, visualize team as org chart, manage assignments via drag-and-drop

**Layout:**
```
┌─────────────────────────────────────────────────────┐
│  ← Back to Clients                                  │
│                                                     │
│  SB Supply                         [Edit Client]   │
│  Status: Active ▼                                   │
│  Marketplaces: US, CA                               │
│  Slack: #client-sbsupply                            │
└─────────────────────────────────────────────────────┘

┌───────────────────── BRANDS ────────────────────────┐
│                                      [+ Add Brand]  │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │  Whoosh                          [Edit]      │   │
│  │  ClickUp: Whoosh Space ✅                    │   │
│  │  Keywords: simulator, wipes                  │   │
│  │  Marketplaces: US, CA                        │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │  Ranqer                          [Edit]      │   │
│  │  ClickUp: ⚠️ Not mapped                      │   │
│  │  Keywords: charger, Pro 2                    │   │
│  │  Marketplaces: US                            │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │  Lifemate                        [Edit]      │   │
│  │  ClickUp: Lifemate Space ✅                  │   │
│  │  Keywords: pet, collar                       │   │
│  │  Marketplaces: US, CA, MX                    │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
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
│  1 week ago: Whoosh brand added                     │
│  2 weeks ago: Client created by Jeff                │
└─────────────────────────────────────────────────────┘
```

**Brands Section:**
- Each client can have multiple brands
- Each brand has its own ClickUp Space (for Debrief task routing)
- `product_keywords` help Debrief identify which brand a task belongs to
- ⚠️ Warning indicator if ClickUp Space not mapped

**Org Chart Interaction:**
- **Empty slot:** Shows "+ Add [Role Name]" as drop zone
- **Filled slot:** Shows team member name + "Remove" button
- **Drag from bench:** Hover over role slot → slot highlights → drop → assignment created
- **Visual hierarchy:** Lines/arrows showing reporting structure
- **Dual roles:** Same person can appear in multiple slots (e.g., Sarah as both Strategy Director AND Brand Manager)

**ClickUp Integration:**
- Brand ClickUp Space dropdown populated by API call to ClickUp (`GET /team/{team_id}/space`)
- Manual "Sync" button refreshes list
- Visual indicator if not mapped (⚠️ warning)

**Assignment History:**
- Shows last 10 changes to this client's team
- Displays: timestamp, action, actor
- Stored in `client_assignments` via `assigned_at`, `assigned_by`

**Actions:**
- Edit client metadata (name, status, marketplaces, Slack channels)
- Add/edit/delete brands
- Sync ClickUp
- Assign/unassign team members via drag-and-drop
- Navigate to team member profiles (click name)

---

### 5.4 Team — All

**Route:** `/command-center/team`

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

**Route:** `/command-center/team/[memberId]`

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

**Route:** `/command-center/roles`

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

**Route:** `/command-center/roles/[function]` (e.g., `/catalog`, `/ppc`, `/brand-managers`)

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

### Architecture: Single-Tenant Design

**Important:** Command Center uses a **single-tenant architecture** that differs from the rest of Agency OS.

**Why Single-Tenant?**
- Command Center manages **Ecomlabs' internal operations** (not multi-tenant client data)
- All data is Ecomlabs-specific: employee profiles, agency client accounts, internal team assignments
- No need for `organization_id` filtering—there's only one organization (Ecomlabs)

**Implications:**
- ✅ **No `organization_id` column** in Command Center tables
- ✅ **RLS policies use `is_admin` checks** instead of org-based isolation
- ✅ **All authenticated Ecomlabs employees** can view data (no cross-tenant concerns)
- ✅ **Only admins can modify** data via RLS policies

**Semantic Distinction:**
- `agency_clients` (Command Center) = **Ecomlabs' agency clients** (the brands Ecomlabs serves)
- `client_profiles` (Composer/Ngram) = **Multi-tenant end-user clients** (Composer users' clients)

These are different entities in different domains. Command Center's single-tenant design is intentional and appropriate.

---

### 6.1 Tables & Schema

#### **`public.profiles` (enhanced)**

We are decoupling the Profile ID from the Auth User ID so we can create **Ghost Profiles** for staff who haven’t logged in yet (or never will).

```sql
create table public.profiles (
  id uuid primary key default gen_random_uuid(),  -- Independent (not referencing auth.users directly)
  auth_user_id uuid references auth.users(id) on delete set null, -- Nullable link to login

  email text unique not null,
  display_name text,
  full_name text,
  avatar_url text,

  -- Role & Access
  is_admin boolean default false,
  allowed_tools text[] default '{}',

  -- Status
  employment_status text default 'active' check (employment_status in ('active', 'inactive', 'contractor')),
  bench_status text default 'available' check (bench_status in ('available', 'assigned', 'unavailable')),

  -- External Mappings
  clickup_user_id text unique,
  slack_user_id text unique,

  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Ensure email matching is case-insensitive for link-on-login behavior
create unique index if not exists idx_profiles_email_lower_unique
  on public.profiles (lower(email));

-- Ensure a single auth user links to at most one profile
create unique index if not exists idx_profiles_auth_user_id_unique
  on public.profiles(auth_user_id)
  where auth_user_id is not null;

-- Performance index for RLS policies
create index if not exists idx_profiles_is_admin
  on public.profiles(is_admin)
  where is_admin = true;

-- GIN index for tool access lookups
create index if not exists idx_profiles_allowed_tools
  on public.profiles using gin(allowed_tools);
```

**Important Notes:**
- Admins can create team members without requiring login (Ghost Profiles have `auth_user_id` = NULL).
- If/when a user logs in later, we link `auth.users.id` → `profiles.auth_user_id` by email (see `handle_new_user()` below).
- `employment_status`:
  - `'active'`: Current employee, shows in "The Bench" and assignment interfaces
  - `'inactive'`: Former employee or on leave, excluded from "The Bench" (soft delete)
  - `'contractor'`: Temporary/contract worker, shows in interfaces but marked distinctly
- `bench_status` is derived: 'assigned' if user has any client assignments, else 'available'
- `is_admin` controls access to Command Center admin features
- `allowed_tools`: Array of tool slugs the user can access (see Tool Access Control below)
- **Performance**: The `idx_profiles_is_admin` partial index optimizes RLS policy checks by only indexing admin users. This significantly improves query performance since RLS policies check `is_admin` on every request.

---

#### Tool Access Control

Team members can be granted access to specific tools. Admins can access all tools regardless of this setting.

**Tool Slugs:**
| Tool | Slug |
|------|------|
| N-Gram | `ngram` |
| N-Pat | `npat` |
| Scribe | `scribe` |
| Root Analysis | `root-analysis` |
| AdScope | `adscope` |
| Command Center | `command-center` |
| Debrief | `debrief` |

**Access Logic (Frontend & API):**
```typescript
function canAccessTool(user: Profile, toolSlug: string): boolean {
  // Admins can access all tools
  if (user.is_admin) return true;

  // Non-admins check allowed_tools array
  return user.allowed_tools?.includes(toolSlug) ?? false;
}
```

**UI Considerations:**
- Homepage tool grid only shows tools the user can access
- Sidebar navigation filters out inaccessible tools
- Direct URL access to restricted tool shows "Access Denied" page
- Admin Command Center UI has checkboxes to toggle tool access per team member

**Example:**
```sql
-- Give Sarah access to Scribe and AdScope
update public.profiles
set allowed_tools = array['scribe', 'adscope']
where email = 'sarah@ecomlabs.ca';

-- Give Mike access to all catalog tools
update public.profiles
set allowed_tools = array['scribe', 'ngram', 'npat', 'root-analysis']
where email = 'mike@ecomlabs.ca';
```

---

#### **`public.agency_roles`** (NEW - Dynamic Roles)

We are moving away from the Postgres enum for roles to allow dynamic role creation without database migrations.

```sql
create table public.agency_roles (
  id uuid primary key default gen_random_uuid(),
  slug text unique not null, -- e.g. 'brand_manager'
  name text not null,        -- e.g. 'Brand Manager'
  created_at timestamptz default now()
);

-- Seed data (replaces the old Enum values)
insert into public.agency_roles (slug, name) values
  ('strategy_director', 'Strategy Director'),
  ('brand_manager', 'Brand Manager'),
  ('catalog_strategist', 'Catalog Strategist'),
  ('catalog_specialist', 'Catalog Specialist'),
  ('ppc_strategist', 'PPC Strategist'),
  ('ppc_specialist', 'PPC Specialist'),
  ('report_specialist', 'Report Specialist');
```

---

#### The "Link on Login" Trigger (Replaces Pending Workflow)

This replaces the `team_members_pending` table and enables linking logins to pre-existing Ghost Profiles by email.

```sql
-- Trigger to link specific email logins to pre-existing Ghost Profiles
create or replace function public.handle_new_user()
returns trigger as $$
declare
  existing_profile_id uuid;
begin
  -- Check if a Ghost Profile already exists (case-insensitive)
  select id into existing_profile_id
  from public.profiles
  where lower(email) = lower(new.email);

  if existing_profile_id is not null then
    -- Link existing Ghost Profile to new Auth User
    update public.profiles
    set
      auth_user_id = new.id,
      updated_at = now(),
      avatar_url = coalesce(avatar_url, new.raw_user_meta_data->>'avatar_url')
    where id = existing_profile_id;
  else
    -- Create fresh profile for new user
    insert into public.profiles (auth_user_id, email, full_name, avatar_url)
    values (
      new.id,
      new.email,
      new.raw_user_meta_data->>'full_name',
      new.raw_user_meta_data->>'avatar_url'
    );
  end if;

  return new;
end;
$$ language plpgsql security definer
   set search_path = public;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();
```

---

#### **`public.agency_clients`** (⚠️ Renamed to avoid conflict with `client_profiles`)

Represents Ecomlabs' client accounts (e.g., SB Supply). Distinct from `client_profiles` which represents external users of Composer/Ngram.

```sql
create table public.agency_clients (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  logo_url text,
  website_url text,
  description text,
  amazon_marketplaces text[] default '{}',
  notes text,
  slack_channel_internal text,
  slack_channel_external text,
  status text default 'active' check (status in ('active', 'paused', 'churned')),
  archived_at timestamptz,
  created_at timestamptz default now(),
  created_by uuid references public.profiles(id),
  updated_at timestamptz default now()
);

comment on column public.agency_clients.amazon_marketplaces is 'Array of marketplace codes: US, CA, MX, UK, DE, etc.';

-- Indexes
create index idx_agency_clients_status on public.agency_clients(status) where status = 'active';
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

#### **`public.brands`** (NEW - Multi-Brand Clients)

A client like "SB Supply" may have multiple brands (Whoosh, Ranqer, Lifemate), each with its own ClickUp Space and product catalog.

```sql
create table public.brands (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.agency_clients(id) on delete cascade,
  name text not null,
  clickup_space_id text,
  clickup_space_name text,
  product_keywords text[] default '{}',
  amazon_marketplaces text[] default '{}',
  notes text,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),

  unique (client_id, name)
);

-- Indexes
create index idx_brands_client on public.brands(client_id);
create index idx_brands_clickup on public.brands(clickup_space_id) where clickup_space_id is not null;
create index idx_brands_keywords on public.brands using gin(product_keywords);

-- RLS
alter table public.brands enable row level security;

create policy "Authenticated users can view brands"
  on public.brands for select to authenticated using (true);

create policy "Only admins can manage brands"
  on public.brands for all to authenticated
  using (exists (select 1 from public.profiles where auth_user_id = auth.uid() and is_admin = true))
  with check (exists (select 1 from public.profiles where auth_user_id = auth.uid() and is_admin = true));

-- Trigger for updated_at
create trigger update_brands_updated_at
  before update on public.brands
  for each row execute function update_updated_at_column();
```

**Key Fields:**
- `product_keywords`: Terms to identify this brand in meeting notes (e.g., `["simulator", "wipes", "Pro 2"]`). Used by Debrief for brand detection.
- `amazon_marketplaces`: Which marketplaces this brand sells in (e.g., `["US", "CA"]`).
- `clickup_space_id`: Where tasks for this brand should be created. Each brand can have its own Space.

**Client vs. Brand Example:**

| Client | Brand | ClickUp Space | Keywords |
|--------|-------|---------------|----------|
| SB Supply | Whoosh | Whoosh Space | simulator, wipes |
| SB Supply | Ranqer | Ranqer Space | charger, Pro 2 |
| SB Supply | Lifemate | Lifemate Space | pet, collar |

---

#### **`public.client_assignments` (⭐ Core Junction Table)**

```sql
create table public.client_assignments (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.agency_clients(id) on delete restrict,
  brand_id uuid references public.brands(id), -- Nullable: if NULL, applies to whole client
  team_member_id uuid not null references public.profiles(id) on delete cascade,
  role_id uuid not null references public.agency_roles(id) on delete restrict,
  assigned_at timestamptz default now(),
  assigned_by uuid references public.profiles(id),
);

-- Indexes for common query patterns
create index idx_assignments_client on public.client_assignments(client_id);
create index idx_assignments_member on public.client_assignments(team_member_id);
create index idx_assignments_brand on public.client_assignments(brand_id);
create index idx_assignments_role on public.client_assignments(role_id);
create index idx_assignments_member_client on public.client_assignments(team_member_id, client_id);
create index idx_assignments_client_role on public.client_assignments(client_id, role_id);

-- Constraint: A person can't have the same role for the same scope twice
-- Note: brand_id is nullable, so use partial unique indexes for correct enforcement.
create unique index idx_assignments_unique_brand_scope
  on public.client_assignments (client_id, brand_id, team_member_id, role_id)
  where brand_id is not null;

create unique index idx_assignments_unique_client_scope
  on public.client_assignments (client_id, team_member_id, role_id)
  where brand_id is null;

-- Trigger: Keep bench_status in sync with assignments
-- When assignments change, update the team member's bench_status
create or replace function sync_bench_status()
returns trigger as $$
declare
  member_id uuid;
  has_assignments boolean;
begin
  -- Determine which team member was affected
  if TG_OP = 'DELETE' then
    member_id := OLD.team_member_id;
  else
    member_id := NEW.team_member_id;
  end if;

  -- Check if member has any remaining assignments
  select exists(
    select 1 from public.client_assignments
    where team_member_id = member_id
  ) into has_assignments;

  -- Update bench_status accordingly
  update public.profiles
  set bench_status = case when has_assignments then 'assigned' else 'available' end,
      updated_at = now()
  where id = member_id
    and bench_status != case when has_assignments then 'assigned' else 'available' end;

  if TG_OP = 'DELETE' then
    return OLD;
  else
    return NEW;
  end if;
end;
$$ language plpgsql security definer
   set search_path = public;

create trigger sync_bench_status_on_assignment_change
  after insert or delete on public.client_assignments
  for each row
  execute function sync_bench_status();
```

**Key Design Decision:**
`role_id` is stored **on the assignment**, not on the person. This allows:
- Sarah to be Brand Manager for Client A
- Sarah to be Catalog Strategist for Client B
- Sarah to be BOTH Strategy Director AND Brand Manager for Client C

**Example Rows:**
```
id | client_id | brand_id | team_member_id | role_id            | assigned_at
---+----------+----------+----------------+--------------------+------------
1  | client-a | null     | sarah-123      | brand_manager      | 2025-11-20
2  | client-a | null     | sarah-123      | strategy_director  | 2025-11-20
3  | client-b | whoosh   | sarah-123      | catalog_strategist | 2025-11-21
4  | client-a | ranqer   | mike-456       | ppc_strategist     | 2025-11-20
```

**Delete Behavior:**
- `team_member_id ON DELETE CASCADE`: When a team member's profile is deleted (employee leaves), their assignments are automatically removed. This is correct behavior since assignments are meaningless without the team member.
- `client_id ON DELETE RESTRICT`: When attempting to delete a client, the delete will fail if assignments exist. This prevents accidental data loss. Instead, use the soft-delete pattern by setting `archived_at` on the client (see archiving strategy above). This preserves assignment history for reporting and audit purposes.

**Brand vs. Client Scope (Routing Rule):**
- If a brand-specific assignment exists for a given role (`brand_id = that brand`), it takes precedence.
- Otherwise, fall back to the client-level assignment (`brand_id is null`).

---

### 6.2 Derived Queries

**Get Client Org Chart:**
```sql
	select
	  r.slug as role,
	  r.name as role_name,
	  ca.brand_id,
	  b.name as brand_name,
	  p.id,
	  p.display_name,
	  p.email,
	  ca.assigned_at,
	  assigned_by_profile.display_name as assigned_by_name
	from client_assignments ca
	join agency_roles r on ca.role_id = r.id
	join profiles p on ca.team_member_id = p.id
	left join brands b on ca.brand_id = b.id
	left join profiles assigned_by_profile on ca.assigned_by = assigned_by_profile.id
	where ca.client_id = :clientId
	order by r.slug, ca.assigned_at;
```

**Get Team Member's Assignments (Reverse Org Chart):**
```sql
	select
	  r.slug as role,
	  r.name as role_name,
	  c.id as client_id,
	  c.name as client_name,
	  ca.brand_id,
	  b.name as brand_name,
	  c.status,
	  ca.assigned_at
	from client_assignments ca
	join agency_roles r on ca.role_id = r.id
	join agency_clients c on ca.client_id = c.id
	left join brands b on ca.brand_id = b.id
	where ca.team_member_id = :memberId
	order by r.slug, c.name;
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
      where auth_user_id = auth.uid() and is_admin = true
    )
  )
  with check (
    exists (
      select 1 from public.profiles
      where auth_user_id = auth.uid() and is_admin = true
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
	      where auth_user_id = auth.uid() and is_admin = true
	    )
	  )
	  with check (
	    exists (
	      select 1 from public.profiles
	      where auth_user_id = auth.uid() and is_admin = true
	    )
	  );
```

#### **`public.agency_roles`**

```sql
alter table public.agency_roles enable row level security;

create policy "Authenticated users can view agency roles"
  on public.agency_roles
  for select
  to authenticated
  using (true);

create policy "Only admins can manage agency roles"
  on public.agency_roles
  for all
  to authenticated
  using (
    exists (
      select 1 from public.profiles
      where auth_user_id = auth.uid() and is_admin = true
    )
  )
  with check (
    exists (
      select 1 from public.profiles
      where auth_user_id = auth.uid() and is_admin = true
    )
  );
```

#### **`public.profiles` (Enhanced Policies)**

⚠️ **Security: Only Admins Can Update Profiles**

To prevent privilege escalation (non-admin setting `is_admin = true` on their own profile), **all profile updates require admin access**. Non-admins cannot update any profile, including their own.

```sql
-- All authenticated users can view profiles (team directory)
create policy "Authenticated users can view profiles"
  on public.profiles
  for select
  to authenticated
  using (true);

-- ONLY admins can update ANY profile
-- This prevents privilege escalation where a non-admin could set is_admin = true
create policy "Only admins can update profiles"
  on public.profiles
  for update
  to authenticated
  using (
    exists (
      select 1 from public.profiles
      where auth_user_id = auth.uid() and is_admin = true
    )
  )
  with check (
    exists (
      select 1 from public.profiles
      where auth_user_id = auth.uid() and is_admin = true
    )
  );

-- ONLY admins can insert new Ghost Profiles via Command Center UI.
-- Note: `handle_new_user()` also inserts/updates profiles on login and should run as a privileged role
-- (table owner; do not FORCE RLS on `public.profiles`).
create policy "Only admins can insert profiles"
  on public.profiles
  for insert
  to authenticated
  with check (
    exists (
      select 1 from public.profiles
      where auth_user_id = auth.uid() and is_admin = true
    )
  );

-- Note: DELETE is intentionally not allowed via RLS (use employment_status = 'inactive')
```

**Why Non-Admins Can't Update Their Own Profile:**
- Prevents privilege escalation (setting `is_admin = true`)
- Prevents unauthorized changes to `allowed_tools`, `employment_status`, etc.
- Profile changes (name, avatar) should go through an admin workflow
- If self-service profile editing is needed later, add a separate "Users can update safe fields" policy that explicitly excludes sensitive columns

**Notes:**
- All policies check `is_admin` flag via subquery (not a stored function)
- Authenticated users = anyone logged in via Google SSO
- Admin-only operations: All profile modifications, manage clients, manage assignments
- Read access is open to all authenticated Ecomlabs employees (team directory visibility)

---

## 7. API Surface

All routes are **admin-only** (enforce `is_admin = true` middleware).

### Clients

- `GET /api/command-center/clients` — List all clients with brands
  - Query params: `status`, `search`, `page`, `pageSize`
  - Returns: `{ clients: Client[], total, page, pageSize }`

- `POST /api/command-center/clients` — Create new client
  - Body: `{ name, amazon_marketplaces?, slack_channel_internal?, slack_channel_external?, status? }`
  - Returns: `{ client: Client }`

- `GET /api/command-center/clients/:id` — Get client detail + brands + org chart
  - Returns: `{ client: Client, brands: Brand[], assignments: Assignment[], history: ActivityLog[] }`

- `PATCH /api/command-center/clients/:id` — Update client metadata
  - Body: `{ name?, logo_url?, website_url?, amazon_marketplaces?, slack_*, status? }`
  - Returns: `{ client: Client }`

- `PATCH /api/command-center/clients/:id/archive` — Archive client (soft delete)
  - Body: `{ archived: boolean }` (set to false to unarchive)
  - Sets `archived_at` timestamp or nullifies it
  - Returns: `{ client: Client }`

---

### Brands

- `GET /api/command-center/clients/:clientId/brands` — List brands for client
  - Returns: `{ brands: Brand[] }`

- `POST /api/command-center/clients/:clientId/brands` — Create new brand
  - Body: `{ name, clickup_space_id?, product_keywords?, amazon_marketplaces? }`
  - Returns: `{ brand: Brand }`

- `PATCH /api/command-center/brands/:brandId` — Update brand
  - Body: `{ name?, clickup_space_id?, product_keywords?, amazon_marketplaces?, notes? }`
  - Returns: `{ brand: Brand }`

- `DELETE /api/command-center/brands/:brandId` — Delete brand
  - Returns: `{ success: boolean }`

### Lookup API (for downstream tools)

- `GET /api/command-center/clients/lookup?name=SB%20Supply` — Find client by name (fuzzy match)
- `GET /api/command-center/brands/lookup?keyword=simulator` — Find brand by product keyword
- `GET /api/command-center/brands/:brandId/clickup-space` — Get ClickUp Space ID for brand

---

### Team Members

- `GET /api/command-center/team` — List all team members
  - Query params: `bench_status`, `role_slug`, `is_admin`, `search`, `page`, `pageSize`
  - Returns: `{ members: TeamMember[], bench: TeamMember[], total }`

- `POST /api/command-center/team` — Create new team member
  - Body: `{ email, display_name, is_admin?, clickup_user_id?, slack_user_id?, allowed_tools? }`
  - Returns: `{ member: TeamMember }`

- `GET /api/command-center/team/:id` — Get team member detail + assignments
  - Returns: `{ member: TeamMember, assignments: GroupedAssignment[], history: ActivityLog[] }`

- `PATCH /api/command-center/team/:id` — Update team member metadata
  - Body: `{ display_name?, is_admin?, clickup_user_id?, slack_user_id?, bench_status?, employment_status?, allowed_tools? }`
  - Returns: `{ member: TeamMember }`

- `PATCH /api/command-center/team/:id/employment-status` — Update employment status (soft delete)
  - Body: `{ employment_status: 'active' | 'inactive' | 'contractor' }`
  - Sets status to 'inactive' for offboarding (preserves all assignment history)
  - Inactive members excluded from "The Bench" and assignment interfaces
  - Returns: `{ member: TeamMember }`

---

### Assignments

- `POST /api/command-center/assignments` — Create assignment (drag-and-drop)
  - Body: `{ client_id, brand_id?, team_member_id, role_slug }`
  - Returns: `{ assignment: Assignment }`

- `DELETE /api/command-center/assignments/:id` — Remove assignment
  - Returns: `{ success: boolean }`

- `GET /api/command-center/assignments/client/:clientId` — Get all assignments for client
  - Returns: `{ assignments: Assignment[] }`

- `GET /api/command-center/assignments/member/:memberId` — Get all assignments for member
  - Returns: `{ assignments: Assignment[] }`

---

### ClickUp Integration

- `POST /api/command-center/clickup/sync-spaces` — Manual sync of ClickUp Spaces
  - Hits ClickUp API: `GET /team/{team_id}/space`
  - Returns: `{ spaces: ClickUpSpace[] }`

- `POST /api/command-center/clickup/sync-users` — Manual sync of ClickUp Users
  - Hits ClickUp API: `GET /team/{team_id}/member`
  - Returns: `{ users: ClickUpUser[] }`

**Note:** These syncs also run nightly via `worker-sync` service.

---

### Roles

- `GET /api/command-center/roles` — Get all roles with counts
  - Returns: `{ roles: { id: uuid, slug: string, name: string, count: number }[] }`

- `GET /api/command-center/roles/:slug` — Get team members with specific role
  - Example: `GET /roles/catalog_strategist`
  - Returns: `{ role: { id, slug, name }, members: TeamMember[], assignments: Assignment[] }`

---

## 8. Integration Strategy

### 8.1 ClickUp Integration

**Purpose:** Enable Debrief to create tasks in the right ClickUp Space and assign the right owner

**ClickUp Team ID:** `42600885` (Ecomlabs workspace)

**How to Find Your Team ID:**
If you need to verify or retrieve your ClickUp Team ID in the future, run this command:
```bash
curl -H "Authorization: YOUR_CLICKUP_API_TOKEN" https://api.clickup.com/api/v2/team
```
Look for the `id` field in the response. You'll need this ID for all Space and User sync operations.

**What We Store:**
- Brand → ClickUp Space ID
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

**Debrief Usage:**
```python
# When creating a task for Brand X and assigning it to the right role
brand = get_brand(brand_id)
assignment = get_assignment(brand.client_id, role='ppc_strategist')
team_member = get_team_member(assignment.team_member_id)

# Create task in the brand's ClickUp Space, assigned to the team member's ClickUp User ID
clickup.create_task(
  space_id=brand.clickup_space_id,       # e.g., "90123456"
  assignee=team_member.clickup_user_id,  # e.g., "12345678"
  title="Run negative keyword audit",
  ...
)
```

---

#### 8.1.1 ClickUp Service Architecture

**Design Decision:** Command Center will consume a **shared ClickUp service** rather than calling the ClickUp API directly.

**Rationale:**
- Multiple tools will need ClickUp integration (Command Center, Debrief, future reporting tools)
- Centralized service provides single source of truth for API interactions
- Easier to implement rate limiting, caching, error handling in one place
- When ClickUp API changes, only one service needs updates
- Consistent authentication and logging across all ClickUp operations

**Service Location:** `backend-core/services/clickup_service.py` (FastAPI) or `/api/integrations/clickup/*` (Next.js API routes)

**Command Center Requirements (MVP):**
The ClickUp service must provide these methods for Command Center:

```python
class ClickUpService:
    """Shared ClickUp API service for all Agency OS tools"""

    def __init__(self, api_token: str, team_id: str = "42600885"):
        self.api_token = api_token
        self.team_id = team_id

    # Command Center uses these for mapping UI
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

**Debrief Requirements (Task Creation):**
Debrief creates ClickUp tasks, so the service must support task creation and updates:

```python
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

**Command Center API Routes:**
Command Center's API routes will call the ClickUp service:

```typescript
// /api/command-center/clickup/sync-spaces.ts
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

**Command Center Strategy:**

**Scenario A: Team Member Logs In First**
1. User clicks "Sign in with Google"
2. Supabase creates `auth.users` entry
3. Trigger runs `handle_new_user()` and creates a `public.profiles` row linked via `profiles.auth_user_id`
4. `is_admin = false` by default
5. Admin navigates to Command Center, sees new profile, can assign to clients

**Scenario B: Admin Adds Team Member First (Not Logged In Yet)** ⭐ **Common during onboarding**
1. Admin clicks "+ New Team Member" (pre-login)
2. Admin creates a **Ghost Profile** with: email, name, ClickUp ID, Slack handle (`auth_user_id` is NULL)
3. Admin can immediately assign this profile to clients/brands (no pending state)
4. When Sarah logs in later:
   - Supabase creates `auth.users`
   - Trigger runs `handle_new_user()` and links the existing Ghost Profile by email (`profiles.auth_user_id = auth.users.id`)

**Why this approach?**
- Allows creating staff records without requiring login
- Eliminates the separate “pending” table and linking trigger
- Enables immediate role assignment and ClickUp mapping for new hires/contractors
- Keeps the login linkage deterministic (match by email; see Section 6.1)

**UI Indicator:**
- Ghost Profiles show with badge: "⏳ Not Logged In"
- Linked profiles show: "✅ Linked"

---

### 8.3 Slack Integration (Future)

**Phase 4+ Feature**

**What We'd Store:**
- Client → Internal Slack Channel (`#client-brandx`)
- Client → External Slack Channel (shared Slack Connect)
- Team Member → Slack User ID

**Debrief Usage:**
- Post notifications when meetings are ready for review
- Post confirmation when tasks are created in ClickUp
- (Optional) DM assignees when new tasks are created

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
   • Access Command Center and manage all clients/team
   • View all tools in Agency OS (future)
   • Assign roles and manage assignments

   [Cancel] [Grant Access]
   ```
3. On confirm: `is_admin = true` saved, toast notification
4. Sarah can now access `/command-center` on next login

**Security:**
- Middleware on all Command Center routes checks `is_admin = true`
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
- Admin can map ClickUp Space to brands
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
- All brands have ClickUp Space ID (or warning if missing)
- All active team members have ClickUp User ID (or warning if missing)

✅ **Debrief Enablement**
- Database has all data needed for Debrief to:
  - Find brand's ClickUp Space
  - Find team member's ClickUp User ID
  - Determine who to assign tasks to based on role
  - Identify the right brand from product keywords in meeting notes

---

### Non-Functional Requirements

✅ **Performance**
- Client list loads in <500ms
- Org chart renders in <200ms
- Drag-and-drop has <100ms response time

✅ **Security**
- All Command Center routes enforce admin-only access
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
- **Time Dashboard:** `/command-center/analytics/time`
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
- Debrief sends Slack notifications when tasks are ready/created
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
❌ **Task extraction + ClickUp task creation UX** (handled by Debrief)
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
- Next.js API routes (for Command Center CRUD operations)
- Supabase Postgres (data layer)
- RLS policies (enforce org-level access in future multi-tenant mode)

**Shared Services:**
- **ClickUp Service** (`backend-core/services/clickup_service.py` or `/api/integrations/clickup/*`)
  - Centralized ClickUp API wrapper used by Command Center, Debrief, and future tools
  - Handles authentication, rate limiting, caching, error retry logic
  - Command Center methods: `get_spaces()`, `get_team_members()`
  - Debrief methods: `create_task()`, `update_task()`, `get_tasks()`
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
- Command Center uses new `agency_clients` table

**Migration Steps:**
1. Run schema migration:
   - Create `agency_roles` table + seed default roles
   - Update `profiles` to decoupled IDs (`profiles.id` independent; add nullable `auth_user_id`)
   - Add `handle_new_user()` trigger on `auth.users` to link logins to Ghost Profiles by email
   - Create `agency_clients` table
   - Create `brands` table
   - Create/update `client_assignments` table to include `brand_id` + `role_id`
   - Add indexes (Section 6.1)
   - Enable RLS policies (Section 6.3)
2. Backfill `is_admin = true` for known admins (manually or via script)
3. Backfill `profiles.auth_user_id` for existing users (match `profiles.email` to `auth.users.email`)
4. Verify no application code assumes `profiles.id = auth.uid()` (this becomes `profiles.auth_user_id = auth.uid()`)

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

- [ ] Main Dashboard (Command Center Home)
- [ ] Clients — All (grid view)
- [ ] Clients — Individual (org chart + bench)
- [ ] Team — All (table + bench section)
- [ ] Team — Individual (reverse org chart)
- [ ] Roles — All Functions (grid of function cards)
- [ ] Roles — By Function (e.g., Catalog Team detail)
- [ ] Modals/Forms:
  - [ ] New Client Modal
  - [ ] Edit Client Modal
  - [ ] New Brand Modal
  - [ ] Edit Brand Modal
  - [ ] New Team Member Modal
  - [ ] Edit Team Member Modal
  - [ ] ClickUp Sync Modal (showing fetched spaces/users)
  - [ ] Confirmation Dialogs (remove assignment, toggle admin, delete brand, etc.)

---

## 16. Decisions Made (Post-Review)

**Resolved after Red Team & Supabase Consultant review (2025-11-21):**

1. ✅ **Multi-Tenancy:** Single-tenant (Ecomlabs internal only). No `organization_id` needed in Command Center tables. Documented in Section 6 (Architecture: Single-Tenant Design).
2. ✅ **Pre-Login Team Members:** Use Ghost Profiles (`profiles.auth_user_id` is NULL until first login) and link on login via `handle_new_user()`.
3. ✅ **Admin Model:** `profiles.is_admin` boolean flag (not role enum).
4. ✅ **Table Naming:** `public.agency_clients` (avoids conflict with existing `client_profiles`).
5. ✅ **RLS Policies:** Defined in Section 6.3 (all authenticated can view, only admins can modify). Uses `profiles.is_admin` checks (not JWT role).
6. ✅ **Indexes:** Composite indexes added for common query patterns (org charts, reverse charts, role filtering). Added `idx_profiles_is_admin` partial index for RLS performance.
7. ✅ **Client Archiving:** Soft delete using `archived_at` column. Archived clients excluded from default views, preserves all historical data and assignments.
8. ✅ **Team Member Offboarding:** Soft delete using `employment_status = 'inactive'`. Inactive members excluded from "The Bench" and assignment interfaces, preserves assignment history.
9. ✅ **ClickUp Team ID:** `42600885` (Ecomlabs workspace). Documented in Section 8.1 with "how to find it" instructions.
10. ✅ **ClickUp Service Architecture:** Command Center will consume a shared ClickUp service (not call API directly). Service will be used by Command Center, Debrief, and future tools. Documented in Section 8.1.1 and Section 13.
11. ✅ **Foreign Key Delete Behavior:** `client_id` uses `ON DELETE RESTRICT` (not CASCADE) to prevent accidental data loss. Team members must be explicitly unassigned before deleting clients. Soft-delete via `archived_at` is preferred. Documented in Section 6.1.

**Resolved after Security Review (2025-12-13):**

12. ✅ **Privilege Escalation Prevention:** Only admins can update ANY profile (not just their own). Non-admins cannot update `is_admin`, `allowed_tools`, or `employment_status` even on their own profile. Documented in Section 6.3 (profiles RLS policies).
13. ✅ **Tool Access Control:** Added `allowed_tools text[]` column to profiles. Admins can set which tools each team member can access. Admins bypass the check and see all tools. Tool slugs: `ngram`, `npat`, `scribe`, `root-analysis`, `adscope`, `command-center`, `debrief`. Documented in Section 6.1.
14. ✅ **search_path Hardening:** All security definer functions now include `SET search_path = public` to prevent schema injection attacks. Applied to `handle_new_user()` and `sync_bench_status()`.
15. ✅ **bench_status Sync:** Added `sync_bench_status()` trigger on `client_assignments` to automatically update `profiles.bench_status` when assignments change. Prevents drift between assignment state and profile status.

**Still Open (Require Product Decision):**

1. **Default Max Clients Per Role:** Should we enforce limits? (e.g., "Brand Managers can't exceed 6 clients") **Recommendation:** No limits in MVP, add Phase 4 with hours data.
2. **Assignment Change Notifications:** Should team members receive email/Slack when assigned to new client? **Recommendation:** Deferred to Phase 5 (Slack integration).

**Resolved after PRD Merge (2025-12-13):**

16. ✅ **Merged Team Central + Client Registry → Command Center:** Single unified feature for team, client, and brand management. Client Registry PRD deleted. Brands table added with `product_keywords` for Debrief integration and per-brand ClickUp Space mapping.

---

**End of PRD**
