# Slice 1 — Implementation Plan (Shell & Intake)

## Overview
Slice 1 covers the initial Composer experience:
1. **Surface 1 — Project Dashboard:** List + create projects.
2. **Surface 2 — Wizard Frame:** Autosave shell that hosts step components.
3. **Surface 3 — Product Info:** Project basics + SKU intake.
4. **Surface 4 — Content Strategy Selection:** Variation vs Distinct and SKU grouping.

The plan below lists per-surface workstreams: frontend components, API endpoints, DTOs, and utilities/hooks. Schema + canonical types already exist (see `docs/composer/01_schema_tenancy.md` and `/lib/composer/types.ts`).

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

### Frontend components
- `ContentStrategyStep` — view host.
- `StrategyToggle` — variations vs distinct radio cards.
- `SkuGroupsBuilder` — drag/drop groups and membership.
- `UnassignedSkuList` — list of ungrouped SKUs.
- `GroupCard` — group name/description/assigned SKUs.

### API endpoints
- `PATCH /api/composer/projects/:id/strategy` — body { strategyType }.
- `POST /api/composer/projects/:id/groups` — create group.
- `PATCH /api/composer/projects/:id/groups/:groupId` — rename/update.
- `POST /api/composer/projects/:id/groups/:groupId/assign` — assign SKUs.
- `DELETE /api/composer/projects/:id/groups/:groupId` — delete empty group.

### Types / DTOs
- `StrategyUpdatePayload` — { strategyType: StrategyType }.
- `SkuGroupInput` — { id?, name, description?, sortOrder? }.
- `AssignSkuPayload` — { variantIds: SkuVariantId[] }.

### Utilities / hooks
- `useStrategy(projectId)` — fetch/update strategy type.
- `useSkuGroups(projectId)` — manage groups + assignments.
- `groupAssignmentMap` helper — variantId → groupId map.
- `canDeleteGroup(groupId)` — ensures group empty before delete.

---

## Ready-to-Build Checklist (Slice 1)
1. **Docs:** `slice_01_shell_intake.md` + this implementation plan finalized.
2. **APIs:** Confirm backend ownership for listed endpoints (projects, variants, strategy, groups, autosave).
3. **Routing:** `/composer` dashboard route and wizard `[projectId]` layout scaffolded.
4. **State:** Shared hooks (`useComposerProjects`, `useComposerProject`, `useAutosaveProject`, `useSkuVariants`, `useSkuGroups`) stubbed.
5. **Design tokens/components:** Badge, chip, table row, drag-and-drop primitives available (or ShadCN equivalents planned).
6. **Testing plan:** Decide on unit tests for hooks, integration tests for autosave flows.
7. **Ops:** Env vars already set; ensure API routes read `current_org_id` via Supabase auth.

Once checklist items are satisfied, we can begin coding the surfaces sequentially (Dashboard → Wizard Frame → Product Info → Strategy Selection).
