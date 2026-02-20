from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from app.services.agencyclaw.brand_mapping_remediation import (
    apply_brand_mapping_remediation_plan,
    build_brand_mapping_remediation_plan,
)


@dataclass
class _FakeResponse:
    data: Any


class _FakeQuery:
    def __init__(self, db: "_FakeDB", table_name: str) -> None:
        self._db = db
        self._table_name = table_name
        self._select_cols: list[str] | None = None
        self._eq_filters: dict[str, Any] = {}
        self._in_filters: dict[str, set[Any]] = {}
        self._limit: int | None = None
        self._update_payload: dict[str, Any] | None = None

    def select(self, columns: str) -> "_FakeQuery":
        self._select_cols = [c.strip() for c in columns.split(",") if c.strip()]
        return self

    def order(self, _col: str, *, desc: bool = False) -> "_FakeQuery":
        _ = desc
        return self

    def limit(self, value: int) -> "_FakeQuery":
        self._limit = value
        return self

    def eq(self, key: str, value: Any) -> "_FakeQuery":
        self._eq_filters[key] = value
        return self

    def in_(self, key: str, values: list[Any]) -> "_FakeQuery":
        self._in_filters[key] = set(values)
        return self

    def update(self, payload: dict[str, Any]) -> "_FakeQuery":
        self._update_payload = payload
        return self

    def execute(self) -> _FakeResponse:
        rows = deepcopy(self._db.tables.get(self._table_name, []))

        def _matches(row: dict[str, Any]) -> bool:
            for key, value in self._eq_filters.items():
                if row.get(key) != value:
                    return False
            for key, values in self._in_filters.items():
                if row.get(key) not in values:
                    return False
            return True

        filtered = [r for r in rows if _matches(r)]

        if self._update_payload is not None:
            for row in self._db.tables.get(self._table_name, []):
                if _matches(row):
                    row_id = str(row.get("id") or "")
                    if row_id in self._db.fail_update_ids:
                        raise RuntimeError(f"update failed for {row_id}")
                    row.update(self._update_payload)
                    self._db.update_calls.append(
                        {"table": self._table_name, "id": row_id, "payload": dict(self._update_payload)}
                    )
            return _FakeResponse(data=[])

        if self._limit is not None:
            filtered = filtered[: self._limit]

        if self._select_cols:
            projected = []
            for row in filtered:
                projected.append({k: row.get(k) for k in self._select_cols})
            filtered = projected

        return _FakeResponse(data=filtered)


class _FakeDB:
    def __init__(self, tables: dict[str, list[dict[str, Any]]]) -> None:
        self.tables = deepcopy(tables)
        self.update_calls: list[dict[str, Any]] = []
        self.fail_update_ids: set[str] = set()

    def table(self, table_name: str) -> _FakeQuery:
        return _FakeQuery(self, table_name)


def _brand(
    *,
    id: str,
    name: str,
    client_id: str,
    space: str | None = None,
    list_id: str | None = None,
) -> dict[str, Any]:
    return {
        "id": id,
        "name": name,
        "client_id": client_id,
        "clickup_space_id": space,
        "clickup_list_id": list_id,
    }


def _client(*, id: str, name: str) -> dict[str, str]:
    return {"id": id, "name": name}


class TestBuildBrandMappingRemediationPlan:
    def test_single_default_mapping_can_apply(self) -> None:
        db = _FakeDB(
            {
                "agency_clients": [_client(id="c1", name="Distex")],
                "brands": [
                    _brand(id="b1", name="Mapped", client_id="c1", space="sp1", list_id="l1"),
                    _brand(id="b2", name="Needs Mapping", client_id="c1", space=None, list_id=None),
                ],
            }
        )

        plan = build_brand_mapping_remediation_plan(db)

        assert len(plan) == 1
        assert plan[0]["brand_id"] == "b2"
        assert plan[0]["safe_to_apply"] is True
        assert plan[0]["proposed_space_id"] == "sp1"
        assert plan[0]["proposed_list_id"] == "l1"
        assert plan[0]["client_name"] == "Distex"

    def test_partial_missing_field_uses_client_default_for_that_field(self) -> None:
        db = _FakeDB(
            {
                "agency_clients": [_client(id="c1", name="Distex")],
                "brands": [
                    _brand(id="b1", name="Default", client_id="c1", space="sp1", list_id="l1"),
                    _brand(id="b2", name="Missing List", client_id="c1", space="sp1", list_id=None),
                ],
            }
        )

        plan = build_brand_mapping_remediation_plan(db)

        assert len(plan) == 1
        assert plan[0]["brand_id"] == "b2"
        assert plan[0]["safe_to_apply"] is True
        assert plan[0]["proposed_space_id"] == "sp1"
        assert plan[0]["proposed_list_id"] == "l1"
        assert plan[0]["missing_fields"] == ["clickup_list_id"]

    def test_multiple_defaults_blocks_auto_apply(self) -> None:
        db = _FakeDB(
            {
                "agency_clients": [_client(id="c1", name="Distex")],
                "brands": [
                    _brand(id="b1", name="Mapped A", client_id="c1", space="sp1", list_id="l1"),
                    _brand(id="b2", name="Mapped B", client_id="c1", space="sp1", list_id="l2"),
                    _brand(id="b3", name="Needs Mapping", client_id="c1", space="sp1", list_id=None),
                ],
            }
        )

        plan = build_brand_mapping_remediation_plan(db)

        assert len(plan) == 1
        assert plan[0]["safe_to_apply"] is False
        assert "multiple defaults for clickup_list_id" in plan[0]["reason"]

    def test_no_defaults_blocks_auto_apply(self) -> None:
        db = _FakeDB(
            {
                "agency_clients": [_client(id="c1", name="Distex")],
                "brands": [
                    _brand(id="b1", name="Needs Mapping", client_id="c1", space=None, list_id=None),
                ],
            }
        )

        plan = build_brand_mapping_remediation_plan(db)

        assert len(plan) == 1
        assert plan[0]["safe_to_apply"] is False
        assert "no client default for clickup_space_id" in plan[0]["reason"]
        assert "no client default for clickup_list_id" in plan[0]["reason"]

    def test_client_filter_limits_scope(self) -> None:
        db = _FakeDB(
            {
                "agency_clients": [
                    _client(id="c1", name="Distex"),
                    _client(id="c2", name="Revant"),
                ],
                "brands": [
                    _brand(id="b1", name="D Default", client_id="c1", space="sp1", list_id="l1"),
                    _brand(id="b2", name="D Missing", client_id="c1", space=None, list_id=None),
                    _brand(id="b3", name="R Missing", client_id="c2", space=None, list_id=None),
                ],
            }
        )

        plan = build_brand_mapping_remediation_plan(db, client_id="c1")

        assert len(plan) == 1
        assert plan[0]["brand_id"] == "b2"
        assert plan[0]["client_id"] == "c1"


