# Database Schema Master (Supabase)

## Snapshot

- Last verified (UTC): `2026-02-25 14:07:18Z`
- Source: live Supabase introspection via MCP (`supabase.execute_sql`)
- Schema: `public`
- Relations: `42` total (`42` tables, `0` views, `0` materialized views)
- Columns: `438`
- Primary key entries: `49`
- Foreign key entries: `59`
- Indexes: `185`
- RLS policies: `68`
- Functions: `100`

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
| `public.ops_chat_sessions` | `table` | `yes` |
| `public.playbook_slack_sessions` | `table` | `yes` |
| `public.playbook_sops` | `table` | `yes` |
| `public.profiles` | `table` | `yes` |
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

## Table Details

### `public.agency_clients`

- RLS enabled: `yes`
- Primary key: `id`
- Foreign keys: `none`
- Policies: `Admins can delete clients` (DELETE); `Admins can insert clients` (INSERT); `Admins can update clients` (UPDATE); `Authenticated users can view clients` (SELECT)
- Indexes (4): `agency_clients_pkey`, `idx_agency_clients_email`, `idx_agency_clients_name`, `idx_agency_clients_status`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | `no` | `gen_random_uuid()` |
| `context_summary` | `text` | `yes` | `` |
| `target_audience` | `text` | `yes` | `` |
| `positioning_notes` | `text` | `yes` | `` |
| `name` | `text` | `no` | `` |
| `company_name` | `text` | `yes` | `` |
| `email` | `text` | `yes` | `` |
| `phone` | `text` | `yes` | `` |
| `status` | `text` | `no` | `'active'::text` |
| `notes` | `text` | `yes` | `` |
| `created_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `updated_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |

### `public.agency_roles`

- RLS enabled: `yes`
- Primary key: `id`
- Foreign keys: `none`
- Policies: `Authenticated users can view roles` (SELECT); `Only admins can manage roles` (ALL)
- Indexes (2): `agency_roles_pkey`, `agency_roles_slug_key`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | `no` | `gen_random_uuid()` |
| `slug` | `text` | `no` | `` |
| `name` | `text` | `no` | `` |
| `created_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |

### `public.agencyclaw_user_preferences`

- RLS enabled: `yes`
- Primary key: `id`
- Foreign keys: `agencyclaw_user_preferences_default_client_id_fkey`: (default_client_id) -> `public.agency_clients`(id); `agencyclaw_user_preferences_profile_id_fkey`: (profile_id) -> `public.profiles`(id)
- Policies: `Authenticated users can view own preferences` (SELECT); `Users manage own preferences` (ALL)
- Indexes (3): `agencyclaw_user_preferences_pkey`, `agencyclaw_user_preferences_profile_id_key`, `idx_user_prefs_profile`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | `no` | `gen_random_uuid()` |
| `profile_id` | `uuid` | `no` | `` |
| `default_client_id` | `uuid` | `yes` | `` |
| `preferences` | `jsonb` | `no` | `'{}'::jsonb` |
| `created_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `updated_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |

### `public.agent_events`

- RLS enabled: `yes`
- Primary key: `id`
- Foreign keys: `agent_events_client_id_fkey`: (client_id) -> `public.agency_clients`(id); `agent_events_employee_id_fkey`: (employee_id) -> `public.profiles`(id); `agent_events_sop_id_fkey`: (sop_id) -> `public.playbook_sops`(id)
- Policies: `Only admins can manage agent events` (ALL); `Only admins can view agent events` (SELECT)
- Indexes (5): `agent_events_pkey`, `idx_agent_events_client_created`, `idx_agent_events_employee_created`, `idx_agent_events_event_type_created`, `idx_agent_events_sop_created`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | `no` | `gen_random_uuid()` |
| `event_type` | `text` | `no` | `` |
| `client_id` | `uuid` | `yes` | `` |
| `employee_id` | `uuid` | `yes` | `` |
| `payload` | `jsonb` | `no` | `'{}'::jsonb` |
| `confidence_level` | `text` | `yes` | `` |
| `sop_id` | `uuid` | `yes` | `` |
| `created_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |

### `public.agent_messages`

- RLS enabled: `yes`
- Primary key: `id`
- Foreign keys: `agent_messages_run_id_fkey`: (run_id) -> `public.agent_runs`(id)
- Policies: `none`
- Indexes (2): `agent_messages_pkey`, `idx_agent_messages_run_created`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | `no` | `gen_random_uuid()` |
| `run_id` | `uuid` | `no` | `` |
| `role` | `text` | `no` | `` |
| `content` | `jsonb` | `no` | `` |
| `summary` | `text` | `yes` | `` |
| `created_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |

### `public.agent_runs`

- RLS enabled: `yes`
- Primary key: `id`
- Foreign keys: `agent_runs_actor_profile_id_fkey`: (actor_profile_id) -> `public.profiles`(id); `agent_runs_client_id_fkey`: (client_id) -> `public.agency_clients`(id); `agent_runs_parent_run_id_fkey`: (parent_run_id) -> `public.agent_runs`(id); `agent_runs_session_id_fkey`: (session_id) -> `public.playbook_slack_sessions`(id); `agent_runs_skill_id_fkey`: (skill_id) -> `public.skill_catalog`(id)
- Policies: `Only admins can manage agent runs` (ALL); `Only admins can view agent runs` (SELECT)
- Indexes (10): `agent_runs_pkey`, `idx_agent_runs_active_scope`, `idx_agent_runs_actor_created`, `idx_agent_runs_client_created`, `idx_agent_runs_parent`, `idx_agent_runs_session_started`, `idx_agent_runs_skill_created`, `idx_agent_runs_status_created`, `idx_agent_runs_trace`, `idx_agent_runs_type_key_created`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | `no` | `gen_random_uuid()` |
| `thread_ts` | `text` | `yes` | `` |
| `source` | `text` | `yes` | `` |
| `input_payload` | `jsonb` | `no` | `'{}'::jsonb` |
| `output_payload` | `jsonb` | `no` | `'{}'::jsonb` |
| `error_message` | `text` | `yes` | `` |
| `started_at` | `timestamp with time zone (timestamptz)` | `yes` | `` |
| `completed_at` | `timestamp with time zone (timestamptz)` | `yes` | `` |
| `created_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `updated_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `session_id` | `uuid` | `yes` | `` |
| `run_type` | `text` | `no` | `` |
| `trace_id` | `uuid` | `no` | `gen_random_uuid()` |
| `run_key` | `text` | `no` | `` |
| `status` | `text` | `no` | `'queued'::text` |
| `parent_run_id` | `uuid` | `yes` | `` |
| `actor_profile_id` | `uuid` | `yes` | `` |
| `client_id` | `uuid` | `yes` | `` |
| `skill_id` | `text` | `yes` | `` |
| `channel_id` | `text` | `yes` | `` |

### `public.agent_skill_events`

- RLS enabled: `yes`
- Primary key: `id`
- Foreign keys: `agent_skill_events_run_id_fkey`: (run_id) -> `public.agent_runs`(id)
- Policies: `none`
- Indexes (2): `agent_skill_events_pkey`, `idx_agent_skill_events_run_created`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | `no` | `gen_random_uuid()` |
| `run_id` | `uuid` | `no` | `` |
| `event_type` | `text` | `no` | `` |
| `skill_id` | `text` | `no` | `` |
| `payload` | `jsonb` | `no` | `` |
| `payload_summary` | `text` | `yes` | `` |
| `created_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |

