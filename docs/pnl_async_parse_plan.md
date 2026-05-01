# Implementation Plan — Defer P&L Transaction Parsing to the Worker

## Context

The P&L manual upload endpoint (`POST /admin/pnl/profiles/{profile_id}/transaction-upload`) currently parses the entire CSV synchronously inside the FastAPI request handler before responding to the browser. The worker then re-parses the same file when it picks up the queued import. Two parses, both holding the full file in memory.

This caps reliable file size at the conservative `MAX_UPLOAD_MB=40` env value because of:
- proxy/browser timeouts during the synchronous parse,
- API-container peak memory under large parses,
- redundant CPU.

**Goal:** make the upload endpoint a thin "stage + queue" call. All parsing, ledger expansion, and per-row work happens exclusively in `worker-sync`.

**Non-goals:** changing the report path, the COGS / other-expenses paths, or the schema. No DB migration is needed — the schema is already permissive enough.

## Deployment prerequisite

`worker-sync` was on Render's **Starter** plan (0.5 CPU / 512 MB) and has been bumped to **Standard** (1 CPU / 2 GB). 2 GB gives comfortable headroom for the worker's combined parse + per-month insert-payload materialization peak (~1.2–1.5 GB on a 50 MB / ~150k-row Amazon Monthly Unified Transaction Report); 512 MB would have OOM'd.

The API container can stay on Starter (512 MB). After this change its peak memory during an upload is roughly **2× the uploaded file size plus multipart/storage-client overhead** — the router buffers chunks in `chunks: list[bytes]` then does `b"".join(chunks)` at `pnl.py:287` and `:306`, so both representations exist briefly. For `MAX_UPLOAD_MB=100` that's a transient ~210–250 MB peak, which still fits comfortably in 512 MB. No parsed object graph is held on the API container.

## Schema confirmation (already verified — no migration required)

`monthly_pnl_imports` columns relevant to this change:

| column | nullable? | default | notes |
|---|---|---|---|
| `period_start` | YES | NULL | already nullable |
| `period_end` | YES | NULL | already nullable |
| `import_scope` | YES | NULL | already nullable; CHECK enforces value ∈ {single_month, multi_month, full_year} when not null |
| `row_count` | NO | 0 | leave NOT NULL; insert with default 0, worker UPDATEs after parse |
| `import_status` | NO | 'pending' | unchanged |
| `source_file_sha256` | YES | NULL | unchanged |

Dedupe unique index is partial: `WHERE source_file_sha256 IS NOT NULL AND import_status = 'running'` (live state per `pg_index`; the original migration `20260315200000_monthly_pnl_phase1_foundation.sql:81` was relaxed by `20260316173000_allow_monthly_pnl_reimport_same_sha.sql:12-15` to allow same-SHA re-imports after a prior success). It does not fire on `pending` or `success` rows, so two queued uploads of the same file won't collide at queue time. The duplicate guard at queue time runs in application code (`_check_duplicate`) and that path stays — see §0 below for the precise dedupe semantics this plan preserves.

## §0 Dedupe semantics — preserved by this plan

The current behavior of `_check_duplicate` (`transaction_import.py:401-442`) is preserved verbatim. The plan does not change dedupe policy. For Codex's benefit, the policy is:

- Same-SHA upload while a non-stale `running` import for the same file exists → **409 Conflict** (`PNLDuplicateFileError`).
- Same-SHA upload after the prior import reached `success` → **allowed**; the new import is created with `supersedes_import_id` pointing at the prior success row, and `deactivate_superseded_months` runs at worker success time. **No 409.**
- Same-SHA upload while the prior `running` import is past `STALE_RUNNING_IMPORT_AGE` → the stale one is marked `error` first, then the new upload proceeds (no 409).

**Pending-window race — fix is in scope (§7b below).** Today this race exists but is small because the upload endpoint parses synchronously, so `pending` rows are short-lived (only between insert and the worker's next 60s poll, and even that doesn't occur until parse finishes — which is itself slow). Deferring the parse widens that window meaningfully: the API will create `pending` rows in a few seconds, and the worker may take 30–60 s to claim. A double-click, refresh, or impatient retry from the user becomes a real chance of two `pending` rows for the same file. When the worker then claims the second one, the partial unique index will fire on the `running` UPDATE and the claim will fail. We're fixing this here rather than deferring — see §7b.

## Code changes

All paths are relative to `/Users/jeff/code/agency-os`.