class TestApplyBrandMappingRemediationPlan:
    def test_dry_run_does_not_update(self) -> None:
        db = _FakeDB({"agency_clients": [], "brands": []})
        plan = [
            {
                "brand_id": "b1",
                "brand_name": "Brand",
                "client_id": "c1",
                "client_name": "Client",
                "current_space_id": None,
                "current_list_id": None,
                "proposed_space_id": "sp1",
                "proposed_list_id": "l1",
                "missing_fields": ["clickup_space_id", "clickup_list_id"],
                "safe_to_apply": True,
                "reason": "single client default mapping",
            }
        ]

        result = apply_brand_mapping_remediation_plan(db, plan, dry_run=True)

        assert result["would_apply"] == 1
        assert result["applied"] == 0
        assert db.update_calls == []

    def test_apply_updates_safe_items_only(self) -> None:
        db = _FakeDB(
            {
                "agency_clients": [_client(id="c1", name="Distex")],
                "brands": [
                    _brand(id="b1", name="Needs Mapping", client_id="c1", space=None, list_id=None),
                    _brand(id="b2", name="Unsafe", client_id="c1", space=None, list_id=None),
                ],
            }
        )
        plan = [
            {
                "brand_id": "b1",
                "brand_name": "Needs Mapping",
                "client_id": "c1",
                "client_name": "Distex",
                "current_space_id": None,
                "current_list_id": None,
                "proposed_space_id": "sp1",
                "proposed_list_id": "l1",
                "missing_fields": ["clickup_space_id", "clickup_list_id"],
                "safe_to_apply": True,
                "reason": "single client default mapping",
            },
            {
                "brand_id": "b2",
                "brand_name": "Unsafe",
                "client_id": "c1",
                "client_name": "Distex",
                "current_space_id": None,
                "current_list_id": None,
                "proposed_space_id": None,
                "proposed_list_id": None,
                "missing_fields": ["clickup_space_id", "clickup_list_id"],
                "safe_to_apply": False,
                "reason": "no client defaults",
            },
        ]

        result = apply_brand_mapping_remediation_plan(db, plan, dry_run=False)

        assert result["applied"] == 1
        assert result["skipped"] >= 1
        assert len(db.update_calls) == 1
        assert db.tables["brands"][0]["clickup_space_id"] == "sp1"
        assert db.tables["brands"][0]["clickup_list_id"] == "l1"

    def test_apply_records_failures(self) -> None:
        db = _FakeDB(
            {
                "agency_clients": [_client(id="c1", name="Distex")],
                "brands": [_brand(id="b1", name="Needs Mapping", client_id="c1", space=None, list_id=None)],
            }
        )
        db.fail_update_ids.add("b1")
        plan = [
            {
                "brand_id": "b1",
                "brand_name": "Needs Mapping",
                "client_id": "c1",
                "client_name": "Distex",
                "current_space_id": None,
                "current_list_id": None,
                "proposed_space_id": "sp1",
                "proposed_list_id": "l1",
                "missing_fields": ["clickup_space_id", "clickup_list_id"],
                "safe_to_apply": True,
                "reason": "single client default mapping",
            }
        ]

        result = apply_brand_mapping_remediation_plan(db, plan, dry_run=False)

        assert result["applied"] == 0
        assert len(result["failures"]) == 1
        assert result["failures"][0]["brand_id"] == "b1"

