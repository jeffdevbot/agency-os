# Scribe Lite — Product Requirements Document (PRD)

**Status:** Draft (Waiting for UI Spec)
**Goal:** Rebuild Scribe with a simplified "Wizard" UX, reusing the existing robust backend/DB foundation.

---

## 1. Philosophy: "Scribe Lite"
- **Simplicity First:** No complex inline editing, no "God Components", no "vibe coding" sprawl.
- **Linear Flow:** Step 1 (Inputs) → Step 2 (Topics) → Step 3 (Outputs).
- **Non-Blocking Navigation:** Users can move freely between stages. No "Locking" or "Unapproving".
- **Dirty State Handling:** If upstream inputs change (e.g., Stage A edit), downstream stages (B/C) show a "Stale Data" warning with a "Regenerate" option, but do not auto-wipe data.
- **Explicit Actions:** "Save", "Generate", "Next". No auto-magic state that gets tangled.
- **Code Quality:** Small, focused components. Custom hooks for logic.
- **Component Structure (Critical):**
  - **Lean Orchestrators:** `page.tsx` files must be minimal (5-10 lines) - they only import and render the main component
  - **Main Logic Components:** Create dedicated components (e.g., `StageB.tsx`, `StageC.tsx`) that handle state, data loading, and orchestration
  - **Sub-Components:** Break down UI into smaller, focused components (e.g., `AttributePreferencesCard.tsx`, `GeneratedContentCard.tsx`, `SkuTopicsCard.tsx`)
  - **Pattern Example:**
    ```
    /[projectId]/stage-b/page.tsx (5 lines - lean wrapper)
    /[projectId]/components/StageB.tsx (main orchestrator)
    /[projectId]/components/SkuTopicsCard.tsx (focused UI component)
    /[projectId]/components/DirtyStateWarning.tsx (reusable component)
    ```

---

## 2. Technical Foundation (The "Keep" Stack)

We are retaining the following backend assets which are already production-ready.

### 2.1 Database Schema (Supabase)
*   `scribe_projects`: Project metadata (name, locale, status).
*   `scribe_skus`: Per-SKU data (product info, attributes).
*   `scribe_variant_attributes` & `scribe_sku_variant_values`: Dynamic attributes.
*   `scribe_keywords` & `scribe_customer_questions`: Per-SKU inputs.
*   `scribe_topics`: Generated topics (Stage B).
*   `scribe_generated_content`: Generated copy (Stage C).
*   `scribe_generation_jobs`: Async job tracking.

### 2.2 Core Logic (`frontend-web/src/lib/scribe`)
*   `topicsGenerator.ts`: LLM logic for Stage B.
*   `copyGenerator.ts`: LLM logic for Stage C.
*   `jobProcessor.ts`: Orchestrates the async jobs.

### 2.3 API Routes (`frontend-web/src/app/api/scribe`)
*   CRUD for Projects, SKUs, Keywords, Questions.
*   `generate-topics` & `generate-copy`: Endpoints to trigger jobs.
*   `jobs/:id`: Endpoint to poll status.

---

## 3. UI Specification & API Mapping

*(To be filled after User provides UI drawings/spec)*

### 3.1 Step 1: Inputs (Stage A)

**Layout:** Card-based SKU list + slide-over edit panel.

**Components:**
*   **Project-Level Custom Attributes:**
    *   Input field for pipe-separated attribute names (e.g., `size|color|material`)
    *   Stored as JSON array in `scribe_projects.custom_attributes`
    *   Displayed as pipe-separated string in UI
*   **CSV Download:**
    *   Button: "Download CSV Template"
    *   Generates CSV with all standard fields + custom attributes
    *   Multi-value fields (keywords, questions, words to avoid) are pipe-separated
*   **CSV Upload:**
    *   Button: "Upload CSV"
    *   Upsert logic: Match by SKU code, update if exists, create if new
    *   Marks downstream stages as stale (does not delete)