### 1. `backend-core/app/services/pnl/transaction_import.py` — `enqueue_file`

**Currently (lines ~64–123):** hashes the file → checks duplicates → calls `_prepare_import` (full parse + ledger expansion) → uploads to storage → creates the import row populated with `period_start`, `period_end`, `import_scope`, `row_count` from the parsed result → builds and returns pending-month summaries from `prepared`.

**Change to:** hash the file → check duplicates (unchanged, sha256-only) → upload to storage → create the import row with `period_start=None`, `period_end=None`, `import_scope=None`, omit `row_count` so the column default (0) takes effect → return `{import: <record>, months: [], summary: {file_size_bytes, queued_at}}`.

Specifically:
- Remove the `_prepare_import(...)` call from `enqueue_file`. Move all of its work into the worker path only.
- Build the queue-time progress payload without `prepared`. Replace the `_build_progress_payload(prepared=prepared, ...)` call inside `enqueue_file` with a new helper, e.g. `_build_queue_progress_payload(file_size_bytes, queued_at)`, that produces:
  ```python
  {
      "stage": "queued",
      "detail": "Queued for worker-sync background processing",
      "heartbeat_at": queued_at,
      "file_size_bytes": file_size_bytes,
  }
  ```
  Do **not** include `total_raw_rows`, `total_months`, `period_start`, `period_end`, `import_scope`, or `months_total` at this stage — they're unknown until the worker parses.
- The return shape becomes `{"import": import_record, "months": [], "summary": {"file_size_bytes": <int>, "queued_at": <iso>}}`. This is intentional: callers that read `months`/`summary` for parsed totals must wait for the worker (the frontend already polls via `getPnlImportSummary`, see §4).
- Keep the existing storage-upload-then-DB-insert ordering with the rollback-on-failure path (`_delete_source_file` if the insert raises). Unchanged.

### 2. `backend-core/app/services/pnl/transaction_import.py` — `process_import`

**Currently (lines ~169–217):** downloads the staged file → parses → calls `_run_import`. Already does the parse — that's the canonical parse location going forward.

**Change to:** after `_prepare_import` succeeds and **before** `_run_import` starts, persist the parsed-derived metadata onto the import row so it stops being `NULL`. Specifically, between the existing `prepared = self._prepare_import(...)` and the `return self._run_import(...)`, add:

```python
self.store.update_import_parsed_metadata(
    import_id,
    period_start=prepared.period_start,
    period_end=prepared.period_end,
    import_scope=prepared.import_scope,
    row_count=len(prepared.raw_rows),
)
```

Wrap the existing parse step's exception handler so a parse failure leaves `import_status='error'` (already does this) **and** the columns remain NULL — that's an acceptable error state.

### 3. `backend-core/app/services/pnl/transaction_import_store.py`

Two changes here, not one — the existing `create_import` signature requires non-null parsed metadata, which conflicts with the queue-time path.

**3a. Loosen `create_import` signature.** Currently (`transaction_import_store.py:130-178`) the method takes `period_start: str`, `period_end: str`, `import_scope: str`, `row_count: int` and always includes those keys in the insert payload. Change to:

```python
def create_import(
    self,
    *,
    profile_id: str,
    source_type: str,
    file_name: str,
    file_sha256: str,
    period_start: str | None,        # ← was str
    period_end: str | None,          # ← was str
    import_scope: str | None,        # ← was str
    row_count: int | None,           # ← was int
    user_id: str | None,
    supersedes_import_id: str | None,
    storage_path: str | None = None,
    raw_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "profile_id": profile_id,
        "source_type": source_type,
        "source_filename": file_name,
        "source_file_sha256": file_sha256,
        "import_status": "pending",
    }
    if period_start is not None:
        payload["period_start"] = period_start
    if period_end is not None:
        payload["period_end"] = period_end
    if import_scope is not None:
        payload["import_scope"] = import_scope
    if row_count is not None:
        payload["row_count"] = row_count
    # ...rest unchanged (supersedes_import_id, initiated_by, storage_path, raw_meta, insert + clear_hash retry)
```

The legacy `import_file` path (which still calls `create_import` with full parsed metadata) keeps working because it passes non-null values; the conditional inclusion is a strict superset of the old behavior.

**3b. Add `update_import_parsed_metadata`.** Place near `update_import_status` (around line 199):

