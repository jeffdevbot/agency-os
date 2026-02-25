# Product Requirement Document: Shared ClickUp Service

**Version:** 1.1
**Last Updated:** 2025-12-14
**Status:** Ready for Engineering
**Owner:** Agency OS

**Purpose:** Provide a single, consistent integration layer for the ClickUp API across Agency OS tools.

**Primary Consumers (current):**
- **Command Center** (`docs/07_command_center_prd.md`) — sync Spaces/Users for mapping; optionally resolve lists.
- **Debrief** (`docs/debrief_prd.md`) — create/update ClickUp tasks for approved meeting action items; match tasks to SOPs.
- **worker-sync** — scheduled sync jobs (spaces/users/list metadata, SOPs/Docs, etc.).

---

## 1. Executive Summary

Agency OS needs ClickUp for:
- mapping **brands → where tasks get created**
- mapping **team members → who tasks get assigned to**
- creating tasks reliably with retries, rate limiting, and consistent error handling
- syncing **SOPs/Docs** for task enrichment (Debrief matches tasks to SOPs)

The ClickUp Service is a shared internal module that:
- centralizes authentication, rate limiting, retries, and common ClickUp calls
- provides a stable API for tools (Command Center, Debrief) to call ClickUp without duplicating integration code

---

## 2. Fit With Command Center + Debrief

### 2.1 Source-of-Truth Fields (from other PRDs)

From `docs/07_command_center_prd.md`:
- `public.brands.clickup_space_id` — which ClickUp Space the brand maps to (for browsing / discovery).
- `public.brands.clickup_list_id` — preferred ClickUp List for task creation (tasks are created in lists).
- `public.profiles.clickup_user_id` — who can be assigned in ClickUp.
- `public.client_assignments` + `public.agency_roles` — role-based routing for Debrief.

From `docs/debrief_prd.md`:
- Debrief creates ClickUp tasks after review, using:
  - brand routing (`brands.clickup_list_id`, fallback: resolve default list from `brands.clickup_space_id`)
  - assignee routing (`profiles.clickup_user_id`)

### 2.2 Important ClickUp API Reality: Tasks are Created in Lists (not Spaces)

ClickUp’s API creates tasks via `POST /list/{list_id}/task`.

Because tasks are created in lists, the ClickUp Service must:
1) Prefer `brands.clickup_list_id` when present
2) Otherwise **resolve a default list** inside `brands.clickup_space_id` (MVP fallback)

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
- `CLICKUP_SOP_FOLDER_ID` (optional; folder containing SOP docs for Debrief sync)

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

async def create_subtask(
    self,
    parent_task_id: str,
    name: str,
    description_md: str | None = None,
    assignee_ids: list[str] | None = None,
) -> ClickUpTask:
    """
    Create a subtask under an existing task.
    Uses POST /list/{list_id}/task with parent={parent_task_id}.
    """
```

### 4.4 Docs APIs (SOP Sync for Debrief)

Debrief syncs SOPs from ClickUp Docs to enable task enrichment. These APIs support a nightly sync job that pulls SOP content into Supabase.

```python
async def search_docs(
    self,
    workspace_id: str | None = None,
    folder_id: str | None = None,
) -> list[ClickUpDoc]:
    """
    Search for Docs in a workspace or folder.
    GET /team/{team_id}/doc (with optional folder_id filter)

    Returns: list of docs with id, name, date_updated, parent info
    """

async def get_doc_pages(
    self,
    doc_id: str,
    format: Literal["markdown", "text"] = "markdown",
) -> list[ClickUpDocPage]:
    """
    Get all pages and content from a Doc.
    GET /doc/{doc_id}/page

    Returns: list of pages with id, name, content (in requested format)
    """

async def get_doc(self, doc_id: str) -> ClickUpDoc:
    """
    Get metadata for a single Doc.
    GET /doc/{doc_id}
    """
