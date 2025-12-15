# Product Requirement Document: Shared ClickUp Service

**Version:** 1.0  
**Last Updated:** 2025-12-15  
**Status:** Ready for Engineering  
**Owner:** Agency OS

**Purpose:** Provide a single, consistent integration layer for the ClickUp API across Agency OS tools.

**Primary Consumers (current):**
- **Command Center** (`docs/07_command_center_prd.md`) — sync Spaces/Users for mapping; optionally resolve lists.
- **Debrief** (`docs/debrief_prd.md`) — create/update ClickUp tasks for approved meeting action items.
- **worker-sync** (future) — scheduled sync jobs (spaces/users/list metadata, templates, etc.).

---

## 1. Executive Summary

Agency OS needs ClickUp for:
- mapping **brands → where tasks get created**
- mapping **team members → who tasks get assigned to**
- creating tasks reliably with retries, rate limiting, and consistent error handling

The ClickUp Service is a shared internal module that:
- centralizes authentication, rate limiting, retries, and common ClickUp calls
- provides a stable API for tools (Command Center, Debrief) to call ClickUp without duplicating integration code

---

## 2. Fit With Command Center + Debrief

### 2.1 Source-of-Truth Fields (from other PRDs)

From `docs/07_command_center_prd.md`:
- `public.brands.clickup_space_id` — where the brand’s work should be created (routing target).
- `public.profiles.clickup_user_id` — who can be assigned in ClickUp.
- `public.client_assignments` + `public.agency_roles` — role-based routing for Debrief.

From `docs/debrief_prd.md`:
- Debrief creates ClickUp tasks after review, using:
  - brand routing (`brands.clickup_space_id`)
  - assignee routing (`profiles.clickup_user_id`)

### 2.2 Important ClickUp API Reality: Tasks are Created in Lists (not Spaces)

ClickUp’s API creates tasks via `POST /list/{list_id}/task`.

Because we currently store **space IDs** on brands (not list IDs), the ClickUp Service must support one of:
1) **Resolve a default list** inside a space (recommended for MVP)
2) Store `brands.clickup_list_id` (recommended future improvement)

This PRD standardizes (1) for MVP while leaving room for (2).

---

## 3. Architecture

### 3.1 Implementation Pattern (MVP): Shared Python Module

Implement as a shared module (importable by `backend-core` and `worker-sync`) so we avoid standing up a separate microservice.

Suggested layout:

```
lib/clickup/
  ├── __init__.py
  ├── service.py          # ClickUpService
  ├── types.py            # dataclasses
  ├── rate_limiter.py     # token bucket limiter
  ├── cache.py            # optional TTL cache
  └── exceptions.py       # typed exceptions
```

**Note:** Frontend code never calls ClickUp directly. All ClickUp interactions happen via backend APIs (FastAPI routes / workers).

### 3.2 Evolution Path (Optional): HTTP Microservice

If we need shared global rate-limiting state across many processes/services, we can move the service to its own FastAPI app and add Redis-backed rate limiting.

---

## 4. Service API Contract

### 4.1 Constructor + Configuration

```python
class ClickUpService:
    def __init__(
        self,
        api_token: str,
        team_id: str,
        rate_limit_per_minute: int = 100,
        enable_cache: bool = True,
        default_list_name: str | None = "Inbox",
        default_list_id: str | None = None,
    ): ...
```

Config sources:
- `CLICKUP_API_TOKEN` (required)
- `CLICKUP_TEAM_ID` (required)
- `CLICKUP_RATE_LIMIT_PER_MINUTE` (optional; default 100)
- `CLICKUP_ENABLE_CACHE` (optional; default true)
- `CLICKUP_DEFAULT_LIST_NAME` (optional; default `"Inbox"`)
- `CLICKUP_DEFAULT_LIST_ID` (optional; if set, overrides name-based resolution)

### 4.2 Read APIs (Command Center)

```python
async def get_spaces(self) -> list[ClickUpSpace]:
    """GET /team/{team_id}/space"""

async def get_team_members(self) -> list[ClickUpUser]:
    """GET /team/{team_id}/member"""

async def get_space_lists(self, space_id: str) -> list[ClickUpList]:
    """GET /space/{space_id}/list"""
```

### 4.3 Write APIs (Debrief)

