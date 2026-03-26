# Supabase Python Client Upgrade Plan

_Drafted: 2026-03-26 (ET)_

Status: `queued for tonight review`

## Purpose

Capture the follow-up work to upgrade the backend Supabase Python client stack
cleanly, remove the deprecated `gotrue` warning path, and verify that the
Claude/MCP rollout did not create hidden dependency risk.

## Why This Exists

Current backend state:

1. `backend-core/requirements.txt` pins `supabase==2.6.0`.
2. The current installed stack still pulls `gotrue`.
3. Focused backend tests now emit this warning:

```text
DeprecationWarning: The `gotrue` package is deprecated ... use `supabase_auth` instead.
```

This warning is not caused by the new ClickUp MCP code. It comes from the
underlying Supabase Python client dependency chain.

## Important Risk Callout

This should **not** require re-authing every Amazon Ads or Windsor account.

Why:

1. Amazon Ads refresh tokens are stored in database rows, not in transient
   local sessions.
2. WBR Amazon Ads reads those stored refresh tokens from:
   - `report_api_connections` (shared current source), or
   - `wbr_amazon_ads_connections` (legacy fallback)
3. Windsor WBR syncing is keyed by stored `windsor_account_id` on
   `wbr_profiles`, not by an interactive OAuth session per account.

So the likely blast radius is backend DB/client compatibility, not mass
credential reconnect work.

## What Changed Recently vs What Did Not

Recent Claude/MCP auth work did happen this week, but it was not a Python
Supabase client migration.

Recent relevant commits:

1. `9c7b79c` — Agency OS MCP pilot foundation
2. `8fde50e` — JWKS auth compatibility for Supabase OAuth
3. `96d4167` — Claude OAuth consent redirect fix
4. `36eedd4` — Supabase OAuth consent page for Claude MCP auth
5. `67af25d` — MCP metadata CORS fix for Claude connector auth

What did **not** happen this week:

1. no move from `gotrue` to `supabase_auth`
2. no Supabase Python dependency refresh
3. no repo-wide migration away from `supabase.create_client(...)`

## Proposed Tonight Scope

1. inspect the latest compatible `supabase` Python package version
2. determine whether the warning disappears via package upgrade alone
3. identify any API incompatibilities before touching production
4. run the auth-sensitive backend suites on a branch
5. decide whether to ship immediately, defer, or add a temporary pytest warning
   filter while the real upgrade is prepared

## Minimum Validation Suite

Run at least:

1. `backend-core/tests/test_auth_jwt_verification.py`
2. `backend-core/tests/test_mcp_pilot.py`
3. `backend-core/tests/test_mcp_clickup.py`
4. `backend-core/tests/test_amazon_ads_auth.py`
5. `backend-core/tests/test_amazon_spapi_auth.py`
6. `backend-core/tests/test_report_api_access.py`
7. targeted WBR / P&L smoke tests if the upgrade touches client init behavior

## Decision Rules

Ship the upgrade only if:

1. the deprecation warning is removed or clearly moved onto a newer supported
   stack
2. Claude MCP auth still works
3. WBR / Reports API auth flows still work
4. Amazon Ads and SP-API token refresh flows still pass
5. there is no evidence of stored token or credential-row breakage

Do **not** ship if:

1. it forces credential reconnects
2. it changes backend auth behavior in a way that needs same-day firefighting
3. it creates uncertainty before client-facing work

## Fallback If Upgrade Is Not Safe Tonight

If the real dependency upgrade looks risky:

1. document the exact package/version issue
2. keep the warning visible in engineering notes
3. optionally add a narrow pytest warning filter so routine test output is
   readable
4. schedule the actual upgrade as its own contained platform task

## Likely Output

Best case:

1. small dependency bump
2. green auth-sensitive test suite
3. warning removed

Medium case:

1. upgrade path identified
2. branch proves there are a few API changes to handle
3. task moves from “worry” to “planned engineering cleanup”

Worst case:

1. upgrade reveals real auth-client incompatibilities
2. we defer until there is safe calendar room
3. no production change is made before meetings or client work
