# Database Docs Policy

## Source Of Truth

- Live Supabase schema and `supabase/migrations/` are canonical.
- `docs/db/schema_master.md` is the generated, current reference.

## Regeneration

- Run `scripts/db/generate-schema-master.sh --linked` after schema migrations when
  your Supabase CLI project link is configured.
- Or run `scripts/db/generate-schema-master.sh --db-url "$SUPABASE_DB_URL"` when
  you want to target a specific remote database explicitly.
- Use `scripts/db/generate-schema-master.sh --check` to detect drift without
  overwriting the file.
- Commit migration + refreshed `docs/db/schema_master.md` in the same PR.

## Legacy Schema Docs

- Files in `docs/archive/**` are historical context, not authoritative schema.
- Keep legacy files for product/history context, but do not treat table definitions there as current.
- For any legacy schema doc that still gets linked, add a short header note: `Historical doc. Current schema: docs/db/schema_master.md`.

## Drift Triage

- If `schema_master.md` disagrees with a non-archive doc, update the doc immediately.
- If `schema_master.md` disagrees with expected product behavior, reconcile via migration first, then regenerate docs.
