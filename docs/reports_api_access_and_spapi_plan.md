# Reports API Access and Direct SP-API Plan

_Drafted: 2026-03-18 (ET)_

## Status update

This document began as the reviewed implementation plan. As of 2026-03-18 ET,
the first four slices are now implemented and deployed.

Implemented:

1. shared `report_api_connections` storage
2. admin `Reports / API Access` page at `/reports/api-access`
3. Amazon Ads shared connection visibility / launch
4. Amazon Seller API auth scaffolding
5. Seller API validation via `getMarketplaceParticipations`
6. Seller API finances smoke test via `listFinancialEventGroups` and
   `listTransactions`
7. region-aware Seller Central + SP-API routing for `NA`, `EU`, and `FE`
8. connection health semantics that distinguish:
   - `connected`
   - `error`
   - `revoked`
   - `not connected`

Operational notes from live rollout:

1. production initially failed because the shared table migration had not yet
   been applied; that is now fixed and the page is live
2. frontend Render deploys hit a broken default Node `22.16.0` image; frontend
   runtime is now pinned to `20.19.0`
3. current blocker is Amazon app-side approval/configuration, not internal
   code:
   - first observed auth error: `MD1000`
   - draft testing required `AMAZON_SPAPI_DRAFT_APP=true`
   - next observed auth error: `MD9100`
   - user has applied for public app approval and paused until Amazon responds
4. current expected SP-API app URIs for this implementation:
   - Login URI: `https://tools.ecomlabs.ca/reports/api-access`
   - Redirect URI: `https://backend-core-re6d.onrender.com/amazon-spapi/callback`
   - optional additional redirect URI:
     `https://backend-core-re6d.onrender.com/api/amazon-spapi/callback`
5. WBR Windsor flows and manual Monthly P&L CSV upload mode remain intact and
   are still the active stable paths while SP-API auth is blocked

## Goal

Create a shared `Reports / API Access` surface for external account
connections, move Amazon Ads connection management there, add Amazon Seller
API authorization there, and use the shared Seller API connection to build a
P&L-first direct-SP-API path.

This is not a full WBR rewrite and not an immediate replacement of the current
Monthly P&L CSV import flow.

## Reviewer checklist

Please review these decisions first:

1. Is the shared separation correct?
   - `API Access` owns auth/token storage/connection state
   - report settings own report-specific selections, backfills, and sync logic
2. Is the shared connection data model correct?
   - especially uniqueness, region handling, and whether `client_id` should be
     the ownership anchor
3. Is the Amazon Ads split correct?
   - move connection management to shared API Access
   - keep advertiser-profile selection and WBR sync behavior inside WBR
4. Is the Amazon Seller API auth flow correct?
   - signed state
   - seller callback with `selling_partner_id` and `spapi_oauth_code`
   - refresh-token storage in shared connection table
5. Are the first SP-API validation targets correct?
   - Sellers API `getMarketplaceParticipations`
   - Finances/payment-disbursement smoke test via
     `listFinancialEventGroups` and `listTransactions`
6. Is the rollout sequence correct?
   - shared API Access and Ads connection move first
   - Seller API auth second
   - P&L-first direct-SP-API smoke test third
7. Are any major migration or security concerns missing?
   - especially old-table deprecation, refresh-token storage, and rate limits

## Why this is needed

Current connection management is fragmented:

1. Amazon Ads authorization is currently embedded inside WBR-specific backend
   and frontend flows.
2. Monthly P&L Windsor compare work has shown that Windsor adds financial
   translation risk we do not control.
3. Current working hypothesis: `non_pnl_transfer` will require Amazon
   payment/disbursement data that Windsor does not currently expose cleanly.

The resulting direction is:

1. centralize connection management
2. keep report-specific usage local
3. build direct Amazon financial access for P&L first

## Current state

### Amazon Ads auth

Current implementation already exists and works:

1. signed OAuth state + URL generation:
   [amazon_ads_auth.py](/Users/jeff/code/agency-os/backend-core/app/services/wbr/amazon_ads_auth.py)
2. public callback route:
   [amazon_ads_oauth.py](/Users/jeff/code/agency-os/backend-core/app/routers/amazon_ads_oauth.py)
3. WBR connect/status/profile-selection endpoints:
   [wbr.py](/Users/jeff/code/agency-os/backend-core/app/routers/wbr.py)
4. WBR UI connection and sync screen:
   [WbrAdsSyncScreen.tsx](/Users/jeff/code/agency-os/frontend-web/src/app/reports/_components/WbrAdsSyncScreen.tsx)

Current coupling problems:

1. refresh token storage is WBR-owned via `wbr_amazon_ads_connections`
2. auth state is keyed to WBR `profile_id`
3. connection management and WBR sync behavior are mixed together in one UI

