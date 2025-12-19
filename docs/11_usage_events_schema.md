# Supabase `usage_events` Table

Snapshot captured from `public.usage_events` via:

```sql
select
    column_name,
    data_type,
    is_nullable,
    column_default
from information_schema.columns
where table_schema = 'public'
  and table_name = 'usage_events'
order by ordinal_position;
```

| Column           | Type                         | Nullable | Default            | Notes |
| ---------------- | ---------------------------- | -------- | ------------------ | ----- |
| `id`             | `uuid`                       | NO       | `gen_random_uuid()`| Primary key |
| `occurred_at`    | `timestamptz`                | NO       | `now()`            | Event timestamp |
| `user_id`        | `uuid`                       | YES      | —                  | Supabase user id (if available) |
| `user_email`     | `text`                       | YES      | —                  | Supabase email |
| `ip`             | `text`                       | YES      | —                  | Request IP captured by backend |
| `file_name`      | `text`                       | YES      | —                  | File uploaded (for tools with uploads) |
| `file_size_bytes`| `bigint`                     | YES      | —                  | Raw upload size |
| `rows_processed` | `integer`                    | YES      | —                  | Domain-specific metric (e.g., rows parsed) |
| `campaigns`      | `integer`                    | YES      | —                  | Domain-specific metric (e.g., campaign count) |
| `tool`           | `text`                       | YES      | —                  | Tool identifier (e.g., `ngram`, `npat`, `root`, `adscope`) |
| `status`         | `text`                       | YES      | —                  | Outcome string (`success`, `error`, …) |
| `duration_ms`    | `integer`                    | YES      | —                  | Processing latency |
| `app_version`    | `text`                       | YES      | —                  | Git/semantic version recorded by tool |
| `meta`           | `jsonb`                      | NO       | `'{}'::jsonb`      | Tool-specific metrics (e.g., `rows_emitted`, memory, etc.) |

When adding new tools:
- Reuse this table for activity logging by inserting a row with the relevant metrics (unused columns can stay `NULL`).
- Prefer adding new metrics to `meta` (JSON) rather than adding columns.
