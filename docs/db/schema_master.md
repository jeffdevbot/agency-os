# Database Schema Master (Supabase)

## Snapshot

- Last verified (UTC): `2026-03-23 20:25:08Z`
- Source: live Supabase introspection via MCP (`supabase.execute_sql` against `information_schema` + `pg_catalog`)
- Schema: `public`
- Relations: `78` total (`77` tables, `1` view, `0` materialized views)
- Columns: `902`
- Primary key entries: `84`
- Foreign key entries: `141`
- Indexes: `306`
- RLS policies: `137`
- Functions: `135`

## Scope Note

This file is the current live schema inventory for the `public` schema.

The repo includes `scripts/db/generate-schema-master.sh`, but this workspace is
not currently linked for `supabase db dump --linked`, so this file was
refreshed directly from live Supabase MCP instead.

## Relations Overview

| Relation | Type | RLS Enabled |
|---|---|---|
| `public.agency_clients` | `table` | `yes` |
| `public.agency_roles` | `table` | `yes` |
| `public.agencyclaw_user_preferences` | `table` | `yes` |
| `public.agent_events` | `table` | `yes` |
| `public.agent_messages` | `table` | `yes` |
| `public.agent_runs` | `table` | `yes` |
| `public.agent_skill_events` | `table` | `yes` |
| `public.agent_tasks` | `table` | `yes` |
| `public.ai_token_usage` | `table` | `yes` |
| `public.app_error_events` | `table` | `yes` |
| `public.brand_market_kpi_targets` | `table` | `yes` |
| `public.brands` | `table` | `yes` |
| `public.clickup_api_credentials` | `table` | `yes` |
| `public.clickup_space_registry` | `table` | `yes` |
| `public.clickup_spaces_cache` | `table` | `yes` |
| `public.clickup_sync_status` | `table` | `yes` |
| `public.clickup_tasks_cache` | `table` | `yes` |
| `public.clickup_users_cache` | `table` | `yes` |
| `public.client_assignments` | `table` | `yes` |
| `public.client_profiles` | `table` | `yes` |
| `public.debrief_extracted_tasks` | `table` | `yes` |
| `public.debrief_meeting_notes` | `table` | `yes` |
| `public.monthly_pnl_cogs_monthly` | `table` | `yes` |
| `public.monthly_pnl_email_drafts` | `table` | `yes` |
| `public.monthly_pnl_import_month_bucket_totals` | `table` | `yes` |
| `public.monthly_pnl_import_month_sku_units` | `table` | `yes` |
| `public.monthly_pnl_import_months` | `table` | `yes` |
| `public.monthly_pnl_imports` | `table` | `yes` |
| `public.monthly_pnl_ledger_entries` | `table` | `yes` |
| `public.monthly_pnl_manual_expense_settings` | `table` | `yes` |
| `public.monthly_pnl_manual_expenses` | `table` | `yes` |
| `public.monthly_pnl_mapping_rules` | `table` | `yes` |
| `public.monthly_pnl_profiles` | `table` | `yes` |
| `public.monthly_pnl_raw_rows` | `table` | `yes` |
| `public.monthly_pnl_sku_cogs` | `table` | `yes` |
| `public.ops_chat_sessions` | `table` | `yes` |
| `public.playbook_slack_sessions` | `table` | `yes` |
| `public.playbook_sops` | `table` | `yes` |
| `public.profiles` | `table` | `yes` |
| `public.report_api_connections` | `table` | `yes` |
| `public.scribe_customer_questions` | `table` | `yes` |
| `public.scribe_generated_content` | `table` | `yes` |
| `public.scribe_generation_jobs` | `table` | `yes` |
| `public.scribe_keywords` | `table` | `yes` |
| `public.scribe_projects` | `table` | `yes` |
| `public.scribe_sku_variant_values` | `table` | `yes` |
| `public.scribe_skus` | `table` | `yes` |
| `public.scribe_topics` | `table` | `yes` |
| `public.scribe_variant_attributes` | `table` | `yes` |
| `public.skill_catalog` | `table` | `yes` |
| `public.skill_invocation_log` | `table` | `yes` |
| `public.skill_policy_overrides` | `table` | `yes` |
| `public.slack_event_receipts` | `table` | `yes` |
| `public.sops` | `table` | `yes` |
| `public.threshold_rules` | `table` | `yes` |
| `public.usage_events` | `table` | `yes` |
| `public.wbr_ads_campaign_daily` | `table` | `yes` |
| `public.wbr_amazon_ads_connections` | `table` | `yes` |
| `public.wbr_asin_exclusions` | `table` | `yes` |
| `public.wbr_asin_group_mapping` | `table` | `yes` |
| `public.wbr_asin_row_map` | `table` | `yes` |
| `public.wbr_business_asin_daily` | `table` | `yes` |
| `public.wbr_campaign_exclusions` | `table` | `yes` |
| `public.wbr_email_drafts` | `table` | `yes` |
| `public.wbr_ingest_runs` | `table` | `yes` |
| `public.wbr_inventory_asin_snapshots` | `table` | `yes` |
| `public.wbr_listing_import_batches` | `table` | `yes` |
| `public.wbr_pacvue_campaign_map` | `table` | `yes` |
| `public.wbr_pacvue_import_batches` | `table` | `yes` |
| `public.wbr_profile_child_asins` | `table` | `yes` |
| `public.wbr_profiles` | `table` | `yes` |
| `public.wbr_report_snapshots` | `table` | `yes` |
| `public.wbr_returns_asin_daily` | `table` | `yes` |
| `public.wbr_rows` | `table` | `yes` |
| `public.wbr_section1_daily` | `table` | `yes` |
| `public.wbr_section1_weekly` | `view` | `n/a` |
| `public.wbr_sync_runs` | `table` | `yes` |
| `public.wbr_windsor_sales_traffic_raw` | `table` | `yes` |