```

**SOP Sync Workflow:**
1. `worker-sync` runs nightly (or on-demand)
2. Calls `search_docs(folder_id=CLICKUP_SOP_FOLDER_ID)` to get all SOP docs
3. For each doc, calls `get_doc_pages(doc_id, format="markdown")` to get content
4. Upserts to `debrief_sops` table in Supabase
5. Regenerates embeddings for semantic search

### 4.5 Default List Resolution (Key Behavior)

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
- `search_docs(folder_id)` (TTL 1 hour)
- `get_doc_pages(doc_id)` (TTL 1 hour) — useful during sync to avoid redundant fetches

Cache scope: in-process only (simple TTL dict).

**Do not** cache write operations (`create_task*`, `create_subtask`, `update_task`).

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

### 7.3 worker-sync: Nightly SOP Sync

The sync worker pulls SOPs from ClickUp Docs into Supabase for Debrief to use during task extraction.

```python
# worker-sync/jobs/sync_sops.py
async def sync_sops_from_clickup():
    clickup = ClickUpService(
        api_token=os.environ["CLICKUP_API_TOKEN"],
        team_id=os.environ["CLICKUP_TEAM_ID"],
    )
    supabase = create_client(...)

    sop_folder_id = os.environ.get("CLICKUP_SOP_FOLDER_ID")
    if not sop_folder_id:
        logger.warning("CLICKUP_SOP_FOLDER_ID not set, skipping SOP sync")
        return

    # Get all docs in the SOP folder
    docs = await clickup.search_docs(folder_id=sop_folder_id)

    for doc in docs:
        # Get full content (all pages) in markdown
        pages = await clickup.get_doc_pages(doc.id, format="markdown")
        content = "\n\n---\n\n".join(page.content for page in pages)

        # Upsert to Supabase
        await supabase.from_("debrief_sops").upsert({
            "clickup_doc_id": doc.id,
            "name": doc.name,
            "content_md": content,
            "clickup_updated_at": doc.date_updated,
            "synced_at": datetime.utcnow().isoformat(),
        }, on_conflict="clickup_doc_id")

        # Regenerate embedding for semantic search
        await regenerate_sop_embedding(doc.id)

    logger.info(f"Synced {len(docs)} SOPs from ClickUp")
```

### 7.4 Debrief: Match Task to SOP

After extracting tasks, Debrief matches them to SOPs and enriches the task description.

```python
# Semantic search for matching SOP
sop = await find_matching_sop(
    task_title=extracted.title,
    task_type=extracted.task_type,  # e.g., "ppc_audit"
)

if sop:
    # LLM customizes SOP with client context
    customized = await customize_sop(
        sop_content=sop.content_md,
        brand_name=brand.name,
        client_context=meeting.summary_content,
        task_details=extracted.raw_text,
    )
    description = customized
else:
    description = extracted.description

# Create task with enriched description
task = await clickup.create_task_in_space(
    space_id=brand.clickup_space_id,
    name=extracted.title,
    description_md=description,
    assignee_ids=[assignee.clickup_user_id] if assignee else [],
)
```

---

## 8. Out of Scope (for MVP)

- Multi-tenant ClickUp credentials stored per organization in DB
- Webhooks (ClickUp events → Agency OS)
- Bidirectional sync (ClickUp updates → Agency OS updates)
- ClickUp Task Templates API (not supported by ClickUp — use Docs for SOPs instead)
- Creating/editing ClickUp Docs (read-only for MVP; SOPs are managed in ClickUp UI)

---

## 9. Open Questions / Follow-ups

1) Should Command Center store `brands.clickup_list_id` to avoid default-list ambiguity? (Recommended: yes; supported in Command Center schema)
2) Should Debrief create tasks in a specific list (e.g., "Inbox") vs "Tasks" depending on brand/team conventions?
3) Do we need a shared/global rate limiter sooner (given `backend-core` + workers)?
4) **SOP folder structure:** Should SOPs be in one flat folder, or organized by category (PPC, Catalog, etc.)? Does the sync need to handle nested folders?
5) **SOP matching strategy:** Keyword-based vs embedding similarity vs task_type enum? Hybrid approach recommended.
6) **SOP versioning:** Should we track SOP version history in Supabase, or just always use latest from ClickUp?