### `public.agent_tasks`

- RLS enabled: `yes`
- Primary key: `id`
- Foreign keys: `agent_tasks_assignee_id_fkey`: (assignee_id) -> `public.profiles`(id); `agent_tasks_client_id_fkey`: (client_id) -> `public.agency_clients`(id)
- Policies: `Only admins can manage agent tasks` (ALL); `Only admins can view agent tasks` (SELECT)
- Indexes (8): `agent_tasks_clickup_task_id_key`, `agent_tasks_pkey`, `idx_agent_tasks_assignee_created`, `idx_agent_tasks_client_created`, `idx_agent_tasks_skill_created`, `idx_agent_tasks_source_ref_created`, `idx_agent_tasks_sprint_week`, `idx_agent_tasks_status_updated`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | `no` | `gen_random_uuid()` |
| `last_error` | `text` | `yes` | `` |
| `created_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `updated_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `clickup_task_id` | `text` | `yes` | `` |
| `client_id` | `uuid` | `yes` | `` |
| `assignee_id` | `uuid` | `yes` | `` |
| `source` | `text` | `no` | `` |
| `source_reference` | `text` | `yes` | `` |
| `skill_invoked` | `text` | `yes` | `` |
| `sprint_week` | `date` | `yes` | `` |
| `status` | `text` | `no` | `'pending'::text` |

### `public.ai_token_usage`

- RLS enabled: `yes`
- Primary key: `id`
- Foreign keys: `scribe_usage_logs_job_id_fkey`: (job_id) -> `public.scribe_generation_jobs`(id); `scribe_usage_logs_project_id_fkey`: (project_id) -> `public.scribe_projects`(id); `scribe_usage_logs_sku_id_fkey`: (sku_id) -> `public.scribe_skus`(id); `scribe_usage_logs_user_id_fkey`: (user_id) -> `public.profiles`(id)
- Policies: `ai_token_usage_insert` (INSERT); `ai_token_usage_select` (SELECT); `scribe_usage_logs_owner_insert` (INSERT); `scribe_usage_logs_owner_select` (SELECT)
- Indexes (1): `scribe_usage_logs_pkey`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | `no` | `gen_random_uuid()` |
| `model` | `text` | `yes` | `` |
| `created_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `stage` | `text` | `yes` | `` |
| `meta` | `jsonb` | `yes` | `'{}'::jsonb` |
| `tool` | `text` | `no` | `` |
| `project_id` | `uuid` | `yes` | `` |
| `user_id` | `uuid` | `no` | `` |
| `job_id` | `uuid` | `yes` | `` |
| `sku_id` | `uuid` | `yes` | `` |
| `prompt_tokens` | `integer (int4)` | `yes` | `` |
| `completion_tokens` | `integer (int4)` | `yes` | `` |
| `total_tokens` | `integer (int4)` | `yes` | `` |

### `public.app_error_events`

- RLS enabled: `yes`
- Primary key: `id`
- Foreign keys: `none`
- Policies: `Admins can view error events` (SELECT)
- Indexes (4): `app_error_events_pkey`, `idx_app_error_events_occurred_at`, `idx_app_error_events_tool_occurred_at`, `idx_app_error_events_user_occurred_at`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | `no` | `gen_random_uuid()` |
| `user_id` | `uuid` | `yes` | `` |
| `user_email` | `text` | `yes` | `` |
| `meta` | `jsonb` | `no` | `'{}'::jsonb` |
| `occurred_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `tool` | `text` | `yes` | `` |
| `severity` | `text` | `no` | `'error'::text` |
| `message` | `text` | `no` | `` |
| `route` | `text` | `yes` | `` |
| `method` | `text` | `yes` | `` |
| `status_code` | `integer (int4)` | `yes` | `` |
| `request_id` | `text` | `yes` | `` |

### `public.brand_market_kpi_targets`

- RLS enabled: `yes`
- Primary key: `id`
- Foreign keys: `brand_market_kpi_targets_brand_id_fkey`: (brand_id) -> `public.brands`(id); `brand_market_kpi_targets_created_by_fkey`: (created_by) -> `public.profiles`(id); `brand_market_kpi_targets_updated_by_fkey`: (updated_by) -> `public.profiles`(id)
- Policies: `Authenticated users can view brand market KPI targets` (SELECT); `Only admins can manage brand market KPI targets` (ALL)
- Indexes (5): `brand_market_kpi_targets_pkey`, `idx_brand_market_kpi_targets_active`, `idx_brand_market_kpi_targets_brand_period`, `idx_brand_market_kpi_targets_market_period`, `idx_brand_market_kpi_targets_unique_active_scope`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | `no` | `gen_random_uuid()` |
| `notes` | `text` | `yes` | `` |
| `active` | `boolean (bool)` | `no` | `true` |
| `created_by` | `uuid` | `yes` | `` |
| `updated_by` | `uuid` | `yes` | `` |
| `created_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `updated_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `brand_id` | `uuid` | `no` | `` |
| `marketplace_code` | `text` | `no` | `` |
| `period_granularity` | `text` | `no` | `` |
| `period_start` | `date` | `no` | `` |
| `tacos_target_pct` | `numeric` | `yes` | `` |
| `acos_target_pct` | `numeric` | `yes` | `` |
| `sales_target` | `numeric` | `yes` | `` |
| `sales_currency` | `text` | `yes` | `` |

### `public.brands`

- RLS enabled: `yes`
- Primary key: `id`
- Foreign keys: `brands_client_id_fkey`: (client_id) -> `public.agency_clients`(id)
- Policies: `Authenticated users can view brands` (SELECT); `Only admins can manage brands` (ALL)
- Indexes (5): `brands_pkey`, `idx_brands_clickup_list`, `idx_brands_clickup_space`, `idx_brands_client`, `idx_brands_keywords`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | `no` | `gen_random_uuid()` |
| `context_summary` | `text` | `yes` | `` |
| `target_audience` | `text` | `yes` | `` |
| `positioning_notes` | `text` | `yes` | `` |
| `client_id` | `uuid` | `no` | `` |
| `name` | `text` | `no` | `` |
| `product_keywords` | `ARRAY (_text)` | `no` | `'{}'::text[]` |
| `amazon_marketplaces` | `ARRAY (_text)` | `no` | `'{}'::text[]` |
| `clickup_space_id` | `text` | `yes` | `` |
| `clickup_list_id` | `text` | `yes` | `` |
| `created_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `updated_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |

