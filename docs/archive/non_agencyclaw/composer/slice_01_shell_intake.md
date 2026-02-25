# Slice 1 — Shell & Intake

## Surface 1: Project Dashboard (New/Resume)

### 1. Title & Scope
- **Surface:** Project Dashboard (New/Resume)
- **Scope:** Entry point to Composer. Lists all projects for the current organization, allows creating a new project, and resumes an existing one.

### 2. Goals
- List Composer projects scoped to the current organization (RLS enforced).
- Give enough context (client, status, strategy, step) to decide what to open.
- Create a new project and jump directly into the wizard (Product Info step).
- Resume an existing project at the saved `activeStep`.

### 3. UX Summary
- **Route:** `/composer`.
- **Header:** “Composer Projects” with a primary **New Project** button.
- **Controls:**
  - Search input: “Search by client or project…”
  - Simple filters: Status (All / Draft / In Progress / Ready for Review / Completed), Strategy (All / Variations / Distinct).
- **Project list rows include:**
  - Project Name & Client Name
  - Marketplaces chips (e.g., `US`, `CA`)
  - Strategy badge (“Variations”, “Distinct”, or “Not set”)
  - Status badge (Draft / In Progress / Ready for Review / Completed)
  - Current step label derived from `activeStep` (e.g., “Product Info”, “Keywords”)
  - “Last edited X ago” from `updatedAt`
  - Primary action button: **Resume**
- **Empty state:** message (“No Composer projects yet.”) + CTA to create a project.

### 4. Data & State
- Source: `composer_projects` → mapped to `ComposerProject` summary.
- Required fields per project:
  - `id`, `clientName`, `projectName`, `marketplaces`, `strategyType`, `status`, `activeStep`, `createdAt`, `updatedAt` (or `lastSavedAt`).
- Derived UI fields:
  - Human-readable step label from `activeStep`.
  - Relative “Last edited” timestamp from `updatedAt`/`lastSavedAt`.
- UI state:
  - `search: string`
  - `status: 'all' | ComposerProjectStatus`
  - `strategy: 'all' | 'variations' | 'distinct'`
  - `page: number`, `pageSize: number`

### 5. API Sketch
- `GET /composer/projects`
  - Query params: `search?`, `status?`, `strategy?`, `page?`, `pageSize?`.
  - Returns `{ projects: ProjectSummary[]; page; pageSize; total; }` sorted by `updated_at DESC`.
  - RLS enforces `organization_id` via `current_org_id()`.
- `POST /composer/projects`
  - Body: `{ projectName: string; clientName?: string; marketplaces?: string[] }`.
  - Backend sets `status='draft'`, `active_step='product_info'`, associates org/user, returns new project.
  - Frontend navigates to `/composer/[projectId]/product-info` (wizard entry).

### 6. Out of Scope (Slice 1)
- Delete/archive actions.
- Advanced filtering (date ranges, tags, multi-select statuses, etc.).
- Analytics/metrics columns.
- Bulk operations.

---

## Surface 2: Wizard Frame (Autosave Shell)

### 1. Title & Scope
- **Surface:** Wizard Frame (Autosave Shell)
- **Scope:** Layout for an individual Composer project that loads project data, hosts step components, manages autosave for shared project fields, and tracks `activeStep`/status.

### 2. Goals
- Provide a consistent frame for all Composer steps (header, stepper, autosave status).
- Load project data by `projectId` (org-scoped) and expose to child surfaces.
- Allow child steps to read project state, trigger saves for shared fields, and update `activeStep` when navigating.
- Handle autosave with clear feedback (“Saving… / Saved / Error”) without blocking navigation.

### 3. UX Summary
- **Route:** `/composer/[projectId]` (or equivalent wizard path).
- **Layout:**
  - Header bar with project name/client/marketplaces, status badge, autosave indicator.
  - Stepper or tabs listing Slice 1 steps (Product Info, Content Strategy). Future steps can be appended later.
  - Content area renders current step component (Surface 3 or 4).
- **Navigation:** clicking step labels or using Next/Previous buttons updates `activeStep` and changes the rendered view.
- **Loading/error:** skeleton or spinner while fetching; friendly error state + “Back to dashboard” CTA if project not found/forbidden.

### 4. Data & State
- Uses full `ComposerProject` (canonical type).
- Frame needs `id`, `projectName`, `clientName`, `marketplaces`, `status`, `activeStep`, plus shared meta fields editable by steps.
- Local frame state:
  - `project: ComposerProject | null`
  - Loading/error booleans.
  - `currentStepId`: derived from `project.activeStep`, default to `product_info`.
  - Autosave state: `autosaveStatus` (`idle | saving | saved | error`), optional `lastSavedAt`.
- Step configuration: small array of `{ id, label }` for steps, used by both stepper and navigation logic.

### 5. API Sketch
- `GET /api/composer/projects/:id`
  - Returns full project, RLS enforced by `current_org_id()`.
- `PATCH /api/composer/projects/:id`
  - Accepts partial fields (`projectName`, `clientName`, `marketplaces`, `status`, `activeStep`, etc.).
  - Used for autosave and step transitions.
- (Optional) `POST /api/composer/projects/:id/autosave`
  - Same payload semantics as PATCH; used only if we want a dedicated autosave route.

### 6. Out of Scope (Slice 1)
- Validation rules that lock progression (e.g., enforcing SKUs before strategy).
- Multi-user presence/conflict handling.
- Step-specific persistence for Product Info / Strategy (handled within Surfaces 3 & 4).
- Project history/versioning views.
