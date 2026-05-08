# MercatoPath Coding Agent Onboarding Kit

**Status:** Draft companion to `docs/mercatopath/mercatopath_brief.md`  
**Purpose:** Give a fresh AI coding agent enough context to scaffold MercatoPath correctly before building product features.

---

## 1. Read this first

MercatoPath is a new public SaaS, not a refactor of agency-os. agency-os validated the product thesis, but MercatoPath should be built greenfield with stricter architecture, tenancy, security, sync durability, and AI-coding guardrails.

Before coding, read:

1. `docs/mercatopath/mercatopath_brief.md`
2. This onboarding kit
3. Any Claude Design / UI brief artifacts provided by Jeff
4. Relevant agency-os reference files only after the new repo boundaries are clear

Do not start by copying agency-os files into the new repo. Use agency-os as reference for proven workflows and edge cases, not as source code to port wholesale.

---

## 2. Product architecture summary

MercatoPath absorbs the durable core of agency-os:

- Amazon ingestion: SP-API, Ads API, Finances API, FBA reports, returns reports
- Encrypted token storage and OAuth
- Multi-tenant warehouse for business, ads, search terms, returns, inventory, and financial events
- Durable sync queue and coverage ledger
- WBR snapshots, scoring, and email drafts
- Monthly P&L, initially with CSV fallback and later Finances API
- MCP server generalized for multi-tenant SaaS
- Reauth, long-term-storage-fee, anomaly, and readiness alerts

agency-os remains, if needed, as an Ecomlabs-private extension layer for ClickUp, internal team/hour/VA tooling, Slack drafts, and other non-SaaS workflows.

---

## 3. Day-0 repo skeleton

Use a monorepo with concrete stub files from day 0:

```text
mercatopath/
  apps/
    web/                 # Next.js
    api/                 # FastAPI
    worker/              # background workers: sync, alerts, notifications
    mcp/                 # TypeScript MCP server
  packages/
    shared/              # generated types, shared TS/Python contracts if practical
    db/                  # migrations, schema generation, DB helpers
  AGENTS.md
  DEPRECATED.md
  Dockerfile.api
  Dockerfile.worker
  Dockerfile.mcp
  docker-compose.yml     # local dev: postgres + API + worker + web
  render.yaml
  Makefile               # make verify, make migrate, make worker
  docs/
    current/
      architecture-overview.md
      glossary.md
    adr/
    archive/
    domains/             # one README per domain
  .claude/
    commands/
      add-fact-table.md
      add-mcp-tool.md
      add-sync-source.md
    code-review-checklist.md
    architecture-overview.md
    glossary.md
  supabase/
    migrations/
    seed/
  scripts/
  fixtures/
```

Default stack:

- Supabase Postgres/Auth/RLS
- Next.js for web
- Python/FastAPI for API
- Python workers for Amazon sync
- TypeScript for MCP server unless the implementation strongly argues otherwise
- Render for web/API/workers in v1

Supabase + Render is acceptable for v1. The critical requirement is that long-running work runs in background workers, not request handlers.

---

## 4. First coding session objective

The first coding session should scaffold the repo and guardrails. It should not attempt to build all product features.

Definition of done for the first session:

- Repo structure exists.
- `AGENTS.md` exists and is prescriptive.
- `docs/current/`, `docs/adr/`, `docs/archive/`, and `DEPRECATED.md` exist.
- Initial ADRs exist.
- Domain module template exists.
- MCP tool template exists.
- Sync job / fact table template exists.
- `make verify` or `just verify` exists.
- CI or local scripts include lint/type/test placeholders and file-size warnings.
- Initial Supabase migration creates core tenancy + durable sync queue tables.
- Worker can claim and complete a fake sync job.
- Web shell can show organization/workspace setup placeholder and sync status placeholder.
- `.claude/glossary.md`, `docs/current/glossary.md`, and `AGENTS.md` contain concrete definitions and coding rules.
- `docker-compose.yml` starts enough local infrastructure for an AI agent to reproduce queue tests.

Do not build full Amazon OAuth until the scaffold and durable queue pattern are in place.

---

## 5. First ADRs to create

Create these before feature work:

- `docs/adr/0001-tenant-model.md`
- `docs/adr/0002-durable-sync-queue.md`
- `docs/adr/0003-amazon-connection-model.md`
- `docs/adr/0004-mcp-context-delivery.md`
- `docs/adr/0005-data-kiosk-first-business-facts.md`
- `docs/adr/0006-ai-maintainability-guardrails.md`

