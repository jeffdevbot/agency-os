# Product Requirement Document: Shared ClickUp Service

**Version:** 0.1 (Early Draft)
**Last Updated:** 2025-11-21
**Status:** Draft / Discussion
**Architecture Pattern:** Option A (Shared Library/Module)

---

## 1. Executive Summary

The **ClickUp Service** is a centralized library for all ClickUp API interactions across Agency OS. It provides a unified interface for Team Central, The Operator, and future tools to interact with ClickUp while handling authentication, rate limiting, retries, and caching in a single location.

**Key Design Decision:** We're implementing this as a **shared Python library/module** (Option A) rather than a standalone microservice, keeping infrastructure simple while providing centralized ClickUp logic.

### Primary Goals

1. **Centralize ClickUp API logic** - Single source of truth for all ClickUp operations
2. **Handle rate limiting** - Respect ClickUp's 100 req/min limit across all consumers
3. **Simplify integration** - Tools import the service rather than implementing ClickUp calls directly
4. **Enable testing** - Mockable interface for unit/integration tests
5. **Future-proof** - Easy to evolve or swap if we migrate to different PM tools

---

## 2. Architecture Overview

### 2.1 Implementation Pattern: Shared Library (Option A)

```
/lib/clickup/                      # Shared library location
  ├── __init__.py
  ├── service.py                   # Main ClickUpService class
  ├── types.py                     # Type definitions (ClickUpTask, ClickUpSpace, etc.)
  ├── rate_limiter.py              # Token bucket rate limiter
  ├── cache.py                     # Optional caching layer
  └── exceptions.py                # Custom exceptions

backend-core/                      # FastAPI backend
  └── app/
      ├── routers/
      │   ├── ops.py               # The Operator routes (imports ClickUpService)
      │   └── team_central.py      # Team Central routes (imports ClickUpService)
      └── services/
          └── sop_librarian.py     # Uses ClickUpService

worker-sync/                       # Background worker
  └── jobs/
      └── sync_clickup_templates.py  # Uses ClickUpService

frontend-web/                      # Next.js frontend
  └── (No direct ClickUp calls - all via backend APIs)
```

**Why this pattern?**
- ✅ Simple to implement and deploy (already part of existing services)
- ✅ Direct function calls (fast, low latency)
- ✅ Shared code across backend-core and worker-sync
- ✅ No extra infrastructure needed
- ⚠️ Rate limiter state is per-process (acceptable for current scale)
- ⚠️ Cache not shared between services (use Supabase for persistent cache if needed)

---

### 2.2 Future Evolution Path (Option B)

If we outgrow Option A, we can evolve to a standalone microservice:

```
clickup-service/                   # New Render service
  ├── app/main.py                  # FastAPI server
  ├── clickup/
  │   ├── service.py
  │   └── types.py
  └── requirements.txt

backend-core/ → HTTP calls to clickup-service
worker-sync/  → HTTP calls to clickup-service
```

**When to migrate:**
- ClickUp rate limits become a bottleneck across services
- Need centralized rate-limit state (shared Redis)
- Want to expose ClickUp integration to external tools
- Building 5+ tools that need ClickUp access

**For now:** Start with Option A, revisit if needed

---

## 3. Service API Contract

### 3.1 Core Service Class