## Domain Grouping

### Org / Auth / Ops

- `agency_clients`
- `agency_roles`
- `agencyclaw_user_preferences`
- `profiles`
- `client_profiles`
- `client_assignments`
- `brands`
- `brand_market_kpi_targets`
- `usage_events`
- `app_error_events`
- `sops`
- `ops_chat_sessions`

### Agent / Playbook / Slack

- `agent_events`
- `agent_messages`
- `agent_runs`
- `agent_skill_events`
- `agent_tasks`
- `playbook_slack_sessions`
- `playbook_sops`
- `slack_event_receipts`
- `skill_catalog`
- `skill_invocation_log`
- `skill_policy_overrides`
- `threshold_rules`

### ClickUp / Debrief

- `clickup_api_credentials`
- `clickup_space_registry`
- `clickup_spaces_cache`
- `clickup_sync_status`
- `clickup_tasks_cache`
- `clickup_users_cache`
- `debrief_meeting_notes`
- `debrief_extracted_tasks`

### Reporting Integrations

- `report_api_connections`

### Scribe

- `scribe_projects`
- `scribe_skus`
- `scribe_keywords`
- `scribe_topics`
- `scribe_generated_content`
- `scribe_generation_jobs`
- `scribe_customer_questions`
- `scribe_variant_attributes`
- `scribe_sku_variant_values`
- `ai_token_usage`

### WBR

- `wbr_profiles`
- `wbr_rows`
- `wbr_sync_runs`
- `wbr_business_asin_daily`
- `wbr_ads_campaign_daily`
- `wbr_inventory_asin_snapshots`
- `wbr_returns_asin_daily`
- `wbr_asin_row_map`
- `wbr_asin_exclusions`
- `wbr_campaign_exclusions`
- `wbr_profile_child_asins`
- `wbr_listing_import_batches`
- `wbr_pacvue_import_batches`
- `wbr_pacvue_campaign_map`
- `wbr_amazon_ads_connections`
- `wbr_ingest_runs`
- `wbr_asin_group_mapping`
- `wbr_report_snapshots`
- `wbr_email_drafts`
- `wbr_section1_daily`
- `wbr_windsor_sales_traffic_raw`
- `wbr_section1_weekly` (view)