### `public.clickup_api_credentials`

- RLS enabled: `yes`
- Primary key: `organization_id, id`
- Foreign keys: `clickup_api_credentials_configured_by_fkey`: (configured_by) -> `public.profiles`(id)
- Policies: `none`
- Indexes (4): `clickup_api_credentials_pkey`, `idx_clickup_credentials_organization`, `idx_clickup_credentials_valid`, `unique_org_credential`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `organization_id` | `uuid` | `no` | `` |
| `id` | `uuid` | `no` | `gen_random_uuid()` |
| `api_token_encrypted` | `text` | `no` | `` |
| `configured_by` | `uuid` | `no` | `` |
| `configured_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `last_verified_at` | `timestamp with time zone (timestamptz)` | `yes` | `` |
| `is_valid` | `boolean (bool)` | `no` | `true` |
| `created_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `updated_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |

### `public.clickup_space_registry`

- RLS enabled: `yes`
- Primary key: `id`
- Foreign keys: `clickup_space_registry_brand_id_fkey`: (brand_id) -> `public.brands`(id)
- Policies: `Authenticated users can view space registry` (SELECT); `Only admins can manage space registry` (ALL)
- Indexes (5): `clickup_space_registry_pkey`, `clickup_space_registry_space_id_key`, `idx_space_registry_active_synced`, `idx_space_registry_brand_id`, `idx_space_registry_classification_active`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | `no` | `gen_random_uuid()` |
| `created_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `updated_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `space_id` | `text` | `no` | `` |
| `team_id` | `text` | `no` | `` |
| `name` | `text` | `no` | `` |
| `classification` | `text` | `no` | `'unknown'::text` |
| `brand_id` | `uuid` | `yes` | `` |
| `active` | `boolean (bool)` | `no` | `true` |
| `last_seen_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `last_synced_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |

### `public.clickup_spaces_cache`

- RLS enabled: `yes`
- Primary key: `organization_id, id`
- Foreign keys: `none`
- Policies: `none`
- Indexes (4): `clickup_spaces_cache_pkey`, `idx_clickup_spaces_cache_expires`, `idx_clickup_spaces_organization`, `idx_clickup_spaces_team`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `organization_id` | `uuid` | `no` | `` |
| `id` | `text` | `no` | `` |
| `name` | `text` | `no` | `` |
| `team_id` | `text` | `no` | `` |
| `cached_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `cache_expires_at` | `timestamp with time zone (timestamptz)` | `no` | `(now() + '01:00:00'::interval)` |

### `public.clickup_sync_status`

- RLS enabled: `yes`
- Primary key: `organization_id, id`
- Foreign keys: `none`
- Policies: `none`
- Indexes (5): `clickup_sync_status_pkey`, `idx_clickup_sync_entity`, `idx_clickup_sync_failures`, `idx_clickup_sync_organization`, `unique_org_entity`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `organization_id` | `uuid` | `no` | `` |
| `id` | `uuid` | `no` | `gen_random_uuid()` |
| `entity_type` | `text` | `no` | `` |
| `last_sync_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `last_sync_success` | `boolean (bool)` | `no` | `true` |
| `last_sync_error` | `text` | `yes` | `` |
| `records_synced` | `integer (int4)` | `no` | `0` |
| `created_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `updated_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |

### `public.clickup_tasks_cache`

- RLS enabled: `yes`
- Primary key: `organization_id, id`
- Foreign keys: `none`
- Policies: `none`
- Indexes (10): `clickup_tasks_cache_pkey`, `idx_clickup_tasks_assignees`, `idx_clickup_tasks_cache_expires`, `idx_clickup_tasks_due_date`, `idx_clickup_tasks_list`, `idx_clickup_tasks_organization`, `idx_clickup_tasks_space`, `idx_clickup_tasks_space_status`, `idx_clickup_tasks_status`, `idx_clickup_tasks_tags`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `organization_id` | `uuid` | `no` | `` |
| `date_created` | `timestamp with time zone (timestamptz)` | `yes` | `` |
| `date_updated` | `timestamp with time zone (timestamptz)` | `yes` | `` |
| `date_closed` | `timestamp with time zone (timestamptz)` | `yes` | `` |
| `due_date` | `timestamp with time zone (timestamptz)` | `yes` | `` |
| `start_date` | `timestamp with time zone (timestamptz)` | `yes` | `` |
| `priority` | `integer (int4)` | `yes` | `` |
| `tags` | `ARRAY (_text)` | `yes` | `'{}'::text[]` |
| `url` | `text` | `yes` | `` |
| `cached_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `cache_expires_at` | `timestamp with time zone (timestamptz)` | `no` | `(now() + '00:05:00'::interval)` |
| `id` | `text` | `no` | `` |
| `name` | `text` | `no` | `` |
| `description` | `text` | `yes` | `` |
| `status` | `text` | `no` | `` |
| `space_id` | `text` | `no` | `` |
| `folder_id` | `text` | `yes` | `` |
| `list_id` | `text` | `no` | `` |
| `assignees` | `ARRAY (_int4)` | `yes` | `'{}'::integer[]` |

### `public.clickup_users_cache`

- RLS enabled: `yes`
- Primary key: `organization_id, id`
- Foreign keys: `none`
- Policies: `none`
- Indexes (5): `clickup_users_cache_pkey`, `idx_clickup_users_cache_expires`, `idx_clickup_users_email`, `idx_clickup_users_organization`, `idx_clickup_users_username`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `organization_id` | `uuid` | `no` | `` |
| `id` | `integer (int4)` | `no` | `` |
| `username` | `text` | `no` | `` |
| `email` | `text` | `yes` | `` |
| `initials` | `text` | `yes` | `` |
| `profile_picture` | `text` | `yes` | `` |
| `cached_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `cache_expires_at` | `timestamp with time zone (timestamptz)` | `no` | `(now() + '24:00:00'::interval)` |

### `public.client_assignments`

- RLS enabled: `yes`
- Primary key: `id`
- Foreign keys: `client_assignments_assigned_by_fkey`: (assigned_by) -> `public.profiles`(id); `client_assignments_brand_id_fkey`: (brand_id) -> `public.brands`(id); `client_assignments_client_id_fkey`: (client_id) -> `public.agency_clients`(id); `client_assignments_role_id_fkey`: (role_id) -> `public.agency_roles`(id); `client_assignments_team_member_id_fkey`: (team_member_id) -> `public.profiles`(id)
- Policies: `Authenticated users can view assignments` (SELECT); `Only admins can manage assignments` (ALL)
- Indexes (9): `client_assignments_pkey`, `idx_assignments_brand`, `idx_assignments_client`, `idx_assignments_client_role`, `idx_assignments_member`, `idx_assignments_member_client`, `idx_assignments_role`, `idx_assignments_unique_brand_role_scope`, `idx_assignments_unique_client_role_scope`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | `no` | `gen_random_uuid()` |
| `client_id` | `uuid` | `no` | `` |
| `team_member_id` | `uuid` | `no` | `` |
| `assigned_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `assigned_by` | `uuid` | `yes` | `` |
| `brand_id` | `uuid` | `yes` | `` |
| `role_id` | `uuid` | `no` | `` |