*   **SKU Cards:**
    *   Display: SKU code, Product name, ASIN, keyword/question counts, last updated
    *   Actions: Edit (opens slide-over), Delete
    *   Empty state: "No SKUs yet. Add your first SKU to begin."
*   **Edit SKU Panel (Slide-Over):**
    *   **Core Fields:** SKU (required), Product Name (required), ASIN (optional)
    *   **Brand Metadata:** Brand tone, Target audience, Supplied content (textareas)
    *   **Multi-Value Lists (pipe-separated textareas):**
        *   Words to avoid (no limit)
        *   Keywords (max 10, live count + validation)
        *   Questions (max 30, live count + validation)
    *   **Custom Attributes:** Dynamic text inputs based on project-level attributes
    *   **Actions:** Cancel, Save Changes

**API Mapping:**
*   List SKUs: `GET /api/scribe/projects/:id/skus`
*   Create SKU: `POST /api/scribe/projects/:id/skus`
*   Update SKU: `PATCH /api/scribe/projects/:id/skus/:skuId`
*   Delete SKU: `DELETE /api/scribe/projects/:id/skus/:skuId`
*   Update Project Attributes: `PATCH /api/scribe/projects/:id`

### 3.2 Step 2: Topics (Stage B)

**Layout:** Same header + progress tracker as Stage A.

**Heading:** "Topic Selection" with instructional text explaining AI generates 7-8 topic angles, user selects 5.

**Components:**
*   **Empty State (No Topics Generated):**
    *   Primary CTA: "Generate Topics" button
    *   Generates 7-8 topics per SKU based on Stage A inputs
    *   Uses async job processing with polling
*   **Topic Selection Interface:**
    *   Grouped by SKU (card per SKU)
    *   Each SKU shows 7-8 topics with checkboxes
    *   Enforces exactly 5 selections per SKU (client + server validation)
    *   Topics display: Title + 3-bullet description (whitespace-pre-line for formatting)
    *   Progress indicator: "X / 5 selected" per SKU
*   **Dirty State Warning:**
    *   Appears if Stage A data changed after topics generated
    *   Shows warning banner with "Regenerate" button
    *   Compares SKU update timestamps vs topic creation timestamps
*   **Navigation:**
    *   Previous: Returns to Stage A
    *   Next: Validates all SKUs have 5 topics selected, proceeds to Stage C

**API Mapping:**
*   Generate: `POST /api/scribe/projects/:id/generate-topics`
*   List Topics: `GET /api/scribe/projects/:id/topics`
*   Update Selection: `PATCH /api/scribe/projects/:id/topics/:topicId` (body: `{ selected: boolean }`)
*   Poll Job: `GET /api/scribe/jobs/:jobId`

### 3.3 Step 3: Output (Stage C)

**Layout:** Same header + progress tracker as Stages A/B.

**Heading:** "Amazon Content Creation" with description: "Generate product titles, bullet points, descriptions, and backend keywords for Amazon listings."

**IMPORTANT:** Before implementing, review `/docs/scribe_lite/scribe_lite_schema_api.md` for complete database schema and API contracts.

---

#### 3.3.1 Generation Control Box (Top of Page)

This single, unified card contains three elements: Attribute Preferences (optional customization) + Generation buttons. It appears at the top of Stage C, above any generated content.