### Monthly P&L

- `monthly_pnl_profiles`
- `monthly_pnl_imports`
- `monthly_pnl_import_months`
- `monthly_pnl_raw_rows`
- `monthly_pnl_ledger_entries`
- `monthly_pnl_mapping_rules`
- `monthly_pnl_import_month_bucket_totals`
- `monthly_pnl_import_month_sku_units`
- `monthly_pnl_sku_cogs`
- `monthly_pnl_manual_expense_settings`
- `monthly_pnl_manual_expenses`
- `monthly_pnl_email_drafts`
- `monthly_pnl_cogs_monthly` (legacy / empty retained table)

## Key Reporting Tables

### `public.monthly_pnl_profiles`

- RLS enabled: `yes`
- Primary key: `id`
- Key foreign keys:
  - `client_id -> agency_clients.id`
  - `created_by -> profiles.id`
  - `updated_by -> profiles.id`
- Columns:
  - `id uuid`
  - `client_id uuid`
  - `marketplace_code text`
  - `currency_code text default 'USD'`
  - `status text default 'draft'`
  - `notes text nullable`
  - `created_by uuid nullable`
  - `updated_by uuid nullable`
  - `created_at timestamptz`
  - `updated_at timestamptz`

### `public.monthly_pnl_imports`

- RLS enabled: `yes`
- Primary key: `id`
- Key foreign keys:
  - `profile_id -> monthly_pnl_profiles.id`
  - `supersedes_import_id -> monthly_pnl_imports.id`
  - `initiated_by -> profiles.id`
- Columns:
  - `id uuid`
  - `profile_id uuid`
  - `source_type text`
  - `period_start date nullable`
  - `period_end date nullable`
  - `source_filename text nullable`
  - `storage_path text nullable`
  - `source_file_sha256 text nullable`
  - `import_scope text nullable`
  - `supersedes_import_id uuid nullable`
  - `import_status text default 'pending'`
  - `row_count int4 default 0`
  - `error_message text nullable`
  - `raw_meta jsonb default '{}'`
  - `initiated_by uuid nullable`
  - `started_at timestamptz nullable`
  - `finished_at timestamptz nullable`
  - `created_at timestamptz`
  - `updated_at timestamptz`

### `public.monthly_pnl_import_months`

- RLS enabled: `yes`
- Primary key: `id`
- Key foreign keys:
  - `profile_id -> monthly_pnl_profiles.id`
  - `import_id -> monthly_pnl_imports.id`
  - `supersedes_import_month_id -> monthly_pnl_import_months.id`
- Columns:
  - `id uuid`
  - `profile_id uuid`
  - `import_id uuid`
  - `source_type text`
  - `entry_month date`
  - `import_status text default 'pending'`
  - `is_active bool default false`
  - `supersedes_import_month_id uuid nullable`
  - `raw_row_count int4 default 0`
  - `ledger_row_count int4 default 0`
  - `mapped_amount numeric default 0`
  - `unmapped_amount numeric default 0`
  - `created_at timestamptz`
  - `updated_at timestamptz`

### `public.monthly_pnl_raw_rows`

- RLS enabled: `yes`
- Primary key: `id`
- Key foreign keys:
  - `import_id -> monthly_pnl_imports.id`
  - `profile_id -> monthly_pnl_profiles.id`
  - `import_month_id -> monthly_pnl_import_months.id`
- Columns:
  - `id uuid`
  - `import_id uuid`
  - `profile_id uuid`
  - `import_month_id uuid nullable`
  - `source_type text`
  - `row_index int4`
  - `posted_at timestamptz nullable`
  - `order_id text nullable`
  - `sku text nullable`
  - `raw_type text nullable`
  - `raw_description text nullable`
  - `release_at timestamptz nullable`
  - `raw_payload jsonb default '{}'`
  - `created_at timestamptz`
  - `updated_at timestamptz`