### `public.client_profiles`

- RLS enabled: `yes`
- Primary key: `id`
- Foreign keys: `none`
- Policies: `Allow Ecomlabs users to manage client profiles` (ALL)
- Indexes (1): `client_profiles_pkey`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | `no` | `gen_random_uuid()` |
| `brand_name` | `text` | `no` | `` |
| `competitor_brands` | `ARRAY (_text)` | `yes` | `` |
| `product_uses` | `ARRAY (_text)` | `yes` | `` |
| `auto_negate_terms` | `ARRAY (_text)` | `yes` | `` |
| `notes` | `text` | `yes` | `` |
| `updated_by` | `text` | `yes` | `` |
| `updated_at` | `timestamp with time zone (timestamptz)` | `yes` | `now()` |
| `brand_variations` | `ARRAY (_text)` | `yes` | `'{}'::text[]` |

### `public.debrief_extracted_tasks`

- RLS enabled: `yes`
- Primary key: `id`
- Foreign keys: `debrief_extracted_tasks_meeting_note_id_fkey`: (meeting_note_id) -> `public.debrief_meeting_notes`(id); `debrief_extracted_tasks_suggested_assignee_id_fkey`: (suggested_assignee_id) -> `public.profiles`(id); `debrief_extracted_tasks_suggested_brand_id_fkey`: (suggested_brand_id) -> `public.brands`(id)
- Policies: `Authenticated users can view extracted tasks` (SELECT); `Only admins can manage extracted tasks` (ALL)
- Indexes (5): `debrief_extracted_tasks_pkey`, `idx_extracted_tasks_assignee`, `idx_extracted_tasks_brand`, `idx_extracted_tasks_meeting`, `idx_extracted_tasks_status`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | `no` | `gen_random_uuid()` |
| `clickup_task_id` | `text` | `yes` | `` |
| `clickup_error` | `text` | `yes` | `` |
| `created_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `updated_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `meeting_note_id` | `uuid` | `no` | `` |
| `raw_text` | `text` | `no` | `` |
| `title` | `text` | `no` | `` |
| `description` | `text` | `yes` | `` |
| `suggested_brand_id` | `uuid` | `yes` | `` |
| `suggested_assignee_id` | `uuid` | `yes` | `` |
| `task_type` | `text` | `yes` | `` |
| `status` | `USER-DEFINED (extracted_task_status)` | `no` | `'pending'::extracted_task_status` |

### `public.debrief_meeting_notes`

- RLS enabled: `yes`
- Primary key: `id`
- Foreign keys: `debrief_meeting_notes_dismissed_by_fkey`: (dismissed_by) -> `public.profiles`(id); `debrief_meeting_notes_suggested_client_id_fkey`: (suggested_client_id) -> `public.agency_clients`(id)
- Policies: `Authenticated users can view meeting notes` (SELECT); `Only admins can manage meeting notes` (ALL)
- Indexes (5): `debrief_meeting_notes_google_doc_id_key`, `debrief_meeting_notes_pkey`, `idx_meeting_notes_date`, `idx_meeting_notes_owner`, `idx_meeting_notes_status`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | `no` | `gen_random_uuid()` |
| `status` | `USER-DEFINED (meeting_note_status)` | `no` | `'pending'::meeting_note_status` |
| `extraction_error` | `text` | `yes` | `` |
| `dismissed_by` | `uuid` | `yes` | `` |
| `dismissed_at` | `timestamp with time zone (timestamptz)` | `yes` | `` |
| `created_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `updated_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `google_doc_id` | `text` | `no` | `` |
| `google_doc_url` | `text` | `no` | `` |
| `title` | `text` | `no` | `` |
| `meeting_date` | `timestamp with time zone (timestamptz)` | `yes` | `` |
| `owner_email` | `text` | `no` | `` |
| `raw_content` | `text` | `yes` | `` |
| `summary_content` | `text` | `yes` | `` |
| `suggested_client_id` | `uuid` | `yes` | `` |

### `public.ops_chat_sessions`

- RLS enabled: `yes`
- Primary key: `organization_id, id`
- Foreign keys: `ops_chat_sessions_client_id_fkey`: (client_id) -> `public.agency_clients`(id); `ops_chat_sessions_user_id_fkey`: (user_id) -> `public.profiles`(id)
- Policies: `none`
- Indexes (7): `idx_ops_chat_sessions_client`, `idx_ops_chat_sessions_created_at`, `idx_ops_chat_sessions_organization`, `idx_ops_chat_sessions_sop_ids`, `idx_ops_chat_sessions_user`, `idx_ops_chat_sessions_user_client`, `ops_chat_sessions_pkey`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `organization_id` | `uuid` | `no` | `` |
| `id` | `uuid` | `no` | `gen_random_uuid()` |
| `user_id` | `uuid` | `no` | `` |
| `title` | `text` | `yes` | `` |
| `client_id` | `uuid` | `yes` | `` |
| `relevant_sop_ids` | `ARRAY (_uuid)` | `yes` | `'{}'::uuid[]` |
| `message_count` | `integer (int4)` | `no` | `0` |
| `created_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `updated_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |

### `public.playbook_slack_sessions`

- RLS enabled: `yes`
- Primary key: `id`
- Foreign keys: `playbook_slack_sessions_active_client_id_fkey`: (active_client_id) -> `public.agency_clients`(id); `playbook_slack_sessions_profile_id_fkey`: (profile_id) -> `public.profiles`(id)
- Policies: `Admins can manage sessions` (ALL); `Admins can view all sessions` (SELECT)
- Indexes (3): `idx_playbook_sessions_last_message`, `idx_playbook_sessions_slack_user`, `playbook_slack_sessions_pkey`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | `no` | `gen_random_uuid()` |
| `slack_user_id` | `text` | `no` | `` |
| `profile_id` | `uuid` | `yes` | `` |
| `active_client_id` | `uuid` | `yes` | `` |
| `context` | `jsonb` | `yes` | `'{}'::jsonb` |
| `last_message_at` | `timestamp with time zone (timestamptz)` | `yes` | `now()` |
| `created_at` | `timestamp with time zone (timestamptz)` | `yes` | `now()` |