```python
# lib/clickup/service.py

from typing import List, Optional, Dict, Any
from lib.clickup.types import ClickUpSpace, ClickUpUser, ClickUpTask, ClickUpTemplate
from lib.clickup.rate_limiter import RateLimiter
from lib.clickup.exceptions import ClickUpAPIError, RateLimitExceeded

class ClickUpService:
    """Shared ClickUp API service for all Agency OS tools

    Handles:
    - Authentication via API token
    - Rate limiting (100 req/min)
    - Exponential backoff retries
    - Optional caching for read-heavy endpoints

    Usage:
        clickup = ClickUpService(api_token=os.getenv("CLICKUP_API_TOKEN"))
        spaces = await clickup.get_spaces()
    """

    def __init__(
        self,
        api_token: str,
        team_id: str = "42600885",  # Ecomlabs team ID
        rate_limit: int = 100,       # Requests per minute
        enable_cache: bool = True
    ):
        """Initialize ClickUp service

        Args:
            api_token: ClickUp API token (from env var)
            team_id: ClickUp team ID (default: Ecomlabs)
            rate_limit: Max requests per minute (default: 100)
            enable_cache: Whether to cache read operations (default: True)
        """
        self.api_token = api_token
        self.team_id = team_id
        self.base_url = "https://api.clickup.com/api/v2"
        self.rate_limiter = RateLimiter(max_requests=rate_limit, window_seconds=60)
        self.cache_enabled = enable_cache
        self._session = None  # aiohttp session (lazy init)

    # --- Team Central Requirements ---

    async def get_spaces(self) -> List[ClickUpSpace]:
        """Fetch all Spaces for the team

        Used by: Team Central (client mapping UI)
        Cache: 1 hour (spaces don't change frequently)
        API: GET /team/{team_id}/space

        Returns:
            List of spaces with id, name, private, multiple_assignees fields
        """

    async def get_team_members(self) -> List[ClickUpUser]:
        """Fetch all Users/Members for the team

        Used by: Team Central (user mapping UI)
        Cache: 1 hour (team members don't change frequently)
        API: GET /team/{team_id}/member

        Returns:
            List of users with id, username, email, initials fields
        """

    # --- The Operator Requirements ---

    async def get_task(self, task_id: str) -> ClickUpTask:
        """Fetch a single task by ID

        Used by: The Operator (SOP canonization)
        Cache: None (always fetch fresh for canonization)
        API: GET /task/{task_id}

        Returns:
            Task with full details (name, description, checklists, subtasks, custom fields)
        """

    async def get_tasks(
        self,
        space_id: Optional[str] = None,
        list_id: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[ClickUpTask]:
        """Fetch tasks with optional filters

        Used by: The Operator (status dashboards, Kanban boards)
        Cache: 5 minutes (balance freshness vs API load)
        API: GET /space/{space_id}/task or GET /list/{list_id}/task

        Args:
            space_id: Filter by space (for client task lists)
            list_id: Filter by list (for specific views)
            filters: Additional filters (status, assignee, due_date, etc.)

        Returns:
            List of tasks matching filters
        """

    async def create_task(
        self,
        list_id: str,
        name: str,
        description: Optional[str] = None,
        markdown_description: Optional[str] = None,
        assignees: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        status: Optional[str] = None,
        priority: Optional[int] = None,
        due_date: Optional[int] = None,
        custom_fields: Optional[List[Dict]] = None
    ) -> ClickUpTask:
        """Create a new task

        Used by: The Operator (creating draft SOP templates)
        Cache: None (write operation)
        API: POST /list/{list_id}/task

        Args:
            list_id: List to create task in
            name: Task title
            description: Plain text description
            markdown_description: Markdown description (preferred)
            assignees: List of user IDs
            tags: List of tag names
            status: Status name (e.g., "Open", "In Progress")
            priority: 1 (urgent) to 4 (low)
            due_date: Unix timestamp (ms)
            custom_fields: List of custom field objects

        Returns:
            Created task with ID and URL
        """

    async def update_task(
        self,
        task_id: str,
        **updates: Any
    ) -> ClickUpTask:
        """Update an existing task

        Used by: The Operator (future - task assignment/updates)
        Cache: None (write operation)
        API: PUT /task/{task_id}

        Args:
            task_id: Task to update
            **updates: Fields to update (name, description, status, assignees, etc.)

        Returns:
            Updated task
        """

    async def get_templates(self) -> List[ClickUpTemplate]:
        """Fetch all task templates for the team

        Used by: The Operator (nightly SOP sync), Worker
        Cache: None (called once daily)
        API: GET /team/{team_id}/taskTemplate

        Returns:
            List of templates with id, name, template structure

        Note:
            ClickUp API does NOT support creating templates programmatically.
            Templates must be created manually in ClickUp UI.
        """

    async def create_task_from_template(
        self,
        list_id: str,
        template_id: str,
        name: str
    ) -> ClickUpTask:
        """Create a task from a template

        Used by: The Operator (future - instantiate SOPs)
        Cache: None (write operation)
        API: POST /list/{list_id}/taskTemplate/{template_id}

        Args:
            list_id: List to create task in
            template_id: Template to use
            name: Name for new task

        Returns:
            Created task
        """

    # --- Helper Methods ---

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json: Optional[Dict] = None,
        retry_count: int = 3
    ) -> Dict[str, Any]:
        """Internal HTTP request handler with rate limiting and retries

        Implements:
        - Rate limiting via token bucket
        - Exponential backoff (2s, 4s, 8s)
        - Auth header injection
        - Error parsing

        Raises:
            RateLimitExceeded: If rate limit hit and retries exhausted
            ClickUpAPIError: For API errors (4xx, 5xx)
        """
```