### `public.monthly_pnl_ledger_entries`

- RLS enabled: `yes`
- Primary key: `id`
- Key foreign keys:
  - `profile_id -> monthly_pnl_profiles.id`
  - `import_id -> monthly_pnl_imports.id`
  - `import_month_id -> monthly_pnl_import_months.id`
  - `mapping_rule_id -> monthly_pnl_mapping_rules.id`
- Columns:
  - `id uuid`
  - `profile_id uuid`
  - `import_id uuid`
  - `import_month_id uuid nullable`
  - `entry_month date`
  - `posted_at timestamptz nullable`
  - `order_id text nullable`
  - `sku text nullable`
  - `source_type text`
  - `source_subtype text nullable`
  - `raw_type text nullable`
  - `raw_description text nullable`
  - `ledger_bucket text`
  - `amount numeric`
  - `currency_code text default 'USD'`
  - `is_mapped bool default false`
  - `mapping_rule_id uuid nullable`
  - `source_row_index int4 nullable`
  - `raw_payload jsonb default '{}'`
  - `created_at timestamptz`
  - `updated_at timestamptz`

### `public.monthly_pnl_mapping_rules`

- RLS enabled: `yes`
- Primary key: `id`
- Key foreign keys:
  - `profile_id -> monthly_pnl_profiles.id`
- Columns:
  - `id uuid`
  - `profile_id uuid nullable`
  - `marketplace_code text default 'US'`
  - `source_type text`
  - `match_spec jsonb default '{}'`
  - `match_operator text default 'exact_fields'`
  - `target_bucket text`
  - `priority int4 default 100`
  - `active bool default true`
  - `created_at timestamptz`
  - `updated_at timestamptz`

### `public.monthly_pnl_import_month_bucket_totals`

- RLS enabled: `yes`
- Primary key: `id`
- Key foreign keys:
  - `profile_id -> monthly_pnl_profiles.id`
  - `import_id -> monthly_pnl_imports.id`
  - `import_month_id -> monthly_pnl_import_months.id`
- Columns:
  - `id uuid`
  - `profile_id uuid`
  - `import_id uuid`
  - `import_month_id uuid`
  - `entry_month date`
  - `ledger_bucket text`
  - `amount numeric default 0`
  - `created_at timestamptz`
  - `updated_at timestamptz`

### `public.monthly_pnl_import_month_sku_units`

- RLS enabled: `yes`
- Primary key: `id`
- Key foreign keys:
  - `import_id -> monthly_pnl_imports.id`
  - `import_month_id -> monthly_pnl_import_months.id`
  - `profile_id -> monthly_pnl_profiles.id`
- Columns:
  - `id uuid`
  - `import_id uuid`
  - `import_month_id uuid`
  - `profile_id uuid`
  - `entry_month date`
  - `sku text`
  - `net_units int4`
  - `order_row_count int4 default 0`
  - `refund_row_count int4 default 0`
  - `created_at timestamptz`
  - `updated_at timestamptz`

### `public.monthly_pnl_sku_cogs`

- RLS enabled: `yes`
- Primary key: `id`
- Key foreign keys:
  - `profile_id -> monthly_pnl_profiles.id`
- Columns:
  - `id uuid`
  - `profile_id uuid`
  - `sku text`
  - `asin text nullable`
  - `unit_cost numeric`
  - `currency_code text default 'USD'`
  - `notes text nullable`
  - `created_at timestamptz`
  - `updated_at timestamptz`

### `public.monthly_pnl_cogs_monthly`

- RLS enabled: `yes`
- Primary key: `id`
- Current status: `legacy / empty retained table` (live SKU-based COGS now uses
  `monthly_pnl_import_month_sku_units` + `monthly_pnl_sku_cogs`)