### `public.playbook_sops`

- RLS enabled: `yes`
- Primary key: `id`
- Foreign keys: `none`
- Policies: `Admins can manage SOPs` (ALL); `Authenticated users can view SOPs` (SELECT)
- Indexes (4): `idx_playbook_sops_aliases`, `idx_playbook_sops_category`, `playbook_sops_clickup_doc_id_clickup_page_id_key`, `playbook_sops_pkey`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | `no` | `gen_random_uuid()` |
| `clickup_doc_id` | `text` | `no` | `` |
| `clickup_page_id` | `text` | `no` | `` |
| `name` | `text` | `no` | `` |
| `content_md` | `text` | `yes` | `` |
| `category` | `text` | `yes` | `` |
| `last_synced_at` | `timestamp with time zone (timestamptz)` | `yes` | `now()` |
| `created_at` | `timestamp with time zone (timestamptz)` | `yes` | `now()` |
| `aliases` | `ARRAY (_text)` | `yes` | `'{}'::text[]` |

### `public.profiles`

- RLS enabled: `yes`
- Primary key: `id`
- Foreign keys: `none`
- Policies: `Only admins can insert profiles` (INSERT); `Only admins can update profiles` (UPDATE); `Users can view all profiles` (SELECT)
- Indexes (8): `idx_profiles_allowed_tools`, `idx_profiles_auth_user_id_unique`, `idx_profiles_clickup_user_id`, `idx_profiles_email_lower_unique_auth`, `idx_profiles_email_lower_unique_ghost`, `idx_profiles_is_admin`, `idx_profiles_role`, `profiles_pkey`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | `no` | `` |
| `auth_user_id` | `uuid` | `yes` | `` |
| `allowed_tools` | `ARRAY (_text)` | `no` | `'{}'::text[]` |
| `employment_status` | `text` | `no` | `'active'::text` |
| `bench_status` | `text` | `no` | `'available'::text` |
| `clickup_user_id` | `text` | `yes` | `` |
| `slack_user_id` | `text` | `yes` | `` |
| `email` | `text` | `no` | `` |
| `full_name` | `text` | `yes` | `` |
| `is_admin` | `boolean (bool)` | `no` | `false` |
| `display_name` | `text` | `yes` | `` |
| `role` | `USER-DEFINED (team_role)` | `no` | `'member'::team_role` |
| `avatar_url` | `text` | `yes` | `` |
| `created_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `updated_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |

### `public.scribe_customer_questions`

- RLS enabled: `yes`
- Primary key: `id`
- Foreign keys: `scribe_customer_questions_project_id_fkey`: (project_id) -> `public.scribe_projects`(id); `scribe_customer_questions_sku_id_fkey`: (sku_id) -> `public.scribe_skus`(id)
- Policies: `scribe_questions_select` (SELECT); `scribe_questions_write` (ALL)
- Indexes (3): `idx_scribe_customer_questions_project`, `idx_scribe_customer_questions_sku`, `scribe_customer_questions_pkey`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | `no` | `gen_random_uuid()` |
| `project_id` | `uuid` | `no` | `` |
| `sku_id` | `uuid` | `no` | `` |
| `question` | `text` | `no` | `` |
| `source` | `text` | `yes` | `` |
| `created_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |

### `public.scribe_generated_content`

- RLS enabled: `yes`
- Primary key: `id`
- Foreign keys: `scribe_generated_content_project_id_fkey`: (project_id) -> `public.scribe_projects`(id); `scribe_generated_content_sku_id_fkey`: (sku_id) -> `public.scribe_skus`(id)
- Policies: `scribe_generated_content_select` (SELECT); `scribe_generated_content_write` (ALL)
- Indexes (4): `idx_scribe_generated_content_project`, `idx_scribe_generated_content_sku`, `scribe_generated_content_pkey`, `unique_scribe_generated_content_sku`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | `no` | `gen_random_uuid()` |
| `prompt_version` | `text` | `yes` | `` |
| `approved` | `boolean (bool)` | `no` | `false` |
| `approved_at` | `timestamp with time zone (timestamptz)` | `yes` | `` |
| `created_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `updated_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `project_id` | `uuid` | `no` | `` |
| `sku_id` | `uuid` | `no` | `` |
| `version` | `integer (int4)` | `no` | `1` |
| `title` | `text` | `yes` | `` |
| `bullets` | `jsonb` | `yes` | `` |
| `description` | `text` | `yes` | `` |
| `backend_keywords` | `text` | `yes` | `` |
| `model_used` | `text` | `yes` | `` |

### `public.scribe_generation_jobs`

- RLS enabled: `yes`
- Primary key: `id`
- Foreign keys: `scribe_generation_jobs_project_id_fkey`: (project_id) -> `public.scribe_projects`(id)
- Policies: `scribe_generation_jobs_select` (SELECT); `scribe_generation_jobs_write` (ALL)
- Indexes (2): `idx_scribe_generation_jobs_project`, `scribe_generation_jobs_pkey`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | `no` | `gen_random_uuid()` |
| `project_id` | `uuid` | `no` | `` |
| `job_type` | `text` | `no` | `` |
| `status` | `text` | `no` | `'queued'::text` |
| `payload` | `jsonb` | `yes` | `` |
| `error_message` | `text` | `yes` | `` |
| `created_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `completed_at` | `timestamp with time zone (timestamptz)` | `yes` | `` |

### `public.scribe_keywords`

