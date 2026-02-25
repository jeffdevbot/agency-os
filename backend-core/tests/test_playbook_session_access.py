from __future__ import annotations

from unittest.mock import MagicMock

from app.services.playbook_session import PlaybookSessionService


def _build_chain_table(response_data: list[dict]) -> MagicMock:
    table = MagicMock()
    table.select.return_value = table
    table.eq.return_value = table
    table.order.return_value = table
    table.limit.return_value = table
    response = MagicMock()
    response.data = response_data
    table.execute.return_value = response
    return table


def test_list_clients_for_picker_non_admin_returns_assigned_only() -> None:
    profiles_table = _build_chain_table([{"id": "p1", "is_admin": False}])
    assignments_table = _build_chain_table(
        [
            {"agency_clients": {"id": "c2", "name": "Bravo", "status": "active"}},
            {"agency_clients": {"id": "c1", "name": "Alpha", "status": "active"}},
        ]
    )
    all_clients_table = _build_chain_table([{"id": "c3", "name": "Gamma", "status": "active"}])

    db = MagicMock()
    db.table.side_effect = lambda name: {
        "profiles": profiles_table,
        "client_assignments": assignments_table,
        "agency_clients": all_clients_table,
    }[name]

    service = PlaybookSessionService(db)
    result = service.list_clients_for_picker("p1")

    assert [c["name"] for c in result] == ["Alpha", "Bravo"]
    assert all_clients_table.execute.call_count == 0


def test_list_clients_for_picker_admin_returns_all_active() -> None:
    profiles_table = _build_chain_table([{"id": "admin-1", "is_admin": True}])
    all_clients_table = _build_chain_table(
        [
            {"id": "c1", "name": "Alpha", "status": "active"},
            {"id": "c2", "name": "Bravo", "status": "active"},
        ]
    )

    db = MagicMock()
    db.table.side_effect = lambda name: {
        "profiles": profiles_table,
        "agency_clients": all_clients_table,
        "client_assignments": _build_chain_table([]),
    }[name]

    service = PlaybookSessionService(db)
    result = service.list_clients_for_picker("admin-1")

    assert [c["name"] for c in result] == ["Alpha", "Bravo"]
