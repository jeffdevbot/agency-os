"""Tests for WBR ↔ The Claw integration: profile resolver, DB lookup, skill tools, tool-use runtime."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from app.services.wbr.wbr_summary_renderer import render_wbr_summary


# ---------------------------------------------------------------------------
# Profile resolver tests
# ---------------------------------------------------------------------------


class _FakeTable:
    def __init__(self, rows: list[dict]):
        self._rows = rows
        self._filters_eq: dict = {}
        self._limit_n: int | None = None

    def select(self, *args, **kwargs):
        return self

    def eq(self, col, val):
        self._filters_eq[col] = val
        return self

    def limit(self, n):
        self._limit_n = n
        return self

    def execute(self):
        filtered = self._rows
        if self._filters_eq:
            filtered = [
                row for row in filtered
                if all(row.get(col) == val for col, val in self._filters_eq.items())
            ]
        if self._limit_n:
            filtered = filtered[:self._limit_n]
        resp = MagicMock()
        resp.data = filtered
        return resp


class _FakeDB:
    def __init__(self, tables: dict[str, list[dict]] | None = None):
        self._tables = {name: list(rows) for name, rows in (tables or {}).items()}

    def table(self, name: str):
        return _FakeTable(self._tables.get(name, []))


class TestResolveWbrProfile:
    def test_resolves_matching_profile(self):
        from app.services.wbr.wbr_profile_resolver import resolve_wbr_profile

        db = _FakeDB(tables={
            "agency_clients": [{"id": "c1", "name": "Whoosh"}],
            "wbr_profiles": [
                {"id": "p1", "client_id": "c1", "marketplace_code": "US"},
                {"id": "p2", "client_id": "c1", "marketplace_code": "CA"},
            ],
        })
        result = resolve_wbr_profile(db, "Whoosh", "US")
        assert result is not None
        assert result["id"] == "p1"

    def test_returns_none_when_client_not_found(self):
        from app.services.wbr.wbr_profile_resolver import resolve_wbr_profile

        db = _FakeDB(tables={"agency_clients": [], "wbr_profiles": []})
        result = resolve_wbr_profile(db, "NoSuchClient", "US")
        assert result is None

    def test_returns_none_when_profile_not_found(self):
        from app.services.wbr.wbr_profile_resolver import resolve_wbr_profile

        db = _FakeDB(tables={
            "agency_clients": [{"id": "c1", "name": "Whoosh"}],
            "wbr_profiles": [{"id": "p1", "client_id": "c1", "marketplace_code": "CA"}],
        })
        result = resolve_wbr_profile(db, "Whoosh", "US")
        assert result is None

    def test_returns_none_for_empty_inputs(self):
        from app.services.wbr.wbr_profile_resolver import resolve_wbr_profile

        db = _FakeDB()
        assert resolve_wbr_profile(db, "", "US") is None
        assert resolve_wbr_profile(db, "Whoosh", "") is None


# ---------------------------------------------------------------------------
# DB lookup tests (lookup_wbr_digest)
# ---------------------------------------------------------------------------


class TestLookupWbrDigest:
    def test_returns_digest_when_profile_and_snapshot_exist(self, monkeypatch):
        from app.services.theclaw import wbr_skill_bridge

        fake_digest = {"digest_version": "wbr_digest_v1", "profile": {"client_name": "Whoosh"}}
        fake_snapshot = {
            "id": "snap-1",
            "digest": fake_digest,
            "source_run_at": "2026-03-18T10:00:00Z",
        }
        fake_profile = {"id": "p1", "client_id": "c1", "marketplace_code": "US"}

        monkeypatch.setattr(
            "app.services.wbr.wbr_profile_resolver.resolve_wbr_profile",
            lambda db, client, market: fake_profile,
        )

        class _FakeSnapshotSvc:
            def __init__(self, db):
                pass
            def get_or_create_snapshot(self, profile_id):
                return fake_snapshot

        monkeypatch.setattr("app.services.wbr.report_snapshots.WBRSnapshotService", _FakeSnapshotSvc)
        monkeypatch.setattr("supabase.create_client", lambda url, key: MagicMock())
        monkeypatch.setattr("app.config.settings", MagicMock(supabase_url="http://fake", supabase_service_role_key="key"))

        result = wbr_skill_bridge.lookup_wbr_digest("Whoosh", "US")
        assert result["profile"]["client_name"] == "Whoosh"
        assert result["source_run_at"] == "2026-03-18T10:00:00Z"

    def test_returns_no_profile_when_profile_missing(self, monkeypatch):
        from app.services.theclaw import wbr_skill_bridge

        monkeypatch.setattr("app.services.wbr.wbr_profile_resolver.resolve_wbr_profile", lambda db, c, m: None)
        monkeypatch.setattr("supabase.create_client", lambda url, key: MagicMock())
        monkeypatch.setattr("app.config.settings", MagicMock(supabase_url="http://fake", supabase_service_role_key="key"))

        result = wbr_skill_bridge.lookup_wbr_digest("NoClient", "US")
        assert result["status"] == "no_profile"

    def test_returns_no_data_when_snapshot_has_no_digest(self, monkeypatch):
        from app.services.theclaw import wbr_skill_bridge

        monkeypatch.setattr(
            "app.services.wbr.wbr_profile_resolver.resolve_wbr_profile",
            lambda db, c, m: {"id": "p1"},
        )

        class _EmptySnapshotSvc:
            def __init__(self, db):
                pass
            def get_or_create_snapshot(self, profile_id):
                return {"id": "snap-1", "digest": None}

        monkeypatch.setattr("app.services.wbr.report_snapshots.WBRSnapshotService", _EmptySnapshotSvc)
        monkeypatch.setattr("supabase.create_client", lambda url, key: MagicMock())
        monkeypatch.setattr("app.config.settings", MagicMock(supabase_url="http://fake", supabase_service_role_key="key"))

        result = wbr_skill_bridge.lookup_wbr_digest("Whoosh", "US")
        assert result["status"] == "no_data"

    def test_list_wbr_profiles_returns_client_marketplace_pairs(self, monkeypatch):
        from app.services.theclaw import wbr_skill_bridge

        class _FakeTable:
            def __init__(self, rows):
                self._rows = rows

            def select(self, *args, **kwargs):
                return self

            def order(self, *args, **kwargs):
                return self

            def execute(self):
                resp = MagicMock()
                resp.data = self._rows
                return resp

        class _FakeDB:
            def table(self, name):
                if name == "agency_clients":
                    return _FakeTable([
                        {"id": "c1", "name": "Basari World"},
                        {"id": "c2", "name": "Whoosh"},
                    ])
                if name == "wbr_profiles":
                    return _FakeTable([
                        {"id": "p1", "client_id": "c1", "display_name": "Basari World", "marketplace_code": "MX"},
                        {"id": "p2", "client_id": "c2", "display_name": "Whoosh", "marketplace_code": "US"},
                    ])
                return _FakeTable([])

        monkeypatch.setattr("supabase.create_client", lambda url, key: _FakeDB())
        monkeypatch.setattr("app.config.settings", MagicMock(supabase_url="http://fake", supabase_service_role_key="key"))

        result = wbr_skill_bridge.list_wbr_profiles()
        assert "profiles" in result
        assert {"profile_id": "p1", "client_name": "Basari World", "display_name": "Basari World", "marketplace_code": "MX"} in result["profiles"]


# ---------------------------------------------------------------------------
# Skill tools registry tests
# ---------------------------------------------------------------------------


class TestSkillToolsRegistry:
    def test_returns_tool_definitions_for_wbr_summary(self):
        from app.services.theclaw.skill_tools import get_skill_tool_definitions

        defs = get_skill_tool_definitions("wbr_summary")
        assert defs is not None
        assert len(defs) == 2
        names = {d["function"]["name"] for d in defs}
        assert names == {"lookup_wbr", "list_wbr_profiles"}

    def test_returns_none_for_unknown_skill(self):
        from app.services.theclaw.skill_tools import get_skill_tool_definitions

        assert get_skill_tool_definitions("nonexistent_skill") is None

    @pytest.mark.asyncio
    async def test_execute_calls_handler(self, monkeypatch):
        from app.services.theclaw.skill_tools import execute_skill_tool_call

        fake_digest = {"digest_version": "wbr_digest_v1", "profile": {"client_name": "Whoosh"}}
        monkeypatch.setattr(
            "app.services.theclaw.wbr_skill_bridge.lookup_wbr_digest",
            lambda client, market: fake_digest,
        )

        tool_result = await execute_skill_tool_call(
            skill_id="wbr_summary",
            tool_name="lookup_wbr",
            arguments_json='{"client":"Whoosh","marketplace":"US"}',
        )
        result = json.loads(tool_result["content"])
        assert result["digest_version"] == "wbr_digest_v1"
        assert tool_result["outcome"] == "read_only_success"

    @pytest.mark.asyncio
    async def test_execute_list_profiles_calls_handler(self, monkeypatch):
        from app.services.theclaw.skill_tools import execute_skill_tool_call

        monkeypatch.setattr(
            "app.services.theclaw.wbr_skill_bridge.list_wbr_profiles",
            lambda: {"profiles": [{"client_name": "Basari World", "marketplace_code": "MX"}]},
        )

        tool_result = await execute_skill_tool_call(
            skill_id="wbr_summary",
            tool_name="list_wbr_profiles",
            arguments_json="{}",
        )
        result = json.loads(tool_result["content"])
        assert result["profiles"][0]["client_name"] == "Basari World"
        assert tool_result["outcome"] == "read_only_success"

    @pytest.mark.asyncio
    async def test_execute_returns_error_for_unknown_tool(self):
        from app.services.theclaw.skill_tools import execute_skill_tool_call

        tool_result = await execute_skill_tool_call(
            skill_id="wbr_summary",
            tool_name="nonexistent_tool",
            arguments_json="{}",
        )
        result = json.loads(tool_result["content"])
        assert "error" in result
        assert tool_result["outcome"] == "tool_error"

    @pytest.mark.asyncio
    async def test_execute_handles_handler_exception(self, monkeypatch):
        from app.services.theclaw.skill_tools import execute_skill_tool_call

        monkeypatch.setattr(
            "app.services.theclaw.wbr_skill_bridge.lookup_wbr_digest",
            lambda client, market: (_ for _ in ()).throw(RuntimeError("DB down")),
        )

        tool_result = await execute_skill_tool_call(
            skill_id="wbr_summary",
            tool_name="lookup_wbr",
            arguments_json='{"client":"Whoosh","marketplace":"US"}',
        )
        result = json.loads(tool_result["content"])
        assert "error" in result
        assert tool_result["outcome"] == "tool_error"

    @pytest.mark.asyncio
    async def test_execute_read_only_error_result_is_tool_error(self, monkeypatch):
        from app.services.theclaw.skill_tools import execute_skill_tool_call

        monkeypatch.setattr(
            "app.services.theclaw.wbr_skill_bridge.lookup_wbr_digest",
            lambda client, market: {"error": "No matching WBR profile"},
        )

        tool_result = await execute_skill_tool_call(
            skill_id="wbr_summary",
            tool_name="lookup_wbr",
            arguments_json='{"client":"Whoosh","marketplace":"US"}',
        )
        result = json.loads(tool_result["content"])
        assert result["error"] == "No matching WBR profile"
        assert tool_result["outcome"] == "tool_error"


# ---------------------------------------------------------------------------
# Renderer footer test
# ---------------------------------------------------------------------------


class TestRendererFooter:
    def test_footer_present_when_source_run_at_set(self):
        digest = _make_minimal_digest(source_run_at="2026-03-18T10:00:00Z")
        text = render_wbr_summary(digest)
        assert "_Snapshot taken 2026-03-18T10:00:00Z_" in text

    def test_footer_absent_when_source_run_at_missing(self):
        digest = _make_minimal_digest()
        text = render_wbr_summary(digest)
        assert "Snapshot taken" not in text


# ---------------------------------------------------------------------------
# Context provider renderer: status dicts (still used for always-on contexts)
# ---------------------------------------------------------------------------


class TestWbrDigestRenderer:
    def test_renders_digest_data(self):
        from app.services.theclaw.context_providers import _render_wbr_digest

        blob = {"digest_version": "wbr_digest_v1", "profile": {"client_name": "Whoosh"}}
        result = _render_wbr_digest(blob)
        assert "WBR digest data" in result
        assert "Whoosh" in result

    def test_renders_status_dict(self):
        from app.services.theclaw.context_providers import _render_wbr_digest

        blob = {"status": "needs_clarification", "detail": "Which marketplace for Whoosh?"}
        result = _render_wbr_digest(blob)
        assert "WBR bridge status: needs_clarification" in result
        assert "Which marketplace for Whoosh?" in result


# ---------------------------------------------------------------------------
# Skill registration: wbr_summary no longer needs context blobs
# ---------------------------------------------------------------------------


class TestWbrSummarySkillRegistration:
    def test_skill_is_registered(self):
        from app.services.theclaw.skill_registry import get_skill_by_id, load_skills

        load_skills(force_reload=True)
        skill = get_skill_by_id("wbr_summary")
        assert skill is not None
        assert skill.skill_id == "wbr_summary"

    def test_skill_does_not_declare_wbr_digest_context(self):
        """Tools replace context blob injection — skill no longer needs wbr_digest."""
        from app.services.theclaw.skill_registry import get_skill_by_id, load_skills

        load_skills(force_reload=True)
        skill = get_skill_by_id("wbr_summary")
        assert skill is not None
        assert "wbr_digest" not in skill.needs_context

    def test_skill_has_tools_registered(self):
        from app.services.theclaw.skill_tools import get_skill_tool_definitions

        defs = get_skill_tool_definitions("wbr_summary")
        assert defs is not None
        assert any(d["function"]["name"] == "lookup_wbr" for d in defs)
        assert any(d["function"]["name"] == "list_wbr_profiles" for d in defs)


# ---------------------------------------------------------------------------
# Runtime integration: tool-use flow
# ---------------------------------------------------------------------------


def _make_fake_llm_response(content, *, tool_calls=None):
    return {
        "content": content,
        "tokens_in": 10, "tokens_out": 10, "tokens_total": 20,
        "model": "gpt-4o-mini", "duration_ms": 5,
        "tool_calls": tool_calls,
    }


def _make_tool_call(*, call_id="call_1", name="lookup_wbr", arguments=None):
    return {
        "id": call_id,
        "type": "function",
        "function": {
            "name": name,
            "arguments": json.dumps(arguments or {}),
        },
    }


@pytest.mark.asyncio
async def test_runtime_tool_use_full_flow(monkeypatch):
    """LLM selects skill → calls lookup_wbr tool → gets digest → formats summary."""
    from app.services.theclaw.slack_minimal_runtime import run_theclaw_minimal_dm_turn
    from tests.theclaw_runtime_test_fakes import FakeSessionService, FakeSlackService

    fake_slack = FakeSlackService()
    fake_session_service = FakeSessionService()
    calls: list[dict[str, object]] = []

    async def _fake_call_chat_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            # Skill selection
            return _make_fake_llm_response('{"skill_id":"wbr_summary","confidence":0.95,"reason":"wbr request"}')
        if len(calls) == 2:
            # Skill execution: LLM decides to call lookup_wbr
            return _make_fake_llm_response(
                "",
                tool_calls=[_make_tool_call(arguments={"client": "Whoosh", "marketplace": "US"})],
            )
        # Final response after tool result
        return _make_fake_llm_response(
            "*WBR Summary — Whoosh US*\nWeek ending 2026-03-15\n"
            "---THECLAW_STATE_JSON---\n{\"context_updates\":{}}\n---END_THECLAW_STATE_JSON---"
        )

    fake_digest = {"digest_version": "wbr_digest_v1", "profile": {"client_name": "Whoosh"}}
    monkeypatch.setattr("app.services.theclaw.wbr_skill_bridge.lookup_wbr_digest", lambda c, m: fake_digest)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.get_slack_service", lambda: fake_slack)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.call_chat_completion", _fake_call_chat_completion)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime._get_session_service", lambda: fake_session_service)

    await run_theclaw_minimal_dm_turn(slack_user_id="U20", channel="D20", text="Show me Whoosh US WBR")

    # 3 LLM calls: skill selection, tool call, final response
    assert len(calls) == 3
    # Second call should include tools
    assert calls[1].get("tools") is not None
    assert any(t["function"]["name"] == "lookup_wbr" for t in calls[1]["tools"])
    # Third call should include tool result in messages
    tool_msg = [m for m in calls[2]["messages"] if m.get("role") == "tool"]
    assert len(tool_msg) == 1
    assert "wbr_digest_v1" in tool_msg[0]["content"]
    # Execution-state grounding note should appear after tool results
    grounding_msgs = [
        m for m in calls[2]["messages"]
        if m.get("role") == "system" and "only retrieved data" in (m.get("content") or "").lower()
    ]
    assert len(grounding_msgs) == 1
    assert "no external systems were modified" in grounding_msgs[0]["content"].lower()
    # Third call should still have tools available (multi-step loop)
    assert calls[2].get("tools") is not None
    # Slack got the formatted reply
    assert len(fake_slack.messages) == 1
    assert "*WBR Summary — Whoosh US*" in fake_slack.messages[0]["text"]


@pytest.mark.asyncio
async def test_runtime_llm_asks_for_clarification_without_tool(monkeypatch):
    """Ambiguous request → LLM asks for clarification without calling any tool."""
    from app.services.theclaw.slack_minimal_runtime import run_theclaw_minimal_dm_turn
    from tests.theclaw_runtime_test_fakes import FakeSessionService, FakeSlackService

    fake_slack = FakeSlackService()
    fake_session_service = FakeSessionService()
    calls: list[dict[str, object]] = []

    async def _fake_call_chat_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _make_fake_llm_response('{"skill_id":"wbr_summary","confidence":0.90,"reason":"wbr"}')
        # LLM decides to ask instead of calling tool
        return _make_fake_llm_response(
            "Which client and marketplace would you like the WBR for?\n"
            "---THECLAW_STATE_JSON---\n{\"context_updates\":{}}\n---END_THECLAW_STATE_JSON---"
        )

    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.get_slack_service", lambda: fake_slack)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.call_chat_completion", _fake_call_chat_completion)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime._get_session_service", lambda: fake_session_service)

    await run_theclaw_minimal_dm_turn(slack_user_id="U21", channel="D21", text="show me the WBR")

    # Only 2 LLM calls: selection + direct response (no tool call)
    assert len(calls) == 2
    assert len(fake_slack.messages) == 1
    assert "client" in fake_slack.messages[0]["text"].lower() or "marketplace" in fake_slack.messages[0]["text"].lower()


@pytest.mark.asyncio
async def test_runtime_no_tools_for_non_wbr_skill(monkeypatch):
    """Non-WBR skill → no tools offered to LLM."""
    from app.services.theclaw.slack_minimal_runtime import run_theclaw_minimal_dm_turn
    from tests.theclaw_runtime_test_fakes import FakeSessionService, FakeSlackService

    fake_slack = FakeSlackService()
    fake_session_service = FakeSessionService()
    calls: list[dict[str, object]] = []

    async def _fake_call_chat_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _make_fake_llm_response('{"skill_id":"none","confidence":0.9,"reason":"general"}')
        return _make_fake_llm_response("Hello! How can I help?")

    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.get_slack_service", lambda: fake_slack)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.call_chat_completion", _fake_call_chat_completion)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime._get_session_service", lambda: fake_session_service)

    await run_theclaw_minimal_dm_turn(slack_user_id="U22", channel="D22", text="hello")

    assert len(calls) == 2
    # No tools in the reply LLM call
    assert calls[1].get("tools") is None
    assert fake_slack.messages[0]["text"] == "Hello! How can I help?"


@pytest.mark.asyncio
async def test_runtime_tool_returns_no_profile(monkeypatch):
    """Tool returns no_profile error → LLM tells user naturally."""
    from app.services.theclaw.slack_minimal_runtime import run_theclaw_minimal_dm_turn
    from tests.theclaw_runtime_test_fakes import FakeSessionService, FakeSlackService

    fake_slack = FakeSlackService()
    fake_session_service = FakeSessionService()
    calls: list[dict[str, object]] = []

    async def _fake_call_chat_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _make_fake_llm_response('{"skill_id":"wbr_summary","confidence":0.92,"reason":"wbr"}')
        if len(calls) == 2:
            return _make_fake_llm_response(
                "",
                tool_calls=[_make_tool_call(arguments={"client": "FakeClient", "marketplace": "US"})],
            )
        return _make_fake_llm_response(
            "I don't have a WBR set up for FakeClient US yet.\n"
            "---THECLAW_STATE_JSON---\n{\"context_updates\":{}}\n---END_THECLAW_STATE_JSON---"
        )

    monkeypatch.setattr(
        "app.services.theclaw.wbr_skill_bridge.lookup_wbr_digest",
        lambda c, m: {"status": "no_profile", "detail": f"No WBR profile found for {c} {m}."},
    )
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.get_slack_service", lambda: fake_slack)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.call_chat_completion", _fake_call_chat_completion)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime._get_session_service", lambda: fake_session_service)

    await run_theclaw_minimal_dm_turn(slack_user_id="U23", channel="D23", text="WBR for FakeClient US")

    assert len(calls) == 3
    # Tool result has no_profile status
    tool_msg = [m for m in calls[2]["messages"] if m.get("role") == "tool"]
    assert "no_profile" in tool_msg[0]["content"]
    # LLM response is natural
    assert "FakeClient" in fake_slack.messages[0]["text"]


@pytest.mark.asyncio
async def test_runtime_tool_execution_failure_handled(monkeypatch):
    """Tool handler raises exception → error returned to LLM → LLM responds gracefully."""
    from app.services.theclaw.slack_minimal_runtime import run_theclaw_minimal_dm_turn
    from tests.theclaw_runtime_test_fakes import FakeSessionService, FakeSlackService

    fake_slack = FakeSlackService()
    fake_session_service = FakeSessionService()
    calls: list[dict[str, object]] = []

    async def _fake_call_chat_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _make_fake_llm_response('{"skill_id":"wbr_summary","confidence":0.95,"reason":"wbr"}')
        if len(calls) == 2:
            return _make_fake_llm_response(
                "",
                tool_calls=[_make_tool_call(arguments={"client": "Whoosh", "marketplace": "US"})],
            )
        return _make_fake_llm_response(
            "Sorry, I couldn't retrieve the WBR data right now. Please try again.\n"
            "---THECLAW_STATE_JSON---\n{\"context_updates\":{}}\n---END_THECLAW_STATE_JSON---"
        )

    def _broken_lookup(client, market):
        raise RuntimeError("DB connection failed")

    monkeypatch.setattr("app.services.theclaw.wbr_skill_bridge.lookup_wbr_digest", _broken_lookup)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.get_slack_service", lambda: fake_slack)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.call_chat_completion", _fake_call_chat_completion)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime._get_session_service", lambda: fake_session_service)

    await run_theclaw_minimal_dm_turn(slack_user_id="U24", channel="D24", text="WBR for Whoosh US")

    assert len(calls) == 3
    # Tool result contains error message
    tool_msg = [m for m in calls[2]["messages"] if m.get("role") == "tool"]
    assert "error" in tool_msg[0]["content"].lower()
    # LLM still responded
    assert len(fake_slack.messages) == 1


# ---------------------------------------------------------------------------
# Multi-step tool-use loop tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_runtime_multi_round_tool_calls(monkeypatch):
    """LLM calls a tool, sees result, calls another tool, then replies."""
    from app.services.theclaw.slack_minimal_runtime import run_theclaw_minimal_dm_turn
    from tests.theclaw_runtime_test_fakes import FakeSessionService, FakeSlackService

    fake_slack = FakeSlackService()
    fake_session_service = FakeSessionService()
    calls: list[dict[str, object]] = []

    async def _fake_call_chat_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _make_fake_llm_response('{"skill_id":"wbr_summary","confidence":0.95,"reason":"compare"}')
        if len(calls) == 2:
            # First tool call: lookup Whoosh US
            return _make_fake_llm_response(
                "",
                tool_calls=[_make_tool_call(call_id="call_1", arguments={"client": "Whoosh", "marketplace": "US"})],
            )
        if len(calls) == 3:
            # Second tool call: lookup Whoosh CA
            return _make_fake_llm_response(
                "",
                tool_calls=[_make_tool_call(call_id="call_2", arguments={"client": "Whoosh", "marketplace": "CA"})],
            )
        # Final response after both tool results
        return _make_fake_llm_response(
            "*WBR Comparison — Whoosh US vs CA*\n"
            "---THECLAW_STATE_JSON---\n{\"context_updates\":{}}\n---END_THECLAW_STATE_JSON---"
        )

    lookup_calls: list[tuple[str, str]] = []

    def _fake_lookup(client, market):
        lookup_calls.append((client, market))
        return {"digest_version": "wbr_digest_v1", "profile": {"client_name": client}, "marketplace": market}

    monkeypatch.setattr("app.services.theclaw.wbr_skill_bridge.lookup_wbr_digest", _fake_lookup)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.get_slack_service", lambda: fake_slack)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.call_chat_completion", _fake_call_chat_completion)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime._get_session_service", lambda: fake_session_service)

    await run_theclaw_minimal_dm_turn(slack_user_id="U30", channel="D30", text="Compare Whoosh US and CA WBR")

    # 4 LLM calls: selection, tool1, tool2, final
    assert len(calls) == 4
    # Two tool lookups
    assert len(lookup_calls) == 2
    assert ("Whoosh", "US") in lookup_calls
    assert ("Whoosh", "CA") in lookup_calls
    # Tools available on every loop iteration (calls 2, 3, and 4)
    for i in [1, 2, 3]:
        assert calls[i].get("tools") is not None
    # Final messages include both tool results
    tool_msgs = [m for m in calls[3]["messages"] if m.get("role") == "tool"]
    assert len(tool_msgs) == 2
    # Slack got the comparison
    assert len(fake_slack.messages) == 1
    assert "Comparison" in fake_slack.messages[0]["text"]


@pytest.mark.asyncio
async def test_runtime_can_recover_via_list_profiles_then_lookup(monkeypatch):
    """LLM can inspect available WBR profiles and retry with the canonical name."""
    from app.services.theclaw.slack_minimal_runtime import run_theclaw_minimal_dm_turn
    from tests.theclaw_runtime_test_fakes import FakeSessionService, FakeSlackService

    fake_slack = FakeSlackService()
    fake_session_service = FakeSessionService()
    calls: list[dict[str, object]] = []

    async def _fake_call_chat_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _make_fake_llm_response('{"skill_id":"wbr_summary","confidence":0.95,"reason":"wbr"}')
        if len(calls) == 2:
            return _make_fake_llm_response(
                "",
                tool_calls=[_make_tool_call(call_id="call_1", name="lookup_wbr", arguments={"client": "Basari", "marketplace": "MX"})],
            )
        if len(calls) == 3:
            return _make_fake_llm_response(
                "",
                tool_calls=[_make_tool_call(call_id="call_2", name="list_wbr_profiles", arguments={})],
            )
        if len(calls) == 4:
            return _make_fake_llm_response(
                "",
                tool_calls=[_make_tool_call(call_id="call_3", name="lookup_wbr", arguments={"client": "Basari World", "marketplace": "MX"})],
            )
        return _make_fake_llm_response(
            "*WBR Summary — Basari World MX*\nWeek ending 2026-03-15\n"
            "---THECLAW_STATE_JSON---\n{\"context_updates\":{}}\n---END_THECLAW_STATE_JSON---"
        )

    def _fake_lookup(client, market):
        if client == "Basari":
            return {"status": "no_profile", "detail": "No WBR profile found for Basari MX."}
        return {"digest_version": "wbr_digest_v1", "profile": {"client_name": client}, "marketplace_code": market}

    monkeypatch.setattr("app.services.theclaw.wbr_skill_bridge.lookup_wbr_digest", _fake_lookup)
    monkeypatch.setattr(
        "app.services.theclaw.wbr_skill_bridge.list_wbr_profiles",
        lambda: {"profiles": [{"client_name": "Basari World", "display_name": "Basari World", "marketplace_code": "MX"}]},
    )
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.get_slack_service", lambda: fake_slack)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.call_chat_completion", _fake_call_chat_completion)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime._get_session_service", lambda: fake_session_service)

    await run_theclaw_minimal_dm_turn(slack_user_id="U31A", channel="D31A", text="How did Basari MX look this week?")

    assert len(calls) == 5
    tool_msgs = [m for m in calls[4]["messages"] if m.get("role") == "tool"]
    assert len(tool_msgs) == 3
    assert "no_profile" in tool_msgs[0]["content"]
    assert "Basari World" in tool_msgs[1]["content"]
    assert "wbr_digest_v1" in tool_msgs[2]["content"]
    assert "Basari World MX" in fake_slack.messages[0]["text"]


@pytest.mark.asyncio
async def test_runtime_tool_budget_exhaustion(monkeypatch):
    """If the model keeps calling tools past the budget, runtime returns fallback."""
    from app.services.theclaw import slack_minimal_runtime
    from app.services.theclaw.slack_minimal_runtime import run_theclaw_minimal_dm_turn
    from tests.theclaw_runtime_test_fakes import FakeSessionService, FakeSlackService

    fake_slack = FakeSlackService()
    fake_session_service = FakeSessionService()
    calls: list[dict[str, object]] = []

    # Use a small budget so the test is fast.
    monkeypatch.setattr(slack_minimal_runtime, "_MAX_TOOL_TURNS", 2)

    call_counter = 0

    async def _fake_call_chat_completion(**kwargs):
        nonlocal call_counter
        call_counter += 1
        calls.append(kwargs)
        if call_counter == 1:
            return _make_fake_llm_response('{"skill_id":"wbr_summary","confidence":0.95,"reason":"wbr"}')
        # Always return tool calls — never produce a final text reply.
        return _make_fake_llm_response(
            "",
            tool_calls=[_make_tool_call(
                call_id=f"call_{call_counter}",
                arguments={"client": "Whoosh", "marketplace": "US"},
            )],
        )

    monkeypatch.setattr(
        "app.services.theclaw.wbr_skill_bridge.lookup_wbr_digest",
        lambda c, m: {"digest_version": "v1"},
    )
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.get_slack_service", lambda: fake_slack)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.call_chat_completion", _fake_call_chat_completion)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime._get_session_service", lambda: fake_session_service)

    await run_theclaw_minimal_dm_turn(slack_user_id="U31", channel="D31", text="WBR for Whoosh US")

    # 1 selection + 2 tool turns (budget=2) = 3 LLM calls
    assert len(calls) == 3
    # Fallback message posted
    assert len(fake_slack.messages) == 1
    assert "processing limit" in fake_slack.messages[0]["text"].lower()


@pytest.mark.asyncio
async def test_runtime_tools_available_every_iteration(monkeypatch):
    """Tools remain available across all loop iterations, not just the first."""
    from app.services.theclaw.slack_minimal_runtime import run_theclaw_minimal_dm_turn
    from tests.theclaw_runtime_test_fakes import FakeSessionService, FakeSlackService

    fake_slack = FakeSlackService()
    fake_session_service = FakeSessionService()
    calls: list[dict[str, object]] = []

    async def _fake_call_chat_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _make_fake_llm_response('{"skill_id":"wbr_summary","confidence":0.95,"reason":"wbr"}')
        if len(calls) == 2:
            return _make_fake_llm_response(
                "",
                tool_calls=[_make_tool_call(call_id="call_1", arguments={"client": "A", "marketplace": "US"})],
            )
        if len(calls) == 3:
            return _make_fake_llm_response(
                "",
                tool_calls=[_make_tool_call(call_id="call_2", arguments={"client": "B", "marketplace": "CA"})],
            )
        return _make_fake_llm_response("Done.\n---THECLAW_STATE_JSON---\n{\"context_updates\":{}}\n---END_THECLAW_STATE_JSON---")

    monkeypatch.setattr("app.services.theclaw.wbr_skill_bridge.lookup_wbr_digest", lambda c, m: {"ok": True})
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.get_slack_service", lambda: fake_slack)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.call_chat_completion", _fake_call_chat_completion)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime._get_session_service", lambda: fake_session_service)

    await run_theclaw_minimal_dm_turn(slack_user_id="U32", channel="D32", text="compare A US and B CA")

    # Verify tools passed on every skill execution call (calls index 1, 2, 3)
    for i in [1, 2, 3]:
        assert calls[i].get("tools") is not None, f"tools missing on call {i}"


# ---------------------------------------------------------------------------
# Execution-state grounding tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_grounding_note_injected_after_tool_execution(monkeypatch):
    """After tool results, a system-level grounding note reminds the LLM no mutations occurred."""
    from app.services.theclaw.slack_minimal_runtime import run_theclaw_minimal_dm_turn
    from tests.theclaw_runtime_test_fakes import FakeSessionService, FakeSlackService

    fake_slack = FakeSlackService()
    fake_session_service = FakeSessionService()
    calls: list[dict[str, object]] = []

    async def _fake_call_chat_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _make_fake_llm_response('{"skill_id":"wbr_summary","confidence":0.95,"reason":"wbr"}')
        if len(calls) == 2:
            return _make_fake_llm_response(
                "",
                tool_calls=[_make_tool_call(arguments={"client": "Whoosh", "marketplace": "US"})],
            )
        return _make_fake_llm_response(
            "Here is the WBR data.\n"
            "---THECLAW_STATE_JSON---\n{\"context_updates\":{}}\n---END_THECLAW_STATE_JSON---"
        )

    monkeypatch.setattr("app.services.theclaw.wbr_skill_bridge.lookup_wbr_digest", lambda c, m: {"ok": True})
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.get_slack_service", lambda: fake_slack)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.call_chat_completion", _fake_call_chat_completion)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime._get_session_service", lambda: fake_session_service)

    await run_theclaw_minimal_dm_turn(slack_user_id="U40", channel="D40", text="WBR for Whoosh US")

    # The final LLM call (calls[2]) should contain the grounding note
    # after the tool result and before the LLM generates its response.
    final_messages = calls[2]["messages"]
    grounding = [m for m in final_messages if m.get("role") == "system" and "only retrieved data" in (m.get("content") or "").lower()]
    assert len(grounding) == 1
    assert "no external systems were modified" in grounding[0]["content"].lower()

    # Grounding note should appear AFTER the tool result, not before.
    tool_idx = next(i for i, m in enumerate(final_messages) if m.get("role") == "tool")
    grounding_idx = next(i for i, m in enumerate(final_messages) if m.get("role") == "system" and "only retrieved data" in (m.get("content") or "").lower())
    assert grounding_idx > tool_idx


@pytest.mark.asyncio
async def test_no_tool_execution_grounding_when_no_tools_called(monkeypatch):
    """When no tools are called, no tool-execution grounding appears, but a
    no-tools-available grounding IS present (since no skill has tools)."""
    from app.services.theclaw.slack_minimal_runtime import run_theclaw_minimal_dm_turn
    from tests.theclaw_runtime_test_fakes import FakeSessionService, FakeSlackService

    fake_slack = FakeSlackService()
    fake_session_service = FakeSessionService()
    calls: list[dict[str, object]] = []

    async def _fake_call_chat_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _make_fake_llm_response('{"skill_id":"none","confidence":0.9,"reason":"general"}')
        return _make_fake_llm_response("Hello! How can I help?")

    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.get_slack_service", lambda: fake_slack)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.call_chat_completion", _fake_call_chat_completion)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime._get_session_service", lambda: fake_session_service)

    await run_theclaw_minimal_dm_turn(slack_user_id="U41", channel="D41", text="hello")

    reply_messages = calls[1]["messages"]
    # No tool-execution grounding (no "only retrieved data" note).
    tool_grounding = [m for m in reply_messages if m.get("role") == "system" and "only retrieved data" in (m.get("content") or "").lower()]
    assert len(tool_grounding) == 0
    # But a no-tools-available grounding IS present.
    no_tools = [m for m in reply_messages if m.get("role") == "system" and "no action tools" in (m.get("content") or "").lower()]
    assert len(no_tools) == 1
    assert fake_slack.messages[0]["text"] == "Hello! How can I help?"


@pytest.mark.asyncio
async def test_grounding_note_per_tool_round_in_multi_step(monkeypatch):
    """Each tool round gets its own grounding note."""
    from app.services.theclaw.slack_minimal_runtime import run_theclaw_minimal_dm_turn
    from tests.theclaw_runtime_test_fakes import FakeSessionService, FakeSlackService

    fake_slack = FakeSlackService()
    fake_session_service = FakeSessionService()
    calls: list[dict[str, object]] = []

    async def _fake_call_chat_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _make_fake_llm_response('{"skill_id":"wbr_summary","confidence":0.95,"reason":"compare"}')
        if len(calls) == 2:
            return _make_fake_llm_response(
                "", tool_calls=[_make_tool_call(call_id="call_1", arguments={"client": "A", "marketplace": "US"})]
            )
        if len(calls) == 3:
            return _make_fake_llm_response(
                "", tool_calls=[_make_tool_call(call_id="call_2", arguments={"client": "B", "marketplace": "CA"})]
            )
        return _make_fake_llm_response("Comparison done.\n---THECLAW_STATE_JSON---\n{\"context_updates\":{}}\n---END_THECLAW_STATE_JSON---")

    monkeypatch.setattr("app.services.theclaw.wbr_skill_bridge.lookup_wbr_digest", lambda c, m: {"ok": True})
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.get_slack_service", lambda: fake_slack)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.call_chat_completion", _fake_call_chat_completion)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime._get_session_service", lambda: fake_session_service)

    await run_theclaw_minimal_dm_turn(slack_user_id="U42", channel="D42", text="compare A US and B CA")

    # Final LLM call (calls[3]) should have 2 grounding notes — one per tool round.
    final_messages = calls[3]["messages"]
    grounding = [m for m in final_messages if m.get("role") == "system" and "only retrieved data" in (m.get("content") or "").lower()]
    assert len(grounding) == 2


@pytest.mark.asyncio
async def test_grounding_note_reflects_mutation_tool(monkeypatch):
    """When a tool is declared as mutating and succeeds, the grounding note says external systems were modified."""
    from app.services.theclaw import skill_tools
    from app.services.theclaw.slack_minimal_runtime import run_theclaw_minimal_dm_turn
    from tests.theclaw_runtime_test_fakes import FakeSessionService, FakeSlackService

    # Temporarily register a fake mutation tool for wbr_summary.
    original_mutates = skill_tools._SKILL_TOOLS["wbr_summary"].get("mutates", {})
    skill_tools._SKILL_TOOLS["wbr_summary"]["mutates"] = {
        "lookup_wbr": True,  # pretend it's a mutation
    }

    fake_slack = FakeSlackService()
    fake_session_service = FakeSessionService()
    calls: list[dict[str, object]] = []

    async def _fake_call_chat_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _make_fake_llm_response('{"skill_id":"wbr_summary","confidence":0.95,"reason":"wbr"}')
        if len(calls) == 2:
            return _make_fake_llm_response(
                "",
                tool_calls=[_make_tool_call(arguments={"client": "Whoosh", "marketplace": "US"})],
            )
        return _make_fake_llm_response(
            "Task created.\n---THECLAW_STATE_JSON---\n{\"context_updates\":{}}\n---END_THECLAW_STATE_JSON---"
        )

    monkeypatch.setattr("app.services.theclaw.wbr_skill_bridge.lookup_wbr_digest", lambda c, m: {"ok": True})
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.get_slack_service", lambda: fake_slack)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.call_chat_completion", _fake_call_chat_completion)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime._get_session_service", lambda: fake_session_service)

    try:
        await run_theclaw_minimal_dm_turn(slack_user_id="U43", channel="D43", text="do something mutating")

        final_messages = calls[2]["messages"]
        grounding = [
            m for m in final_messages
            if m.get("role") == "system" and "modified external systems" in (m.get("content") or "").lower()
        ]
        assert len(grounding) == 1
        # Must NOT say "no external systems were modified"
        assert "no external systems were modified" not in grounding[0]["content"].lower()
        # Must say to report accurately
        assert "report" in grounding[0]["content"].lower()
    finally:
        # Restore original mutates mapping.
        skill_tools._SKILL_TOOLS["wbr_summary"]["mutates"] = original_mutates


@pytest.mark.asyncio
async def test_grounding_note_reflects_mutation_not_executed(monkeypatch):
    """When a mutation tool returns an error, grounding says mutation did not execute."""
    from app.services.theclaw import skill_tools
    from app.services.theclaw.slack_minimal_runtime import run_theclaw_minimal_dm_turn
    from tests.theclaw_runtime_test_fakes import FakeSessionService, FakeSlackService

    original_mutates = skill_tools._SKILL_TOOLS["wbr_summary"].get("mutates", {})
    skill_tools._SKILL_TOOLS["wbr_summary"]["mutates"] = {
        "lookup_wbr": True,
    }

    fake_slack = FakeSlackService()
    fake_session_service = FakeSessionService()
    calls: list[dict[str, object]] = []

    async def _fake_call_chat_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return _make_fake_llm_response('{"skill_id":"wbr_summary","confidence":0.95,"reason":"wbr"}')
        if len(calls) == 2:
            return _make_fake_llm_response(
                "",
                tool_calls=[_make_tool_call(arguments={"client": "Whoosh", "marketplace": "US"})],
            )
        return _make_fake_llm_response("Could not complete the action.")

    # Handler returns an error dict — mutation was not executed.
    monkeypatch.setattr(
        "app.services.theclaw.wbr_skill_bridge.lookup_wbr_digest",
        lambda c, m: {"error": "permission denied"},
    )
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.get_slack_service", lambda: fake_slack)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime.call_chat_completion", _fake_call_chat_completion)
    monkeypatch.setattr("app.services.theclaw.slack_minimal_runtime._get_session_service", lambda: fake_session_service)

    try:
        await run_theclaw_minimal_dm_turn(slack_user_id="U44", channel="D44", text="do something mutating")

        final_messages = calls[2]["messages"]
        grounding = [
            m for m in final_messages
            if m.get("role") == "system" and "did not execute" in (m.get("content") or "").lower()
        ]
        assert len(grounding) == 1
        assert "do not claim" in grounding[0]["content"].lower()
    finally:
        skill_tools._SKILL_TOOLS["wbr_summary"]["mutates"] = original_mutates


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_minimal_digest(*, source_run_at: str | None = None) -> dict:
    d = {
        "digest_version": "wbr_digest_v1",
        "profile": {
            "profile_id": "p1",
            "client_name": "Whoosh",
            "marketplace_code": "US",
            "display_name": "Whoosh US",
        },
        "window": {
            "week_count": 4,
            "window_start": "2026-02-16",
            "window_end": "2026-03-15",
            "week_labels": [],
            "week_ending": "2026-03-15",
        },
        "headline_metrics": {
            "section1": {"total_sales": 1000.0, "total_sales_wow": 0.1},
            "section2": {},
            "section3": {},
        },
        "wins": [],
        "concerns": [],
        "data_quality_notes": [],
        "section_summaries": {},
    }
    if source_run_at:
        d["source_run_at"] = source_run_at
    return d