ADR shape:

```md
# 0000 — Decision Title

## Status
Proposed | Accepted | Superseded

## Context
What problem forced the decision?

## Decision
What are we doing?

## Alternatives Considered
What else did we consider?

## Consequences
What tradeoffs follow from this?
```

No `*_plan.md` should survive after a feature merges. Convert durable decisions into ADRs and move stale planning docs into `docs/archive/`.

---

## 6. Glossary definitions to pin down

Create `docs/current/glossary.md` and `.claude/glossary.md` with schema-level definitions. These terms must not be left for each agent to reinterpret:

- **Organization:** one customer account / billing / security container. One row in `organizations`. Owns members and workspaces.
- **User:** one human identity, mapped indirectly from Supabase `auth.users`. Application code should reference `users.id`, not `auth.users.id` directly, so auth provider details stay portable.
- **Organization member:** one user's role inside an organization. One row in `org_members`.
- **Workspace:** one Amazon business, client, or account cluster. One row in `workspaces`. Belongs to one organization. Workspace IDs in URLs should use stable slugs such as `acme-co`; database primary keys can still be UUIDs.
- **Workspace member:** one user's permission inside a workspace. One row in `workspace_members`.
- **Connection:** one authorized credential set, such as Seller Central/SP-API or Amazon Ads. One row in `connections`. A workspace can have multiple connections; a connection may be associated with multiple workspaces only if the product explicitly supports shared credentials.
- **Marketplace:** one Amazon marketplace such as US, CA, UK, DE. Store Amazon marketplace IDs, country codes, currency, and region explicitly.
- **Sync job:** one row in `sync_jobs`; an enqueued unit of work with an idempotency key and retry/lease metadata.
- **Coverage:** one row or rollup in `sync_coverage`; product truth for whether a dataset/date window is ready, partial, stale, or errored.
- **Fact:** one row in a canonical `fct_*` table. A fact is owned by exactly one `(workspace, source, marketplace, dataset, grain, date window, transform_version)` tuple.
- **Dataset:** a logical product dataset such as `business_by_asin`, `ads_campaign_daily`, `ads_search_terms`, `inventory_health`, `returns`, or `financial_events`.
- **Source:** the upstream family that produced data, such as `spapi_reports`, `data_kiosk`, `amazon_ads`, `finances_api`, or `manual_csv`.
- **Fast lane:** highest-priority initial sync jobs for recent high-utility data, usually last 30 days.
- **Deep backfill:** lower-priority historical jobs that continue after the workspace becomes usable.

---

## 7. Initial schema migration requirements

Create a real first migration, e.g. `supabase/migrations/0001_init.sql` or timestamped equivalent. This will become the most-copied pattern in the repo, so make it clean.

Minimum tables:

- `users`
- `organizations`
- `org_members`
- `workspaces`
- `workspace_members`
- `marketplaces`
- `connections`
- `workspace_connections`
- `sync_jobs`
- `sync_coverage`
- `sync_events` or `outbox_events`

Schema rules:

- Use snake_case in database columns.
- Use `created_at`, `updated_at`, and `*_at` for timestamps.
- Use `*_date` only for true date-only values.
- Store encrypted token material in clearly named encrypted columns, not plaintext.
- Add the first RLS policies in the initial migration so future agents copy the correct indirection pattern.
- Application tables should indirect from `auth.users` through the app-level `users` table.
- Add uniqueness constraints for job idempotency and membership uniqueness.

Do not defer RLS to "later." The first migration should show the intended security model even if only a small subset of policies exists.

---

## 8. Domain module contract

Every backend domain should use the same shape:

```text
apps/api/app/services/<domain>/
  repository.py    # DB access only, no business logic
  service.py       # business logic; orchestrates repositories + external clients
  schema.py        # Pydantic models for I/O
  mcp_tools.py     # MCP tool surface for this domain, if any
  tests/
    test_service.py
    test_repository.py
```

Rules:

- Routers import from `service.py`, not `repository.py`.
- MCP tools import from `service.py`, not `repository.py`.
- Repositories own DB access.
- External API clients do not write facts directly.
- Transform modules convert raw source payloads to canonical fact rows.
- Store/repository modules write facts idempotently.