- RLS enabled: `yes`
- Primary key: `id`
- Foreign keys: `scribe_keywords_project_id_fkey`: (project_id) -> `public.scribe_projects`(id); `scribe_keywords_sku_id_fkey`: (sku_id) -> `public.scribe_skus`(id)
- Policies: `scribe_keywords_select` (SELECT); `scribe_keywords_write` (ALL)
- Indexes (3): `idx_scribe_keywords_project`, `idx_scribe_keywords_sku`, `scribe_keywords_pkey`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | `no` | `gen_random_uuid()` |
| `project_id` | `uuid` | `no` | `` |
| `sku_id` | `uuid` | `no` | `` |
| `keyword` | `text` | `no` | `` |
| `source` | `text` | `yes` | `` |
| `priority` | `integer (int4)` | `yes` | `` |
| `created_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |

### `public.scribe_projects`

- RLS enabled: `yes`
- Primary key: `id`
- Foreign keys: `scribe_projects_created_by_fkey`: (created_by) -> `public.profiles`(id)
- Policies: `scribe_projects_select` (SELECT); `scribe_projects_write` (ALL)
- Indexes (2): `idx_scribe_projects_created_by`, `scribe_projects_pkey`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | `no` | `gen_random_uuid()` |
| `status` | `text` | `no` | `'draft'::text` |
| `created_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `updated_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `locale` | `text` | `no` | `'en-US'::text` |
| `format_preferences` | `jsonb` | `yes` | `` |
| `created_by` | `uuid` | `no` | `` |
| `name` | `text` | `no` | `` |
| `category` | `text` | `yes` | `` |
| `sub_category` | `text` | `yes` | `` |

### `public.scribe_sku_variant_values`

- RLS enabled: `yes`
- Primary key: `id`
- Foreign keys: `scribe_sku_variant_values_attribute_id_fkey`: (attribute_id) -> `public.scribe_variant_attributes`(id); `scribe_sku_variant_values_sku_id_fkey`: (sku_id) -> `public.scribe_skus`(id)
- Policies: `scribe_sku_variant_values_select` (SELECT); `scribe_sku_variant_values_write` (ALL)
- Indexes (2): `idx_scribe_sku_variant_values_sku`, `scribe_sku_variant_values_pkey`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | `no` | `gen_random_uuid()` |
| `sku_id` | `uuid` | `no` | `` |
| `attribute_id` | `uuid` | `no` | `` |
| `value` | `text` | `no` | `` |
| `created_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `updated_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |

### `public.scribe_skus`

- RLS enabled: `yes`
- Primary key: `id`
- Foreign keys: `scribe_skus_project_id_fkey`: (project_id) -> `public.scribe_projects`(id)
- Policies: `scribe_skus_select` (SELECT); `scribe_skus_write` (ALL)
- Indexes (2): `idx_scribe_skus_project`, `scribe_skus_pkey`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | `no` | `gen_random_uuid()` |
| `sort_order` | `integer (int4)` | `yes` | `` |
| `created_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `updated_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `attribute_preferences` | `jsonb` | `yes` | `` |
| `project_id` | `uuid` | `no` | `` |
| `sku_code` | `text` | `no` | `` |
| `asin` | `text` | `yes` | `` |
| `product_name` | `text` | `yes` | `` |
| `brand_tone` | `text` | `yes` | `` |
| `target_audience` | `text` | `yes` | `` |
| `words_to_avoid` | `ARRAY (_text)` | `no` | `'{}'::text[]` |
| `supplied_content` | `text` | `yes` | `` |

### `public.scribe_topics`

- RLS enabled: `yes`
- Primary key: `id`
- Foreign keys: `scribe_topics_project_id_fkey`: (project_id) -> `public.scribe_projects`(id); `scribe_topics_sku_id_fkey`: (sku_id) -> `public.scribe_skus`(id)
- Policies: `scribe_topics_select` (SELECT); `scribe_topics_write` (ALL)
- Indexes (4): `idx_scribe_topics_project`, `idx_scribe_topics_selected`, `idx_scribe_topics_sku`, `scribe_topics_pkey`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | `no` | `gen_random_uuid()` |
| `created_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `updated_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `selected` | `boolean (bool)` | `no` | `false` |
| `project_id` | `uuid` | `no` | `` |
| `sku_id` | `uuid` | `no` | `` |
| `topic_index` | `smallint (int2)` | `no` | `` |
| `title` | `text` | `no` | `` |
| `description` | `text` | `yes` | `` |
| `generated_by` | `text` | `yes` | `` |
| `approved` | `boolean (bool)` | `no` | `false` |
| `approved_at` | `timestamp with time zone (timestamptz)` | `yes` | `` |

### `public.scribe_variant_attributes`

- RLS enabled: `yes`
- Primary key: `id`
- Foreign keys: `scribe_variant_attributes_project_id_fkey`: (project_id) -> `public.scribe_projects`(id)
- Policies: `scribe_variant_attributes_select` (SELECT); `scribe_variant_attributes_write` (ALL)
- Indexes (2): `idx_scribe_variant_attributes_project`, `scribe_variant_attributes_pkey`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | `no` | `gen_random_uuid()` |
| `project_id` | `uuid` | `no` | `` |
| `name` | `text` | `no` | `` |
| `slug` | `text` | `no` | `` |
| `sort_order` | `integer (int4)` | `yes` | `` |
| `created_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `updated_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |

### `public.skill_catalog`

- RLS enabled: `yes`
- Primary key: `id`
- Foreign keys: `none`
- Policies: `Authenticated users can view skill catalog` (SELECT); `Only admins can manage skill catalog` (ALL)
- Indexes (3): `idx_skill_catalog_enabled_default`, `idx_skill_catalog_owner_service`, `skill_catalog_pkey`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `id` | `text` | `no` | `` |
| `updated_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `name` | `text` | `no` | `` |
| `description` | `text` | `no` | `''::text` |
| `owner_service` | `text` | `no` | `` |
| `input_schema` | `jsonb` | `no` | `'{}'::jsonb` |
| `output_schema` | `jsonb` | `no` | `'{}'::jsonb` |
| `implemented_in_code` | `boolean (bool)` | `no` | `true` |
| `enabled_default` | `boolean (bool)` | `no` | `true` |
| `created_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |

### `public.skill_invocation_log`

- RLS enabled: `yes`
- Primary key: `id`
- Foreign keys: `skill_invocation_log_actor_profile_id_fkey`: (actor_profile_id) -> `public.profiles`(id); `skill_invocation_log_skill_id_fkey`: (skill_id) -> `public.skill_catalog`(id)
- Policies: `Only admins can manage skill invocation log` (ALL); `Only admins can view skill invocation log` (SELECT)
- Indexes (5): `idx_skill_invocation_actor_created`, `idx_skill_invocation_skill_created`, `idx_skill_invocation_status_created`, `skill_invocation_log_idempotency_key_key`, `skill_invocation_log_pkey`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | `no` | `gen_random_uuid()` |
| `updated_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `idempotency_key` | `text` | `no` | `` |
| `skill_id` | `text` | `no` | `` |
| `actor_profile_id` | `uuid` | `yes` | `` |
| `status` | `text` | `no` | `` |
| `request_payload` | `jsonb` | `no` | `'{}'::jsonb` |
| `response_payload` | `jsonb` | `no` | `'{}'::jsonb` |
| `error_message` | `text` | `yes` | `` |
| `created_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |

### `public.skill_policy_overrides`

- RLS enabled: `yes`
- Primary key: `id`
- Foreign keys: `skill_policy_overrides_created_by_fkey`: (created_by) -> `public.profiles`(id); `skill_policy_overrides_skill_id_fkey`: (skill_id) -> `public.skill_catalog`(id)
- Policies: `Only admins can manage skill policies` (ALL); `Only admins can view skill policies` (SELECT)
- Indexes (4): `idx_skill_policy_scope_lookup`, `idx_skill_policy_unique_global`, `idx_skill_policy_unique_scoped`, `skill_policy_overrides_pkey`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | `no` | `gen_random_uuid()` |
| `created_by` | `uuid` | `yes` | `` |
| `created_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `updated_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `skill_id` | `text` | `no` | `` |
| `scope_type` | `text` | `no` | `` |
| `scope_id` | `uuid` | `yes` | `` |
| `enabled` | `boolean (bool)` | `yes` | `` |
| `min_role_tier` | `text` | `yes` | `` |
| `requires_confirmation` | `boolean (bool)` | `yes` | `` |
| `allowed_channels` | `ARRAY (_text)` | `no` | `'{}'::text[]` |
| `max_calls_per_hour` | `integer (int4)` | `yes` | `` |

### `public.slack_event_receipts`

- RLS enabled: `yes`
- Primary key: `id`
- Foreign keys: `none`
- Policies: `Only admins can manage slack event receipts` (ALL); `Only admins can view slack event receipts` (SELECT)
- Indexes (5): `idx_slack_event_receipts_event_source_received`, `idx_slack_event_receipts_slack_event_id`, `idx_slack_event_receipts_status_received`, `slack_event_receipts_event_key_key`, `slack_event_receipts_pkey`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | `no` | `gen_random_uuid()` |
| `received_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `processed_at` | `timestamp with time zone (timestamptz)` | `yes` | `` |
| `created_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `updated_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `event_key` | `text` | `no` | `` |
| `event_source` | `text` | `no` | `` |
| `slack_event_id` | `text` | `yes` | `` |
| `event_type` | `text` | `yes` | `` |
| `status` | `text` | `no` | `'processing'::text` |
| `error_message` | `text` | `yes` | `` |
| `request_payload` | `jsonb` | `no` | `'{}'::jsonb` |
| `response_payload` | `jsonb` | `no` | `'{}'::jsonb` |