**Visual Layout:**
```
┌─────────────────────────────────────────────────────────────────┐
│ ▶ Attribute Preferences (Optional)                              │
│   Control where custom attributes appear in your content         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│ [Generate Sample (1 SKU)]  [Generate All (X SKUs)]             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Dirty State Warning:**
* When SKUs or topics change after copy has been generated, show a warning banner above the buttons inside this control box.
* CTA: "Regenerate" triggers the Generate All flow (uses existing button handlers) and uses the current generation loading state. When dirty, the "Generate All" button label switches to "Regenerate All" and runs for all SKUs (even if content already exists).
* Based on timestamp comparison: if any SKU `updated_at` or topic `created_at/updated_at` is newer than generated content `updated_at`, the banner appears.

**When Attribute Preferences Expanded:**
```
┌─────────────────────────────────────────────────────────────────┐
│ ▼ Attribute Preferences (Optional)                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│ Specify where custom attributes must appear in generated copy.  │
│                                                                  │
│ 💡 Example: Selling picture frames with "Dimensions"? Check     │
│    "Title" to ensure every title includes dimensions like       │
│    "8x10 Wooden Picture Frame".                                │
│                                                                  │
│ ┌──────────────┬─────────┬──────────┬─────────────┐           │
│ │ Attribute    │ Title   │ Bullets  │ Description │           │
│ ├──────────────┼─────────┼──────────┼─────────────┤           │
│ │ Size         │   ☐     │    ☐     │      ☐      │           │
│ │ Color        │   ☐     │    ☐     │      ☐      │           │
│ │ Material     │   ☐     │    ☑     │      ☐      │           │
│ │ Dimensions   │   ☑     │    ☐     │      ☐      │           │
│ └──────────────┴─────────┴──────────┴─────────────┘           │
│                                                                  │
│ ℹ️  These preferences apply to all SKUs in this project         │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│ [Generate Sample (1 SKU)]  [Generate All (X SKUs)]             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

#### 3.3.2 Attribute Preferences Component Details

**Component:** `AttributePreferencesCard.tsx` (NEW - create from scratch, simpler than existing legacy component)

**Collapsible Behavior:**
*   **Default State:** Collapsed (shows 2-line summary)
*   **Expanded State:** Shows full table + instructions
*   **Toggle:** Click anywhere on header to expand/collapse
*   **Icon:** Chevron right (▶) when collapsed, down (▼) when expanded

**Data Flow:**
1. **Load variant attributes** from API: `GET /api/scribe/projects/:id/variant-attributes`
   - Returns: `[{ id, name, slug, sort_order }, ...]`
   - Example: `[{ id: "...", name: "Size", slug: "size" }, { id: "...", name: "Color", slug: "color" }]`

2. **Load current preferences** (if any): Each SKU has `attribute_preferences` in `scribe_skus` table
   - Initially `null` (no preferences set)
   - Structure when set: `{ mode: "overrides", rules: { "Size": { sections: ["title", "bullets"] } } }`

3. **Display Logic:**
   - If no variant attributes exist → Hide card entirely (nothing to configure)
   - If variant attributes exist → Show card (collapsed by default)

4. **Table Rendering:**
   - Rows: One per variant attribute (from API), sorted by `sort_order`
   - Columns: Attribute Name, Title checkbox, Bullets checkbox, Description checkbox
   - Checkbox state: Read from first SKU's preferences (all SKUs share same prefs)

5. **Save Logic (Optimistic Updates):**
   - When user toggles checkbox:
     - Immediately update UI (optimistic)
     - Build new preferences object: `{ mode: "overrides", rules: { [attrName]: { sections: [...checked] } } }`
     - Send PATCH to **ALL SKUs**: `PATCH /api/scribe/projects/:id/skus/:skuId` with body: `{ attribute_preferences: {...} }`
     - If error: Revert UI change, show error message
   - **Apply to All SKUs:** Since preferences apply project-wide, loop through all SKU IDs and send PATCH to each
   - If NO checkboxes are selected for any attribute: Send `null` (sets mode back to "auto")

