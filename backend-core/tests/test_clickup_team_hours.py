from __future__ import annotations

import pytest

from app.services.clickup import ClickUpConfigurationError
from app.services.clickup_team_hours import ClickUpTeamHoursService


class _FakeClickUp:
    def __init__(self, *, team_id: str, teams: list[dict], entries: list[dict]):
        self.team_id = team_id
        self._teams = teams
        self._entries = entries
        self.calls: list[dict] = []

    async def get_authorized_workspaces(self) -> list[dict]:
        return self._teams

    async def get_time_entries(self, **kwargs):
        self.calls.append(kwargs)
        return self._entries


class _FakeSupabase:
    def __init__(self, tables: dict[str, list[dict]]):
        self.tables = {name: list(rows) for name, rows in tables.items()}

    def table(self, name: str):
        return _FakeTable(self, name)


class _FakeTable:
    def __init__(self, db: _FakeSupabase, name: str):
        self._db = db
        self._name = name

    def select(self, *_args, **_kwargs):
        return self

    def execute(self):
        return type("Resp", (), {"data": [dict(row) for row in self._db.tables.get(self._name, [])]})()


@pytest.mark.asyncio
async def test_build_report_returns_full_roster_and_daily_series():
    clickup = _FakeClickUp(
        team_id="team-1",
        teams=[
            {
                "id": "team-1",
                "members": [
                    {"user": {"id": 101, "username": "Alice CU", "email": "alice@clickup.test", "timezone": "Asia/Kolkata"}},
                    {"user": {"id": 202, "username": "Bob CU", "email": "bob@clickup.test", "timezone": "Asia/Karachi"}},
                    {"user": {"id": 303, "username": "Carol CU", "email": "carol@clickup.test", "timezone": "Asia/Manila"}},
                ],
            }
        ],
        entries=[
            {
                "id": "te-1",
                "wid": "team-1",
                "user": {"id": 101, "username": "Alice CU", "email": "alice@clickup.test"},
                "duration": "7200000",
                "start": "1700000000000",
                "end": "1700007200000",
                "task": {"id": "task-1", "name": "Mapped by list"},
                "task_location": {
                    "space_id": "space-a",
                    "space_name": "Alpha Space",
                    "list_id": "list-a",
                    "list_name": "Alpha List",
                },
            },
            {
                "id": "te-2",
                "wid": "team-1",
                "user": {"id": 101, "username": "Alice CU", "email": "alice@clickup.test"},
                "duration": "3600000",
                "start": "1700086400000",
                "end": "1700090000000",
                "task": {"id": "task-2", "name": "Mapped by unique space"},
                "task_location": {
                    "space_id": "space-b",
                    "space_name": "Beta Space",
                    "list_id": "unknown-list",
                    "list_name": "Unknown List",
                },
            },
            {
                "id": "te-3",
                "wid": "team-1",
                "user": {"id": 202, "username": "Bob CU", "email": "bob@clickup.test"},
                "duration": "1800000",
                "start": "1700000000000",
                "end": "1700001800000",
                "task": {"id": "task-3", "name": "Shared client"},
                "task_location": {
                    "space_id": "space-shared",
                    "space_name": "Shared Space",
                    "list_id": "shared-list",
                    "list_name": "Shared List",
                },
            },
        ],
    )
    db = _FakeSupabase(
        {
            "profiles": [
                {
                    "id": "profile-1",
                    "email": "alice@agency.test",
                    "display_name": "Alice",
                    "full_name": "Alice Agency",
                    "clickup_user_id": "101",
                    "employment_status": "active",
                },
                {
                    "id": "profile-2",
                    "email": "zoe@agency.test",
                    "display_name": "Zoe",
                    "full_name": "Zoe Agency",
                    "clickup_user_id": None,
                    "employment_status": "active",
                },
                {
                    "id": "profile-dup-1",
                    "email": "bob-1@agency.test",
                    "display_name": "Bob One",
                    "full_name": "Bob One",
                    "clickup_user_id": "202",
                    "employment_status": "active",
                },
                {
                    "id": "profile-dup-2",
                    "email": "bob-2@agency.test",
                    "display_name": "Bob Two",
                    "full_name": "Bob Two",
                    "clickup_user_id": "202",
                    "employment_status": "active",
                },
            ],
            "agency_clients": [
                {"id": "client-a", "name": "Alpha Client", "status": "active"},
                {"id": "client-b", "name": "Beta Client", "status": "active"},
                {"id": "client-c", "name": "Gamma Client", "status": "active"},
                {"id": "client-z", "name": "Zero Client", "status": "inactive"},
            ],
            "brands": [
                {
                    "id": "brand-a",
                    "client_id": "client-a",
                    "name": "Alpha Brand",
                    "clickup_space_id": "space-a",
                    "clickup_list_id": "list-a",
                },
                {
                    "id": "brand-b",
                    "client_id": "client-b",
                    "name": "Beta Brand",
                    "clickup_space_id": "space-b",
                    "clickup_list_id": None,
                },
                {
                    "id": "brand-c1",
                    "client_id": "client-c",
                    "name": "Gamma Brand 1",
                    "clickup_space_id": "space-shared",
                    "clickup_list_id": "shared-list",
                },
                {
                    "id": "brand-c2",
                    "client_id": "client-c",
                    "name": "Gamma Brand 2",
                    "clickup_space_id": "space-shared",
                    "clickup_list_id": "shared-list",
                },
            ],
        }
    )

    service = ClickUpTeamHoursService(db, clickup)
    result = await service.build_report_async(
        start_date_ms=1700000000000,
        end_date_ms=1700086400000,
    )

    assert clickup.calls == [
        {
            "start_date": 1700000000000,
            "end_date": 1700086400000,
            "assignee_ids": ["101", "202", "303"],
            "include_task_tags": True,
            "include_location_names": True,
        }
    ]

    assert result["date_range"]["days"] == ["2023-11-14", "2023-11-15"]
    assert result["summary"] == {
        "total_hours": 3.5,
        "mapped_hours": 3.5,
        "unmapped_hours": 0.0,
        "unattributed_hours": 0.0,
        "unique_users": 2,
        "entry_count": 3,
        "running_entries": 0,
        "team_member_count": 5,
        "team_members_with_hours": 2,
        "client_count": 4,
        "clients_with_hours": 3,
    }

    assert [member["team_member_name"] for member in result["team_members"]] == [
        "Alice",
        "Bob CU",
        "Bob One",
        "Bob Two",
        "Zoe",
    ]

    alice = result["team_members"][0]
    assert alice["link_status"] == "linked"
    assert alice["timezone_name"] == "Asia/Kolkata"
    assert alice["day_range"] == ["2023-11-15", "2023-11-16"]
    assert alice["total_hours"] == 3.0
    assert [series["label"] for series in alice["series"]] == [
        "Alpha Client • Alpha Brand",
        "Beta Client • Beta Brand",
    ]
    assert alice["daily"] == [
        {
            "date": "2023-11-15",
            "total_hours": 2.0,
            "segments": [
                {
                    "key": "client-a|brand-a|space-a|list-a",
                    "label": "Alpha Client • Alpha Brand",
                    "client_id": "client-a",
                    "client_name": "Alpha Client",
                    "brand_id": "brand-a",
                    "brand_name": "Alpha Brand",
                    "mapped": True,
                    "hours": 2.0,
                    "duration_ms": 7200000,
                }
            ],
        },
        {
            "date": "2023-11-16",
            "total_hours": 1.0,
            "segments": [
                {
                    "key": "client-b|brand-b|space-b|unknown-list",
                    "label": "Beta Client • Beta Brand",
                    "client_id": "client-b",
                    "client_name": "Beta Client",
                    "brand_id": "brand-b",
                    "brand_name": "Beta Brand",
                    "mapped": True,
                    "hours": 1.0,
                    "duration_ms": 3600000,
                }
            ],
        },
    ]

    bob_clickup = result["team_members"][1]
    assert bob_clickup["team_member_profile_id"] is None
    assert bob_clickup["clickup_user_id"] == "202"
    assert bob_clickup["link_status"] == "unlinked"
    assert bob_clickup["timezone_name"] == "Asia/Karachi"
    assert bob_clickup["day_range"] == ["2023-11-15", "2023-11-16"]
    assert bob_clickup["series"][0]["label"] == "Gamma Client"
    assert bob_clickup["daily"][0]["date"] == "2023-11-15"

    zero_member = result["team_members"][-1]
    assert zero_member["team_member_name"] == "Zoe"
    assert zero_member["total_hours"] == 0.0
    assert zero_member["timezone_name"] is None
    assert zero_member["day_range"] == ["2023-11-14", "2023-11-15"]
    assert zero_member["daily"] == []

    assert [client["client_name"] for client in result["clients"]] == [
        "Alpha Client",
        "Beta Client",
        "Gamma Client",
        "Zero Client",
    ]
    gamma = result["clients"][2]
    assert gamma["timezone_name"] == "Asia/Karachi"
    assert gamma["day_range"] == ["2023-11-15", "2023-11-16"]
    assert gamma["series"][0]["label"] == "Bob CU"
    assert gamma["daily"][0]["segments"][0]["brand_name"] is None

    assert result["unmapped_users"] == [
        {
            "clickup_user_id": "202",
            "clickup_username": "Bob CU",
            "clickup_user_email": "bob@clickup.test",
            "total_hours": 0.5,
        }
    ]
    assert result["unmapped_spaces"] == []


@pytest.mark.asyncio
async def test_build_report_raises_when_configured_workspace_is_missing():
    clickup = _FakeClickUp(team_id="team-1", teams=[{"id": "team-2", "members": []}], entries=[])
    db = _FakeSupabase({"profiles": [], "agency_clients": [], "brands": []})

    service = ClickUpTeamHoursService(db, clickup)

    with pytest.raises(ClickUpConfigurationError):
        await service.build_report_async(start_date_ms=1, end_date_ms=2)