---

### 3.2 Type Definitions

```python
# lib/clickup/types.py

from typing import List, Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass

@dataclass
class ClickUpSpace:
    """ClickUp Space representation"""
    id: str
    name: str
    private: bool
    multiple_assignees: bool
    features: Dict[str, Any]

@dataclass
class ClickUpUser:
    """ClickUp User/Member representation"""
    id: str
    username: str
    email: str
    color: str
    initials: str
    profilePicture: Optional[str] = None

@dataclass
class ClickUpTask:
    """ClickUp Task representation"""
    id: str
    name: str
    description: str
    markdown_description: str
    status: Dict[str, str]
    orderindex: str
    date_created: str
    date_updated: str
    date_closed: Optional[str]
    creator: Dict[str, Any]
    assignees: List[Dict[str, Any]]
    checklists: List[Dict[str, Any]]
    tags: List[Dict[str, str]]
    parent: Optional[str]
    priority: Optional[Dict[str, Any]]
    due_date: Optional[str]
    start_date: Optional[str]
    time_estimate: Optional[int]
    custom_fields: List[Dict[str, Any]]
    url: str

@dataclass
class ClickUpTemplate:
    """ClickUp Task Template representation"""
    id: str
    name: str
    template: Dict[str, Any]  # Full template structure

@dataclass
class ClickUpList:
    """ClickUp List representation"""
    id: str
    name: str
    orderindex: int
    content: str
    status: Dict[str, Any]
    priority: Optional[Dict[str, Any]]
    assignee: Optional[Dict[str, Any]]
    task_count: int
    due_date: Optional[str]
    start_date: Optional[str]
    folder: Dict[str, str]
    space: Dict[str, str]
```

---

### 3.3 Rate Limiter

```python
# lib/clickup/rate_limiter.py

import asyncio
import time
from typing import Optional

class RateLimiter:
    """Token bucket rate limiter for ClickUp API

    ClickUp limits: 100 requests per minute per workspace

    This implementation:
    - Uses token bucket algorithm
    - Supports async/await
    - Blocks until tokens available (no exceptions)
    - Refills tokens at steady rate

    Usage:
        limiter = RateLimiter(max_requests=100, window_seconds=60)
        await limiter.acquire()  # Blocks until token available
    """

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_tokens = max_requests
        self.tokens = max_requests
        self.refill_rate = max_requests / window_seconds  # tokens per second
        self.last_refill = time.time()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire a token (blocks if none available)"""
        async with self._lock:
            await self._refill()

            while self.tokens < 1:
                # Calculate wait time for next token
                wait_time = (1 - self.tokens) / self.refill_rate
                await asyncio.sleep(wait_time)
                await self._refill()

            self.tokens -= 1

    async def _refill(self) -> None:
        """Refill tokens based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(
            self.max_tokens,
            self.tokens + (elapsed * self.refill_rate)
        )
        self.last_refill = now
```