**Styling:**
*   Bordered card with light gray background when collapsed
*   White background when expanded
*   Table uses clean borders, adequate padding (16px cells)
*   Checkboxes: Blue accent color (#0a6fd6), 16x16px
*   Info icon + text in muted gray below table

**Edge Cases:**
*   No variant attributes defined in Stage A → Hide card entirely
*   Loading state: Show skeleton/spinner while fetching attributes
*   Save error: Show inline error message, revert checkbox state

---

#### 3.3.3 Generation Buttons

**Location:** Below Attribute Preferences card (or at top if no attributes)

**Visual Design:**
*   Horizontal layout with both buttons side-by-side
*   "Generate Sample" button: Primary blue (#0a6fd6), solid
*   "Generate All" button: Secondary style (white background, blue border)
*   Adequate spacing between buttons (12px gap)

**Button States:**
*   **Before Any Generation:**
    - Generate Sample: Enabled, primary emphasis
    - Generate All: Enabled, secondary style
*   **During Generation:**
    - Active button shows spinner + "Generating..." text
    - Other button disabled
*   **After Sample Generated:**
    - Generate Sample: Changes to "Regenerate Sample"
    - Generate All: Becomes primary emphasis (encourage full generation)

**Behavior:**
1. **Generate Sample:**
   - Picks **first SKU** in list (by sort_order)
   - Sends: `POST /api/scribe/projects/:id/generate-copy` with body: `{ mode: "sample", skuIds: [firstSkuId] }`
   - Returns: `{ jobId }`
   - Poll job status: `GET /api/scribe/jobs/:jobId` every 2 seconds
   - On success: Load generated content, display AmazonProductCard below
   - On error: Show error message

2. **Generate All:**
   - Gets all SKU IDs from project
   - Sends: `POST /api/scribe/projects/:id/generate-copy` with body: `{ mode: "all", skuIds: [...allSkuIds] }`
   - Returns: `{ jobId }`
   - Poll job status with progress updates
   - On success: Load all generated content, display multiple AmazonProductCards
   - Skips SKUs that already have content (preserves manual edits)

**Validation:**
*   Check that all SKUs have exactly 5 selected topics before allowing generation
*   Show error if validation fails: "Please select exactly 5 topics for each SKU in Stage B"

---

#### 3.3.4 Empty State (Before Generation)

**When:** No generated content exists yet

**Display:**
```
┌─────────────────────────────────────────────────────────────────┐
│                                                                  │
│                 No Content Generated Yet                         │
│                                                                  │
│  Start by generating a sample for one SKU to preview the        │
│  output, then generate for all SKUs when you're ready.          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

*   Center-aligned text, muted gray color
*   Appears below Generation Control Box
*   Disappears once any content is generated

---

#### 3.3.5 Implementation Notes

**Attribute Preferences Implementation:**
*   Current UI uses the project-wide preferences card (single table) per 3.3.2.
*   Legacy per-SKU AttributePreferencesCard remains in the repo but is unused; keep it for now to avoid regressions until we formally remove it.

**Required Reading:**
*   `/docs/scribe_lite/scribe_lite_schema_api.md` - Complete schema reference
*   Pay special attention to:
     - Section 1.3: Variant Attributes tables
     - Section 1.2: `scribe_skus.attribute_preferences` field (jsonb)
     - Section 2.3: API endpoints for variant attributes

**Data Structure Reference:**
```typescript
// Variant Attribute (from API)
interface VariantAttribute {
  id: string;
  name: string;  // e.g., "Size", "Color"
  slug: string;  // e.g., "size", "color"
  sort_order: number;
}

// Attribute Preferences (stored in scribe_skus.attribute_preferences)
interface AttributePreferences {
  mode: "auto" | "overrides";
  rules?: {
    [attributeName: string]: {
      sections: ("title" | "bullets" | "description")[];
    };
  };
}

// Examples:
// Auto mode (AI decides): null or { mode: "auto" }
// With overrides: {
//   mode: "overrides",
//   rules: {
//     "Size": { sections: ["title", "bullets"] },
//     "Color": { sections: ["description"] }
//   }
// }
```

**State Management:**
*   Parent component (StageC.tsx) manages:
    - SKU list
    - Variant attributes list
    - Generated content per SKU
    - Generation job polling
*   AttributePreferencesCard manages:
    - Collapsed/expanded state (internal)
    - Checkbox states (derived from first SKU's preferences)
    - Save operations (optimistic updates)

---

#### 3.3.6 After Generation: Content Display

**Components:**

*   **After Sample/Full Generation: Amazon Product Page Cards**
    *   **Card Header (outside mockup area):**
        *   SKU name and product name from Stage A
        *   Action buttons: [Edit] [Regenerate]
    *   **Amazon Product Page Mockup (2-column layout):**
        *   **Column 1 (Left): Product Images**
            *   Wireframe image placeholders (SVG or styled divs)
            *   1 large hero image area + 3-4 smaller thumbnail boxes stacked vertically on the left
            *   Tinted in Amazon orange (#FF9900)
            *   Simple "image icon" to indicate placeholder
        *   **Column 2 (Right): Product Details**
            *   **Title:** Generated product title (14-16px, bold)
            *   **Reviews:** Mock rating display (e.g., "5.0 ★★★★★ 125 ratings") - static/decorative
            *   **Price:** Mock price (e.g., "$XX.XX") - static/decorative placeholder
            *   **"About this item" heading** (bold)
            *   **Bullet points:** 5 generated bullets displayed as list
        *   **Description section (full-width below columns):**
            *   Generated description text
        *   **Card Styling:**
            *   Subtle Amazon orange border (#FF9900, 1-2px)
            *   Light orange background tint (very light, e.g., #FFF9F0 or similar)
            *   Keeps Amazon product page "illusion" without being overwhelming
    *   **Backend Keywords Box (below product mockup):**
        *   Separate box/section clearly distinct from the product page mockup
        *   Shows generated backend keywords (display only, not editable in card view)
        *   Light gray background to differentiate from product page content
    *   **Collapse/Expand Behavior:**
        *   **First SKU:** Expanded by default (shows full card)
        *   **Subsequent SKUs:** Collapsed by default, showing compact preview:
            *   SKU name + title snippet + [Expand] button
        *   Click SKU header or [Expand] to toggle visibility
    *   **After Full Generation:**
        *   List of SKU cards (first expanded, rest collapsed)
        *   Global Actions: "Generate All" button (top), Export CSV button (top or bottom)

**Editing Behavior:**
*   **Edit via Slide-Over Panel** (same pattern as Stage A EditSkuPanel):
    *   Click [Edit] button → Slide-over opens from right
    *   Form fields: Title (input), Bullets (5 textareas), Description (textarea)
    *   Backend Keywords: Display-only field (not editable)
    *   Actions: [Cancel] [Save Changes]
    *   On save: PATCH to API → close panel → refresh card display
*   **Regenerate:** Triggers new generation for that SKU (overwrites any edits)
*   **Generate All:** Skips SKUs with existing content (preserves edits)

**API Mapping:**
*   Generate Sample: `POST /api/scribe/projects/:id/generate-copy` (body: `{ mode: "sample" }`)
*   Generate All: `POST /api/scribe/projects/:id/generate-copy` (body: `{ mode: "all" }`)
*   Get Content: `GET /api/scribe/projects/:id/generated-content/:skuId`
*   Update Content: `PATCH /api/scribe/projects/:id/generated-content/:skuId`
*   Regenerate SKU: `POST /api/scribe/projects/:id/skus/:skuId/regenerate-copy`
*   Poll Job: `GET /api/scribe/jobs/:jobId`

---

## 4. UI Components

### 4.1 Reusable Component: Title Header (`ScribeHeader`)
*   **Purpose:** Universal header for branding consistency.
*   **Content:**
    *   Left-aligned: "SCRIBE" wordmark + Tagline: "Create amazing Amazon copy."
*   **Style:** Minimal, uses existing brand colors/typography.
*   **Usage:** Appears on Home, Project, and all Stages.

### 4.2 Reusable Component: Progress Tracker (`ScribeProgressTracker`)
*   **Purpose:** Visual roadmap (A → B → C) replacing approval locking.
*   **Content:**
    *   Three steps: (A) Enter SKU Data → (B) Generate Topics → (C) Generate Copy.
    *   Includes "Previous" and "Next" buttons below the tracker.
*   **Behavior:**
    *   **Clickable:** All steps are clickable at any time (non-blocking).
    *   **Visual States:** Current (Highlighted), Completed (Filled/Outlined), Incomplete (Grey); implementation keeps the logic lightweight (no strict gating).
    *   **Completeness Logic (current build):**
        *   Stage A: Has at least 1 SKU.
        *   Stage B: Not wired; navigation stays open.
        *   Stage C: Marks complete when any generated content exists.
*   **Props:**
    *   `currentStage` ("A", "B", or "C")
    *   `stageAComplete`, `stageBComplete`, `stageCComplete` (boolean)
    *   `onNavigate` (callback for stage navigation)

### 4.3 Stage C Components

**Component Structure:**
```
/[projectId]/stage-c/page.tsx (5 lines - lean wrapper)
/[projectId]/components/StageC.tsx (main orchestrator)
/[projectId]/components/AttributePreferencesCard.tsx (collapsible preferences UI)
/[projectId]/components/AmazonProductCard.tsx (product page mockup)
/[projectId]/components/EditGeneratedContentPanel.tsx (slide-over edit form)
```

**AmazonProductCard.tsx:**
*   **Purpose:** Display generated content in Amazon product page mockup format
*   **Props:** SKU data, generated content, onEdit, onRegenerate, isExpanded, onToggleExpand
*   **Layout:**
    *   Card header with SKU name + action buttons (outside mockup)
    *   2-column product page mockup (images left, details right)
        *   Description section (full-width)
        *   Backend keywords box (separate, below mockup)
*   **Styling:** Light orange background tint, subtle orange border, Amazon-inspired typography

**EditGeneratedContentPanel.tsx:**
*   **Purpose:** Slide-over form for editing generated content (same pattern as EditSkuPanel)
*   **Props:** skuId, content, onSave, onClose
*   **Form Fields:** Title (input), Bullets (5 textareas), Description (textarea), Backend Keywords (display-only)
*   **Actions:** Cancel, Save Changes

#### 3.3.7 Export CSV (Stage C)
*   **Purpose:** Download Amazon-ready content for all SKUs as CSV.
*   **Columns (ordered):**
    *   `SKU`
    *   `Product Name`
    *   `ASIN` (empty if missing)
    *   Custom attributes — one column per project attribute (sorted by `sort_order`; header uses attribute name; value from SKU’s variant value or empty)
    *   `Product Title`
    *   `Bullet Point 1` … `Bullet Point 5` (pad with empty strings if fewer than 5 bullets)
    *   `Description`
    *   `Backend Keywords`
*   **Backend keywords format:** Space-delimited search terms (Amazon discourages commas; strip commas and collapse multiple spaces if present).
*   **Data source:**
    *   Generated copy from `scribe_generated_content` (title, bullets, description, backend keywords).
    *   Stage A data for SKU/Product Name/ASIN and custom attributes via `scribe_sku_variant_values` + `scribe_variant_attributes`.
    *   Include SKUs without generated content with empty copy fields to keep alignment.
*   **File naming:** `scribe_<project-name-slug>_amazon_content_<YYYYMMDD-HHMM>.csv` (slug: lowercase, spaces→dash, alphanumerics + dashes).
*   **CSV details:** UTF-8 with header row; RFC 4180 quoting/escaping; plain text bullets (no markdown/HTML); preserve locale characters.
*   **Implementation:** Keep `page.tsx` lean; wire the Export button to a dedicated module/route (e.g., `/api/scribe/projects/:id/export-copy`) that streams the CSV.
    *   **API Path (current build):** `GET /api/scribe/projects/:id/export-copy`

## 5. Migration Strategy (The "Archive")

1.  **Archived:** Legacy frontend code moved to `src/app/scribe/_legacy_v1/`.
2.  **Archived:** Legacy documentation moved to `docs/archive/scribe_legacy/`.
3.  **Created:** New component library at `src/app/scribe/components/` (`ScribeHeader`, `ScribeProgressTracker`).
4.  **Status:** Ready for Stage A/B/C implementation once UI specs are provided.
