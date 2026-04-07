from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.mcp.auth import MCPUser
from app.mcp.event_logging import MCPToolInvocation
from app.mcp.tools.analyst import AnalystQueryError, register_analyst_tools
from app.mcp.tools.clients import register_client_tools


def _make_mock_mcp() -> Any:
    class _MockMCP:
        def __init__(self) -> None:
            self._registered: list[dict[str, Any]] = []

        def tool(self, *, name: str, description: str, structured_output: bool) -> Any:
            def decorator(fn: Any) -> Any:
                self._registered.append(
                    {
                        "name": name,
                        "description": description,
                        "structured_output": structured_output,
                        "fn": fn,
                    }
                )
                return fn

            return decorator

    return _MockMCP()


@dataclass
class _MockInvocation:
    tool_name: str
    is_mutation: bool | None
    success_calls: list[dict[str, Any]] = field(default_factory=list)
    error_calls: list[dict[str, Any]] = field(default_factory=list)

    def success(self, **meta: Any) -> None:
        self.success_calls.append(meta)

    def error(self, *, error_type: str | None = None, **meta: Any) -> None:
        payload = dict(meta)
        if error_type is not None:
            payload["error_type"] = error_type
        self.error_calls.append(payload)


def test_mcp_tool_invocation_logs_success_payload(monkeypatch):
    payloads: list[dict[str, Any]] = []
    monkeypatch.setattr("app.mcp.event_logging.mcp_event_logger.log", payloads.append)
    monkeypatch.setattr("app.mcp.event_logging.logger.info", lambda *_args, **_kwargs: None)

    invocation = MCPToolInvocation(
        tool_name="get_wbr_summary",
        user=MCPUser(
            profile_id="11111111-1111-1111-1111-111111111111",
            auth_user_id="22222222-2222-2222-2222-222222222222",
            email="ops@ecomlabs.ca",
            employment_status="active",
        ),
    )

    invocation.success(profile_id="profile-1", result_count=2, ignored=None)

    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["tool_name"] == "get_wbr_summary"
    assert payload["status"] == "success"
    assert payload["user_id"] == "11111111-1111-1111-1111-111111111111"
    assert payload["user_email"] == "ops@ecomlabs.ca"
    assert payload["surface"] == "claude_mcp"
    assert payload["connector_name"] == "Ecomlabs Tools"
    assert payload["is_mutation"] is False
    assert payload["meta"] == {"profile_id": "profile-1", "result_count": 2}
    assert isinstance(payload["duration_ms"], int)
    assert payload["duration_ms"] >= 0


def test_resolve_client_wrapper_records_success(monkeypatch):
    invocations: list[_MockInvocation] = []

    def _start(tool_name: str, *, is_mutation: bool | None = None) -> _MockInvocation:
        invocation = _MockInvocation(tool_name=tool_name, is_mutation=is_mutation)
        invocations.append(invocation)
        return invocation

    monkeypatch.setattr("app.mcp.tools.clients.start_mcp_tool_invocation", _start)
    monkeypatch.setattr(
        "app.mcp.tools.clients.resolve_client_matches",
        lambda query: {"matches": [{"client_id": "client-1"}]},
    )

    mock_mcp = _make_mock_mcp()
    register_client_tools(mock_mcp)
    fn = next(r["fn"] for r in mock_mcp._registered if r["name"] == "resolve_client")

    result = fn("Whoosh")

    assert result == {"matches": [{"client_id": "client-1"}]}
    assert len(invocations) == 1
    invocation = invocations[0]
    assert invocation.tool_name == "resolve_client"
    assert invocation.is_mutation is False
    assert invocation.error_calls == []
    assert invocation.success_calls == [{"query_length": 6, "match_count": 1}]


def test_query_business_facts_wrapper_records_structured_error(monkeypatch):
    invocations: list[_MockInvocation] = []

    def _start(tool_name: str, *, is_mutation: bool | None = None) -> _MockInvocation:
        invocation = _MockInvocation(tool_name=tool_name, is_mutation=is_mutation)
        invocations.append(invocation)
        return invocation

    monkeypatch.setattr("app.mcp.tools.analyst.start_mcp_tool_invocation", _start)
    monkeypatch.setattr("app.mcp.tools.analyst._get_supabase_admin_client", lambda: object())

    def _raise_error(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise AnalystQueryError("missing_row_scope", "Row scope is missing")

    monkeypatch.setattr("app.mcp.tools.analyst._query_business_facts", _raise_error)

    mock_mcp = _make_mock_mcp()
    register_analyst_tools(mock_mcp)
    fn = next(r["fn"] for r in mock_mcp._registered if r["name"] == "query_business_facts")

    result = fn(
        profile_id="profile-1",
        date_from="2026-03-01",
        date_to="2026-03-31",
        group_by="row",
        child_asins=None,
        row_id=None,
        metrics=None,
        limit=25,
    )

    assert result == {"error": "missing_row_scope", "message": "Row scope is missing"}
    assert len(invocations) == 1
    invocation = invocations[0]
    assert invocation.tool_name == "query_business_facts"
    assert invocation.success_calls == []
    assert invocation.error_calls == [
        {
            "profile_id": "profile-1",
            "group_by": "row",
            "row_id": None,
            "child_asin_count": 0,
            "limit": 25,
            "error_type": "missing_row_scope",
        }
    ]
