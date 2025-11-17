# Slice 1 — Surface 3: Product Info Step (Micro-spec)

**File:** `docs/composer/slice_01_product_info_step.md`  
**Related:**  
- `01_schema_tenancy.md`  
- `02_types_canonical.md`  
- `slice_01_shell_intake.md`  

---

## 1. Scope & Purpose

Surface 3 is the **Product Info** step in the Composer wizard.

Its job is to capture all core product context needed before keyword work and copy generation:

1. **Project meta** (what are we writing, for whom, where)  
2. **Brand & product brief** (tone, positioning, constraints)  
3. **SKU intake** (all SKUs/variants for this project)  
4. **Attribute summary** (what attributes exist across SKUs)

This step **does not** perform any AI operations and **does not** touch keyword pools or themes. It is strictly about structured intake and persistence.

---

## 2. Entry & Exit

### 2.1 Entry

- Route: Product Info step inside existing Composer wizard shell  
  - e.g. `/composer/[projectId]/product-info` (or whatever the stepper already uses)
- Preconditions:
  - User is authenticated and has an active `organization_id`.
  - A `composer_projects` row exists for `[projectId]` belonging to this org.
  - Wizard shell is already loading the project and exposing `projectId` + `ComposerProject`.

### 2.2 Exit / “Step Complete”

The step is considered **complete enough to move on** when:

- `project_name` is non-empty.  
- `client_name` is non-empty.  
- At least one `marketplace` is selected.  
- At least one `composer_sku_variants` row exists for the project **with a valid `sku`** (ASIN optional).

The wizard can still allow navigation with warnings, but this is the baseline validation.

---

## 3. UX Overview

The Product Info step is laid out as a **two-column** layout within the wizard shell:

- **Left (main) column:**
  1. Project meta block
  2. Brand & product brief block
  3. FAQ block

- **Right column:**
  1. SKU table (full-width within column)
  2. Attribute summary panel (under table)

### 3.1 Project Meta Block

Fields:

- **Project name** (text, required)  
- **Client / brand name** (text, required)  
- **Marketplaces** (multi-select chip list, e.g. `["US","CA","UK","DE","FR","IT","ES","NL","PL","SE"]`)  
- **Category** (single select or free text; initial implementation can be a simple text input)

Behavior:

- Loads from `ComposerProject` fields mapped as:
  - `project_name`
  - `client_name`
  - `marketplaces` (string[])
  - `category`
- Edits use controlled inputs and autosave (debounced) via a single “Project Meta” update call.

### 3.2 Brand & Product Brief Block

Fields (mapped to `ProductBrief` / project meta):

- **Brand tone** (long text / textarea)  
- **What NOT to say** (list of strings; chips or multi-line repeater)  
- **Product brief** (subfields can be any or all of, depending on canonical type):
  - Target audience  
  - Use cases  
  - Differentiators  
  - Safety notes / warnings  
  - Certifications / claims  
- **Supplied info** (freeform long text to capture anything else the client gave us)

Behavior:

- All fields autosave through the same “Project Meta” endpoint as above.
- No step gating beyond required fields described in §2.2, but missing brief fields may be highlighted as “recommended”.

### 3.3 FAQ Block

Fields:

- Repeater list of items:
  - `question` (required)
  - `answer` (optional)

Behavior:

- Add, edit, remove Q&A rows inline.
- Persisted as `faq: Array<{ question: string; answer?: string }>` in the project meta payload.

### 3.4 SKU Table

Purpose: capture and maintain all SKUs/variants for this project.

Columns:

- **SKU** (required)  
- **ASIN** (optional)  
- **Parent SKU** (optional)  
- **Dynamic attributes** (one column per attribute, e.g. `color`, `size`, `material`, `pack_count`, etc.)  
- **Notes** (optional)

Features:

- **Inline editing**:
  - Clicking a cell allows editing (text inputs).
- **Add row**:
  - Button adds a blank row with focus in the SKU cell.
- **Delete row**:
  - Trash icon / delete action per row.
- **CSV import** (Upload CSV button):
  - Accepts CSV/TSV and returns normalized rows + detected attributes.
  - Imported rows **merge** into the existing table: matching SKUs are updated, new SKUs appended.
- **Autosave**:
  - Inline edits and imports auto-save via the variants API; no manual “Save” button.

Validation:

- Each row:
  - `sku` must be non-empty.
  - `asin` optional; leave blank for new-to-Amazon products.
- Duplicate `(sku)` for the same project should be surfaced as an error.
- Rows with missing required fields get inline error state (e.g., red border + tooltip/message).

### 3.5 Attribute Summary Panel

Purpose: show a concise overview of attribute keys across SKUs (to help think about variations vs distinct products).