- Key foreign keys:
  - `profile_id -> monthly_pnl_profiles.id`
  - `source_import_id -> monthly_pnl_imports.id`
- Columns:
  - `id uuid`
  - `profile_id uuid`
  - `entry_month date`
  - `sku text nullable`
  - `asin text nullable`
  - `amount numeric`
  - `currency_code text default 'USD'`
  - `source_import_id uuid nullable`
  - `created_at timestamptz`
  - `updated_at timestamptz`

### `public.monthly_pnl_manual_expense_settings`

- RLS enabled: `yes`
- Primary key: `id`
- Key foreign keys:
  - `profile_id -> monthly_pnl_profiles.id`
- Columns:
  - `id uuid`
  - `profile_id uuid`
  - `expense_key text`
  - `is_enabled bool default false`
  - `created_at timestamptz`
  - `updated_at timestamptz`

### `public.monthly_pnl_manual_expenses`

- RLS enabled: `yes`
- Primary key: `id`
- Key foreign keys:
  - `profile_id -> monthly_pnl_profiles.id`
- Columns:
  - `id uuid`
  - `profile_id uuid`
  - `entry_month date`
  - `expense_key text`
  - `amount numeric`
  - `notes text nullable`
  - `created_at timestamptz`
  - `updated_at timestamptz`

### `public.monthly_pnl_email_drafts`

- RLS enabled: `yes`
- Primary key: `id`
- Key foreign keys:
  - `client_id -> agency_clients.id`
  - `created_by -> profiles.id`
- Columns:
  - `id uuid`
  - `client_id uuid`
  - `report_month date`
  - `draft_kind text`
  - `prompt_version text`
  - `comparison_mode_requested text`
  - `comparison_mode_used text`
  - `marketplace_scope text`
  - `profile_ids jsonb`
  - `brief_payload jsonb`
  - `subject text`
  - `body text`
  - `model text nullable`
  - `created_by uuid nullable`
  - `created_at timestamptz`

### `public.report_api_connections`

- RLS enabled: `yes`
- Primary key: `id`
- Key foreign keys:
  - `client_id -> agency_clients.id`
  - `created_by -> profiles.id`
  - `updated_by -> profiles.id`
- Columns:
  - `id uuid`
  - `client_id uuid`
  - `provider text`
  - `connection_status text default 'connected'`
  - `external_account_id text nullable`
  - `refresh_token text nullable`
  - `region_code text nullable`
  - `access_meta jsonb default '{}'`
  - `connected_at timestamptz nullable`
  - `last_validated_at timestamptz nullable`
  - `last_error text nullable`
  - `created_by uuid nullable`
  - `updated_by uuid nullable`
  - `created_at timestamptz`
  - `updated_at timestamptz`

### `public.wbr_profiles`

- RLS enabled: `yes`
- Primary key: `id`
- Key foreign keys:
  - `client_id -> agency_clients.id`
  - `created_by -> profiles.id`
  - `updated_by -> profiles.id`
- Columns:
  - `id uuid`
  - `client_id uuid`
  - `marketplace_code text`
  - `display_name text`
  - `week_start_day text`
  - `status text default 'draft'`
  - `windsor_account_id text nullable`
  - `amazon_ads_profile_id text nullable`
  - `amazon_ads_account_id text nullable`
  - `backfill_start_date date nullable`
  - `daily_rewrite_days int4 default 14`
  - `created_by uuid nullable`
  - `updated_by uuid nullable`
  - `created_at timestamptz`
  - `updated_at timestamptz`
  - `amazon_ads_refresh_token text nullable`
  - `sp_api_auto_sync_enabled bool default false`
  - `ads_api_auto_sync_enabled bool default false`

### `public.wbr_rows`

- RLS enabled: `yes`
- Primary key: `id`
- Key foreign keys:
  - `profile_id -> wbr_profiles.id`
  - `parent_row_id -> wbr_rows.id`
  - `created_by -> profiles.id`
  - `updated_by -> profiles.id`