Add lint or CI checks for import boundaries as early as practical.

---

## 9. Durable sync architecture

Hard rule:

> Anything that takes longer than about five seconds runs in a worker. HTTP routes only validate, discover, enqueue, and return.

Day-1 tables:

- `sync_jobs`
- `sync_coverage`
- `sync_events` or equivalent event/outbox table

`sync_jobs` is execution state. `sync_coverage` is product truth for UI and MCP freshness.

Worker claim pattern:

- Use direct Postgres connection from workers, or a Supabase RPC/Postgres function.
- Use one atomic statement/function with `FOR UPDATE SKIP LOCKED`.
- Do not claim jobs with separate Supabase REST `select` then `update` calls.
- Claim transaction should be short: claim row, set lease, commit.
- Call Amazon after the claim transaction commits.

Minimum job fields:

- `id`
- `workspace_id`
- `source`
- `marketplace_id`
- `dataset`
- `report_type`
- `grain`
- `date_from`
- `date_to`
- `priority`
- `idempotency_key`
- `status`
- `attempts`
- `next_attempt_at`
- `claimed_at`
- `lease_expires_at`
- `heartbeat_at`
- `worker_id`
- `last_error`
- `created_at`
- `updated_at`

Minimum coverage fields:

- `workspace_id`
- `source`
- `marketplace_id`
- `dataset`
- `grain`
- `date_from`
- `date_to`
- `status`
- `row_count`
- `last_successful_job_id`
- `last_verified_at`
- `fresh_through_date`
- `error_code`
- `error_message`

Readiness states:

- `empty`
- `queued`
- `syncing`
- `ready_recent`
- `ready_full`
- `partial_error`
- `stale`
- `reauth_required`

Stale-claim reaper is mandatory. Expired leases must return to queued or failed according to retry policy.

Create an actual worker template in `apps/worker/template_job_handler.py` with this shape:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from psycopg import AsyncConnection


@dataclass(frozen=True)
class Job:
    id: str
    workspace_id: str
    dataset: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class JobResult:
    status: str
    row_count: int = 0
    error_code: str | None = None
    error_message: str | None = None


async def claim_one_job(db: AsyncConnection, worker_id: str) -> Job | None:
    async with db.transaction():
        row = await db.execute(
            """
            update sync_jobs
            set status = 'running',
                worker_id = %(worker_id)s,
                claimed_at = now(),
                lease_expires_at = now() + interval '10 minutes',
                attempts = attempts + 1,
                updated_at = now()
            where id = (
                select id
                from sync_jobs
                where status = 'queued'
                  and next_attempt_at <= now()
                order by priority desc, created_at asc
                for update skip locked
                limit 1
            )
            returning id, workspace_id, dataset, payload
            """,
            {"worker_id": worker_id},
        )
        record = await row.fetchone()
    return Job(**record) if record else None


async def run_job(db: AsyncConnection, job: Job) -> JobResult:
    raise NotImplementedError


async def finalize_job(db: AsyncConnection, job: Job, result: JobResult) -> None:
    raise NotImplementedError


async def reap_stale_claims(db: AsyncConnection) -> int:
    raise NotImplementedError