Displayed information:

- List of **attribute keys** detected from SKU `attributes` JSON (e.g., `color`, `size`, `material`).  
- For each key:
  - Count of SKUs with a non-empty value (e.g., `color — 10/12 SKUs`).

Behavior:

- Purely read-only in V1.
- Updates live as SKU table changes.

---

## 4. Data Model & Contracts (Conceptual)

> Exact TypeScript interfaces are in `02_types_canonical.md`. This section just defines what this step reads/writes.

### 4.1 Tables Touched

- `composer_projects`
  - Fields relevant to this step (names may differ slightly by schema, but conceptually):
    - `id`
    - `organization_id`
    - `project_name`
    - `client_name`
    - `marketplaces` (string[])
    - `category`
    - `product_brief` (JSONB / structured)
    - `brand_tone` (text)
    - `what_not_to_say` (text[] or JSONB)
    - `supplied_info` (JSONB/text)
    - `faq` (JSONB)
    - `updated_at`, `last_saved_at`

- `composer_sku_variants`
  - Fields:
    - `id`
    - `organization_id`
    - `project_id`
    - `sku` (string, required)
    - `asin` (string, optional)
    - `parent_sku` (string | null)
    - `attributes` (JSONB: `Record<string, string | null>`)
    - `notes` (text | null)
    - `created_at`, `updated_at`

### 4.2 Conceptual DTOs

These are **shapes**; Codex can define them in TS aligned with canonical types.

- **Project Meta Payload**
  - Contains all fields edited in §3.1–3.3 in a single object.
  - Used by a single update endpoint for Product Info.

- **Sku Variant Input**
  - Editable row representation, including `id?`, `sku`, `asin`, `parentSku?`, `attributes`, `notes?`.

- **Import Result**
  - Output from CSV/paste import:
    - `variants: SkuVariantInput[]`
    - `detectedAttributes: string[]`

- **Variants Upsert Payload**
  - Input for batch save:
    - `variants: SkuVariantInput[]`

---

## 5. API Surface (High-level)

Detailed API contracts will live in a separate doc; here is the minimal set for Slice 1 Product Info:

1. **Update project meta (Product Info subset)**  
   - `PATCH /api/composer/projects/:projectId/meta`  
   - Body: Project Meta Payload  
   - Effect: updates only fields related to this step on `composer_projects`.

2. **Import SKUs from CSV/paste**  
   - `POST /api/composer/projects/:projectId/variants/import`  
   - Body: `{ source: "csv" | "paste"; raw: string }`  
   - Effect: parse + normalize; **no DB writes**; returns Import Result.

3. **Batch upsert SKUs**  
   - `PATCH /api/composer/projects/:projectId/variants`  
   - Body: Variants Upsert Payload  
   - Effect: insert/update rows in `composer_sku_variants` for this project/org, enforcing unique `(project_id, sku)`.

4. **Delete SKU variant**  
   - `DELETE /api/composer/projects/:projectId/variants/:variantId`  
   - Effect: removes the variant if it belongs to the org + project.

All endpoints are **org-scoped and RLS-friendly** (must filter by `organization_id` + `project_id`).

---

## 6. Validation Rules

Central rules this step must enforce or surface:

- **Project meta**
  - `project_name`: required, non-empty string.
  - `client_name`: required, non-empty string.
  - `marketplaces`: required, at least length 1.

- **SKU table**
  - At least **one** row with `sku` populated.
  - Each persisted row:
    - `sku` non-empty.
  - Duplicate `sku` within this project should be flagged before save (or cause a clear error on save).

- **FAQ**
  - If present, each `question` must be non-empty; `answer` is optional.

A helper-level validation function (used by the wizard) should produce:

- `isValid: boolean`
- A structured error object summarizing:
  - Missing meta fields
  - Missing SKU data
  - Row-specific errors

---

## 7. Integration Notes (Wizard & Autosave)

- Product Info step **renders inside** the existing wizard layout; it should not reinvent navigation.
- Autosave:
  - Project meta + brief + FAQ use **debounced autosave** via `PATCH /projects/:id/meta`.
  - SKUs use the shared auto-save flow (variants API) so edits/imports persist without a manual save button.
- Wizard “Next” button:
  - Uses the validation rules in §2.2 and §6 to determine if the user can proceed without warnings.
  - The step may allow progression with warnings (implementation detail), but this micro-spec defines the required baseline for “valid”.

---
## 8. Status & Next Steps

- Backend APIs described here (meta PATCH, SKU variants CRUD/import) are implemented and org-scoped with conflict detection/merging.
- Remaining scope for Slice 1 lives in Surface 4 (Content Strategy) — see `docs/composer/slice_01_shell_intake.md` for next steps.