```python
async def create_task_in_list(
    self,
    list_id: str,
    name: str,
    description_md: str | None = None,
    assignee_ids: list[str] | None = None,
    tags: list[str] | None = None,
    priority: int | None = None,
    due_date_ms: int | None = None,
    custom_fields: list[dict] | None = None,
) -> ClickUpTask:
    """POST /list/{list_id}/task"""

async def create_task_in_space(
    self,
    space_id: str,
    name: str,
    description_md: str | None = None,
    assignee_ids: list[str] | None = None,
    tags: list[str] | None = None,
    priority: int | None = None,
    due_date_ms: int | None = None,
    custom_fields: list[dict] | None = None,
    override_list_id: str | None = None,
) -> ClickUpTask:
    """
    Convenience wrapper for Debrief.
    Resolves a default list_id in the given space (cached), then calls create_task_in_list().
    """

async def update_task(self, task_id: str, updates: dict) -> ClickUpTask:
    """PUT /task/{task_id}"""

async def get_task(self, task_id: str) -> ClickUpTask:
    """GET /task/{task_id} (useful for debugging and future tools)"""
```

### 4.4 Default List Resolution (Key Behavior)

`create_task_in_space()` must resolve a list as follows:
1. If `override_list_id` is provided, use it.
2. Else if `CLICKUP_DEFAULT_LIST_ID` is set, use it.
3. Else fetch lists in the space and select:
   - first list whose name matches `CLICKUP_DEFAULT_LIST_NAME` (case-insensitive), else
   - first available list returned by ClickUp.
4. Cache `space_id -> resolved_list_id` for 1 hour (or until process restart).

If no lists exist, raise `ClickUpConfigurationError` with a human-readable message.

---

## 5. Rate Limiting, Retries, and Error Handling

### 5.1 Rate Limiting

ClickUp limits are per workspace (commonly 100 requests/min).

MVP uses an in-process async token bucket limiter:
- safe and simple for current scale
- not globally coordinated across multiple processes/services

If we see frequent 429s across services, we migrate to:
- centralized limiter (Redis), or
- route all ClickUp calls through a single service (Option B).

### 5.2 Retries

Retry transient failures:
- 429 (rate limit)
- 5xx
- timeouts

No retry on:
- 400/422 validation errors
- 401 auth errors
- 404 not found

Use exponential backoff with jitter (e.g., 1s/2s/4s + random 0–250ms).

### 5.3 Exceptions

Provide typed exceptions:
- `ClickUpAuthError`
- `ClickUpNotFoundError`
- `ClickUpValidationError`
- `ClickUpRateLimitError`
- `ClickUpAPIError` (fallback)
- `ClickUpConfigurationError` (space has no list; missing config; etc.)

---

## 6. Caching Strategy (MVP)

Cache is optional but recommended for:
- `get_spaces()` (TTL 1 hour)
- `get_team_members()` (TTL 1 hour)
- `get_space_lists(space_id)` (TTL 1 hour)
- `resolve_default_list_id(space_id)` (TTL 1 hour)

Cache scope: in-process only (simple TTL dict).

**Do not** cache write operations (`create_task*`, `update_task`).

---

## 7. Usage Examples

### 7.1 Command Center: Sync Spaces + Users

Command Center uses the service to populate dropdowns for:
- mapping `brands.clickup_space_id`
- mapping `profiles.clickup_user_id`

```python
clickup = ClickUpService(
    api_token=os.environ["CLICKUP_API_TOKEN"],
    team_id=os.environ["CLICKUP_TEAM_ID"],
)

spaces = await clickup.get_spaces()
users = await clickup.get_team_members()
```

### 7.2 Debrief: Send Approved Tasks to ClickUp

Debrief routes tasks to a brand’s ClickUp space, and assigns them to a mapped ClickUp user ID.

```python
task = await clickup.create_task_in_space(
    space_id=brand.clickup_space_id,
    name=extracted.title,
    description_md=build_description_md(extracted, meeting),
    assignee_ids=[assignee.clickup_user_id] if assignee.clickup_user_id else [],
)
```

---

## 8. Out of Scope (for MVP)

- Multi-tenant ClickUp credentials stored per organization in DB
- “Template canonization” flows (Operator/SOP tooling)
- Webhooks (ClickUp events → Agency OS)
- Bidirectional sync (ClickUp updates → Agency OS updates)

---

## 9. Open Questions / Follow-ups

1) Should Command Center store `brands.clickup_list_id` (optional) to avoid default-list ambiguity?
2) Should Debrief create tasks in a specific list (e.g., “Inbox”) vs “Tasks” depending on brand/team conventions?
3) Do we need a shared/global rate limiter sooner (given `backend-core` + workers)?

