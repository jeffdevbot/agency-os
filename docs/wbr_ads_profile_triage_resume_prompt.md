# WBR Ads Profile Triage Resume Prompt

_Last updated: 2026-03-25 (ET)_

Continue WBR Amazon Ads profile triage work in
`/Users/jeff/code/agency-os`.

Resolved-state note:

1. this is now a historical/reference restart prompt, not the primary active
   WBR entrypoint
2. on 2026-03-25 (ET), Lifestyle CA was checked live against a user-provided
   Amazon campaign export for `2026-03-16`
3. the DB matched that export exactly for:
   - ad spend: `80.37 CAD`
   - ad-attributed sales: `267.58 CAD`
4. if this thread reopens, start by confirming the exact console metric basis
   and date rather than assuming a fresh data mismatch still exists

Read first, in this order:

1. `docs/current_handoffs.md`
2. `docs/wbr_ads_profile_triage_handoff.md`
3. `docs/windsor_wbr_ingestion_runbook.md`
4. `AGENTS.md`

Before using the Supabase MCP, refresh auth in the terminal:

```bash
codex mcp logout supabase
codex mcp login supabase
codex mcp list
```

Important:

1. if MCP tool calls in the chat still return `Auth required` after that,
   assume stale chat-session state and start a fresh Codex session

If you do return to this thread, the target is:

1. verify the exact day/metric the user thinks is wrong
2. do live Supabase inspection first
3. compare against a concrete export before proposing code changes

Exact profiles:

1. Lifestyle US WBR profile:
   `67067450-9701-4b47-a42e-44d079ef60f6`
2. Lifestyle CA WBR profile:
   `11aad1a8-1ea2-407f-9cec-0c9fcc9939f4`

What is already proven:

1. Lifestyle US Section 2 was wrong because the old advertiser profile was
   selected:
   - old profile ID: `1002483439513772`
   - corrected profile ID: `3546678326685543`
2. after the US reruns:
   - March 16, 2026 DB spend = `196.93`
   - March 16-22, 2026 DB spend = `1590.49`
   - those matched manual export and Campaign Manager exactly
3. conclusion for US:
   - code path was fine
   - root cause was wrong advertiser-profile selection

Latest CA validated state:

1. after reconnect/reselection, the saved CA metadata became:
   - advertiser profile ID: `1002483439513772`
   - account ID: `A1RH4YRPSH6LRR`
   - country code: `CA`
   - currency code: `CAD`
   - marketplace string ID: `A2EUQ1WTGCTBG2`
2. unlike US, CA did not switch to a numerically different advertiser profile
   ID
3. live March 16, 2026 validation against the Amazon campaign export matched
   the DB exactly:
   - spend `80.37 CAD`
   - sales `267.58 CAD`
4. the three non-zero-sales campaigns also matched exactly between the DB and
   the export

Best first checks:

1. inspect latest `wbr_sync_runs` for Lifestyle CA after the reconnect
2. inspect `wbr_ads_campaign_daily` totals for the exact disputed day
3. compare the exact metric basis against Campaign Manager/manual export
4. if the user provides a day-level campaign export, compare campaign names,
   spend, and sales directly against the DB

Useful live comparison target:

1. the exact metric/day the user is citing
2. do not mix spend and sales when triaging console vs DB differences
3. do not assume a weekly mismatch if the checked day/export already matches

Constraints:

1. use live Supabase facts first
2. do not propose code changes unless the refreshed CA facts still look wrong
3. preserve the now-corrected US setup
4. remember that full Amazon Ads OAuth reconnect affects the shared client
   token, while advertiser-profile selection is per WBR profile
