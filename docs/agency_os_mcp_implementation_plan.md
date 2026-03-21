# Agency OS MCP Implementation Plan

_Drafted: 2026-03-21 (ET)_

## Summary

This document is the focused implementation plan for the first `agency-os` MCP
pilot.

It complements:

1. [claude_primary_surface_plan.md](/Users/jeff/code/agency-os/docs/claude_primary_surface_plan.md)
2. [shared_ai_service_plan.md](/Users/jeff/code/agency-os/docs/shared_ai_service_plan.md)

This plan is intentionally narrow:

1. official MCP Python SDK
2. hosted inside `backend-core`
3. Jeff-only Claude Pro pilot
4. WBR-first tool surface

## Slice 0

### Goal

Stand up the MCP foundation so Claude Pro can connect to Agency OS and call one
real tool end to end.

### Scope

1. official MCP Python SDK
2. MCP server mounted in `backend-core`
3. Jeff-only pilot auth
4. first tool: `resolve_client`
5. MCP Inspector smoke test

### Explicitly out of scope

1. Team rollout auth/governance
2. shared internal AI runtime refactor
3. Scribe / Debrief / AdScope integration
4. WBR draft tool
5. P&L tools
6. child-ASIN tools

## Runtime and hosting

### Chosen runtime

1. official MCP Python SDK
2. `mcp.server.fastmcp.FastMCP`
3. Streamable HTTP transport

### Hosting

1. mount inside existing `backend-core` FastAPI app
2. use a dedicated MCP base path such as `/mcp`
3. if the SDK requires multiple subpaths, follow the SDK exactly and document the final route shape in code comments and docs

### Repo insertion points

1. FastAPI app entry:
   - [main.py](/Users/jeff/code/agency-os/backend-core/app/main.py)
2. Existing auth helpers:
   - [auth.py](/Users/jeff/code/agency-os/backend-core/app/auth.py)
3. WBR bridge/reuse seams:
   - [wbr_skill_bridge.py](/Users/jeff/code/agency-os/backend-core/app/services/theclaw/wbr_skill_bridge.py)
   - [wbr.py](/Users/jeff/code/agency-os/backend-core/app/routers/wbr.py)
   - [email_drafts.py](/Users/jeff/code/agency-os/backend-core/app/services/wbr/email_drafts.py)
   - [report_snapshots.py](/Users/jeff/code/agency-os/backend-core/app/services/wbr/report_snapshots.py)

## Code organization rules

The MCP layer must stay thin and modular.

### Required structure

1. `backend-core/app/mcp/server.py`
   - MCP server/bootstrap only
2. `backend-core/app/mcp/auth.py`
   - auth, allowlist, user resolution
3. `backend-core/app/mcp/tools/wbr.py`
   - WBR/client-domain tool definitions and wrappers
4. optional small helper modules only if needed

### Avoid

1. one giant `agency_os_mcp.py`
2. embedding business logic in tool wrappers
3. copying WBR/P&L logic into MCP modules
4. using The Claw `SKILL.md` files as the MCP interface

Implementation rule:

1. reuse backend services
2. wrap them in MCP-facing tool definitions
3. do not expose the Slack runtime directly

## Pilot auth model

### Required behavior

1. only Jeff may authenticate and use tools in the Pro pilot
2. all other users are rejected cleanly
3. auth shape should be forward-compatible with later Team rollout

### Default allowlist rule

1. primary identifier: Supabase `sub`
2. secondary check: email if available
3. if both are present, require both to match configured values

### Config

1. `MCP_PILOT_ALLOWED_USER_ID`
2. `MCP_PILOT_ALLOWED_EMAIL`

Fail closed if the expected pilot identifiers are not configured.

### Open auth questions

1. exact OAuth callback/token mechanics depend on the chosen remote MCP auth pattern
2. final auth middleware/hook shape should follow the official SDK and Claude remote MCP expectations, not be invented ad hoc

## Slice 0 tool contract

### Tool: `resolve_client`

Purpose:

1. resolve a free-text client query to canonical Agency OS clients before other tools are called

Input:

```json
{
  "query": "string"
}
```

Output:

```json
{
  "matches": [
    {
      "client_id": "uuid",
      "client_name": "string",
      "active_wbr_marketplaces": ["US", "CA"]
    }
  ]
}
```

Rules:

1. return only clients relevant to the WBR-first pilot
2. include active WBR marketplace coverage in the response
3. do not silently choose a match
4. return `{ "matches": [] }` on no match

### Reuse seam

Implement against current WBR/client lookup data, not Slack skill prompts.

## Logging expectations

For slice 0, use normal backend logging.

Each invocation log should include:

1. tool name
2. Agency OS user id
3. success/error outcome
4. timestamp
5. whether the tool is read-only or mutating

Do not create a new DB logging table in slice 0.

## Acceptance criteria

### Slice 0 is complete when

1. the MCP server mounts successfully in `backend-core`
2. MCP Inspector can connect
3. Jeff can authenticate
4. a non-allowlisted user cannot authenticate or use tools
5. `resolve_client` works end to end

### Manual smoke tests

1. Claude Pro connects to the private `agency-os` integration
2. `resolve_client("Whoosh")` returns canonical matches
3. `resolve_client("Basari")` returns the expected WBR-relevant client match candidates

## Test plan

1. unit tests for allowlist auth
2. unit tests for `resolve_client`
3. app-mount test for the MCP server
4. MCP Inspector smoke test
5. Claude Pro manual smoke test

## Next slices

### Slice 1

1. `list_wbr_profiles`
2. `get_wbr_summary`

### Slice 2

1. `draft_wbr_email`
2. mutation logging expectations tightened for draft creation

### Later

1. `get_monthly_pnl_report`
2. `list_child_asins`
3. `query_adscope_view`

## Open questions

1. What exact path shape will the official MCP SDK require once mounted in FastAPI?
2. What exact remote-MCP auth flow is required by Claude for this runtime?
3. Should `resolve_client` stay WBR-scoped in slice 0 or eventually become a shared client resolver across multiple tool domains?
