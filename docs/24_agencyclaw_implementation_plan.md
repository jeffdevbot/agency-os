# AgencyClaw Implementation Plan (Chunked)

## 1. Purpose
This document is the execution blueprint for AgencyClaw implementation.
It is separate from `docs/23_agencyclaw_prd.md`:
- PRD = product decisions and behavior.
- Implementation plan = execution order, prompts, and acceptance gates.

## 2. Working Rules
- Work one chunk at a time.
- No scope expansion inside a chunk.
- Every chunk ships with tests.
- Every mutation path must preserve idempotency, confirmation, and audit requirements from PRD v1.9.
- Unimplemented skills remain disabled in `skill_catalog`.

## 3. Definition Of Done (Per Chunk)
- Behavior implemented end-to-end for chunk scope.
- Permission checks and policy gates enforced.
- Idempotency and concurrency requirements handled where applicable.
- Tests added for happy path and key failure/ambiguity paths.
- `skill_catalog` row updated to `implemented_in_code=true` and enabled only when ready.
- Tracker updated (`docs/25_agencyclaw_execution_tracker.md`).

## 4. Chunk Roadmap
1. C1: Weekly task read path (`clickup_task_list_weekly`)
2. C2: Task create flow (`clickup_task_create`) with thin-task clarification
3. C3: Confirmation protocol + Slack dedupe hardening
4. C4: Concurrency guard + ClickUp reliability/idempotency
5. C5: Team identity sync + reconciliation (`needs_review` decisions)
6. C6: ClickUp space sync/classification + brand mapping controls
7. C7: Standalone `meeting_parser` + debrief review path hardening
8. C8: `client_context_builder` + token budget enforcement + metadata

## 5. Chunk Details
## C1: Weekly Task Read Path
- Scope:
  - Slack query: "what's being worked on this week for client X"
  - Resolve client/brand.
  - Read ClickUp tasks with pagination and Slack-friendly formatting.
  - Cap response at 200 tasks with truncation notice.
- Acceptance:
  - Handles ambiguous client/brand with clarification.
  - Handles missing ClickUp mapping fail-closed.
  - Returns useful "no tasks" response.
- Skill target:
  - `clickup_task_list_weekly`

## C2: Task Create Flow
- Scope:
  - `clickup_task_create` to brand backlog default destination.
  - Thin-task clarification workflow.
  - "Create anyway as draft" workflow.
  - Return ClickUp URL after success.
- Acceptance:
  - Confirmation required in channel contexts.
  - Missing mapping fails closed with actionable message.
  - Task URL is always returned on success.

## C3: Confirmation + Dedupe
- Scope:
  - Ephemeral Block Kit self-confirmation.
  - 10-minute expiry handling.
  - `slack_event_receipts` idempotent handling for interactions.
- Acceptance:
  - Duplicate interaction deliveries are no-ops.
  - Expired confirms do not mutate state.

## C4: Concurrency + Reliability
- Scope:
  - Advisory lock pattern for mutation skills.
  - ClickUp retry/backoff for transient failures.
  - ClickUp create idempotency key and orphan handling.
- Acceptance:
  - Concurrent writes to same entity do not race.
  - ClickUp 429/timeout behavior is deterministic and user-visible.

## C5: Team Identity Sync
- Scope:
  - Sync Slack users + ClickUp users (read-only source ingestion).
  - Deterministic matching to `profiles`.
  - `needs_review` decision in Slack for ambiguous mappings.
- Acceptance:
  - Auto-match, new-profile, and needs-review outcomes all supported.
  - Admin decision path is audited and idempotent.

## C6: ClickUp Space Sync + Classification
- Scope:
  - Ingest spaces and maintain classification:
    `brand_scoped`, `shared_service`, `unknown`.
  - Admin classification and brand map/unmap via chat skills.
- Acceptance:
  - Brand routing uses only `brand_scoped` by default.
  - `unknown` spaces block routing until classified.

## C7: Meeting Parser Hardening
- Scope:
  - Implement and test standalone `meeting_parser`.
  - Integrate with debrief ingest/review path.
- Acceptance:
  - Parser is testable independently from ClickUp send.
  - Quality and ambiguity handling are explicit.

## C8: Client Context Builder
- Scope:
  - Build 4,000-token context pack with deterministic truncation.
  - Emit metadata (`included_sources`, `omitted_sources`, token estimate, freshness).
- Acceptance:
  - Deterministic output for same inputs.
  - Budget guardrails enforced and tested.

## 6. Prompt Template (For Coding Agent)
```text
Implement Chunk <ID> in repo `agency-os`.

Rules:
- Work only within this chunk scope.
- Use PRD `docs/23_agencyclaw_prd.md` (v1.9) as source of truth.
- No extra features.
- Add/update tests.
- Keep migration changes separate unless this chunk requires schema.

Deliverables:
1) Files changed + rationale
2) Tests added/updated
3) Commands run and outcomes
4) Risks/TODOs
```

