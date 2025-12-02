# ⚠️ Composer Deprecation Plan — ACTIVE DECOMMISSION

**Status:** Composer is frozen. Scribe (Stages A/B/C) is live and replacing it.

**Purpose:** Retire Composer after Scribe is stable without breaking shared infra or confusing users.

---

## 1) Inventory & Ownership
- Identify all Composer assets: frontend routes/components, backend handlers/jobs, Supabase tables/functions, shared libs (e.g., auth hooks, callLLM wrappers).
- Confirm current usage: grep for Composer imports in Scribe/backends; check production traffic/links to Composer routes; verify no shared queues/tasks rely on Composer code.
- Assign an owner for deprecation and a reviewer for shared schema/RLS changes.

## 2) Freeze Surface (No New Use)
- Hide/feature-flag Composer UI in prod (remove nav links/deep links).
- Mark Composer packages/modules as deprecated in READMEs to deter new dependencies.
- If any Composer endpoints remain exposed, add a banner/notice “Deprecated: use Scribe.”

## 3) Data & Schema Plan
- List Composer-specific tables/schemas (distinct from Scribe). For each: keep, archive, or drop.
- If retention is needed, export to cold storage; otherwise plan drops with a rollback point.
- Ensure RLS doesn’t leak or break when parent tables are removed; adjust cascades carefully.

## 4) Code & Infra Teardown (Phased)
- Phase 1: Delete unused Composer frontend routes/components and dead backend handlers; keep shared utilities untouched.
- Phase 2: Remove Composer-specific jobs/queues; ensure no cron/task references remain.
- Phase 3: Drop Composer tables/functions/views (post-retention/export), update migrations/seeds.
- Phase 4: Remove any Composer-specific env vars/config and CI steps.

## 5) Verification & Rollback
- After each phase, run CI/tests; check app boot/logs for missing imports/envs.
- Monitor errors/alerts post-deployment; keep backups/exports for schema drops.
- Rollback strategy: re-enable feature flag or revert commit; restore DB from backup if needed.

## 6) Comms & Timeline
- Announce deprecation internally (what replaces it, when code/schema go away).
- Target: start teardown after Scribe Stage C ships; schedule schema drops with DBAs/ops.
