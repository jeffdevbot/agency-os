# Slice 2 — Implementation Plan (Keyword Pipeline)

**Status:** Draft
**Source PRD:** `docs/04_amazon_composer_prd.md` (v1.6)

## Overview
Slice 2 implements the **Keyword Pipeline**, the engine that powers all downstream content generation. It transforms raw user inputs into structured, approved keyword groups.

**Goal:** "I can upload raw keywords, clean them of junk/competitors, and organize them into logical groups for writing."
> Grouping applies to the Description/Bullets pool. Titles pool stops at the cleaned state (titles are handled per SKU later), but we still run upload + cleanup for titles so they feed backend keywords.

### Scope
1.  **Surface 5 — Keyword Upload:** Ingest raw terms into pools (Description/Bullets + Titles).
2.  **Surface 6 — Keyword Cleanup:** Dedupe, filter (banned/brand), and approve pools.
3.  **Surface 7 — Grouping Plan:** AI-suggested grouping + manual overrides + approval.

---

## 1. State Machine & Transitions

The pipeline enforces a strict approval flow to prevent "garbage in, garbage out."

### States (Per Keyword Pool)
*   `empty`: No keywords uploaded.
*   `uploaded`: Keywords exist but haven't been cleaned.
*   `cleaned`: User has reviewed and approved the cleaned list.
*   `grouped`: User has approved the grouping plan (usually only Description/Bullets).

### Transitions
| Action | From State | To State | Side Effects |
| :--- | :--- | :--- | :--- |
| **Upload/Add Keywords** | `empty`, `uploaded`, `cleaned`, `grouped` | `uploaded` | Resets `cleaned`/`grouped` approvals. Forces re-cleaning. |
| **Approve Cleaning** | `uploaded` | `cleaned` | Unlocks Grouping Step. |
| **Change Grouping Config** | `cleaned`, `grouped` | `cleaned` | Resets grouping approval. Forces re-grouping. |
| **Approve Grouping** | `cleaned` | `grouped` | Unlocks Themes & Content Generation. |

> **Critical Rule:** Modifying the upstream "Raw" or "Cleaned" lists **must** invalidate downstream approvals to ensure consistency.

---

## 2. Surface 5: Keyword Upload (Micro-Spec)

### UX Summary
*   **Scope:** Per-scope (Project vs SKU Group).
*   **Tabs:** "Description & Bullets" (Primary) vs "Titles" (Secondary).
*   **Inputs:** CSV Upload (Drag & Drop), Paste Textarea, Manual Add Input.
*   **Preview:** Read-only list of "Raw Keywords" (deduped on ingest).
*   **CSV Contract:** Single column (`keyword`) header required; max 5k terms per upload; UTF-8; reject files >5 MB with friendly error.

### Data Model
*   `composer_keyword_pools`
    *   `project_id`, optional `group_id`.
    *   `pool_type`: `'body'` | `'titles'`.
    *   `status`: `'empty' | 'uploaded' | 'cleaned' | 'grouped'`.
    *   `raw_keywords` JSONB array (inline up to N terms) + optional `raw_keywords_url` for large uploads.
    *   `cleaned_keywords`, `removed_keywords` JSONB.
    *   `clean_settings`, `cleaned_at`, `grouped_at`, `approved_at`.

### API Endpoints
*   `GET /api/composer/projects/:id/keyword-pools` (list all pools).
*   `POST /api/composer/projects/:id/keyword-pools` (create/append).
    *   Body: `{ poolType, keywords: string[] }`.
    *   Logic: Merges with existing raw list, dedupes case-insensitive. **Resets approval flags.**

---

## 3. Surface 6: Keyword Cleanup (Micro-Spec)

### UX Summary
*   **View:** Split view (Removed vs Cleaned).
*   **Removed Panel:** List of terms removed by system filters.
    *   *Action:* "Restore" (moves back to Cleaned).
*   **Cleaned Panel:** List of valid terms.
    *   *Action:* "Remove" (moves to Removed with reason "manual").
    *   *Action:* Inline Edit (fix typos).
*   **Filters (Toggles):**
    *   "Remove Competitors" (uses global blacklist).
    *   "Remove Brand Name" (uses project client name).
    *   "Remove Colors/Sizes" (optional, uses attribute detection).
*   **Primary Action:** "Approve Cleaning" (locks state).

