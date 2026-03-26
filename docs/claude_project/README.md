# Claude Project Bundle

Use this folder for the Claude Project setup instead of uploading large planning
docs.

## Status Checklist

### Backend / Auth

- [x] MCP server mounted in `backend-core`
- [x] Claude remote connector can authenticate through Supabase OAuth
- [x] Supabase JWT signing rotated to asymmetric ECC key
- [x] Backend auth supports JWKS verification with legacy `HS256` fallback
- [x] Jeff-only MCP allowlist is configured and working
- [ ] Add `OAUTH_STATE_SIGNING_SECRET` to Render to fully decouple OAuth state signing from `SUPABASE_JWT_SECRET`
- [ ] Decide when to remove the legacy `HS256` fallback after enough time has passed for old tokens to expire

### Claude Connector

- [x] Private `Agency OS` connector added in Claude Pro
- [x] Connector can connect successfully
- [x] Tool permissions configured
- [ ] Set read-only tools to `Always allow` if you want less friction:
  - `resolve_client`
  - `list_wbr_profiles`
  - `get_wbr_summary`
  - `list_monthly_pnl_profiles`
  - `get_monthly_pnl_report`
  - `get_monthly_pnl_email_brief`
  - `list_clickup_tasks`
  - `get_clickup_task`
  - `resolve_team_member`
- [ ] Keep `draft_wbr_email`, `draft_monthly_pnl_email`, and `create_clickup_task` on approval unless/until you want mutating actions to run without confirmation

### Claude Project

- [x] Personal Claude Project created
- [x] `project_instructions.md` added to Project Instructions
- [x] `wbr_mcp_playbook.md` uploaded to Project Files
- [x] `monthly_pnl_mcp_playbook.md` uploaded to Project Files once you want Monthly P&L available in Claude
- [ ] Upload `clickup_mcp_playbook.md` to Project Files once you want ClickUp available in Claude
- [ ] Re-paste the latest `project_instructions.md` if the local file changes
- [ ] Re-upload the latest `wbr_mcp_playbook.md` if the local file changes
- [ ] Re-upload the latest `monthly_pnl_mcp_playbook.md` if the local file changes
- [ ] Re-upload the latest `clickup_mcp_playbook.md` if the local file changes

### WBR Pilot Tools

- [x] `resolve_client` smoke-tested
- [x] `list_wbr_profiles` smoke-tested
- [x] `get_wbr_summary` smoke-tested
- [x] `draft_wbr_email` smoke-tested
- [x] Real persisted WBR draft created from Claude

### Monthly P&L Read-Only Tools

- [x] `resolve_client` smoke-tested for Monthly P&L routing metadata
- [x] `list_monthly_pnl_profiles` smoke-tested
- [x] `get_monthly_pnl_report` smoke-tested
- [x] `get_monthly_pnl_email_brief` smoke-tested

### Monthly P&L Draft Tool

- [x] `draft_monthly_pnl_email` smoke-tested

### Monthly P&L Current State

- [x] Monthly P&L Claude surface is live
- [x] Shared `resolve_client` returns team / brand / marketplace / report metadata
- [x] WBR and Monthly P&L both work in the same Agency OS Claude Project
- [x] Monthly P&L YoY is live in the web app
- [x] Claude can still reason about YoY using the existing P&L tools

### ClickUp Current State

- [x] ClickUp Claude surface is live
- [x] Shared `resolve_client` returns brand / ClickUp routing metadata
- [x] Claude can review mapped backlog tasks through `list_clickup_tasks`
- [x] Claude can inspect mapped task links through `get_clickup_task`
- [x] Claude can preview and create mapped ClickUp tasks
- [x] ClickUp MCP surface is now in real pilot testing with the same Claude
  Project bundle as WBR and Monthly P&L

### Next Expansion Options

- [ ] tighten tool descriptions / output formatting based on pilot usage
- [ ] reduce approval friction for read-only tools
- [ ] add additional narrow Claude Project files only when a workflow is stable
- [ ] decide when to move from Jeff-only Claude Pro usage to a broader Claude Team rollout

## What To Add To Claude

### Instructions

Paste the contents of `project_instructions.md` into the Claude Project
Instructions panel.

### Files

Upload only the files Claude needs for durable reference:

1. `wbr_mcp_playbook.md`
2. `monthly_pnl_mcp_playbook.md`
3. `clickup_mcp_playbook.md`

Optional later:

1. additional narrow runbooks for other Agency OS workflows
2. client/reporting conventions if they are short and stable

## What Not To Upload

Avoid uploading:

1. `docs/claude_primary_surface_plan.md`
2. `docs/agency_os_mcp_implementation_plan.md`
3. large internal READMEs that describe implementation details Claude does not
   need during normal WBR work

Those documents are useful for product and architecture decisions, but they are
too large and too broad for a day-to-day Claude Project.

## Current Scope

This bundle now supports a small shared reporting surface:

1. Agency OS WBR MCP workflows
2. Agency OS Monthly P&L MCP workflows
3. Agency OS ClickUp MCP workflows
4. live WBR tools plus live Monthly P&L analysis / brief / draft tools plus
   live ClickUp review / preview / create tools
5. the expected usage pattern for client resolution, profile resolution,
   summary retrieval, task inspection, assignee resolution, brief generation,
   and draft / task creation where supported

Current live testing status:

1. WBR is live in Claude
2. Monthly P&L is live in Claude
3. ClickUp is now live in Claude and actively being tested on the Jeff-only
   pilot surface

Expand this folder only when a workflow is stable enough to deserve durable
Claude Project knowledge.
