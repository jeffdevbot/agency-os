# Scribe Testing Plan (by Slice)

## Slice 1 — Project Shell & RLS
- Auth/RLS: user A cannot see/update user B’s projects; unauthorized returns 401.
- CRUD: create/list/detail/update name/category/status; archive/restore flows.
- Status transitions: valid (draft → topics_generated → copy_generated → approved), invalid returns 409.
- Archived guard: writes to archived return 403; reads still allowed.
- Pagination/sort defaults honored on list.

## Slice 2 — Product Data (Stage A)
- Limits: 50 SKUs cap; 10 keywords/SKU; validation errors when exceeded.
- Apply-to-all propagates correctly; does not overwrite overrides unless flagged.
- Stage A approval blocks when required data missing; passes when present.
- RLS: SKUs/keywords/questions/attrs not visible or writable across users.

## Slice 3 — Topics Generation (Stage B)
- Preconditions: generate-topics rejects unless Stage A approved.
- Job lifecycle: queued → running → succeeded/failed; topics persisted on success.
- Topics CRUD: edit/reorder, per-SKU/shared; approve topics sets status to topics_generated.
- Optimistic locking: concurrent edit/regenerate conflict returns 409.

## Slice 4 — Copy Generation (Stage C)
- Preconditions: generate-copy rejects unless topics approved.
- Job lifecycle: copy job writes generated_content; regeneration bumps version.
- Limits enforced: 5 bullets, title/backend lengths/bytes; validation errors on overflow.
- Approve copy transitions status; conflicts handled (409 on stale updates).

## Slice 5 — Export & Polish
- CSV export: headers + rows correct; includes all SKUs; works for archived (read-only).
- Pagination/sorting defaults still honored on list endpoints post-export wiring.

## Cross-Cutting
- Error envelope shape (`{ error: { code, message } }`) consistent across endpoints.
- Archived projects: write attempts on any child routes return 403; reads allowed.
- RLS smoke: multi-user isolation across all tables.