### Data Model & Rules
*   Fields on `composer_keyword_pools`:
    *   `cleaned_keywords`, `removed_keywords` (with reason enum).
    *   `clean_settings` JSON (removeColors/brand/competitor/stopwords).
    *   `cleaned_at` timestamp and `status='cleaned'` when approved.
*   Cleaning logic (deterministic):
    *   **Duplicates:** case-insensitive exact match after trimming; keep first occurrence.
    *   **Banned/Brand/Competitor:** compare against global lists + project `client_name`/`what_not_to_say`.
    *   **Stop/junk terms:** maintain curated blacklist (e.g., “n/a”, “tbd”).
    *   **Color/Size filters:** optional toggles using attribute detection heuristics (color lexicon, size regex).

### API Endpoints
*   `POST /api/composer/keyword-pools/:id/clean`
    *   Body: `{ config: CleaningConfig }`.
    *   Logic: Runs deterministic filters. Updates `cleaned_keywords` / `removed_keywords`.
*   `PATCH /api/composer/keyword-pools/:id`
    *   Body: `{ cleanedKeywords?, removedKeywords?, approved: boolean }`.
    *   Logic: Handles manual moves/edits and final approval.

---

## 4. Surface 7: Grouping Plan (Micro-Spec)

### UX Summary
*   **Config Panel:**
    *   **Strategy:** Dropdown (`Single Group`, `Per SKU`, `Per Attribute`, `Custom`).
    *   **Attribute:** (If `Per Attribute` selected) Dropdown of attributes (e.g., "Color").
    *   **Target Groups:** (If `Custom`) Number input (e.g., "Create 5 groups").
*   **Preview:**
    *   List of proposed groups with labels (e.g., "Blue Keywords", "Red Keywords").
    *   Keyword count per group.
*   **Manual Overrides:**
    *   Drag & drop keywords between groups.
    *   Rename groups.
*   **Primary Action:** "Approve Grouping".

### Data Model
*   `composer_keyword_groups`: AI output rows per pool (`label`, `phrases[]`, `group_index`, metadata, timestamps).
*   `composer_keyword_group_overrides`: user adjustments (`action`, `phrase`, `target_group_label/index`).
*   Final grouping view = AI groups + overrides merged server-side.

### AI Worker Contract (Grouping)
*   **Model:** `gpt-4o-mini` (High speed/low cost).
*   **Input:**
    ```json
    {
      "keywords": ["blue shirt", "red shirt", "cotton tee"],
      "strategy": "attribute",
      "attribute_values": ["Blue", "Red"],
      "target_count": null
    }
    ```
*   **Output:**
    ```json
    {
      "groups": [
        { "label": "Blue", "keywords": ["blue shirt"] },
        { "label": "Red", "keywords": ["red shirt"] },
        { "label": "General", "keywords": ["cotton tee"] }
      ]
    }
    ```

### API Endpoints
*   `POST /api/composer/keyword-pools/:id/grouping-plan` — persist config + enqueue worker.
*   `GET /api/composer/keyword-pools/:id/groups` — returns `{ groups, overrides, merged }`.
*   `POST /api/composer/keyword-pools/:id/group-overrides` — apply manual drag/drop edits.
*   `DELETE /api/composer/keyword-pools/:id/group-overrides` — reset overrides.
*   `PATCH /api/composer/keyword-pools/:id` — mark grouping approved (`status='grouped'`).

---

## 5. Workstreams

### Frontend
1.  **KeywordUpload:** File dropzone, paste parser, raw list component.
2.  **KeywordCleanup:** Dual-pane list with "move" actions, filter toggles.
3.  **GroupingPlan:** Config form, AI loading state, Group card list (drag/drop).

### Backend
1.  **Pool Service:** CRUD for `keyword_pools`, merge logic.
2.  **Cleaning Service:** Deterministic filter logic (Stopwords, Banned terms).
3.  **Grouping Agent:** OpenAI wrapper for grouping logic.
4.  **State Enforcer:** Middleware/Service logic to reset approvals on upstream changes.

### Verification Plan
*   **Unit Tests:**
    *   `cleanKeywords(raw, config)`: Verify dedupe and blacklist logic.
    *   `mergeKeywords(existing, new)`: Verify set union logic.
*   **Integration Tests:**
    *   Full flow: Upload -> Clean -> Approve -> Group -> Approve.
    *   Regression: Upload new keywords -> Verify `cleaning_approved` becomes false.
