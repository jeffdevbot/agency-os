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
async def test_build_report_maps_list_first_then_space_and_preserves_unlinked_buckets():
    clickup = _FakeClickUp(
        team_id="team-1",
        teams=[
            {
                "id": "team-1",
                "members": [
                    {"user": {"id": 101, "username": "Alice CU", "email": "alice@clickup.test"}},
                    {"user": {"id": 202, "username": "Bob CU", "email": "bob@clickup.test"}},
                    {"user": {"id": 303, "username": "Carol CU", "email": "carol@clickup.test"}},
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
                "billable": True,
                "task": {"id": "task-1", "name": "Mapped by list"},
                "task_location": {
                    "space_id": "space-a",
                    "space_name": "Alpha Space",
                    "list_id": "list-a",
                    "list_name": "Alpha List",
                },
                "task_tags": [{"name": "ops"}],
            },
            {
                "id": "te-2",
                "wid": "team-1",
                "user": {"id": 101, "username": "Alice CU", "email": "alice@clickup.test"},
                "duration": "3600000",
                "start": "1700010000000",
                "end": "1700013600000",
                "billable": True,
                "task": {"id": "task-2", "name": "Mapped by unique space"},
                "task_location": {
                    "space_id": "space-b",
                    "space_name": "Beta Space",
                    "list_id": "unknown-list",
                    "list_name": "Unknown List",
                },
                "task_tags": [],
            },
            {
                "id": "te-3",
                "wid": "team-1",
                "user": {"id": 202, "username": "Bob CU", "email": "bob@clickup.test"},
                "duration": "1800000",
                "start": "1700020000000",
                "end": "1700021800000",
                "billable": False,
                "task": {"id": "task-3", "name": "Unmapped space"},
                "task_location": {
                    "space_id": "space-shared",
                    "space_name": "Shared Space",
                    "list_id": "shared-list",
                    "list_name": "Shared List",
                },
                "task_tags": [],
            },
            {
                "id": "te-4",
                "wid": "team-1",
                "user": {"id": 303, "username": "Carol CU", "email": "carol@clickup.test"},
                "duration": "-1",
                "start": "1700030000000",
                "end": None,
                "billable": None,
                "task": {"id": "task-4", "name": "Running"},
                "task_location": {
                    "space_id": "space-z",
                    "space_name": "Zeta Space",
                    "list_id": "list-z",
                    "list_name": "Zeta List",
                },
                "task_tags": [],
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
                },
                {
                    "id": "profile-dup-1",
                    "email": "bob-1@agency.test",
                    "display_name": "Bob One",
                    "full_name": "Bob One",
                    "clickup_user_id": "202",
                },
                {
                    "id": "profile-dup-2",
                    "email": "bob-2@agency.test",
                    "display_name": "Bob Two",
                    "full_name": "Bob Two",
                    "clickup_user_id": "202",
                },
            ],
            "agency_clients": [
                {"id": "client-a", "name": "Alpha Client"},
                {"id": "client-b", "name": "Beta Client"},
                {"id": "client-c", "name": "Gamma Client"},
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
    assert result["summary"] == {
        "total_hours": 3.5,
        "mapped_hours": 3.5,
        "unmapped_hours": 0.0,
        "unattributed_hours": 0.0,
        "unique_users": 3,
        "entry_count": 4,
        "running_entries": 1,
    }

    alice = result["by_team_member"][0]
    assert alice["team_member_name"] == "Alice"
    assert alice["mapped"] is True
    assert alice["total_hours"] == 3.0
    assert alice["clients"][0]["client_name"] == "Alpha Client"
    assert alice["clients"][0]["brand_name"] == "Alpha Brand"
    assert alice["clients"][0]["total_hours"] == 2.0
    assert alice["clients"][1]["client_name"] == "Beta Client"
    assert alice["clients"][1]["brand_name"] == "Beta Brand"
    assert alice["clients"][1]["total_hours"] == 1.0

    bob = result["by_team_member"][1]
    assert bob["team_member_name"] == "Bob CU"
    assert bob["mapped"] is False
    assert bob["mapped_hours"] == 0.5
    assert bob["unmapped_hours"] == 0.0
    assert bob["clients"][0]["client_name"] == "Gamma Client"
    assert bob["clients"][0]["brand_name"] is None
    assert bob["clients"][0]["mapped"] is True

    carol = result["by_team_member"][2]
    assert carol["total_hours"] == 0.0
    assert carol["mapped"] is False

    assert result["by_client"] == [
        {
            "client_id": "client-a",
            "client_name": "Alpha Client",
            "brand_id": "brand-a",
            "brand_name": "Alpha Brand",
            "mapped": True,
            "team_member_count": 1,
            "space_count": 1,
            "entry_count": 1,
            "total_hours": 2.0,
        },
        {
            "client_id": "client-b",
            "client_name": "Beta Client",
            "brand_id": "brand-b",
            "brand_name": "Beta Brand",
            "mapped": True,
            "team_member_count": 1,
            "space_count": 1,
            "entry_count": 1,
            "total_hours": 1.0,
        },
        {
            "client_id": "client-c",
            "client_name": "Gamma Client",
            "brand_id": None,
            "brand_name": None,
            "mapped": True,
            "team_member_count": 1,
            "space_count": 1,
            "entry_count": 1,
            "total_hours": 0.5,
        },
        {
            "client_id": None,
            "client_name": "Unlinked Space",
            "brand_id": None,
            "brand_name": None,
            "mapped": False,
            "team_member_count": 1,
            "space_count": 1,
            "entry_count": 1,
            "total_hours": 0.0,
        },
    ]
    assert result["by_space"] == [
        {
            "space_id": "space-a",
            "space_name": "Alpha Space",
            "list_id": "list-a",
            "list_name": "Alpha List",
            "client_id": "client-a",
            "client_name": "Alpha Client",
            "brand_id": "brand-a",
            "brand_name": "Alpha Brand",
            "mapped": True,
            "team_member_count": 1,
            "entry_count": 1,
            "total_hours": 2.0,
        },
        {
            "space_id": "space-b",
            "space_name": "Beta Space",
            "list_id": "unknown-list",
            "list_name": "Unknown List",
            "client_id": "client-b",
            "client_name": "Beta Client",
            "brand_id": "brand-b",
            "brand_name": "Beta Brand",
            "mapped": True,
            "team_member_count": 1,
            "entry_count": 1,
            "total_hours": 1.0,
        },
        {
            "space_id": "space-shared",
            "space_name": "Shared Space",
            "list_id": "shared-list",
            "list_name": "Shared List",
            "client_id": "client-c",
            "client_name": "Gamma Client",
            "brand_id": None,
            "brand_name": None,
            "mapped": True,
            "team_member_count": 1,
            "entry_count": 1,
            "total_hours": 0.5,
        },
        {
            "space_id": "space-z",
            "space_name": "Zeta Space",
            "list_id": "list-z",
            "list_name": "Zeta List",
            "client_id": None,
            "client_name": "Unlinked Space",
            "brand_id": None,
            "brand_name": None,
            "mapped": False,
            "team_member_count": 1,
            "entry_count": 1,
            "total_hours": 0.0,
        },
    ]

    assert result["unmapped_users"] == [
        {
            "clickup_user_id": "202",
            "clickup_username": "Bob CU",
            "clickup_user_email": "bob@clickup.test",
            "total_hours": 0.5,
        },
        {
            "clickup_user_id": "303",
            "clickup_username": "Carol CU",
            "clickup_user_email": "carol@clickup.test",
            "total_hours": 0.0,
        },
    ]
    assert result["unmapped_spaces"] == [
        {
            "space_id": "space-z",
            "space_name": "Zeta Space",
            "list_id": "list-z",
            "list_name": "Zeta List",
            "total_hours": 0.0,
        },
    ]


@pytest.mark.asyncio
async def test_build_report_raises_when_configured_workspace_is_missing():
    clickup = _FakeClickUp(team_id="team-1", teams=[{"id": "team-2", "members": []}], entries=[])
    db = _FakeSupabase({"profiles": [], "agency_clients": [], "brands": []})

    service = ClickUpTeamHoursService(db, clickup)

    with pytest.raises(ClickUpConfigurationError):
        await service.build_report_async(start_date_ms=1, end_date_ms=2)