Current live transition state:

1. Amazon Ads callback now dual-writes into shared `report_api_connections`
   while preserving legacy `wbr_amazon_ads_connections`
2. WBR Amazon Ads reads prefer shared connection storage when a healthy shared
   connection exists
3. WBR falls back to legacy storage when the shared Ads row is absent or not
   healthy
4. advertiser-profile selection remains WBR-owned

### Monthly P&L direct-Amazon status

Current SP-API setup progress:

1. Standardized env var names have been chosen for Render configuration:
   - `AMAZON_SPAPI_LWA_CLIENT_ID`
   - `AMAZON_SPAPI_LWA_CLIENT_SECRET`
   - `AMAZON_SPAPI_APP_ID`
2. Draft-auth env was needed during testing:
   - `AMAZON_SPAPI_DRAFT_APP=true`
3. Missing production credential for real calls:
   - seller-authorized refresh token

Important constraint:

1. client ID and client secret are not enough to call seller-authorized SP-API
   endpoints such as Finances API
2. we need a seller OAuth flow and refresh-token storage

Current live blocker:

1. seller OAuth flow is implemented and reaches Amazon successfully
2. production does not yet have a completed seller authorization
3. Amazon app approval/configuration is the blocker, not backend/frontend
   implementation

## Architecture principles

Separate these concerns:

### Shared API Access owns

1. connect / disconnect / reauthorize
2. token storage
3. connection health and validation
4. account discovery
5. provider-level metadata

### Report settings own

1. report-specific selections
2. backfills
3. refreshes
4. sync runs
5. compare logic
6. report-specific mappings

Implication:

1. Amazon Ads refresh token should move to shared connection management
2. WBR should still own:
   - `amazon_ads_profile_id`
   - `amazon_ads_account_id`
   - backfill / daily refresh
   - Section 2 sync behavior
3. Amazon Seller API connection should be shared
4. P&L should own direct-finance backfill/compare behavior

This shared-vs-report-specific split is the controlling design rule for the
rest of this plan.

## Product design

### New shared page

Add an admin-only page:

1. route recommendation: `/reports/api-access`

Alternative:

1. `/reports/integrations`

Recommendation:

1. use `/reports/api-access`
2. it is clearer that this page is about account authorization and connection
   state, not generic report settings

### Initial sections on the page

1. `Amazon Seller API`
2. `Amazon Ads`
3. optional later placeholder: `Windsor`

Each section should show:

1. connected / not connected
2. connected at
3. account identifier / hint
4. last validation result
5. connect button
6. reconnect / reauthorize button
7. disconnect button
8. lightweight metadata summary

## Data model

### Recommendation

Add a shared connection table instead of storing auth only inside report-local
tables.

Recommended table:

1. `report_api_connections`

Recommended columns:

1. `id uuid primary key default gen_random_uuid()`
2. `client_id uuid not null references public.agency_clients(id) on delete restrict`
3. `provider text not null`
   - expected initial values:
     - `amazon_ads`
     - `amazon_spapi`
4. `connection_status text not null default 'connected'`
   - expected values:
     - `connected`
     - `error`
     - `revoked`
5. `external_account_id text`
   - Ads: LWA account hint if available
   - SP-API: `selling_partner_id`
6. `refresh_token text`
7. `access_meta jsonb not null default '{}'::jsonb`
8. `connected_at timestamptz`
9. `last_validated_at timestamptz`
10. `last_error text`
11. `created_by uuid references public.profiles(id)`
12. `updated_by uuid references public.profiles(id)`
13. `created_at timestamptz not null default now()`
14. `updated_at timestamptz not null default now()`

Recommended uniqueness:

1. Day-one assumption: one shared connection per `client_id + provider`.
2. Use a unique index on `(client_id, provider)` for the first implementation.
3. Add `region_code text` as metadata from the start.
4. Expected `region_code` values:
   - `NA`
   - `EU`
   - `FE`
5. If we later need multiple seller accounts per client/provider, widen the
   uniqueness rule in a follow-up migration once the real usage pattern exists.
6. This keeps the first rollout simple while still recording enough metadata to
   evolve later.

### What should remain report-specific

Do not move these fields into shared auth storage:

1. WBR `amazon_ads_profile_id`
2. WBR `amazon_ads_account_id`

Reason:

1. those are WBR usage decisions, not connection-level credentials

## Amazon Ads migration plan

### Backend refactor path

#### Phase A: non-breaking storage refactor

1. introduce `report_api_connections`
2. update Ads callback to write to shared connection storage
3. keep current WBR endpoints working
4. update WBR sync service to read refresh token from shared connection storage
5. exact lookup change:
   - current: `profile_id -> wbr_amazon_ads_connections`
   - target: `wbr_profile.client_id -> report_api_connections where provider = 'amazon_ads'`

