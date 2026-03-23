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
- [ ] Keep `draft_wbr_email` and `draft_monthly_pnl_email` on approval unless/until you want mutating actions to run without confirmation

### Claude Project

- [x] Personal Claude Project created
- [x] `project_instructions.md` added to Project Instructions
- [x] `wbr_mcp_playbook.md` uploaded to Project Files
- [x] `monthly_pnl_mcp_playbook.md` uploaded to Project Files once you want Monthly P&L available in Claude
- [ ] Re-paste the latest `project_instructions.md` if the local file changes
- [ ] Re-upload the latest `wbr_mcp_playbook.md` if the local file changes
- [ ] Re-upload the latest `monthly_pnl_mcp_playbook.md` if the local file changes

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
2. Agency OS Monthly P&L read-only MCP workflows
3. the live WBR tools plus the first read-only P&L tools
4. the expected usage pattern for client resolution, profile resolution,
   summary retrieval, and draft creation where supported

Expand this folder only when a workflow is stable enough to deserve durable
Claude Project knowledge.
