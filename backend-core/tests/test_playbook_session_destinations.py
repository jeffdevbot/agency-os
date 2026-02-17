from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.playbook_session import PlaybookSessionService


def _build_service_with_brand_rows(rows: list[dict]) -> PlaybookSessionService:
    db = MagicMock()
    table = MagicMock()
    db.table.return_value = table
    table.select.return_value = table
    table.eq.return_value = table
    table.order.return_value = table
    table.limit.return_value = table
    table.execute.return_value = SimpleNamespace(data=rows)
    return PlaybookSessionService(db)


def test_get_all_brand_destinations_includes_list_only_mappings():
    service = _build_service_with_brand_rows(
        [
            {
                "id": "b1",
                "name": "List-only Brand",
                "clickup_space_id": None,
                "clickup_list_id": "12345",
            },
            {
                "id": "b2",
                "name": "Space Brand",
                "clickup_space_id": "sp1",
                "clickup_list_id": None,
            },
            {
                "id": "b3",
                "name": "No Mapping",
                "clickup_space_id": None,
                "clickup_list_id": None,
            },
        ]
    )

    results = service.get_all_brand_destinations_for_client("client-1")

    ids = {row["id"] for row in results}
    assert ids == {"b1", "b2"}


def test_get_all_brand_destinations_blank_client_short_circuits():
    db = MagicMock()
    service = PlaybookSessionService(db)
    assert service.get_all_brand_destinations_for_client("") == []
    db.table.assert_not_called()