#### Phase B: UI relocation

1. move Ads connection card to `Reports / API Access`
2. replace WBR connect flow with:
   - status summary
   - link to `API Access`

#### Phase C: old table deprecation

1. backfill `report_api_connections` from `wbr_amazon_ads_connections`
2. move all reads to `report_api_connections`
3. stop all writes to `wbr_amazon_ads_connections`
4. keep the old table temporarily as legacy data only
5. mark it deprecated in docs once production reads are switched
6. drop it in a later cleanup migration after validation

### Impact

Low to medium.

Main risks:

1. token lookup regression in WBR ads sync
2. callback state tied too tightly to current `profile_id`
3. duplicated or stale connection data during migration

Mitigation:

1. keep current WBR endpoints temporarily as wrappers
2. migrate read path before removing old UI
3. add focused tests around token lookup and callback persistence

## Amazon Seller API authorization plan

### Goal

Add a seller OAuth flow so we can obtain and store a seller refresh token for
SP-API.

### Backend components

Recommended new files:

1. `backend-core/app/services/reports/amazon_spapi_auth.py`
2. `backend-core/app/routers/report_api_access.py`

Potentially reuse patterns from:

1. [amazon_ads_auth.py](/Users/jeff/code/agency-os/backend-core/app/services/wbr/amazon_ads_auth.py)
2. [amazon_ads_oauth.py](/Users/jeff/code/agency-os/backend-core/app/routers/amazon_ads_oauth.py)

### Required env vars

1. `AMAZON_SPAPI_LWA_CLIENT_ID`
2. `AMAZON_SPAPI_LWA_CLIENT_SECRET`
3. `AMAZON_SPAPI_APP_ID`
4. `AMAZON_SPAPI_DRAFT_APP` during draft/beta auth testing

### Auth flow

1. admin clicks `Connect Amazon Seller API`
2. backend creates signed state
3. backend builds Seller Central auth URL
4. browser redirects to Amazon
5. seller authorizes app
6. callback receives:
   - `state`
   - `selling_partner_id`
   - `spapi_oauth_code`
7. backend validates state
8. backend exchanges `spapi_oauth_code` for refresh token
9. backend stores connection in `report_api_connections`
10. backend runs a validation call
11. backend redirects back to frontend API Access page

Implemented additions:

1. state now records explicit `region_code`
2. stored shared connection also records `region_code`
3. downstream validate + finance smoke test use the stored region
4. frontend requires explicit region selection before launch
5. redirect errors are surfaced back on `/reports/api-access`

Error handling should follow the existing Amazon Ads callback patterns:

1. invalid or expired state
2. user denied authorization
3. token exchange failure
4. database write failure
5. redirect back to a frontend path that can surface failure cleanly

### Draft-app note

If the SP-API app is still in draft/beta during testing, the auth URL should
include the appropriate beta/draft version parameter for the seller auth flow.
Treat this as a potential implementation blocker, not a cosmetic detail.

Observed live result:

1. draft-app handling was required in practice
2. after enabling draft mode, the next observed blocker became Amazon app
   configuration / approval rather than auth URL construction itself

### Connection validation target

First validation should be lightweight and explicit.

Recommended first validation:

1. fetch an LWA access token using the stored refresh token
2. call Sellers API `getMarketplaceParticipations`
3. persist last-success / last-error status

Status:

1. implemented
2. deployed
3. blocked on obtaining the first real seller refresh token

## Monthly P&L direct-SP-API plan

### Recommendation

Do not replace Monthly P&L CSV imports immediately.

Instead:

1. keep CSV-backed months as source of truth
2. add a direct-Amazon compare path beside the current Windsor compare
3. use that path to validate direct Amazon financial coverage

### Why P&L first

1. P&L is the urgent reconciliation problem
2. `non_pnl_transfer` is the main reason to validate Amazon
   payment/disbursement access directly
3. Windsor has already shown source-boundary mismatches on financial rows
4. a full WBR migration is much broader and should wait

### Recommended first deliverable

Build a smoke-test endpoint before full ingestion:

1. use stored seller refresh token
2. get a fresh access token
3. run connection validation via Sellers API `getMarketplaceParticipations`
4. then hit the first finance/payment endpoint
5. return raw or lightly normalized JSON for one recent window

This should answer:

1. can we authenticate successfully?
2. can we see payment/disbursement identifiers?
3. do we have a clean path for `non_pnl_transfer`?

### Finance smoke test target

The finance smoke test should target the payment/disbursement path specifically,
not just any finance endpoint.

Recommended sequence:

1. deliberately test the two-API payment flow Amazon documents:
   - Finances API v0 `listFinancialEventGroups`
   - Finances API v2024-06-19 `listTransactions`