### `public.sops`

- RLS enabled: `yes`
- Primary key: `organization_id, id`
- Foreign keys: `sops_client_id_fkey`: (client_id) -> `public.agency_clients`(id); `sops_created_by_fkey`: (created_by) -> `public.profiles`(id)
- Policies: `none`
- Indexes (9): `idx_sops_category`, `idx_sops_client`, `idx_sops_created_at`, `idx_sops_created_by`, `idx_sops_embedding`, `idx_sops_organization`, `idx_sops_tags`, `idx_sops_title`, `sops_pkey`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `organization_id` | `uuid` | `no` | `` |
| `created_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `updated_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `id` | `uuid` | `no` | `gen_random_uuid()` |
| `title` | `text` | `no` | `` |
| `content` | `text` | `no` | `` |
| `category` | `text` | `yes` | `` |
| `client_id` | `uuid` | `yes` | `` |
| `tags` | `ARRAY (_text)` | `yes` | `'{}'::text[]` |
| `embedding` | `USER-DEFINED (vector)` | `yes` | `` |
| `created_by` | `uuid` | `yes` | `` |

### `public.threshold_rules`

- RLS enabled: `yes`
- Primary key: `id`
- Foreign keys: `threshold_rules_client_id_fkey`: (client_id) -> `public.agency_clients`(id)
- Policies: `Only admins can manage threshold rules` (ALL); `Only admins can view threshold rules` (SELECT)
- Indexes (4): `idx_threshold_rules_client_active`, `idx_threshold_rules_metric_active`, `idx_threshold_rules_playbook_active`, `threshold_rules_pkey`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | `no` | `gen_random_uuid()` |
| `active` | `boolean (bool)` | `no` | `true` |
| `created_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `updated_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `playbook` | `text` | `no` | `` |
| `client_id` | `uuid` | `yes` | `` |
| `metric` | `text` | `no` | `` |
| `condition` | `text` | `no` | `` |
| `threshold_value` | `numeric` | `no` | `` |
| `task_type` | `text` | `no` | `` |
| `assignee_role_slug` | `text` | `no` | `` |
| `task_template` | `text` | `no` | `` |

### `public.usage_events`

- RLS enabled: `yes`
- Primary key: `id`
- Foreign keys: `none`
- Policies: `usage_read_own` (SELECT)
- Indexes (5): `idx_usage_events_tool_occurred_at`, `usage_events_occurred_at_idx`, `usage_events_pkey`, `usage_events_status_idx`, `usage_events_user_id_idx`

| Column | Type | Nullable | Default |
|---|---|---|---|
| `id` | `uuid` | `no` | `gen_random_uuid()` |
| `status` | `text` | `yes` | `` |
| `duration_ms` | `integer (int4)` | `yes` | `` |
| `app_version` | `text` | `yes` | `` |
| `tool` | `text` | `yes` | `` |
| `meta` | `jsonb` | `no` | `'{}'::jsonb` |
| `occurred_at` | `timestamp with time zone (timestamptz)` | `no` | `now()` |
| `user_id` | `uuid` | `yes` | `` |
| `user_email` | `text` | `yes` | `` |
| `ip` | `text` | `yes` | `` |
| `file_name` | `text` | `yes` | `` |
| `file_size_bytes` | `bigint (int8)` | `yes` | `` |
| `rows_processed` | `integer (int4)` | `yes` | `` |
| `campaigns` | `integer (int4)` | `yes` | `` |

## Functions (`public` schema)