---

### 3.4 Custom Exceptions

```python
# lib/clickup/exceptions.py

class ClickUpAPIError(Exception):
    """Base exception for ClickUp API errors"""
    def __init__(self, message: str, status_code: int, response: dict):
        super().__init__(message)
        self.status_code = status_code
        self.response = response

class RateLimitExceeded(ClickUpAPIError):
    """Raised when rate limit is exceeded and retries exhausted"""
    pass

class ClickUpAuthError(ClickUpAPIError):
    """Raised for authentication failures (401)"""
    pass

class ClickUpNotFoundError(ClickUpAPIError):
    """Raised when resource not found (404)"""
    pass

class ClickUpValidationError(ClickUpAPIError):
    """Raised for validation errors (400, 422)"""
    pass
```

---

## 4. Usage Examples

### 4.1 Team Central: Sync Spaces

```python
# backend-core/app/routers/team_central.py

from fastapi import APIRouter, HTTPException
from lib.clickup.service import ClickUpService
from lib.clickup.exceptions import ClickUpAPIError
import os

router = APIRouter(prefix="/api/team-central")

@router.post("/clickup/sync-spaces")
async def sync_clickup_spaces():
    """Fetch all ClickUp spaces for client mapping UI"""
    try:
        clickup = ClickUpService(api_token=os.getenv("CLICKUP_API_TOKEN"))
        spaces = await clickup.get_spaces()

        return {
            "spaces": [
                {
                    "id": space.id,
                    "name": space.name,
                    "private": space.private
                }
                for space in spaces
            ]
        }
    except ClickUpAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
```

---

### 4.2 The Operator: Canonize Task

```python
# backend-core/app/services/sop_librarian.py

from lib.clickup.service import ClickUpService
from lib.clickup.exceptions import ClickUpNotFoundError
import os
import re

class SOPLibrarian:
    def __init__(self):
        self.clickup = ClickUpService(api_token=os.getenv("CLICKUP_API_TOKEN"))

    async def canonize_task(self, task_url: str, suggested_name: str) -> dict:
        """Create a generalized SOP from an executed task"""

        # Extract task ID from URL
        task_id = self._extract_task_id(task_url)

        # Fetch task details
        try:
            task = await self.clickup.get_task(task_id)
        except ClickUpNotFoundError:
            raise ValueError(f"Task not found: {task_id}")

        # AI generalization (pseudo-code)
        generalized = await self._generalize_task(task)

        # Create draft template task in "Templates" list
        draft = await self.clickup.create_task(
            list_id=os.getenv("CLICKUP_TEMPLATES_LIST_ID"),
            name=suggested_name,
            markdown_description=generalized["description"],
            tags=["sop-draft", generalized["category"]]
        )

        return {
            "clickup_task_id": draft.id,
            "clickup_task_url": draft.url,
            "generalized_content": generalized,
            "detected_variables": generalized["variables"],
            "instructions": "Click ••• → Templates → Save as Template"
        }

    def _extract_task_id(self, url: str) -> str:
        """Extract task ID from ClickUp URL"""
        # https://app.clickup.com/t/abc123 → abc123
        match = re.search(r'/t/([a-zA-Z0-9]+)', url)
        if not match:
            raise ValueError(f"Invalid ClickUp task URL: {url}")
        return match.group(1)
```

---

### 4.3 Worker: Nightly Template Sync

