import asyncio
import os
import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx


class ClickUpError(Exception):
    pass


class ClickUpAuthError(ClickUpError):
    pass


class ClickUpNotFoundError(ClickUpError):
    pass


class ClickUpValidationError(ClickUpError):
    pass


class ClickUpRateLimitError(ClickUpError):
    pass


class ClickUpAPIError(ClickUpError):
    pass


class ClickUpConfigurationError(ClickUpError):
    pass


@dataclass(frozen=True)
class ClickUpTask:
    id: str
    url: Optional[str] = None


class ClickUpService:
    def __init__(
        self,
        api_token: str,
        team_id: str,
        rate_limit_per_minute: int = 100,
        enable_cache: bool = True,
        default_list_name: Optional[str] = "Inbox",
        default_list_id: Optional[str] = None,
    ) -> None:
        self.api_token = api_token
        self.team_id = team_id
        self.rate_limit_per_minute = rate_limit_per_minute
        self.enable_cache = enable_cache
        self.default_list_name = default_list_name or "Inbox"
        self.default_list_id = default_list_id

        self._client = httpx.AsyncClient(
            base_url="https://api.clickup.com/api/v2",
            headers={"Authorization": self.api_token},
            timeout=httpx.Timeout(30.0),
        )

        self._space_list_cache: dict[str, tuple[float, str]] = {}
        self._rate_limit_lock = asyncio.Lock()
        self._next_allowed_request_at = 0.0
        self._clock = time.monotonic
        if self.rate_limit_per_minute > 0:
            self._min_request_interval_s = 60.0 / float(self.rate_limit_per_minute)
        else:
            self._min_request_interval_s = 0.0

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _apply_rate_limit(self) -> None:
        if self._min_request_interval_s <= 0:
            return

        async with self._rate_limit_lock:
            now = self._clock()
            wait_s = max(0.0, self._next_allowed_request_at - now)
            if wait_s > 0:
                await asyncio.sleep(wait_s)
                now = self._clock()
            self._next_allowed_request_at = max(now, self._next_allowed_request_at) + self._min_request_interval_s

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        params: dict[str, str | int | float | bool] | None = None,
    ) -> dict[str, Any]:
        max_attempts = 5
        backoff_s = 1.0

        for attempt in range(1, max_attempts + 1):
            try:
                await self._apply_rate_limit()
                response = await self._client.request(method, path, json=json, params=params)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt == max_attempts:
                    raise ClickUpAPIError(f"ClickUp request failed: {exc}") from exc
                await asyncio.sleep(backoff_s + (0.25 * (attempt - 1)))
                backoff_s *= 2
                continue

            if response.status_code == 401:
                raise ClickUpAuthError("ClickUp auth failed (401). Check CLICKUP_API_TOKEN.")
            if response.status_code == 404:
                raise ClickUpNotFoundError(f"ClickUp resource not found: {path}")
            if response.status_code in (400, 422):
                text = response.text
                raise ClickUpValidationError(f"ClickUp validation error ({response.status_code}): {text}")

            if response.status_code == 429 or response.status_code >= 500:
                if attempt == max_attempts:
                    text = response.text
                    if response.status_code == 429:
                        raise ClickUpRateLimitError(f"ClickUp rate limited (429): {text}")
                    raise ClickUpAPIError(f"ClickUp API error ({response.status_code}): {text}")
                await asyncio.sleep(backoff_s + (0.25 * (attempt - 1)))
                backoff_s *= 2
                continue

            if response.status_code < 200 or response.status_code >= 300:
                text = response.text
                raise ClickUpAPIError(f"ClickUp API error ({response.status_code}): {text}")

            return response.json()  # type: ignore[no-any-return]

        raise ClickUpAPIError("Unexpected ClickUp request failure")

    async def list_spaces(self, *, team_id: str | None = None) -> list[dict[str, Any]]:
        """GET /team/{team_id}/space — list all spaces in the workspace."""
        tid = team_id or self.team_id
        data = await self._request("GET", f"/team/{tid}/space")
        return [
            {"id": str(s["id"]), "name": str(s.get("name", "")), "team_id": tid}
            for s in data.get("spaces", [])
        ]

    async def get_authorized_workspaces(self) -> list[dict[str, Any]]:
        """GET /team — list workspaces visible to the authenticated user."""
        data = await self._request("GET", "/team")
        teams = data.get("teams")
        if not isinstance(teams, list):
            return []
        return [team for team in teams if isinstance(team, dict)]

    async def get_time_entries(
        self,
        *,
        start_date: int | None = None,
        end_date: int | None = None,
        assignee_ids: list[str | int] | None = None,
        include_task_tags: bool = False,
        include_location_names: bool = False,
        include_approval_history: bool = False,
        include_approval_details: bool = False,
        space_id: str | int | None = None,
        folder_id: str | int | None = None,
        list_id: str | int | None = None,
        task_id: str | None = None,
        is_billable: bool | None = None,
    ) -> list[dict[str, Any]]:
        """GET /team/{team_id}/time_entries — fetch time entries within a date range."""
        location_filters = [
            value
            for value in (space_id, folder_id, list_id, task_id)
            if value not in (None, "")
        ]
        if len(location_filters) > 1:
            raise ClickUpValidationError(
                "Only one of space_id, folder_id, list_id, or task_id may be provided"
            )

        params: dict[str, str] = {
            "include_task_tags": str(include_task_tags).lower(),
            "include_location_names": str(include_location_names).lower(),
            "include_approval_history": str(include_approval_history).lower(),
            "include_approval_details": str(include_approval_details).lower(),
        }
        if start_date is not None:
            params["start_date"] = str(int(start_date))
        if end_date is not None:
            params["end_date"] = str(int(end_date))

        normalized_assignees: list[str] = []
        for raw in assignee_ids or []:
            raw_str = str(raw).strip()
            if not raw_str:
                continue
            try:
                normalized_assignees.append(str(int(raw_str)))
            except ValueError:
                continue
        if normalized_assignees:
            params["assignee"] = ",".join(normalized_assignees)

        if space_id not in (None, ""):
            params["space_id"] = str(space_id)
        if folder_id not in (None, ""):
            params["folder_id"] = str(folder_id)
        if list_id not in (None, ""):
            params["list_id"] = str(list_id)
        if task_id:
            params["task_id"] = str(task_id)
        if is_billable is not None:
            params["is_billable"] = str(is_billable).lower()

        data = await self._request("GET", f"/team/{self.team_id}/time_entries", params=params)
        rows = data.get("data")
        if not isinstance(rows, list):
            return []
        return [row for row in rows if isinstance(row, dict)]

    async def get_space_lists(self, space_id: str) -> list[dict[str, Any]]:
        data = await self._request("GET", f"/space/{space_id}/list")
        lists = data.get("lists")
        if not isinstance(lists, list):
            return []
        return lists

    async def resolve_default_list_id(self, space_id: str, override_list_id: str | None = None) -> str:
        if override_list_id:
            return override_list_id

        if self.default_list_id:
            return self.default_list_id

        if self.enable_cache:
            cached = self._space_list_cache.get(space_id)
            if cached:
                cached_at, list_id = cached
                if (time.time() - cached_at) < 3600:
                    return list_id

        lists = await self.get_space_lists(space_id)
        if not lists:
            raise ClickUpConfigurationError("ClickUp space has no lists; cannot create tasks.")

        target_name = (self.default_list_name or "Inbox").strip().lower()
        selected = None
        for item in lists:
            name = str(item.get("name", "")).strip().lower()
            if name == target_name:
                selected = item
                break
        if not selected:
            selected = lists[0]

        list_id = str(selected.get("id", "")).strip()
        if not list_id:
            raise ClickUpAPIError("ClickUp list resolution returned an empty list id.")

        if self.enable_cache:
            self._space_list_cache[space_id] = (time.time(), list_id)

        return list_id

    async def get_tasks_in_list(
        self,
        list_id: str,
        *,
        date_updated_gt: int | None = None,
        date_updated_lt: int | None = None,
        page: int = 0,
        include_closed: bool = False,
        subtasks: bool = False,
    ) -> list[dict[str, Any]]:
        """Fetch tasks from a ClickUp list with optional date/page filters.

        Date params are epoch milliseconds (ClickUp convention).
        Returns raw task dicts from the ClickUp API.
        """
        params: dict[str, str] = {
            "page": str(page),
            "subtasks": str(subtasks).lower(),
            "include_closed": str(include_closed).lower(),
        }
        if date_updated_gt is not None:
            params["date_updated_gt"] = str(date_updated_gt)
        if date_updated_lt is not None:
            params["date_updated_lt"] = str(date_updated_lt)

        data = await self._request("GET", f"/list/{list_id}/task", params=params)
        tasks = data.get("tasks")
        if not isinstance(tasks, list):
            return []
        return tasks

    async def get_tasks_in_list_all_pages(
        self,
        list_id: str,
        *,
        date_updated_gt: int | None = None,
        date_updated_lt: int | None = None,
        include_closed: bool = False,
        max_tasks: int = 200,
    ) -> list[dict[str, Any]]:
        """Paginate through all tasks in a list up to max_tasks."""
        all_tasks: list[dict[str, Any]] = []
        page = 0
        while len(all_tasks) < max_tasks:
            batch = await self.get_tasks_in_list(
                list_id,
                date_updated_gt=date_updated_gt,
                date_updated_lt=date_updated_lt,
                page=page,
                include_closed=include_closed,
            )
            if not batch:
                break
            all_tasks.extend(batch)
            page += 1
            # ClickUp returns up to 100 per page; if fewer, we're done.
            if len(batch) < 100:
                break
        return all_tasks[:max_tasks]

    async def create_task_in_list(
        self,
        list_id: str,
        name: str,
        description_md: str | None = None,
        assignee_ids: list[str] | None = None,
    ) -> ClickUpTask:
        normalized_assignees: list[int] = []
        for raw in assignee_ids or []:
            raw_str = str(raw).strip()
            if not raw_str:
                continue
            try:
                normalized_assignees.append(int(raw_str))
            except ValueError:
                continue

        payload: dict[str, Any] = {
            "name": name,
            "description": description_md or "",
        }
        if normalized_assignees:
            payload["assignees"] = normalized_assignees

        data = await self._request("POST", f"/list/{list_id}/task", json=payload)
        task_id = str(data.get("id", "")).strip()
        if not task_id:
            raise ClickUpAPIError("ClickUp create task returned no id.")
        url = data.get("url")
        return ClickUpTask(id=task_id, url=str(url) if url else None)

    async def create_task_in_space(
        self,
        space_id: str,
        name: str,
        description_md: str | None = None,
        assignee_ids: list[str] | None = None,
        override_list_id: str | None = None,
    ) -> ClickUpTask:
        list_id = await self.resolve_default_list_id(space_id, override_list_id=override_list_id)
        return await self.create_task_in_list(
            list_id=list_id,
            name=name,
            description_md=description_md,
            assignee_ids=assignee_ids,
        )


def get_clickup_service() -> ClickUpService:
    api_token = os.environ.get("CLICKUP_API_TOKEN")
    team_id = os.environ.get("CLICKUP_TEAM_ID")
    if not api_token:
        raise ClickUpConfigurationError("CLICKUP_API_TOKEN not set")
    if not team_id:
        raise ClickUpConfigurationError("CLICKUP_TEAM_ID not set")

    rate = int(os.environ.get("CLICKUP_RATE_LIMIT_PER_MINUTE", "100"))
    enable_cache = os.environ.get("CLICKUP_ENABLE_CACHE", "true").lower() != "false"
    default_list_name = os.environ.get("CLICKUP_DEFAULT_LIST_NAME", "Inbox")
    default_list_id = os.environ.get("CLICKUP_DEFAULT_LIST_ID")

    return ClickUpService(
        api_token=api_token,
        team_id=team_id,
        rate_limit_per_minute=rate,
        enable_cache=enable_cache,
        default_list_name=default_list_name,
        default_list_id=default_list_id,
    )
