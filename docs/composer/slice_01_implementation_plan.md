# Slice 1 — Implementation Plan (Shell & Intake)

_Last updated: 2025-11-19_

## Overview
Slice 1 covers the initial Composer experience:
1. **Surface 1 — Project Dashboard:** List + create projects. **Status: Completed (Nov 16)**
2. **Surface 2 — Wizard Frame:** Autosave shell that hosts step components. **Status: Completed (Nov 16)**
3. **Surface 3 — Product Info:** Project basics + SKU intake. **Status: Completed (Nov 17)**
4. **Surface 4 — Content Strategy Selection:** Variation vs Distinct and SKU grouping. **Status: Completed (Nov 19)**

**Slice 1 is feature-complete.** The plan below lists per-surface workstreams: frontend components, API endpoints, DTOs, and utilities/hooks. Schema + canonical types already exist (see `docs/composer/01_schema_tenancy.md` and `/lib/composer/types.ts`).

---

## Surface 1 — Project Dashboard (New/Resume)

### Frontend components
- `app/(protected)/composer/page.tsx` — page shell.
- `ComposerProjectDashboard` — header, filters, list.
- `ComposerProjectFilters` — search + status/strategy selectors.
- `ComposerProjectTable` — renders rows + “Resume” CTA.
- `ComposerEmptyState` — message + “Create Project”.
- `CreateProjectModal` — collects basic info.

### API endpoints
- `GET /api/composer/projects` — supports `search`, `status`, `strategy`, `page`, `pageSize`.
- `POST /api/composer/projects` — body `{ projectName: string; clientName?: string; marketplaces?: string[] }`.

### Types / DTOs
- `ProjectSummary` (subset of `ComposerProject`).
- `GetProjectsParams`, `GetProjectsResponse`.
- `CreateProjectPayload`, `CreateProjectResponse`.

### Utilities / hooks
- `useProjectFilters()` — manages search/status/strategy/page state.
- `useComposerProjects(params)` — fetch + cache projects list.
- `useCreateProject()` — POST + navigation to wizard entry.

---

## Surface 2 — Wizard Frame (Autosave Shell)

### Frontend components
- `app/(protected)/composer/[projectId]/layout.tsx` — tab shell.
- `ComposerWizardHeader` — project meta + autosave indicator.
- `ComposerStepper` — stepper UI.
- `ComposerWizardNav` — prev/next controls.
- `AutosaveToast` — “Saving/Saved/Error” indicator.

### API endpoints
- `GET /api/composer/projects/:id` — fetch project detail.
- `PATCH /api/composer/projects/:id` — update meta/activeStep/status.
- `POST /api/composer/projects/:id/autosave` — optional partial updates for high-frequency autosaves.

### Types / DTOs
- `ProjectDetailResponse` (full `ComposerProject`).
- `UpdateProjectPayload` — partial project fields (name, brand info, activeStep, status).
- `AutosavePayload` — partial composer project fields.

### Utilities / hooks
- `useComposerProject(projectId)` — fetch + cache detail.
- `useAutosaveProject()` — debounced save helper with statuses.
- `getStepLabel(stepId)` — map ID → label.
- `getStepRoute(projectId, stepId)` — consistent routing.

---

## Surface 3 — Product Info (SKU Intake)

### Frontend components
- `ProductInfoStep` — host component.
- `ProjectMetaForm` — project basics, marketplaces, category.
- `BrandGuidelinesForm` — tone, whatNotToSay, supplied info, FAQ.
- `SkuTable` — editable table (add/delete/edit, CSV import, paste).
- `AttributeSummaryPanel` — derived attribute chips/toggles.
- `FaqRepeater` — Q/A repeater.

### API endpoints
- `PATCH /api/composer/projects/:id/meta` — update meta/product brief/brand fields.
- `POST /api/composer/projects/:id/variants/import` — accepts CSV/paste, returns parsed rows + attributes.
- `PATCH /api/composer/projects/:id/variants` — batch upsert SKUs.
- `DELETE /api/composer/projects/:id/variants/:variantId` — remove SKU.