```python
# worker-sync/jobs/sync_clickup_templates.py

from lib.clickup.service import ClickUpService
from lib.clickup.exceptions import ClickUpAPIError
import os
import asyncio
from supabase import create_client

async def sync_clickup_templates():
    """Nightly job: Sync ClickUp templates to Supabase SOP library"""

    clickup = ClickUpService(api_token=os.getenv("CLICKUP_API_TOKEN"))
    supabase = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    )

    try:
        # Fetch all templates
        templates = await clickup.get_templates()

        synced_count = 0
        new_count = 0
        updated_count = 0

        for template in templates:
            # Check if exists in Supabase
            existing = supabase.table("sops").select("*").eq(
                "clickup_template_id", template.id
            ).execute()

            # Detect variables in template content
            variables = detect_variables(template.template)

            # Generate embedding for search
            embedding = await generate_embedding(template.name + " " + str(template.template))

            # Upsert to Supabase
            if existing.data:
                # Update existing
                supabase.table("sops").update({
                    "name": template.name,
                    "content": template.template,
                    "variables": variables,
                    "embedding": embedding,
                    "last_synced_at": "now()"
                }).eq("clickup_template_id", template.id).execute()
                updated_count += 1
            else:
                # Insert new
                supabase.table("sops").insert({
                    "clickup_template_id": template.id,
                    "name": template.name,
                    "content": template.template,
                    "scope": "canonical",  # Default; can be refined
                    "variables": variables,
                    "embedding": embedding
                }).execute()
                new_count += 1

            synced_count += 1

        print(f"✅ Synced {synced_count} templates ({new_count} new, {updated_count} updated)")

    except ClickUpAPIError as e:
        print(f"❌ Sync failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(sync_clickup_templates())
```

---

## 5. Configuration & Environment

### 5.1 Required Environment Variables

```bash
# Render Environment Group: agency-os-env-var

# ClickUp API (Personal API Token)
CLICKUP_API_TOKEN="pk_xxxxx..."

# ClickUp Team ID (Ecomlabs)
CLICKUP_TEAM_ID="42600885"

# ClickUp Templates List ID (where draft SOPs are created)
CLICKUP_TEMPLATES_LIST_ID="list_123456"

# Optional: Rate limit override (default: 100 req/min)
CLICKUP_RATE_LIMIT=100

# Optional: Enable/disable caching (default: true)
CLICKUP_ENABLE_CACHE=true
```

---

### 5.2 Caching Strategy

**Read-Heavy Endpoints (Cache Enabled):**
- `get_spaces()` - Cache: 1 hour (spaces rarely change)
- `get_team_members()` - Cache: 1 hour (team changes infrequent)
- `get_tasks()` - Cache: 5 minutes (balance freshness vs load)

**Write Operations (No Cache):**
- `create_task()`
- `update_task()`
- `create_task_from_template()`

**Always Fresh:**
- `get_task()` - Used for SOP canonization (must be current)
- `get_templates()` - Called once daily (no cache needed)

**Cache Implementation:**
- In-memory cache per process (simple dict with TTL)
- Future: Redis-backed cache if we move to Option B (microservice)

---

## 6. Error Handling & Retry Strategy

### 6.1 Retry Logic

```python
# Exponential backoff for transient errors

async def _request(self, method, endpoint, retry_count=3):
    for attempt in range(retry_count):
        try:
            # Acquire rate limit token
            await self.rate_limiter.acquire()

            # Make request
            response = await self._session.request(method, endpoint, ...)

            # Success
            if response.status < 400:
                return await response.json()

            # Handle errors
            if response.status == 429:  # Rate limit
                wait = 2 ** attempt  # 2s, 4s, 8s
                await asyncio.sleep(wait)
                continue

            if response.status >= 500:  # Server error
                wait = 2 ** attempt
                await asyncio.sleep(wait)
                continue

            # Client errors (4xx) - don't retry
            raise ClickUpAPIError(...)

        except asyncio.TimeoutError:
            if attempt < retry_count - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            raise

    # All retries exhausted
    raise RateLimitExceeded(...)
```

---

### 6.2 Error Response Mapping

| ClickUp Status | Exception | Retry? |
|----------------|-----------|--------|
| 200-299 | Success | N/A |
| 400 | `ClickUpValidationError` | No |
| 401 | `ClickUpAuthError` | No |
| 404 | `ClickUpNotFoundError` | No |
| 422 | `ClickUpValidationError` | No |
| 429 | `RateLimitExceeded` | Yes (3x) |
| 500-599 | `ClickUpAPIError` | Yes (3x) |
| Timeout | `ClickUpAPIError` | Yes (3x) |