```

Future sync domains should copy this claim/finalize shape instead of inventing new worker loops.

---

## 10. Supabase implementation notes

Supabase supports the required queue pattern.

Preferred worker DB access:

- Use the Supabase direct Postgres connection string from a persistent worker with `psycopg`, `asyncpg`, or SQLAlchemy.
- If IPv6 is a problem in the host environment, use Supavisor session mode or Supabase's IPv4 add-on.

Alternative:

- Put the job claim in a Postgres function and call it through Supabase `.rpc()`.

Avoid:

- Multi-call REST claiming.
- Holding row locks while calling Amazon.
- Depending on request handlers for backfills.

---

## 11. MCP bootstrap decisions

The brief says "TypeScript MCP server"; the first implementation pass must pin down the missing details in an ADR.

Default assumptions to start from:

- Library: `@modelcontextprotocol/sdk`.
- Server location: `apps/mcp`.
- Auth: bearer token tied to an organization/workspace membership for v1, with a path to OAuth later if MCP client support improves.
- Installation: customer copies an MCP server URL/config from the MercatoPath MCP setup screen.
- Context delivery: server instructions + `get_mcp_capabilities` bootstrap tool + workflow guide resources/tools.
- Standard tool output shape:

```ts
type McpToolResult<T> = {
  data: T;
  freshness: {
    status: "ready_recent" | "ready_full" | "partial_error" | "stale" | "reauth_required";
    freshThroughDate?: string;
    coverageWarnings: string[];
  };
  caveats: string[];
  nextToolHints: string[];
  meta: {
    workspaceId: string;
    datasetVersions: Record<string, string>;
  };
};
```

Initial MCP v0 tools:

- `get_sync_freshness_status`
- `query_business_facts`

Do not build a large MCP surface before tenancy, freshness, and tool output shape are proven.

---

## 12. First-domain build order

Use sprints with acceptance criteria, not broad phases.

### Sprint 0 — scaffold, schema, auth shell

Acceptance criteria:

- Repo skeleton exists.
- Local dev starts.
- Initial schema migration exists.
- Supabase auth shell exists.
- Organization/workspace tables and basic RLS pattern exist.
- `make verify` runs.

### Sprint 1 — durable queue and first fake job

Acceptance criteria:

- `sync_jobs` and `sync_coverage` exist.
- Worker claims one fake job atomically.
- Worker finalizes success/failure.
- Stale-claim reaper exists.
- Tests prove two workers do not claim the same job.

### Sprint 2 — first real sync source

Scope: Sales & Traffic, one region/marketplace, fast-lane only.

Acceptance criteria:

- SP-API connection placeholder or real SP-API OAuth exists.
- Sales & Traffic/Data Kiosk job can be enqueued.
- Worker writes canonical business facts and coverage.
- Sync status UI reads coverage.

### Sprint 3 — Ads source and rate limiter

Acceptance criteria:

- Amazon Ads connection flow or placeholder exists.
- Ads fast-lane campaign jobs enqueue and run.
- Per-source rate limiter exists.
- Coverage distinguishes Seller Central vs Ads readiness.

### Sprint 4 — MCP v0

Acceptance criteria:

- MCP server boots.
- Bearer-token auth works.
- `get_sync_freshness_status` works.
- `query_business_facts` works.
- Tool output includes freshness, caveats, and next-tool hints.

---

## 13. Naming and style conventions

Decide once, document in `docs/current/architecture-overview.md` and `AGENTS.md`, and enforce with lint where possible.

Defaults:

- Database: snake_case.
- Python: snake_case.
- TypeScript variables/functions: camelCase.
- TypeScript types/components: PascalCase.
- Convert between DB/Python/TS via codegen or explicit mappers.
- Timestamps: `created_at`, `updated_at`, `*_at`.
- Dates: `*_date` only for date-only fields.
- IDs: choose UUIDv7 if available in the chosen stack; otherwise UUID with clear generated defaults. Do not mix UUIDs and BigInt sequences casually.
- URL identifiers: stable slugs for user-facing organization/workspace paths.
- Error response shape:

  ```json
  {
    "error": {
      "code": "sync_job_not_found",
      "message": "Sync job not found",
      "details": {}
    }
  }
  ```

- Logging: structured JSON to stdout, captured by Render.

---

## 14. Public-app review prep packet

Phase 0 cannot submit Amazon public-app review until these exist:

- Privacy policy.
- Security questionnaire answers.
- OAuth app display name.
- Logo assets in required sizes.
- App description copy.
- Support contact and SLA statement.
- Data flow diagram.
- Data retention/deletion policy.
- Explanation of encrypted token storage.
- Explanation of least-privilege roles and why each Amazon role is needed.

Treat this as a parallel workstream, not something to discover after the product skeleton is built.

---

## 15. Local development contract

AI coding agents need one-command local reproducibility.

Day-0 local dev should include:

- `docker-compose.yml` for Postgres, API, worker, and web where practical.
- Seed script creating one organization, one workspace, one fake connection, and fake `sync_jobs` / `sync_coverage` rows in every readiness state.
- Fake Amazon mock server or VCR-style cassettes so tests can run without hitting Amazon.
- `apps/api/README.md`, `apps/worker/README.md`, `apps/mcp/README.md`, and `apps/web/README.md` with pasteable commands.
- `make verify` for the whole repo.
- `make worker` to run the worker locally.
- `make seed` to reset the dev state.

---

## 16. Golden fixtures to extract from agency-os

Create sanitized fixtures early:

- Real SP-API Sales & Traffic / Data Kiosk sample.
- Real Amazon Ads campaign report sample.
- Real Amazon Ads search-term report sample.
- Real Finances API transaction sample.
- Real FBA inventory/planning report sample.
- Real returns report sample.
- Failure case: rate limit.
- Failure case: auth expired / reauth required.
- Failure case: report timeout / pending too long.

These fixtures let future AI sessions write tests without re-deriving Amazon response shapes from scratch.

---

## 17. AGENTS.md v0 content

Draft `AGENTS.md` during scaffold. It should include:

- Read `docs/current/architecture-overview.md`, `docs/current/glossary.md`, and relevant ADRs before editing.
- Identify the domain before changing code.
- Use domain templates.
- Routers and MCP tools call services, not repositories.
- Do not add long-running work to request handlers.
- Add or update tests/fixtures with code changes.
- Do not edit deprecated paths without asking.
- Do not extend files over 600 lines without calling it out.
- If architecture changes, add/update an ADR.
- Run `make verify` before final response.

---

## 18. Anti-roadmap: not v1

Do not build or scaffold these unless Jeff explicitly changes the plan:

- White-label / custom branding.
- Slack integration.
- Billing dashboard beyond Stripe Hosted Pages / customer portal.
- Advanced charts or BI dashboards.
- AMC integration.
- Mobile app.
- Self-serve admin tooling beyond reauth, connection repair, team access, and billing basics.
- Email templating UI.
- Automated SOP execution or actions on Amazon.
- Multi-region writes / replication.
- Vendor Central / 1P support.
- Enterprise SSO.
- Custom per-customer data warehouse exports.

This list exists because AI agents tend to helpfully expand scope.

---

## 19. Testing contract

Every new feature needs tests at the right seam:

- Transform logic: unit tests with sanitized fixtures.
- Repository logic: integration tests against a test database.
- Worker logic: integration test that enqueues, claims, runs, and updates coverage.
- API route: integration test for auth/input/error shape.
- MCP tool: integration test for tool response shape, freshness warnings, and tenant scoping.

Golden fixtures should exist for:

- Data Kiosk JSONL
- Reports API Sales & Traffic
- Ads campaign reports
- Ads search-term reports
- Finances transactions
- FBA inventory / planning reports
- Returns reports
- Fee reports

---

## 20. AI coding rules

When in doubt:

- If something might be deprecated, ask before extending it.
- If ownership is unclear, propose a split instead of adding to a large file.
- If there are multiple patterns, copy the most recent equivalent pattern unless an ADR says otherwise.
- If a behavior changes architecture, schema, public API, MCP tool output, or sync semantics, update an ADR or domain README.
- If a change cannot be tested cleanly, improve the seam instead of merging untested glue.

File-size guidance:

- Prefer files under ~300 lines.
- Treat 400+ lines as a review smell.
- Warn at 600+ lines in CI.
- Treat 700+ lines as a refactor ticket unless generated/declarative/test fixture.

---

## 21. Suggested first AI prompt

Use this when starting the first MercatoPath coding session:

> We are building MercatoPath, a greenfield SaaS based on `docs/mercatopath/mercatopath_brief.md` and `docs/mercatopath/coding_agent_onboarding.md`. Do not copy agency-os wholesale. First scaffold the repo guardrails and durable sync foundation: monorepo structure under `apps/` and `packages/`, `AGENTS.md`, `DEPRECATED.md`, `docs/current`, `docs/adr`, `docs/domains`, `.claude`, initial ADRs, domain templates, MCP/fact-table templates, `make verify`, local dev compose/seed, initial Supabase migrations for tenancy + `sync_jobs` + `sync_coverage`, and a worker that can claim/complete a fake job using atomic Postgres locking or RPC. Keep HTTP routes fast; no long-running work in request handlers. Add tests for the queue claim path and coverage update path. Stop before building real Amazon OAuth unless the scaffold is complete.

---

## 22. Initial product surfaces after scaffold

After the scaffold is in place, build the first UI slice:

1. Sign up / login shell
2. Organization setup
3. First workspace setup
4. Team invite placeholder
5. Connect Seller Central placeholder
6. Connect Amazon Ads placeholder
7. Account/profile mapping placeholder
8. Sync status screen reading `sync_coverage`
9. MCP setup placeholder

The first UI should prove the onboarding shape and readiness model before deep feature work begins.