2. call Finances API v0 `listFinancialEventGroups`
3. confirm we receive financial event group identifiers and group totals
4. pick one returned `FinancialEventGroupId`
5. call Finances API v2024-06-19 `listTransactions` with:
   - `relatedIdentifierName = FINANCIAL_EVENT_GROUP_ID`
   - `relatedIdentifierValue = <FinancialEventGroupId>`
   - `transactionStatus = RELEASED`
6. inspect whether the returned payment transactions provide the data needed to
   explain or reconstruct `non_pnl_transfer`

This is the right smoke test because it directly tests the current gap around
payout/disbursement visibility and matches Amazon’s own documented tutorial for
determining which released transactions make up a payment.

### Rate-limit note

SP-API throttling should be assumed from day one.

Implications:

1. smoke tests should stay serialized and low-volume
2. backfill design should not assume naive tight loops
3. retry, pacing, and throttling should be centralized in the eventual
   implementation

### After smoke test

Recommended next step:

1. add `Amazon direct compare` beside `Windsor compare`
2. compare direct Amazon financial rows against CSV-backed month totals
3. keep direct-Amazon work compare-only until parity is trusted

## Ownership model recommendation

### Shared connection ownership key

Recommendation:

1. key shared connections by `client_id` as the ownership anchor
2. use uniqueness on `(client_id, provider)` for day one
3. widen later only if a real multi-account or multi-region need appears

Reason:

1. authorization is fundamentally an account/client connection, not a single
   report setting
2. WBR and P&L can both consume shared client-level connections
3. some clients may eventually need multiple external accounts or regions
4. report-specific decisions still stay local to each report profile

### What not to do

Avoid:

1. keying shared auth to a single WBR or P&L profile
2. storing one global SP-API refresh token in Render as the long-term design

Temporary exception:

1. a single env-var refresh token is acceptable only for short-lived smoke
   testing on one account

## Rollout sequence

Recommended execution order:

### Pass 1

1. add design/migration for `report_api_connections`
2. add shared `Reports / API Access` page shell
3. add Amazon Ads status/connect UI there
4. keep existing WBR endpoints working

### Pass 2

1. refactor Ads callback + storage to shared connection table
2. make WBR consume shared Ads connection
3. leave advertiser-profile selection and sync controls on WBR

### Pass 3

1. add Amazon Seller API connect flow
2. add public callback
3. store seller refresh token in shared connection table
4. add validation endpoint and UI status

### Pass 4

1. add P&L-first direct-SP-API smoke test
2. validate finance/payment-disbursement visibility
3. decide next compare-only direct-Amazon P&L step

## Risks and tradeoffs

### Benefits

1. one place to manage account auth
2. cleaner separation between auth and report logic
3. easier reuse of Amazon Seller API connection across P&L and future tools
4. reduced dependence on Windsor for financial truth

### Risks

1. connection migration could briefly break WBR Ads sync if token lookup is not
   updated correctly
2. Seller API auth introduces another public callback surface that must be
   secured with signed state
3. direct SP-API work can expand too broadly if not kept P&L-first
4. refresh tokens are still plain text unless we explicitly add at-rest
   encryption

### Token storage note

Current and proposed designs both store refresh tokens as normal database text
fields unless we add an encryption layer.

Recommendation:

1. document plaintext refresh-token storage as a known limitation if we do not
   address it immediately
2. prefer app-level or database-assisted encryption later
3. do not let encryption block the first connection-management refactor, but do
   track it explicitly

### Scope control

Keep the first implementation intentionally narrow:

1. shared API Access page
2. Ads connection move
3. Seller API auth
4. P&L smoke test

Do not include:

1. full WBR de-Windsor migration
2. full P&L source replacement
3. generic connector platform work beyond the needed cases

## Open decisions for review

Remaining review questions:

1. Is the day-one simplification to unique `(client_id, provider)` acceptable,
   with `region_code` captured as metadata and future widening deferred until a
   real multi-account need appears?
2. Is the documented Amazon Ads split still the right one:
   - connection management in shared API Access
   - advertiser-profile discovery and selection in WBR
3. Is the first Seller API sequence correct:
   - first `getMarketplaceParticipations`
   - then the payment/disbursement smoke test

Current recommendation:

1. keep route name as `/reports/api-access`
2. use the shared table name `report_api_connections`
3. keep Amazon Ads advertiser-profile discovery and selection in WBR
4. validate Seller API auth first, then run the finance/disbursement smoke test

## Recommendation summary

Recommended path:

1. create shared `Reports / API Access`
2. move only Amazon Ads connection management there
3. keep WBR-specific advertiser profile and sync controls in WBR
4. add Amazon Seller API auth there
5. use that shared Seller API connection for a P&L-first direct-SP-API smoke
   test before broader refactors
