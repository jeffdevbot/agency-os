# WBR v2 Schema Plan

This document turns the WBR v2 prototype plan into a concrete database plan.
It now also serves as a reference for the live WBR schema shape and the design
choices behind it.

## Current implementation status

As of March 15, 2026:

1. Migrations 1-8 are implemented and applied live:
   - `20260312000001_wbr_profiles_and_rows.sql`
   - `20260312000002_wbr_imports_and_mappings.sql`
   - `20260312000003_wbr_sync_runs_and_fact_tables.sql`
   - `20260313000001_wbr_amazon_ads_connections.sql`
   - `20260313000002_wbr_ads_campaign_daily_campaign_type_unique.sql`
   - `20260313000003_wbr_profile_auto_sync_flags.sql`
   - `20260314000001_wbr_inventory_and_returns_tables.sql`
   - `20260315100000_expand_wbr_sync_run_source_types_for_section3.sql`
2. The application layer is wired to the full current WBR v2 stack:
   - profiles and row tree
   - Pacvue import and campaign mapping
   - listings import and Windsor listings import
   - ASIN mapping and CSV round-trip
   - Windsor business sync + Section 1 report
   - Amazon Ads OAuth/profile selection + sync + Section 2 report
   - Windsor inventory + returns sync + Section 3 report
   - nightly worker toggles + `worker-sync` execution
3. Amazon Ads sync now uses a queued/background report lifecycle:
   - manual backfills/manual refreshes enqueue report jobs and return quickly
   - queued report state is persisted in `wbr_sync_runs.request_meta`
   - `worker-sync` polls Amazon, downloads completed reports, and finalizes runs
4. `wbr_ads_campaign_daily` now stores `campaign_type` and uses uniqueness on:
   - `(profile_id, report_date, campaign_type, campaign_name)`
5. The sections below mix live schema notes with retained design rationale from
   the original rollout plan. When rollout-sequencing language conflicts with
   the current app, treat the applied migrations, `PROJECT_STATUS.md`, and the
   live codepaths as the source of truth. `docs/wbr_v2_handoff.md` is now a
   historical/reference doc rather than the default restart entrypoint.
6. The current main report UI is now tabbed by section, supports server-side
   Excel export, and includes inline trend charts for Sections 1 and 2. Those
   are application-layer features and do not change the core schema, but they
   are part of the shipped WBR v2 surface.

## Decision on the old migration

The untracked migration `supabase/migrations/20260225000001_wbr_section1_foundation.sql` should not be kept.

Reason:

1. It models the old WBR as a flat Section 1 pipeline around `group_label`.
2. The new WBR model requires a row tree shared across business and ads sections.
3. The old migration hard-codes a Sunday-start weekly view, which conflicts with the new per-profile week start requirement.
4. The old migration encodes Windsor-specific assumptions directly into the main WBR schema instead of treating source ingestion and report modeling separately.
5. It also contains permissive read policies that are too broad for a multi-tenant reporting system.
6. The file is untracked, so removing it does not delete a committed migration history.

What is still useful from that file:

1. Daily child-ASIN business grain is still correct.
2. Ingest run logging is still needed.
3. Replace-style rewrites for recent windows are still the right operational pattern.

What should change:

1. `group_label` must be replaced by a row-tree model.
2. WBR must be modeled per client + marketplace profile.
3. Ads facts need their own source tables.
4. Weekly rollups cannot be defined by a single fixed Sunday-start view.

## Schema goals

The schema must support:

1. One WBR profile per client + marketplace.
2. A reusable row tree shared across sections.
3. Manual parent rows and auto-derived leaf rows.
4. Child-ASIN-to-row mapping.
5. Campaign-name-to-row mapping via Pacvue imports.
6. Separate source fact tables for Windsor business data and Amazon Ads data.
7. Historical backfill and rolling rewrite syncs.
8. QA tables/views for unmapped campaigns, unmapped ASINs, and reconciliation.
9. Secure RLS aligned to admin or future explicit client access rules.
10. Async/queued sync-run metadata for long-running external report generation.

