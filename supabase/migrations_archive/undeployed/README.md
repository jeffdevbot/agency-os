Archived migrations in this directory are intentionally excluded from the active
`supabase/migrations/` rollout path.

Use this for migrations that exist in the repo history but are not part of the
canonical live migration ledger for the current production database.

If one of these changes is needed later, create a new migration in
`supabase/migrations/` with a fresh timestamp instead of restoring the archived
file in place.
