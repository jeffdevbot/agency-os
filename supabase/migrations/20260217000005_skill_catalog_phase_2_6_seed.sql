-- =====================================================================
-- MIGRATION: Seed missing AgencyClaw skills through Phase 2.6
-- Purpose:
--   Add PRD-listed skill IDs that were not included in initial seed migration.
-- Notes:
--   - Existing rows are preserved (ON CONFLICT DO NOTHING).
--   - These entries are seeded disabled until implemented.
-- =====================================================================

INSERT INTO public.skill_catalog (
  id,
  name,
  description,
  owner_service,
  implemented_in_code,
  enabled_default
)
VALUES
  -- KPI + ClickUp interaction skills
  ('kpi_target_upsert', 'KPI Target Upsert', 'Create or update marketplace KPI targets for a brand period.', 'orchestrator', false, false),
  ('kpi_target_lookup', 'KPI Target Lookup', 'Resolve KPI targets with monthly/annual fallback semantics.', 'orchestrator', false, false),
  ('clickup_task_list_weekly', 'ClickUp Task List Weekly', 'List active tasks for a client or brand within current week scope.', 'relay', false, false),
  ('clickup_task_create', 'ClickUp Task Create', 'Create a ClickUp task in the resolved brand backlog destination.', 'relay', false, false),
  ('clickup_task_update', 'ClickUp Task Update', 'Update existing ClickUp task fields and status.', 'relay', false, false),
  ('clickup_task_quality_gate', 'ClickUp Task Quality Gate', 'Validate required task fields before create/update execution.', 'orchestrator', false, false),
  ('clickup_task_duplicate_check', 'ClickUp Task Duplicate Check', 'Detect likely duplicate task create requests via idempotency signals.', 'orchestrator', false, false),

  -- Meeting/debrief parsing and context
  ('meeting_parser', 'Meeting Parser', 'Parse meeting notes into structured actions, owners, and metadata.', 'orchestrator', false, false),
  ('debrief_meeting_ingest', 'Debrief Meeting Ingest', 'Ingest and normalize meeting artifacts for debrief processing.', 'orchestrator', false, false),
  ('debrief_task_review', 'Debrief Task Review', 'Review extracted debrief tasks for quality, gaps, and routing readiness.', 'orchestrator', false, false),
  ('client_context_builder', 'Client Context Builder', 'Assemble fixed-budget client context pack for orchestrator prompts.', 'orchestrator', false, false),
  ('client_brief', 'Client Brief', 'Generate concise client brief with priorities, KPIs, risks, and blockers.', 'orchestrator', false, false),
  ('sop_lookup', 'SOP Lookup', 'Lookup SOP guidance by category, alias, and relevance.', 'orchestrator', false, false),
  ('sop_sync_run', 'SOP Sync Run', 'Trigger SOP synchronization refresh and report sync summary.', 'orchestrator', false, false),

  -- Reliability and operations
  ('run_status_lookup', 'Run Status Lookup', 'Retrieve run status, outputs, and failure details from agent runs.', 'orchestrator', false, false),
  ('run_retry', 'Run Retry', 'Retry failed runs with policy and idempotency checks.', 'orchestrator', false, false),
  ('event_dedupe_audit', 'Event Dedupe Audit', 'Inspect Slack dedupe receipts and duplicate handling outcomes.', 'audit', false, false),
  ('error_digest', 'Error Digest', 'Summarize recent errors grouped by tool, severity, and route.', 'audit', false, false),
  ('usage_cost_report', 'Usage Cost Report', 'Aggregate model token usage and estimated cost by scope.', 'audit', false, false),

  -- Assignment/reporting helpers
  ('cc_assignment_matrix', 'Assignment Matrix', 'Render assignment matrix by client, brand, and role.', 'orchestrator', false, false),
  ('cc_role_capacity_snapshot', 'Role Capacity Snapshot', 'Summarize role coverage/capacity from current assignments.', 'orchestrator', false, false),
  ('cc_policy_explain', 'Policy Explain', 'Explain why a requested action is allowed, denied, or gated.', 'orchestrator', false, false),

  -- Command Center team/profile parity skills
  ('cc_team_member_lookup', 'Team Member Lookup', 'Lookup employee profile by name, email, Slack ID, or ClickUp ID.', 'orchestrator', false, false),
  ('cc_team_member_create', 'Team Member Create', 'Create a new team member profile record.', 'orchestrator', false, false),
  ('cc_team_member_update', 'Team Member Update', 'Update team member profile fields and operational flags.', 'orchestrator', false, false),
  ('cc_team_member_update_slack_id', 'Team Member Update Slack ID', 'Set or replace Slack user ID mapping for a profile.', 'orchestrator', false, false),
  ('cc_team_member_update_clickup_id', 'Team Member Update ClickUp ID', 'Set or replace ClickUp user ID mapping for a profile.', 'orchestrator', false, false),
  ('cc_team_member_archive', 'Team Member Archive', 'Archive or deactivate a team member profile.', 'orchestrator', false, false),

  -- Command Center client/brand parity skills
  ('cc_client_update', 'Client Update', 'Update client operational fields and context metadata.', 'orchestrator', false, false),
  ('cc_brand_list_all', 'Brand List All', 'List all brands and ClickUp mapping coverage.', 'orchestrator', false, false),
  ('cc_brand_create', 'Brand Create', 'Create a new brand under a client.', 'orchestrator', false, false),
  ('cc_brand_update', 'Brand Update', 'Update brand metadata, routing, and context fields.', 'orchestrator', false, false),
  ('cc_brand_clickup_mapping_audit', 'Brand ClickUp Mapping Audit', 'Report brands missing ClickUp space/list mappings.', 'orchestrator', false, false),
  ('cc_brand_clickup_space_set', 'Brand ClickUp Space Set', 'Set or replace ClickUp space mapping for a brand.', 'orchestrator', false, false),
  ('cc_brand_clickup_list_set', 'Brand ClickUp List Set', 'Set or replace ClickUp list mapping for a brand.', 'orchestrator', false, false),
  ('cc_brand_delete', 'Brand Delete', 'Delete archived or unused brand when policy permits.', 'orchestrator', false, false)
ON CONFLICT (id) DO NOTHING;