## Core design choice

The schema should be centered on `wbr_profile_id`, not raw `client_id + account_id` across every table.

Reason:

1. Each WBR is marketplace-specific.
2. Week-start settings are profile-specific.
3. The row tree belongs to one profile.
4. Source config belongs to one profile.
5. This avoids mixing unrelated marketplaces or account scopes under one client id.

## Live tables and design notes

### 1. `wbr_profiles`

Purpose:

- Root configuration object for one client + marketplace WBR.

Columns:

- `id uuid primary key default gen_random_uuid()`
- `client_id uuid not null references public.agency_clients(id) on delete restrict`
- `marketplace_code text not null`
- `display_name text not null`
- `week_start_day text not null check (week_start_day in ('sunday', 'monday'))`
- `status text not null default 'draft' check (status in ('draft', 'active', 'paused', 'archived'))`
- `windsor_account_id text`
- `amazon_ads_profile_id text`
- `amazon_ads_account_id text`
- `backfill_start_date date`
- `daily_rewrite_days integer not null default 14 check (daily_rewrite_days >= 1 and daily_rewrite_days <= 60)`
- `sp_api_auto_sync_enabled boolean not null default false`
- `ads_api_auto_sync_enabled boolean not null default false`
- `created_by uuid references public.profiles(id)`
- `updated_by uuid references public.profiles(id)`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

Constraints/indexes:

- Unique index on `(client_id, marketplace_code, display_name)` if multiple profiles per marketplace are not desired.
- Index on `(client_id, marketplace_code)`.
- Index on `status`.

Notes:

- `display_name` is the operator-facing label like `WHOOSH INC [US]`.
- If later needed, source credentials can be moved to separate config tables, but this is enough for the prototype.
- Ads API queued-report state currently lives in `wbr_sync_runs.request_meta` rather than a dedicated report-job table.

### 2. `wbr_rows`

Purpose:

- Define the WBR row tree.

Columns:

- `id uuid primary key default gen_random_uuid()`
- `profile_id uuid not null references public.wbr_profiles(id) on delete cascade`
- `row_label text not null`
- `row_kind text not null check (row_kind in ('parent', 'leaf'))`
- `parent_row_id uuid references public.wbr_rows(id) on delete set null`
- `sort_order integer not null default 0`
- `active boolean not null default true`
- `created_by uuid references public.profiles(id)`
- `updated_by uuid references public.profiles(id)`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

Constraints/indexes:

- Partial unique index on `(profile_id, row_kind, row_label)` where `active = true`.
- Index on `(profile_id, parent_row_id, sort_order)`.
- Check or trigger to prevent a row from parenting itself and to keep parent/child rows inside the same profile.

Notes:

- Parent and leaf rows may intentionally share the same visible label. Example: a parent `Screen Shine | Pro` can contain a leaf child also named `Screen Shine | Pro`.
- v1 should support only one parent level.
- If deeper nesting is ever needed, this model can support it, but UI and queries should initially assume one parent level.

### 3. `wbr_pacvue_import_batches`

Purpose:

- Track Pacvue file imports.

Columns:

- `id uuid primary key default gen_random_uuid()`
- `profile_id uuid not null references public.wbr_profiles(id) on delete cascade`
- `source_filename text`
- `import_status text not null default 'running' check (import_status in ('running', 'success', 'error'))`
- `rows_read integer not null default 0`
- `rows_loaded integer not null default 0`
- `error_message text`
- `initiated_by uuid references public.profiles(id)`
- `started_at timestamptz not null default now()`
- `finished_at timestamptz`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

Indexes:

- Index on `(profile_id, created_at desc)`.

### 4. `wbr_pacvue_campaign_map`

Purpose:

- Store imported campaign/tag metadata from Pacvue.

Columns:

- `id uuid primary key default gen_random_uuid()`
- `profile_id uuid not null references public.wbr_profiles(id) on delete cascade`
- `import_batch_id uuid not null references public.wbr_pacvue_import_batches(id) on delete cascade`
- `campaign_name text not null`
- `raw_tag text not null`
- `row_id uuid not null references public.wbr_rows(id) on delete cascade`
- `leaf_row_label text not null`
- `goal_code text`
- `raw_payload jsonb not null default '{}'::jsonb`
- `active boolean not null default true`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

Constraints/indexes:

- Partial unique index on `(profile_id, campaign_name)` where `active = true`.
- Index on `(profile_id, leaf_row_label)`.
- Index on `(profile_id, row_id)`.
- Index on `(profile_id, goal_code)`.

Notes:

- `row_id` should always reference a `leaf` row in the same profile.
- `active` allows one current mapping snapshot per campaign while preserving import history.

### 5. `wbr_listing_import_batches`

Purpose:

- Track uploaded listings/all-listings imports.

Columns:

- `id uuid primary key default gen_random_uuid()`
- `profile_id uuid not null references public.wbr_profiles(id) on delete cascade`
- `source_filename text`
- `import_status text not null default 'running' check (import_status in ('running', 'success', 'error'))`
- `rows_read integer not null default 0`
- `rows_loaded integer not null default 0`
- `error_message text`
- `initiated_by uuid references public.profiles(id)`
- `started_at timestamptz not null default now()`
- `finished_at timestamptz`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

### 6. `wbr_profile_child_asins`

Purpose:

- Canonical list of known child ASINs for one profile.

Columns:

- `id uuid primary key default gen_random_uuid()`
- `profile_id uuid not null references public.wbr_profiles(id) on delete cascade`
- `listing_batch_id uuid references public.wbr_listing_import_batches(id) on delete set null`
- `parent_asin text`
- `child_asin text not null`
- `parent_sku text`
- `child_sku text`
- `fnsku text`
- `upc text`
- `category text`
- `parent_title text`
- `child_product_name text`
- `source_item_style text`
- `size text`
- `fulfillment_method text`
- `raw_payload jsonb not null default '{}'::jsonb`
- `active boolean not null default true`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

Constraints/indexes:

- Unique index on `(profile_id, child_asin)` where `active = true`.
- Index on `(profile_id, source_item_style)`.

Notes:

- `source_item_style` is useful because current manual WBRs effectively treat item style as the row label/mapping value.

### 7. `wbr_asin_row_map`

Purpose:

- Map each child ASIN to exactly one leaf row.

Columns:

- `id uuid primary key default gen_random_uuid()`
- `profile_id uuid not null references public.wbr_profiles(id) on delete cascade`
- `child_asin text not null`
- `row_id uuid not null references public.wbr_rows(id) on delete cascade`
- `mapping_source text not null default 'manual' check (mapping_source in ('manual', 'imported', 'suggested'))`
- `active boolean not null default true`
- `created_by uuid references public.profiles(id)`
- `updated_by uuid references public.profiles(id)`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

Constraints/indexes:

- Partial unique index on `(profile_id, child_asin)` where `active = true`.
- Index on `(profile_id, row_id)`.

Required integrity rule:

- `row_id` must reference a `leaf` row belonging to the same `profile_id`.
- `child_asin` must exist in the active ASIN catalog for the same `profile_id`.
- This should be enforced with a trigger because a plain FK cannot express it.

### 8. `wbr_sync_runs`

Purpose:

- Generic sync/backfill logging for all WBR sources.

Columns:

- `id uuid primary key default gen_random_uuid()`
- `profile_id uuid not null references public.wbr_profiles(id) on delete cascade`
- `source_type text not null check (source_type in ('windsor_business', 'windsor_inventory', 'windsor_returns', 'amazon_ads', 'pacvue_import', 'listing_import'))`
- `job_type text not null check (job_type in ('backfill', 'daily_refresh', 'manual_rerun', 'import'))`
- `date_from date`
- `date_to date`
- `status text not null default 'running' check (status in ('running', 'success', 'error'))`
- `rows_fetched integer not null default 0`
- `rows_loaded integer not null default 0`
- `request_meta jsonb not null default '{}'::jsonb`
- `error_message text`
- `initiated_by uuid references public.profiles(id)`
- `started_at timestamptz not null default now()`
- `finished_at timestamptz`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

Indexes:

- Index on `(profile_id, source_type, created_at desc)`.
- Index on `(status, created_at desc)`.

Reasoning:

- The old `wbr_ingest_runs` concept is worth keeping, but it should become source-agnostic.
- For Amazon Ads, the currently shipped implementation also stores queued
  report-job state in `request_meta` so the worker can resume polling/download
  work across loops without a separate job table.

### 9. `wbr_business_asin_daily`

Purpose:

- Daily business facts from Windsor at child ASIN grain.

Columns:

- `id uuid primary key default gen_random_uuid()`
- `profile_id uuid not null references public.wbr_profiles(id) on delete cascade`
- `sync_run_id uuid references public.wbr_sync_runs(id) on delete set null`
- `report_date date not null`
- `child_asin text not null`
- `parent_asin text`
- `currency_code text not null`
- `page_views bigint not null default 0 check (page_views >= 0)`
- `unit_sales bigint not null default 0 check (unit_sales >= 0)`
- `sales numeric(18, 2) not null default 0`
- `source_payload jsonb not null default '{}'::jsonb`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

Constraints/indexes:

- Unique constraint on `(profile_id, report_date, child_asin)`.
- Index on `(profile_id, report_date desc)`.
- Index on `(profile_id, child_asin, report_date desc)`.

Operational rule:

- Rewrite by date window, not append-only.
- If `sync_run_id` is present, it must belong to the same `profile_id` and have `source_type = 'windsor_business'`.

### 10. `wbr_ads_campaign_daily`

Purpose:

- Daily Amazon Ads metrics at campaign grain.

Columns:

- `id uuid primary key default gen_random_uuid()`
- `profile_id uuid not null references public.wbr_profiles(id) on delete cascade`
- `sync_run_id uuid references public.wbr_sync_runs(id) on delete set null`
- `report_date date not null`
- `campaign_id text`
- `campaign_name text not null`
- `campaign_type text not null default 'sponsored_products'`
- `impressions bigint not null default 0 check (impressions >= 0)`
- `clicks bigint not null default 0 check (clicks >= 0)`
- `spend numeric(18, 2) not null default 0`
- `orders bigint not null default 0 check (orders >= 0)`
- `sales numeric(18, 2) not null default 0`
- `currency_code text`
- `source_payload jsonb not null default '{}'::jsonb`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

Constraints/indexes:

- Unique constraint on `(profile_id, report_date, campaign_type, campaign_name)` for prototype exact-name matching across SP/SB/SD.
- Index on `(profile_id, report_date desc)`.
- Index on `(profile_id, campaign_name)`.
- Optional non-unique index on `(profile_id, campaign_id)`.

Operational rule:

- Rewrite rolling recent windows to handle attribution and reporting lag.
- If `sync_run_id` is present, it must belong to the same `profile_id` and have `source_type = 'amazon_ads'`.

## Derived views

These views are not currently shipped as persistent database views.
Equivalent weekly rollups and QA outputs are currently computed in the service
layer, primarily in:

- `backend-core/app/services/wbr/section1_report.py`
- `backend-core/app/services/wbr/section2_report.py`

If database views are added later, the definitions below remain the intended
shape.

### 1. `wbr_unmapped_campaigns`

Definition:

- Campaigns present in `wbr_ads_campaign_daily` with no exact match in `wbr_pacvue_campaign_map` for the same profile.

Purpose:

- QA for new or renamed campaigns.

### 2. `wbr_unmapped_asins`

Definition:

- Child ASINs known from listings or business facts with no row mapping.

Purpose:

- QA for incomplete row coverage.

### 3. `wbr_row_weekly_business`

Definition:

- Weekly business metrics rolled from `wbr_business_asin_daily` through `wbr_asin_row_map` into `wbr_rows`, with week bucket derived from `wbr_profiles.week_start_day`.

### 4. `wbr_row_weekly_ads`

Definition:

- Weekly ads metrics rolled from `wbr_ads_campaign_daily` through `wbr_pacvue_campaign_map` into `wbr_rows`, with week bucket derived from `wbr_profiles.week_start_day`.

### 5. `wbr_row_weekly_combined`

Definition:

- Combined weekly row output joining business and ads weekly metrics for the renderer.

Important note:

- The old `wbr_section1_weekly` single-purpose view should not be recreated.
- The new weekly views must join to `wbr_profiles` so week starts can differ by profile.

## RLS plan

The old migration used `using (true)` on selects. Do not repeat that.

Prototype RLS policy:

1. `select` access for WBR tables should initially be admin-only.
2. `insert/update/delete` access should also be admin-only.
3. If client-facing WBR access is added later, it should be implemented with explicit profile-scoped access rules, not blanket authenticated reads.

Implementation pattern:

- Reuse the project’s admin test on `public.profiles`.
- Prefer a helper function if the same policy is repeated across many WBR tables.

## Applied migration sequence

The initial phased rollout described in this plan has now been implemented with
the following live migrations:

1. `20260312000001_wbr_profiles_and_rows.sql`
2. `20260312000002_wbr_imports_and_mappings.sql`
3. `20260312000003_wbr_sync_runs_and_fact_tables.sql`
4. `20260313000001_wbr_amazon_ads_connections.sql`
5. `20260313000002_wbr_ads_campaign_daily_campaign_type_unique.sql`
6. `20260313000003_wbr_profile_auto_sync_flags.sql`

Notable differences versus the original phased plan:

1. Amazon Ads OAuth connection storage shipped as its own migration rather than
   being folded into the earlier schema tranche.
2. The `campaign_type` uniqueness fix for `wbr_ads_campaign_daily` shipped as a
   follow-up migration after the first Ads API rollout.
3. Nightly sync toggles shipped on `wbr_profiles`; the planned QA and rollup
   views did not ship as database views.
4. Amazon Ads report-job state was kept inside `wbr_sync_runs.request_meta`
   rather than introducing a dedicated async job table in this tranche.

## Backend impact

Most of the intended backend impact has already happened.

Live code paths targeting the new schema now include:

- `backend-core/app/services/wbr/profiles.py`
- `backend-core/app/services/wbr/pacvue_imports.py`
- `backend-core/app/services/wbr/listing_imports.py`
- `backend-core/app/services/wbr/asin_mappings.py`
- `backend-core/app/services/wbr/windsor_business_sync.py`
- `backend-core/app/services/wbr/amazon_ads_sync.py`
- `backend-core/app/services/wbr/section1_report.py`
- `backend-core/app/services/wbr/section2_report.py`
- `backend-core/app/services/wbr/nightly_sync.py`

Intentional leftovers still tied to the old schema/path:

- `backend-core/app/services/wbr/windsor_section1_ingest.py`
- legacy `/admin/wbr/section1/*` routes

Those paths should not drive the final schema design. They remain compatibility
surface only.

## Current follow-on focus

This schema plan no longer has an immediate bootstrap step; the foundation is
already live. If WBR work resumes, use this schema doc plus the live code and
`PROJECT_STATUS.md` first. Treat `docs/wbr_v2_handoff.md` as historical/debug
reference rather than the primary restart doc.