```python
def update_import_parsed_metadata(
    self,
    import_id: str,
    *,
    period_start: date,
    period_end: date,
    import_scope: str,
    row_count: int,
) -> None:
    self.db.table("monthly_pnl_imports").update(
        {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "import_scope": import_scope,
            "row_count": row_count,
        }
    ).eq("id", import_id).execute()
```

No other store changes.

### 4. Frontend — `frontend-web/src/app/reports/_components/PnlReportScreen.tsx` and progress labels

**The one frontend change that's non-optional:** `PnlReportScreen.tsx` around line 429 currently formats the upload-success message as `"Queued file for {monthLabel}"`, where `monthLabel` is derived from `result.months[0].entry_month`. With deferred parsing, `result.months` is empty at upload time, so `monthLabel` will be undefined. Change the success message to a month-agnostic string, e.g. `"Queued file. The worker will start processing it shortly."` — once polling kicks in, the user gets per-month progress within ~5s anyway.

`uploadPnlTransactionReport` (`pnlApi.ts:340`) destructures `{import, months}`; the existing `(data.months ?? []) as PnlImportMonth[]` already handles the empty array, so the type doesn't need changing. The polling path (`PnlReportScreen.tsx:300+`) already drives status and progress lines from `getPnlImportSummary`, so it stays unchanged.

**Recommended (UX polish, backend-side):** there is no "stage map" in `pnlImportProgress.ts` — `buildPnlImportProgressLines` (line 93) renders `progress.detail` verbatim and derives the rest from numeric counters. So the user-facing copy for the `queued` and `preparing` stages comes from whatever string the backend writes into `raw_meta.async_import_progress_v1.detail`. Make sure the `_build_queue_progress_payload` in §1 emits a clear string ("Queued for the worker — usually starts within 60 seconds") and that the `process_import` "preparing" progress update emits one too ("Worker is parsing the file"). No frontend code change required for the progress text itself — the useful copy is upstream.

### 5. `backend-core/app/services/pnl/transaction_import.py` — `import_file` (legacy synchronous path)

`import_file` is **not used in production** (only by router code and tests; grep confirms only `tests/test_pnl_transaction_import.py` calls it). Leave it alone — it remains a useful end-to-end test harness that exercises parse + insert in one call. Do not touch.

### 6. Tests