---

## 7. Testing Strategy

### 7.1 Unit Tests (with Mocks)

```python
# tests/test_clickup_service.py

import pytest
from lib.clickup.service import ClickUpService
from lib.clickup.types import ClickUpSpace
from unittest.mock import AsyncMock, patch

@pytest.fixture
def clickup_service():
    return ClickUpService(api_token="test_token")

@pytest.mark.asyncio
async def test_get_spaces(clickup_service):
    """Test fetching spaces with mocked API response"""

    mock_response = {
        "spaces": [
            {"id": "123", "name": "Brand X", "private": False},
            {"id": "456", "name": "Brand Y", "private": True}
        ]
    }

    with patch.object(clickup_service, '_request', new=AsyncMock(return_value=mock_response)):
        spaces = await clickup_service.get_spaces()

        assert len(spaces) == 2
        assert spaces[0].id == "123"
        assert spaces[0].name == "Brand X"

@pytest.mark.asyncio
async def test_rate_limiting(clickup_service):
    """Test that rate limiter blocks when limit reached"""

    # Set very low rate limit for testing
    clickup_service.rate_limiter.max_tokens = 2

    start = time.time()

    # These should be instant
    await clickup_service.rate_limiter.acquire()
    await clickup_service.rate_limiter.acquire()

    # This should block until refill
    await clickup_service.rate_limiter.acquire()

    elapsed = time.time() - start
    assert elapsed > 0.5  # Should have waited for refill
```

---

### 7.2 Integration Tests (Real API)

```python
# tests/integration/test_clickup_integration.py

import pytest
import os
from lib.clickup.service import ClickUpService

@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_clickup_api():
    """Test actual ClickUp API calls (requires CLICKUP_API_TOKEN)"""

    api_token = os.getenv("CLICKUP_API_TOKEN")
    if not api_token:
        pytest.skip("CLICKUP_API_TOKEN not set")

    clickup = ClickUpService(api_token=api_token)

    # Test get_spaces
    spaces = await clickup.get_spaces()
    assert len(spaces) > 0
    assert all(hasattr(s, 'id') for s in spaces)

    # Test get_team_members
    members = await clickup.get_team_members()
    assert len(members) > 0
    assert all(hasattr(m, 'email') for m in members)
```

---

## 8. Performance & Monitoring

### 8.1 Metrics to Track

**API Performance:**
- Request latency (p50, p95, p99)
- Error rate by endpoint
- Rate limit hits
- Cache hit rate

**Resource Usage:**
- Memory usage (cache size)
- Active connections
- Token bucket state

**Business Metrics:**
- Templates synced per day
- Tasks created per day
- Most-used endpoints

---

### 8.2 Logging

```python
import logging

logger = logging.getLogger("clickup.service")

async def _request(self, method, endpoint, ...):
    logger.info(f"ClickUp API: {method} {endpoint}")

    try:
        # ... request logic ...
        logger.debug(f"Response: {response.status} in {duration}ms")
    except Exception as e:
        logger.error(f"ClickUp API error: {e}", exc_info=True)
        raise
```

**Log Levels:**
- `INFO` - All API requests (method, endpoint)
- `DEBUG` - Response details, cache hits/misses
- `WARNING` - Rate limit warnings, retries
- `ERROR` - API errors, timeouts

---

## 9. Security Considerations

### 9.1 API Token Management

- ✅ Store in environment variables (never hardcode)
- ✅ Use Render environment group (`agency-os-env-var`)
- ✅ Personal API Token (for now) - Admin/Owner only
- 🔄 Future: OAuth for multi-user access

### 9.2 Data Privacy

- ✅ Never log full API responses (may contain sensitive data)
- ✅ Never expose API token in error messages
- ✅ Sanitize task content before logging

---

## 10. Future Enhancements

### Phase 2: Advanced Features