- Columns:
  - `id uuid`
  - `profile_id uuid`
  - `row_label text`
  - `row_kind text`
  - `parent_row_id uuid nullable`
  - `sort_order int4 default 0`
  - `active bool default true`
  - `created_by uuid nullable`
  - `updated_by uuid nullable`
  - `created_at timestamptz`
  - `updated_at timestamptz`

### `public.wbr_sync_runs`

- RLS enabled: `yes`
- Primary key: `id`
- Key foreign keys:
  - `profile_id -> wbr_profiles.id`
  - `initiated_by -> profiles.id`
- Columns:
  - `id uuid`
  - `profile_id uuid`
  - `source_type text`
  - `job_type text`
  - `date_from date nullable`
  - `date_to date nullable`
  - `status text default 'running'`
  - `rows_fetched int4 default 0`
  - `rows_loaded int4 default 0`
  - `request_meta jsonb default '{}'`
  - `error_message text nullable`
  - `initiated_by uuid nullable`
  - `started_at timestamptz`
  - `finished_at timestamptz nullable`
  - `created_at timestamptz`
  - `updated_at timestamptz`

### `public.wbr_report_snapshots`

- RLS enabled: `yes`
- Primary key: `id`
- Key foreign keys:
  - `profile_id -> wbr_profiles.id`
  - `created_by -> profiles.id`
- Columns:
  - `id uuid`
  - `profile_id uuid`
  - `snapshot_kind text`
  - `week_count int4`
  - `week_ending date nullable`
  - `window_start date`
  - `window_end date`
  - `source_run_at timestamptz default now()`
  - `digest_version text`
  - `digest jsonb`
  - `raw_report jsonb nullable`
  - `created_by uuid nullable`
  - `created_at timestamptz`

### `public.wbr_asin_exclusions`

- RLS enabled: `yes`
- Primary key: `id`
- Key foreign keys:
  - `profile_id -> wbr_profiles.id`
  - `created_by -> profiles.id`
  - `updated_by -> profiles.id`
- Columns:
  - `id uuid`
  - `profile_id uuid`
  - `child_asin text`
  - `exclusion_source text default 'manual'`
  - `exclusion_reason text nullable`
  - `active bool default true`
  - `created_by uuid nullable`
  - `updated_by uuid nullable`
  - `created_at timestamptz`
  - `updated_at timestamptz`

### `public.wbr_campaign_exclusions`

- RLS enabled: `yes`
- Primary key: `id`
- Key foreign keys:
  - `profile_id -> wbr_profiles.id`
  - `created_by -> profiles.id`
  - `updated_by -> profiles.id`
- Columns:
  - `id uuid`
  - `profile_id uuid`
  - `campaign_name text`
  - `exclusion_source text default 'manual'`
  - `exclusion_reason text nullable`
  - `active bool default true`
  - `created_by uuid nullable`
  - `updated_by uuid nullable`
  - `created_at timestamptz`
  - `updated_at timestamptz`

### `public.wbr_email_drafts`

- RLS enabled: `yes`
- Primary key: `id`
- Key foreign keys:
  - `client_id -> agency_clients.id`
  - `created_by -> profiles.id`
- Columns:
  - `id uuid`
  - `client_id uuid`
  - `snapshot_group_key text`
  - `draft_kind text`
  - `prompt_version text`
  - `marketplace_scope text`
  - `snapshot_ids jsonb`
  - `subject text`
  - `body text`
  - `model text nullable`
  - `created_by uuid nullable`
  - `created_at timestamptz`

### `public.wbr_section1_weekly`

- Type: `view`
- Current live view in `public`
- Exposes weekly rollups over WBR Section 1 daily data

## Maintenance

- Regenerate this file from live Supabase after schema changes.
- Treat `supabase/migrations/` + live DB as source of truth.
- If the local script returns a zeroed snapshot, do not commit that output. Refresh the file from direct Supabase MCP introspection instead.
