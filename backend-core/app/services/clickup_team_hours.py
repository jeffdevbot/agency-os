from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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


def _safe_zoneinfo(timezone_name: str | None) -> ZoneInfo | None:
    if not timezone_name:
        return None
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return None


def _day_key_from_ms(value: int | None, *, fallback_ms: int, timezone_name: str | None = None) -> str:
    candidate_ms = value if value and value > 0 else fallback_ms
    zone = _safe_zoneinfo(timezone_name) or UTC
    return datetime.fromtimestamp(candidate_ms / 1000, tz=UTC).astimezone(zone).strftime("%Y-%m-%d")


def _day_keys_in_range(
    start_date_ms: int,
    end_date_ms: int,
    *,
    timezone_name: str | None = None,
) -> list[str]:
    zone = _safe_zoneinfo(timezone_name) or UTC
    start_day = datetime.fromtimestamp(start_date_ms / 1000, tz=UTC).astimezone(zone).date()
    end_day = datetime.fromtimestamp(end_date_ms / 1000, tz=UTC).astimezone(zone).date()
    days: list[str] = []
    current = start_day
    while current <= end_day:
        days.append(current.isoformat())
        current += timedelta(days=1)
    return days


def _continuous_day_keys(values: set[str]) -> list[str]:
    if not values:
        return []
    parsed = sorted(date.fromisoformat(value) for value in values)
    days: list[str] = []
    current = parsed[0]
    end = parsed[-1]
    while current <= end:
        days.append(current.isoformat())
        current += timedelta(days=1)
    return days


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

        mappings = self._load_mappings(workspace)
        normalized = [self._normalize_entry(row, mappings, fallback_day_ms=start_date_ms) for row in entries]
        return self._build_response(
            normalized,
            mappings=mappings,
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

    def _workspace_timezones(self, workspace: dict[str, Any]) -> dict[str, str]:
        timezone_by_clickup_user: dict[str, str] = {}
        for member in workspace.get("members") or []:
            if not isinstance(member, dict):
                continue
            user = member.get("user")
            if not isinstance(user, dict):
                continue
            user_id = _as_str(user.get("id"))
            timezone_name = _as_str(user.get("timezone"))
            if user_id and _safe_zoneinfo(timezone_name):
                timezone_by_clickup_user[user_id] = timezone_name  # type: ignore[assignment]
        return timezone_by_clickup_user

    def _load_mappings(self, workspace: dict[str, Any]) -> dict[str, Any]:
        profiles_resp = (
            self.db.table("profiles")
            .select("id, email, display_name, full_name, clickup_user_id, employment_status")
            .execute()
        )
        brands_resp = (
            self.db.table("brands")
            .select("id, client_id, name, clickup_space_id, clickup_list_id")
            .execute()
        )
        clients_resp = self.db.table("agency_clients").select("id, name, status").execute()

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

        profile_link_status_by_id: dict[str, str] = {}
        for row in profiles:
            if not isinstance(row, dict):
                continue
            profile_id = _as_str(row.get("id"))
            if not profile_id:
                continue
            clickup_user_id = _as_str(row.get("clickup_user_id"))
            if not clickup_user_id:
                profile_link_status_by_id[profile_id] = "unlinked"
            elif len(profiles_by_clickup_user.get(clickup_user_id, [])) == 1:
                profile_link_status_by_id[profile_id] = "linked"
            else:
                profile_link_status_by_id[profile_id] = "ambiguous"

        scopes_by_list_id: dict[str, list[_MappedScope]] = defaultdict(list)
        scopes_by_space_id: dict[str, list[_MappedScope]] = defaultdict(list)
        brand_count_by_client_id: dict[str, int] = defaultdict(int)
        for row in brands:
            if not isinstance(row, dict):
                continue
            brand_id = _as_str(row.get("id"))
            client_id = _as_str(row.get("client_id"))
            brand_name = str(row.get("name") or "").strip()
            if not brand_id or not client_id or not brand_name:
                continue
            brand_count_by_client_id[client_id] += 1
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
            "profiles": [row for row in profiles if isinstance(row, dict)],
            "clients": [row for row in clients if isinstance(row, dict)],
            "profiles_by_clickup_user": profiles_by_clickup_user,
            "profile_link_status_by_id": profile_link_status_by_id,
            "timezone_by_clickup_user": self._workspace_timezones(workspace),
            "scopes_by_list_id": scopes_by_list_id,
            "scopes_by_space_id": scopes_by_space_id,
            "brand_count_by_client_id": brand_count_by_client_id,
        }

    def _normalize_entry(
        self,
        row: dict[str, Any],
        mappings: dict[str, Any],
        *,
        fallback_day_ms: int,
    ) -> dict[str, Any]:
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
        start_ms = _safe_int(row.get("start"))
        timezone_name = mappings["timezone_by_clickup_user"].get(clickup_user_id) if clickup_user_id else None

        return {
            "time_entry_id": _as_str(row.get("id")),
            "workspace_id": _as_str(row.get("wid")),
            "clickup_user_id": clickup_user_id,
            "clickup_username": _as_str(user.get("username")),
            "clickup_user_email": _as_str(user.get("email")),
            "team_member_profile_id": profile.get("id") if profile else None,
            "team_member_name": self._profile_name(profile) if profile else None,
            "team_member_email": _as_str(profile.get("email")) if profile else None,
            "team_member_link_status": (
                mappings["profile_link_status_by_id"].get(str(profile.get("id")))
                if profile and _as_str(profile.get("id"))
                else "unlinked"
            ),
            "billable": bool(row.get("billable")) if row.get("billable") is not None else None,
            "start_ms": start_ms,
            "end_ms": _safe_int(row.get("end")),
            "timezone_name": timezone_name,
            "day_key": _day_key_from_ms(start_ms, fallback_ms=fallback_day_ms, timezone_name=timezone_name),
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

    def _build_team_entity(
        self,
        profile: dict[str, Any],
        link_status: str,
        timezone_name: str | None,
    ) -> dict[str, Any]:
        profile_id = _as_str(profile.get("id")) or "unknown-profile"
        return {
            "entity_id": f"profile:{profile_id}",
            "team_member_profile_id": profile_id,
            "clickup_user_id": _as_str(profile.get("clickup_user_id")),
            "team_member_name": self._profile_name(profile) or "Unnamed team member",
            "team_member_email": _as_str(profile.get("email")),
            "employment_status": _as_str(profile.get("employment_status")) or "active",
            "link_status": link_status,
            "timezone_name": timezone_name,
            "total_duration_ms": 0,
            "mapped_duration_ms": 0,
            "unmapped_duration_ms": 0,
            "entry_count": 0,
            "days": set(),
            "boundary_days": set(),
            "series": {},
            "daily": {},
        }

    def _build_clickup_only_entity(self, row: dict[str, Any]) -> dict[str, Any]:
        clickup_user_id = row["clickup_user_id"] or "unknown"
        return {
            "entity_id": f"clickup:{clickup_user_id}",
            "team_member_profile_id": None,
            "clickup_user_id": row["clickup_user_id"],
            "team_member_name": row["clickup_username"] or "Unlinked ClickUp User",
            "team_member_email": row["clickup_user_email"],
            "employment_status": "unknown",
            "link_status": "unlinked",
            "timezone_name": row["timezone_name"],
            "total_duration_ms": 0,
            "mapped_duration_ms": 0,
            "unmapped_duration_ms": 0,
            "entry_count": 0,
            "days": set(),
            "boundary_days": set(),
            "series": {},
            "daily": {},
        }

    def _build_client_entity(self, client: dict[str, Any], brand_count: int) -> dict[str, Any]:
        client_id = _as_str(client.get("id")) or "unknown-client"
        return {
            "entity_id": f"client:{client_id}",
            "client_id": client_id,
            "client_name": _as_str(client.get("name")) or "Unknown client",
            "status": _as_str(client.get("status")) or "active",
            "brand_count": brand_count,
            "timezone_name": None,
            "boundary_days": set(),
            "total_duration_ms": 0,
            "entry_count": 0,
            "days": set(),
            "series": {},
            "daily": {},
        }

    def _upsert_daily_segment(
        self,
        entity: dict[str, Any],
        *,
        day_key: str,
        segment_key: str,
        duration_ms: int,
        segment_factory: callable,
    ) -> None:
        if duration_ms <= 0:
            return
        day = entity["daily"].setdefault(
            day_key,
            {"date": day_key, "total_duration_ms": 0, "segments": {}},
        )
        day["total_duration_ms"] += duration_ms
        segment = day["segments"].setdefault(segment_key, segment_factory())
        segment["duration_ms"] += duration_ms

    def _finalize_daily(self, daily_map: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for day_key in sorted(daily_map.keys()):
            day = daily_map[day_key]
            segments = [
                {**segment, "hours": _hours(segment["duration_ms"])}
                for segment in day["segments"].values()
            ]
            segments.sort(key=lambda item: (-item["hours"], str(item["label"])))
            rows.append(
                {
                    "date": day_key,
                    "total_hours": _hours(day["total_duration_ms"]),
                    "segments": segments,
                }
            )
        return rows

    def _entity_day_range(
        self,
        *,
        start_date_ms: int,
        end_date_ms: int,
        timezone_name: str | None,
        observed_days: set[str],
        boundary_days: set[str],
    ) -> list[str]:
        if timezone_name:
            base_days = set(
                _day_keys_in_range(
                    start_date_ms,
                    end_date_ms,
                    timezone_name=timezone_name,
                )
            )
        else:
            base_days = set(_day_keys_in_range(start_date_ms, end_date_ms))
        return _continuous_day_keys(base_days | observed_days | boundary_days)

    def _build_response(
        self,
        rows: list[dict[str, Any]],
        *,
        mappings: dict[str, Any],
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

        day_keys = _day_keys_in_range(start_date_ms, end_date_ms)

        team_entities: dict[str, dict[str, Any]] = {}
        for profile in mappings["profiles"]:
            profile_id = _as_str(profile.get("id"))
            if not profile_id:
                continue
            clickup_user_id = _as_str(profile.get("clickup_user_id"))
            team_entities[f"profile:{profile_id}"] = self._build_team_entity(
                profile,
                mappings["profile_link_status_by_id"].get(profile_id, "unlinked"),
                mappings["timezone_by_clickup_user"].get(clickup_user_id) if clickup_user_id else None,
            )

        client_entities: dict[str, dict[str, Any]] = {}
        for client in mappings["clients"]:
            client_id = _as_str(client.get("id"))
            if not client_id:
                continue
            client_entities[f"client:{client_id}"] = self._build_client_entity(
                client,
                mappings["brand_count_by_client_id"].get(client_id, 0),
            )

        unmapped_user_totals: dict[str, dict[str, Any]] = {}
        unmapped_space_totals: dict[str, dict[str, Any]] = {}

        for row in rows:
            member_key = (
                f"profile:{row['team_member_profile_id']}"
                if row["team_member_profile_id"]
                else f"clickup:{row['clickup_user_id'] or 'unknown'}"
            )
            member = team_entities.setdefault(
                member_key,
                self._build_clickup_only_entity(row),
            )
            member["total_duration_ms"] += row["duration_ms"]
            member["entry_count"] += 1
            if row["duration_ms"] > 0:
                member["days"].add(row["day_key"])
            if row["timezone_name"]:
                member["timezone_name"] = row["timezone_name"]
            if row["client_id"]:
                member["mapped_duration_ms"] += row["duration_ms"]
            else:
                member["unmapped_duration_ms"] += row["duration_ms"]
            member["boundary_days"].update(
                _day_keys_in_range(
                    start_date_ms,
                    end_date_ms,
                    timezone_name=member["timezone_name"],
                )
            )

            member_series_key = "|".join(
                [
                    row["client_id"] or "unmapped-client",
                    row["brand_id"] or "no-brand",
                    row["space_id"] or "no-space",
                    row["list_id"] or "no-list",
                ]
            )
            member_series = member["series"].setdefault(
                member_series_key,
                {
                    "key": member_series_key,
                    "label": (
                        f"{row['client_name']} • {row['brand_name']}"
                        if row["client_name"] and row["brand_name"]
                        else row["client_name"]
                        or row["space_name"]
                        or row["list_name"]
                        or "Unlinked Space"
                    ),
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
            member_series["duration_ms"] += row["duration_ms"]
            self._upsert_daily_segment(
                member,
                day_key=row["day_key"],
                segment_key=member_series_key,
                duration_ms=row["duration_ms"],
                segment_factory=lambda: {
                    "key": member_series_key,
                    "label": member_series["label"],
                    "client_id": member_series["client_id"],
                    "client_name": member_series["client_name"],
                    "brand_id": member_series["brand_id"],
                    "brand_name": member_series["brand_name"],
                    "mapped": member_series["mapped"],
                    "duration_ms": 0,
                },
            )

            if row["client_id"]:
                client_key = f"client:{row['client_id']}"
                client = client_entities.get(client_key)
                if client:
                    client["total_duration_ms"] += row["duration_ms"]
                    client["entry_count"] += 1
                    if row["duration_ms"] > 0:
                        client["days"].add(row["day_key"])
                    if client["timezone_name"] in (None, row["timezone_name"]):
                        client["timezone_name"] = row["timezone_name"]
                    else:
                        client["timezone_name"] = "mixed"
                    client["boundary_days"].add(
                        _day_key_from_ms(
                            start_date_ms,
                            fallback_ms=start_date_ms,
                            timezone_name=row["timezone_name"],
                        )
                    )
                    client["boundary_days"].add(
                        _day_key_from_ms(
                            end_date_ms,
                            fallback_ms=end_date_ms,
                            timezone_name=row["timezone_name"],
                        )
                    )

                    client_series_key = "|".join(
                        [
                            row["team_member_profile_id"] or "no-profile",
                            row["clickup_user_id"] or "no-clickup",
                            row["brand_id"] or "no-brand",
                        ]
                    )
                    client_series = client["series"].setdefault(
                        client_series_key,
                        {
                            "key": client_series_key,
                            "label": (
                                f"{member['team_member_name']} • {row['brand_name']}"
                                if row["brand_name"]
                                else member["team_member_name"]
                            ),
                            "team_member_profile_id": member["team_member_profile_id"],
                            "team_member_name": member["team_member_name"],
                            "team_member_email": member["team_member_email"],
                            "clickup_user_id": member["clickup_user_id"],
                            "brand_id": row["brand_id"],
                            "brand_name": row["brand_name"],
                            "duration_ms": 0,
                        },
                    )
                    client_series["duration_ms"] += row["duration_ms"]
                    self._upsert_daily_segment(
                        client,
                        day_key=row["day_key"],
                        segment_key=client_series_key,
                        duration_ms=row["duration_ms"],
                        segment_factory=lambda: {
                            "key": client_series_key,
                            "label": client_series["label"],
                            "team_member_profile_id": client_series["team_member_profile_id"],
                            "team_member_name": client_series["team_member_name"],
                            "team_member_email": client_series["team_member_email"],
                            "clickup_user_id": client_series["clickup_user_id"],
                            "brand_id": client_series["brand_id"],
                            "brand_name": client_series["brand_name"],
                            "duration_ms": 0,
                        },
                    )

            if row["team_member_link_status"] != "linked":
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

        team_members = []
        for entity in team_entities.values():
            series = [
                {**series_row, "total_hours": _hours(series_row["duration_ms"])}
                for series_row in entity["series"].values()
            ]
            series.sort(key=lambda item: (-item["total_hours"], str(item["label"])))
            team_members.append(
                {
                    "entity_id": entity["entity_id"],
                    "team_member_profile_id": entity["team_member_profile_id"],
                    "clickup_user_id": entity["clickup_user_id"],
                    "team_member_name": entity["team_member_name"],
                    "team_member_email": entity["team_member_email"],
                    "employment_status": entity["employment_status"],
                    "link_status": entity["link_status"],
                    "timezone_name": entity["timezone_name"],
                    "total_hours": _hours(entity["total_duration_ms"]),
                    "mapped_hours": _hours(entity["mapped_duration_ms"]),
                    "unmapped_hours": _hours(entity["unmapped_duration_ms"]),
                    "entry_count": entity["entry_count"],
                    "active_day_count": len(entity["days"]),
                    "day_range": self._entity_day_range(
                        start_date_ms=start_date_ms,
                        end_date_ms=end_date_ms,
                        timezone_name=entity["timezone_name"],
                        observed_days=entity["days"],
                        boundary_days=entity["boundary_days"],
                    ),
                    "series": series,
                    "daily": self._finalize_daily(entity["daily"]),
                }
            )
        team_members.sort(
            key=lambda item: (-item["total_hours"], str(item["team_member_name"]).lower())
        )

        clients = []
        for entity in client_entities.values():
            series = [
                {**series_row, "total_hours": _hours(series_row["duration_ms"])}
                for series_row in entity["series"].values()
            ]
            series.sort(key=lambda item: (-item["total_hours"], str(item["label"])))
            clients.append(
                {
                    "entity_id": entity["entity_id"],
                    "client_id": entity["client_id"],
                    "client_name": entity["client_name"],
                    "status": entity["status"],
                    "brand_count": entity["brand_count"],
                    "timezone_name": entity["timezone_name"],
                    "total_hours": _hours(entity["total_duration_ms"]),
                    "entry_count": entity["entry_count"],
                    "active_day_count": len(entity["days"]),
                    "day_range": self._entity_day_range(
                        start_date_ms=start_date_ms,
                        end_date_ms=end_date_ms,
                        timezone_name=entity["timezone_name"] if entity["timezone_name"] != "mixed" else None,
                        observed_days=entity["days"],
                        boundary_days=entity["boundary_days"],
                    ),
                    "series": series,
                    "daily": self._finalize_daily(entity["daily"]),
                }
            )
        clients.sort(key=lambda item: (-item["total_hours"], str(item["client_name"]).lower()))

        unique_users = len(
            {
                row["clickup_user_id"] or row["clickup_username"] or row["clickup_user_email"] or "unknown"
                for row in rows
            }
        )

        return {
            "date_range": {
                "start_date_ms": start_date_ms,
                "end_date_ms": end_date_ms,
                "days": day_keys,
            },
            "summary": {
                "total_hours": _hours(total_duration_ms),
                "mapped_hours": _hours(mapped_duration_ms),
                "unmapped_hours": _hours(total_duration_ms - mapped_duration_ms),
                "unattributed_hours": _hours(unattributed_duration_ms),
                "unique_users": unique_users,
                "entry_count": len(rows),
                "running_entries": running_entries,
                "team_member_count": len(team_members),
                "team_members_with_hours": sum(1 for item in team_members if item["total_hours"] > 0),
                "client_count": len(clients),
                "clients_with_hours": sum(1 for item in clients if item["total_hours"] > 0),
            },
            "team_members": team_members,
            "clients": clients,
            "unmapped_users": [
                {
                    "clickup_user_id": row["clickup_user_id"],
                    "clickup_username": row["clickup_username"],
                    "clickup_user_email": row["clickup_user_email"],
                    "total_hours": _hours(row["duration_ms"]),
                }
                for row in sorted(
                    unmapped_user_totals.values(),
                    key=lambda item: (
                        -_hours(item["duration_ms"]),
                        str(item["clickup_username"] or item["clickup_user_email"] or ""),
                    ),
                )
            ],
            "unmapped_spaces": [
                {
                    "space_id": row["space_id"],
                    "space_name": row["space_name"] or "Unlinked Space",
                    "list_id": row["list_id"],
                    "list_name": row["list_name"],
                    "total_hours": _hours(row["duration_ms"]),
                }
                for row in sorted(
                    unmapped_space_totals.values(),
                    key=lambda item: (
                        -_hours(item["duration_ms"]),
                        str(item["space_name"] or item["space_id"] or ""),
                    ),
                )
            ],
        }
