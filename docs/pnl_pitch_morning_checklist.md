# P&L Pitch — Morning Checklist

Saved overnight by Claude after we hit the chunk-size scaling cliff. Read this first when you wake up.

## TL;DR — what happened overnight

- ✅ March 2026 (701s) — the gold standard
- ✅ **September 2025 succeeded** (1072s / 17:52)
- ✅ **August 2025 succeeded** (2029s / 33:49 — well past any prior failure point)
- 🧹 **Cleanup done**: orphaned `raw_rows` + `ledger_entries` + `bucket_totals` + `sku_units` + `import_months` from the 5 statement-timeout failures all DELETEd to clear the way for clean retries
- 🔁 **Re-queue done**: all 7 errored imports (Oct, Nov, Dec, Jan, Feb 2026 + Jun, Jul 2025) flipped from `error` to `pending`, raw_meta progress reset to "queued" with the `async_import_v1=true` flag preserved so the worker claims them
- ✅ Code fix shipped: `IMPORT_INSERT_CHUNK_SIZE` 500 → 100 (commit `ec73b7f`)
- ✅ Service-role `statement_timeout` bumped to 10 min
- ✅ Worker memory bumped to 2 GB

**By the time you read this**, the worker should have already started chewing through the retries. Each is ~30-50 min based on Aug's 33:49 + table-growth slowdown. Total queue time ≈ 4-5 hours.

## Step 1 — Check the queue first

Run this query — if status looks healthy, you can skip ahead and just verify the report:

```sql
SELECT
  source_filename,
  import_status,
  CASE
    WHEN import_status = 'success' THEN '✅'
    WHEN import_status = 'running' THEN '🔄'
    WHEN import_status = 'pending' THEN '⏳'
    ELSE '❌'
  END AS state,
  raw_meta -> 'async_import_progress_v1' ->> 'detail' AS detail,
  EXTRACT(EPOCH FROM (finished_at - started_at))::int AS runtime_sec
FROM monthly_pnl_imports
WHERE source_type = 'amazon_transaction_upload'
  AND created_at > now() - interval '24 hours'
ORDER BY created_at DESC;
```

**Best case** (everything worked overnight): all 10 rows are ✅ success. Skip to Step 6.
**Mixed case**: some ✅, some ❌ with statement_timeout errors. See Step 2 to investigate.
**Worst case**: most ❌. Pitch goes with what we have (March, Sep, Aug at minimum).

## Step 2 — If retries failed: verify Render redeployed

Open Render dashboard → `worker-sync` → check the "Deploys" tab. Most recent deploy should reference commit `ec73b7f` (chunk-size fix) or later. If not, click **Manual Deploy → Deploy latest commit**. Takes ~2 min.

If retries failed even with `ec73b7f` live, drop chunk size further (e.g. 100 → 50 or 25) by editing `IMPORT_INSERT_CHUNK_SIZE` in `backend-core/app/services/pnl/transaction_import_store.py`, push, redeploy, then redo Step 5.

## Step 2 — Confirm `statement_timeout` is still set

```sql
SELECT rolname, rolconfig
FROM pg_roles
WHERE rolname = 'service_role';
```

You want to see `statement_timeout=10min` in `rolconfig`. If it's gone (Supabase reverted it), re-apply it before flipping anything to pending.

## Step 3 — Confirm cleanup happened (already done overnight)

Last night's imports left orphaned rows in `monthly_pnl_raw_rows` and `monthly_pnl_ledger_entries`. Reports already ignore them (their `import_month.is_active=false`), but they bloat the indexes and slow future inserts. **Already executed by the overnight run** — verify with:

```sql
SELECT
  i.source_filename,
  i.import_status,
  COALESCE(SUM(CASE WHEN r.import_id IS NOT NULL THEN 1 END), 0) AS leftover_raw_rows,
  COALESCE(SUM(CASE WHEN l.import_id IS NOT NULL THEN 1 END), 0) AS leftover_ledger_rows
FROM monthly_pnl_imports i
LEFT JOIN monthly_pnl_raw_rows r ON r.import_id = i.id
LEFT JOIN monthly_pnl_ledger_entries l ON l.import_id = i.id
WHERE i.source_type = 'amazon_transaction_upload'
  AND i.import_status = 'error'
  AND i.created_at > now() - interval '24 hours'
GROUP BY i.id, i.source_filename, i.import_status
ORDER BY i.created_at;
```

All `leftover_*` columns should be 0.

## Step 4 — Re-queue (already done overnight)

All 7 errored imports were flipped from `error` to `pending` overnight with the `async_import_v1=true` flag preserved. If somehow they're back to `error` and not yet retried, you can re-flip them with:

```sql
UPDATE monthly_pnl_imports
SET
  import_status = 'pending',
  error_message = NULL,
  started_at = NULL,
  finished_at = NULL,
  raw_meta = jsonb_set(
    raw_meta,
    '{async_import_progress_v1}',
    jsonb_build_object(
      'stage', 'queued',
      'detail', 'Re-queued after chunk-size fix and partial-data cleanup',
      'heartbeat_at', to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"+00:00"')
    )
  )
WHERE source_type = 'amazon_transaction_upload'
  AND import_status = 'error'
  AND error_message LIKE '%statement timeout%'
  AND created_at > now() - interval '24 hours'
RETURNING id, source_filename;
```

## Step 5 — Watch them complete

```sql
SELECT
  source_filename,
  import_status,
  CASE
    WHEN import_status = 'success' THEN '✅'
    WHEN import_status = 'running' THEN '🔄'
    WHEN import_status = 'pending' THEN '⏳'
    ELSE '❌'
  END AS state,
  raw_meta -> 'async_import_progress_v1' ->> 'detail' AS detail,
  EXTRACT(EPOCH FROM (now() - started_at))::int AS sec_running,
  EXTRACT(EPOCH FROM (finished_at - started_at))::int AS runtime_sec
FROM monthly_pnl_imports
WHERE source_type = 'amazon_transaction_upload'
  AND created_at > now() - interval '24 hours'
ORDER BY created_at DESC;
```

Total queue time for ~9 files at ~20 min each, processed 1 at a time = **~3 hours after you flip them to pending**. Plenty of time before the pitch if you do this in the morning.

## Step 6 — Once finished, open the report

Navigate to the P&L report for the client's profile. With 13 months of data (Mar 2025 → Mar 2026), you'll be able to demo:
- Trailing 12-month P&L
- YoY view (once you have a full 12 months in 2025)
- Month-over-month trends

## Things that might go sideways

**If imports keep failing with `code: '57014'`:** the chunk size is still too big for the current ledger table volume. Drop it further — 50, then 25 — by editing `IMPORT_INSERT_CHUNK_SIZE` in `backend-core/app/services/pnl/transaction_import_store.py`, commit, push, redeploy. Each halving roughly halves per-chunk time.

**If imports fail with a different error:** ping me with the `error_message` value from the import row.

**If the queue gets stuck (no progress for >20 min on a single import):** the worker may have died. Check Render `worker-sync` logs and restart if needed.

## Files staged for retry

These all have `storage_path` set, so re-queue works without re-upload:

- 2025JunMonthlyUnifiedTransaction.csv (manually stopped)
- 2025JulMonthlyUnifiedTransaction.csv (manually stopped)
- 2025AugMonthlyUnifiedTransaction.csv (likely errored overnight)
- 2025SepMonthlyUnifiedTransaction.csv (likely errored overnight)
- 2025OctMonthlyUnifiedTransaction.csv (errored at 11:02)
- 2025NovMonthlyUnifiedTransaction.csv (errored at 4:27)
- 2025DecMonthlyUnifiedTransaction.csv (errored at 7:18)
- 2026JanMonthlyUnifiedTransaction.csv (errored at 3:33)
- 2026FebMonthlyUnifiedTransaction.csv (errored at 4:30)