### Types / DTOs
- `ProjectMetaPayload` — { projectName, clientName, marketplaces, category, productBrief, brandTone, whatNotToSay, suppliedInfo, faq }.
- `SkuVariantInput` — { id?, sku, asin, parentSku?, attributes, notes? }.
- `ImportSkuResponse` — { variants: SkuVariantInput[]; detectedAttributes: string[] }.
- `VariantUpsertPayload` — { variants: SkuVariantInput[] }.

### Utilities / hooks
- `useSkuVariants(projectId)` — manages list + optimistic updates.
- `useSkuCsvImport()` — parse CSV/paste.
- `inferAttributes(variants)` — deduce attribute columns.
- `validateProductInfoForm()` — front-end validation helper.

---

## Surface 4 — Content Strategy Selection

**Status: Completed (Nov 19, 2025)**

### Frontend components
- `ContentStrategyStep` — view host (`/app/composer/[projectId]/components/content-strategy/ContentStrategyStep.tsx`).
- `StrategyToggle` — variations vs distinct radio cards.
- `SkuGroupsBuilder` — drag/drop groups and membership.
- `UnassignedSkuList` — list of ungrouped SKUs.
- `GroupCard` — group name/description/assigned SKUs.

### API endpoints (implemented)
- `GET /api/composer/projects/[projectId]/groups` — list all groups for a project (sorted by `sort_order`).
- `POST /api/composer/projects/[projectId]/groups` — create group with `{ name, description? }`.
- `PATCH /api/composer/projects/[projectId]/groups/[groupId]` — update group `{ name?, description?, sortOrder? }`.
- `DELETE /api/composer/projects/[projectId]/groups/[groupId]` — delete empty group (fails if SKUs assigned).
- `POST /api/composer/projects/[projectId]/groups/[groupId]/assign` — assign SKUs with `{ variantIds: string[] }`.
- `POST /api/composer/projects/[projectId]/variants/unassign` — unassign SKUs with `{ variantIds: string[] }`.

### Types / DTOs
- `ComposerSkuGroup` — canonical type from `/lib/composer/types.ts`.
- `CreateGroupPayload` — `{ name: string; description?: string | null }`.
- `UpdateGroupPayload` — `{ name?: string; description?: string | null; sortOrder?: number }`.
- `AssignPayload` — `{ variantIds: string[] }`.
- `UnassignPayload` — `{ variantIds: string[] }`.

### Utilities / hooks
- `useSkuGroups(projectId)` — `/lib/composer/hooks/useSkuGroups.ts` manages groups with optimistic updates; exposes `groups`, `isLoading`, `error`, `refresh`, `createGroup`, `updateGroup`, `deleteGroup`, `assignToGroup`, `unassignVariants`.

---

## Ready-to-Build Checklist (Slice 1)
1. [x] **Docs:** `slice_01_shell_intake.md` + this implementation plan finalized.
2. [x] **APIs:** All endpoints implemented (projects, variants, strategy, groups, autosave).
3. [x] **Routing:** `/composer` dashboard route and wizard `[projectId]` layout scaffolded.
4. [x] **State:** Shared hooks (`useComposerProjects`, `useComposerProject`, `useAutosaveProject`, `useSkuVariants`, `useSkuGroups`) implemented.
5. [x] **Design tokens/components:** Badge, chip, table row primitives using ShadCN components.
6. [ ] **Testing plan:** Unit tests for hooks, integration tests for autosave flows (deferred to hardening phase).
7. [x] **Ops:** Env vars set; API routes use org fallback via Supabase session metadata.

**Slice 1 delivery complete (Nov 19, 2025).** All four surfaces are implemented and functional. Next: begin Slice 2 (Keyword Pipeline).
