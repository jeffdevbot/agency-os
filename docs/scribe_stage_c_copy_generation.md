# Scribe — Stage C Copy Generation (Prompt & Orchestration)

_Status (2025-11-28, EST): Stage C backend + UI shipped; attribute prefs UI is minimal (auto/overrides toggle only) and will be polished. Stage B/C unapprove supported; export CTA added in Stage C UI._

## Inputs (per SKU)
- Product name; SKU code/ASIN
- Brand tone; target audience
- Supplied content
- Variant attributes/values
- Approved topics (5), each with title + 3 bullets (from Stage B)
- Keywords (max 10); customer questions
- Words to avoid
- Attribute-usage preferences (stored in `scribe_skus.attribute_preferences`):
  - Mode: auto (let Scribe decide) or overrides
  - If overrides: per attribute (e.g., Color: Red; Size: Large; Material: Cotton) and selected sections (Title, Bullets, Description, Backend Keywords)
  - Set via `PATCH /projects/:id/skus/:sku_id` with validation for mode and sections

## Output JSON
```json
{
  "title": "...",
  "bullets": ["...", "...", "...", "...", "..."],
  "description": "...",
  "backend_keywords": "...",
  "prompt_version": "scribe_stage_c_v1",
  "model": "...",
  "tokens_in": 0,
  "tokens_out": 0
}
```
- Persisted fields: title, bullets (exactly 5), description, backend_keywords; version increment on regenerate.
- Logged alongside: prompt_version, model, tokens.

## Attribute Handling
- Auto mode: smart defaults—include key attrs (color/size/capacity/material) naturally; avoid repetition/attribute spam; combine where appropriate (e.g., “Red cotton T-shirt”); don’t repeat attrs in every bullet; description mentions attrs sparingly; backend keywords may include synonyms without duplicating title/bullets.
- Overrides mode: inject explicit rules, e.g.:
  - Color: Red → include in TITLE only; do not repeat in bullets/description unless necessary.
  - Size: Large → include in TITLE only.
  - Material: Cotton → include in Bullets and Description; mention at most once in bullets.
- General: avoid repeating attributes across bullets; no attribute stuffing; respect the selected sections.

## Amazon Policy Constraints (prompt + validation)
- Title: ≤ ~200 chars; no ALL CAPS; no emojis/HTML; safe claims.
- Bullets: exactly 5; no emojis/HTML; no medical/prohibited claims; avoid attribute spam.
- Description: plain text; safe claims only.
- Backend keywords: 249 bytes; no ASINs/competitor brands; avoid repeating title/bullets terms; no forbidden terms.

## Job Orchestration
- Precondition: project status `stage_b_approved`; each target SKU has 5 approved topics.
- Request shapes (see canonical API):
  - `POST /projects/:id/generate-copy` — `{ skuIds?: [...], mode?: "all"|"sample" }`
  - `POST /projects/:id/skus/:sku_id/regenerate-copy` — `{ sections?: [...] }` (optional; default full regenerate)
- For each SKU: call prompt → upsert `scribe_generated_content` (bullets=5 enforced; limits enforced; version++ on regenerate; section-scoped overwrite allowed if enabled).
- Errors: record per-SKU errors in job payload; if any fail, job status = failed; approval stays blocked; single attempt per job; no auto-retry; user retries via regenerate; timeout = fail fast.
- Logging: `scribe_usage_logs` per call with tool='scribe', project/user/job/sku, tokens/model/prompt_version.

## Approval & Export
- Approval: `POST /projects/:id/approve-copy` requires generated content per SKU; sets `stage_c_approved` (final `approved` remains reserved).
- Unapprove: `POST /projects/:id/unapprove-copy` allowed only when `stage_c_approved`; reverts status to `stage_b_approved` (copy is retained for rework).
- CSV export: include Stage C fields per SKU (title, bullet_1..5, description, backend_keywords); no Stage C import in v1.