| Function | Routine Type | Returns |
|---|---|---|
| `public.array_to_halfvec` | `FUNCTION` | `USER-DEFINED` |
| `public.array_to_sparsevec` | `FUNCTION` | `USER-DEFINED` |
| `public.array_to_vector` | `FUNCTION` | `USER-DEFINED` |
| `public.avg` | `None` | `USER-DEFINED` |
| `public.binary_quantize` | `FUNCTION` | `bit` |
| `public.cleanup_old_agent_runs` | `FUNCTION` | `integer` |
| `public.cleanup_old_slack_event_receipts` | `FUNCTION` | `integer` |
| `public.cleanup_stale_playbook_sessions` | `FUNCTION` | `integer` |
| `public.cosine_distance` | `FUNCTION` | `double precision` |
| `public.current_org_id` | `FUNCTION` | `uuid` |
| `public.halfvec` | `FUNCTION` | `USER-DEFINED` |
| `public.halfvec_accum` | `FUNCTION` | `ARRAY` |
| `public.halfvec_add` | `FUNCTION` | `USER-DEFINED` |
| `public.halfvec_avg` | `FUNCTION` | `USER-DEFINED` |
| `public.halfvec_cmp` | `FUNCTION` | `integer` |
| `public.halfvec_combine` | `FUNCTION` | `ARRAY` |
| `public.halfvec_concat` | `FUNCTION` | `USER-DEFINED` |
| `public.halfvec_eq` | `FUNCTION` | `boolean` |
| `public.halfvec_ge` | `FUNCTION` | `boolean` |
| `public.halfvec_gt` | `FUNCTION` | `boolean` |
| `public.halfvec_in` | `FUNCTION` | `USER-DEFINED` |
| `public.halfvec_l2_squared_distance` | `FUNCTION` | `double precision` |
| `public.halfvec_le` | `FUNCTION` | `boolean` |
| `public.halfvec_lt` | `FUNCTION` | `boolean` |
| `public.halfvec_mul` | `FUNCTION` | `USER-DEFINED` |
| `public.halfvec_ne` | `FUNCTION` | `boolean` |
| `public.halfvec_negative_inner_product` | `FUNCTION` | `double precision` |
| `public.halfvec_out` | `FUNCTION` | `cstring` |
| `public.halfvec_recv` | `FUNCTION` | `USER-DEFINED` |
| `public.halfvec_send` | `FUNCTION` | `bytea` |
| `public.halfvec_spherical_distance` | `FUNCTION` | `double precision` |
| `public.halfvec_sub` | `FUNCTION` | `USER-DEFINED` |
| `public.halfvec_to_float4` | `FUNCTION` | `ARRAY` |
| `public.halfvec_to_sparsevec` | `FUNCTION` | `USER-DEFINED` |
| `public.halfvec_to_vector` | `FUNCTION` | `USER-DEFINED` |
| `public.halfvec_typmod_in` | `FUNCTION` | `integer` |
| `public.hamming_distance` | `FUNCTION` | `double precision` |
| `public.handle_new_auth_user` | `FUNCTION` | `trigger` |
| `public.hnsw_bit_support` | `FUNCTION` | `internal` |
| `public.hnsw_halfvec_support` | `FUNCTION` | `internal` |
| `public.hnsw_sparsevec_support` | `FUNCTION` | `internal` |
| `public.hnswhandler` | `FUNCTION` | `index_am_handler` |
| `public.inner_product` | `FUNCTION` | `double precision` |
| `public.ivfflat_bit_support` | `FUNCTION` | `internal` |
| `public.ivfflat_halfvec_support` | `FUNCTION` | `internal` |
| `public.ivfflathandler` | `FUNCTION` | `index_am_handler` |
| `public.jaccard_distance` | `FUNCTION` | `double precision` |
| `public.l1_distance` | `FUNCTION` | `double precision` |
| `public.l2_distance` | `FUNCTION` | `double precision` |
| `public.l2_norm` | `FUNCTION` | `double precision` |
| `public.l2_normalize` | `FUNCTION` | `USER-DEFINED` |
| `public.sparsevec` | `FUNCTION` | `USER-DEFINED` |
| `public.sparsevec_cmp` | `FUNCTION` | `integer` |
| `public.sparsevec_eq` | `FUNCTION` | `boolean` |
| `public.sparsevec_ge` | `FUNCTION` | `boolean` |
| `public.sparsevec_gt` | `FUNCTION` | `boolean` |
| `public.sparsevec_in` | `FUNCTION` | `USER-DEFINED` |
| `public.sparsevec_l2_squared_distance` | `FUNCTION` | `double precision` |
| `public.sparsevec_le` | `FUNCTION` | `boolean` |
| `public.sparsevec_lt` | `FUNCTION` | `boolean` |
| `public.sparsevec_ne` | `FUNCTION` | `boolean` |
| `public.sparsevec_negative_inner_product` | `FUNCTION` | `double precision` |
| `public.sparsevec_out` | `FUNCTION` | `cstring` |
| `public.sparsevec_recv` | `FUNCTION` | `USER-DEFINED` |
| `public.sparsevec_send` | `FUNCTION` | `bytea` |
| `public.sparsevec_to_halfvec` | `FUNCTION` | `USER-DEFINED` |
| `public.sparsevec_to_vector` | `FUNCTION` | `USER-DEFINED` |
| `public.sparsevec_typmod_in` | `FUNCTION` | `integer` |
| `public.subvector` | `FUNCTION` | `USER-DEFINED` |
| `public.sum` | `None` | `USER-DEFINED` |
| `public.sync_bench_status` | `FUNCTION` | `trigger` |
| `public.update_updated_at_column` | `FUNCTION` | `trigger` |
| `public.vector` | `FUNCTION` | `USER-DEFINED` |
| `public.vector_accum` | `FUNCTION` | `ARRAY` |
| `public.vector_add` | `FUNCTION` | `USER-DEFINED` |
| `public.vector_avg` | `FUNCTION` | `USER-DEFINED` |
| `public.vector_cmp` | `FUNCTION` | `integer` |
| `public.vector_combine` | `FUNCTION` | `ARRAY` |
| `public.vector_concat` | `FUNCTION` | `USER-DEFINED` |
| `public.vector_dims` | `FUNCTION` | `integer` |
| `public.vector_eq` | `FUNCTION` | `boolean` |
| `public.vector_ge` | `FUNCTION` | `boolean` |
| `public.vector_gt` | `FUNCTION` | `boolean` |
| `public.vector_in` | `FUNCTION` | `USER-DEFINED` |
| `public.vector_l2_squared_distance` | `FUNCTION` | `double precision` |
| `public.vector_le` | `FUNCTION` | `boolean` |
| `public.vector_lt` | `FUNCTION` | `boolean` |
| `public.vector_mul` | `FUNCTION` | `USER-DEFINED` |
| `public.vector_ne` | `FUNCTION` | `boolean` |
| `public.vector_negative_inner_product` | `FUNCTION` | `double precision` |
| `public.vector_norm` | `FUNCTION` | `double precision` |
| `public.vector_out` | `FUNCTION` | `cstring` |
| `public.vector_recv` | `FUNCTION` | `USER-DEFINED` |
| `public.vector_send` | `FUNCTION` | `bytea` |
| `public.vector_spherical_distance` | `FUNCTION` | `double precision` |
| `public.vector_sub` | `FUNCTION` | `USER-DEFINED` |
| `public.vector_to_float4` | `FUNCTION` | `ARRAY` |
| `public.vector_to_halfvec` | `FUNCTION` | `USER-DEFINED` |
| `public.vector_to_sparsevec` | `FUNCTION` | `USER-DEFINED` |
| `public.vector_typmod_in` | `FUNCTION` | `integer` |

## Maintenance

- Regenerate this file with `scripts/db/generate-schema-master.sh` after schema changes.
- Treat `supabase/migrations/` + live DB as source of truth; this file is generated documentation.
- If drift is detected, update migrations and docs in the same PR.
