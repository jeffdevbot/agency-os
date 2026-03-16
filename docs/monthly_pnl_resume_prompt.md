Continue the Monthly P&L debugging work in `agency-os`.

Read first:

1. `docs/monthly_pnl_handoff.md`
2. `docs/monthly_pnl_implementation_plan.md`
3. `PROJECT_STATUS.md`
4. `AGENTS.md`

Current reality:

1. Monthly P&L foundation, import pipeline, report service, and frontend route are built.
2. Live testing is still broken.
3. The key real file is:
   - `/Users/jeff/Downloads/2025DecMonthlyUnifiedTransaction.csv`
4. Manual December 2025 numbers are in the handoff doc and should be the reconciliation target.

Most recent live symptoms:

1. `POST /admin/pnl/profiles/c8e854cf-b989-4e3f-8cf4-58a43507c67a/transaction-upload` returns `500`
2. stale `Jan 2026` data is still visible from the earlier bad import
3. after refresh the UI showed `Failed to list P&L profiles`

Important context:

1. `165ad01` fixed ledger pagination.
2. `b5b5d1f` switched month assignment to `date/time` first and added reimport supersede logic.
3. `f4acff1` added a compatibility fallback for environments that still have the old SHA unique index.
4. The stale January month should disappear only after a successful replacement import supersedes the bad old import.

Your task:

1. Get up to speed fast from the handoff doc.
2. Diagnose the live `500` on transaction upload using the real failure path, not guesses.
3. Verify whether the latest backend deploy is live.
4. Inspect live import/import-month state for profile `c8e854cf-b989-4e3f-8cf4-58a43507c67a`.
5. Fix the upload failure.
6. Ensure the successful replacement import deactivates the stale January month slice.
7. Then reconcile the rendered December 2025 P&L against the manual spreadsheet and fix remaining mapping/model differences.

Guidelines:

1. Prioritize correctness over speed.
2. Do not overbuild new features.
3. Keep changes focused on Monthly P&L.
4. Use the real transaction file behavior and live SQL state as the source of truth.
5. Add/update tests for any code you change.

Expected deliverable for this session:

1. successful live re-import of the December 2025 file
2. no stale January carryover from the old bad import
3. December report materially closer to the manual spreadsheet
4. concise summary of:
   - root cause
   - code changes
   - migrations if any
   - residual mismatches still to reconcile
