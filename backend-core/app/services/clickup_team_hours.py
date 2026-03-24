from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from supabase import Client

from .clickup import ClickUpConfigurationError, ClickUpService


MS_PER_HOUR = 3_600_000


def _as_str(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _hours(duration_ms: int) -> float:
    return round(duration_ms / MS_PER_HOUR, 2)


def _safe_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class _MappedScope:
    client_id: str
    client_name: str
    brand_id: str | None = None
    brand_name: str | None = None


class ClickUpTeamHoursService:
    def __init__(self, db: Client, clickup: ClickUpService) -> None:
        self.db = db
        self.clickup = clickup

    async def build_report_async(self, *, start_date_ms: int, end_date_ms: int) -> dict[str, Any]:
        if start_date_ms <= 0 or end_date_ms <= 0:
            raise ValueError("start_date_ms and end_date_ms must be positive Unix millisecond values")
        if start_date_ms > end_date_ms:
            raise ValueError("start_date_ms must be less than or equal to end_date_ms")

        workspace = await self._get_configured_workspace_async()
        assignee_ids = self._workspace_assignee_ids(workspace)
        entries = await self.clickup.get_time_entries(
            start_date=start_date_ms,
            end_date=end_date_ms,
            assignee_ids=assignee_ids,
            include_task_tags=True,
            include_location_names=True,
        )

        mappings = self._load_mappings()
        normalized = [self._normalize_entry(row, mappings) for row in entries]
        return self._build_response(
            normalized,
            start_date_ms=start_date_ms,
            end_date_ms=end_date_ms,
        )

    async def _get_configured_workspace_async(self) -> dict[str, Any]:
        teams = await self.clickup.get_authorized_workspaces()
        configured = str(self.clickup.team_id or "").strip()
        for team in teams:
            team_id = _as_str(team.get("id"))
            if team_id == configured:
                return team
        raise ClickUpConfigurationError(
            f"Configured CLICKUP_TEAM_ID {configured!r} was not found in authorized workspaces"
        )

    def _workspace_assignee_ids(self, workspace: dict[str, Any]) -> list[str]:
        assignee_ids: list[str] = []
        for member in workspace.get("members") or []:
            if not isinstance(member, dict):
                continue
            user = member.get("user")
            if not isinstance(user, dict):
                continue
            user_id = _as_str(user.get("id"))
            if user_id:
                assignee_ids.append(user_id)
        return assignee_ids

    def _load_mappings(self) -> dict[str, Any]:
        profiles_resp = (
            self.db.table("profiles")
            .select("id, email, display_name, full_name, clickup_user_id")
            .execute()
        )
        brands_resp = (
            self.db.table("brands")
            .select("id, client_id, name, clickup_space_id, clickup_list_id")
            .execute()
        )
        clients_resp = self.db.table("agency_clients").select("id, name").execute()

        profiles = profiles_resp.data if isinstance(profiles_resp.data, list) else []
        brands = brands_resp.data if isinstance(brands_resp.data, list) else []
        clients = clients_resp.data if isinstance(clients_resp.data, list) else []

        client_name_by_id = {
            str(row.get("id")): str(row.get("name") or "").strip() or "Unknown client"
            for row in clients
            if isinstance(row, dict) and _as_str(row.get("id"))
        }

        profiles_by_clickup_user: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in profiles:
            if not isinstance(row, dict):
                continue
            clickup_user_id = _as_str(row.get("clickup_user_id"))
            if clickup_user_id:
                profiles_by_clickup_user[clickup_user_id].append(row)

        scopes_by_list_id: dict[str, list[_MappedScope]] = defaultdict(list)
        scopes_by_space_id: dict[str, list[_MappedScope]] = defaultdict(list)
        for row in brands:
            if not isinstance(row, dict):
                continue
            brand_id = _as_str(row.get("id"))
            client_id = _as_str(row.get("client_id"))
            brand_name = str(row.get("name") or "").strip()
            if not brand_id or not client_id or not brand_name:
                continue
            mapped = _MappedScope(
                client_id=client_id,
                client_name=client_name_by_id.get(client_id, "Unknown client"),
                brand_id=brand_id,
                brand_name=brand_name,
            )
            list_id = _as_str(row.get("clickup_list_id"))
            if list_id:
                scopes_by_list_id[list_id].append(mapped)
            space_id = _as_str(row.get("clickup_space_id"))
            if space_id:
                scopes_by_space_id[space_id].append(mapped)

        return {
            "profiles_by_clickup_user": profiles_by_clickup_user,
            "scopes_by_list_id": scopes_by_list_id,
            "scopes_by_space_id": scopes_by_space_id,
        }

    def _normalize_entry(self, row: dict[str, Any], mappings: dict[str, Any]) -> dict[str, Any]:
        user = row.get("user") if isinstance(row.get("user"), dict) else {}
        task = row.get("task") if isinstance(row.get("task"), dict) else {}
        task_location = row.get("task_location") if isinstance(row.get("task_location"), dict) else {}

        clickup_user_id = _as_str(user.get("id"))
        list_id = _as_str(task_location.get("list_id"))
        space_id = _as_str(task_location.get("space_id"))

        profile = self._resolve_profile(clickup_user_id, mappings["profiles_by_clickup_user"])
        scope = self._resolve_scope(
            list_id=list_id,
            space_id=space_id,
            scopes_by_list_id=mappings["scopes_by_list_id"],
            scopes_by_space_id=mappings["scopes_by_space_id"],
        )

        raw_duration_ms = _safe_int(row.get("duration")) or 0
        is_running = raw_duration_ms < 0
        duration_ms = max(raw_duration_ms, 0)

        return {
            "time_entry_id": _as_str(row.get("id")),
            "workspace_id": _as_str(row.get("wid")),
            "clickup_user_id": clickup_user_id,
            "clickup_username": _as_str(user.get("username")),
            "clickup_user_email": _as_str(user.get("email")),
            "team_member_profile_id": profile.get("id") if profile else None,
            "team_member_name": self._profile_name(profile) if profile else None,
            "team_member_email": _as_str(profile.get("email")) if profile else None,
            "team_member_mapped": bool(profile),
            "billable": bool(row.get("billable")) if row.get("billable") is not None else None,
            "start_ms": _safe_int(row.get("start")),
            "end_ms": _safe_int(row.get("end")),
            "duration_ms": duration_ms,
            "is_running": is_running,
            "description": _as_str(row.get("description")),
            "task_id": _as_str(task.get("id")),
            "task_custom_id": _as_str(task.get("custom_id")),
            "task_name": _as_str(task.get("name")),
            "task_url": _as_str(row.get("task_url")),
            "space_id": space_id,
            "space_name": _as_str(task_location.get("space_name")),
            "folder_id": _as_str(task_location.get("folder_id")),
            "folder_name": _as_str(task_location.get("folder_name")),
            "list_id": list_id,
            "list_name": _as_str(task_location.get("list_name")),
            "task_tags": [
                str(tag.get("name") or "").strip()
                for tag in (row.get("task_tags") or [])
                if isinstance(tag, dict) and str(tag.get("name") or "").strip()
            ],
            "brand_id": scope.brand_id if scope else None,
            "brand_name": scope.brand_name if scope else None,
            "client_id": scope.client_id if scope else None,
            "client_name": scope.client_name if scope else None,
            "space_mapped": bool(scope),
        }

    def _resolve_profile(
        self,
        clickup_user_id: str | None,
        profiles_by_clickup_user: dict[str, list[dict[str, Any]]],
    ) -> dict[str, Any] | None:
        if not clickup_user_id:
            return None
        matches = profiles_by_clickup_user.get(clickup_user_id, [])
        if len(matches) != 1:
            return None
        return matches[0]

    def _resolve_scope(
        self,
        *,
        list_id: str | None,
        space_id: str | None,
        scopes_by_list_id: dict[str, list[_MappedScope]],
        scopes_by_space_id: dict[str, list[_MappedScope]],
    ) -> _MappedScope | None:
        if list_id:
            resolved = self._collapse_scopes(scopes_by_list_id.get(list_id, []))
            if resolved:
                return resolved
        if not space_id:
            return None
        return self._collapse_scopes(scopes_by_space_id.get(space_id, []))

    def _collapse_scopes(self, scopes: list[_MappedScope]) -> _MappedScope | None:
        if not scopes:
            return None

        unique_scopes = {
            (scope.client_id, scope.client_name, scope.brand_id, scope.brand_name): scope
            for scope in scopes
        }
        deduped = list(unique_scopes.values())
        if len(deduped) == 1:
            return deduped[0]

        client_ids = {scope.client_id for scope in deduped}
        if len(client_ids) == 1:
            first = deduped[0]
            return _MappedScope(
                client_id=first.client_id,
                client_name=first.client_name,
                brand_id=None,
                brand_name=None,
            )

        return None

    def _profile_name(self, profile: dict[str, Any]) -> str | None:
        return (
            _as_str(profile.get("display_name"))
            or _as_str(profile.get("full_name"))
            or _as_str(profile.get("email"))
        )

    def _build_response(
        self,
        rows: list[dict[str, Any]],
        *,
        start_date_ms: int,
        end_date_ms: int,
    ) -> dict[str, Any]:
        total_duration_ms = sum(row["duration_ms"] for row in rows)
        mapped_duration_ms = sum(row["duration_ms"] for row in rows if row["space_mapped"])
        unattributed_duration_ms = sum(
            row["duration_ms"]
            for row in rows
            if not row["client_id"]
        )
        running_entries = sum(1 for row in rows if row["is_running"])

        by_member: dict[str, dict[str, Any]] = {}
        by_client_totals: dict[str, dict[str, Any]] = {}
        by_space_totals: dict[str, dict[str, Any]] = {}
        unmapped_user_totals: dict[str, dict[str, Any]] = {}
        unmapped_space_totals: dict[str, dict[str, Any]] = {}

        for row in rows:
            member_key = (
                f"profile:{row['team_member_profile_id']}"
                if row["team_member_profile_id"]
                else f"clickup:{row['clickup_user_id'] or 'unknown'}"
            )
            member = by_member.setdefault(
                member_key,
                {
                    "clickup_user_id": row["clickup_user_id"],
                    "team_member_profile_id": row["team_member_profile_id"],
                    "team_member_name": row["team_member_name"]
                    or row["clickup_username"]
                    or "Unlinked ClickUp User",
                    "team_member_email": row["team_member_email"] or row["clickup_user_email"],
                    "mapped": bool(row["team_member_mapped"]),
                    "total_duration_ms": 0,
                    "mapped_duration_ms": 0,
                    "unmapped_duration_ms": 0,
                    "clients": {},
                },
            )
            member["total_duration_ms"] += row["duration_ms"]
            if row["client_id"]:
                member["mapped_duration_ms"] += row["duration_ms"]
            else:
                member["unmapped_duration_ms"] += row["duration_ms"]

            client_key = "|".join(
                [
                    row["client_id"] or "unmapped-client",
                    row["brand_id"] or "unmapped-brand",
                    row["space_id"] or "unmapped-space",
                    row["list_id"] or "unmapped-list",
                ]
            )
            client_bucket = member["clients"].setdefault(
                client_key,
                {
                    "client_id": row["client_id"],
                    "client_name": row["client_name"] or "Unlinked Space",
                    "brand_id": row["brand_id"],
                    "brand_name": row["brand_name"],
                    "space_id": row["space_id"],
                    "space_name": row["space_name"],
                    "list_id": row["list_id"],
                    "list_name": row["list_name"],
                    "mapped": bool(row["space_mapped"]),
                    "duration_ms": 0,
                },
            )
            client_bucket["duration_ms"] += row["duration_ms"]

            client_summary_key = "|".join(
                [
                    row["client_id"] or "unmapped-client",
                    row["brand_id"] or "unmapped-brand",
                ]
            )
            client_summary = by_client_totals.setdefault(
                client_summary_key,
                {
                    "client_id": row["client_id"],
                    "client_name": row["client_name"] or "Unlinked Space",
                    "brand_id": row["brand_id"],
                    "brand_name": row["brand_name"],
                    "mapped": bool(row["space_mapped"]),
                    "duration_ms": 0,
                    "entry_count": 0,
                    "team_member_ids": set(),
                    "space_keys": set(),
                },
            )
            client_summary["duration_ms"] += row["duration_ms"]
            client_summary["entry_count"] += 1
            client_summary["team_member_ids"].add(
                row["team_member_profile_id"]
                or row["clickup_user_id"]
                or row["clickup_username"]
                or "unknown"
            )
            client_summary["space_keys"].add(
                row["space_id"] or row["list_id"] or row["task_id"] or "unknown"
            )

            space_summary_key = "|".join(
                [
                    row["space_id"] or "unmapped-space",
                    row["list_id"] or "unmapped-list",
                ]
            )
            space_summary = by_space_totals.setdefault(
                space_summary_key,
                {
                    "space_id": row["space_id"],
                    "space_name": row["space_name"] or "Unlinked Space",
                    "list_id": row["list_id"],
                    "list_name": row["list_name"],
                    "client_id": row["client_id"],
                    "client_name": row["client_name"],
                    "brand_id": row["brand_id"],
                    "brand_name": row["brand_name"],
                    "mapped": bool(row["space_mapped"]),
                    "duration_ms": 0,
                    "entry_count": 0,
                    "team_member_ids": set(),
                },
            )
            space_summary["duration_ms"] += row["duration_ms"]
            space_summary["entry_count"] += 1
            space_summary["team_member_ids"].add(
                row["team_member_profile_id"]
                or row["clickup_user_id"]
                or row["clickup_username"]
                or "unknown"
            )

            if not row["team_member_mapped"]:
                unmapped_user_key = row["clickup_user_id"] or "unknown"
                unmapped_user = unmapped_user_totals.setdefault(
                    unmapped_user_key,
                    {
                        "clickup_user_id": row["clickup_user_id"],
                        "clickup_username": row["clickup_username"],
                        "clickup_user_email": row["clickup_user_email"],
                        "duration_ms": 0,
                    },
                )
                unmapped_user["duration_ms"] += row["duration_ms"]

            if not row["space_mapped"]:
                unmapped_space_key = (
                    row["space_id"]
                    or row["list_id"]
                    or row["task_id"]
                    or "no-location"
                )
                unmapped_space = unmapped_space_totals.setdefault(
                    unmapped_space_key,
                    {
                        "space_id": row["space_id"],
                        "space_name": row["space_name"],
                        "list_id": row["list_id"],
                        "list_name": row["list_name"],
                        "duration_ms": 0,
                    },
                )
                unmapped_space["duration_ms"] += row["duration_ms"]

        by_team_member = []
        for member in by_member.values():
            clients = []
            for bucket in member["clients"].values():
                clients.append(
                    {
                        "client_id": bucket["client_id"],
                        "client_name": bucket["client_name"],
                        "brand_id": bucket["brand_id"],
                        "brand_name": bucket["brand_name"],
                        "space_id": bucket["space_id"],
                        "space_name": bucket["space_name"],
                        "list_id": bucket["list_id"],
                        "list_name": bucket["list_name"],
                        "mapped": bucket["mapped"],
                        "total_hours": _hours(bucket["duration_ms"]),
                    }
                )
            clients.sort(
                key=lambda item: (
                    -item["total_hours"],
                    str(item["client_name"] or ""),
                    str(item["brand_name"] or ""),
                    str(item["space_name"] or ""),
                )
            )
            by_team_member.append(
                {
                    "clickup_user_id": member["clickup_user_id"],
                    "team_member_profile_id": member["team_member_profile_id"],
                    "team_member_name": member["team_member_name"],
                    "team_member_email": member["team_member_email"],
                    "mapped": member["mapped"],
                    "total_hours": _hours(member["total_duration_ms"]),
                    "mapped_hours": _hours(member["mapped_duration_ms"]),
                    "unmapped_hours": _hours(member["unmapped_duration_ms"]),
                    "clients": clients,
                }
            )

        by_team_member.sort(
            key=lambda item: (-item["total_hours"], str(item["team_member_name"] or ""))
        )

        by_client = [
            {
                "client_id": row["client_id"],
                "client_name": row["client_name"],
                "brand_id": row["brand_id"],
                "brand_name": row["brand_name"],
                "mapped": row["mapped"],
                "team_member_count": len(row["team_member_ids"]),
                "space_count": len(row["space_keys"]),
                "entry_count": row["entry_count"],
                "total_hours": _hours(row["duration_ms"]),
            }
            for row in by_client_totals.values()
        ]
        by_client.sort(
            key=lambda item: (
                -item["total_hours"],
                str(item["client_name"] or ""),
                str(item["brand_name"] or ""),
            )
        )

        by_space = [
            {
                "space_id": row["space_id"],
                "space_name": row["space_name"],
                "list_id": row["list_id"],
                "list_name": row["list_name"],
                "client_id": row["client_id"],
                "client_name": row["client_name"] or "Unlinked Space",
                "brand_id": row["brand_id"],
                "brand_name": row["brand_name"],
                "mapped": row["mapped"],
                "team_member_count": len(row["team_member_ids"]),
                "entry_count": row["entry_count"],
                "total_hours": _hours(row["duration_ms"]),
            }
            for row in by_space_totals.values()
        ]
        by_space.sort(
            key=lambda item: (
                -item["total_hours"],
                str(item["space_name"] or ""),
                str(item["list_name"] or ""),
            )
        )

        unmapped_users = [
            {
                "clickup_user_id": row["clickup_user_id"],
                "clickup_username": row["clickup_username"],
                "clickup_user_email": row["clickup_user_email"],
                "total_hours": _hours(row["duration_ms"]),
            }
            for row in unmapped_user_totals.values()
        ]
        unmapped_users.sort(key=lambda item: (-item["total_hours"], str(item["clickup_username"] or "")))

        unmapped_spaces = [
            {
                "space_id": row["space_id"],
                "space_name": row["space_name"] or "Unlinked Space",
                "list_id": row["list_id"],
                "list_name": row["list_name"],
                "total_hours": _hours(row["duration_ms"]),
            }
            for row in unmapped_space_totals.values()
        ]
        unmapped_spaces.sort(key=lambda item: (-item["total_hours"], str(item["space_name"] or "")))

        return {
            "date_range": {
                "start_date_ms": start_date_ms,
                "end_date_ms": end_date_ms,
            },
            "summary": {
                "total_hours": _hours(total_duration_ms),
                "mapped_hours": _hours(mapped_duration_ms),
                "unmapped_hours": _hours(total_duration_ms - mapped_duration_ms),
                "unattributed_hours": _hours(unattributed_duration_ms),
                "unique_users": len(by_team_member),
                "entry_count": len(rows),
                "running_entries": running_entries,
            },
            "by_team_member": by_team_member,
            "by_client": by_client,
            "by_space": by_space,
            "unmapped_users": unmapped_users,
            "unmapped_spaces": unmapped_spaces,
        }