**Webhooks Support:**
- Listen for ClickUp events (task created, status changed)
- Real-time updates instead of polling
- Reduce API calls by 80%

**Bulk Operations:**
- `create_tasks_batch()` for mass task creation
- `update_tasks_batch()` for bulk updates
- Optimize with parallel requests (within rate limits)

**Advanced Caching:**
- Redis-backed cache (if we move to Option B)
- Shared cache across services
- Invalidation on webhooks

**Multi-Workspace Support:**
- Support multiple ClickUp teams
- Per-workspace rate limiting
- Workspace routing

---

### Phase 3: Migration to Option B (Microservice)

**If we outgrow Option A:**

1. Extract `/lib/clickup/` to standalone repo
2. Create FastAPI wrapper (HTTP endpoints)
3. Deploy as new Render service
4. Update consumers to make HTTP calls
5. Implement Redis-backed cache
6. Add centralized rate limiter (shared state)

**Migration checklist:**
- [ ] Extract library to `clickup-service/` repo
- [ ] Create HTTP API layer
- [ ] Deploy to Render
- [ ] Update backend-core to use HTTP client
- [ ] Update worker-sync to use HTTP client
- [ ] Implement Redis cache
- [ ] Monitor performance vs Option A

---

## 11. Open Questions & Decisions Needed

1. **Template List ID:** Where should Operator create draft SOP tasks? Need to designate a ClickUp list.
2. **Cache Backend:** Start with in-memory or use Supabase for persistent cache?
3. **Monitoring:** Integrate with existing monitoring (Sentry, Datadog) or just logs for M1?
4. **Webhook Strategy:** Should we plan for webhooks now, or defer to Phase 2?
5. **Multi-Tenant:** If we ever support multiple ClickUp teams, how do we handle auth/routing?

---

## 12. Dependencies

- ✅ Python 3.9+
- ✅ `aiohttp` for async HTTP requests
- ✅ `pydantic` for type validation (optional)
- ✅ Environment variable: `CLICKUP_API_TOKEN`
- ✅ Environment variable: `CLICKUP_TEAM_ID`

---

## 13. Acceptance Criteria

### M1 (MVP)

- ✅ ClickUpService class implemented with all required methods
- ✅ Rate limiter enforces 100 req/min limit
- ✅ Exponential backoff retry works for 429/5xx errors
- ✅ Team Central can fetch spaces and team members
- ✅ The Operator can fetch tasks, create tasks, and sync templates
- ✅ Worker can sync templates nightly
- ✅ Unit tests cover core functionality (>80% coverage)
- ✅ Integration tests pass against real ClickUp API

### M2 (Hardening)

- ✅ Caching reduces API calls by 50%+
- ✅ Logging captures all API interactions
- ✅ Error handling provides clear, actionable messages
- ✅ Performance metrics tracked (latency, error rate)
- ✅ Documentation complete (docstrings, README)

---

_This is an early draft. Feedback welcome! Update as we refine the architecture during implementation._

---

## Appendix: ClickUp API Reference

**Official Docs:** https://clickup.com/api

**Key Endpoints Used:**

| Endpoint | Method | Purpose | Consumer |
|----------|--------|---------|----------|
| `/team/{team_id}/space` | GET | List spaces | Team Central |
| `/team/{team_id}/member` | GET | List team members | Team Central |
| `/task/{task_id}` | GET | Get task details | The Operator |
| `/space/{space_id}/task` | GET | List tasks in space | The Operator |
| `/list/{list_id}/task` | POST | Create task | The Operator |
| `/task/{task_id}` | PUT | Update task | The Operator |
| `/team/{team_id}/taskTemplate` | GET | List templates | The Operator, Worker |
| `/list/{list_id}/taskTemplate/{template_id}` | POST | Create task from template | The Operator (future) |

**Rate Limits:**
- 100 requests per minute per workspace
- Rate limit headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

**Authentication:**
- Header: `Authorization: {api_token}`
- Token format: `pk_xxxxx...` (Personal API Token)