- `backend-core/tests/test_pnl_router.py`
  - The upload-endpoint tests assert the response shape from `enqueue_file`. Update assertions: `months` is now `[]`, `summary` now contains `{file_size_bytes, queued_at}` instead of the parsed totals. The import row should still be returned with `import_status='pending'`.
  - Add a test that asserts `enqueue_file` does **not** call `_prepare_import` (or, equivalently, that no parse occurs and large invalid CSV bytes don't surface a `PNLValidationError` until the worker runs).

- `backend-core/tests/test_pnl_transaction_import.py`
  - Existing `enqueue_file` tests need updates for the new response shape.
  - Existing `import_file` tests stay unchanged — they cover the parse path that now lives in the worker.
  - Add a test for `process_import` that asserts after parse, the import row has `period_start`, `period_end`, `import_scope`, and `row_count` populated correctly. The simplest path is to call `enqueue_file` then `process_import` against the same in-memory fake DB and assert the final row state.

- `backend-core/tests/test_pnl_worker.py`
  - Should already cover `process_import` indirectly via `run_pending`. Add a happy-path assertion that after `run_pending`, the claimed import has parsed metadata persisted.

### 7. Robust progress tracking + dedupe tightening (newly in scope)

This section bundles three tightly-related changes that together close the staleness and dedupe holes that get worse under deferred parsing.

#### 7a. Switch staleness check to use heartbeat

`_is_stale_running_import` (`transaction_import.py:590-594`) currently keys off `started_at` (or `created_at`). It is called both inside the worker loop (`worker.py:37`) **and** inside `_check_duplicate` at queue time (`transaction_import.py:414`). With deferred parsing, a legitimate import on a 50–80 MB file can run >15 minutes total (parse + 600k–900k ledger inserts). Today's check would let a re-uploading user inadvertently mark that legitimate in-flight import as `error` and supersede it.

**Change:** read the heartbeat from `raw_meta.async_import_progress_v1.heartbeat_at` and use that as the staleness reference, falling back to `started_at` then `created_at`:

```python
def _is_stale_running_import(self, row: dict[str, Any]) -> bool:
    raw_meta = row.get("raw_meta") if isinstance(row.get("raw_meta"), dict) else None
    progress = (raw_meta or {}).get(ASYNC_IMPORT_PROGRESS_KEY) if raw_meta else None
    heartbeat_at = _parse_db_timestamp((progress or {}).get("heartbeat_at")) if isinstance(progress, dict) else None
    reference = heartbeat_at or _parse_db_timestamp(row.get("started_at")) or _parse_db_timestamp(row.get("created_at"))
    if reference is None:
        return False
    return (datetime.now(UTC) - reference) >= STALE_RUNNING_IMPORT_AGE
```

The listing query in `worker.py:80-94` already selects `raw_meta`, so no query change there. `_check_duplicate`'s `list_duplicate_candidates` (`transaction_import_store.py:75-93`) selects `id, import_status, created_at, started_at` — **add `raw_meta` to that select** so the heartbeat is available.

#### 7b. Tighten `_check_duplicate` to also 409 on `pending` collisions

Add a same-SHA `pending` check to `_check_duplicate` (`transaction_import.py:401-442`). After the existing running-import branch, before the success-superseded branch, add:

```python
pending_import = next(
    (row for row in filtered_rows if row.get("import_status") == "pending"),
    None,
)
if pending_import:
    raise PNLDuplicateFileError(
        f"This file is already queued for import (import {pending_import['id']})"
    )
```

This closes the rapid-upload race that the deferred-parse change makes more visible. Cost: a real second upload of the same file while the first is still `pending` returns 409 — same behavior as the existing running-collision case. The user can retry once the first import finishes (or hits success/error).

#### 7c. Heartbeat inside `_process_month_slice` so a single large month doesn't look stale

`_run_import` writes heartbeats only on month boundaries (`transaction_import.py:292-304`, `:314-327`). Inside `_process_month_slice` (`:444-520`) the worker can spend 5–15 minutes on raw/ledger/bucket/SKU inserts for a single 150k-row month with **no heartbeat refresh**. A duplicate-upload check arriving during that window would still mark the import stale even with the heartbeat-based check from §7a.

**Change:** emit a heartbeat between each insert phase inside `_process_month_slice`. Concretely, after each of these calls, call `self._update_import_progress(import_id, stage="processing_month", detail=<phase label>, ...)`:

1. after `_insert_raw_rows` → `detail="Inserted raw rows for {month}"`
2. after `_insert_ledger_entries` → `detail="Inserted ledger entries for {month}"`
3. after `_insert_bucket_totals` → `detail="Inserted bucket totals for {month}"`
4. after `_insert_sku_unit_totals` → `detail="Inserted SKU unit totals for {month}"`

Pass `import_id` into `_process_month_slice` if not already (it is — line 446). Use the existing `_update_import_progress` helper; pass `prepared=None` for these intermediate beats and supply only `stage`, `detail`, plus running counters if useful. Each heartbeat is one DB UPDATE — negligible compared to the insert workload.

This guarantees a heartbeat refresh at minimum every 1–4 minutes during the heaviest insert phase, even on a single large month.

### 8. Bump `MAX_UPLOAD_MB`

Raise `MAX_UPLOAD_MB` to **100** (in env config) **after** the code changes ship. The new architecture comfortably handles 50–80 MB files because the upload endpoint never touches the parsed object graph in memory — only `worker-sync` does, on its 2 GB container. Keep 100 MB as a soft guardrail rather than removing it entirely; Supabase storage uploads should also stay reasonable.

## Acceptance criteria

A successful run of this work means all of:

1. Uploading a 50–80 MB Amazon Monthly Unified Transaction Report no longer holds the HTTP request open through CSV parsing or ledger expansion. The response carries `import_status='pending'` and a populated `import.id`. **Measured target (not a guarantee):** server-side overhead beyond byte transfer + Supabase Storage upload + DB insert should be small (a few seconds at most). The two known sources of remaining server-side time are (a) the API-to-Supabase Storage upload, which depends on the API container's outbound throughput to Supabase, and (b) the `chunks: list[bytes]` → `b"".join(chunks)` buffer at `pnl.py:287/306`. Verify the actual end-to-end time on the production link, not in dev.
2. The frontend immediately shows "Background import status: queued" and transitions through `preparing → processing_month → success` without intervention.
3. Once the worker finishes, `monthly_pnl_imports.period_start`, `period_end`, `import_scope`, and `row_count` are populated for the import row.
4. The resulting report (`GET /profiles/{id}/report`) is identical to what the synchronous path would have produced for the same input file. Side-by-side a smaller test file before/after the change to confirm.
5. Same-file re-upload semantics (see §0 and §7b):
   - while a non-stale `running` import for that SHA exists → 409
   - while a `pending` import for that SHA exists → 409 (new behavior, closes the pending-window race)
   - after a `success` import for that SHA → allowed, supersedes; downstream months reactivate correctly
6. A long-running import (>15 min total) is **not** marked stale-error by either the worker loop or a duplicate-upload attempt, including the case where a single large month sits inside `_process_month_slice` for >15 minutes (verify via the new heartbeat-based staleness check from §7a and the intra-month heartbeats from §7c).
7. `pytest backend-core/tests/test_pnl_*.py` passes.

## Out of scope (do not touch)

- COGS upload, manual expenses, Windsor compare paths.
- The `pnl_claim_pending_imports` and `pnl_activate_month_slice` RPCs.
- The 15-minute *value* of `STALE_RUNNING_IMPORT_AGE` itself — keep at 15 minutes. Only the *reference timestamp* changes (heartbeat instead of `started_at`); see §7.
- Streaming CSV parsing inside the worker. The worker still loads the file into memory once. That's fine — `worker-sync` runs alone and 2 GB Standard sizing handles it.
- Streaming the per-table insert payloads (currently `insert_raw_rows` / `insert_ledger_entries` / `insert_bucket_totals` / `insert_sku_unit_totals` materialize the full payload list per month before chunking). Worth doing eventually for very large multi-month imports, but unnecessary at 2 GB worker memory for the current 50–80 MB target. Capture as a follow-up.

## Suggested execution order

1. Loosen `create_import` signature in the store (§3a) and add `update_import_parsed_metadata` (§3b).
2. Update `process_import` to call `update_import_parsed_metadata` after parse (§2).
3. Strip the parse out of `enqueue_file`, adjust the return shape, and add the queue-time progress payload helper (§1).
4. Switch `_is_stale_running_import` to the heartbeat-based reference (§7a), add the `pending` 409 branch to `_check_duplicate` (§7b), and add intra-month heartbeats inside `_process_month_slice` (§7c). Add `raw_meta` to `list_duplicate_candidates` select.
5. Update the success-message in `PnlReportScreen.tsx` (§4).
6. Update tests (§6).
7. Manual end-to-end test with a 50 MB+ file against staging. Confirm the report matches what the synchronous path produces on a smaller file. Verify a long import is not killed by a re-upload after 15 min.
8. Bump `MAX_UPLOAD_MB` in env config (§8).

## Reviewer checklist (for me to verify after Codex finishes)

- [ ] `enqueue_file` no longer calls `_prepare_import`.
- [ ] `process_import` persists parsed metadata before `_run_import` runs.
- [ ] `create_import` accepts `None` for `period_start`, `period_end`, `import_scope`, `row_count` and conditionally includes them in the insert payload; legacy `import_file` callers still pass non-null and behave as before.
- [ ] Storage rollback path on insert failure is preserved.
- [ ] Dedupe (`_check_duplicate`) still runs at queue time with the §0 semantics intact.
- [ ] `_is_stale_running_import` uses the heartbeat from `raw_meta.async_import_progress_v1.heartbeat_at` with a fallback ladder to `started_at` then `created_at`. `list_duplicate_candidates` selects `raw_meta`.
- [ ] `_check_duplicate` returns 409 on same-SHA `pending` rows (§7b).
- [ ] `_process_month_slice` emits a heartbeat between each insert phase (raw rows, ledger entries, bucket totals, SKU unit totals) (§7c).
- [ ] Upload response is well-formed when `months=[]` and `summary` is the new shape.
- [ ] Frontend success message no longer references `result.months[0].entry_month`.
- [ ] Backend writes useful `detail` strings for `queued` and `preparing` stages so `buildPnlImportProgressLines` renders meaningful copy.
- [ ] `import_file` (legacy sync) untouched.
- [ ] Tests cover: queue without parse, parse-failure leaves metadata NULL + status `error`, successful parse populates metadata, heartbeat-based staleness behaves correctly (a long-but-active import is not flagged stale; a truly abandoned one is).
- [ ] Manual: 50–80 MB upload responds within network time + ≤2 s overhead; report output matches a known-good baseline.
