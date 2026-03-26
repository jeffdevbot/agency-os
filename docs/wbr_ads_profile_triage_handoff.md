# WBR Ads Profile Triage Handoff

_Last updated: 2026-03-25 (ET)_

## Current debugging focus

This handoff is for the live WBR Amazon Ads profile/account triage work on the
Lifestyle client.

Resolved state as of 2026-03-25 (ET):

1. Lifestyle US was proven to have used the wrong advertiser profile and was
   fixed by selecting the correct one.
2. Lifestyle CA was rechecked live against a March 16 Amazon campaign export.
3. for that checked day, the CA DB facts matched the Amazon export exactly, so
   the immediate day-level validation thread is no longer blocked.

## Supabase MCP restart note

This chat hit the known stale Supabase MCP state issue again.

Use these terminal commands before the new session:

```bash
codex mcp logout supabase
codex mcp login supabase
codex mcp list
```

Expected rule:

1. if terminal login succeeds but MCP tool calls in the chat still return
   `Auth required`, treat the chat as stale session state
2. start a fresh Codex session instead of debating the config

## What was triaged

### Lifestyle US

Profile:

- WBR profile: `67067450-9701-4b47-a42e-44d079ef60f6`
- marketplace: `US`

What was wrong:

1. Section 1 business sales initially looked too low in WBR because unmapped
   ASIN sales were omitted from visible WBR rows.
2. Section 2 ads spend was initially wrong because the wrong Amazon Ads
   advertiser profile was selected.

Section 1 finding:

1. latest completed week `2026-03-16` through `2026-03-22`
   - raw business sales in DB: `9706.03`
   - mapped sales shown in WBR: `6874.83`
   - unmapped sales hidden from visible WBR rows: `2831.20`
2. user manually added missing leaf row labels for the missing ASINs in the
   WBR row config

Section 2 wrong-profile finding:

1. old/wrong advertiser profile ID:
   `1002483439513772`
2. corrected advertiser profile ID:
   `3546678326685543`
3. old bad March 16-22 weekly DB total:
   `508.04`
4. old bad March 16 daily DB total:
   `80.37`
5. manual March 16 campaign export total:
   `196.93`
6. manual/Campaign Manager March 16-22 weekly total:
   `1590.49`

What was proven after the fix:

1. after re-selecting the correct US advertiser profile and rerunning:
   - March 16 daily DB spend became `196.93`
   - March 16-22 weekly DB spend became `1590.49`
2. those now match the user’s manual export and Campaign Manager exactly
3. conclusion: the code path was fine; the original issue was the wrong
   advertiser profile selection

Operational details for US:

1. the corrected US reruns used the new profile ID
   `3546678326685543`
2. the first corrected 2-day rerun (`2026-03-16` to `2026-03-17`) took about
   `25m 46s`
3. the other corrected chunks finished in roughly `26 minutes`

### Lifestyle CA

Profile:

- WBR profile: `11aad1a8-1ea2-407f-9cec-0c9fcc9939f4`
- marketplace: `CA`

Pre-refresh suspicious state:

1. before reconnect/reselection, CA showed the same suspicious weekly ads
   spend pattern as the old wrong US dataset
2. March 16-22 daily CA DB spend before rerun was:
   - `2026-03-16`: `80.37 CAD`
   - `2026-03-17`: `70.38 CAD`
   - `2026-03-18`: `64.44 CAD`
   - `2026-03-19`: `91.33 CAD`
   - `2026-03-20`: `71.02 CAD`
   - `2026-03-21`: `58.17 CAD`
   - `2026-03-22`: `72.33 CAD`
3. pre-refresh March 16-22 weekly total was:
   `508.04 CAD`
4. that strongly suggested CA was also effectively pointed at the wrong
   advertiser-profile data

CA profile metadata after reconnect/reselection:

1. advertiser profile ID remained:
   `1002483439513772`
2. account ID:
   `A1RH4YRPSH6LRR`
3. new persisted metadata now says:
   - country code: `CA`
   - currency code: `CAD`
   - marketplace string ID: `A2EUQ1WTGCTBG2`
4. this means CA did not switch to a numerically different advertiser profile
   ID the way US did, but it did become explicitly tagged as Canada

What was proven on the 2026-03-25 validation pass:

1. the latest successful CA reruns were still using profile ID
   `1002483439513772`
2. live DB facts for `2026-03-16` summed to:
   - ad spend: `80.37 CAD`
   - ad-attributed sales: `267.58 CAD`
3. the user-provided Amazon campaign export for the same March 16 day matched
   those DB values exactly
4. the three non-zero-sales campaigns matched exactly between the DB and the
   export:
   - `B00OCTPXD4 - NZ Sheepskin Rugs | SB | PC-Store | MKW | Br.M | 0 - gen | Perf`
     - spend `2.55`, sales `142.09`, orders `2`
   - `B0B41XWZ2B - Medical Sheepskins | SPA | Mix. | Rsrch`
     - spend `5.55`, sales `73.48`, orders `1`
   - `B0DXYTQZJ4 - Poufs | SPA | Los. | Rsrch`
     - spend `9.32`, sales `52.01`, orders `1`
5. conclusion for the checked CA day:
   - the DB and Amazon export were aligned
   - the immediate March 16 CA validation is resolved
   - this did not reproduce the earlier US wrong-profile symptom on that
     checked day

## Important architecture note

Amazon Ads behavior here is subtle:

1. the OAuth connection refresh token is shared by `client_id` through
   `report_api_connections`
2. the selected advertiser profile ID is saved per WBR profile
3. queued/in-flight sync runs keep their own `amazon_ads_profile_id` in
   `wbr_sync_runs.request_meta`
4. but pending runs re-read the shared refresh token while polling
5. because of that:
   - re-selecting a WBR advertiser profile is safe while another run is in
     flight
   - full OAuth reconnect is better deferred until no other runs are still
     polling

## Code/product changes completed during this session

These are already pushed and live in the repo:

1. WBR now persists Amazon Ads advertiser-profile metadata on selection:
   - `amazon_ads_country_code`
   - `amazon_ads_currency_code`
   - `amazon_ads_marketplace_string_id`
2. repo migration:
   `supabase/migrations/20260325113000_add_wbr_amazon_ads_profile_metadata.sql`
3. pushed commit:
   `f337cbf` (`Store Amazon Ads profile metadata for WBR`)
4. migration was applied to the live Supabase DB

## If this thread reopens later

Start with live Supabase inspection first, then compare against a concrete
Amazon export using an absolute date and exact metric basis:

1. `wbr_profiles`
   - verify the current CA profile metadata row for
     `11aad1a8-1ea2-407f-9cec-0c9fcc9939f4`
2. `wbr_sync_runs`
   - inspect the latest CA `amazon_ads` reruns created after the reconnect
   - confirm `status = success`
   - confirm `request_meta->>'amazon_ads_profile_id'`
3. `wbr_ads_campaign_daily`
   - compare the exact day-level metric in question first
   - confirm whether the console number is spend, sales, or another view-level
     aggregate before treating it as a mismatch
   - then compute broader weekly totals only after the day-level basis is
     clear

## Main question answered

For the checked March 16, 2026 CA export, the refreshed Lifestyle CA
`wbr_ads_campaign_daily` facts matched Amazon exactly.
