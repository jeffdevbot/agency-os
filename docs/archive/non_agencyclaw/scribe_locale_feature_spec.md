# Scribe: Project Locale Selection Feature Spec

## Goal
Replace the unused "Marketplaces" text field on project creation with a locale dropdown that controls the language/dialect for AI-generated content. **Implemented:** Locale stored on projects; UI uses dropdown; Stage B/C prompts/job runner receive locale.

## Scope
- Schema: Add `locale` column to `scribe_projects`
- UI: Replace marketplace text input with locale dropdown
- Backend: Validate locale, pass to AI generators
- Prompts: Update Stage B & C prompts with locale instruction

---

## 1. Database Schema (implemented)
- Column: `scribe_projects.locale` text NOT NULL default `en-US`
- Constraint: `scribe_projects_locale_check` enforces allowed locales (`en-US`, `en-CA`, `en-GB`, `en-AU`, `fr-CA`, `fr-FR`, `es-MX`, `es-ES`, `de-DE`, `it-IT`, `pt-BR`, `nl-NL`)
- Comment: BCP 47 locale code for content generation (e.g., en-US, fr-CA)

---

## 2. UI Changes

### Project Creation Page (`/scribe`) (implemented)
- Replaced marketplaces text input with a locale dropdown labeled "Language / Marketplace."
- Options: `en-US`, `en-CA`, `en-GB`, `en-AU`, `fr-CA`, `fr-FR`, `es-MX`, `es-ES`, `de-DE`, `it-IT`, `pt-BR`, `nl-NL`.
- Default: `en-US`.

---

## 3. API Changes

### POST `/api/scribe/projects` (implemented)
- Accepts `locale` (required); validated against allowed set; defaults to `en-US` when not provided.
- GETs include `locale` in project responses.

---

## 4. AI Prompt Changes

### Stage B/C prompts (implemented)
- `topicsGenerator` and `copyGenerator` now accept locale and inject a LANGUAGE line in the prompt.
- Job processor fetches project locale and passes it to generators.

---

## 5. Job Processor Changes

### `jobProcessor.ts` (implemented)
- Fetches project locale and passes to Stage B/C generators.

---

## 6. Frontend Project Page Changes

### Load/display locale (partial)
- Locale is fetched as part of project data; list view shows locale. Detail page can optionally display it; locale is not editable post-creation (by design).

---

## 7. Migration for Existing Projects

**Default behavior:**
- All existing projects default to `en-US`
- Migration sets `locale = 'en-US'` for all null values
- No breaking changes (English content continues to work)

---

## 8. Testing

### Unit Tests
- ✅ Locale validation (valid/invalid codes)
- ✅ Prompt building with different locales
- ✅ Default to `en-US` when null

### Integration Tests
- ✅ Create project with locale
- ✅ Generate topics in `fr-CA` → verify French output
- ✅ Generate copy in `en-GB` → verify British spelling

### Manual Testing
1. Create project with `en-GB`
2. Add SKU with keywords: "color", "center"
3. Generate topics → should use "colour", "centre"
4. Generate copy → should use British spelling throughout

---

## 9. Edge Cases

**What if locale is null/missing?**
- Default to `en-US` everywhere

**What about existing generated content?**
- Leave as-is (no regeneration needed)
- Future regenerations use new locale

**Can locale be changed after creation?**
- Not in MVP (locked after creation)
- Could add later with Stage A locking

---

## 10. Out of Scope (Future)

- ❌ Changing locale after project creation
- ❌ Per-SKU locale overrides
- ❌ Locale-specific character limits (all use Amazon EN limits)
- ❌ Translation features

---

## 11. Supported Locales

| Locale Code | Display Name | Amazon Marketplace |
|-------------|--------------|-------------------|
| `en-US` | English (United States) | amazon.com |
| `en-CA` | English (Canada) | amazon.ca |
| `en-GB` | English (United Kingdom) | amazon.co.uk |
| `en-AU` | English (Australia) | amazon.com.au |
| `fr-CA` | French (Canada) | amazon.ca |
| `fr-FR` | French (France) | amazon.fr |
| `es-MX` | Spanish (Mexico) | amazon.com.mx |
| `es-ES` | Spanish (Spain) | amazon.es |
| `de-DE` | German (Germany) | amazon.de |
| `it-IT` | Italian (Italy) | amazon.it |
| `pt-BR` | Portuguese (Brazil) | amazon.com.br |
| `nl-NL` | Dutch (Netherlands) | amazon.nl |

---

## 12. Files to Modify

1. `supabase/migrations/20250XXX_scribe_project_locale.sql` (new)
2. `frontend-web/src/app/scribe/page.tsx` (project creation)
3. `frontend-web/src/app/api/scribe/projects/route.ts` (POST handler)
4. `frontend-web/src/lib/scribe/topicsGenerator.ts` (add locale param)
5. `frontend-web/src/lib/scribe/copyGenerator.ts` (add locale param)
6. `frontend-web/src/lib/scribe/jobProcessor.ts` (pass locale to generators)
7. `docs/scribe_schema_api.md` (update docs)

---

## 13. Implementation Checklist

- [ ] Write migration for `locale` column
- [ ] Run migration on dev database
- [ ] Update project creation UI with dropdown
- [ ] Update POST `/api/scribe/projects` to accept locale
- [ ] Update topicsGenerator to accept locale parameter
- [ ] Update copyGenerator to accept locale parameter
- [ ] Update jobProcessor to fetch and pass locale
- [ ] Update docs/scribe_schema_api.md
- [ ] Write unit tests for locale validation
- [ ] Manual test: Create project in `en-GB` and verify British spelling
- [ ] Manual test: Create project in `fr-FR` and verify French output

---

## 14. Estimated Effort

**Size:** Small/Medium

**Time:** 2-3 hours

**Complexity:** Low (mostly straightforward plumbing)

---

## 15. User-Facing Changes

**Before:**
- Text input: "Marketplaces (comma-separated)"
- No language control

**After:**
- Dropdown: "Language / Marketplace"
- 12 locale options
- Generated content respects locale dialect/language
- British English uses "colour", "centre", etc.
- French generates entirely in French
- German generates entirely in German
