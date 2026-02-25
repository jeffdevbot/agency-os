# Scribe Lite — Title Blueprint (Project-Level) Spec

**Status:** Draft (design agreed; not implemented yet)

## Problem
Scribe’s current Stage C title generation is LLM-driven and can produce inconsistent ordering/punctuation across SKUs in the same project (e.g., Brand/Size/Material swap positions across variants). This is especially visible in projects with many variant combinations (e.g., 5 sizes × 5 materials = 25 SKUs).

## Goal
Make titles **deterministic and consistent across all SKUs in a project** by introducing a **project-level Title Blueprint** that:
- Defines an ordered sequence of title “blocks” (fixed + variable).
- Uses a **single separator style per project** (e.g., ` - `, ` — `, `, `, ` | `).
- Limits the LLM’s role to a **single “feature phrase” block** that is length-bounded, while the overall title structure is assembled by code.

Non-goals:
- Refactoring Stage A data model or introducing new “project-level fields” beyond existing project config storage.
- Supporting per-SKU “include/exclude” logic for title blocks (assumed not needed).

## Proposed UX (Stage C)
Place Title Blueprint controls inside the existing Stage C preferences area (alongside format/attribute preferences).

### Controls
1. **Separator (project-wide)**
   - Dropdown: ` - `, ` — `, `, `, ` | `.
   - Stored as a literal string (including surrounding spaces).

2. **Title Blueprint builder (drag-and-drop ordered blocks)**
   - Users add blocks from an “Available blocks” list and reorder via drag-and-drop.
   - Blocks are rendered in a simple list with:
     - Block label (e.g., “Product Name”, “Color”, “Size”, “Feature Phrase (AI)”).
     - Optional remove button.

3. **Per-SKU title preview table**
   - Shows each SKU’s assembled title preview + character count (and warnings).
   - Highlights SKUs where:
     - Fixed blocks exceed Amazon’s 200-char title max.
     - Remaining budget for the AI phrase is too small (e.g., <= 0 chars).

### Available blocks (no Stage A refactor)
We will only use existing per-SKU fields plus the project’s existing dynamic variant attributes.

**Fixed/value blocks**
- `Product Name` → `scribe_skus.product_name` (treated as literal; no rewriting)
- Any `Variant Attribute` (dynamic) → from `scribe_variant_attributes` / `scribe_sku_variant_values` (e.g., Size, Material, Brand, Product Line)

**AI block (single)**
- `Feature Phrase (AI)` → a short, human-style feature/benefit phrase generated during Stage C generation.

Note: If a client needs Brand/Product Line included, they can add them as variant attributes and populate the same value across all SKUs (via UI editing or CSV).

## Data Model
Store the blueprint at the **project level** (not per SKU).

### Recommended storage (minimal schema churn)
Extend the existing JSON column:
- `scribe_projects.format_preferences` (jsonb)

Add a nested shape (example):
```json
{
  "bulletCapsHeaders": true,
  "descriptionParagraphs": true,
  "title": {
    "separator": " - ",
    "blocks": [
      { "type": "sku_field", "key": "product_name" },
      { "type": "variant_attribute", "attributeId": "uuid-of-size-attr" },
      { "type": "variant_attribute", "attributeId": "uuid-of-material-attr" },
      { "type": "llm_phrase", "key": "feature_phrase" }
    ]
  }
}
```

Notes:
- `separator` is required when `title.blocks` exists.
- Exactly one `llm_phrase` block is supported (by design).

## Title Assembly Rules
Titles are assembled by code as:
1. Evaluate blocks in order for a given SKU.
2. Convert each block to a string value (or empty string).
3. Drop empty values.
4. Join remaining values with the project’s chosen separator.

### Block resolution
- `sku_field:product_name` → `scribe_skus.product_name` (string)
- `variant_attribute:{attributeId}` → value for `(sku_id, attribute_id)` from `scribe_sku_variant_values.value`
- `llm_phrase:feature_phrase` → generated string from Stage C (per SKU)

### Separator enforcement
Use exactly one separator string per project. No mixed punctuation patterns.

## Character Budgeting (Amazon title max = 200 chars)
We compute a per-SKU budget for the AI phrase:
1. Assemble the title **without** the AI phrase block(s).
2. If fixed title is empty, `remaining = 200`.
3. If fixed title is non-empty, `remaining = 200 - fixedTitle.length - separator.length`.

If `remaining <= 0`, the SKU cannot include the AI phrase. The UI should show an error/warning.

## LLM Integration (Single “Feature Phrase” Block)
Instead of asking the model to write the full title, Stage C generation will request:
- bullets/description/backend keywords (existing behavior), and
- **one short `feature_phrase`** that must fit the per-SKU remaining character budget.

### Prompt constraints (feature phrase)
For each SKU:
- Output language: project locale.
- Output must be a single phrase (no separator characters), suitable to be appended as a block.
- Must be **<= remaining chars** (hard cap), and target a word range (models hit words more reliably).
- Avoid prohibited content (existing policy constraints).
- Do not include SKU codes, ASINs, or competitor brands.

### Enforcement strategy
Because char counts are not perfectly reliable:
1. Ask for `feature_phrase` with a hard cap and a suggested word range (e.g., 6–10 words).
2. Validate generated length in code.
3. If too long: run a low-temperature “shorten” retry with the exact cap.
4. If still too long: truncate at a word boundary to the cap (last resort).

## Interaction with Attribute Preferences
Existing per-SKU `attribute_preferences` currently allows forcing attributes into specific sections.

With Title Blueprint enabled:
- **Remove “Title”** as a selectable section from the `attribute_preferences` UI (to avoid conflicts/redundancy).
- Keep options for **bullets / description / backend keywords**.
- Backward compatibility: if stored `attribute_preferences` contains `title`, treat it as deprecated/no-op when Title Blueprint is enabled.

## Validation & Failure Modes
Stage C should surface actionable errors early:
- **Blueprint not configured:** fall back to current behavior (or block generation until configured; TBD during implementation).
- **Fixed blocks exceed 200 chars:** block generation for affected SKUs (recommended) or generate with empty AI phrase and still fail policy (not recommended).
- **Missing required data:** if a chosen attribute is blank for a SKU, omit it (assumes optional) and warn in the preview.

## Implementation Notes (for later)
Expected touchpoints:
- Stage C UI: add “Title Blueprint” builder + preview + save into `scribe_projects.format_preferences.title`.
- Generation: modify Stage C generator to produce `feature_phrase` and assemble `scribe_generated_content.title` deterministically.
- Tests: add unit coverage for title assembly + budgeting + retry/trim logic.

